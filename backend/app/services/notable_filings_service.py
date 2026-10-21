"""Notable filings — market-wide EDGAR-native discovery for the homepage.

Replaces the retired own-DB "Trending Filings" section (keep/fix/kill review,
``tasks/homepage-sections-review-findings.md``): instead of re-sorting the 20 most recent filings
we happen to have ingested, a twice-daily scan sweeps EDGAR full-text search (EFTS) across ALL
companies for high-signal filings — 8-Ks with material item codes, 10-K/10-Q, S-1, SC 13D — scores
them with signals we own, and persists the candidates in ``notable_filings``. The public endpoint
serves ONLY from Postgres (provider blips can never blank the homepage; the section self-omits).

Three layers, mirroring ``earnings_calendar_service``:

1. **Pure scoring** (no I/O, ``pulse_service``-style): form/item weights and reason derivation.
   The stored score (base signal plus owned demand) breaks a tie between filings of one day when
   the feed is served.
2. **Scan** (``run_scan``): EFTS query plan generalizing ``_sweep_edgar_2_02`` — phrase queries
   narrow high-volume forms server-side (the definitive filter is client-side on ``hit.items``),
   query-less first-page listings cover the low-volume forms (EFTS 500s on query-less pagination,
   so those are page-0 only, per-day). Upserts on ``accession_number``; prunes rows older than
   14 days. Runs as a dedicated Cloud Run job (``scripts/notable_filings_job.py``) — recurring
   work must not ride the ``/internal/jobs/*`` BackgroundTasks (see DEPLOYMENT.md).
3. **Serve** (``get_notable_filings``): D-046's rule (``docs/brand/decisions-log.md``, F3). From the
   ≤7-day window it serves 10-K and 10-Q filings only (``SERVED_FORMS``, matched exactly;
   ``base_signal`` keeps any form ending in "/A" out of the table), from companies that hold a
   summary the filing page shows (``summary_placeholders.is_summary_ready``; the company is the
   candidate's issuer, the stored company holding its CIK and its ticker), newest first with the
   stored score breaking a tie, one filing per company, at most ``MAX_FILINGS``. The scan's other
   forms stay stored and are not served. Fewer than ``MIN_COMPANIES`` distinct companies → empty
   (ReportingThisWeek's self-omission contract). Gated on ``settings.NOTABLE_FILINGS_ENABLED`` so the
   surface ships dark. Never raises.
"""
from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, Filing, NotableFiling, Summary, UserSearch, Watchlist
from app.services.earnings_calendar_service import today_eastern
from app.services.summary_placeholders import is_summary_ready
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)

# Below this many distinct companies the section would look sparse next to the rest of the
# homepage — treated the same as empty so the section omits itself (ReportingThisWeek precedent;
# the review's "a one-card section is worse than absence").
MIN_COMPANIES = 3

# Serve window: the section promises filings "from the past week".
SERVE_WINDOW_DAYS = 7
# Rows older than this are pruned by the scan — nothing serves them anymore.
RETENTION_DAYS = 14

# D-046 (docs/brand/decisions-log.md, F3): the feed serves annual and quarterly reports only, at
# most six. The scan keeps scoring and storing its other forms; the serve path leaves them out.
SERVED_FORMS: Tuple[str, ...] = ("10-K", "10-Q")
MAX_FILINGS = 6

# ---------------------------------------------------------------------------- pure scoring

# 8-K item weights, highest-signal first. An 8-K whose items match NONE of these is dropped —
# routine 7.01 (Reg FD) / 8.01 (other events) / 9.01 (exhibits-only) disclosures are noise for a
# homepage discovery surface. Weights are also the reason-precedence order.
_ITEM_WEIGHTS: List[Tuple[str, float, str]] = [
    ("1.03", 95.0, "bankruptcy"),
    ("4.02", 90.0, "restatement"),
    ("2.02", 80.0, "earnings_results"),
    ("2.01", 75.0, "acquisition"),
    ("5.02", 65.0, "executive_change"),
    ("1.01", 60.0, "material_agreement"),
]

