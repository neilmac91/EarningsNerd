"""Internal, token-gated job triggers (e.g. Cloud Scheduler → HTTP).

These let an external scheduler kick the Phase 2 filing scan / digest without a separate Cloud Run
job, gated by a shared-secret header (`X-Internal-Token`). There is no user session here, so the
normal `is_admin` gating doesn't apply — auth is the constant-time token compare below.

Each trigger returns 202 immediately and runs the work in a background task (the scan/digest can be
slow; we don't want to hold the request open and hit Cloud Run's HTTP timeout). The Cloud Run *job*
remains the primary, more robust mechanism for production scheduling — see docs/DEPLOYMENT.md.
"""
from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.config import settings
from app.services import filing_scan_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_internal_token(x_internal_token: Optional[str] = Header(None)) -> None:
    """Constant-time shared-secret check. 503 if not configured, 401 if missing/wrong."""
    expected = settings.INTERNAL_JOB_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal job endpoints are not configured.",
        )
    if not x_internal_token or not hmac.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token.")


async def _run_filing_scan() -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        stats = await filing_scan_service.run_filing_scan(db)
        logger.info("Filing scan (internal trigger) complete: %s", stats)
    except Exception:
        logger.exception("Filing scan (internal trigger) failed")
    finally:
        db.close()


async def _run_daily_digest() -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        stats = await filing_scan_service.run_daily_digest(db)
        logger.info("Daily digest (internal trigger) complete: %s", stats)
    except Exception:
        logger.exception("Daily digest (internal trigger) failed")
    finally:
        db.close()


