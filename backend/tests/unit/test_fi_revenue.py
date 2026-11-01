"""E264: a financial filer's companyfacts revenue is its reported total, never its ASC 606 fee line.

Fixtures (``tests/fixtures/companyfacts_fi/<TICKER>.json``) are SEC companyfacts fetched 2026-11-01 through
``facts/transport``, trimmed to the us-gaap USD items of the tags each case reads, every item whose period ends on or
after the filer's first kept year, with the fields start, end, val, accn, fy, fp, form and filed: IBKR from 2012
(RevenuesNetOfInterestExpense, Revenues, the ASC 606 tag, ProfitLoss), BLK from 2015 (Revenues, ASC 606), ICE from 2011
(Revenues, ASC 606), WFC from 2015 (RevenuesNetOfInterestExpense, Revenues), AMT from 2014 (Revenues, SalesRevenueNet,
ASC 606, OperatingLeaseLeaseIncome), TROW from 2007 (RevenuesNetOfInterestExpense, Revenues, ASC 606), KKR from 2016
(Revenues, ASC 606), AXP from 2015 (RevenuesNetOfInterestExpense, both ASC 606 tags), PNC from 2017 (Revenues, ASC 606)
and MET from 2020 (Revenues, ASC 606). Each gives the same tag choice and the same revenue rows, after its first kept
year, as the full payload. The lender without a total (fee 50 beside net interest income 400) stays pinned by
``test_companyfacts_ingest.py``'s financial cases.
"""
import ast
import copy
import json
import uuid
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pytest

from app.services.facts import fi_revenue
from app.services.facts.companyfacts import normalize_companyfacts
from app.services.facts.concepts import COMPANYFACTS_DURATION_TAGS, HEADLINE_GAAP_TAGS, _classify_duration
from app.services.facts.currency import admitted_items
from app.services.facts.reconcile import extract_authoritative_values

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures" / "companyfacts_fi"
TICKERS = ("IBKR", "BLK", "ICE", "WFC", "AMT", "TROW", "KKR", "AXP", "PNC", "MET")
RNOIE, REV, SRN = "RevenuesNetOfInterestExpense", "Revenues", "SalesRevenueNet"
FEE, FEEI = "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax"
FEE_TAGS = {f"us-gaap:{FEE}", f"us-gaap:{FEEI}"}


def _load(ticker):
    return json.loads((FIXTURES / f"{ticker}.json").read_text())


def _as_of(payload, cutoff):
    """The payload as SEC served it on ``cutoff``: the items filed on or before it."""
    out = copy.deepcopy(payload)
    for node in out["facts"]["us-gaap"].values():
        node["units"] = {u: [i for i in items if i["filed"] <= cutoff] for u, items in node["units"].items()}
    return out


def _drop(payload, tag, pred):
    out = copy.deepcopy(payload)
    node = out["facts"]["us-gaap"].get(tag)
    if node:
        node["units"]["USD"] = [i for i in node["units"]["USD"] if not pred(i)]
    return out


def _item(val, end, start, accn, form="10-K", filed=None, fp="FY"):
    return {"val": val, "end": end, "start": start, "accn": accn, "form": form,
            "filed": filed or f"{int(end[:4]) + 1}-02-15", "fy": int(end[:4]), "fp": fp}


def _years(tag_vals):
    """{tag: {year: value}} as calendar-year 10-K items, one accession per year."""
    return {"facts": {"us-gaap": {tag: {"units": {"USD": [_item(v, f"{y}-12-31", f"{y}-01-01", f"K{y}")
                                                         for y, v in sorted(vals.items())]}}
                                  for tag, vals in tag_vals.items()}}}


def _facts(payload):
    return normalize_companyfacts(1, payload, financial_sic=True)[0]


def _fy(payload):
    facts = _facts(payload)
    return {f["period_end"].year: (round(f["value"] / 1e9, 3), (f.get("raw_tag") or "").removeprefix("us-gaap:"))
            for f in facts if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}, facts


def _operands(fact):
    """(raw_tag, start, end, value) of a revenue row, or of each operand of a calculated one."""
    if fact.get("raw_tag"):
        return [(fact["raw_tag"], fact["period_start"], fact["period_end"], fact["value"])]
    return [(i.get("raw_tag"), i.get("period_start"), i.get("period_end"), i.get("value"))
            for i in (fact.get("provenance") or {}).get("inputs") or []]


