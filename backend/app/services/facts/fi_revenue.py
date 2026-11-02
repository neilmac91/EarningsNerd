"""A financial filer's revenue in companyfacts: its reported total, never its ASC 606 fee line (E264, E286).

For SIC 6000-6799 the generic registry fails both ways: its first tag, the ASC 606 element, is a fee subset beside a
bank's, insurer's or REIT's total (IBKR, MET, AMT, AXP, COF), and it never reads the bank total element.
``financial_revenue_tags`` chooses, from the filer's own payload, the tags the collector then reads in its usual
per-period merge (the first tag with data wins a period). A later tag fills periods the earlier ones lack only on
evidence that it measures the same thing: its value at the latest period it shares with them matches a value they
reported there (WFC, MS, JPM; never IBKR's gross Revenues beside its net total). A total element sharing none does
not fill; an ASC 606 element sharing no year has its own test (2). Periods are years where two tags share any, else
quarters. A bank's sum is its net interest income plus its noninterest income as one filing reports them for a year
(a quarter, only in (2)); its net total is that sum, or less a provision (HDB).

1. The total elements, in order: RevenuesNetOfInterestExpense, Revenues, SalesRevenueNet, then RealEstateRevenueNet
   and SalesRevenueServicesNet, which filers tagged before ASC 606 (ARE, BRX, PLD, MRSH). One is left out when a
   filing reads it more than 3% above the bank's sum for a year (WBHC's gross Revenues, MUFG's segment figure; USB's
   total reads 1.2% above). A quarter's sum leaves none out, since STT's 2020 10-Qs tag their noninterest income near
   zero; so WBHC's 10-Qs still read its gross Revenues (E290). One is also left out when it reports one year, which
   another total element reports among others (CLSK's FY2019 component); or when it is below the ASC 606 element
   (excluding assessed tax) at every period both report. Below 90% of it, that is a partial line (BLK's FY2024
   10-K). From 90%, it is the total before ASC 606 restated it (AJG FY2014-15): read last, so it fills only the
   periods every other tag lacks, and only when that element is read.
2. The ASC 606 elements, excluding then including assessed tax (CBOE, ARE, BRX, SDEV and HUT tag their total with
   the latter), after the totals, each read only when it is the filer's total. Either its value matches the earlier
   tags' at the latest year it shares with them (ICE, NDAQ, EQIX, O, PNC); or it shares no year with them, matches
   them at the latest quarter they share if they share one (a quarter can refuse it, never admit it), and no filing
   reads it more than 3% below the bank's sum (RF's, FITB's and WAL's fee lines read 1-9% of it): a year's, or where
   no filing reports the element for a year beside both lines, a quarter's (a 10-Q's own facts). Either way no
   period it fills reads it below the interest, premium, investment or lease revenue beside it, a total never being
   below one of its parts: TRC's and PAPL's totals sit above their lease and interest lines, while BNY's 2018 fee
   quarters sit below its noninterest income and SYF's fees below its net interest income.

A lender without a total gets no revenue row (SYF, WBHC): its top line stays its net interest income. With no total
element, a fee subset that reads above every part beside it is read as the total, as one with nothing beside it is.
"""
from __future__ import annotations

from datetime import date

from app.services.facts.concepts import CROSS_CHECK_TOLERANCE
from app.services.facts.currency import admitted_items

TOTAL_TAGS = (
    "RevenuesNetOfInterestExpense", "Revenues", "SalesRevenueNet", "RealEstateRevenueNet", "SalesRevenueServicesNet",
)
FEE_TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
FEE_TAGS = (FEE_TAG, "RevenueFromContractWithCustomerIncludingAssessedTax")
NON_606_TAGS = (  # revenue outside ASC 606: interest, premiums, investment income (a BDC's whole total), leases
    "InterestIncomeExpenseNet", "InterestAndDividendIncomeOperating", "InterestIncomeOperating", "NoninterestIncome",
    "PremiumsEarnedNet", "NetInvestmentIncome", "GrossInvestmentIncomeOperating", "OperatingLeaseLeaseIncome",
    "LeaseIncome", "OperatingLeasesIncomeStatementLeaseRevenue",
)  # not InvestmentIncomeNet: NDAQ, ICE and BX tag nonoperating income with it beside a fee line that is their total
RULE_TAGS = (*TOTAL_TAGS, *FEE_TAGS, *NON_606_TAGS)  # every element the rule reads, a bank's sum among the parts
PARTIAL_RATIO = 0.9  # a total element below this share of the ASC 606 element is a partial line (BLK's at 0.62)
IDENTITY_TOLERANCE = 0.03  # a line against the bank's sum (module docstring)
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


