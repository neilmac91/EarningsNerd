from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import json
from pydantic import BaseModel, Field
import logging
from fastapi.responses import Response, StreamingResponse

from app.database import get_db
from app.models import (
    Filing,
    Summary,
    User,
    SummaryGenerationProgress,
)
from app.routers.auth import get_current_user_optional
from app.dependencies import require_entitlement
from app.services.entitlements import get_entitlements
from app.services.export_service import export_service
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.subscription_service import (
    check_qa_limit,
    get_current_month,
    increment_user_qa,
)
from app.services.copilot_service import answer_filing_question
from app.services.summary_generation_service import (
    mark_stale_progress_as_error,
    progress_as_dict,
)
from app.services.summary_pipeline import stream_filing_summary, to_sse
from app.services.provenance_service import enrich_summary_provenance
from app.services.change_report_service import build_change_report

router = APIRouter()
logger = logging.getLogger(__name__)
SUMMARY_LIMITER = RateLimiter(limit=5, window_seconds=60)
# Copilot Q&A is cheaper per call than a summary but still hits the model — allow a higher
# burst than summaries while still throttling abuse (per IP, sliding window).
ASK_LIMITER = RateLimiter(limit=10, window_seconds=60)


class AskRequest(BaseModel):
    """Body for the "Ask this Filing" Copilot endpoint."""
    question: str = Field(..., min_length=1, max_length=2000)
    history: Optional[list[dict]] = None

class SummaryResponse(BaseModel):
    id: int
    filing_id: int
    business_overview: Optional[str]
    financial_highlights: Optional[dict]
    risk_factors: Optional[list]
    management_discussion: Optional[str]
    key_changes: Optional[str]
    raw_summary: Optional[dict]

    class Config:
        from_attributes = True

@router.get("/filing/{filing_id}/progress")
async def get_summary_progress(
    filing_id: int,
    db: Session = Depends(get_db)
):
    """Get progress status for summary generation"""
    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        # Summary exists, return completed status
        return {
            "stage": "completed",
            "elapsedSeconds": 0
        }

    progress = (
        db.query(SummaryGenerationProgress)
        .filter(SummaryGenerationProgress.filing_id == filing_id)
        .first()
    )
    if progress:
        # Surface orphaned/stalled generations as a retryable error instead of an
        # eternal "generating" state if the background task died without finishing.
        if mark_stale_progress_as_error(progress):
            db.commit()
        return progress_as_dict(progress)

    return {"stage": "pending", "elapsedSeconds": 0}