def _fee_rows(facts):
    return [f for f in facts if f["concept"] == "revenue" and any(t in FEE_TAGS for t, *_ in _operands(f))]


@pytest.mark.parametrize("ticker,tags", [
    ("IBKR", (RNOIE,)), ("WFC", (RNOIE, REV)), ("BLK", (FEE,)), ("ICE", (REV, FEE)), ("AMT", (REV, SRN)),
    ("TROW", (RNOIE, REV, FEE)), ("KKR", (REV,)), ("AXP", (RNOIE,)), ("PNC", (REV, FEE)), ("MET", (REV,)),
])
def test_each_filer_reads_its_own_tags(ticker, tags):
    assert fi_revenue.financial_revenue_tags(_load(ticker)["facts"]["us-gaap"], "USD") == tags


def test_a_broker_reads_its_net_total_never_its_fee_line():
    years, facts = _fy(_load("IBKR"))
    assert years[2025] == (6.205, RNOIE) and years[2018] == (1.903, RNOIE)
    assert [years[y][0] for y in (2016, 2017, 2018, 2019)] == [1.396, 1.702, 1.903, 1.937]
    assert min(years) == 2014 and _fee_rows(facts) == []  # gross Revenues (2012-2019) never fills
    margin = [round(f["value"], 1) for f in facts if f["concept"] == "net_margin" and f["fiscal_period"] == "FY"
              and f["period_end"].year == 2025]
    assert margin == [70.2]  # 178.6 on the fee line


def test_a_newest_10k_without_the_total_keeps_the_older_years():
    payload = _load("IBKR")
    last = max((i for i in payload["facts"]["us-gaap"][RNOIE]["units"]["USD"] if i["form"] == "10-K"),
               key=lambda i: i["filed"])["accn"]
    years, facts = _fy(_drop(payload, RNOIE, lambda i: i["accn"] == last))
    assert years[2024] == (5.185, RNOIE) and 2025 not in years and _fee_rows(facts) == []


def test_gross_revenues_never_fills_beside_the_net_total_it_never_overlaps():
    years, _ = _fy(_drop(_load("IBKR"), REV, lambda i: i["end"] >= "2014"))
    assert min(years) == 2014


def test_a_second_total_fills_only_where_it_agrees():
    years, _ = _fy(_load("WFC"))
    assert (years[2016], years[2017], years[2019], years[2025]) == (
        (88.267, REV), (88.389, REV), (86.832, RNOIE), (83.699, RNOIE))


def test_a_partial_revenues_line_never_wins():
    years, _ = _fy(_load("BLK"))
    then, _ = _fy(_as_of(_load("BLK"), "2025-03-31"))  # its FY2024 10-K tagged a sub-line as Revenues
    assert [years[y] for y in (2022, 2023, 2024, 2025)] == [(17.873, FEE), (17.859, FEE), (20.407, FEE), (24.216, FEE)]
    assert [then[y] for y in (2022, 2023, 2024)] == [(17.873, FEE), (17.859, FEE), (20.407, FEE)]


def test_the_fee_tag_fills_only_after_a_total_it_matches():
    years, _ = _fy(_load("ICE"))
    assert (years[2011][1], years[2015], years[2018], years[2025]) == (REV, (4.682, REV), (6.276, FEE), (12.64, FEE))


def test_a_legacy_total_fills_and_the_fee_subset_never_does():
    years, facts = _fy(_load("AMT"))
    assert (years[2014], years[2025]) == ((4.1, SRN), (10.645, REV)) and _fee_rows(facts) == []
    without, facts = _fy(_drop(_load("AMT"), REV, lambda i: True))
    assert max(without) == 2017 and _fee_rows(facts) == []  # lease income beside the fee tag


def test_fee_items_that_once_carried_the_total_never_admit_the_fee_tag():
    payload = _drop(_drop(_load("AMT"), REV, lambda i: True), SRN, lambda i: i["end"] < "2016")
    assert _fee_rows(_facts(payload)) == []  # AMT's 2018 10-Qs tagged its total with the fee tag


def test_the_fee_tag_is_the_total_when_nothing_else_is_beside_it():
    years, _ = _fy(_load("TROW"))  # the fee tag alone since FY2016: no total, nothing else beside it
    assert (years[2008], years[2012], years[2016], years[2025]) == (
        (2.121, REV), (3.022, RNOIE), (4.285, FEE), (7.315, FEE))


