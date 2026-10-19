"""Companyfacts freshness, persistence and shared in-flight synchronization."""
from __future__ import annotations

import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy.orm import Session

from app.models import Company, Filing
from app.services.facts.companyfacts import normalize_companyfacts
from app.services.facts.concepts import COMPANYFACTS_INFLIGHT_WAIT_SECONDS, _is_financial_sic
from app.services.facts.currency import demote_convenience_rows
from app.services.facts.transport import _fetch_companyfacts_async, logger
from app.services.facts.upsert import upsert_facts_bulk
from app.utils.datetimes import ensure_utc, utcnow


# Per-company in-flight sync dedup (the summary_pipeline._claim_inflight pattern): concurrent
# coverage requests for the same company collapse into one SEC fetch. Process-local, with Redis
# off: each API instance (up to two) dedups its own requests, and a fetch repeated on the other
# instance upserts the same facts.
_inflight_syncs: dict[int, asyncio.Event] = {}

_T = TypeVar("_T")

# ``ingest_companyfacts_by_id``'s database units (the freshness read, a follower's re-read, the
# persist) wait for a pool slot in threads of their own, never on the event loop or in its default
# executor. A slot holder can need a default-executor thread for its next step (login keeps its
# connection checked out while it awaits bcrypt through ``asyncio.to_thread``), so units waiting
# there could leave neither side able to move until the pool timed out; the Copilot's lookups keep
# to threads of their own for the same reason (``copilot_chat._LOOKUP_THREADS``). A unit holds no
# slot while it waits for a thread and needs no other thread while it holds one. Two threads keep
# the sync to half of the API's four slots.
_SYNC_THREADS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="companyfacts_sync")


def _submit(unit: Callable[[], _T]) -> asyncio.Future[_T]:
    """``asyncio.to_thread`` on the sync's own threads: the same context copy."""
    call = functools.partial(contextvars.copy_context().run, unit)
    return asyncio.get_running_loop().run_in_executor(_SYNC_THREADS, call)


async def _run_to_completion(unit: Callable[[], _T]) -> _T:
    """Run ``unit`` on a sync thread and outlast a cancellation of the caller.

    A thread cannot be stopped, so a cancelled caller waits for it before the cancellation goes on:
    the leader's ``finally`` must not wake followers (or let another leader start) while its persist
    is still writing. The coverage route cancels its sync task once, at the frontend's wait budget."""
    work = _submit(unit)
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        await asyncio.wait({work})
        raise


def _companyfacts_fresh_result(
    db: Session, company: Company, *, force: bool
) -> Optional[dict[str, Any]]:
    """Return the unchanged TTL result, or ``None`` when this company needs a fetch."""
    synced_at = ensure_utc(company.facts_synced_at) if company.facts_synced_at is not None else None
    if force or synced_at is None:
        return None

    from app.config import settings

    if utcnow() - synced_at >= timedelta(
        hours=settings.COMPANYFACTS_SYNC_TTL_HOURS
    ):
        return None
    newer_filing = (
        db.query(Filing.id)
        .filter(Filing.company_id == company.id, Filing.filing_date > synced_at)
        .first()
    )
    if newer_filing is not None:
        return None
    return {
        "synced": True, "refreshed": False, "inserted": 0, "skipped": 0,
        "demoted": 0, "unsupported_ifrs": False,
    }


def _persist_companyfacts_payload(
    db: Session, company: Company, payload: dict[str, Any]
) -> dict[str, Any]:
    """Normalize and persist one already-fetched payload in the caller's short transaction; each
    native-currency row demotes its current USD twin, whatever its source or filing, and a native
    ratio stored behind a USD-derived one takes its place (rows demoted, never deleted or rewritten)."""
    company_id = company.id  # the commit expires the row; reading it back would check out again
    facts, meta = normalize_companyfacts(
        company_id, payload, financial_sic=_is_financial_sic(company.sic)
    )
    result = upsert_facts_bulk(db, facts, commit=False)  # all-zero counters for an empty batch
    result["demoted"] += demote_convenience_rows(db, facts)
    company.facts_synced_at = utcnow()
    db.commit()
    logger.info(
        "companyfacts_sync company=%s inserted=%s skipped=%s demoted=%s ifrs=%s",
        company_id, result["inserted"], result["skipped"], result["demoted"],
        meta["unsupported_ifrs"],
    )
    return {
        "synced": True, "refreshed": True, **result,
        "unsupported_ifrs": meta["unsupported_ifrs"],
    }


