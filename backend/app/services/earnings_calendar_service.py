"""Earnings-calendar engine — ingest, reconciliation, scoring, and serving (strategy §3.3–§3.7).

The calendar is served entirely from Postgres (`earnings_events`); providers touch the DB only via
the daily refresh job, never the render path. Sources and precedence:

  reported (edgar_8k)  — 8-K Item 2.02 ground truth; TERMINAL, overrides everything, never overwritten
  provider (alpha_vantage) — forward estimates for not-yet-reported quarters
  pattern              — per-company history estimate (P3; the fallback for provider-missing rows)

Nothing here raises on a provider hiccup: a flaky bridge (Alpha Vantage) must not break the engine,
which still produces reported + already-known rows from EDGAR on its own.

The pure helpers (`infer_event_time`, `most_recent_quarter_end`, `compute_anticipation_score`) carry
the logic worth unit-testing; the DB functions stay thin around them.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company, EarningsEvent, Watchlist
from app.models.earnings import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    SOURCE_ALPHA_VANTAGE,
    SOURCE_EDGAR_8K,
    STATUS_CONFIRMED,
    STATUS_ESTIMATED,
    STATUS_REPORTED,
    TIME_AMC,
    TIME_BMO,
    TIME_DMH,
)

logger = logging.getLogger(__name__)

_NY_TZ = ZoneInfo("America/New_York")

# event_date is an America/New_York calendar day, so "today" for the ingest/alert jobs must be the
# NY date — Cloud Run runs UTC, and date.today() there would query the wrong day near the ET/UTC
# midnight boundary.
def today_eastern() -> date:
    return datetime.now(_NY_TZ).date()

# Curated large caps that should never rank below noise on their reporting day. Reused from the
# homepage feature to keep one canonical list; a mega-cap floor in the anticipation score.
try:
    from app.services.reporting_this_week_service import CURATED_TICKERS as _CURATED
    CURATED_TICKERS = set(_CURATED)
except Exception:  # pragma: no cover - defensive; the constant is a plain dict today
    CURATED_TICKERS = set()


# --------------------------------------------------------------------------- pure helpers

def infer_event_time(acceptance: Optional[datetime]) -> Optional[str]:
    """Map an 8-K acceptance timestamp to a bmo/amc/dmh slot, DST-safe.

    Converts to America/New_York and compares against the trading day: accepted at/before 09:30 ET
    ≈ before open, at/after 16:00 ET ≈ after close, otherwise during market hours. Returns None when
    no timestamp is available (the caller then preserves the habitual slot or leaves it unknown).
    """
    if acceptance is None:
        return None
    dt = acceptance
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ny = dt.astimezone(_NY_TZ)
    minutes = ny.hour * 60 + ny.minute
    if minutes <= 9 * 60 + 30:
        return TIME_BMO
    if minutes >= 16 * 60:
        return TIME_AMC
    return TIME_DMH


_QUARTER_ENDS = ((3, 31), (6, 30), (9, 30), (12, 31))


def most_recent_quarter_end(d: date) -> date:
    """Latest calendar quarter-end on/before ``d`` (fallback fiscal period for a reported 8-K when
    we have no prior estimate row to attach it to — the company's real fiscal quarter is unknown
    without XBRL, refined later by the P3 pattern backfill)."""
    candidates = [date(d.year, m, day) for m, day in _QUARTER_ENDS] + [date(d.year - 1, 12, 31)]
    eligible = [q for q in candidates if q <= d]
    return max(eligible)


def compute_anticipation_score(*, is_curated: bool, watch_count: int, has_estimate: bool) -> float:
    """Owned anticipation ranking (strategy §3.7). v1 uses only signals we control:

      - mega-cap floor: curated names get a large constant so AAPL/NVDA never sink below noise
      - own-user demand: log-scaled watchlist count (our strongest first-party signal)
      - analyst coverage proxy: a small bump when a provider estimate exists

    Public-float weighting (the doc's strongest proxy) arrives with the P3 companyfacts backfill;
    the formula can grow without a schema or API change (raw inputs live in the row's fields).
    """
    score = 0.0
    if is_curated:
        score += 1000.0
    score += 100.0 * math.log1p(max(0, watch_count))
    if has_estimate:
        score += 10.0
    return score


@dataclass
class RefreshStats:
    av_rows: int = 0
    av_upserted: int = 0
    edgar_hits: int = 0
    edgar_reported: int = 0
    scored: int = 0

    def as_dict(self) -> dict:
        return {
            "av_rows": self.av_rows,
            "av_upserted": self.av_upserted,
            "edgar_hits": self.edgar_hits,
            "edgar_reported": self.edgar_reported,
            "scored": self.scored,
        }


# --------------------------------------------------------------------------- ingest

def _watch_counts(db: Session) -> dict[str, int]:
    """company.ticker(upper) -> number of users watching it. One grouped query, no N+1."""
    rows = (
        db.query(Company.ticker, func.count(Watchlist.id))
        .join(Watchlist, Watchlist.company_id == Company.id)
        .group_by(Company.ticker)
        .all()
    )
    return {(t or "").upper(): int(n) for t, n in rows if t}


def ingest_alpha_vantage(db: Session, rows: Iterable) -> int:
    """Upsert provider estimates. Reported rows are never touched (terminal); a changed date is
    recorded on the row. Returns the number of rows created or updated."""
    now = datetime.now(timezone.utc)
    upserted = 0
    for row in rows:
        ticker = (getattr(row, "symbol", "") or "").upper()
        fpe = getattr(row, "fiscal_period_end", None)
        if not ticker or fpe is None:
            continue  # need a fiscal period to key on (uniqueness invariant)
        existing = (
            db.query(EarningsEvent)
            .filter(EarningsEvent.ticker == ticker, EarningsEvent.fiscal_period_end == fpe)
            .first()
        )
        # Precedence: a provider estimate must never overwrite ground truth (reported) OR a
        # confirmed row (a source with a real confirmation flag outranks an AV estimate).
        if existing is not None and existing.status in (STATUS_REPORTED, STATUS_CONFIRMED):
            existing.last_seen_at = now
            continue
        new_date = getattr(row, "report_date", None)
        if new_date is None:
            continue
        if existing is None:
            db.add(
                EarningsEvent(
                    ticker=ticker,
                    company_name=getattr(row, "company_name", None),
                    fiscal_period_end=fpe,
                    event_date=new_date,
                    event_time=getattr(row, "event_time", None),
                    status=STATUS_ESTIMATED,
                    confidence=CONFIDENCE_MEDIUM,
                    eps_estimate=getattr(row, "eps_estimate", None),
                    source=SOURCE_ALPHA_VANTAGE,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            # Flush so this row is visible to later existence checks in the SAME transaction —
            # SessionLocal is autoflush=False, so without this the EDGAR pass (and a repeated
            # (ticker, fpe) later in this run) wouldn't see it and would INSERT a duplicate, making
            # the final commit raise on the unique constraint and lose the whole day's ingest.
            db.flush()
        else:
            if existing.event_date != new_date:
                existing.prior_event_date = existing.event_date
                existing.date_changed_at = now
            existing.event_date = new_date
            if getattr(row, "event_time", None):
                existing.event_time = row.event_time
            if getattr(row, "eps_estimate", None) is not None:
                existing.eps_estimate = row.eps_estimate
            if existing.company_name is None:
                existing.company_name = getattr(row, "company_name", None)
            existing.source = SOURCE_ALPHA_VANTAGE
            existing.last_seen_at = now
        upserted += 1
    return upserted


def ingest_edgar_reported(db: Session, hits: Iterable) -> int:
    """Flip events to ``reported`` from 8-K Item 2.02 hits (ground truth). Attaches to the open
    estimate for that ticker whose fiscal period precedes the event, else inserts a fresh reported
    row keyed on the most-recent calendar quarter-end. Returns the number of reported rows written."""
    now = datetime.now(timezone.utc)
    reported = 0
    for hit in hits:
        items = getattr(hit, "items", None) or []
        if "2.02" not in items:
            continue  # only earnings-results 8-Ks
        ticker = (getattr(hit, "ticker", None) or "").upper()
        filed = _as_date(getattr(hit, "filed_date", None))
        if not ticker or filed is None:
            continue
        accession = getattr(hit, "accession_no", None)
        acceptance = _as_datetime(getattr(hit, "acceptance_datetime", None))
        # Attach to the open row this 8-K reports: the nearest not-yet-reported event for the ticker
        # whose fiscal period is on/before the filing and whose date is within a quarter of it.
        existing = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.ticker == ticker,
                EarningsEvent.status != STATUS_REPORTED,
                EarningsEvent.fiscal_period_end <= filed,
                EarningsEvent.event_date >= filed - timedelta(days=100),
            )
            .order_by(EarningsEvent.fiscal_period_end.desc())
            .first()
        )
        if existing is not None:
            if existing.event_date != filed:
                existing.prior_event_date = existing.event_date
                existing.date_changed_at = now
            existing.event_date = filed
            existing.status = STATUS_REPORTED
            existing.confidence = CONFIDENCE_HIGH
            existing.source = SOURCE_EDGAR_8K
            existing.accession_number = accession
            # Only set reported_at when we actually have the 8-K acceptance timestamp — the
            # market-wide EFTS sweep carries only the filing DATE, so fabricating the job clock here
            # would be misleading. When acceptance is known, derive the bmo/amc slot from it; when
            # not, keep the company's habitual slot (the estimate's) rather than blanking it.
            existing.reported_at = acceptance
            slot = infer_event_time(acceptance)
            if slot:
                existing.event_time = slot
            if not existing.cik:
                existing.cik = getattr(hit, "cik", None)
            existing.last_seen_at = now
        else:
            fpe = most_recent_quarter_end(filed)
            dup = (
                db.query(EarningsEvent)
                .filter(EarningsEvent.ticker == ticker, EarningsEvent.fiscal_period_end == fpe)
                .first()
            )
            if dup is not None:
                # A row already exists for this fiscal period but fell outside the attach window
                # above (e.g. its estimated date was far from the filing). Flip it to reported
                # rather than dropping this genuine 8-K or inserting a duplicate (ticker, fpe).
                if dup.status != STATUS_REPORTED:
                    if dup.event_date != filed:
                        dup.prior_event_date = dup.event_date
                        dup.date_changed_at = now
                    dup.event_date = filed
                    dup.status = STATUS_REPORTED
                    dup.confidence = CONFIDENCE_HIGH
                    dup.source = SOURCE_EDGAR_8K
                    dup.accession_number = accession
                    dup.reported_at = acceptance
                    slot = infer_event_time(acceptance)
                    if slot:
                        dup.event_time = slot
                    dup.last_seen_at = now
                    reported += 1
                continue
            db.add(
                EarningsEvent(
                    ticker=ticker,
                    cik=getattr(hit, "cik", None),
                    company_name=getattr(hit, "company", None),
                    fiscal_period_end=fpe,
                    event_date=filed,
                    event_time=infer_event_time(acceptance),
                    status=STATUS_REPORTED,
                    confidence=CONFIDENCE_HIGH,
                    source=SOURCE_EDGAR_8K,
                    accession_number=accession,
                    reported_at=acceptance,
                    first_seen_at=now,
                    last_seen_at=now,
                )
            )
            db.flush()  # visible to later in-run existence checks (autoflush=False)
        reported += 1
    return reported


def recompute_scores(db: Session, *, only_from: Optional[date] = None) -> int:
    """Recompute ``anticipation_score`` for open rows. Cheap: one grouped watch-count query, then a
    pass over the (bounded) forward window. Returns the number of rows scored."""
    counts = _watch_counts(db)
    q = db.query(EarningsEvent)
    if only_from is not None:
        q = q.filter(EarningsEvent.event_date >= only_from)
    scored = 0
    for ev in q.all():
        ev.anticipation_score = compute_anticipation_score(
            is_curated=ev.ticker in CURATED_TICKERS,
            watch_count=counts.get(ev.ticker, 0),
            has_estimate=ev.eps_estimate is not None,
        )
        scored += 1
    return scored


async def run_refresh(db: Session, *, av_client=None, efts_client=None) -> RefreshStats:
    """Daily ingest: Alpha Vantage bulk estimates + EDGAR 8-K Item 2.02 sweep (yesterday→today),
    then rescore. Commits once at the end. Never raises on a provider failure."""
    stats = RefreshStats()

    if av_client is None:
        from app.integrations.alpha_vantage import alpha_vantage_client
        av_client = alpha_vantage_client
    if efts_client is None:
        from app.integrations.sec_api import sec_full_text_search_client
        efts_client = sec_full_text_search_client

    today = today_eastern()

    # 1. Alpha Vantage bulk estimates.
    try:
        av_rows = await av_client.fetch_earnings_calendar()
        stats.av_rows = len(av_rows)
        stats.av_upserted = ingest_alpha_vantage(db, av_rows)
    except Exception:  # never let the bridge break the engine
        logger.exception("Alpha Vantage ingest failed")

    # 2. EDGAR 8-K Item 2.02 sweep for the last two days (covers weekend/holiday gaps).
    try:
        start = (today - timedelta(days=2)).isoformat()
        end = today.isoformat()
        hits = await _sweep_edgar_2_02(efts_client, start, end)
        stats.edgar_hits = len(hits)
        stats.edgar_reported = ingest_edgar_reported(db, hits)
    except Exception:
        logger.exception("EDGAR 8-K sweep failed")

    # 3. Rescore the forward window.
    try:
        stats.scored = recompute_scores(db, only_from=today - timedelta(days=7))
    except Exception:
        logger.exception("Anticipation-score recompute failed")

    # Guard the single commit: if any in-run duplicate slipped past the per-insert flush, a rollback
    # keeps the DB consistent (previous good snapshot) rather than half-applying. Errors are logged,
    # not raised — a failed daily job must not page anyone; the next run re-ingests.
    try:
        db.commit()
    except Exception:
        logger.exception("Earnings refresh commit failed; rolling back this run")
        db.rollback()
    return stats


async def _sweep_edgar_2_02(efts_client, start: str, end: str, *, max_pages: int = 40) -> list:
    """Page through 8-Ks whose text contains the Item 2.02 heading, keeping only true 2.02 hits.

    The phrase query narrows the result set server-side; the definitive filter is client-side on
    each hit's ``items`` (the `&items=` request param is undocumented/inconsistent — strategy appendix).
    EFTS returns 100 hits/page by default, so max_pages=40 covers ~4000 phrase-matching 8-Ks — well
    above a heavy 2-day window (~700). If the cap is ever hit we log it rather than truncating silently.
    """
    query = '"Results of Operations and Financial Condition"'
    collected: list = []
    seen: set[str] = set()
    offset = 0
    total = 0
    for _ in range(max_pages):
        result = await efts_client.search(
            query=query, forms="8-K", start_date=start, end_date=end, from_offset=offset
        )
        page = getattr(result, "hits", []) or []
        total = getattr(result, "total", 0)
        if not page:
            break
        for hit in page:
            if "2.02" not in (getattr(hit, "items", None) or []):
                continue
            key = getattr(hit, "accession_no", None) or ""
            if key and key not in seen:
                seen.add(key)
                collected.append(hit)
        offset += len(page)
        if offset >= total:
            break
    else:
        # Loop exhausted max_pages without reaching `total` — surface the truncation.
        if offset < total:
            logger.warning(
                "EDGAR 2.02 sweep hit the page cap (%s of %s hits scanned, %s..%s); some reported "
                "flips may be deferred to the next run.", offset, total, start, end,
            )
    return collected


# --------------------------------------------------------------------------- serving

def _as_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _as_datetime(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _event_to_dict(ev: EarningsEvent) -> dict:
    """The public CalendarEvent contract (features/calendar/api/calendar-api.ts)."""
    return {
        "ticker": ev.ticker,
        "company_name": ev.company_name or ev.ticker,
        "event_date": ev.event_date.isoformat() if ev.event_date else None,
        "event_time": ev.event_time,
        "status": ev.status,
        "confidence": ev.confidence,
        "eps_estimate": _to_float(ev.eps_estimate),
        "eps_actual": _to_float(ev.eps_actual),
        "anticipation_score": _to_float(ev.anticipation_score) or 0.0,
    }


def events_in_range(db: Session, from_date: date, to_date: date) -> list[dict]:
    """All earnings events in [from_date, to_date], highest anticipation first (public /api/calendar)."""
    rows = (
        db.query(EarningsEvent)
        .filter(EarningsEvent.event_date >= from_date, EarningsEvent.event_date <= to_date)
        .order_by(EarningsEvent.event_date.asc(), EarningsEvent.anticipation_score.desc())
        .all()
    )
    return [_event_to_dict(ev) for ev in rows]