@router.post("/filing/{filing_id}/generate-stream")
async def generate_summary_stream(
    filing_id: int,
    request: Request,
    force: bool = False,
    entry_point: Optional[str] = None,
    ph_id: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Generate AI summary with streaming response (guests allowed).

    Args:
        force: If True, delete existing summary and regenerate from scratch.
               Use this for "Regenerate Analysis" functionality.
        entry_point: Where the visitor entered the funnel (forwarded by the
                     frontend for activation analytics, e.g. "homepage").
        ph_id: The client's PostHog distinct_id, so server-side funnel events
               join with frontend events on the same person.
    """
    # Use user ID for authenticated users, IP for guests
    client_host = request.client.host if request.client else "unknown"
    user_id_log = current_user.id if current_user else "Guest"
    logger.info(f"[stream:{filing_id}] Incoming stream request from {user_id_log} (IP: {client_host}, force={force})")

    rate_limit_key = f"summary:{current_user.id}" if current_user else f"summary:guest:{client_host}"

    enforce_rate_limit(
        request,
        SUMMARY_LIMITER,
        rate_limit_key,
        error_detail="Too many summary requests. Please try again shortly.",
    )
    # Eagerly load content_cache and company relationship to avoid detached session issues
    filing = db.query(Filing).options(
        joinedload(Filing.content_cache),
        joinedload(Filing.company)
    ).filter(Filing.id == filing_id).first()

    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        if force:
            # Force regeneration: delete existing summary and related data
            logger.info(f"[stream:{filing_id}] Force regeneration requested - deleting existing summary")
            db.delete(summary)

            # Also clear XBRL data to get fresh data
            if filing.xbrl_data is not None:
                filing.xbrl_data = None
                logger.info(f"[stream:{filing_id}] Cleared XBRL data for regeneration")

            # Clear progress record
            progress = db.query(SummaryGenerationProgress).filter(
                SummaryGenerationProgress.filing_id == filing_id
            ).first()
            if progress:
                db.delete(progress)

            db.commit()
        else:
            # Return existing summary as JSON
            async def existing_summary():
                payload = {
                    'type': 'complete',
                    'summary': summary.business_overview,
                    'summary_id': summary.id,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            return StreamingResponse(
                existing_summary(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable buffering for Cloud Run/nginx
                }
            )

    # S5: per-IP daily quota for guests (flagged). Only reached when we're actually going to
    # generate (a cached summary returned above and is not counted). Never gates the first
    # summary — a new IP is always under the cap — and fails open if Redis is down.
    from app.config import settings as _settings
    # Skip when the client IP is unresolvable ("unknown" from a proxy/network config) — all such
    # guests would otherwise share one quota key and exhaust the daily limit collectively.
    if current_user is None and _settings.ENABLE_GUEST_DAILY_QUOTA and client_host != "unknown":
        from app.services.guest_quota import check_and_increment_guest_quota

        allowed, count = await check_and_increment_guest_quota(
            client_host, _settings.GUEST_DAILY_SUMMARY_LIMIT
        )
        if not allowed:
            logger.info(f"[stream:{filing_id}] Guest {client_host} over daily quota ({count}/{_settings.GUEST_DAILY_SUMMARY_LIMIT})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"You've reached today's free limit of {_settings.GUEST_DAILY_SUMMARY_LIMIT} "
                    "summaries. Create a free account to generate more."
                ),
            )

    user_id = current_user.id if current_user else None
    logger.info(f"[stream:{filing_id}] Starting summary stream for user {user_id}")

    # Activation funnel telemetry context. Plain values are captured eagerly here —
    # the pipeline generator below runs after this request's DB session is gone, so ORM
    # attribute access inside it would be unsafe. Prefer the client's PostHog
    # distinct_id so server events join frontend events on the same person.
    telemetry_distinct_id = (ph_id or "")[:200] or (
        str(current_user.id) if current_user else f"guest:{client_host}"
    )
    telemetry_entry_point = (entry_point or "")[:64] or None
    telemetry_ctx = {
        "filing_id": filing_id,
        "filing_type": filing.filing_type,
        "ticker": filing.company.ticker if filing.company else None,
        "user_type": "authenticated" if current_user else "guest",
        "forced": force,
    }

    async def event_stream():
        async for event in stream_filing_summary(
            filing_id=filing_id,
            current_user=current_user,
            user_id=user_id,
            telemetry_distinct_id=telemetry_distinct_id,
            telemetry_entry_point=telemetry_entry_point,
            telemetry_ctx=telemetry_ctx,
        ):
            yield to_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for Cloud Run/nginx
        }
    )


@router.post("/filing/{filing_id}/ask-stream")
async def ask_filing_stream(
    filing_id: int,
    body: AskRequest,
    request: Request,
    current_user: User = Depends(require_entitlement("copilot", "Ask this Filing")),
    db: Session = Depends(get_db),
):
    """Grounded single-filing Q&A with a streaming (SSE) response. Pro-only ("copilot" entitlement).

    The model answers using only this filing's cached content; the server verifies each cited excerpt
    against the filing text (reusing the Trace-to-Source provenance helpers) and emits honest
    verified/cited labels plus ``#:~:text=`` deep links. Excluded from the timeout middleware by the
    ``*stream*`` name rule. Metering: counts against the Pro fair-use monthly cap.
    """
    enforce_rate_limit(
        request,
        ASK_LIMITER,
        f"ask:{current_user.id}",
        error_detail="Too many questions. Please try again shortly.",
    )

    filing = db.query(Filing).options(
        joinedload(Filing.content_cache),
        joinedload(Filing.company),
    ).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Fair-use soft cap (Pro only reaches here). 429 when over, otherwise meter this question.
    allowed, count, cap = check_qa_limit(current_user, db)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"You've reached this month's fair-use limit of {cap} Copilot questions. "
                "It resets at the start of next month."
            ),
        )
    increment_user_qa(current_user.id, get_current_month(), db)

    async def event_stream():
        async for event in answer_filing_question(
            filing=filing,
            question=body.question,
            history=body.history,
        ):
            yield to_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for Cloud Run/nginx
        }
    )

@router.get("/filing/{filing_id}", response_model=SummaryResponse)
async def get_summary(filing_id: int, db: Session = Depends(get_db)):
    """Get summary for a filing.

    Risk factors are enriched with Trace-to-Source provenance (a deep link to the original SEC
    filing plus an honest verified/cited label) at serialization time, so every existing summary
    gains provenance without a migration or regeneration.
    """
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()

    if not summary:
        # Return empty summary instead of 404 to allow frontend to trigger generation
        return {
            "id": 0,
            "filing_id": filing_id,
            "business_overview": None,
            "financial_highlights": None,
            "risk_factors": None,
            "management_discussion": None,
            "key_changes": None,
            "raw_summary": None
        }

    # Load the filing (with its cached content) to verify excerpts and build EDGAR deep links.
    filing = (
        db.query(Filing)
        .options(joinedload(Filing.content_cache))
        .filter(Filing.id == filing_id)
        .first()
    )

    # SEC-verified XBRL values, used to mark financial metrics as "verified". Best-effort: any
    # extraction issue must never break the summary response.
    xbrl_standardized = None
    if filing is not None and getattr(filing, "xbrl_data", None):
        try:
            from app.services.edgar.compat import xbrl_service
            xbrl_standardized = xbrl_service.extract_standardized_metrics(filing.xbrl_data)
        except Exception:
            logger.warning(
                f"[summary:{filing_id}] XBRL standardization for provenance failed; continuing",
                exc_info=True,
            )

    return enrich_summary_provenance(summary, filing, xbrl_standardized)

@router.get("/filing/{filing_id}/what-changed")
async def get_what_changed(filing_id: int, db: Session = Depends(get_db)):
    """Deterministic period-over-period change report for a filing vs its prior same-form filing.

    Reports financial-metric deltas, new/resolved risk factors, and management's key-changes
    narrative. DB-only, no LLM — cheap to serve. Returns ``has_changes: false`` when there's no
    prior filing to compare against.
    """
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    return build_change_report(db, filing)


@router.get("/filing/{filing_id}/export/pdf")
async def export_summary_pdf(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export summary as PDF (Pro feature)"""

    # Require authentication for exports
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Gate on the centralised entitlement (Subscription-derived, is_pro mirror as fallback).
    if not get_entitlements(current_user).can_export:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PDF export is a Pro feature. Upgrade to Pro to access this feature."
        )

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    try:
        pdf_bytes = await export_service.export_pdf(summary, filing)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filing.company.name}_{filing.filing_type}_{filing.filing_date.strftime("%Y%m%d") if filing.filing_date else "summary"}.pdf"'
            }
        )
    except Exception as e:
        logger.error(f"PDF export failed for filing {filing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate PDF. Please try again later."
        )

@router.get("/filing/{filing_id}/export/csv")
async def export_summary_csv(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export summary financial metrics as CSV (Pro feature)"""

    # Require authentication for exports
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Gate on the centralised entitlement (Subscription-derived, is_pro mirror as fallback).
    if not get_entitlements(current_user).can_export:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSV export is a Pro feature. Upgrade to Pro to access this feature."
        )

    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")

    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    try:
        csv_content = export_service.generate_csv(summary, filing)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filing.company.name}_{filing.filing_type}_{filing.filing_date.strftime("%Y%m%d") if filing.filing_date else "summary"}.csv"'
            }
        )
    except Exception as e:
        logger.error(f"CSV export failed for filing {filing_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate CSV. Please try again later."
        )
