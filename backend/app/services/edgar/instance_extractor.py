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
# 20-F / 40-F are foreign ANNUAL reports, so they share the 10-K annual window.
DURATION_WINDOWS: Dict[str, Tuple[int, int]] = {
    "10-K": (320, 390),
    "10-Q": (75, 105),
    "20-F": (320, 390),
    "40-F": (320, 390),
}

# Concept candidates per metric, in priority order. `Revenues` first: within a
# single filing's XBRL instance there is no stale-tag risk (unlike the
# companyfacts API), and when both are tagged `Revenues` is the income
# statement's total top line (e.g. WMT/XOM include membership/other income
# there) — the figure a summary will quote.
# Each metric lists US-GAAP concept candidates first, then IFRS (ifrs-full) candidates for
# foreign private issuers that report under IFRS (e.g. ASML, Novo Nordisk). `_fact_records` tries
# both the us-gaap and ifrs-full namespaces per name, so the first candidate that resolves in
# either taxonomy wins. (Alibaba files under US-GAAP, so its blocker is currency, not IFRS.)
DURATION_CONCEPTS: Dict[str, List[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "NetSales",
        # IFRS
        "Revenue",
        "RevenueFromContractsWithCustomers",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",  # IFRS total comprehensive profit/loss for the period
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLossAttributableToOwnersOfParent",  # IFRS
    ],
    "earnings_per_share": [
        "EarningsPerShareBasic",
        "EarningsPerShareDiluted",
        "EarningsPerShareBasicAndDiluted",
        # IFRS
        "BasicEarningsLossPerShare",
        "DilutedEarningsLossPerShare",
    ],
    # P1.5: diluted EPS explicitly, so a report can show basic AND diluted (the figure investors
    # quote) without conflating them — the basic/diluted mismatch the eval kept flagging.
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "DilutedEarningsLossPerShare"],
    # P1.1 depth: income-statement profitability + cash-flow-statement flows. All are
    # duration facts for the filing's period; absent concepts (e.g. GrossProfit for a bank)
    # simply yield an empty series — never wrong data.
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        "CashFlowsFromUsedInOperatingActivities",  # IFRS
    ],
    "capital_expenditures": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PurchaseOfPropertyPlantAndEquipment",  # IFRS
    ],
}

# Balance-sheet (instant) concepts. Deliberately excludes
# LiabilitiesAndStockholdersEquity as a total_liabilities candidate: that
# concept equals total assets, so reporting it as liabilities is wrong (the
# legacy last-resort path still carries it for compatibility).
# `Assets` and `Liabilities` share the same concept name in us-gaap and ifrs-full, so they need no
# IFRS-specific candidate. Equity/debt differ, so IFRS names are appended.
INSTANT_CONCEPTS: Dict[str, List[str]] = {
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashAndCashEquivalents",  # also the IFRS name
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ],
    # P1.1 depth: balance-sheet equity + debt (instant facts). LongTermDebt is a
    # conservative, clearly-labelled debt anchor (not "total debt", which has no single
    # universal concept); the model still sees the full balance sheet for the rest.
    "shareholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "Equity",  # IFRS
        "EquityAttributableToOwnersOfParent",  # IFRS
    ],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt", "NoncurrentBorrowings"],
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


# Taxonomies tried per concept, in order. US-GAAP first (the common case, incl. Alibaba); IFRS
# only reached when the us-gaap query is empty, so domestic filers pay no extra query.
_CONCEPT_NAMESPACES: Tuple[str, ...] = ("us-gaap", "ifrs-full")


def _fact_records(xb: Any, concept: str) -> List[Dict[str, Any]]:
    """All facts for a concept as row dicts, trying us-gaap then ifrs-full (empty on failure).

    A foreign private issuer reporting under IFRS tags the concept in the ``ifrs-full`` namespace;
    a domestic/US-GAAP filer (incl. Alibaba) tags it in ``us-gaap``. The first namespace that
    yields facts wins, so the same candidate name resolves in whichever taxonomy the filer used.
    """
    for namespace in _CONCEPT_NAMESPACES:
        try:
            df = xb.facts.query().by_concept(f"{namespace}:{concept}", exact=True).to_dataframe()
        except Exception as exc:  # noqa: BLE001 - any query failure means "no facts"
            logger.debug(f"Fact query failed for {namespace}:{concept}: {exc}")
            continue
        if df is not None and not getattr(df, "empty", True):
            return df.to_dict("records")
    return []


