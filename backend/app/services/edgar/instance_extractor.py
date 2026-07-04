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
import math
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


# Roadmap 2.6 (Phase A): richer cited financials — the full cash-flow statement (investing +
# financing flows, on top of the operating CF + capex we already extract) and working-capital
# components (current assets/liabilities). Kept in separate dicts and merged into the extraction
# only when `settings.RICHER_FINANCIALS_ENABLED` is on, so the default behaviour — and the eval
# baseline — is byte-for-byte unchanged until the founder flips the flag. US-GAAP first, IFRS next.
RICHER_DURATION_CONCEPTS: Dict[str, List[str]] = {
    "investing_cash_flow": [
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
        "CashFlowsFromUsedInInvestingActivities",  # IFRS
    ],
    "financing_cash_flow": [
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
        "CashFlowsFromUsedInFinancingActivities",  # IFRS
    ],
}

RICHER_INSTANT_CONCEPTS: Dict[str, List[str]] = {
    "current_assets": ["AssetsCurrent", "CurrentAssets"],  # IFRS: CurrentAssets
    "current_liabilities": ["LiabilitiesCurrent", "CurrentLiabilities"],  # IFRS: CurrentLiabilities
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
    candidates: List[Tuple[str, float, Optional[str], float]],
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
    for cand in candidates:  # candidates carry (end, value, ccy[, decimals]); only end + ccy are used
        ends_by_ccy.setdefault(cand[2], set()).add(cand[0])
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


def _parse_decimals(raw: Any) -> float:
    """XBRL ``decimals`` as a precision rank (higher = finer): 'INF' → +inf; missing/junk → -inf."""
    if raw is None:
        return float("-inf")
    text = str(raw).strip().upper()
    if text in ("INF", "+INF"):
        return float("inf")
    try:
        return float(int(text))
    except (TypeError, ValueError):
        return float("-inf")


def _resolve_period_value(facts: List[Tuple[float, float]]) -> Optional[float]:
    """The single consolidated value for one period end, or None when genuinely ambiguous.

    A filer sometimes tags the same line twice undimensioned at different precision — e.g. revenue
    as 32,667,300,000 (``decimals=-5``) AND a rounded 32,700,000,000 (``decimals=-8``). These are
    the same figure, so the finest-precision value wins, PROVIDED every coarser value equals that
    value rounded to the coarser fact's own ``decimals``. Values that are not such a clean rounding
    are genuinely divergent (e.g. an unreconciled restatement) and stay ambiguous → None (dropped) —
    which is also the conservative result when precision is unknown (decimals missing → -inf).
    """
    distinct = {round(v, 4) for v, _ in facts}
    if len(distinct) <= 1:
        return next(iter(distinct)) if distinct else None
    best_value, _best_dec = max(facts, key=lambda vd: vd[1])
    for value, dec in facts:
        if round(value, 4) == round(best_value, 4):
            continue
        # `value` must EQUAL `best_value` rounded to the coarser fact's own (finite) decimals — else
        # it's a genuine conflict. Compare at fixed precision (>= 4 dp) rather than an absolute
        # tolerance, so positive decimals (cents, EPS) and same-precision distinct values (e.g.
        # 100 vs 101 at decimals=0) are not silently collapsed. Guard isfinite BEFORE int(dec)
        # (int(±inf) raises).
        if not math.isfinite(dec):
            return None
        ndigits = max(4, int(dec))
        if round(value, ndigits) != round(round(best_value, int(dec)), ndigits):
            return None
    return best_value


def _series_from_values(
    values_by_end: Dict[str, List[Tuple[float, float]]],
    period_of_report: str,
    max_items: int,
) -> List[Tuple[str, float]]:
    """Resolve one value per period end (genuine ambiguity drops the period), newest first.

    Each period maps to its undimensioned (value, decimals) facts; ``_resolve_period_value`` picks
    the consolidated figure or returns None when the values genuinely conflict. Returns [] unless an
    unambiguous entry exists for the filing's own period_of_report — the anchor that proves the
    concept is the one this filing actually reports.
    """
    series: List[Tuple[str, float]] = []
    for end in sorted(values_by_end, reverse=True):
        resolved = _resolve_period_value(values_by_end[end])
        if resolved is None:
            logger.debug(f"Ambiguous consolidated values for {end}: {sorted(values_by_end[end])}")
            continue
        series.append((end, resolved))
    if not series or series[0][0] != period_of_report:
        return []
    return series[:max_items]


def duration_series_currency_concept(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str], Optional[str]]:
    """Income-statement series + reporting currency + the winning concept.

    The first candidate concept with an unambiguous, undimensioned fact of the form's standard
    duration ending on period_of_report wins; its facts for earlier period ends (the filing's own
    comparatives) follow, newest first. Facts are filtered to the issuer's reporting currency
    (so a USD convenience translation alongside a CNY/EUR figure for the same period is NOT treated
    as an ambiguous duplicate, which previously dropped the whole period). Concepts are never mixed
    within one series. Returns (series, currency, concept); currency is None when facts carry no
    currency, and concept is the winning us-gaap/ifrs candidate (recorded as a ``raw_tag`` so
    downstream can detect a concept that flips between filings). Both are None when nothing resolves.
    """
    for concept in concepts:
        candidates: List[Tuple[str, float, Optional[str], float]] = []
        for row in _fact_records(xb, concept):
            if row.get("is_dimensioned"):
                continue
            end = _iso_date(row.get("period_end"))
            value = _numeric(row.get("numeric_value"))
            if end is None or value is None or end > period_of_report:
                continue
            if not duration_in_window(row.get("period_start"), end, form):
                continue
            candidates.append((end, value, _currency(row), _parse_decimals(row.get("decimals"))))
        currency = _reporting_currency(candidates, period_of_report)
        values_by_end: Dict[str, List[Tuple[float, float]]] = {}
        for end, value, ccy, dec in candidates:
            if currency is not None and ccy != currency:
                continue
            values_by_end.setdefault(end, []).append((round(value, 4), dec))
        series = _series_from_values(values_by_end, period_of_report, max_items)
        if series:
            return series, currency, concept
    return [], None, None