def test_a_crisis_quarter_keeps_the_reported_total():
    years, facts = _fy(_load("KKR"))
    assert [years[y][0] for y in (2016, 2017, 2018, 2019, 2020)] == [2.04, 3.557, 2.396, 4.221, 4.231]
    q1 = [f for f in facts if f["concept"] == "revenue" and (f["fiscal_year"], f["fiscal_period"]) == (2020, "Q1")]
    assert q1 == [] and _fee_rows(facts) == []  # -1.00B is rejected, never replaced by 0.38B of fees


def test_a_card_issuer_never_reads_either_fee_tag():
    years, facts = _fy(_load("AXP"))
    assert years[2025] == (72.229, RNOIE) and years[2016] == (35.438, RNOIE) and _fee_rows(facts) == []


def test_a_bank_whose_fee_tag_carried_its_total_reads_it_only_where_no_total_does():
    years, facts = _fy(_load("PNC"))
    assert (years[2019], years[2025]) == ((16.839, REV), (23.099, REV)) and _fee_rows(facts) == []
    then, _ = _fy(_as_of(_load("PNC"), "2020-03-31"))  # its FY2019 10-K tagged total revenue with the fee tag
    assert (then[2018], then[2019]) == ((17.132, REV), (17.827, FEE))


def test_an_insurer_reads_its_total():
    years, facts = _fy(_load("MET"))
    assert [years[y][0] for y in (2022, 2023, 2024, 2025)] == [68.77, 66.905, 70.986, 77.084] and _fee_rows(facts) == []


@pytest.mark.parametrize("beside", ["OperatingLeaseLeaseIncome", "InterestIncomeExpenseNet",
                                    "GrossInvestmentIncomeOperating"])  # a BDC's total investment income
def test_no_total_and_other_revenue_beside_the_fee_tag_is_no_revenue(beside):
    years, _ = _fy(_years({FEE: {y: 450e6 for y in range(2022, 2026)}, beside: {y: 60e6 for y in range(2022, 2026)}}))
    assert years == {}


def test_a_crisis_year_keeps_the_reported_total():
    years, _ = _fy(_years({RNOIE: {2021: 100e6, 2022: 40e6, 2023: 110e6, 2024: 120e6, 2025: 130e6},
                           FEE: {2021: 60e6, 2022: 55e6, 2023: 62e6, 2024: 65e6, 2025: 70e6}}))
    assert years[2022] == (0.04, RNOIE)


def test_a_depressed_latest_year_never_admits_the_fee_tag():
    payload = _years({REV: {2022: 1.2e9, 2023: 1.1e9, 2024: 1.4e9, 2025: 0.3e9},
                      FEE: {2022: 0.6e9, 2023: 0.62e9, 2024: 0.65e9, 2025: 0.7e9}})
    payload["facts"]["us-gaap"][FEE]["units"]["USD"].append(
        _item(0.2e9, "2026-03-31", "2026-01-01", "Q126", form="10-Q", filed="2026-05-01", fp="Q1"))
    years, facts = _fy(payload)
    assert years[2025] == (0.3, REV) and _fee_rows(facts) == []


def test_the_fee_tag_is_judged_on_the_value_it_would_give():
    payload = _years({REV: {y: 7.0e9 for y in range(2018, 2023)}, FEE: {y: 0.5e9 for y in range(2018, 2026)}})
    payload["facts"]["us-gaap"][FEE]["units"]["USD"].insert(
        0, _item(7.0e9, "2022-12-31", "2022-01-01", "K2022A", filed="2023-01-15"))  # first filed, then corrected
    years, facts = _fy(payload)
    assert max(years) == 2022 and _fee_rows(facts) == []


def test_the_fee_tag_is_judged_at_the_latest_year_it_shares():
    years, facts = _fy(_years({REV: {y: 10.0e9 for y in range(2020, 2025)},
                               FEE: {2020: 10.0e9, **{y: 1.0e9 for y in range(2021, 2026)}}}))
    assert 2025 not in years and _fee_rows(facts) == []