async def ingest_companyfacts(
    db: Session,
    company: Company,
    *,
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Sync one company's companyfacts history into ``financial_fact`` (TTL-guarded, deduped).

    Freshness: a sync newer than ``COMPANYFACTS_SYNC_TTL_HOURS`` is a no-op UNLESS a Filing row
    newer than the stamp exists (a fresh filing shouldn't wait out the TTL) or ``force`` is set.
    ``facts_synced_at`` is stamped even for empty/IFRS-only results so unsupported filers aren't
    refetched hourly; a FAILED fetch does not stamp (retry on next touch). ``fetcher`` is
    injectable for tests (async ``cik -> dict | None``).
    """
    fresh = _companyfacts_fresh_result(db, company, force=force)
    if fresh is not None:
        return fresh

    inflight = _inflight_syncs.get(company.id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        db.expire(company)  # pick up the leader's facts_synced_at
        return {"synced": company.facts_synced_at is not None, "refreshed": False, "inserted": 0,
                "skipped": 0, "demoted": 0, "unsupported_ifrs": False, "waited": True}

    event = asyncio.Event()
    _inflight_syncs[company.id] = event
    try:
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(company.cik)
        if payload is None:
            return {"synced": False, "refreshed": False, "inserted": 0, "skipped": 0, "demoted": 0,
                    "unsupported_ifrs": False, "error": "fetch_failed"}
        return _persist_companyfacts_payload(db, company, payload)
    finally:
        if _inflight_syncs.get(company.id) is event:
            _inflight_syncs.pop(company.id, None)
        event.set()


async def ingest_companyfacts_by_id(
    company_id: int,
    *,
    session_factory: Callable[[], Session],
    force: bool = False,
    fetcher: Optional[Callable[[str], Any]] = None,
) -> dict[str, Any]:
    """Sync coverage facts without retaining a database connection during external waits.

    The coverage route can outlive its request while the SEC fetch continues in the background.
    Keep its database ownership to short units: the leader claims the sync, reads the company's
    freshness, and after the fetch persists; a same-company follower waits on the process-local
    event with no session of its own, then reads the stamp the leader left.  The caller-owned
    ``ingest_companyfacts`` contract remains intact for batch jobs and tests that deliberately
    manage a larger transaction.

    Each unit runs on the sync's own threads (``_SYNC_THREADS``): the coverage route runs this as a
    task on the API's event loop, where a checkout would freeze the loop while the pool is full, and
    the persist's normalize and bulk upsert would block it for their whole run
    (lessons/ops-release-cached-filing-reads-before-yield.md).
    """

    def read_freshness() -> tuple[Optional[dict[str, Any]], Optional[str]]:
        with session_factory() as db:
            company = db.get(Company, company_id)
            if company is None:
                return {"synced": False}, None
            fresh = _companyfacts_fresh_result(db, company, force=force)
            if fresh is not None:
                return fresh, None
            return None, company.cik

    def read_synced_at() -> Optional[datetime]:
        with session_factory() as db:
            return db.query(Company.facts_synced_at).filter(Company.id == company_id).scalar()

    inflight = _inflight_syncs.get(company_id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        synced_at = await _submit(read_synced_at)
        return {
            "synced": synced_at is not None, "refreshed": False, "inserted": 0, "skipped": 0,
            "demoted": 0, "unsupported_ifrs": False, "waited": True,
        }

    # Claim the sync before the freshness read, in the same loop step as the check above. The read
    # waits on a sync thread, and a same-company request arriving meanwhile must follow this one:
    # read first, and a leader finishing during the read would leave it a stale stamp and no
    # claim to follow, so it would lead a second fetch.
    event = asyncio.Event()
    _inflight_syncs[company_id] = event
    try:
        settled, cik = await _submit(read_freshness)
        if settled is not None:
            return settled
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(cik)
        if payload is None:
            return {
                "synced": False, "refreshed": False, "inserted": 0, "skipped": 0,
                "demoted": 0, "unsupported_ifrs": False, "error": "fetch_failed",
            }

        def persist() -> dict[str, Any]:
            with session_factory() as db:
                company = db.get(Company, company_id)
                if company is None:
                    return {"synced": False}
                return _persist_companyfacts_payload(db, company, payload)

        return await _run_to_completion(persist)
    finally:
        if _inflight_syncs.get(company_id) is event:
            _inflight_syncs.pop(company_id, None)
        event.set()