# Non-8-K form weights + reasons.
_FORM_WEIGHTS: Dict[str, Tuple[float, str]] = {
    "SC 13D": (70.0, "activist_stake"),
    "10-K": (55.0, "annual_report"),
    "10-Q": (45.0, "quarterly_report"),
    "S-1": (40.0, "ipo_filing"),
}

# Display copy for each internal reason slug. These labels state only what the filing form or 8-K
# item category proves; the scan does not read filing prose to corroborate a narrower event claim.
REASON_LABELS: Dict[str, str] = {
    "bankruptcy": "Bankruptcy or receivership",
    "restatement": "Non-reliance disclosure",
    "earnings_results": "Results or financial condition",
    "acquisition": "Completed acquisition or disposition",
    "activist_stake": "Beneficial ownership filing",
    "executive_change": "Leadership or compensation disclosure",
    "material_agreement": "Material agreement",
    "annual_report": "Annual report",
    "quarterly_report": "Quarterly report",
    "ipo_filing": "S-1 registration filing",
}


def base_signal(form: Optional[str], items: Optional[List[str]]) -> Optional[Tuple[float, str]]:
    """Map a filing's (form, 8-K items) to its (base weight, reason slug), or None to drop it.

    8-Ks score by their highest-weighted material item; other forms by the form itself.
    Amendments (a form string still ending in "/A" — EFTS ``root_form`` usually strips this, so
    the check is a belt-and-braces guard) are dropped: the original filing was the news.
    """
    normalized = (form or "").strip().upper()
    if not normalized or normalized.endswith("/A"):
        return None
    if normalized == "8-K":
        item_set = {str(i).strip() for i in (items or [])}
        for code, weight, reason in _ITEM_WEIGHTS:
            if code in item_set:
                return weight, reason
        return None
    return _FORM_WEIGHTS.get(normalized)


_DEMAND_BOOST_CAP = 30.0


def demand_boost(watch_count: int, search_count: int) -> float:
    """Own-user demand: log-scaled watchlist + 7-day search counts (the shape of
    ``compute_anticipation_score``). Capped so demand re-ranks within neighbouring signal tiers
    but can never lift a routine 10-Q (45) over an unwatched bankruptcy (95)."""
    raw = 10.0 * math.log1p(max(0, watch_count)) + 4.0 * math.log1p(max(0, search_count))
    return min(_DEMAND_BOOST_CAP, raw)


# ---------------------------------------------------------------------------- scan

@dataclass
class ScanStats:
    queries: int = 0
    pages: int = 0
    raw_hits: int = 0
    dropped_duplicate: int = 0
    dropped_no_ticker: int = 0
    dropped_low_signal: int = 0
    dropped_no_url: int = 0
    dropped_bad_date: int = 0
    upserted_new: int = 0
    upserted_updated: int = 0
    pruned: int = 0
    # True when the final commit failed and the run was rolled back — the other counters then
    # describe work that was DISCARDED (same contract as RefreshStats.commit_failed).
    commit_failed: bool = False
    source_errors: int = 0
    truncated_queries: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "queries": self.queries,
            "pages": self.pages,
            "raw_hits": self.raw_hits,
            "dropped_duplicate": self.dropped_duplicate,
            "dropped_no_ticker": self.dropped_no_ticker,
            "dropped_low_signal": self.dropped_low_signal,
            "dropped_no_url": self.dropped_no_url,
            "dropped_bad_date": self.dropped_bad_date,
            "upserted_new": self.upserted_new,
            "upserted_updated": self.upserted_updated,
            "pruned": self.pruned,
            "commit_failed": self.commit_failed,
            "source_errors": self.source_errors,
            "truncated_queries": self.truncated_queries,
        }