def _quarter_shape(fee_q1_2017, beside=None):
    """AXP's shape as SEC served it from its Q1 2018 10-Q until its FY2018 10-K: the net total's FY2017 and Q1 2017
    (from the 10-K), and the fee tag's Q1 2017 and Q1 2018 (from the 10-Qs), so the two share a quarter but no year."""
    usgaap = {RNOIE: {"units": {"USD": [_item(33.5e9, "2017-12-31", "2017-01-01", "K17", filed="2018-02-15"),
                                        _item(7.9e9, "2017-03-31", "2017-01-01", "K17", filed="2018-02-15")]}},
              FEE: {"units": {"USD": [_item(fee_q1_2017, "2017-03-31", "2017-01-01", "Q117", form="10-Q",
                                            filed="2017-04-25", fp="Q1"),
                                      _item(6.6e9, "2018-03-31", "2018-01-01", "Q118", form="10-Q", filed="2018-04-25",
                                            fp="Q1")]}}}
    if beside:
        usgaap[beside] = {"units": {"USD": [_item(1.0e9, "2018-03-31", "2018-01-01", "Q118", form="10-Q",
                                                  filed="2018-04-25", fp="Q1")]}}
    return {"facts": {"us-gaap": usgaap}}


def test_a_shared_quarter_refuses_a_fee_tag_below_the_total():
    payload = _quarter_shape(6.0e9)  # 6.0 against the total's 7.9
    assert fi_revenue.financial_revenue_tags(payload["facts"]["us-gaap"], "USD") == (RNOIE,)
    assert _fee_rows(_facts(payload)) == []


@pytest.mark.parametrize("beside,tags", [(None, (RNOIE, FEE)), ("InterestIncomeExpenseNet", (RNOIE,))])
def test_a_shared_quarter_never_admits_the_fee_tag_on_its_own(beside, tags):
    # The fee tag matches the total at the one quarter they share; whether it fills Q1 2018 is the component test's.
    payload = _quarter_shape(7.9e9, beside)
    assert fi_revenue.financial_revenue_tags(payload["facts"]["us-gaap"], "USD") == tags


def test_a_shared_year_decides_before_a_later_shared_quarter():
    # EQIX's and O's shape: the fee tag is the REIT's whole total, its Q4 sits beside the year, and lease income is
    # tagged beside it. The shared year admits the fee tag, so it fills the quarter no total reports yet.
    payload = _years({REV: {2024: 8.75e9, 2025: 9.22e9}, FEE: {2024: 8.75e9, 2025: 9.22e9},
                      "OperatingLeaseLeaseIncome": {2025: 1.0e9}})
    usgaap = payload["facts"]["us-gaap"]
    usgaap[REV]["units"]["USD"].append(_item(2.4e9, "2025-12-31", "2025-10-01", "K2025"))
    usgaap[FEE]["units"]["USD"] += [_item(2.4e9, "2025-12-31", "2025-10-01", "K2025"),
                                    _item(2.5e9, "2026-03-31", "2026-01-01", "Q126", form="10-Q", filed="2026-05-01",
                                          fp="Q1")]
    assert fi_revenue.financial_revenue_tags(usgaap, "USD") == (REV, FEE)
    first_quarter = [f for f in _facts(payload) if f["concept"] == "revenue" and f["period_end"] == date(2026, 3, 31)]
    assert [(round(f["value"] / 1e9, 2), f["raw_tag"]) for f in first_quarter] == [(2.5, f"us-gaap:{FEE}")]


@pytest.mark.parametrize("fee_2022,tags", [(19.9e9, (REV, FEE)), (3.1e9, (REV,)), (12.95e9, (REV, FEE))])
def test_a_fee_tag_a_year_admits_fills_no_period_below_a_part_beside_it(fee_2022, tags):
    # PNC's shape: the fee tag carries the total at FY2021, the last year a total reports. At FY2022 it reads the total
    # again, only the fee subset, or a total that is all net interest income, rounded below the 13.0B of it beside it.
    # A total is never below one of its parts, within the cross-check's tolerance.
    payload = _years({REV: {2020: 16.9e9, 2021: 19.2e9}, FEE: {2021: 19.2e9, 2022: fee_2022},
                      "InterestIncomeExpenseNet": {2021: 12.0e9, 2022: 13.0e9}})
    assert fi_revenue.financial_revenue_tags(payload["facts"]["us-gaap"], "USD") == tags
    years, _ = _fy(payload)
    authority = {end.year for (concept, end), _v in extract_authoritative_values(payload, financial=True).items()
                 if concept == "revenue"}
    filled = ((round(fee_2022 / 1e9, 3), FEE), True) if FEE in tags else (None, False)
    assert (years.get(2022), 2022 in authority) == filled


