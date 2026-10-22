"""Company filing lists behind ``GET /api/filings/company/{ticker}`` (``app/routers/filings.py``).

Moved verbatim from the router so it stays HTTP only: the B2 freshness cache, the DB-first
background refresh, the on-visit history backfill, the CIK-first company persistence on a miss, the
filing-type defaults, the cached reads and the cold live fetch's persistence. The router keeps the
request path's SEC awaits (the background refresh, which runs after the response, awaits its own
fetch here), the ``BackgroundTasks`` scheduling, the durable-task handoff (it does no database work),
the error mapping and the fallback log lines; the skip and background-failure warnings moved here
with their code, so they now log as ``app.services.filing_list_service``.

The background tasks open their own short-lived sessions, each in a synchronous unit run in the
thread pool (``run_owned_sync``; E123). Everything else is one synchronous unit
on the request's session, which the router runs in the thread pool, so its checkout never waits on
the event loop. Each unit releases the request's pooled connection before it returns, so nothing is
held across an SEC or queue await or left for the dependency's finalizer
(:func:`release_request_session`; ``tests/unit/test_cached_filings_pool_lifetime.py`` and
``tests/unit/test_filings_endpoint_db_first.py::test_sec_network_phases_do_not_retain_queuepool_connections``).
A unit hands back plain values: the response DTOs, built with the router's converter, or a
:class:`CompanyIdentity`. After a commit the rows are expired, and a lazy read after the release
would check a connection out again (``lessons/ops-release-cached-filing-reads-before-yield.md``).
"""
import asyncio
import logging
import threading
from datetime import datetime, timedelta
from itertools import chain
from operator import attrgetter
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, TypeVar

from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Company, Filing
from app.services.company_resolution import resolve_or_create_company_by_cik
from app.services.edgar.client import _take_recent
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.config import FilingType
from app.services.request_work import run_owned_sync
from app.utils.datetimes import utc_from_iso, utcnow

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Constants for filings endpoint configuration
SEC_REQUEST_TIMEOUT_SECONDS = 20.0  # Timeout for SEC EDGAR requests (within frontend's 30s limit)
CACHED_FILINGS_LIMIT = 20  # Rows the default list serves per group: the reports, and 6-Ks apart

# B2: stale-within-TTL cache for the company filings list. The hot path already persists every SEC
# fetch into the Filing table, so a recently-synced ticker can serve its list straight from the DB
# (~ms) instead of paying the 3-5s SEC round-trip on every load. In-memory by design — single Cloud
# Run instance, Redis off in prod (mirrors companies.py's _quote_cache). Staleness is bounded by the
# TTL; the new-filing ALERT path (filing-scan job) is independent, so users are still notified of new
# filings even if this list lags by up to the TTL.
FILINGS_LIST_TTL = timedelta(hours=3)
MAX_FILINGS_SYNC_ENTRIES = 2000  # bound memory; oldest (ticker,types) key is evicted past this
_filings_synced_at: Dict[Tuple[str, Tuple[str, ...]], datetime] = {}
# The live listing marks its key from a worker thread and the background refresh from the event loop,
# so the evict-then-insert runs under a lock: an insert between the eviction's iter() and next() would
# raise. A read is one dict lookup and needs none.
_filings_synced_lock = threading.Lock()


def filings_cache_fresh(ticker: str, types_list: List[str]) -> bool:
    """True when this (ticker, types) was synced from SEC within the TTL."""
    synced = _filings_synced_at.get((ticker, tuple(types_list)))
    return synced is not None and (utcnow() - synced) < FILINGS_LIST_TTL


def _mark_filings_synced(ticker: str, types_list: List[str]) -> None:
    """Record a successful live SEC sync for this (ticker, types), evicting the oldest if full."""
    with _filings_synced_lock:
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
    try:
        sec_filings = await asyncio.wait_for(
            sec_edgar_service.get_filings(cik, types_list),
            timeout=SEC_REQUEST_TIMEOUT_SECONDS,
        )
        if await run_owned_sync(_persist_refreshed_filings, company_id, sec_filings):
            _mark_filings_synced(ticker_upper, types_list)
    except Exception:
        logger.warning(
            "Background filings refresh failed for %s; serving persisted rows (stale within TTL)",
            ticker_upper,
            exc_info=True,
        )
    finally:
        _refreshing_keys.discard(key)


