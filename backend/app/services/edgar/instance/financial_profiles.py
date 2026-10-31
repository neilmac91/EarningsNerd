"""Accession-aware XBRL extraction: financial profiles."""

from typing import Any, Dict, List, Optional

from .core import logger

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
        # A bank MUST yield both interest components — this is what separates a real bank from an
        # asset-manager/broker-dealer that merely tags a net-interest line (KKR, SCHW). When only one
        # resolves, the profile is rejected and the filer falls through to the reported-total path.
        "required": ("net_interest_income", "noninterest_income"),
        "selectors": [
            ("net_interest_income", ("InterestIncomeExpenseNet",), "NetInterestIncome"),
            ("noninterest_income", ("NoninterestIncome",), "NonInterestIncome"),
            # The bank's own reported consolidated total, when it publishes one (e.g. JPM "Total net
            # revenue" $182.4B); self-gates to nothing for small banks (MCB) that report no such line.
            ("revenue", ("Revenues", "RevenuesNetOfInterestExpense"), "Revenue"),
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


def cash_financial_classification(company: Any, sic: Any, profile_key: Optional[str] = None) -> dict:
    """Internal cash eligibility from the selected company's already available metadata.

    EdgarTools business_category is a cached_property; never invoke that lazy property here.
    The existing statement classifier may already have populated it. Missing metadata is not
    evidence of a nonfinancial issuer, even when the old bank-component predicate is false.
    """
    from edgar.entity.categorization import BusinessCategory

    cached_category = getattr(company, "__dict__", {}).get("business_category")
    category = cached_category if isinstance(cached_category, str) else None
    token = str(sic).strip() if sic is not None and not isinstance(sic, bool) else ""
    # SIC 9995/9999 are non-operating/unclassified, not affirmative operating-industry evidence.
    code = int(token) if token.isascii() and token.isdigit() and 3 <= len(token) <= 4 else None
    if code is not None and not 100 <= code < 9000:
        code = None
    profile = profile_key if profile_key in {p["key"] for p in FINANCIAL_PROFILES} else None
    financial_categories = {
        BusinessCategory.BANK.value, BusinessCategory.INSURANCE_COMPANY.value,
        BusinessCategory.INVESTMENT_MANAGER.value, BusinessCategory.BDC.value,
        BusinessCategory.REIT.value, BusinessCategory.ETF.value,
        BusinessCategory.MUTUAL_FUND.value, BusinessCategory.CLOSED_END_FUND.value,
    }
    if profile or category in financial_categories or (
        code is not None and FINANCIAL_SIC_LOW <= code <= FINANCIAL_SIC_HIGH
    ):
        classified = True
    elif code is not None and category == BusinessCategory.OPERATING_COMPANY.value:
        classified = False
    else:
        classified = None
    return {"is_financial": classified, "sic": f"{code:04d}" if code is not None else None,
            "profile": profile, "business_category": category if isinstance(category, str) else None}


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
