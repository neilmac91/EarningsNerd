"""Accession-aware XBRL instance extraction helpers (issue #240).

These helpers operate on an edgartools XBRL instance (``filing.xbrl()``) and
select facts for the filing's OWN reporting period: undimensioned
(consolidated) facts ending on the filing's period_of_report, with durations
matching the form's standard slice (12-month for a 10-K, 3-month for a 10-Q).

They generalize the single-fact selection in ``backend/evals/build_golden_set.py``
(the eval golden-set builder) into the series shape the product's XBRL service
returns, so the product and the eval harness ground on the same period and
duration semantics.

Kept dependency-light on purpose (no app config or edgartools imports): the
eval builder imports from here before app settings are loaded, and unit tests
exercise these functions with fake fact-query objects.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Acceptable duration windows in days. 52/53-week fiscal years run 364-371
# days; fiscal quarters run 84-98. Anything outside is the wrong period slice
# (Q4 vs FY, quarter vs YTD) and must not be reported as the filing's figure.
DURATION_WINDOWS: Dict[str, Tuple[int, int]] = {"10-K": (320, 390), "10-Q": (75, 105)}

# Concept candidates per metric, in priority order. `Revenues` first: within a
# single filing's XBRL instance there is no stale-tag risk (unlike the
# companyfacts API), and when both are tagged `Revenues` is the income
# statement's total top line (e.g. WMT/XOM include membership/other income
# there) — the figure a summary will quote.
DURATION_CONCEPTS: Dict[str, List[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "NetSales",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "earnings_per_share": [
        "EarningsPerShareBasic",
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
    ],
}

# Balance-sheet (instant) concepts. Deliberately excludes
# LiabilitiesAndStockholdersEquity as a total_liabilities candidate: that
# concept equals total assets, so reporting it as liabilities is wrong (the
# legacy last-resort path still carries it for compatibility).
INSTANT_CONCEPTS: Dict[str, List[str]] = {
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashAndCashEquivalents",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ],
}


def normalize_form(form: Optional[str]) -> str:
    """Normalize a form label to its base type: "10-K/A" -> "10-K"."""
    return str(form or "").split("/")[0].strip().upper()


def _iso_date(value: Any) -> Optional[str]:
    """Coerce a period boundary to an ISO date string, or None.

    Fact-query DataFrames may carry dates as strings, datetimes, NaN (missing
    period_start on instant facts) or NaT; only a YYYY-MM-DD prefix survives.
    """
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    text = str(value)[:10]
    if len(text) == 10 and text[:4].isdigit() and text[4] == "-" and text[7] == "-":
        return text
    return None


def duration_in_window(start: Any, end: Any, form: str) -> bool:
    """True when [start, end] spans the standard duration for the base form."""
    window = DURATION_WINDOWS.get(normalize_form(form))
    start_iso, end_iso = _iso_date(start), _iso_date(end)
    if window is None or not start_iso or not end_iso:
        return False
    try:
        days = (date.fromisoformat(end_iso) - date.fromisoformat(start_iso)).days
    except (ValueError, TypeError):
        return False
    low, high = window
    return low <= days <= high


def _fact_records(xb: Any, concept: str) -> List[Dict[str, Any]]:
    """All facts for a us-gaap concept as row dicts (empty list on failure)."""
    try:
        df = xb.facts.query().by_concept(f"us-gaap:{concept}", exact=True).to_dataframe()
    except Exception as exc:  # noqa: BLE001 - any query failure means "no facts"
        logger.debug(f"Fact query failed for {concept}: {exc}")
        return []
    if df is None or getattr(df, "empty", True):
        return []
    return df.to_dict("records")


def _numeric(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if number != number else number  # NaN guard


def _series_from_values(
    values_by_end: Dict[str, set],
    period_of_report: str,
    max_items: int,
) -> List[Tuple[str, float]]:
    """Dedupe per period end (ambiguity drops the period), newest first.

    Returns [] unless an unambiguous entry exists for the filing's own
    period_of_report — the anchor that proves the concept is the one this
    filing actually reports.
    """
    series: List[Tuple[str, float]] = []
    for end in sorted(values_by_end, reverse=True):
        values = values_by_end[end]
        if len(values) > 1:
            logger.debug(f"Ambiguous consolidated values for {end}: {sorted(values)}")
            continue
        series.append((end, next(iter(values))))
    if not series or series[0][0] != period_of_report:
        return []
    return series[:max_items]


def duration_series(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> List[Tuple[str, float]]:
    """Income-statement series from the filing's instance.

    The first candidate concept with an unambiguous, undimensioned fact of the
    form's standard duration ending on period_of_report wins; its facts for
    earlier period ends (the filing's own comparatives) follow, newest first.
    Concepts are never mixed within one series.
    """
    for concept in concepts:
        values_by_end: Dict[str, set] = {}
        for row in _fact_records(xb, concept):
            if row.get("is_dimensioned"):
                continue
            end = _iso_date(row.get("period_end"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            if not duration_in_window(row.get("period_start"), end, form):
                continue
            values_by_end.setdefault(end, set()).add(round(value, 4))
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            return series
    return []


def instant_series(
    xb: Any,
    concepts: List[str],
    period_of_report: str,
    max_items: int = 5,
) -> List[Tuple[str, float]]:
    """Balance-sheet series: undimensioned instant facts (no period_start),
    anchored at period_of_report, plus the filing's comparative instants."""
    for concept in concepts:
        values_by_end: Dict[str, set] = {}
        for row in _fact_records(xb, concept):
            if row.get("is_dimensioned"):
                continue
            if _iso_date(row.get("period_start")) is not None:
                continue  # duration fact, not an instant
            end = _iso_date(row.get("period_end"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            values_by_end.setdefault(end, set()).add(round(value, 4))
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            return series
    return []