def _persist_refreshed_filings(company_id: int, sec_filings: List[dict]) -> bool:
    """The background refresh's one database unit, in the thread pool: upsert the refreshed list on
    a session of its own, closed (and so rolled back on a failure) before it returns. False when the
    company is gone. On the event loop its checkout would freeze the loop while the pool is full
    (E123)."""
    from app.services.filing_scan_service import upsert_filings

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        if company is None:
            return False
        upsert_filings(db, company, sec_filings)
        return True


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


class CompanyIdentity(NamedTuple):
    """The company fields the filings route reads after its unit has released the session."""

    id: int
    cik: str
    needs_history_backfill: bool

    @classmethod
    def of(cls, company: Company) -> "CompanyIdentity":
        return cls(company.id, company.cik, company.history_backfilled_at is None)


def stored_company_identity(db: Session, ticker_upper: str) -> Optional[CompanyIdentity]:
    """The stored company for this (already upper-cased) ticker, or None on a miss; releases the
    session either way, so the miss path's SEC awaits hold no connection."""
    try:
        company = db.query(Company).filter(Company.ticker == ticker_upper).first()
        return None if company is None else CompanyIdentity.of(company)
    finally:
        release_request_session(db)


def release_request_session(db: Session) -> None:
    """Return the request session's pooled connection now, before an SEC or queue await, or before
    the route returns. The sync ``get_db`` finalizer runs in the thread pool only after the async
    route yields, so a completed read left open there can starve the pool
    (``lessons/ops-release-cached-filing-reads-before-yield.md``). The Session stays reusable for a
    later short unit.

    A close that fails is logged, not raised. Units call this in a ``finally``, where raising would
    replace the unit's own outcome: a refresh whose rotation has committed would answer 500 and lose
    the rotated token, and a refresh's 401 would become a 500. The logged traceback reaches Sentry.
    When the rollback fails because the connection dropped after the unit's last statement, the
    session has already let go of its transaction, and SQLAlchemy has invalidated the connection and
    returned its pool slot, so the dependency's finalizer finds nothing left to release. A rollback
    that fails for another reason holds the slot until garbage collection, as it did when the
    finalizer closed."""
    try:
        db.close()
    except Exception:
        logger.exception("Releasing the request session failed; the unit's own outcome stands")


def persist_sec_company(db: Session, sec_data: Dict[str, Any], primary: Optional[str]) -> CompanyIdentity:
    """Create the Company row for an SEC search hit, or reuse the row already stored for its CIK
    (self-healing a stale ticker to ``primary``), commit it and release the session.

    Called on the request session after the router's SEC awaits; any exception propagates to the
    router's miss-path handlers unchanged.
    """
    try:
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
        return CompanyIdentity.of(company)
    finally:
        release_request_session(db)


def requested_filing_types(filing_types: Optional[str]) -> List[str]:
    """The form types to list for a ``?filing_types=`` value (None when absent), amendments added.

    The caller's value is validated here, where it enters: each entry reads as its SEC form
    (``10k`` lists ``10-K``) and an unknown one is dropped, as the SEC layer drops it, so a value
    that names no known form lists nothing.
    """
    # Parse filing types. Default to the domestic financial reports; when FPI support is enabled,
    # also discover foreign-issuer forms (20-F annual, 6-K interim, 40-F) so ADRs like Alibaba
    # ($BABA) list their filings instead of showing an empty state. An explicit ?filing_types=
    # query always wins. Page-scoped: only this endpoint expands — the dashboard feed / scanner /
    # alerts keep their own form sets (see tasks/fpi-support-roadmap.md, Phase 5).
    # The default set lives in latest_filing_service, so search names the same latest filing.
    from app.services.filing_amendment_service import expand_amendment_forms
    from app.services.latest_filing_service import company_list_forms
    if filing_types:
        forms = (FilingType.from_string(t, strict=False) for t in filing_types.split(","))
        return expand_amendment_forms([f.value for f in forms if f is not FilingType.UNKNOWN])
    return company_list_forms()


def other_filing_forms() -> List[str]:
    """Every form ``requested_filing_types`` can list that ``company_list_forms()`` does not, in one
    fixed order: the second refresh a filings visit queues when it serves stored rows of one of
    them (``routers/filings.py``). With the list forms it is one of only two refresh payloads a
    visit can produce; the worker fetches only the forms :func:`forms_to_refresh` keeps."""
    from app.services.latest_filing_service import company_list_forms
    listed = set(company_list_forms())
    return [form.value for form in FilingType if form is not FilingType.UNKNOWN and form.value not in listed]