@pytest.mark.parametrize("ticker", TICKERS)
def test_the_authority_reads_the_feeds_revenue(ticker):
    payload = _load(ticker)
    authority = {end: v for (concept, end), v in extract_authoritative_values(payload, financial=True).items()
                 if concept == "revenue"}
    feed = {f["period_end"]: f["value"] for f in _facts(payload)
            if f["concept"] == "revenue" and f["fiscal_period"] == "FY"}
    assert authority == feed


def test_the_default_authority_is_unchanged():
    plain = {end.year: v for (concept, end), v in extract_authoritative_values(_load("IBKR")).items()
             if concept == "revenue"}
    assert plain[2025] == 2_440_000_000.0  # a non-financial filer's reading: the first tag with data


@pytest.mark.parametrize("ticker", TICKERS)
def test_never_the_fee_line_where_a_total_reports_more_at_any_filing_date(ticker):
    """Rule 12: replayed as SEC served it at every filing date in the fixture, each state the payload passed through,
    no revenue row (or calculation operand) carries the fee tag at a period any total tag reports more than 1% above
    it, in the full fixture; the fee-subset filers carry none at all."""
    full = _load(ticker)
    totals: dict = {}
    for tag in fi_revenue.TOTAL_TAGS:
        listed = full["facts"]["us-gaap"].get(tag, {}).get("units", {}).get("USD", [])
        for key, _start, value, _item_ in admitted_items(listed, instant=False):
            totals.setdefault(key, []).append(value)
    filed = sorted({i["filed"] for node in full["facts"]["us-gaap"].values() for items in node["units"].values()
                    for i in items})
    for cutoff in filed:
        rows = _fee_rows(_facts(_as_of(full, cutoff)))
        assert not (rows and ticker in ("IBKR", "AMT", "AXP", "KKR", "MET")), (cutoff, rows[:1])
        for fact in rows:
            for tag, start, end, value in _operands(fact):
                start = date.fromisoformat(start) if isinstance(start, str) else start
                end = date.fromisoformat(end) if isinstance(end, str) else end
                larger = [v for v in totals.get((end, _classify_duration(start, end)), []) if v > value * 1.01]
                assert larger == [], (cutoff, end, value)


def test_the_total_tags_stay_out_of_the_generic_registries():
    assert COMPANYFACTS_DURATION_TAGS["revenue"] == (FEE, REV, FEEI, SRN, "NetSales")  # non-financial filers unchanged
    assert HEADLINE_GAAP_TAGS["revenue"] == (FEE, REV, FEEI, SRN)
    named = [p.relative_to(BACKEND).as_posix() for p in (BACKEND / "app" / "services" / "facts").glob("*.py")
             if RNOIE in p.read_text()]
    assert named == ["app/services/facts/fi_revenue.py"]  # never a currency vote (currency.py reads the registries)


def _calls(path, name):
    tree = ast.parse(path.read_text())
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None)) == name]


# The functions that read a financial filer's revenue only when told it is one: each keyword defaults to False, the
# generic reading, so a call that drops it quietly reads the fee line again.
_FILER = {"extract_authoritative_values": "financial", "normalize_companyfacts": "financial_sic"}