def _by_filing(usgaap: dict, tag: str, unit: str, foreign: frozenset, klass: str = "FY") -> dict:
    """Each admitted item of ``tag`` for a year (``klass`` "Q": a quarter), {(period end, accession): value}. One filing
    states a bank's lines on one basis, where the latest filed values can mix bases (PNC's 2017 noninterest income,
    recast in a 2020 filing)."""
    node = usgaap.get(tag)
    units = node.get("units") if isinstance(node, dict) else None
    listed = units.get(unit) if isinstance(units, dict) else None
    return {(key[0], str(item.get("accn") or "")): float(value)
            for key, _start, value, item in admitted_items(listed if isinstance(listed, list) else [], instant=False)
            if key[1] == klass and item.get("accn") not in foreign}


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


def _years(series: _Items) -> set:
    return {key for key in series if key[1] == "FY"}


def _take(chosen: list[str], held: _Items, tag: str, series: _Items) -> None:
    """Choose ``tag``: it fills the periods no earlier choice holds, and a later tag is judged against them too."""
    chosen.append(tag)
    for key, values in series.items():
        held.setdefault(key, values)


def _fee_admitted(fee: _Items, held: _Items, beside: list, bank_ratios: list[float]) -> bool:
    """An ASC 606 element is the filer's total where it fills (module docstring, 2)."""
    if not fee:
        return False
    shared = _shared(fee, held)  # the years both report, else the quarters
    agrees = bool(shared) and _matches(_read(fee[max(shared)]), held[max(shared)])
    below_a_part = any(key not in held and _read(fee[key]) < (1 - CROSS_CHECK_TOLERANCE) * v for key, v in beside)
    if shared and (max(shared)[1] == "FY" or not agrees):  # a shared year decides; a shared quarter can only refuse
        return agrees and not below_a_part
    return not below_a_part and all(r >= 1 - IDENTITY_TOLERANCE for r in bank_ratios)


def financial_revenue_tags(usgaap: dict, unit: str, foreign: frozenset = frozenset()) -> tuple[str, ...]:
    """The tags a financial filer's revenue is read from, in priority order (module docstring); () for none."""
    lines = ("InterestIncomeExpenseNet", "NoninterestIncome")  # a bank's sum (module docstring)
    sums = {klass: [_by_filing(usgaap, line, unit, foreign, klass) for line in lines] for klass in ("FY", "Q")}

    def bank_ratios(tag: str, klass: str = "FY") -> list[float]:  # the tag over the bank's sum, per filing and period
        (nii, non), line = sums[klass], _by_filing(usgaap, tag, unit, foreign, klass)
        return [line[k] / parts for k in set(line) & set(nii) & set(non) if (parts := nii[k] + non[k]) > 0]

    fee = _items(usgaap, FEE_TAG, unit, foreign)
    totals = {tag: series for tag in TOTAL_TAGS if (series := _items(usgaap, tag, unit, foreign))
              and all(r <= 1 + IDENTITY_TOLERANCE for r in bank_ratios(tag))}
    chosen: list[str] = []
    held: _Items = {}  # each period's values, from the first chosen tag that reports it
    restated: list[str] = []  # totals just below the ASC 606 element: the years before ASC 606 restated them
    for tag, series in totals.items():
        years = _years(series)
        if len(years) == 1 and any(years < _years(other) for other in totals.values()):
            continue  # one year that another total element reports among others: a one-off line (CLSK)
        below = _shared(series, fee)
        if below and all(_read(series[k]) < (1 - CROSS_CHECK_TOLERANCE) * _read(fee[k]) for k in below):
            if all(_read(series[k]) >= PARTIAL_RATIO * _read(fee[k]) for k in below):
                restated.append(tag)
            continue  # a partial line, or a total the ASC 606 element restated
        shared = _shared(series, held)
        if not chosen or (shared and _matches(_read(series[max(shared)]), held[max(shared)])):
            _take(chosen, held, tag, series)
    for tag in FEE_TAGS:
        series = _items(usgaap, tag, unit, foreign)
        beside = [(key, v) for part in NON_606_TAGS for key, got in _items(usgaap, part, unit, foreign).items()
                  if key in series and (v := _read(got)) > 0]  # each positive part, as read, at a period it reports
        ratios = bank_ratios(tag) or bank_ratios(tag, "Q")  # a quarter's sum where no filing reports a year (a 10-Q)
        if _fee_admitted(series, held, beside, ratios):
            _take(chosen, held, tag, series)
    return (*chosen, *(restated if FEE_TAG in chosen else ()))
