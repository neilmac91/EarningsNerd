"""Multi-Period Analysis endpoints (`/api/analysis`) — the Pro flagship surface.

- ``GET /{ticker}/coverage`` — auth-only (any logged-in user: the free teaser needs real period
  chips). Lazily ingests the company's SEC companyfacts history (one rate-limited request, 24h
  TTL, per-company dedup) and returns the selectable periods per mode.
- ``POST /{ticker}/dataset`` — Pro (``can_analyze_trends``). The deterministic dataset: aligned
  grid, YoY/QoQ/CAGR, inflection signals, citation markers. Tables and charts render from this
  alone; no AI involved.
- ``POST /{ticker}/stream`` — Pro. SSE narrative generation (M3): cache-first (no meter, no AI on
  a hit), fair-use metered on fresh completions only.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi import Response as FastAPIResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import require_entitlement
from app.models import Company, User
from app.routers.auth import get_current_user
from app.schemas.analysis import (
    CoverageLimits,
    CoverageResponse,
    DatasetRequest,
    StreamRequest,
)
from app.services import facts_service, trend_analysis_service
from app.services.llm_pricing import estimate_inference_cost_usd
from app.services.posthog_client import capture_analysis_inference
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.subscription_service import (
    check_analysis_limit,
    get_current_month,
    increment_user_analysis,
)
from app.services.summary_pipeline import to_sse

router = APIRouter()
logger = logging.getLogger(__name__)

COVERAGE_LIMITER = RateLimiter(limit=30, window_seconds=60)
DATASET_LIMITER = RateLimiter(limit=30, window_seconds=60)
# Fresh narrative generations hit the model; cached re-serves are cheap but ride the same route.
STREAM_LIMITER = RateLimiter(limit=10, window_seconds=60)

# How long the coverage request waits for a first-touch companyfacts sync before answering
# `syncing: true` and letting the fetch finish in the background (frontend budget is ~30s).
COVERAGE_SYNC_WAIT_SECONDS = 20.0

# Strong references to background sync tasks (the summary_pipeline._spawn_background pattern) so
# the event loop can't garbage-collect one mid-fetch after we answer `syncing: true`.
_background_syncs: set[asyncio.Task] = set()


def _limits() -> CoverageLimits:
    return CoverageLimits(
        annual=settings.ANALYSIS_MAX_ANNUAL_PERIODS,
        quarterly=settings.ANALYSIS_MAX_QUARTERLY_PERIODS,
    )


def _get_company(db: Session, ticker: str) -> Company:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if company is None:
        # The frontend resolves a ticker through GET /api/companies/{ticker} (get-or-create from
        # EDGAR) before calling analysis endpoints, so a miss here means a genuinely unknown ticker.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


async def _ingest_with_own_session(company_id: int) -> dict:
    """Run the companyfacts ingest on a dedicated session so it can safely outlive the request
    (the coverage endpoint answers `syncing: true` after 20s and lets this finish)."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        company = db.get(Company, company_id)
        if company is None:
            return {"synced": False}
        return await facts_service.ingest_companyfacts(db, company)
    finally:
        db.close()


