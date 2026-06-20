"""Multi-year fundamentals timeline from the SEC company-facts API.

Builds an annual (fiscal-year) time series for headline financial metrics by
reading the public, keyless SEC company-facts endpoint
(``https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json``) — the same source
the XBRL service already falls back to.

This is deliberately distinct from the per-filing ``Filing.xbrl_data`` extraction
in ``edgar/xbrl_service.py``: that surfaces a single filing's current/prior
figures, whereas this returns a long annual series (up to ~12 years) for
charting trends. It calls company-facts once per company and caches the small
parsed result (the raw payload can be several MB).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_FETCH_TIMEOUT = 30.0
_MAX_YEARS = 12

# Parsed-result cache (raw company-facts is multi-MB; the parsed series is tiny).
# In-memory only, which matches prod (Redis is off there). Keyed by zero-padded CIK.
_CACHE_TTL_SECONDS = 6 * 60 * 60
_CACHE_MAX = 256
_cache: "Dict[str, Tuple[float, Dict[str, List[Tuple[int, str, float]]]]]" = {}

_USD = ("USD",)
# metric_key -> (label, candidate us-gaap concepts, unit keys, kind)
#   kind: "duration" (flow item with a start date) | "instant" (balance-sheet item)
_METRICS: Dict[str, Tuple[str, List[str], Tuple[str, ...], str]] = {
    "revenue": (
        "Revenue",
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "NetSales",
            "Revenue",
            "TotalRevenue",
        ],
        _USD,
        "duration",
    ),
    "gross_profit": ("Gross Profit", ["GrossProfit"], _USD, "duration"),
    "operating_income": ("Operating Income", ["OperatingIncomeLoss"], _USD, "duration"),
    "net_income": ("Net Income", ["NetIncomeLoss", "ProfitLoss"], _USD, "duration"),
    "operating_cash_flow": (
        "Operating Cash Flow",
        [
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ],
        _USD,
        "duration",
    ),
    "eps_diluted": (
        "Diluted EPS",
        ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
        ("USD/shares", "pure", "USD"),
        "duration",
    ),
    "total_assets": ("Total Assets", ["Assets"], _USD, "instant"),
    "shareholders_equity": (
        "Shareholders' Equity",
        [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ],
        _USD,
        "instant",
    ),
}
_UNIT_LABEL = {"eps_diluted": "USD/share"}


@dataclass
class FundamentalPoint:
    fiscal_year: int
    period_end: str
    value: float


@dataclass
class MetricSeries:
    metric: str
    label: str
    unit: str  # "USD" | "USD/share" | "percent"
    points: List[FundamentalPoint]


@dataclass
class FundamentalsTimeline:
    ticker: str
    cik: str
    company_name: Optional[str]
    metrics: List[MetricSeries]


def _annual_points(
    fact: object, unit_keys: Tuple[str, ...], kind: str
) -> List[Tuple[int, str, float]]:
    """Extract [(fiscal_year, period_end, value)] of annual figures from one concept.

    Annual = reported on a 10-K. For flow items we additionally require a
    full-year (~365-day) duration so the Q4 stub that also appears in a 10-K is
    excluded. Deduped by fiscal year, preferring the FY period and latest filing.
    """

    if not isinstance(fact, dict):
        return []
    units = fact.get("units")
    if not isinstance(units, dict):
        return []

    rows: list = []
    for unit_key in unit_keys:
        data = units.get(unit_key)
        if isinstance(data, list) and data:
            rows = data
            break
    if not rows:
        return []

    def _rank(item: dict) -> Tuple[int, str]:
        return (1 if item.get("fp") == "FY" else 0, item.get("filed") or "")

    best_by_fy: Dict[int, dict] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        if not str(item.get("form") or "").startswith("10-K"):
            continue
        fy, end, val = item.get("fy"), item.get("end"), item.get("val")
        if fy is None or end is None or val is None:
            continue
        if kind == "duration":
            start = item.get("start")
            if not start:
                continue
            try:
                days = (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days
            except (ValueError, TypeError):
                continue
            if not (300 <= days <= 400):
                continue
        incumbent = best_by_fy.get(fy)
        if incumbent is None or _rank(item) > _rank(incumbent):
            best_by_fy[fy] = item

    points: List[Tuple[int, str, float]] = []
    for fy, item in best_by_fy.items():
        try:
            points.append((int(fy), str(item["end"]), float(item["val"])))
        except (ValueError, TypeError):
            continue
    points.sort(key=lambda p: p[0], reverse=True)
    return points[:_MAX_YEARS]


def _series_for(
    us_gaap: dict, candidates: List[str], unit_keys: Tuple[str, ...], kind: str
) -> List[Tuple[int, str, float]]:
    """Pick the candidate concept with the most recent annual data.

    Issuers retire tags over time (e.g. AAPL moved from ``Revenues`` to
    ``RevenueFromContractWithCustomerExcludingAssessedTax``), so the concept with
    the newest fiscal year — not merely the first present — is the live one.
    """

    best: List[Tuple[int, str, float]] = []
    best_latest = -1
    for concept in candidates:
        points = _annual_points(us_gaap.get(concept), unit_keys, kind)
        if points and points[0][0] > best_latest:
            best, best_latest = points, points[0][0]
    return best


def parse_company_facts(facts_data: object) -> Dict[str, List[Tuple[int, str, float]]]:
    """Parse a company-facts payload into annual series per metric key."""
    out: Dict[str, List[Tuple[int, str, float]]] = {}
    facts = facts_data.get("facts", {}) if isinstance(facts_data, dict) else {}
    us_gaap = facts.get("us-gaap", {}) if isinstance(facts, dict) else {}
    if not isinstance(us_gaap, dict) or not us_gaap:
        return out
    for key, (_label, candidates, unit_keys, kind) in _METRICS.items():
        out[key] = _series_for(us_gaap, candidates, unit_keys, kind)
    return out


def _margin_series(
    numerator: List[Tuple[int, str, float]], revenue_by_fy: Dict[int, Tuple[str, float]]
) -> List[FundamentalPoint]:
    """Year-aligned margin (%) = numerator / revenue * 100, where revenue != 0."""
    points: List[FundamentalPoint] = []
    for fy, end, val in numerator:
        rev = revenue_by_fy.get(fy)
        if not rev or rev[1] == 0:
            continue
        points.append(FundamentalPoint(fiscal_year=fy, period_end=end, value=round(val / rev[1] * 100, 2)))
    return points


def _build_timeline(
    ticker: str,
    cik: str,
    company_name: Optional[str],
    parsed: Dict[str, List[Tuple[int, str, float]]],
) -> FundamentalsTimeline:
    metrics: List[MetricSeries] = []
    for key, (label, _c, _u, _k) in _METRICS.items():
        series = parsed.get(key) or []
        if not series:
            continue
        metrics.append(
            MetricSeries(
                metric=key,
                label=label,
                unit=_UNIT_LABEL.get(key, "USD"),
                points=[FundamentalPoint(fiscal_year=fy, period_end=end, value=val) for fy, end, val in series],
            )
        )

    # Derived margins, aligned by fiscal year against revenue.
    revenue_by_fy = {fy: (end, val) for fy, end, val in (parsed.get("revenue") or [])}
    if revenue_by_fy:
        for key, label in (
            ("gross_profit", "Gross Margin"),
            ("operating_income", "Operating Margin"),
            ("net_income", "Net Margin"),
        ):
            margin_points = _margin_series(parsed.get(key) or [], revenue_by_fy)
            if margin_points:
                metric_name = label.lower().replace(" ", "_")
                metrics.append(MetricSeries(metric=metric_name, label=label, unit="percent", points=margin_points))

    return FundamentalsTimeline(ticker=ticker.upper(), cik=cik, company_name=company_name, metrics=metrics)


def _cache_get(cik: str) -> Optional[Dict[str, List[Tuple[int, str, float]]]]:
    entry = _cache.get(cik)
    if not entry:
        return None
    ts, parsed = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(cik, None)
        return None
    return parsed


def _cache_set(cik: str, parsed: Dict[str, List[Tuple[int, str, float]]]) -> None:
    if len(_cache) >= _CACHE_MAX:
        # Drop the oldest entry (simple bound; this cache is small and low-churn).
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    _cache[cik] = (time.monotonic(), parsed)


async def _fetch_company_facts(
    cik: str, *, transport: Optional[httpx.AsyncBaseTransport] = None
) -> dict:
    url = COMPANY_FACTS_URL.format(cik=cik)
    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT, transport=transport) as client:
        response = await client.get(
            url, headers={"User-Agent": settings.SEC_USER_AGENT, "Accept": "application/json"}
        )
        response.raise_for_status()
        return response.json()


async def get_fundamentals_timeline(
    ticker: str,
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
    company_resolver=None,
) -> FundamentalsTimeline:
    """Resolve the ticker, fetch + parse company-facts, and build the annual timeline.

    ``company_resolver`` is an injection seam for tests; by default it lazily uses
    the EdgarTools client (kept out of module import so this stays unit-testable
    without the heavy ``edgartools`` dependency).

    Raises ``CompanyNotFoundError`` for an unknown ticker (mapped to 404 by the
    router) and ``httpx.HTTPError`` on upstream failure (mapped to 502).
    """

    if company_resolver is None:
        from app.services.edgar import edgar_client

        company_resolver = edgar_client.get_company

    company = await company_resolver(ticker)
    cik = company.cik

    parsed = _cache_get(cik)
    if parsed is None:
        facts = await _fetch_company_facts(cik, transport=transport)
        parsed = parse_company_facts(facts)
        _cache_set(cik, parsed)

    return _build_timeline(ticker, cik, company.name, parsed)
