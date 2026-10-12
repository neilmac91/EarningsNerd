"""Accession-aware XBRL extraction: concepts."""

from typing import Dict, List

# Concept candidates per metric, in priority order. `Revenues` first: within a
# single filing's XBRL instance there is no stale-tag risk (unlike the
# companyfacts API), and when both are tagged `Revenues` is the income
# statement's total top line (e.g. WMT/XOM include membership/other income
# there) — the figure a summary will quote.
# Each metric lists US-GAAP concept candidates first, then IFRS (ifrs-full) candidates for
# foreign private issuers that report under IFRS (e.g. ASML, Novo Nordisk). `_fact_records_with_concept` tries
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
    # T5.3 shareholder returns — CASH-FLOW-STATEMENT payments only, live-verified across
    # AAPL/MSFT/ASML/WFC/JPM/BAC/C (us-gaap) and TSM/NVO (ifrs-full). Facts are debit-balance
    # elements tagged POSITIVE ("cash paid" magnitudes), stored as-tagged — the capex precedent.
    # `dividends_paid` lists TOTAL tags only; filers that tag common/preferred as separate
    # components with NO total (WFC-class) are resolved by summing DIVIDEND_COMPONENT_CONCEPTS —
    # first-candidate-wins over a component would report the common-only subset as the unqualified
    # total (WFC FY2025: 5,434M common vs 6,484M actually paid — a 16% understatement).
    # EXCLUDED trap tags (wrong-by-construction, verified live; pinned by
    # test_shareholder_returns_extraction.py): `DividendsCommonStockCash` is dividends DECLARED,
    # not paid (MSFT: 24,678M declared vs 24,082M paid); ifrs `DividendsPaid` is the
    # equity-statement distribution, not cash (TSM: 531,618M vs 466,779M paid);
    # `StockRepurchasedAndRetiredDuringPeriodValue` is the equity-statement measure
    # (AAPL: 89,300M vs 90,711M cash paid).
    "dividends_paid": [
        "PaymentsOfDividends",
        "PaymentsOfOrdinaryDividends",  # combined total on e.g. BAC (~common + preferred)
        "DividendsPaidClassifiedAsFinancingActivities",  # IFRS
    ],
    "share_repurchases": [
        "PaymentsForRepurchaseOfCommonStock",
        "PaymentsForRepurchaseOfEquity",  # umbrella tag (preferred/unit repurchases)
        "PaymentsToAcquireOrRedeemEntitysShares",  # IFRS
    ],
}


# Per-class dividend payment components, resolved INDIVIDUALLY and summed per period when no total
# tag exists (never first-candidate-wins — each is a disjoint subset, not an alternative spelling).
# A component-absent filer (MSFT: common only; no preferred in the capital structure) resolves to
# its sole tagged component unchanged.
DIVIDEND_COMPONENT_CONCEPTS: List[str] = [
    "PaymentsOfDividendsCommonStock",
    "PaymentsOfDividendsPreferredStockAndPreferenceStock",
]


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
        # ASU 2016-18 total (includes restricted cash) — what JPM-class banks migrated to.
        # LAST = lowest priority: only resolves when no unrestricted-cash tag is present
        # (data-quality plan P0-3).
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
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