# The EFTS query plan. Phrase queries reuse the `_sweep_edgar_2_02` doctrine: the phrase only
# narrows the result set server-side (paginating safely, which query-less EFTS cannot — it 500s
# on from>0); the definitive filter is client-side via `base_signal`. Phrases are the standard
# 8-K item headings / statutory cover-page language, so misses are rare and cost only absence
# from a discovery surface.
_EIGHT_K_PHRASES: List[str] = [
    '"Results of Operations and Financial Condition"',        # 2.02
    '"Entry into a Material Definitive Agreement"',           # 1.01
    '"Completion of Acquisition or Disposition of Assets"',   # 2.01
    '"Departure of Directors or Certain Officers"',           # 5.02
    # 4.02 — the official heading starts "Non-Reliance …", but EFTS 500s on the hyphenated
    # token inside a quoted phrase (observed live 2026-07-06); this hyphen-free sub-phrase is
    # still specific and the definitive filter is items-based anyway.
    '"Previously Issued Financial Statements"',               # 4.02
    '"Bankruptcy or Receivership"',                           # 1.03
]
_EIGHT_K_PAGE_CAP = 12
_REPORT_QUERIES: List[Tuple[str, str, int]] = [
    # (form, query, page cap) — cover-page statutory language
    ("10-K", '"annual report"', 10),
    ("10-Q", '"quarterly report"', 10),
]
# Low-volume forms (~10-40 filings/day market-wide): query-less listings, one page per DAY so a
# single page-0 response (~100 hits) can't silently truncate a multi-day window.
_LISTING_FORMS: List[str] = ["S-1", "SC 13D"]


def _parse_filed_date(value: Optional[str]) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


async def _paged_search(
    efts_client, stats: ScanStats, seen: set, collected: List[Any],
    *, query: Optional[str], forms: str, start: str, end: str, max_pages: int,
) -> None:
    """One EFTS query, paginated, appending unseen hits to ``collected``.

    Generalizes ``earnings_calendar_service._sweep_edgar_2_02``: page via from_offset/total,
    dedupe on accession across ALL queries in the scan (exhibits arrive as separate hits), and
    log (never silently truncate) when the page cap is hit.
    """
    stats.queries += 1
    offset = 0
    total = 0
    for _ in range(max_pages):
        try:
            result = await efts_client.search(
                query=query, forms=forms, start_date=start, end_date=end, from_offset=offset
            )
        except Exception:
            # EFTS pagination 500s sporadically at deeper offsets (observed live at from=200,
            # 2026-07-06). Keep the hits already collected from earlier pages rather than
            # aborting the whole query; the overlapping next scan re-covers the window.
            if offset:
                stats.source_errors += 1
                stats.truncated_queries.append(f"{forms}:{query or 'listing'}@{offset}")
                logger.warning(
                    "Notable-filings sweep aborted mid-pagination for %s:%s at offset %s "
                    "(EFTS error); keeping %s hits already collected",
                    forms, query, offset, len(collected),
                )
                return
            raise
        stats.pages += 1
        page = getattr(result, "hits", []) or []
        total = getattr(result, "total", 0)
        if not page:
            break
        for hit in page:
            stats.raw_hits += 1
            key = getattr(hit, "accession_no", None) or ""
            if not key or key in seen:
                stats.dropped_duplicate += 1
                continue
            seen.add(key)
            collected.append(hit)
        offset += len(page)
        if offset >= total:
            break
        if not query:
            # Query-less EFTS pagination 500s (sec_api guard) — page 0 only by design.
            break
    if offset < total and (query or offset >= max_pages * 100):
        label = f"{forms}:{query or 'listing'}"
        stats.truncated_queries.append(label)
        logger.warning(
            "Notable-filings sweep hit its page cap for %s (%s of %s hits scanned, %s..%s)",
            label, offset, total, start, end,
        )