def duration_series_with_currency(
    xb: Any,
    concepts: List[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Back-compat wrapper: income-statement series + currency (drops the winning concept)."""
    series, currency, _concept = duration_series_currency_concept(
        xb, concepts, form, period_of_report, max_items
    )
    return series, currency


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
        candidates: List[Tuple[str, float, Optional[str], float]] = []
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
            candidates.append((end, value, _currency(row), _parse_decimals(row.get("decimals"))))
        currency = _reporting_currency(candidates, period_of_report)
        values_by_end: Dict[str, List[Tuple[float, float]]] = {}
        for end, value, ccy, dec in candidates:
            if currency is not None and ccy != currency:
                continue
            values_by_end.setdefault(end, []).append((round(value, 4), dec))
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


# ---------------------------------------------------------------------------
# Industry-aware revenue for FINANCIAL INSTITUTIONS (filing 528 / MCB fix).
#
# A generic revenue tag is wrong for a financial institution: a bank rarely tags a `Revenues`
# top line, so the flat priority list falls through to `RevenueFromContractWithCustomer…`, which
# under ASC 606 is only fee/non-interest income (a subset). EdgarTools' own standardization shares
# this blind spot (it maps that fee tag to a generic "Revenue"). The reliable fix is to read the
# filing's AS-REPORTED income statement (`xb.statements.income_statement()`), which renders the
# filer's actual line items, and select the industry-correct line(s) by concept + statement
# structure. Non-financial filers keep the generic fact-query path unchanged.
#
# Empirically validated against real filings (MCB bank, MET insurer, BLK asset manager, ARCC BDC):
#   • the total/component rows carry a set `standard_concept`, while disaggregation sub-lines under
#     the same us-gaap concept carry a null one — so (concept anchor + expected standard_concept)
#     uniquely identifies the total line even when a concept appears on several presentation rows;
#   • `standard_concept == "Revenue"` is attached to a bank's $11M fee-income row, so it must NOT be
#     trusted for banks — the specific concept anchors are what make banks correct;
#   • some financial filers (e.g. ARCC) carry a blank SIC, so `is_financial_institution()` is the
#     gate and concept-presence is the sub-type signal.
# ---------------------------------------------------------------------------

# Broad financial-services SIC band, used only as a fallback gate when `is_financial_institution()`
# is unavailable/False. Sub-typing is by concept presence, not SIC (robust to blank/mis-set SIC).
FINANCIAL_SIC_LOW, FINANCIAL_SIC_HIGH = 6000, 6799

# Ordered financial-institution profiles. `detect` = concept locals whose presence sub-types the
# filer (empty = catch-all). Each selector = (standardized_key, anchor concept locals in priority
# order, expected standard_concept marking the total/component row). `suppress` = generic keys to
# OMIT (banks emit components, never a single conflated "revenue").
FINANCIAL_PROFILES: List[Dict[str, Any]] = [
    {
        "key": "bank",
        "detect": ("InterestIncomeExpenseNet", "NoninterestIncome"),
        "selectors": [
            ("net_interest_income", ("InterestIncomeExpenseNet",), "NetInterestIncome"),
            ("noninterest_income", ("NoninterestIncome",), "NonInterestIncome"),
        ],
        "suppress": ("revenue",),
    },
    {
        "key": "insurer",
        "detect": ("PremiumsEarnedNet",),
        "selectors": [
            ("revenue", ("Revenues",), "Revenue"),
            ("premiums_earned", ("PremiumsEarnedNet",), "Revenue"),
            ("net_investment_income", ("NetInvestmentIncome",), "Revenue"),
        ],
        "suppress": (),
    },
    {
        # BDC / closed-end fund: "revenue" is TOTAL investment income (gross, before expenses) —
        # `GrossInvestmentIncomeOperating`. Net investment income is after expenses (≈ a BDC's "net
        # income"), and its standard_concept is misleadingly "Revenue", so anchor on the gross total.
        "key": "bdc",
        "detect": ("GrossInvestmentIncomeOperating", "InvestmentIncomeOperating", "InvestmentIncomeNet"),
        "selectors": [
            ("revenue", ("GrossInvestmentIncomeOperating", "InvestmentIncomeOperating",
                         "InvestmentIncomeOperatingNet", "InvestmentIncomeNet", "Revenues"), "Revenue"),
        ],
        "suppress": (),
    },
    {
        # Catch-all for financial institutions not sub-typed above (asset managers, broker-dealers):
        # read their genuine as-reported total-revenue line instead of a guessed tag.
        "key": "financial_generic",
        "detect": (),
        "selectors": [
            ("revenue", ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                         "RevenueFromContractWithCustomerIncludingAssessedTax"), "Revenue"),
        ],
        "suppress": (),
    },
]


def _concept_local(concept: Any) -> str:
    """Local name of an as-reported ``concept`` cell: ``us-gaap_InterestIncomeExpenseNet`` -> the
    part after the namespace ``_`` (``mcb_Foo`` -> ``Foo``). Namespace/local are joined by a single
    underscore; us-gaap/ifrs local names themselves carry none."""
    text = str(concept or "")
    return text.split("_", 1)[1] if "_" in text else text


def is_financial_institution(company: Any, sic: Optional[str]) -> bool:
    """True when the filer is a bank/insurer/investment-manager/BDC.

    Primary signal is edgartools' ``company.is_financial_institution()`` (True even when SIC is
    blank, e.g. ARCC); the broad financial-services SIC band is only a fallback when that is
    unavailable. Duck-typed so unit tests can pass a lightweight fake.
    """
    probe = getattr(company, "is_financial_institution", None)
    try:
        if callable(probe) and bool(probe()):
            return True
    except Exception as exc:  # noqa: BLE001 - any failure just falls back to SIC
        logger.debug(f"is_financial_institution() probe failed: {exc}")
    try:
        code = int(str(sic)[:4]) if sic not in (None, "") else None
    except (TypeError, ValueError):
        code = None
    return code is not None and FINANCIAL_SIC_LOW <= code <= FINANCIAL_SIC_HIGH


def income_statement_dataframe(xb: Any) -> Any:
    """The filing's as-reported income statement as a face-value DataFrame, or None.

    Uses ``view="standard"`` (undimensioned face values — the filing document view; the successor
    to the deprecated ``include_dimensions=False``). Fully defensive: any failure in the statement
    machinery returns None so the caller falls back to the generic fact-query path and extraction
    never hard-fails.
    """
    try:
        statement = xb.statements.income_statement()
        if statement is None:
            return None
        try:
            df = statement.to_dataframe(view="standard")
        except TypeError:
            df = statement.to_dataframe()  # older signatures without `view`
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"income_statement() unavailable: {exc}")
        return None
    if df is None or getattr(df, "empty", True):
        return None
    return df


def _statement_period_columns(df: Any, form: str) -> List[Tuple[str, Any]]:
    """[(period_end_iso, column)] for the statement's dated period columns, newest first.

    Columns look like ``"2025-12-31 (FY)"``. For annual forms we require the ``(FY)`` marker so a
    quarterly/YTD column can never be mistaken for the fiscal-year figure.
    """
    annual = normalize_form(form) in ("10-K", "20-F", "40-F")
    cols: List[Tuple[str, Any]] = []
    for col in df.columns:
        text = str(col)
        end = _iso_date(text[:10])
        if end is None:
            continue
        if annual and "(FY)" not in text:
            continue
        cols.append((end, col))
    cols.sort(key=lambda pc: pc[0], reverse=True)
    return cols


def _truthy_flag(value: Any) -> bool:
    """Normalize a statement flag cell to a bool. The as-reported DataFrame carries ``abstract`` /
    ``is_breakdown`` / ``dimension`` as booleans for face rows (``False``), but older/other views may
    use NaN or a dimension-axis string. NaN/None/"" → False; a real bool passes through; any other
    non-empty value (e.g. an axis name) → True."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, float) and value != value:  # NaN
        return False
    return bool(str(value).strip())


def _row_is_face_value(row: Any) -> bool:
    """A usable statement line: not an abstract header, not a dimensional breakdown member."""
    return not (
        _truthy_flag(row.get("abstract"))
        or _truthy_flag(row.get("is_breakdown"))
        or _truthy_flag(row.get("dimension"))
    )


def _select_statement_series(
    df: Any,
    anchors: Tuple[str, ...],
    expected_std: Optional[str],
    period_cols: List[Tuple[str, Any]],
    period_of_report: str,
    max_items: int = 5,
) -> Tuple[List[Tuple[str, float]], Optional[str]]:
    """Series + winning us-gaap tag for the total/component row of the first resolving anchor.

    For each anchor concept (priority order), take the face-value rows whose local concept matches.
    When several rows share the concept (a total plus disaggregation sub-lines), the total is the
    one whose ``standard_concept`` equals ``expected_std`` — the marker the as-reported statement
    puts only on the recognized line. Reads that row's value from every dated period column and
    requires an anchor at ``period_of_report`` (proving it is the figure this filing reports).
    """
    records = df.to_dict("records")
    for anchor in anchors:
        matches = [r for r in records if _concept_local(r.get("concept")) == anchor and _row_is_face_value(r)]
        if not matches:
            continue
        chosen = None
        if len(matches) == 1:
            chosen = matches[0]
        elif expected_std:
            marked = [r for r in matches if str(r.get("standard_concept") or "") == expected_std]
            if len(marked) == 1:
                chosen = marked[0]
        if chosen is None:
            continue  # genuinely ambiguous — don't guess
        series: List[Tuple[str, float]] = []
        for end, col in period_cols:
            if end > period_of_report:
                continue
            value = _numeric(chosen.get(col))
            if value is not None:
                series.append((end, value))
        if series and series[0][0] == period_of_report:
            return series[:max_items], f"us-gaap:{anchor}"
    return [], None


def match_financial_profile(df: Any) -> Optional[Dict[str, Any]]:
    """The financial-institution profile for an as-reported income statement, by concept presence."""
    present = {
        _concept_local(r.get("concept"))
        for r in df.to_dict("records")
        if _row_is_face_value(r)
    }
    for profile in FINANCIAL_PROFILES:
        detect = profile["detect"]
        if not detect or present.intersection(detect):
            return profile
    return None


def extract_financial_statement_metrics(
    xb: Any,
    company: Any,
    sic: Optional[str],
    form: str,
    period_of_report: str,
    max_items: int = 5,
) -> Optional[Tuple[str, Dict[str, Tuple[List[Tuple[str, float]], str]], Tuple[str, ...]]]:
    """Industry-correct revenue for a financial institution, from its as-reported income statement.

    Returns ``(profile_key, {standardized_key: (series, raw_tag)}, suppress_keys)`` or None when the
    filer isn't a financial institution, the statement is unavailable, or nothing resolves — in
    every None case the caller keeps the unchanged generic fact-query extraction.
    """
    if not is_financial_institution(company, sic):
        return None
    df = income_statement_dataframe(xb)
    if df is None:
        return None
    period_cols = _statement_period_columns(df, form)
    if not period_cols:
        return None
    profile = match_financial_profile(df)
    if profile is None:
        return None
    metrics: Dict[str, Tuple[List[Tuple[str, float]], str]] = {}
    for key, anchors, expected_std in profile["selectors"]:
        series, raw_tag = _select_statement_series(
            df, anchors, expected_std, period_cols, period_of_report, max_items
        )
        if series and raw_tag:
            metrics[key] = (series, raw_tag)
    if not metrics:
        return None
    return profile["key"], metrics, tuple(profile["suppress"])
