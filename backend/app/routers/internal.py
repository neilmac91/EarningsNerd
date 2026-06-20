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

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

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