@router.post("/jobs/filing-scan", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_filing_scan(background: BackgroundTasks):
    background.add_task(_run_filing_scan)
    return {"status": "accepted", "job": "filing-scan"}


@router.post("/jobs/filing-digest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_filing_digest(background: BackgroundTasks):
    background.add_task(_run_daily_digest)
    return {"status": "accepted", "job": "filing-digest"}


async def _run_earnings_refresh() -> None:
    from app.database import SessionLocal
    from app.services import earnings_calendar_service

    db = SessionLocal()
    try:
        stats = await earnings_calendar_service.run_refresh(db)
        logger.info("Earnings-calendar refresh (internal trigger) complete: %s", stats.as_dict())
    except Exception:
        logger.exception("Earnings-calendar refresh (internal trigger) failed")
    finally:
        db.close()


async def _run_earnings_alerts() -> None:
    from app.database import SessionLocal
    from app.services import earnings_alert_service

    db = SessionLocal()
    try:
        stats = await earnings_alert_service.send_earnings_day_alerts(db)
        logger.info("Earnings-day alerts (internal trigger) complete: %s", stats)
    except Exception:
        logger.exception("Earnings-day alerts (internal trigger) failed")
    finally:
        db.close()


@router.post("/jobs/earnings-calendar-refresh", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_earnings_refresh(background: BackgroundTasks):
    """Daily ingest: Alpha Vantage bulk estimates + EDGAR 8-K Item 2.02 sweep + rescore."""
    background.add_task(_run_earnings_refresh)
    return {"status": "accepted", "job": "earnings-calendar-refresh"}


@router.post("/jobs/earnings-day-alerts", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_earnings_alerts(background: BackgroundTasks):
    """Send one batched email per opted-in user whose watched companies report today."""
    background.add_task(_run_earnings_alerts)
    return {"status": "accepted", "job": "earnings-day-alerts"}


def _run_backfill_facts() -> None:
    # Sync (CPU/DB-bound) → FastAPI runs it in a threadpool, off the event loop.
    from app.database import SessionLocal
    from app.services import facts_service

    db = SessionLocal()
    try:
        stats = facts_service.backfill_facts(db)
        logger.info("Facts backfill (internal trigger) complete: %s", stats)
    except Exception:
        logger.exception("Facts backfill (internal trigger) failed")
    finally:
        db.close()


@router.post("/jobs/backfill-facts", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_backfill_facts(background: BackgroundTasks):
    background.add_task(_run_backfill_facts)
    return {"status": "accepted", "job": "backfill-facts"}


class NotableFilingsScanRequest(BaseModel):
    """One-off manual kick of the notable-filings EDGAR scan (e.g. the first seed run).

    ``days`` widens the trailing window beyond NOTABLE_FILINGS_SCAN_DAYS. The recurring schedule
    rides the dedicated Cloud Run job (scripts/notable_filings_job.py), not this endpoint.
    """

    days: Optional[int] = Field(default=None, ge=0, le=14)


async def _run_notable_filings_scan(days: Optional[int]) -> None:
    from app.database import SessionLocal
    from app.services import notable_filings_service

    db = SessionLocal()
    try:
        stats = await notable_filings_service.run_scan(db, days=days)
        logger.info("Notable-filings scan (internal trigger) complete: %s", stats.as_dict())
    except Exception:
        logger.exception("Notable-filings scan (internal trigger) failed")
    finally:
        db.close()


@router.post("/jobs/notable-filings-scan", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_notable_filings_scan(
    background: BackgroundTasks, req: NotableFilingsScanRequest | None = None
):
    """Sweep EDGAR full-text search for notable filings into the notable_filings table."""
    days = req.days if req else None
    background.add_task(_run_notable_filings_scan, days)
    return {"status": "accepted", "job": "notable-filings-scan", "days": days}


class SyncCompanyfactsRequest(BaseModel):
    """Multi-Period Analysis (M1): warm the companyfacts-backed period history for a cohort.

    ``tickers`` > ``watchlist_only`` > all companies (optionally capped by ``limit``). One SEC
    request per company through the shared rate limiter, so even the full fleet is minutes.
    """

    tickers: list[str] = Field(default_factory=list)
    watchlist_only: bool = False
    limit: Optional[int] = None
    force: bool = False


async def _run_sync_companyfacts(
    tickers: list[str], watchlist_only: bool, limit: Optional[int], force: bool
) -> None:
    from app.database import SessionLocal
    from app.services import facts_service

    db = SessionLocal()
    try:
        stats = await facts_service.sync_companyfacts_batch(
            db, tickers=tickers or None, watchlist_only=watchlist_only, limit=limit, force=force
        )
        logger.info("Companyfacts sync (internal trigger) complete: %s", stats)
    except Exception:
        logger.exception("Companyfacts sync (internal trigger) failed")
    finally:
        db.close()


@router.post("/jobs/sync-companyfacts", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(_require_internal_token)])
async def trigger_sync_companyfacts(req: SyncCompanyfactsRequest, background: BackgroundTasks):
    tickers = [t.strip().upper() for t in req.tickers if t and t.strip()]
    background.add_task(_run_sync_companyfacts, tickers, req.watchlist_only, req.limit, req.force)
    return {
        "status": "accepted",
        "job": "sync-companyfacts",
        "tickers": len(tickers),
        "watchlist_only": req.watchlist_only,
    }


class PrecomputeRequest(BaseModel):
    """Roadmap A1: warm the cold path by pre-generating analyses for an explicit ticker list.

    Deliberately list-driven (no implicit fleet sweep) — the operator chooses the cohort. ``dry_run``
    returns a coverage report (what would generate vs is already cached) without spending tokens.
    """

    tickers: list[str] = Field(default_factory=list)
    forms: list[str] = Field(default_factory=lambda: ["10-K"])
    force: bool = False
    dry_run: bool = False


async def _run_precompute(tickers: list[str], forms: list[str], force: bool) -> None:
    from app.services import precompute_service

    try:
        out = await precompute_service.precompute(tickers, forms=forms, force=force)
        logger.info("Precompute (internal trigger) complete: %s", out["stats"])
    except Exception:
        logger.exception("Precompute (internal trigger) failed")


@router.post("/jobs/precompute", dependencies=[Depends(_require_internal_token)])
async def trigger_precompute(req: PrecomputeRequest, background: BackgroundTasks, response: Response):
    """Pre-generate (and cache) the latest 10-K/10-Q analyses for the given tickers.

    ``dry_run=true`` runs synchronously and returns the coverage report (no generation). A real run
    is fire-and-forget (202) — generation is slow, so we don't hold the request open."""
    from app.services import precompute_service

    tickers = [t.strip().upper() for t in req.tickers if t and t.strip()]
    if not tickers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="`tickers` must be a non-empty list.")
    forms = [f.strip().upper() for f in req.forms if f and f.strip()] or ["10-K"]

    if req.dry_run:
        # A dry run does a couple of (serial) SEC round-trips per job, so a large cohort would blow
        # the request/gateway timeout. Cap the synchronous preview; use a real run for the full fleet.
        if len(tickers) * len(forms) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dry run is capped at 100 total jobs (tickers x forms) to avoid gateway timeouts.",
            )
        out = await precompute_service.precompute(tickers, forms=forms, force=False, dry_run=True)
        return {"status": "ok", "job": "precompute", "dry_run": True, **out}

    response.status_code = status.HTTP_202_ACCEPTED
    background.add_task(_run_precompute, tickers, forms, req.force)
    return {"status": "accepted", "job": "precompute", "tickers": len(tickers), "forms": forms}
