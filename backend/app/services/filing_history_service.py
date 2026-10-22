"""Deep filing-history backfill via EFTS (P1-6).

The company-filings endpoint serves only the newest filings (a recent-window submissions
download). This backfills DEEP history — 10-K/10-Q since 2001, and with ``ENABLE_FPI_FILINGS`` on a
foreign private issuer's 20-F/40-F annual reports — into the ``filings`` table so the company page
can show a full history and the fiscal-year filter has data to work with.

Uses the EFTS full-text-search integration (``app.integrations.sec_api`` — Path B: rate-limited via
``sec_rate_limiter``, no circuit breaker) with query-less form+cik+date-window listings: one
page-0 request per window (EFTS returns HTTP 500 for ``from>0`` on query-less searches), windows
sized so a company's per-window hit count stays under the ~100-hit page cap. Rows are written
through ``filing_scan_service.upsert_filings`` (NOT-NULL-safe, accession-deduped). Each company is
stamped ``companies.history_backfilled_at`` so the on-visit enqueue never re-walks it.

Annual and quarterly amendments are included; same-period originals remain available, and 10-K/10-Q
originals are marked superseded (``mark_superseded_filings`` covers those two forms only).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, Watchlist
from app.services import filing_scan_service
from app.services.edgar.config import FilingType
from app.services.request_work import run_owned_sync
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)

# Match the company display: retain both originals and same-period amendments.
_BACKFILL_FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A")
# A foreign private issuer's annual reports, walked while ENABLE_FPI_FILINGS lists 20-F and 40-F on
# the company page. Their amendments are stored too, as the walk runs once per company, though the
# default list serves only the originals. They join the same per-window query, so they cost no EFTS
# request, and a filer adds hits only for forms it files: about one a year, under the four reports a
# year the windows are sized for. 6-K stays out: a high-volume interim form (a heavy filer furnishes
# one most business days) would fill a window's ~100-hit page and push the annual reports off it.
_FPI_BACKFILL_FORMS = ("20-F", "20-F/A", "40-F", "40-F/A")
# Transient-5xx retries scoped to THIS path — the shared limiter's execute_with_backoff only
# retries rate-limit errors, not the sporadic 5xx EFTS emits, so we add a small bounded ladder.
_BACKFILL_RETRY_ATTEMPTS = 3


def _backfill_forms() -> tuple[str, ...]:
    """The forms the walk lists and keeps: the foreign annual reports only behind ENABLE_FPI_FILINGS."""
    return _BACKFILL_FORMS + (_FPI_BACKFILL_FORMS if settings.ENABLE_FPI_FILINGS else ())


def _windows(since_year: int, end: datetime, window_years: int) -> list[tuple[str, str]]:
    """Inclusive ``[start, end]`` ISO date windows from ``since_year`` to today, ``window_years``
    wide. The final window ends today so newly-filed reports are always covered."""
    out: list[tuple[str, str]] = []
    end_year = end.year
    y = max(1, since_year)
    while y <= end_year:
        last = min(y + max(1, window_years) - 1, end_year)
        w_end = end.date().isoformat() if last == end_year else f"{last}-12-31"
        out.append((f"{y}-01-01", w_end))
        y = last + 1
    return out


def _hit_to_filing_dict(hit: Any) -> Optional[dict]:
    """Adapt an ``EftsHit`` to the ``upsert_filings`` dict shape, or ``None`` to skip.

    Skips rows missing the NOT-NULL keys (accession/sec_url/document_url), unknown/other forms,
    so only clean annual/quarterly reports and their amendments are inserted."""
    accession = getattr(hit, "accession_no", None)
    sec_url = getattr(hit, "sec_url", None)
    document_url = getattr(hit, "document_url", None)
    raw_form = getattr(hit, "form", None)
    filed_date = getattr(hit, "filed_date", None)
    if not accession or not sec_url or not document_url or not raw_form or not filed_date:
        return None
    ftype = FilingType.from_string(raw_form, strict=False)
    if ftype is FilingType.UNKNOWN or ftype.value not in _backfill_forms():
        return None
    return {
        "accession_number": accession,
        "filing_type": ftype.value,
        "filing_date": filed_date,
        "report_date": getattr(hit, "period_ending", None) or None,
        "sec_url": sec_url,
        "document_url": document_url,
    }


async def _search_window_with_retry(efts_client, *, forms: str, cik: str, start: str, end: str):
    """One query-less page-0 EFTS listing for a form+cik+window, with a small transient-5xx retry
    scoped to this path. Raises the last exception if every attempt fails."""
    last_exc: Optional[Exception] = None
    for attempt in range(_BACKFILL_RETRY_ATTEMPTS):
        try:
            return await efts_client.search(
                query=None, forms=forms, start_date=start, end_date=end, ciks=cik
            )
        except Exception as exc:  # noqa: BLE001 — EFTS is a best-effort backfill source
            last_exc = exc
            logger.warning(
                "History backfill EFTS window %s..%s (cik=%s) attempt %d/%d failed: %s",
                start, end, cik, attempt + 1, _BACKFILL_RETRY_ATTEMPTS, exc,
            )
    raise last_exc  # type: ignore[misc]


async def _fetch_history_rows(
    *, cik: str, ticker: str, efts_client=None
) -> tuple[list[dict], int, int]:
    """Fetch and validate one company's bounded EFTS windows without owning a DB session."""
    if efts_client is None:
        from app.integrations.sec_api import sec_full_text_search_client
        efts_client = sec_full_text_search_client

    forms = ",".join(_backfill_forms())
    windows = _windows(
        settings.HISTORY_BACKFILL_SINCE_YEAR, utcnow(), settings.HISTORY_BACKFILL_WINDOW_YEARS
    )

    seen: set[str] = set()
    rows: list[dict] = []
    windows_ok = 0
    for start, end in windows:
        try:
            result = await _search_window_with_retry(
                efts_client, forms=forms, cik=cik, start=start, end=end
            )
        except Exception:
            logger.exception(
                "History backfill window %s..%s failed for %s after retries", start, end, ticker
            )
            continue
        windows_ok += 1
        for hit in (getattr(result, "hits", None) or []):
            rec = _hit_to_filing_dict(hit)
            if rec is None:
                continue
            acc = rec["accession_number"]
            if acc in seen:
                continue
            seen.add(acc)
            rows.append(rec)

    return rows, len(windows), windows_ok


