"""Financial-fact concepts extracted from the facts_service facade."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from app.services.facts.quarterly import FINAL_QUARTER_WINDOW, QUARTER_WINDOW


# Financial-institution revenue concepts affected by the as-reported-statement fix (filing 528).
# When remediating, the stale rows under these concepts (e.g. a bank's fee-income-only "revenue")
# are deleted and re-inserted from the corrected extraction — raw_tag is NOT in the identity key,
# so a plain re-upsert would skip them.
AFFECTED_FINANCIAL_CONCEPTS: tuple[str, ...] = (
    "revenue", "net_interest_income", "noninterest_income",
    "premiums_earned", "net_investment_income",
)

# Standardized concept (from xbrl_service.extract_standardized_metrics) → DEFAULT unit, used only
# when the fact carries no reporting currency (domestic US filers). When a fact carries a currency
# (e.g. CNY/EUR for a foreign private issuer), `_unit_for` substitutes it so the value is never
# implied-USD. Margins are ratios ("pure"); per-share metrics are <ccy>/shares.
_CONCEPT_UNITS: dict[str, str] = {
    "revenue": "USD",
    "net_income": "USD",
    "gross_profit": "USD",
    "operating_income": "USD",
    "total_assets": "USD",
    "cash_and_equivalents": "USD",
    "operating_cash_flow": "USD",
    "capital_expenditures": "USD",
    "free_cash_flow": "USD",
    "shareholders_equity": "USD",
    "long_term_debt": "USD",
    "earnings_per_share": "USD/shares",
    "eps_diluted": "USD/shares",
    "net_margin": "pure",
    "gross_margin": "pure",
    "operating_margin": "pure",
    # Financial-institution revenue components/totals (filing 528 / MCB fix). All monetary totals;
    # deliberately NOT in NON_NEGATIVE_CONCEPTS (net interest income / net investment income can be
    # negative), and NOT in HEADLINE_GAAP_TAGS so the companyfacts cross-check leaves them alone.
    "net_interest_income": "USD",
    "noninterest_income": "USD",
    "premiums_earned": "USD",
    "net_investment_income": "USD",
    # Roadmap 2.6: full cash-flow statement + working-capital lines (flag-gated extraction).
    "investing_cash_flow": "USD",
    "financing_cash_flow": "USD",
    "current_assets": "USD",
    "current_liabilities": "USD",
    "working_capital": "USD",
    "current_ratio": "pure",
    # T5.3 shareholder returns: cash PAID (as-tagged positive magnitudes, the capex precedent).
    # Deliberately NOT in NON_NEGATIVE_CONCEPTS — mirror capex: a rare credit-signed filer's value
    # is stored as-tagged rather than hard-rejected (the reconcile magnitude check is sign-invariant
    # and will NOT flag it); user-visible surfaces normalize with abs(), the FCF/§4 precedent.
    "dividends_paid": "USD",
    "share_repurchases": "USD",
}

# Concepts that are physically impossible below zero — a negative value is a parse error,
# not a legitimate datum (a loss lives in net_income/operating_income, never in revenue or
# total_assets). These hard-reject; everything else can legitimately be negative.
NON_NEGATIVE_CONCEPTS: frozenset[str] = frozenset(
    {"revenue", "total_assets", "cash_and_equivalents", "long_term_debt",
     # Roadmap 2.6: balance-sheet totals + the current ratio can't be negative (working_capital CAN
     # be, and the investing/financing cash flows routinely are — so those stay out of this set).
     "current_assets", "current_liabilities", "current_ratio"}
)

# A period-over-period swing beyond this factor (either direction) is treated as a likely
# scale bug (the ABNB "$ in millions" → 1, XOM EPS 0.00 class), flagged not rejected.
_MAGNITUDE_TOLERANCE = 10.0


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _fiscal_period(form: Optional[str]) -> Optional[str]:
    # Annual reports report the full fiscal year: 10-K (domestic) and 20-F / 40-F (foreign private
    # issuers). For a 10-Q the quarter can't be inferred from the period alone, and a 6-K is
    # free-form, so both are left unset rather than guessed.
    return "FY" if (form or "").upper().replace("-", "").startswith(("10K", "20F", "40F")) else None


def _duration_start(raw: Any, period_end: date) -> Optional[date]:
    """A source start that genuinely precedes its period end, else None (duration unknown).

    Deliberately incurious: it parses what extraction preserved and rejects anything that is not a
    real date strictly before the end. It never derives a start from the form, the fiscal label,
    the period end or a neighbouring period.
    """
    start = _parse_date(raw)
    return start if start is not None and start < period_end else None


def _unit_for(concept: str, currency: Optional[str]) -> str:
    """Resolve the stored unit for a fact, substituting the as-filed reporting currency.

    Domestic filers carry no currency → the USD/USD-shares/pure defaults stand. A foreign issuer's
    fact carries its reporting currency (e.g. "CNY"), which replaces the USD assumption so a CNY
    value is never stored/labelled as USD: monetary → "CNY", per-share → "CNY/shares", ratios stay
    "pure".
    """
    base = _CONCEPT_UNITS.get(concept, "USD")
    if base == "pure" or not currency:
        return base
    return f"{currency}/shares" if base.endswith("/shares") else currency


# Standardized concept -> candidate us-gaap tags (tried in priority order, filled per period).
HEADLINE_GAAP_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "total_assets": ("Assets",),
}
_INSTANT_HEADLINE = frozenset({"total_assets"})  # balance-sheet (instant) vs duration concepts
# Relative gap above which the parsed value is treated as wrong and replaced by companyfacts.
CROSS_CHECK_TOLERANCE = 0.01


# Upper bound on one sync companyfacts fetch when it is handed to the app loop: the limiter's full
# backoff ladder (Retry-After honoured up to 120s per attempt) can legitimately take minutes.
COMPANYFACTS_SYNC_TIMEOUT_SECONDS = 600.0


# Duration windows shared with the per-filing extractor (instance_extractor.DURATION_WINDOWS):
# 52/53-week fiscal years run 364-371 days, fiscal quarters 84-98 (incl. 14-week quarters).
# Six-/nine-month cumulative slices are derivation inputs, never discrete-quarter rows.
_CF_ANNUAL_WINDOW = (320, 390)
_CF_QUARTER_WINDOW = QUARTER_WINDOW
_CF_YTD6_WINDOW = (150, 215)
_CF_YTD9_WINDOW = (250, 295)

_QUARTER_PERIODS = ("Q1", "Q2", "Q3", "Q4")

# us-gaap tag candidates per standardized concept, in priority order. Ordering follows
# HEADLINE_GAAP_TAGS for the shared concepts (companyfacts context: the ASC-606 revenue tag first).
# Periods are merged ACROSS tags (first tag with data wins per period), so a filer that migrated
# tags (SalesRevenueNet → RevenueFromContractWithCustomer...) keeps its full history. us-gaap only:
# IFRS filers (ifrs-full) are detected and reported unsupported (v1 scope).
COMPANYFACTS_DURATION_TAGS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "NetSales",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capital_expenditures": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ),
    "investing_cash_flow": (
        "NetCashProvidedByUsedInInvestingActivities",
        "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
    ),
    "financing_cash_flow": (
        "NetCashProvidedByUsedInFinancingActivities",
        "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
    ),
    "earnings_per_share": ("EarningsPerShareBasic", "EarningsPerShareBasicAndDiluted"),
    "eps_diluted": ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"),
    # Financial-institution components/totals — exact tags, safe for banks/insurers (unlike the
    # generic revenue tags, which resolve to the ASC-606 fee-income subset for a bank — the
    # filing 528 / MCB bug — hence the `financial_sic` guard in normalize_companyfacts).
    "net_interest_income": ("InterestIncomeExpenseNet",),
    "noninterest_income": ("NoninterestIncome",),
    "premiums_earned": ("PremiumsEarnedNet",),
    "net_investment_income": ("NetInvestmentIncome",),
}

COMPANYFACTS_INSTANT_TAGS: dict[str, tuple[str, ...]] = {
    "total_assets": ("Assets",),
    "cash_and_equivalents": (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
        # ASU 2016-18 total (includes restricted cash) — the tag JPM and every large-bank
        # adopter MIGRATED to (JPM FY2019+, BAC FY2020+). Appended LAST deliberately: per-period
        # first-tag-wins keeps pre-migration years on the legacy tags' identical values (zero
        # churn), while post-migration years — previously MISSING entirely — fill from this tag
        # (data-quality plan P0-3).
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ),
    "shareholders_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "long_term_debt": ("LongTermDebtNoncurrent", "LongTermDebt"),
    "current_assets": ("AssetsCurrent",),
    "current_liabilities": ("LiabilitiesCurrent",),
}

# Generic revenue tags are WRONG for banks/insurers (fee-income subset — the MCB fix would be
# undone by re-ingesting them); the exact FI component tags above carry their top line instead.
_FI_SKIPPED_CONCEPTS: frozenset[str] = frozenset({"revenue"})


def _classify_duration(start: date, end: date) -> Optional[str]:
    """Classify annual, discrete-quarter and cumulative calculation inputs."""
    days = (end - start).days
    if _CF_ANNUAL_WINDOW[0] <= days <= _CF_ANNUAL_WINDOW[1]:
        return "FY"
    if FINAL_QUARTER_WINDOW[0] <= days <= FINAL_QUARTER_WINDOW[1]:
        return "Q"
    if _CF_YTD6_WINDOW[0] <= days <= _CF_YTD6_WINDOW[1]:
        return "YTD6"
    if _CF_YTD9_WINDOW[0] <= days <= _CF_YTD9_WINDOW[1]:
        return "YTD9"
    return None


_VALID_FP = frozenset(_QUARTER_PERIODS)


def _is_financial_sic(sic: Optional[str]) -> bool:
    """Financial-services SIC band (6000-6799) — lexical compare on the 4-digit String column,
    same convention as ``remediate_industry_facts``."""
    return bool(sic) and "6000" <= str(sic) <= "6799"


COMPANYFACTS_INFLIGHT_WAIT_SECONDS = 25.0
