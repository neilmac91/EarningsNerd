"""Company filing lists behind ``GET /api/filings/company/{ticker}`` (``app/routers/filings.py``).

Moved verbatim from the router so it stays HTTP only: the B2 freshness cache, the DB-first
background refresh, the on-visit history backfill, the CIK-first company persistence on a miss, the
filing-type defaults, the cached reads and the cold live fetch's persistence. The router keeps the
SEC awaits, the ``BackgroundTasks`` scheduling, the durable-task handoff (it does no database work),
the error mapping and the fallback log lines; the skip and background-failure warnings moved here
with their code, so they now log as ``app.services.filing_list_service``.

The background tasks open their own short-lived sessions. Everything else is one synchronous unit
on the request's session, run where the router used to run it (on the event loop). The request's
pooled connection is released before every SEC and queue await and before the route returns
(:func:`release_request_session`; ``tests/unit/test_cached_filings_pool_lifetime.py`` and
``tests/unit/test_filings_endpoint_db_first.py::test_sec_network_phases_do_not_retain_queuepool_connections``).
A unit that ends the request's database work builds the response DTOs with the router's converter
before it closes: after a commit the rows are expired, and a lazy read after the close would check
a connection out again (``lessons/ops-release-cached-filing-reads-before-yield.md``).
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal
from app.models import Company, Filing
from app.services.company_resolution import resolve_or_create_company_by_cik
from app.services.edgar.compat import sec_edgar_service
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Constants for filings endpoint configuration
SEC_REQUEST_TIMEOUT_SECONDS = 20.0  # Timeout for SEC EDGAR requests (within frontend's 30s limit)
CACHED_FILINGS_LIMIT = 20  # Maximum number of cached filings to return as fallback

# B2: stale-within-TTL cache for the company filings list. The hot path already persists every SEC
# fetch into the Filing table, so a recently-synced ticker can serve its list straight from the DB
# (~ms) instead of paying the 3-5s SEC round-trip on every load. In-memory by design — single Cloud
# Run instance, Redis off in prod (mirrors companies.py's _quote_cache). Staleness is bounded by the
# TTL; the new-filing ALERT path (filing-scan job) is independent, so users are still notified of new
# filings even if this list lags by up to the TTL.
FILINGS_LIST_TTL = timedelta(hours=3)
MAX_FILINGS_SYNC_ENTRIES = 2000  # bound memory; oldest (ticker,types) key is evicted past this
_filings_synced_at: Dict[Tuple[str, Tuple[str, ...]], datetime] = {}


def filings_cache_fresh(ticker: str, types_list: List[str]) -> bool:
    """True when this (ticker, types) was synced from SEC within the TTL."""
    synced = _filings_synced_at.get((ticker, tuple(types_list)))
    return synced is not None and (utcnow() - synced) < FILINGS_LIST_TTL


def _mark_filings_synced(ticker: str, types_list: List[str]) -> None:
    """Record a successful live SEC sync for this (ticker, types), evicting the oldest if full."""
    if len(_filings_synced_at) >= MAX_FILINGS_SYNC_ENTRIES:
        _filings_synced_at.pop(next(iter(_filings_synced_at)), None)  # insertion-ordered → oldest
    _filings_synced_at[(ticker, tuple(types_list))] = utcnow()


# In-flight guard for the DB-first background refresh (below): collapses a burst of concurrent loads
# of the same stale (ticker, types) into a single SEC refresh instead of one per request. Per-process
# (mirrors _filings_synced_at); a duplicate on another Cloud Run instance is harmless (idempotent
# upsert). Cleared in the refresh's finally.
_refreshing_keys: set = set()

# In-flight guard for the on-visit deep-history backfill (P1-6). Same rationale as _refreshing_keys:
# a burst of concurrent first-visits to a cold company would otherwise each fire a full multi-window
# EFTS walk before the first one stamps history_backfilled_at. Keyed by company id; check-and-add is
# synchronous (no await between), so it collapses the burst to one walk per company per process.
_history_backfilling_ids: set = set()


async def refresh_company_filings(
    cik: str, ticker_upper: str, types_list: List[str], company_id: int
) -> None:
    """Best-effort background refresh of a company's filings from SEC (DB-first serving).

    Runs AFTER the response is sent (FastAPI BackgroundTasks). Opens its OWN short-lived session —
    never the request-scoped one (which is already closed) — does the now-bounded SEC fetch (QW2:
    one recent-window submissions download, not the full history), upserts via the shared
    ``upsert_filings`` twin, and marks the (ticker, types) synced so the next load takes the fast
    path. Any failure only logs: the user was already served the persisted rows, and the list is
    allowed to lag by ``FILINGS_LIST_TTL``.
    """
    key = (ticker_upper, tuple(types_list))
    if key in _refreshing_keys:
        return  # a refresh for this exact key is already in flight in this process
    _refreshing_keys.add(key)
    db = None
    try:
        sec_filings = await asyncio.wait_for(
            sec_edgar_service.get_filings(cik, types_list),
            timeout=SEC_REQUEST_TIMEOUT_SECONDS,
        )
        db = SessionLocal()
        company = db.get(Company, company_id)
        if company is None:
            return
        from app.services.filing_scan_service import upsert_filings
        upsert_filings(db, company, sec_filings)
        _mark_filings_synced(ticker_upper, types_list)
    except Exception:
        logger.warning(
            "Background filings refresh failed for %s; serving persisted rows (stale within TTL)",
            ticker_upper,
            exc_info=True,
        )
        if db is not None:
            db.rollback()
    finally:
        if db is not None:
            db.close()
        _refreshing_keys.discard(key)


async def run_history_backfill_on_visit(company_id: int) -> None:
    """Best-effort one-time deep-history backfill for a company on first view (P1-6). Opens its own
    short-lived session (the request session is already closed), collapses concurrent first-visits
    with an in-flight guard (a full walk hasn't stamped the company yet, so the stamp re-check alone
    can't dedupe a burst), and never raises — the user was already served whatever rows exist."""
    if company_id in _history_backfilling_ids:
        return  # a backfill for this company is already in flight in this process
    _history_backfilling_ids.add(company_id)
    try:
        from app.services import filing_history_service
        await filing_history_service.backfill_company_by_id(
            company_id, session_factory=SessionLocal
        )
    except Exception:
        logger.warning("On-visit history backfill failed for company %s", company_id, exc_info=True)
    finally:
        _history_backfilling_ids.discard(company_id)


def company_by_ticker(db: Session, ticker_upper: str) -> Optional[Company]:
    """The stored company for this (already upper-cased) ticker, or None on a miss."""
    return db.query(Company).filter(Company.ticker == ticker_upper).first()


def release_request_session(db: Session) -> None:
    """Return the request session's pooled connection now, before an SEC or queue await, or before
    the route returns. The sync ``get_db`` finalizer runs in the thread pool only after the async
    route yields, so a completed read left open there can starve the pool
    (``lessons/ops-release-cached-filing-reads-before-yield.md``). The Session stays reusable for a
    later short unit."""
    db.close()


def persist_sec_company(db: Session, sec_data: Dict[str, Any], primary: Optional[str]) -> Company:
    """Create the Company row for an SEC search hit, or reuse the row already stored for its CIK
    (self-healing a stale ticker to ``primary``), and commit it.

    Called on the request session after the router's SEC awaits; any exception propagates to the
    router's miss-path handlers unchanged.
    """
    company = resolve_or_create_company_by_cik(
        db,
        cik=sec_data["cik"],
        ticker=primary or sec_data["ticker"],
        name=sec_data["name"],
        exchange=sec_data.get("exchange"),
        path="filings.get_company_filings",
        canonical_ticker=primary,  # self-heal a stale ticker → primary (P0-1)
    )
    db.commit()
    db.refresh(company)
    return company


def requested_filing_types(filing_types: Optional[str]) -> List[str]:
    """The form types to list for a ``?filing_types=`` value (None when absent), amendments added."""
    # Parse filing types. Default to the domestic financial reports; when FPI support is enabled,
    # also discover foreign-issuer forms (20-F annual, 6-K interim, 40-F) so ADRs like Alibaba
    # ($BABA) list their filings instead of showing an empty state. An explicit ?filing_types=
    # query always wins. Page-scoped: only this endpoint expands — the dashboard feed / scanner /
    # alerts keep their own form sets (see tasks/fpi-support-roadmap.md, Phase 5).
    if filing_types:
        types_list = [t.strip() for t in filing_types.split(",")]
    elif settings.ENABLE_FPI_FILINGS:
        types_list = ["10-K", "10-Q", "20-F", "6-K", "40-F"]
    else:
        types_list = ["10-K", "10-Q"]

    from app.services.filing_amendment_service import expand_amendment_forms
    return expand_amendment_forms(types_list)


def cached_filings(
    db: Session,
    company_id: int,
    types_list: List[str],
    limit: Optional[int],
    convert: Callable[[Filing], T],
) -> List[T]:
    """The company's persisted filings of these types, newest first, converted; releases the session.

    joinedload(company) so the converter doesn't lazy-load the company per row (this is the primary
    serving path, not just a fallback).
    """
    # Default serves the recent cap (unchanged behaviour); an explicit ?limit= (P1-6 "show full
    # history") raises it so the deep-backfilled rows surface.
    row_cap = limit or CACHED_FILINGS_LIMIT
    try:
        cached = db.query(Filing).options(joinedload(Filing.company)).filter(
            Filing.company_id == company_id,
            Filing.filing_type.in_(types_list)
        ).order_by(Filing.filing_date.desc()).limit(row_cap).all()
        return [convert(f) for f in cached]
    finally:
        # A sync dependency's finalizer runs in the thread pool after this async route yields.
        # Release completed reads now so a competing synchronous checkout cannot block the
        # event loop while waiting for those very finalizers to return the serving slots.
        db.close()


def cached_filings_after_rollback(
    db: Session,
    company_id: int,
    types_list: List[str],
    limit: Optional[int],
    convert: Callable[[Filing], T],
) -> List[T]:
    """Roll back a failed live unit, then serve :func:`cached_filings` (the error fallbacks)."""
    db.rollback()  # Ensure clean session state
    return cached_filings(db, company_id, types_list, limit, convert)


def persist_live_filings(
    db: Session,
    ticker_upper: str,
    types_list: List[str],
    company_id: int,
    sec_filings: List[Dict[str, Any]],
    convert: Callable[[Filing], T],
) -> List[T]:
    """Persist a live SEC listing and return it converted, in SEC order.

    New rows are inserted, existing rows on the old ``cgi-bin/viewer`` URL are rewritten, superseded
    filings are marked and everything commits in one transaction; the (ticker, types) is then
    stamped fresh. The DTOs are built last, after the commit, while the session is still open: the
    router's ``finally`` releases it. Any exception propagates to the router's fallbacks.
    """
    filings = []
    new_filings = []  # Track newly added filings for batch refresh

    # Prefetch existing filings in a single query to avoid an N+1
    # (previously this loop issued one SELECT per SEC filing).
    accession_numbers = [
        f["accession_number"] for f in sec_filings if f.get("accession_number")
    ]
    existing_by_accession = {
        f.accession_number: f
        for f in db.query(Filing)
        .filter(Filing.accession_number.in_(accession_numbers))
        .all()
    } if accession_numbers else {}

    for sec_filing in sec_filings:
        # Validate required fields from SEC response before database operations
        sec_url = sec_filing.get("sec_url")
        document_url = sec_filing.get("document_url")

        # Skip filings with missing required URLs to prevent NOT NULL violations
        if not sec_url:
            logger.warning(
                f"Skipping filing {sec_filing.get('accession_number')} - missing sec_url"
            )
            continue

        accession_number = sec_filing.get("accession_number")
        if not accession_number:
            logger.warning("Skipping filing - missing accession_number")
            continue

        # Check if filing exists (from the prefetched map — no per-iteration query)
        filing = existing_by_accession.get(accession_number)

        if not filing:
            # Only create new filing if we have all required fields
            if not document_url:
                logger.warning(
                    f"Skipping new filing {sec_filing.get('accession_number')} - missing document_url"
                )
                continue

            filing = Filing(
                company_id=company_id,
                accession_number=accession_number,
                filing_type=sec_filing["filing_type"],
                filing_date=datetime.fromisoformat(sec_filing["filing_date"]),
                period_end_date=datetime.fromisoformat(sec_filing["report_date"]) if sec_filing.get("report_date") else None,
                document_url=document_url,
                sec_url=sec_url
            )
            db.add(filing)
            new_filings.append(filing)
        else:
            # Update existing filing with new URL format if it's using old format
            # Only update if new values are valid (not None)
            if filing.sec_url and "cgi-bin/viewer" in filing.sec_url:
                if sec_url and document_url:
                    filing.sec_url = sec_url
                    filing.document_url = document_url
                else:
                    logger.warning(
                        f"Skipping URL update for filing {filing.accession_number} - "
                        f"new sec_url or document_url is None"
                    )

        filings.append(filing)

    # Batch commit: single transaction for all database changes
    if new_filings or db.dirty:
        from app.services.filing_amendment_service import mark_superseded_filings
        db.flush()
        mark_superseded_filings(db, company_id)
        db.commit()
        # Refresh new filings to get generated IDs
        for filing in new_filings:
            db.refresh(filing)

    # Mark this (ticker, types) freshly synced so subsequent loads take the B2 fast path.
    _mark_filings_synced(ticker_upper, types_list)

    # Convert to response models after commit
    return [convert(f) for f in filings]