def forms_to_refresh(db: Session, company_id: int, forms: List[str]) -> List[str]:
    """The forms of a durable refresh's payload that the worker fetches. The list-forms payload is
    fetched whole, so a company's first 10-Q or 20-F arrives. It is recognised in either state of
    ``ENABLE_FPI_FILINGS``, because a queued task can outlive a change of the flag. Any other payload
    keeps only the forms the company already has rows of. So a refresh keeps stored rows fresh but
    never adds another form nobody stored, which would spend the fetch's row budget and reach the pages
    that read every stored form (the watchlist, the dashboard, the digest)."""
    from app.services.latest_filing_service import company_list_forms
    if forms in (company_list_forms(fpi=False), company_list_forms(fpi=True)):
        return forms
    stored = {form for (form,) in db.query(Filing.filing_type).filter(Filing.company_id == company_id).distinct()}
    return [form for form in forms if form in stored]


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
    # Each group serves its newest `row_cap` rows: the reports, and the 6-Ks (FilingType.is_interim)
    # apart, as on the live fetch (edgar/client.py RECENT_FILINGS_MATERIALIZE_CAP): an issuer that
    # furnishes a 6-K most business days would otherwise fill the cap and hide its 20-F/40-F. The
    # default cap is CACHED_FILINGS_LIMIT; an explicit ?limit= (P1-6 "show full history") raises it
    # so the deep-backfilled rows surface. With no 6-K type requested, this is the one reports query.
    row_cap = limit or CACHED_FILINGS_LIMIT
    six_k_types = [t for t in types_list if FilingType.from_string(t, strict=False).is_interim]
    report_types = [t for t in types_list if t not in six_k_types]
    try:
        newest_per_group = [
            db.query(Filing).options(joinedload(Filing.company)).filter(
                Filing.company_id == company_id,
                Filing.filing_type.in_(types)
            ).order_by(Filing.filing_date.desc()).limit(row_cap).all()
            for types in (report_types, six_k_types)
            if types
        ]
        cached = sorted(chain.from_iterable(newest_per_group), key=lambda f: f.filing_date, reverse=True)
        return [convert(f) for f in cached]
    finally:
        # A sync dependency's finalizer runs in the thread pool after this async route yields.
        # Release completed reads now so a competing checkout never waits for those very
        # finalizers to return the serving slots.
        release_request_session(db)


def cached_filings_after_rollback(
    db: Session,
    company_id: int,
    types_list: List[str],
    limit: Optional[int],
    convert: Callable[[Filing], T],
) -> List[T]:
    """Serve :func:`cached_filings` for the error fallbacks. The rollback first is a guard: every
    earlier unit releases the session before it returns, a failed live persist included, so it
    normally finds no transaction to roll back."""
    db.rollback()  # Ensure clean session state
    return cached_filings(db, company_id, types_list, limit, convert)


def persist_live_filings(
    db: Session,
    ticker_upper: str,
    types_list: List[str],
    company_id: int,
    sec_filings: List[Dict[str, Any]],
    limit: Optional[int],
    convert: Callable[[Filing], T],
) -> List[T]:
    """Persist a live SEC listing and return it converted, in SEC order.

    New rows are inserted, existing rows on the old ``cgi-bin/viewer`` URL are rewritten, superseded
    filings are marked and everything commits in one transaction; the (ticker, types) is then
    stamped fresh. Every listed row is persisted; an explicit ``limit`` caps each group of the
    response (the 6-Ks, and every other form), as :func:`cached_filings` does. The DTOs are built
    last, after the commit, while the session is still open: the router's unit releases it once
    this returns or raises. Any exception propagates to the router's fallbacks.
    """
    from app.services.filing_amendment_service import lock_company_filings, mark_superseded_filings

    filings = []
    new_filings = []  # Track newly added filings for batch refresh

    lock_company_filings(db, company_id)  # before the check below reads which rows exist
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
                filing_date=utc_from_iso(sec_filing["filing_date"]),
                period_end_date=utc_from_iso(sec_filing["report_date"]) if sec_filing.get("report_date") else None,
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
        db.flush()
        mark_superseded_filings(db, company_id)
        db.commit()
        # Refresh new filings to get generated IDs
        for filing in new_filings:
            db.refresh(filing)

    # Mark this (ticker, types) freshly synced so subsequent loads take the B2 fast path.
    _mark_filings_synced(ticker_upper, types_list)

    # Convert to response models after commit; ?limit= keeps the newest `limit` of each group with
    # the live fetch's own per-group rule.
    if limit is not None:
        filings = _take_recent(filings, limit, six_k_apart=True, form=attrgetter("filing_type"))
    return [convert(f) for f in filings]
