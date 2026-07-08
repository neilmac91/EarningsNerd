"""Deep filing-history backfill via EFTS (P1-6).

The company-filings endpoint serves only the newest filings (a recent-window submissions
download). This backfills DEEP history — 10-K/10-Q since 2001 — into the ``filings`` table so the
company page can show a full history and the fiscal-year filter has data to work with.

Uses the EFTS full-text-search integration (``app.integrations.sec_api`` — Path B: rate-limited via
``sec_rate_limiter``, no circuit breaker) with query-less form+cik+date-window listings: one
page-0 request per window (EFTS returns HTTP 500 for ``from>0`` on query-less searches), windows
sized so a company's per-window hit count stays under the ~100-hit page cap. Rows are written
through ``filing_scan_service.upsert_filings`` (NOT-NULL-safe, accession-deduped). Each company is
stamped ``companies.history_backfilled_at`` so the on-visit enqueue never re-walks it.

Amendments (/A) are excluded, matching the company-filings display's form set (10-K, 10-Q).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, Watchlist
from app.services import filing_scan_service
from app.services.edgar.config import FilingType
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)

# Forms we backfill + display. Amendments (/A) are intentionally excluded to match the
# company-filings endpoint's default form set (no double-listing of restated periods).
_BACKFILL_FORMS = ("10-K", "10-Q")
_ALLOWED_FILING_TYPES = frozenset(_BACKFILL_FORMS)
# Transient-5xx retries scoped to THIS path — the shared limiter's execute_with_backoff only
# retries rate-limit errors, not the sporadic 5xx EFTS emits, so we add a small bounded ladder.
_BACKFILL_RETRY_ATTEMPTS = 3


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
    and amendments — so only clean 10-K/10-Q rows are inserted."""
    accession = getattr(hit, "accession_no", None)
    sec_url = getattr(hit, "sec_url", None)
    document_url = getattr(hit, "document_url", None)
    raw_form = getattr(hit, "form", None)
    filed_date = getattr(hit, "filed_date", None)
    if not accession or not sec_url or not document_url or not raw_form or not filed_date:
        return None
    ftype = FilingType.from_string(raw_form, strict=False)
    if ftype is FilingType.UNKNOWN or ftype.value not in _ALLOWED_FILING_TYPES:
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


async def backfill_company(db: Session, company: Company, *, efts_client=None) -> dict:
    """Backfill one company's 10-K/10-Q history since ``HISTORY_BACKFILL_SINCE_YEAR`` and stamp it.

    A per-window EFTS failure (after retries) is logged and skipped, not raised — a partial
    backfill is fine (the next visit/run re-covers it). The company is stamped only when at least
    one window succeeded, so a total EFTS outage retries on the next visit instead of marking the
    company done with no data."""
    if efts_client is None:
        from app.integrations.sec_api import sec_full_text_search_client
        efts_client = sec_full_text_search_client

    forms = ",".join(_BACKFILL_FORMS)
    windows = _windows(
        settings.HISTORY_BACKFILL_SINCE_YEAR, utcnow(), settings.HISTORY_BACKFILL_WINDOW_YEARS
    )

    seen: set[str] = set()
    rows: list[dict] = []
    windows_ok = 0
    for start, end in windows:
        try:
            result = await _search_window_with_retry(
                efts_client, forms=forms, cik=company.cik, start=start, end=end
            )
        except Exception:
            logger.exception(
                "History backfill window %s..%s failed for %s after retries", start, end, company.ticker
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

    inserted = filing_scan_service.upsert_filings(db, company, rows)
    if windows_ok:
        company.history_backfilled_at = utcnow()
        db.commit()
    stats = {
        "ticker": company.ticker, "windows": len(windows), "windows_ok": windows_ok,
        "hits": len(rows), "inserted": len(inserted),
    }
    logger.info("History backfill %s", stats)
    return stats


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
        ids = [cid for (cid,) in db.query(Watchlist.company_id).distinct().all()]
        q = q.filter(Company.id.in_(ids)) if ids else q.filter(Company.id.is_(None))
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
    for company in companies:
        try:
            s = await backfill_company(db, company)
            totals["companies"] += 1
            totals["inserted"] += s["inserted"]
        except Exception:
            db.rollback()
            totals["failed"] += 1
            logger.exception("History backfill failed for %s", getattr(company, "ticker", "?"))
    logger.info("History backfill batch complete: %s", totals)
    return totals
