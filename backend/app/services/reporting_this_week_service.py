"""Curated large-cap earnings for the current US market week (public, no-auth homepage feature).

Reuses the existing FMP earnings-calendar integration (date-range based, not user-scoped) and
intersects it against a hardcoded curated ticker allowlist. Caching is in-memory only (L1) —
Redis is off in production (SKIP_REDIS_INIT=true) — since this is a cheap, idempotent derived
computation rather than an expensive multi-source aggregation. Never raises; degrades to an
empty result on any FMP failure, so the homepage section can simply omit itself.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.integrations.fmp import FMPClient, fmp_client

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

    def __init__(self, fmp: Optional[FMPClient] = None) -> None:
        self._fmp = fmp or fmp_client
        # Caches the FULL matched list (unlimited) so different callers requesting different
        # `limit` values within the same cache window each get correctly sliced results —
        # caching the already-limited response would let a small-limit request poison the
        # cache for a later, larger-limit request in the same window.
        self._cache_companies: Optional[List[ReportingCompany]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_week: Optional[tuple[date, date]] = None

    async def get_reporting_this_week(
        self, *, limit: int = 16, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Return curated large-caps reporting this week, soonest first.

        Always returns a dict with a `companies` list (possibly empty) and a `status` field
        (`ok` | `empty`). Never raises.
        """
        monday, friday = current_market_week()
        now = datetime.utcnow()

        if (
            not force_refresh
            and self._cache_companies is not None
            and self._cache_timestamp is not None
            and self._cache_week == (monday, friday)
            and now - self._cache_timestamp < self._cache_ttl
        ):
            companies = self._cache_companies
        else:
            companies = await self._fetch(monday, friday)
            self._cache_companies = companies
            self._cache_timestamp = now
            self._cache_week = (monday, friday)

        status = "ok" if len(companies) >= MIN_COMPANIES else "empty"
        sliced = companies[:limit] if status == "ok" else []
        return {
            "companies": [c.to_dict() for c in sliced],
            "week_start": monday.isoformat(),
            "week_end": friday.isoformat(),
            "status": status,
            "timestamp": self._cache_timestamp.isoformat() + "Z",
        }

    async def _fetch(self, monday: date, friday: date) -> List[ReportingCompany]:
        try:
            events = await self._fmp.fetch_earnings_calendar(from_date=monday, to_date=friday)
        except Exception as exc:  # never let a flaky integration break the homepage
            logger.warning("Reporting-this-week FMP fetch failed: %s", exc)
            return []

        matches: List[ReportingCompany] = []
        for symbol, event in (events or {}).items():
            sym = symbol.upper()
            name = CURATED_TICKERS.get(sym)
            if not name:
                continue
            earnings_date = getattr(event, "earnings_date", None)
            if not earnings_date:
                continue
            matches.append(ReportingCompany(
                ticker=sym,
                name=name,
                earnings_date=earnings_date,
                time=getattr(event, "time", None),
            ))

        matches.sort(key=lambda c: (c.earnings_date, c.ticker))
        return matches


reporting_this_week_service = ReportingThisWeekService()