@router.get("/{ticker}/coverage", response_model=CoverageResponse)
async def get_coverage(
    ticker: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Selectable periods per mode for a company (triggers the lazy companyfacts sync)."""
    enforce_rate_limit(
        request,
        COVERAGE_LIMITER,
        f"analysis-coverage:{current_user.id}",
        error_detail="Too many coverage requests. Please retry in a minute.",
    )
    company = _get_company(db, ticker)

    task = asyncio.create_task(_ingest_with_own_session(company.id))
    _background_syncs.add(task)
    task.add_done_callback(_background_syncs.discard)
    done, _pending = await asyncio.wait({task}, timeout=COVERAGE_SYNC_WAIT_SECONDS)

    sync: dict = {"synced": False}
    if task in done:
        try:
            sync = task.result()
        except Exception:  # noqa: BLE001 - a failed sync degrades to whatever the DB already has
            logger.exception("companyfacts sync failed inside coverage for %s", company.ticker)
    else:
        # First-touch sync still running — serve what exists and tell the client to retry.
        periods = trend_analysis_service.available_periods(db, company.id)
        return CoverageResponse(
            ticker=company.ticker,
            company_name=company.name,
            supported=True,
            syncing=True,
            synced_at=None,
            annual=periods["annual"],
            quarterly=periods["quarterly"],
            limits=_limits(),
        )

    db.expire(company)  # the ingest wrote facts_synced_at through its own session
    periods = trend_analysis_service.available_periods(db, company.id)
    has_any = bool(periods["annual"] or periods["quarterly"])
    reason = None
    if not has_any:
        reason = "ifrs_filer" if sync.get("unsupported_ifrs") else "no_facts"
    return CoverageResponse(
        ticker=company.ticker,
        company_name=company.name,
        supported=has_any,
        reason=reason,
        syncing=False,
        synced_at=company.facts_synced_at.isoformat() if company.facts_synced_at else None,
        annual=periods["annual"],
        quarterly=periods["quarterly"],
        limits=_limits(),
    )


@router.post("/{ticker}/dataset")
async def get_dataset(
    ticker: str,
    body: DatasetRequest,
    request: Request,
    current_user: User = Depends(require_entitlement("can_analyze_trends", "Multi-Period Analysis")),
    db: Session = Depends(get_db),
):
    """The deterministic N-period dataset (grid + charts render from this alone)."""
    enforce_rate_limit(
        request,
        DATASET_LIMITER,
        f"analysis-dataset:{current_user.id}",
        error_detail="Too many analysis requests. Please retry in a minute.",
    )
    company = _get_company(db, ticker)
    try:
        dataset = trend_analysis_service.build_dataset(
            db, company, body.mode, body.start_period, body.end_period
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return dataset


def _meter_analysis_best_effort(user_id: int) -> None:
    """Meter one FRESH analysis generation in a fresh DB session (best-effort — a metering failure
    must never break the stream the user already received)."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        increment_user_analysis(user_id, get_current_month(), db)
    except Exception:  # noqa: BLE001 - metering must not break the stream
        logger.warning("Failed to meter analysis for user %s", user_id, exc_info=True)
    finally:
        db.close()


def _emit_analysis_cost_best_effort(user_id: int, ticker: str, mode: str, event: dict) -> None:
    """Per-generation inference-cost telemetry (PostHog). Best-effort, never breaks the stream."""
    try:
        usage = event.get("usage") or {}
        if not usage:
            return
        capture_analysis_inference(
            distinct_id=str(user_id),
            model=usage.get("model"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            cache_hit_tokens=usage.get("cache_hit_tokens"),
            cache_miss_tokens=usage.get("cache_miss_tokens"),
            cost_usd=estimate_inference_cost_usd(
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                cache_hit_tokens=usage.get("cache_hit_tokens"),
                cache_miss_tokens=usage.get("cache_miss_tokens"),
            ),
            ticker=ticker,
            mode=mode,
            n_periods=event.get("n_periods"),
            grounded=event.get("grounded"),
        )
    except Exception:  # noqa: BLE001 - telemetry must not break the stream
        logger.warning("Failed to emit analysis cost telemetry for user %s", user_id, exc_info=True)


@router.post("/{ticker}/stream")
async def stream_analysis(
    ticker: str,
    body: StreamRequest,
    request: Request,
    current_user: User = Depends(require_entitlement("can_analyze_trends", "Multi-Period Analysis")),
    db: Session = Depends(get_db),
):
    """Streamed (SSE) AI trend narrative over the deterministic dataset.

    Cache-first: a stored narrative whose prompt_version + dataset fingerprint still match is
    re-served instantly (no model call, no meter); ``force`` regenerates. Metering counts only
    fresh "analysis" completions against the monthly fair-use cap — a failed or aborted generation
    never burns quota. Excluded from the timeout middleware by the ``*stream*`` name rule.
    """
    enforce_rate_limit(
        request,
        STREAM_LIMITER,
        f"analysis-stream:{current_user.id}",
        error_detail="Too many analysis generations. Please retry in a minute.",
    )
    company = _get_company(db, ticker)

    allowed, _count, cap = check_analysis_limit(current_user, db)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"You've reached this month's fair-use limit of {cap} analyses. "
                "It resets at the start of next month."
            ),
        )

    # Snapshot everything the generator needs — it runs after this request's session is gone.
    company_id = company.id
    ticker_value = company.ticker
    user_id = current_user.id

    async def event_stream():
        metered = False
        async for event in trend_analysis_service.stream_trend_narrative(
            company_id=company_id,
            mode=body.mode,
            start_period=body.start_period,
            end_period=body.end_period,
            force=body.force,
            user_id=user_id,
        ):
            if (
                not metered
                and event.get("type") == "complete"
                and event.get("kind") == "analysis"
                and not event.get("cached")
            ):
                await run_in_threadpool(_meter_analysis_best_effort, user_id)
                metered = True
                _emit_analysis_cost_best_effort(user_id, ticker_value, body.mode, event)
            yield to_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable buffering for Cloud Run/nginx
        },
    )


@router.get("/export/{analysis_id}/pdf")
async def export_analysis_pdf(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export a completed analysis as PDF (Pro `can_export`, the summaries export pattern)."""
    from app.models import TrendAnalysis
    from app.services.entitlements import get_entitlements
    from app.services.export_service import export_service

    if not get_entitlements(current_user).can_export:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PDF export is a Pro feature. Upgrade to Pro to access this feature.",
        )
    analysis = db.get(TrendAnalysis, analysis_id)
    if analysis is None or not analysis.narrative_md:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    company = db.get(Company, analysis.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    try:
        pdf_bytes = await export_service.export_analysis_pdf(analysis, company)
    except Exception:
        logger.exception("Analysis PDF export failed for analysis %s", analysis_id)
        raise HTTPException(
            status_code=500, detail="Failed to generate PDF. Please try again later."
        )
    filename = f"{company.ticker}_multi_period_{analysis.mode}_{analysis.period_key}.pdf".replace(
        "..", "-"
    )
    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
