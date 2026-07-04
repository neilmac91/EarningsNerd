"""Earnings-calendar engine — ingest, reconciliation, scoring, and serving (strategy §3.3–§3.7).

The calendar is served entirely from Postgres (`earnings_events`); providers touch the DB only via
the daily refresh job, never the render path. Sources and precedence:

  reported (edgar_8k)  — 8-K Item 2.02 ground truth; TERMINAL, overrides everything, never overwritten
                         (flips are guarded by timing plausibility — `is_probable_earnings_release` —
                         and the market-wide sweep never inserts rows, it only flips known ones)
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

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Company, EarningsEvent, Watchlist
from app.models.earnings import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
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
from app.services import index_membership_service

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


# 8-K Item 2.02 covers ANY "Results of Operations" disclosure — pre-announcements (BIIB 2026-07-01),
# delivery numbers (TSLA), royalty-trust distribution notices (MVO) — not only earnings releases.
# A 2.02 hit may therefore only flip a calendar row when its TIMING corroborates it: either the
# filing lands in the window where companies actually close and report a quarter, or it lands on
# (±) the date the provider expected the release.
EARNINGS_RELEASE_MIN_GAP_DAYS = 10   # real reporters close books ≥~12d after quarter end (JPM ~14d)
EARNINGS_RELEASE_MAX_GAP_DAYS = 90   # beyond a quarter, the matched row is a stale leftover, not this filing's quarter
EARNINGS_RELEASE_MAX_DELTA_DAYS = 7  # the vast majority of real dates land within ±7d of the provider estimate


def is_probable_earnings_release(filed: date, *, fiscal_period_end: date, event_date: date) -> bool:
    """Timing-plausibility guard for a 2.02 8-K against the calendar row it would flip.

    ``gap`` = days from the row's fiscal quarter end to the filing (earnings releases cluster in
    [10, 90]); ``delta`` = distance from the row's expected date (a release on the expected day is
    plausible even with an off fiscal-period guess). BIIB's pre-announcement (gap 1, delta 28) and
    TSLA's delivery 8-K (gap 2, delta ~20) fail both arms; JPM-style releases (gap ~14) and
    on-estimate releases (delta ≤ 7) pass.
    """
    gap = (filed - fiscal_period_end).days
    delta = abs((filed - event_date).days)
    return (
        EARNINGS_RELEASE_MIN_GAP_DAYS <= gap <= EARNINGS_RELEASE_MAX_GAP_DAYS
        or delta <= EARNINGS_RELEASE_MAX_DELTA_DAYS
    )


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
    # 2.02 hits rejected by the timing-plausibility guard (pre-announcements etc.) — nonzero on a
    # normal week; a sudden zero with high edgar_hits means the guard stopped being applied.
    skipped_non_earnings: int = 0
    # 2.02 hits with no prior calendar row — the market-wide sweep is flip-only, never insert.
    skipped_no_prior: int = 0
    # Rows skipped because their ticker is outside the S&P 500 / Nasdaq 100 universe (only nonzero
    # when CALENDAR_INDEX_FILTER_ENABLED is on). AV estimates for non-members are never inserted, and
    # a stray non-member row is never flipped by the EDGAR sweep.
    skipped_non_member: int = 0
    # Past-dated estimates downgraded to low confidence by the staleness pass.
    stale_downgraded: int = 0
    scored: int = 0
    # True when the final commit failed and the run was rolled back — the other counters then
    # describe work that was DISCARDED. Surfaced in the job log for monitoring (the job itself
    # deliberately never raises, matching filing_scan's contract).
    commit_failed: bool = False

    def as_dict(self) -> dict:
        return {
            "av_rows": self.av_rows,
            "av_upserted": self.av_upserted,
            "edgar_hits": self.edgar_hits,
            "edgar_reported": self.edgar_reported,
            "skipped_non_earnings": self.skipped_non_earnings,
            "skipped_no_prior": self.skipped_no_prior,
            "skipped_non_member": self.skipped_non_member,
            "stale_downgraded": self.stale_downgraded,
            "scored": self.scored,
            "commit_failed": self.commit_failed,
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


def ingest_alpha_vantage(
    db: Session,
    rows: Iterable,
    *,
    today: Optional[date] = None,
    stats: Optional[RefreshStats] = None,
) -> int:
    """Upsert provider estimates. Reported rows are never touched (terminal); a changed date is
    recorded on the row. Past-dated provider rows are skipped — a stale snapshot date must not
    create or overwrite calendar rows (it would also be flip-bait for the EDGAR sweep's 100-day
    attach window). When the index filter is on, tickers outside the S&P 500 / Nasdaq 100 universe
    are skipped here (the only INSERT site) and counted on ``stats.skipped_non_member``. Returns the
    number of rows created or updated."""
    now = datetime.now(timezone.utc)
    if today is None:
        today = today_eastern()
    if stats is None:
        stats = RefreshStats()  # solo callers/tests: keep the counter bumps unconditional
    members = index_membership_service.active_member_filter()
    upserted = 0
    for row in rows:
        ticker = (getattr(row, "symbol", "") or "").upper()
        fpe = getattr(row, "fiscal_period_end", None)
        if not ticker or fpe is None:
            continue  # need a fiscal period to key on (uniqueness invariant)
        if members is not None and index_membership_service.normalize_ticker(ticker) not in members:
            stats.skipped_non_member += 1
            continue  # outside the S&P 500 / Nasdaq 100 universe (index filter on)
        new_date = getattr(row, "report_date", None)
        if new_date is None or new_date < today:
            continue
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


def ingest_edgar_reported(
    db: Session, hits: Iterable, *, stats: Optional[RefreshStats] = None
) -> int:
    """Flip events to ``reported`` from 8-K Item 2.02 hits (ground truth), guarded by timing
    plausibility. Attaches to the open estimate for that ticker whose fiscal period precedes the
    event, falling back to the row keyed on the most-recent calendar quarter-end; a hit only flips
    a row when `is_probable_earnings_release` corroborates it (2.02 also covers pre-announcements
    and other interim disclosures). The market-wide sweep is flip-only: hits with no prior calendar
    row are counted and skipped, never inserted. Returns the number of reported rows written;
    per-skip reasons land on ``stats`` when provided."""
    now = datetime.now(timezone.utc)
    if stats is None:
        stats = RefreshStats()  # keeps the counter bumps unconditional; discarded for solo callers
    members = index_membership_service.active_member_filter()
    reported = 0
    for hit in hits:
        items = getattr(hit, "items", None) or []
        if "2.02" not in items:
            continue  # only earnings-results 8-Ks
        ticker = (getattr(hit, "ticker", None) or "").upper()
        filed = _as_date(getattr(hit, "filed_date", None))
        if not ticker or filed is None:
            continue
        if members is not None and index_membership_service.normalize_ticker(ticker) not in members:
            # Non-member: never flip a stray legacy row, and skip the DB lookups entirely. AV ingest
            # already keeps non-members out, so this is belt-and-suspenders + a cheap early-out.
            stats.skipped_non_member += 1
            continue
        accession = getattr(hit, "accession_no", None)
        acceptance = _as_datetime(getattr(hit, "acceptance_datetime", None))
        # Attach to the open row this 8-K reports: the nearest not-yet-reported event for the ticker
        # whose fiscal period is on/before the filing and whose date is within a quarter of it.
        target = (
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
        if target is None:
            # Fall back to the row keyed on the calendar quarter — it may sit outside the attach
            # window above (e.g. its estimated date was far from the filing).
            dup = (
                db.query(EarningsEvent)
                .filter(
                    EarningsEvent.ticker == ticker,
                    EarningsEvent.fiscal_period_end == most_recent_quarter_end(filed),
                )
                .first()
            )
            if dup is None:
                # Flip-only sweep: a 2.02 hit with no prior calendar row is skipped, never
                # inserted — the item code alone can't establish an earnings event (royalty-trust
                # distribution 8-Ks and the like would pollute the calendar). Extension point:
                # corroborate no-prior hits via the filer's submissions JSON before trusting them.
                stats.skipped_no_prior += 1
                continue
            if dup.status == STATUS_REPORTED:
                continue  # terminal — already flipped (possibly by an earlier hit this run)
            target = dup
        if not is_probable_earnings_release(
            filed, fiscal_period_end=target.fiscal_period_end, event_date=target.event_date
        ):
            # Timing matches neither the quarter-close reporting window nor the expected date:
            # a pre-announcement / interim 2.02, not the earnings release. The estimate stands.
            logger.info(
                "Skipping implausible 2.02 hit for %s (%s): gap=%sd delta=%sd",
                ticker,
                accession,
                (filed - target.fiscal_period_end).days,
                abs((filed - target.event_date).days),
            )
            stats.skipped_non_earnings += 1
            continue
        if target.event_date != filed:
            target.prior_event_date = target.event_date
            target.date_changed_at = now
        target.event_date = filed
        target.status = STATUS_REPORTED
        target.confidence = CONFIDENCE_HIGH
        target.source = SOURCE_EDGAR_8K
        target.accession_number = accession
        # Only set reported_at when we actually have the 8-K acceptance timestamp — the
        # market-wide EFTS sweep carries only the filing DATE, so fabricating the job clock here
        # would be misleading. When acceptance is known, derive the bmo/amc slot from it; when
        # not, keep the company's habitual slot (the estimate's) rather than blanking it.
        target.reported_at = acceptance
        slot = infer_event_time(acceptance)
        if slot:
            target.event_time = slot
        if not target.cik:
            target.cik = getattr(hit, "cik", None)
        target.last_seen_at = now
        reported += 1
    return reported


def downgrade_stale_estimates(db: Session, *, today: date) -> int:
    """Estimates whose date has passed without a reported flip are stale — the date was wrong or
    the 8-K wasn't seen (strategy §3.5). Drop them to low confidence so the UI can frame the date
    as "may move" if the row resurfaces; they stay ``estimated`` and a later provider pass or 8-K
    still updates them. Bulk UPDATE; returns the number of rows downgraded."""
    updated = (
        db.query(EarningsEvent)
        .filter(
            EarningsEvent.status == STATUS_ESTIMATED,
            EarningsEvent.event_date < today,
            EarningsEvent.confidence != CONFIDENCE_LOW,
        )
        .update({"confidence": CONFIDENCE_LOW}, synchronize_session=False)
    )
    return int(updated or 0)


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


async def run_refresh(
    db: Session,
    *,
    av_client=None,
    efts_client=None,
    sweep_from: Optional[date] = None,
    sweep_to: Optional[date] = None,
) -> RefreshStats:
    """Daily ingest: Alpha Vantage bulk estimates + EDGAR 8-K Item 2.02 sweep (yesterday→today),
    then stale-estimate downgrade and rescore. Commits once at the end. Never raises on a provider
    failure. ``sweep_from``/``sweep_to`` widen the EFTS window for a one-shot re-sweep of past days
    (e.g. after a data repair); the scheduled job uses the trailing 2-day default."""
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
        stats.av_upserted = ingest_alpha_vantage(db, av_rows, today=today, stats=stats)
    except Exception:  # never let the bridge break the engine
        logger.exception("Alpha Vantage ingest failed")

    # 2. EDGAR 8-K Item 2.02 sweep for the last two days (covers weekend/holiday gaps).
    try:
        start = (sweep_from or today - timedelta(days=2)).isoformat()
        end = (sweep_to or today).isoformat()
        hits = await _sweep_edgar_2_02(efts_client, start, end)
        stats.edgar_hits = len(hits)
        stats.edgar_reported = ingest_edgar_reported(db, hits, stats=stats)
    except Exception:
        logger.exception("EDGAR 8-K sweep failed")

    # 3. Downgrade past-dated estimates that never got their reported flip.
    try:
        stats.stale_downgraded = downgrade_stale_estimates(db, today=today)
    except Exception:
        logger.exception("Stale-estimate downgrade failed")

    # 4. Rescore the forward window.
    try:
        stats.scored = recompute_scores(db, only_from=today - timedelta(days=7))
    except Exception:
        logger.exception("Anticipation-score recompute failed")

    # Guard the single commit: if any in-run duplicate slipped past the per-insert flush, a rollback
    # keeps the DB consistent (previous good snapshot) rather than half-applying. Errors are logged
    # and surfaced via stats.commit_failed, not raised — a failed daily job must not page anyone;
    # the next run re-ingests.
    try:
        db.commit()
    except Exception:
        logger.exception("Earnings refresh commit failed; rolling back this run")
        db.rollback()
        stats.commit_failed = True
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


def events_in_range(
    db: Session, from_date: date, to_date: date, *, today: Optional[date] = None
) -> list[dict]:
    """All earnings events in [from_date, to_date], highest anticipation first (public /api/calendar).

    Past days serve facts only: an estimate whose date has passed is suppressed — either the
    company already reported (the reported row is what should show) or the estimate was wrong,
    and rendering it on a past day would misstate history."""
    if today is None:
        today = today_eastern()
    query = db.query(EarningsEvent).filter(
        EarningsEvent.event_date >= from_date,
        EarningsEvent.event_date <= to_date,
        or_(EarningsEvent.status == STATUS_REPORTED, EarningsEvent.event_date >= today),
    )
    # Discovery surface: restrict to the S&P 500 / Nasdaq 100 universe when the filter is on. None
    # means "unfiltered" (flag off or list unhealthy), so a bad list can never empty the calendar.
    members = index_membership_service.active_member_filter()
    if members is not None:
        query = query.filter(EarningsEvent.ticker.in_(members))
    rows = query.order_by(
        EarningsEvent.event_date.asc(), EarningsEvent.anticipation_score.desc()
    ).all()
    return [_event_to_dict(ev) for ev in rows]