def _filer_uses(path):
    """Each use of a ``_FILER`` function in ``path`` as (name, scope, how): "call" for a direct call that passes its
    keyword, "bare" for a direct call without it, and "other" for a use that would hide a call from the gate (an
    aliased import, a bound name, a partial, an argument). A name built at run time (getattr with a string) is beyond
    an AST walk."""
    tree = ast.parse(path.read_text())
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def scope(node):
        names = []
        while node in parent:
            node = parent[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
        return ".".join(reversed(names)) or "<module>"

    def named(node):
        name = getattr(node, "id", getattr(node, "attr", None))
        return name if isinstance(node, (ast.Name, ast.Attribute)) and name in _FILER else None

    uses, direct = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (name := named(node.func)):
            direct.add(node.func)
            uses.append((name, scope(node), "call" if any(k.arg == _FILER[name] for k in node.keywords) else "bare"))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            uses += [(name, scope(node), "other") for alias in node.names
                     if (name := alias.name.split(".")[-1]) in _FILER and alias.asname not in (None, name)]
    return uses + [(named(node), scope(node), "other") for node in ast.walk(tree) if named(node) and node not in direct]


@pytest.mark.parametrize("source,how", [
    ("from app.services.facts.reconcile import extract_authoritative_values as read\nread(p)\n", "other"),
    ("from app.services import facts_service\nread = facts_service.extract_authoritative_values\nread(p)\n", "other"),
    ("import functools\nfrom app.services.facts.reconcile import extract_authoritative_values\n"
     "functools.partial(extract_authoritative_values)\n", "other"),
    ("from app.services.facts import reconcile\nreconcile.extract_authoritative_values(p)\n", "bare"),
    ("from app.services.facts import reconcile\nreconcile.extract_authoritative_values(p, financial=True)\n", "call"),
    ("from app.services import facts_service\nfacts_service.normalize_companyfacts(1, p)\n", "bare"),
    ("from app.services import facts_service\nfacts_service.normalize_companyfacts(1, p, financial=True)\n", "bare"),
    ("from app.services.facts.companyfacts import normalize_companyfacts\n"
     "normalize_companyfacts(1, p, financial_sic=s)\n", "call"),
])
def test_the_filer_gate_reads_every_form_it_names(tmp_path, source, how):
    path = tmp_path / "planted.py"
    path.write_text(source)
    assert [found for _name, _scope, found in _filer_uses(path)] == [how]


def test_every_authority_and_normalizer_call_names_its_filer():
    """Rule 12: every use of extract_authoritative_values or normalize_companyfacts in app/, scripts/ and evals/ is a
    direct call that passes its keyword (financial=, financial_sic=), but E211's temporary proxy step: one bare
    authority call, in _Planner.__init__, whose one financial company (JPM) files no ASC 606 tag. It leaves with E211
    (todo E206), and the pin fails once it is stale."""
    found = Counter((path.relative_to(BACKEND).as_posix(), name, scope, how)
                    for root in ("app", "scripts", "evals") for path in (BACKEND / root).rglob("*.py")
                    if any(fn in path.read_text() for fn in _FILER)  # a use the walk can read names it
                    for name, scope, how in _filer_uses(path) if how != "call")
    assert found == {
        ("app/services/proxy_fact_repair.py", "extract_authoritative_values", "_Planner.__init__", "bare"): 1,
    }


def test_the_collector_and_the_census_read_the_same_choice():
    from scripts.restatement_census import measure_company

    for path in (BACKEND / "app/services/facts/companyfacts.py", BACKEND / "scripts/restatement_census.py"):
        assert _calls(path, "financial_revenue_tags"), path
    cells, _info = measure_company("IBKR", _load("IBKR"), True, 10)
    assert sum(1 for c in cells if c["concept"] == "revenue") == 10


def test_a_non_financial_filer_never_reaches_the_rule(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("financial_revenue_tags read for a non-financial filer")

    monkeypatch.setattr("app.services.facts.companyfacts.financial_revenue_tags", boom)
    monkeypatch.setattr("app.services.facts.reconcile.financial_revenue_tags", boom)
    payload = _load("IBKR")
    facts = normalize_companyfacts(1, payload, financial_sic=False)[0]
    assert any(f["raw_tag"] == f"us-gaap:{FEE}" for f in facts if f["concept"] == "revenue")  # today's generic reading
    assert extract_authoritative_values(payload)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.mark.requires_db
@pytest.mark.parametrize("sic,stored,source", [("6211", 6_205_000_000.0, "edgar_xbrl"),
                                               ("7372", 2_440_000_000.0, "companyfacts")])
def test_the_backfill_cross_check_keeps_a_financial_filers_total(sic, stored, source):
    from app.database import SessionLocal
    from app.models import Company, Filing, FinancialFact
    from app.services.facts.jobs import backfill_facts

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        company = Company(cik=suffix, ticker=("F" + suffix).upper(), name=f"Co {suffix}", sic=sic)
        db.add(company)
        db.commit()
        db.add(Filing(company_id=company.id, accession_number=f"ACC-fi-{suffix}", filing_type="10-K",
                      filing_date=datetime(2026, 2, 27), document_url="https://sec.example/x.htm",
                      sec_url="https://sec.example/", xbrl_data={"mark": "FI"}))
        db.commit()

        def extract(_xbrl):  # the statement reader's broker total
            return {"revenue": {"current": {"period": "2025-12-31", "value": 6_205_000_000.0}}}

        backfill_facts(db, extract=extract, companyfacts_fetcher=lambda _cik: _load("IBKR"), tickers=[company.ticker])
        row = db.query(FinancialFact).filter_by(company_id=company.id, concept="revenue").one()
        assert (float(row.value), row.source) == (stored, source)
    finally:
        db.close()
