"""A financial filer's revenue in companyfacts: its reported total, never its ASC 606 fee line (E264).

For SIC 6000-6799 the generic registry fails both ways: its first tag, the ASC 606 element, is a fee subset beside a
bank's, insurer's or REIT's total (IBKR, MET, AMT, AXP, COF), and it never reads the bank total element.
``financial_revenue_tags`` chooses, from the filer's own payload, the tags the collector then reads in its usual
per-period merge (the first tag with data wins a period):

1. The total elements, in order: RevenuesNetOfInterestExpense, Revenues, SalesRevenueNet. One is left out when it is
   below the fee element at every period both report (a partial line under a total element: BLK's FY2024 10-K). A
   later one fills periods the earlier ones lack only on evidence that it measures the same thing: its value at the
   latest period it shares with them matches a value they reported there (WFC, MS, JPM; never IBKR's gross Revenues
   beside its net total). Sharing none, it does not fill. Periods are years where two tags share any, else quarters.
2. The fee element last, so it fills only periods no total reports, and only when it is the filer's total. Either
   its value matches the totals' at the latest year it shares with them (ICE, NDAQ, EQIX, O, PNC) and no period it
   fills reads below the interest, premium, investment or lease revenue beside it, a total never being below one of
   its parts; or it shares no year with them, matches them at the latest quarter they share if they share one (a
   quarter can refuse it, never admit it), and no period of it carries such revenue beside it at all (BLK, TROW).

A lender without a total gets no revenue row (SYF): its top line stays its net interest income.
"""
from __future__ import annotations

from datetime import date

from app.services.facts.concepts import CROSS_CHECK_TOLERANCE
from app.services.facts.currency import admitted_items

TOTAL_TAGS = ("RevenuesNetOfInterestExpense", "Revenues", "SalesRevenueNet")
FEE_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
NON_606_TAGS = (  # revenue outside ASC 606: interest, premiums, investment income (a BDC's whole total), leases
    "InterestIncomeExpenseNet", "InterestAndDividendIncomeOperating", "InterestIncomeOperating", "NoninterestIncome",
    "PremiumsEarnedNet", "NetInvestmentIncome", "GrossInvestmentIncomeOperating", "OperatingLeaseLeaseIncome",
    "LeaseIncome", "OperatingLeasesIncomeStatementLeaseRevenue",
)  # not InvestmentIncomeNet: NDAQ, ICE and BX tag nonoperating income with it beside a fee line that is their total
_Items = dict[tuple[date, str], list[tuple[str, float]]]


def _items(usgaap: dict, tag: str, unit: str, foreign: frozenset) -> _Items:
    """Each admitted year or quarter item of ``tag`` in ``unit``, (filed, value) per (period end, klass)."""
    node = usgaap.get(tag)
    units = node.get("units") if isinstance(node, dict) else None
    listed = units.get(unit) if isinstance(units, dict) else None
    out: _Items = {}
    for key, _start, value, item in admitted_items(listed if isinstance(listed, list) else [], instant=False):
        if key[1] in ("FY", "Q") and item.get("accn") not in foreign:
            out.setdefault(key, []).append((str(item.get("filed") or ""), float(value)))
    return out


def _read(values: list[tuple[str, float]]) -> float:
    """The value the collector reads for a period: the latest filed, a later item winning a tie."""
    return max(enumerate(values), key=lambda pair: (pair[1][0], pair[0]))[1][1]


def _shared(a: _Items, b: _Items) -> set:
    """The periods two tags both report: the years when there is any, else the quarters."""
    keys = set(a) & set(b)
    return {key for key in keys if key[1] == "FY"} or keys


def _matches(value: float, values: list[tuple[str, float]]) -> bool:
    """``value`` is within ``CROSS_CHECK_TOLERANCE`` of a value another tag reported for the same period."""
    return any(abs(value - v) <= CROSS_CHECK_TOLERANCE * max(abs(value), abs(v)) for _, v in values)


def financial_revenue_tags(usgaap: dict, unit: str, foreign: frozenset = frozenset()) -> tuple[str, ...]:
    """The tags a financial filer's revenue is read from, in priority order (module docstring); () for none."""
    fee = _items(usgaap, FEE_TAG, unit, foreign)
    chosen: list[str] = []
    held: _Items = {}  # each period's values, from the first chosen tag that reports it
    for tag in TOTAL_TAGS:
        series = _items(usgaap, tag, unit, foreign)
        below = _shared(series, fee)
        if not series or (below and all(_read(series[k]) < (1 - CROSS_CHECK_TOLERANCE) * _read(fee[k]) for k in below)):
            continue
        shared = _shared(series, held)
        if chosen and not (shared and _matches(_read(series[max(shared)]), held[max(shared)])):
            continue
        chosen.append(tag)
        for key, values in series.items():
            held.setdefault(key, values)
    shared = _shared(fee, held)  # the years both report, else the quarters
    agrees = bool(shared) and _matches(_read(fee[max(shared)]), held[max(shared)])
    beside = [(key, v) for tag in NON_606_TAGS for key, got in _items(usgaap, tag, unit, foreign).items()
              if key in fee for _, v in got if v > 0]  # positive non-606 revenue at a period the fee tag reports
    if shared and (max(shared)[1] == "FY" or not agrees):  # a shared year decides; a shared quarter can only refuse
        admit = agrees and not any(  # where the fee tag fills a period, it is no smaller than a part beside it
            key not in held and _read(fee[key]) < (1 - CROSS_CHECK_TOLERANCE) * v for key, v in beside)
    else:
        admit = bool(fee) and not beside
    return (*chosen, FEE_TAG) if admit else tuple(chosen)
