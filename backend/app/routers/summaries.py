from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import json
from pydantic import BaseModel, Field, field_validator
import logging
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from app.services.posthog_client import capture_copilot_inference
from app.services.llm_pricing import estimate_inference_cost_usd

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import (
    Filing,
    Summary,
    User,
    SummaryGenerationProgress,
)
from app.routers.auth import get_current_user_optional
from app.dependencies import require_copilot_or_taste
from app.services.entitlements import get_entitlements
from app.services.export_service import export_service
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.subscription_service import (
    check_qa_limit,
    get_current_month,
    increment_user_copilot_free_taste,
    increment_user_qa,
)
from app.services.copilot_service import answer_filing_question, snapshot_filing
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

    @field_validator("history")
    @classmethod
    def _bound_history(cls, v: Optional[list[dict]]) -> Optional[list[dict]]:
        """Cap history size so a malicious client can't stuff the prompt.

        ``question`` is already length-bounded, but ``history`` is free-form: without this a single
        multi-MB turn (or a huge array) would be accepted and fed toward the model context. We keep
        only the most recent ``COPILOT_HISTORY_MAX_ITEMS`` turns and truncate each turn's ``content``
        to ``COPILOT_HISTORY_ITEM_CHAR_CAP`` chars. (The generator also re-truncates as defense in
        depth; see ``copilot_service._build_messages``.)
        """
        if not v:
            return v
        cap = settings.COPILOT_HISTORY_ITEM_CHAR_CAP
        trimmed = v[-settings.COPILOT_HISTORY_MAX_ITEMS:]
        out: list[dict] = []
        for turn in trimmed:
            if isinstance(turn, dict):
                content = turn.get("content")
                if isinstance(content, str) and len(content) > cap:
                    turn = {**turn, "content": content[:cap]}
            out.append(turn)
        return out

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


def _meter_qa_best_effort(user_id: int, is_free_taste: bool = False) -> None:
    """Meter one answered Copilot question in a fresh DB session (best-effort).

    Free users (``is_free_taste``) decrement their lifetime free-taste allowance; Pro users
    increment the monthly fair-use ``qa_count``. Called from inside the SSE generator, which runs
    after the request's DB session may already be gone (see ``snapshot_filing``), so it opens its own
    short-lived session. A metering failure must never break the answer stream, so errors are
    swallowed (and logged).
    """
    db = SessionLocal()
    try:
        if is_free_taste:
            increment_user_copilot_free_taste(user_id, db)
        else:
            increment_user_qa(user_id, get_current_month(), db)
    except Exception:  # noqa: BLE001 — metering must not break the answer stream
        logger.warning("Failed to meter Copilot QA for user %s", user_id, exc_info=True)
    finally:
        db.close()


def _emit_copilot_cost_best_effort(
    user_id: int, filing_id: int, ticker, event: dict, is_free_taste: bool = False
) -> None:
    """Emit a Copilot answer's token usage + estimated inference cost to PostHog (roadmap 2.1).

    Keyed on ``str(user_id)`` — the same id the frontend identifies on — so it joins the person's
    journey without a separate alias. Best-effort: telemetry must never break the answer stream, so
    a missing-usage answer (provider returned none) is a quiet no-op and any failure is swallowed.
    """
    try:
        usage = event.get("usage") or {}
        if not usage:
            return
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        cache_hit_tokens = usage.get("cache_hit_tokens")
        cache_miss_tokens = usage.get("cache_miss_tokens")
        capture_copilot_inference(
            distinct_id=str(user_id),
            model=usage.get("model"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens"),
            cache_hit_tokens=cache_hit_tokens,
            cache_miss_tokens=cache_miss_tokens,
            cost_usd=estimate_inference_cost_usd(
                prompt_tokens,
                completion_tokens,
                cache_hit_tokens=cache_hit_tokens,
                cache_miss_tokens=cache_miss_tokens,
            ),
            filing_id=filing_id,
            ticker=ticker,
            kind=event.get("kind"),
            grounded=event.get("grounded"),
            is_free_taste=is_free_taste,
        )
    except Exception:  # noqa: BLE001 — telemetry must not break the answer stream
        logger.warning("Failed to emit Copilot cost telemetry for user %s", user_id, exc_info=True)


@router.post("/filing/{filing_id}/ask-stream")
async def ask_filing_stream(
    filing_id: int,
    body: AskRequest,
    request: Request,
    current_user: User = Depends(require_copilot_or_taste),
    db: Session = Depends(get_db),
):
    """Grounded single-filing Q&A with a streaming (SSE) response.

    Open to Pro (full "copilot" entitlement) and to Free users within their lifetime free-taste
    allowance (roadmap 2.2); the dependency 403s a Free user once the taste is spent. The model
    answers using only this filing's cached content; the server verifies each cited excerpt against
    the filing text (reusing the Trace-to-Source provenance helpers) and emits honest verified/cited
    labels plus ``#:~:text=`` deep links. Excluded from the timeout middleware by the ``*stream*``
    name rule. Metering: Pro counts against the monthly fair-use cap; Free decrements the lifetime
    free-taste counter — both only on a successful answer.
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

    # Free users reach here on their lifetime free-taste allowance (gated upstream by
    # require_copilot_or_taste); they meter the lifetime counter, not the monthly cap. The monthly
    # fair-use cap is a Pro-only protection against runaway volume.
    is_free_taste = not get_entitlements(current_user).copilot
    if not is_free_taste:
        allowed, count, cap = check_qa_limit(current_user, db)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"You've reached this month's fair-use limit of {cap} Copilot questions. "
                    "It resets at the start of next month."
                ),
            )
    # Snapshot the filing into detached plain objects up front. The SSE generator below runs after
    # this request's session may be gone, so it must never touch the ORM (mirrors
    # generate_summary_stream's eager value capture).
    filing_ctx = snapshot_filing(filing)
    user_id = current_user.id

    async def event_stream():
        # Meter on the first successful completion only: a failed/aborted generation (an ``error``
        # event, or a client disconnect before completion) must NOT burn the user's fair-use quota.
        # The not-disclosed path still emits ``complete`` (the model did its job), so it counts.
        metered = False
        async for event in answer_filing_question(
            filing=filing_ctx,
            question=body.question,
            history=body.history,
        ):
            if not metered and event.get("type") == "complete":
                # Offload the synchronous DB write to a worker thread so it never blocks the event
                # loop mid-stream (it opens its own fresh SessionLocal, so it's thread-safe). Free
                # users decrement the lifetime free-taste counter; Pro the monthly fair-use count.
                await run_in_threadpool(_meter_qa_best_effort, user_id, is_free_taste)
                metered = True
                # Per-answer inference-cost telemetry (roadmap 2.1) — token usage rides the complete
                # event; cost is estimated here. Non-blocking (PostHog batches) + best-effort.
                _emit_copilot_cost_best_effort(
                    user_id,
                    filing_id,
                    getattr(getattr(filing_ctx, "company", None), "ticker", None),
                    event,
                    is_free_taste,
                )
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