def _persist_history_rows(
    db: Session,
    company: Company,
    *,
    rows: list[dict],
    windows: int,
    windows_ok: int,
    require_complete: bool = False,
) -> dict:
    """Persist already-fetched history in one short caller-owned transaction."""
    ticker = company.ticker
    inserted = filing_scan_service.upsert_filings(db, company, rows)
    if windows_ok and (not require_complete or windows_ok == windows):
        company.history_backfilled_at = utcnow()
        db.commit()
    stats = {
        "ticker": ticker, "windows": windows, "windows_ok": windows_ok,
        "hits": len(rows), "inserted": len(inserted),
    }
    logger.info("History backfill %s", stats)
    if require_complete and windows_ok != windows:
        raise RuntimeError("History backfill incomplete; retry missing windows")
    return stats


async def backfill_company(db: Session, company: Company, *, efts_client=None) -> dict:
    """Backfill one company through a caller-owned session, preserving batch-job behavior.

    A per-window EFTS failure (after retries) is logged and skipped, not raised — a partial
    backfill is fine (the next visit/run re-covers it). The company is stamped only when at least
    one window succeeded, so a total EFTS outage retries on the next visit instead of marking the
    company done with no data. Callers that must release DB ownership during external I/O use
    ``backfill_company_by_id`` instead.
    """
    rows, windows, windows_ok = await _fetch_history_rows(
        cik=company.cik, ticker=company.ticker, efts_client=efts_client
    )
    return _persist_history_rows(
        db, company, rows=rows, windows=windows, windows_ok=windows_ok
    )


