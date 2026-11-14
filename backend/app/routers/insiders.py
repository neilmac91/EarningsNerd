"""Insider-activity endpoint (SEC Form 4), served from the stored scan (ADR 0009)."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import require_beta
from app.models import User
from app.schemas.insiders import InsiderActivityResponse
from app.services import insider_scan_service, insider_service
from app.services.filing_list_service import release_request_session
from app.services.rate_limiter import RateLimiter, enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

# Off unless settings.ENABLE_INSIDER_ACTIVITY (404), and then for a signed-in beta account only. A request reads
# the database and makes no request to SEC: the scan that fills the store runs on the task worker. A page polls
# while a scan is under way (every 8 s for at most 3 minutes), so 30 a minute per account is one reader on a few
# company pages; the account, not the IP, is the key, since every caller is signed in.
_insiders_rate_limiter = RateLimiter(limit=30, window_seconds=60)
# On-visit handoffs of a scan step, per process, whoever asks. The service hands one off only when a step would do
# something and few enough issuers are scanning (``insider_service.read_insider_activity``), and a task's name
# carries the issuer and a one-minute bucket, so one issuer is one task a minute. This is the backstop behind
# both: the scan rows show a new scan only once its first step has run.
_scan_handoffs = RateLimiter(limit=4, window_seconds=60)
# Issuers this process handed off within the task name's bucket: a page that polls every few seconds while its
# scan's first step is still queued asks for the same task again, which the queue would drop anyway.
_handed_off: dict[str, float] = {}
_HANDED_OFF_ENTRIES = 512


async def _hand_off(cik: str) -> None:
    now = time.monotonic()
    if now < _handed_off.get(cik, 0.0):
        return
    if not _scan_handoffs.allow("insider-scan"):
        return   # left unrecorded, so the next request after the window hands it off
    if not await insider_scan_service.request_scan(cik):
        return   # the queue did not take it: unrecorded too, so the reader's next request asks again
    if len(_handed_off) >= _HANDED_OFF_ENTRIES:
        _handed_off.pop(next(iter(_handed_off)), None)
    _handed_off[cik] = now + insider_scan_service.VISIT_DEDUPE_SECONDS


def _require_insider_activity() -> None:
    # A route dependency runs before query validation and before the session is read, so while off a GET
    # answers exactly like an unknown path (FastAPI's own 404 body), whatever the query string and whoever asks.
    # Other methods still get 405, and the route stays in the OpenAPI schema; neither reaches the database.
    if not settings.ENABLE_INSIDER_ACTIVITY:
        raise HTTPException(status_code=404, detail="Not Found")


@router.get(
    "/{ticker}/insiders",
    response_model=InsiderActivityResponse,
    dependencies=[Depends(_require_insider_activity)],
)
async def get_company_insiders(
    request: Request,
    ticker: str,
    window_days: int = Query(
        90,
        ge=1,
        le=730,
        description="Trailing window (days) for the buy/sell aggregation.",
    ),
    current_user: User = Depends(require_beta),
    db: Session = Depends(get_db),
) -> InsiderActivityResponse:
    """A company's stored insider (Form 4) open-market trades over a trailing window: a buy/sell signal with a
    Rule 10b5-1 split, the most recent trades, and how far the background scan has got. Always answers from the
    database; ``scan.retry_after_seconds`` says when asking again can show more. 404 unless
    ENABLE_INSIDER_ACTIVITY; a signed-in beta account only."""
    enforce_rate_limit(
        request,
        _insiders_rate_limiter,
        f"insiders:{current_user.id}",
        error_detail="Too many insider-activity requests. Please retry in a minute.",
        include_client_ip=False,
    )

    def read() -> dict | None:
        try:
            return insider_service.read_insider_activity(db, ticker, window_days=window_days)
        finally:
            release_request_session(db)   # before the queue await below

    activity = await run_in_threadpool(read)
    if activity is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if activity.pop("scan_due"):
        await _hand_off(activity["cik"])
    return activity