def _currency(row: Dict[str, Any]) -> Optional[str]:
    """Reporting currency (ISO-4217) of a fact row, or None when absent/non-monetary.

    edgartools exposes a ``currency`` column per fact; per-share and unitless facts carry no
    currency. Returns an upper-cased code (e.g. "CNY", "USD", "EUR") or None.
    """
    ccy = row.get("currency")
    if ccy is None:
        return None
    if isinstance(ccy, float) and ccy != ccy:  # float NaN — keep this guard: str(nan)=="nan",
        return None                            # which would otherwise pass the 3-alpha check below.
    text = str(ccy).strip().upper()
    # ISO-4217 codes are exactly three letters; this also rejects pandas <NA>, "" and other junk.
    return text if len(text) == 3 and text.isalpha() else None


def _reporting_currency(
    candidates: List[Tuple[str, float, Optional[str]]],
    period_of_report: str,
) -> Optional[str]:
    """Pick the issuer's reporting currency from candidate facts for one concept.

    Foreign filers (e.g. Alibaba) tag the SAME line in BOTH their reporting currency (all periods)
    AND a USD convenience translation (usually only the latest period). The reporting currency is
    the one covering the most distinct period-ends; ties prefer the currency present at the filing's
    own period_of_report, then alphabetical for determinism. Returns None when no fact carries a
    currency (unit tests, per-share concepts), which disables currency filtering.
    """
    ends_by_ccy: Dict[Optional[str], set] = {}
    for end, _value, ccy in candidates:
        ends_by_ccy.setdefault(ccy, set()).add(end)
    real = {c: ends for c, ends in ends_by_ccy.items() if c}
    if not real:
        return None
    # Rank by: most distinct period-ends (the native currency spans all presented years; a USD
    # convenience translation is usually only the latest year), then presence at the filing's own
    # period, then prefer a NON-USD code (USD is the convenience-translation convention, so on a tie
    # the native currency wins), then alphabetical for determinism.
    return max(
        real.items(),
        key=lambda item: (
            len(item[1]),
            period_of_report in item[1],
            item[0] != "USD",
            item[0],
        ),
    )[0]


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


def duration_series_with_currency(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Income-statement series + reporting currency from the filing's instance.

    The first candidate concept with an unambiguous, undimensioned fact of the form's standard
    duration ending on period_of_report wins; its facts for earlier period ends (the filing's own
    comparatives) follow, newest first. Facts are filtered to the issuer's reporting currency
    (so a USD convenience translation alongside a CNY/EUR figure for the same period is NOT treated
    as an ambiguous duplicate, which previously dropped the whole period). Concepts are never mixed
    within one series. Returns (series, currency); currency is None when facts carry no currency.
    """
    for concept in concepts:
        candidates: List[Tuple[str, float, Optional[str]]] = []
        for row in _fact_records(xb, concept):
            if row.get("is_dimensioned"):
                continue
            end = _iso_date(row.get("period_end"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            if not duration_in_window(row.get("period_start"), end, form):
                continue
            candidates.append((end, value, _currency(row)))
        currency = _reporting_currency(candidates, period_of_report)
        values_by_end: Dict[str, set] = {}
        for end, value, ccy in candidates:
            if currency is not None and ccy != currency:
                continue
            values_by_end.setdefault(end, set()).add(round(value, 4))
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            return series, currency
    return [], None


def instant_series_with_currency(
    xb: Any,
    concepts: List[str],
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Balance-sheet series + reporting currency: undimensioned instant facts (no period_start),
    anchored at period_of_report, plus the filing's comparative instants. Facts are filtered to the
    issuer's reporting currency (see ``duration_series_with_currency``)."""
    for concept in concepts:
        candidates: List[Tuple[str, float, Optional[str]]] = []
        for row in _fact_records(xb, concept):
            if row.get("is_dimensioned"):
                continue
            if _iso_date(row.get("period_start")) is not None:
                continue  # duration fact, not an instant
            # Instant (balance-sheet) facts carry their date in `period_instant`; `period_end` is
            # None for them. Keying only on period_end silently dropped EVERY balance-sheet fact
            # (total assets, equity, debt, cash), so balance-sheet XBRL was always empty and ROE/ROA
            # never derived. Fall back to period_instant.
            end = _iso_date(row.get("period_end")) or _iso_date(row.get("period_instant"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            candidates.append((end, value, _currency(row)))
        currency = _reporting_currency(candidates, period_of_report)
        values_by_end: Dict[str, set] = {}
        for end, value, ccy in candidates:
            if currency is not None and ccy != currency:
                continue
            values_by_end.setdefault(end, set()).add(round(value, 4))
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            return series, currency
    return [], None


def duration_series(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> List[Tuple[str, float]]:
    """Back-compat wrapper returning only the value series (drops the currency)."""
    return duration_series_with_currency(xb, concepts, form, period_of_report, max_items)[0]


def instant_series(
    xb: Any,
    concepts: List[str],
    period_of_report: str,
    max_items: int = 5,
) -> List[Tuple[str, float]]:
    """Back-compat wrapper returning only the value series (drops the currency)."""
    return instant_series_with_currency(xb, concepts, period_of_report, max_items)[0]
