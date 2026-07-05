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
from app.services.rate_limiter import RateLimiter, enforce_rate_limit

router = APIRouter()
logger = logging.getLogger(__name__)

COVERAGE_LIMITER = RateLimiter(limit=30, window_seconds=60)
DATASET_LIMITER = RateLimiter(limit=30, window_seconds=60)

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
