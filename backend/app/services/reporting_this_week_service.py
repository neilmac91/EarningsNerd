"""Most-anticipated large-cap earnings for the current US market week (public homepage feature).

Now served from the owned `earnings_events` table (strategy §3.7): the week's events ranked by
`anticipation_score` (which carries a mega-cap floor from `CURATED_TICKERS`), replacing the old
FMP ∩ hardcoded-allowlist intersect. Caching is in-memory only (L1) — Redis is off in production
(SKIP_REDIS_INIT=true) — since this is a cheap, idempotent DB read. Never raises; degrades to an
empty result on any failure, so the homepage section can simply omit itself.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import EarningsEvent
from app.models.earnings import STATUS_REPORTED

logger = logging.getLogger(__name__)

_NY_TZ = ZoneInfo("America/New_York")

# Below this many matches, the section would look sparse next to its "premium curated row"
# framing — treated the same as empty so the homepage section omits itself entirely.
MIN_COMPANIES = 4

# Curated large-cap tickers spanning sectors, used ONLY for this feature. Deliberately separate
# from QuickAccessBar's TOP_COMPANIES (frontend) and pregenerate_examples.py's DEFAULT_TICKERS
# (both ~8 tickers) — on any given week only ~1/13 of a company's year has earnings, so a small
# pool would almost always yield zero matches. This list is intentionally broad.
CURATED_TICKERS: Dict[str, str] = {
    # Technology / Internet
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "GOOGL": "Alphabet",
    "AMZN": "Amazon", "META": "Meta", "AVGO": "Broadcom", "ORCL": "Oracle",
    "CRM": "Salesforce", "ADBE": "Adobe", "CSCO": "Cisco", "IBM": "IBM",
    "NFLX": "Netflix", "AMD": "AMD", "INTC": "Intel", "QCOM": "Qualcomm",
    "TXN": "Texas Instruments", "NOW": "ServiceNow", "UBER": "Uber", "BABA": "Alibaba",
    # Financials
    "JPM": "JPMorgan Chase", "BAC": "Bank of America", "WFC": "Wells Fargo",
    "GS": "Goldman Sachs", "MS": "Morgan Stanley", "V": "Visa", "MA": "Mastercard",
    "AXP": "American Express", "BLK": "BlackRock", "C": "Citigroup", "SCHW": "Charles Schwab",
    # Healthcare
    "UNH": "UnitedHealth Group", "JNJ": "Johnson & Johnson", "LLY": "Eli Lilly",
    "PFE": "Pfizer", "ABBV": "AbbVie", "MRK": "Merck", "TMO": "Thermo Fisher Scientific",
    "ABT": "Abbott Laboratories",
    # Consumer
    "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot", "PG": "Procter & Gamble",
    "KO": "Coca-Cola", "PEP": "PepsiCo", "MCD": "McDonald's", "NKE": "Nike",
    "SBUX": "Starbucks", "DIS": "Disney", "TSLA": "Tesla",
    # Industrials / Energy
    "BA": "Boeing", "CAT": "Caterpillar", "GE": "GE Aerospace", "HON": "Honeywell",
    "XOM": "ExxonMobil", "CVX": "Chevron", "UPS": "UPS", "LMT": "Lockheed Martin",
}


@dataclass
class ReportingCompany:
    ticker: str
    name: str
    earnings_date: date
    time: Optional[str]  # "bmo" | "amc" | None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "earnings_date": self.earnings_date.isoformat(),
            "time": self.time,
        }


def current_market_week(today: Optional[date] = None) -> tuple[date, date]:
    """Return (Monday, Friday) of the current US market week in America/New_York,
    independent of the server's or visitor's local timezone."""
    now_ny = (
        datetime.now(_NY_TZ)
        if today is None
        else datetime.combine(today, datetime.min.time(), tzinfo=_NY_TZ)
    )
    monday = now_ny.date() - timedelta(days=now_ny.weekday())  # Monday == 0
    friday = monday + timedelta(days=4)
    return monday, friday


class ReportingThisWeekService:
    """Curated large-cap earnings reporting in the current US market week."""

    _cache_ttl = timedelta(hours=6)

    def __init__(self) -> None:
        # Caches the FULL matched list (unlimited) so different callers requesting different
        # `limit` values within the same cache window each get correctly sliced results —
        # caching the already-limited response would let a small-limit request poison the
        # cache for a later, larger-limit request in the same window.
        self._cache_companies: Optional[List[ReportingCompany]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_week: Optional[tuple[date, date, date]] = None

    async def get_reporting_this_week(
        self, db: Session, *, limit: int = 16, force_refresh: bool = False,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Return the week's most-anticipated large-caps, ranked. Always returns a dict with a
        `companies` list (possibly empty) and a `status` field (`ok` | `empty`). Never raises."""
        # NY-today is resolved locally rather than via earnings_calendar_service.today_eastern():
        # that module imports CURATED_TICKERS from THIS one, and the reverse import would close a
        # cycle its defensive try/except silently swallows — zeroing out curated scoring.
        today_ny = today if today is not None else datetime.now(_NY_TZ).date()
        monday, friday = current_market_week(today_ny)
        now = datetime.now(timezone.utc)

        # today_ny is part of the cache key so the past-day filter rolls at ET midnight rather
        # than whenever the 6h TTL happens to lapse.
        if (
            not force_refresh
            and self._cache_companies is not None
            and self._cache_timestamp is not None
            and self._cache_week == (monday, friday, today_ny)
            and now - self._cache_timestamp < self._cache_ttl
        ):
            companies = self._cache_companies
        else:
            companies = self._fetch(db, monday, friday, today_ny)
            self._cache_companies = companies
            self._cache_timestamp = now
            self._cache_week = (monday, friday, today_ny)

        status = "ok" if len(companies) >= MIN_COMPANIES else "empty"
        sliced = companies[:limit] if status == "ok" else []
        return {
            "companies": [c.to_dict() for c in sliced],
            "week_start": monday.isoformat(),
            "week_end": friday.isoformat(),
            "status": status,
            # isoformat() already carries the +00:00 offset (now that the timestamp is tz-aware);
            # appending "Z" too would malform it.
            "timestamp": self._cache_timestamp.isoformat(),
        }

    def _fetch(self, db: Session, monday: date, friday: date, today: date) -> List[ReportingCompany]:
        """The week's events, most-anticipated first (the anticipation score already carries the
        CURATED_TICKERS mega-cap floor, so no allowlist intersect is needed). Days already behind
        us serve facts only — a past-dated estimate is either already reported or was wrong."""
        try:
            events = (
                db.query(EarningsEvent)
                .filter(
                    EarningsEvent.event_date >= monday,
                    EarningsEvent.event_date <= friday,
                    or_(EarningsEvent.status == STATUS_REPORTED, EarningsEvent.event_date >= today),
                )
                .order_by(EarningsEvent.anticipation_score.desc(), EarningsEvent.event_date.asc())
                .all()
            )
        except Exception as exc:  # never let a query hiccup break the homepage
            logger.warning("Reporting-this-week fetch failed: %s", exc)
            return []

        matches: List[ReportingCompany] = []
        for ev in events:
            if not ev.event_date:
                continue
            name = ev.company_name or CURATED_TICKERS.get(ev.ticker) or ev.ticker
            matches.append(ReportingCompany(
                ticker=ev.ticker,
                name=name,
                earnings_date=ev.event_date,
                time=ev.event_time,
            ))
        return matches


reporting_this_week_service = ReportingThisWeekService()
