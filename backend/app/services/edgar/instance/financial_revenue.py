"""A financial filer's revenue on the per-filing path: E264's choice, read from the filing's own facts (E278).

Read from fixed lists, a financial filer's revenue can be the wrong line: the statement reader's bank and catch-all
profiles anchor revenue on fixed tags, and the generic fact list reads the ASC 606 fee element second. So a fee line
(AXP; IBKR since FY2020), a gross total beside the net one (IBKR's FY2016-19 Revenues) or a partial line (BLK's FY2024
Revenues) would win where the filer reports a fuller total. E264 chooses a financial filer's revenue tags in
companyfacts (``facts/fi_revenue.financial_revenue_tags``). ``financial_revenue_concepts`` applies that rule to the
chosen filing's own undimensioned facts and nothing else (rule 2): no other filing, and no SEC request. The tags it
returns, in priority order, are the only revenue candidates on each route that reads this filing's revenue:
- the revenue selector of the profiles in ``FILING_REVENUE_PROFILES``, on the as-reported income statement;
- the generic fact list, when the statement reader returns nothing.

An empty choice means no revenue: a lender that reports no total (SYF). None means the routes read as before: a
non-financial filer, a filing that tags none of the rule's elements (an IFRS filer), or a failure, which is logged.
The insurer and BDC profiles keep their own totals: an insurer's total is never its fee line, and a BDC's total
investment income is one of the parts the rule reads beside the fee element.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.services.facts.fi_revenue import FEE_TAG, NON_606_TAGS, TOTAL_TAGS, financial_revenue_tags

from .core import _currency, _iso_date, _numeric, _reporting_currency, logger
from .financial_profiles import is_financial_institution

FILING_REVENUE_PROFILES = frozenset({"bank", "financial_generic"})
_RULE_TAGS = (*TOTAL_TAGS, FEE_TAG, *NON_606_TAGS)  # every element the rule reads
_UNIT = "filing"  # the one unit the filing's items are listed under: its reporting currency


def _rows(xb: Any, tag: str) -> List[Dict[str, Any]]:
    """The filing's facts for ``us-gaap:<tag>``; a failed query reads as none (``_fact_records_with_concept``)."""
    try:
        df = xb.facts.query().by_concept(f"us-gaap:{tag}", exact=True).to_dataframe()
    except Exception as exc:  # noqa: BLE001 - any query failure means "no facts"
        logger.debug(f"Fact query failed for us-gaap:{tag}: {exc}")
        return []
    return [] if df is None or getattr(df, "empty", True) else df.to_dict("records")


def _choose(xb: Any, company: Any, sic: Optional[str], form: str, period_of_report: str) -> Optional[Tuple[str, ...]]:
    if not is_financial_institution(company, sic):
        return None
    facts = []  # (tag, end, value, currency, start): undimensioned, valued, and no later than the filing's period
    for tag in _RULE_TAGS:
        for row in _rows(xb, tag):
            end, value = _iso_date(row.get("period_end")), _numeric(row.get("numeric_value"))
            if row.get("is_dimensioned") or end is None or value is None or end > period_of_report:
                continue
            facts.append((tag, end, value, _currency(row), _iso_date(row.get("period_start"))))
    if not facts:
        return None
    currency = _reporting_currency(
        [(end, value, ccy, 0.0) for _tag, end, value, ccy, _start in facts], period_of_report)
    usgaap: Dict[str, Any] = {}  # the filing's own items, shaped as companyfacts lists them
    for tag, end, value, ccy, start in facts:
        if currency is None or ccy == currency:
            item = {"form": form, "val": value, "start": start, "end": end, "accn": "", "filed": ""}
            usgaap.setdefault(tag, {"units": {_UNIT: []}})["units"][_UNIT].append(item)
    return financial_revenue_tags(usgaap, _UNIT)


def financial_revenue_concepts(
    xb: Any, company: Any, sic: Optional[str], form: str, period_of_report: str
) -> Optional[Tuple[str, ...]]:
    """The tags this filing's revenue is read from, in priority order; () for none; None to read as before.

    The filer is financial by the statement reader's own test (``is_financial_institution``). Only the filing's own
    facts are read: each tag's undimensioned facts ending on or before ``period_of_report``, in the reporting currency
    the rule's facts carry (``_reporting_currency``). Never raises: extraction must not break on the choice, so a
    failure is logged and the routes read as before.
    """
    try:
        return _choose(xb, company, sic, form, period_of_report)
    except Exception as exc:  # noqa: BLE001 - never let the choice break extraction
        logger.warning(f"Financial revenue choice failed: {exc}")
        return None
