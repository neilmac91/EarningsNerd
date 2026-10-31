"""Extended annual facts from SEC companyfacts: the cost lines, cash uses and balances the driver tree needs.

The production dataset (``trend_analysis.dataset.build_dataset``) carries 26 headline concepts. Depth needs
more: cost of revenue, R&D, SG&A, stock-based compensation, D&A, tax, interest, buybacks, dividends,
acquisitions, investments, debt, and for banks and insurers their own lines. Each concept lists candidate
us-gaap tags in priority order, merged per period (first tag with a value wins), the same rule
``facts.concepts.COMPANYFACTS_DURATION_TAGS`` uses.

Every value records the tag, the accession that FIRST reported it and the accession of the LATEST filing
that reported it, and both values. A difference between them is a recast or restatement and is surfaced
as a data check, never silently resolved. Only 10-K/10-K/A facts with an annual duration are read.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

# concept -> (kind, unit, candidate tags). kind: "duration" | "instant".
EXTENDED_CONCEPTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # Top-line cross-check: every revenue tag the filer used, compared against the dataset's choice.
    "revenue_reported_total": ("duration", "USD", (
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
    )),
    # Net income as each year's own 10-K reported it, to check the metrics table's figure against.
    "net_income_10k": ("duration", "USD", ("NetIncomeLoss", "ProfitLoss")),
    "cost_of_revenue": ("duration", "USD", (
        "CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold", "CostOfServices",
        "CostOfGoodsAndServicesSoldExcludingDepreciationDepletionAndAmortization",
    )),
    "research_and_development": ("duration", "USD", (
        "ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    )),
    "acquired_in_process_rd": ("duration", "USD", (
        "ResearchAndDevelopmentInProcess", "AcquiredInProcessResearchAndDevelopment",
    )),
    "selling_general_admin": ("duration", "USD", ("SellingGeneralAndAdministrativeExpense",)),
    "selling_marketing": ("duration", "USD", ("SellingAndMarketingExpense", "MarketingAndAdvertisingExpense")),
    "general_admin": ("duration", "USD", ("GeneralAndAdministrativeExpense",)),
    "operating_expenses": ("duration", "USD", ("OperatingExpenses", "CostsAndExpenses")),
    "depreciation_amortization": ("duration", "USD", (
        "DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
        "DepreciationAndAmortization", "Depreciation",
    )),
    "stock_based_compensation": ("duration", "USD", (
        "ShareBasedCompensation", "AllocatedShareBasedCompensationExpense",
    )),
    "interest_expense": ("duration", "USD", (
        "InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt",
    )),
    "pretax_income": ("duration", "USD", (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    )),
    "income_tax": ("duration", "USD", ("IncomeTaxExpenseBenefit",)),
    "other_nonoperating": ("duration", "USD", ("NonoperatingIncomeExpense", "OtherNonoperatingIncomeExpense")),
    "goodwill_impairment": ("duration", "USD", ("GoodwillImpairmentLoss",)),
    "asset_impairment": ("duration", "USD", ("AssetImpairmentCharges", "ImpairmentOfLongLivedAssetsHeldForUse")),
    "diluted_shares": ("duration", "shares", ("WeightedAverageNumberOfDilutedSharesOutstanding",)),
    "share_repurchases": ("duration", "USD", ("PaymentsForRepurchaseOfCommonStock",)),
    "dividends_paid": ("duration", "USD", ("PaymentsOfDividendsCommonStock", "PaymentsOfDividends")),
    "acquisitions": ("duration", "USD", ("PaymentsToAcquireBusinessesNetOfCashAcquired",)),
    "debt_issued": ("duration", "USD", ("ProceedsFromIssuanceOfLongTermDebt", "ProceedsFromIssuanceOfDebt")),
    "debt_repaid": ("duration", "USD", ("RepaymentsOfLongTermDebt", "RepaymentsOfDebt")),
    # Banks.
    "interest_income": ("duration", "USD", ("InterestAndDividendIncomeOperating", "InterestIncomeOperating")),
    "noninterest_expense": ("duration", "USD", ("NoninterestExpense",)),
    "credit_loss_provision": ("duration", "USD", (
        "ProvisionForLoanLeaseAndOtherLosses", "ProvisionForLoanAndLeaseLosses",
        "ProvisionForCreditLossesNet", "CreditLossExpenseReversal",
        "FinancingReceivableCreditLossExpenseReversal",
    )),
    "preferred_dividends": ("duration", "USD", (
        "PreferredStockDividendsIncomeStatementImpact", "DividendsPreferredStock",
    )),
    # Insurers.
    "claims_incurred": ("duration", "USD", (
        "PolicyholderBenefitsAndClaimsIncurredNet", "IncurredClaimsPropertyCasualtyAndLiability",
        "LiabilityForUnpaidClaimsAndClaimsAdjustmentExpenseIncurredClaims1",
    )),
    # Balances.
    "short_term_investments": ("instant", "USD", (
        "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent", "ShortTermInvestments",
    )),
    "long_term_investments": ("instant", "USD", (
        "MarketableSecuritiesNoncurrent", "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent",
        "LongTermInvestments",
    )),
    "debt_current": ("instant", "USD", ("LongTermDebtCurrent", "DebtCurrent")),
    "short_term_borrowings": ("instant", "USD", ("ShortTermBorrowings", "CommercialPaper")),
    "debt_noncurrent": ("instant", "USD", (
        "LongTermDebtNoncurrent", "LongTermDebt", "ConvertibleNotesPayable", "ConvertibleDebtNoncurrent",
        "ConvertibleLongTermNotesPayable", "SeniorLongTermNotes", "LongTermNotesPayable",
    )),
    "inventory": ("instant", "USD", ("InventoryNet",)),
    "receivables": ("instant", "USD", ("AccountsReceivableNetCurrent", "ReceivablesNetCurrent")),
    "total_liabilities": ("instant", "USD", ("Liabilities",)),
    "goodwill": ("instant", "USD", ("Goodwill",)),
    "loans": ("instant", "USD", (
        "LoansAndLeasesReceivableNetReportedAmount",
        "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss",
        "LoansAndLeasesReceivableNetOfDeferredIncome",
    )),
    "deposits": ("instant", "USD", ("Deposits",)),
    "credit_loss_allowance": ("instant", "USD", (
        "FinancingReceivableAllowanceForCreditLossExcludingAccruedInterest",
        "AllowanceForLoanAndLeaseLossesReceivablesNetReportedAmount",
        "FinancingReceivableAllowanceForCreditLosses",
    )),
}

_ANNUAL_DAYS = (320, 390)
_ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT")


def _days(start: Optional[str], end: str) -> Optional[int]:
    if not start:
        return None
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _tag_series(payload: dict[str, Any], tag: str, kind: str, unit: str) -> dict[str, dict[str, Any]]:
    """period_end -> {first, latest} reports of one tag (annual, 10-K family only)."""
    node = (payload.get("facts", {}).get("us-gaap", {}) or {}).get(tag)
    if not node:
        return {}
    rows = node.get("units", {}).get(unit) or []
    by_end: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("form") not in _ANNUAL_FORMS:
            continue
        end = row.get("end")
        if not end:
            continue
        if kind == "duration":
            days = _days(row.get("start"), end)
            if days is None or not (_ANNUAL_DAYS[0] <= days <= _ANNUAL_DAYS[1]):
                continue
        by_end.setdefault(end, []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for end, reports in by_end.items():
        reports.sort(key=lambda r: (r.get("filed") or "", r.get("accn") or ""))
        first, latest = reports[0], reports[-1]
        values = sorted({float(r["val"]) for r in reports})
        out[end] = {
            "tag": tag,
            "start": first.get("start"),
            "first_value": float(first["val"]),
            "first_accession": first.get("accn"),
            "first_filed": first.get("filed"),
            "latest_value": float(latest["val"]),
            "latest_accession": latest.get("accn"),
            "latest_filed": latest.get("filed"),
            "distinct_values": values,
        }
    return out


def extended_series(payload: dict[str, Any], period_ends: list[str]) -> dict[str, dict[str, Any]]:
    """concept -> period_end (of ``period_ends``) -> chosen report, aligned within a week.

    The chosen value is the FIRST-reported one (the value in the 10-K for that year, which is what that
    year's MD&A discusses); the latest value is kept beside it so a recast is visible.
    """
    def align(series: dict[str, dict[str, Any]], target: str) -> Optional[dict[str, Any]]:
        t = date.fromisoformat(target)
        best = None
        for end, report in series.items():
            gap = abs((date.fromisoformat(end) - t).days)
            if gap <= 7 and (best is None or gap < best[0]):
                best = (gap, end, report)
        return {**best[2], "end": best[1]} if best else None

    out: dict[str, dict[str, Any]] = {}
    for concept, (kind, unit, tags) in EXTENDED_CONCEPTS.items():
        per_tag = [(tag, _tag_series(payload, tag, kind, unit)) for tag in tags]
        chosen: dict[str, Any] = {}
        for target in period_ends:
            for tag, series in per_tag:
                hit = align(series, target)
                if hit is not None:
                    alternatives = {
                        other: round(found["first_value"], 2)
                        for other, other_series in per_tag
                        if other != tag and (found := align(other_series, target)) is not None
                    }
                    chosen[target] = {**hit, "alternatives": alternatives}
                    break
        if chosen:
            out[concept] = {"kind": kind, "unit": unit, "points": chosen}
    return out
