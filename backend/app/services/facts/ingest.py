"""Companyfacts freshness, persistence and shared in-flight synchronization."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models import Company, Filing
from app.services.facts.companyfacts import normalize_companyfacts
from app.services.facts.concepts import COMPANYFACTS_INFLIGHT_WAIT_SECONDS, _is_financial_sic
from app.services.facts.transport import _fetch_companyfacts_async, logger
from app.services.facts.upsert import upsert_facts_bulk
from app.utils.datetimes import ensure_utc, utcnow


# Per-company in-flight sync dedup (the summary_pipeline._claim_inflight pattern): concurrent
# coverage requests for the same company collapse into one SEC fetch. Process-local is the right
# scope — prod is a single Cloud Run instance with Redis off.
_inflight_syncs: dict[int, asyncio.Event] = {}


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
    """Normalize and persist one already-fetched payload in the caller's short transaction."""
    facts, meta = normalize_companyfacts(
        company.id, payload, financial_sic=_is_financial_sic(company.sic)
    )
    result = (
        upsert_facts_bulk(db, facts, commit=False)
        if facts
        else {"inserted": 0, "skipped": 0, "demoted": 0}
    )
    company.facts_synced_at = utcnow()
    db.commit()
    logger.info(
        "companyfacts_sync company=%s inserted=%s skipped=%s demoted=%s ifrs=%s",
        company.id, result["inserted"], result["skipped"], result["demoted"],
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
    Keep its database ownership to two short units: a freshness/snapshot read, then (for the
    leader) persistence after the fetch.  A same-company follower waits on the process-local event
    with no session of its own.  The caller-owned ``ingest_companyfacts`` contract remains intact
    for batch jobs and tests that deliberately manage a larger transaction.
    """
    with session_factory() as db:
        company = db.get(Company, company_id)
        if company is None:
            return {"synced": False}

        fresh = _companyfacts_fresh_result(db, company, force=force)
        if fresh is not None:
            return fresh

        cik = company.cik

    inflight = _inflight_syncs.get(company_id)
    if inflight is not None:
        try:
            await asyncio.wait_for(inflight.wait(), timeout=COMPANYFACTS_INFLIGHT_WAIT_SECONDS)
        except asyncio.TimeoutError:
            pass
        with session_factory() as db:
            synced_at = db.query(Company.facts_synced_at).filter(Company.id == company_id).scalar()
        return {
            "synced": synced_at is not None, "refreshed": False, "inserted": 0, "skipped": 0,
            "demoted": 0, "unsupported_ifrs": False, "waited": True,
        }

    event = asyncio.Event()
    _inflight_syncs[company_id] = event
    try:
        fetch = fetcher or _fetch_companyfacts_async
        payload = await fetch(cik)
        if payload is None:
            return {
                "synced": False, "refreshed": False, "inserted": 0, "skipped": 0,
                "demoted": 0, "unsupported_ifrs": False, "error": "fetch_failed",
            }
        with session_factory() as db:
            company = db.get(Company, company_id)
            if company is None:
                return {"synced": False}
            return _persist_companyfacts_payload(db, company, payload)
    finally:
        if _inflight_syncs.get(company_id) is event:
            _inflight_syncs.pop(company_id, None)
        event.set()