async def backfill_company_by_id(
    company_id: int,
    *,
    session_factory: Callable[[], Session],
    efts_client=None,
    require_complete: bool = False,
    force: bool = False,
) -> dict | None:
    """Backfill an on-visit company without retaining a connection during EFTS I/O.

    The two sessions are owned here and contain only short read/persistence units, each run in the
    thread pool (``run_owned_sync``), so neither checkout waits on the event loop: with
    ``DURABLE_TASKS_ENABLED`` off the visit's backfill runs in the API process after the response
    (E123). Generic batch callers keep using ``backfill_company`` so this path never closes their
    sessions or discards pending mutations.
    """
    identity = await run_owned_sync(_company_to_backfill, session_factory, company_id, force)
    if identity is None:
        return None
    cik, ticker = identity

    rows, windows, windows_ok = await _fetch_history_rows(
        cik=cik, ticker=ticker, efts_client=efts_client
    )

    return await run_owned_sync(
        _persist_backfill, session_factory, company_id,
        rows=rows, windows=windows, windows_ok=windows_ok, require_complete=require_complete,
    )


def _company_to_backfill(
    session_factory: Callable[[], Session], company_id: int, force: bool
) -> tuple[str, str] | None:
    """The backfill's first unit: the company's CIK and ticker, or None when it is gone or done."""
    with session_factory() as db:
        company = db.get(Company, company_id)
        if company is None or (not force and company.history_backfilled_at is not None):
            return None
        return company.cik, company.ticker


def _persist_backfill(
    session_factory: Callable[[], Session],
    company_id: int,
    *,
    rows: list[dict],
    windows: int,
    windows_ok: int,
    require_complete: bool,
) -> dict | None:
    """The backfill's second unit: persist the fetched rows on a session of its own, or None when
    the company is gone."""
    with session_factory() as db:
        company = db.get(Company, company_id)
        if company is None:
            return None
        return _persist_history_rows(
            db, company, rows=rows, windows=windows, windows_ok=windows_ok,
            require_complete=require_complete,
        )


def _resolve_cohort(
    db: Session, *, tickers: Optional[list[str]], watchlist_only: bool, limit: Optional[int]
) -> list[Company]:
    """Cohort precedence: explicit ``tickers`` > ``watchlist_only`` > all companies (un-backfilled
    first so a capped run makes progress each time). Always bounded by
    ``HISTORY_BACKFILL_MAX_COMPANIES``."""
    q = db.query(Company)
    if tickers:
        q = q.filter(Company.ticker.in_([t.upper() for t in tickers]))
    elif watchlist_only:
        # DB-side subquery — avoids loading every watchlist id into Python and the SQLite 999-param
        # cap; an empty watchlist naturally matches zero companies.
        q = q.filter(Company.id.in_(db.query(Watchlist.company_id).distinct()))
    else:
        q = q.order_by(Company.history_backfilled_at.is_(None).desc(), Company.id)
    cap = settings.HISTORY_BACKFILL_MAX_COMPANIES
    if limit is not None:
        cap = min(limit, cap)
    return q.limit(cap).all()


async def batch_backfill(
    db: Session, *, tickers: Optional[list[str]] = None,
    watchlist_only: bool = False, limit: Optional[int] = None,
) -> dict:
    """Backfill a cohort serially (paced by the shared SEC limiter). One company's failure never
    stops the walk."""
    companies = _resolve_cohort(db, tickers=tickers, watchlist_only=watchlist_only, limit=limit)
    totals = {"companies": 0, "inserted": 0, "failed": 0}
    # backfill_company commits per company; the default expire-on-commit would then expire every
    # loaded Company, so each subsequent iteration (and the exception handler's company.ticker)
    # would re-SELECT the row (N+1). Disable it for the walk (mirrors sync_companyfacts_batch).
    original_expire = db.expire_on_commit
    db.expire_on_commit = False
    try:
        for company in companies:
            try:
                s = await backfill_company(db, company)
                totals["companies"] += 1
                totals["inserted"] += s["inserted"]
            except Exception:
                db.rollback()
                totals["failed"] += 1
                logger.exception("History backfill failed for %s", getattr(company, "ticker", "?"))
    finally:
        db.expire_on_commit = original_expire
    logger.info("History backfill batch complete: %s", totals)
    return totals