async def run_scan(db: Session, *, efts_client=None, days: Optional[int] = None) -> ScanStats:
    """Sweep EDGAR for the trailing window, score, upsert into ``notable_filings``, prune.

    Provider failures retain partial work and return error counters; the CLI records failure
    and exits nonzero, while API callers keep best-effort returns. Request budget: worst case (peak
    earnings/10-K season) ≈ 56 requests ≈ 56 s of the job's own 1 req/s bucket (deploy-pinned; 10 locally);
    typical ≈ 25.
    """
    stats = ScanStats()
    if efts_client is None:
        from app.integrations.sec_api import sec_full_text_search_client
        efts_client = sec_full_text_search_client

    today = today_eastern()
    window_days = days if days is not None else settings.NOTABLE_FILINGS_SCAN_DAYS
    start_date = today - timedelta(days=max(0, window_days))
    start = start_date.isoformat()
    end = today.isoformat()

    seen: set = set()
    collected: List[Any] = []

    # 8-K phrase sweeps (paginated).
    for phrase in _EIGHT_K_PHRASES:
        try:
            await _paged_search(
                efts_client, stats, seen, collected,
                query=phrase, forms="8-K", start=start, end=end, max_pages=_EIGHT_K_PAGE_CAP,
            )
        except Exception:
            stats.source_errors += 1
            logger.exception("Notable-filings 8-K sweep failed for %s", phrase)

    # 10-K / 10-Q cover-page sweeps (paginated).
    for form, query, cap in _REPORT_QUERIES:
        try:
            await _paged_search(
                efts_client, stats, seen, collected,
                query=query, forms=form, start=start, end=end, max_pages=cap,
            )
        except Exception:
            stats.source_errors += 1
            logger.exception("Notable-filings %s sweep failed", form)

    # Low-volume query-less listings, one page-0 request per day in the window.
    for form in _LISTING_FORMS:
        day = start_date
        while day <= today:
            iso = day.isoformat()
            try:
                await _paged_search(
                    efts_client, stats, seen, collected,
                    query=None, forms=form, start=iso, end=iso, max_pages=1,
                )
            except Exception:
                stats.source_errors += 1
                logger.exception("Notable-filings %s listing failed for %s", form, iso)
            day += timedelta(days=1)

    watch_counts = _watch_counts(db)
    search_counts = _search_counts(db)

    # Score + upsert.
    rows: Dict[str, dict] = {}
    for hit in collected:
        signal = base_signal(getattr(hit, "form", None), getattr(hit, "items", None))
        if signal is None:
            stats.dropped_low_signal += 1
            continue
        ticker = (getattr(hit, "ticker", None) or "").strip().upper()
        if not ticker:
            stats.dropped_no_ticker += 1
            continue
        sec_url = getattr(hit, "sec_url", None)
        if not sec_url:
            stats.dropped_no_url += 1
            continue
        filed = _parse_filed_date(getattr(hit, "filed_date", None))
        if filed is None:
            stats.dropped_bad_date += 1
            continue
        weight, reason = signal
        score = weight + demand_boost(watch_counts.get(ticker, 0), search_counts.get(ticker, 0))
        accession = getattr(hit, "accession_no")
        rows[accession] = {
            "accession_number": accession,
            "ticker": ticker,
            "cik": getattr(hit, "cik", None),
            "company_name": getattr(hit, "company", None),
            "form": (getattr(hit, "form", "") or "").strip().upper(),
            "items": (getattr(hit, "items", None) or None),
            "reason": reason,
            "filed_date": filed,
            "score": score,
            "sec_url": sec_url,
        }

    now = utcnow()
    try:
        if rows:
            existing = {
                row.accession_number: row
                for row in db.query(NotableFiling)
                .filter(NotableFiling.accession_number.in_(list(rows.keys())))
                .all()
            }
            for accession, payload in rows.items():
                current = existing.get(accession)
                if current is None:
                    db.add(NotableFiling(**payload, first_seen_at=now, last_seen_at=now))
                    stats.upserted_new += 1
                else:
                    # Refresh everything except first_seen_at (demand/score move between scans).
                    for key, value in payload.items():
                        setattr(current, key, value)
                    current.last_seen_at = now
                    stats.upserted_updated += 1

        cutoff = today - timedelta(days=RETENTION_DAYS)
        stats.pruned = (
            db.query(NotableFiling)
            .filter(NotableFiling.filed_date < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        logger.exception("Notable-filings scan commit failed; rolling back this run")
        db.rollback()
        stats.commit_failed = True

    return stats


def _watch_counts(db: Session) -> Dict[str, int]:
    """company.ticker(upper) -> watchers. One grouped query (shape of
    ``earnings_calendar_service._watch_counts``); empty on any failure."""
    try:
        rows = (
            db.query(Company.ticker, func.count(Watchlist.id))
            .join(Watchlist, Watchlist.company_id == Company.id)
            .group_by(Company.ticker)
            .all()
        )
        return {(t or "").upper(): int(n) for t, n in rows if t}
    except Exception:
        logger.warning("Notable-filings watch-count query failed", exc_info=True)
        return {}


def _search_counts(db: Session, *, days: int = 7) -> Dict[str, int]:
    """company.ticker(upper) -> UserSearch rows in the trailing window; empty on any failure."""
    try:
        since = utcnow() - timedelta(days=days)
        rows = (
            db.query(Company.ticker, func.count(UserSearch.id))
            .join(UserSearch, UserSearch.company_id == Company.id)
            .filter(UserSearch.created_at >= since)
            .group_by(Company.ticker)
            .all()
        )
        return {(t or "").upper(): int(n) for t, n in rows if t}
    except Exception:
        logger.warning("Notable-filings search-count query failed", exc_info=True)
        return {}


# ---------------------------------------------------------------------------- serve

def _cik_key(cik: Optional[str]) -> Optional[str]:
    """A CIK with its leading zeros stripped, the one form its spellings share; None for none."""
    return str(cik or "").strip().lstrip("0") or None


def _issuer(row: NotableFiling) -> Optional[Tuple[str, str]]:
    """A candidate's issuer as ``(CIK, ticker)``; None when the scan stored no CIK or ticker."""
    cik = _cik_key(row.cik)
    return (cik, row.ticker) if cik and row.ticker else None


def _issuers_with_ready_summary(db: Session, issuers: Set[Tuple[str, str]]) -> Set[Tuple[str, str]]:
    """The ``(CIK, ticker)`` pairs among ``issuers`` whose stored company holds a summary the
    filing page shows.

    A candidate is an EDGAR row, not an ingested filing, so the test is at its issuer: the stored
    company holding the candidate's CIK, since ``Company.cik`` is unique and ``Company.ticker`` is
    not (a reused ticker can name an older issuer). That company must also carry the candidate's
    ticker, the lookup ``/company/{ticker}`` makes (``filing_list_service.stored_company_identity``),
    so a card opens the company this found; any of its filings counts. A CIK is matched in its
    zero-padded and stripped spellings, as ``company_resolution`` matches it. Readiness is
    ``is_summary_ready``, the filing page's rule, with ``raw_summary.writer_error`` read in the
    database as ``latest_filing_service`` reads it, so no ``raw_summary`` is loaded. One query for
    the whole window, never one per candidate.
    """
    if not issuers:
        return set()
    spellings = sorted({spelling for cik, _ in issuers for spelling in (cik, cik.zfill(10))})
    writer_error = Summary.raw_summary["writer_error"].as_string()
    rows = (
        db.query(Company.cik, Company.ticker, Summary.business_overview, writer_error)
        .join(Filing, Filing.company_id == Company.id)
        .join(Summary, Summary.filing_id == Filing.id)
        .filter(Company.cik.in_(spellings))
        .all()
    )
    ready = {
        (_cik_key(cik), ticker) for cik, ticker, overview, failed in rows if is_summary_ready(overview, failed)
    }
    return ready & issuers


class NotableFilingsService:
    """Serve-from-Postgres read path with an L1 cache (Redis is off in prod, ADR-0004)."""

    _cache_ttl = timedelta(minutes=15)

    def __init__(self) -> None:
        # The served list (at most MAX_FILINGS, unsliced by `limit`) with its New York day and fill
        # time, so different `limit` values within one cache window each get correctly sliced
        # results (ReportingThisWeekService's cache rationale). Requests read it from worker
        # threads, so a fill replaces the whole snapshot in one assignment: a reader sees one fill
        # or the next, never a mix.
        self._cache: Optional[Tuple[date, datetime, List[Dict[str, Any]]]] = None
        # Single flight (ReportingThisWeekService's fill lock, a thread lock here because requests
        # run in the thread pool): concurrent misses queue here and recheck, so one read fills the
        # cache instead of one pooled connection each. A waiter holds no connection: its session
        # has run no query yet. A failed read fills nothing, so the next waiter reads again
        # (lessons/arch-cache-only-reads-that-succeeded.md).
        self._fill_lock = threading.Lock()

    def _cached(
        self, today: date, now: datetime
    ) -> Optional[Tuple[date, datetime, List[Dict[str, Any]]]]:
        """The cached snapshot, if it is for ``today`` and inside the TTL."""
        cached = self._cache
        if cached is not None and cached[0] == today and now - cached[1] < self._cache_ttl:
            return cached
        return None

    def get_notable_filings(
        self, db: Session, *, limit: int = MAX_FILINGS, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """D-046's notable filings, ≤``SERVE_WINDOW_DAYS`` old. Always returns a dict with a
        ``filings`` list (possibly empty) and ``status`` (``ok`` | ``empty``). Never raises.

        Synchronous SQLAlchemy: the route runs it in the thread pool and releases the session in
        the same unit (``lessons/ops-release-cached-filing-reads-before-yield.md``)."""
        now = utcnow()
        today = today_eastern()

        if not settings.NOTABLE_FILINGS_ENABLED:
            return {"filings": [], "status": "empty", "timestamp": now.isoformat()}

        hit = None if force_refresh else self._cached(today, now)
        if hit is None:
            with self._fill_lock:
                now = utcnow()
                hit = None if force_refresh else self._cached(today, now)
                if hit is None:
                    fetched = self._fetch(db, today)
                    if fetched is None:  # a failed read serves this request only; the next retries
                        hit = (today, now, [])
                    else:
                        hit = (today, now, fetched)
                        self._cache = hit
        _, filled_at, served = hit

        status = "ok" if len(served) >= MIN_COMPANIES else "empty"
        return {
            "filings": served[:limit] if status == "ok" else [],
            "status": status,
            "timestamp": filled_at.isoformat(),
        }

    def _fetch(self, db: Session, today: date) -> Optional[List[Dict[str, Any]]]:
        """D-046's list: the window's ``SERVED_FORMS`` rows from companies holding a summary the
        filing page shows, newest first (the stored score, then the accession number, breaking a
        tie, as ``ops/detection/notable_homepage_candidates.sql`` orders the window), a company's
        newest row standing for it, at most ``MAX_FILINGS``. Two queries for the whole window.
        ``None`` when a read failed, so the caller can tell it from an empty window."""
        window_start = today - timedelta(days=SERVE_WINDOW_DAYS)
        try:
            rows = (
                db.query(NotableFiling)
                .filter(NotableFiling.filed_date >= window_start, NotableFiling.form.in_(SERVED_FORMS))
                .order_by(
                    NotableFiling.filed_date.desc(),
                    NotableFiling.score.desc(),
                    NotableFiling.accession_number,
                )
                .all()
            )
            summarized = _issuers_with_ready_summary(db, {_issuer(row) for row in rows if _issuer(row)})
        except Exception as exc:  # never let a query hiccup break the homepage
            logger.warning("Notable-filings fetch failed: %s", exc)
            return None

        served: List[NotableFiling] = []
        seen: Set[str] = set()
        for row in rows:  # newest first, so a company's first row is its newest
            if _issuer(row) not in summarized or row.ticker in seen:
                continue
            seen.add(row.ticker)
            served.append(row)
            if len(served) == MAX_FILINGS:
                break
        return [
            {
                "ticker": row.ticker,
                "company_name": row.company_name or row.ticker,
                "form": row.form,
                "reason": row.reason,
                "reason_label": REASON_LABELS.get(row.reason, row.reason.replace("_", " ").title()),
                "filed_date": row.filed_date.isoformat(),
                "sec_url": row.sec_url,
            }
            for row in served
        ]


notable_filings_service = NotableFilingsService()
