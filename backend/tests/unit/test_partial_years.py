"""A quarterly report's year that holds only part of one never reaches a reader (E291, ``facts/fiscal_naming.py``).

CBAN's and FIX's Q1 2026 10-Qs tag their Q1 2025 comparatives with the full-year span 2025-01-01..2025-12-31, and,
filed after the 10-Ks, won FY2025 wherever the latest filed item wins. ``without_partial_years`` drops such an item
for every reader of companyfacts duration items: the collector's admission (``currency.admitted_items``), the
backfill cross-check's authority (``reconcile.extract_authoritative_values``) and the per-filing fallback
(``edgar/xbrl_companyfacts.py``). The fixtures are trimmed from SEC's payloads (CBAN's of 2026-11-02, FIX's of
2026-11-01) to the items ending from 2024 on.
"""
import ast
import json
from datetime import date
from pathlib import Path

import pytest

from app.services.edgar.xbrl_companyfacts import parse_company_facts
from app.services.facts.companyfacts import normalize_companyfacts
from app.services.facts.fiscal_naming import QUARTERLY_FORMS, without_partial_years
from app.services.facts.reconcile import extract_authoritative_values

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures" / "companyfacts_partial_years"
END = date(2025, 12, 31)
CBAN_10K, CBAN_10Q = "0000711669-26-000007", "0001104659-26-057671"
FIX_10K, FIX_10Q = "0001104659-26-017530", "0001104659-26-047689"


def _item(start, end, val, form="10-Q", accn="0000000000-26-000001", filed="2026-05-08"):
    return {"start": start, "end": end, "val": val, "form": form, "accn": accn, "filed": filed}


QUARTER = _item("2025-01-01", "2025-03-31", 20952000, accn="q1-2025", filed="2025-05-09")
ANNUAL = _item("2025-01-01", "2025-12-31", 91901000, form="10-K", accn="10k-2025", filed="2026-03-13")


# --- the rule --------------------------------------------------------------------------------------------------------

def test_a_10q_year_equal_to_another_filings_first_quarter_is_dropped():
    # CBAN's shape: the quarter is the Q1 2025 10-Q's own, and the year sits only in the Q1 2026 10-Q.
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    assert without_partial_years([QUARTER, ANNUAL, year]) == [QUARTER, ANNUAL]


def test_the_10q_carrying_the_quarter_too_loses_only_the_year():
    # FIX's shape: one 10-Q tags the comparative twice, with the quarter's span and with the year's.
    quarter, year = (_item("2025-01-01", end, 1831286000, accn="q1-2026") for end in ("2025-03-31", "2025-12-31"))
    assert without_partial_years([quarter, year]) == [quarter]


@pytest.mark.parametrize("end", ["2025-06-30", "2025-09-30"])
def test_a_year_equal_to_six_or_nine_months_from_the_same_start_is_dropped(end):
    # HP's FY2016 revenue was its first half; STX's FY2021 operating cash flow its nine months, in another filing.
    to_date = _item("2025-01-01", end, 3000000, accn="ytd")
    year = _item("2025-01-01", "2025-12-31", 3000000, accn="q-later")
    assert without_partial_years([to_date, year]) == [to_date]


def test_a_recast_year_matching_no_shorter_item_stays():
    # Macy's restated FY2021 in a December 2024 10-Q: 1,419M against the 10-K's 1,430M, no quarter of either.
    recast = _item("2025-01-01", "2025-12-31", 90000000, accn="restating-10q")
    assert without_partial_years([QUARTER, ANNUAL, recast]) == [QUARTER, ANNUAL, recast]


@pytest.mark.parametrize("value", [20952001, 20953000, 20900000])
def test_only_the_very_figure_marks_a_partial_year(value):
    # Estee Lauder's FY2023 operating income, 1,509M in its 10-K and again in two 10-Qs, sits 0.3% below its nine
    # months' 1,514M: a real year whose fourth quarter lost money. A tolerance of 0.5% would drop it, and DLR's and
    # TRC's real years with it.
    year = _item("2025-01-01", "2025-12-31", value, accn="q1-2026")
    assert without_partial_years([QUARTER, year]) == [QUARTER, year]


@pytest.mark.parametrize("end", ["2025-05-15", "2025-08-31"])
def test_a_span_neither_a_quarter_nor_six_or_nine_months_never_drops_the_year(end):
    # 134 and 242 days from the year's start: no class of _classify_duration, so no part of a year here.
    span = _item("2025-01-01", end, 20952000, accn="other-span")
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    assert without_partial_years([span, year]) == [span, year]


def test_an_annual_reports_year_equal_to_its_first_quarter_stays():
    # BMY's FY2011 investing cash flow equals its Q1 2011's: a 10-K's year is never second-guessed.
    year = _item("2025-01-01", "2025-12-31", 20952000, form="10-K", accn="10k")
    assert without_partial_years([QUARTER, year]) == [QUARTER, year]


def test_a_zero_year_stays():
    # LIFD's FY2019 revenue is zero in its 10-K and its 10-Q alike: the rest of a year can be exactly nothing then.
    quarter, year = _item("2025-01-01", "2025-03-31", 0), _item("2025-01-01", "2025-12-31", 0, accn="q-later")
    assert without_partial_years([quarter, year]) == [quarter, year]


@pytest.mark.parametrize("start", ["2025-04-01", "2024-12-31", "2025-01-02"])
def test_a_shorter_item_from_another_start_never_drops_the_year(start):
    # Macy's FY2023 EPS equals its Q3's by coincidence: only the year's own start ties a part to it.
    part = _item(start, "2025-06-30" if start == "2025-04-01" else "2025-03-31", 20952000, accn="q")
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q-later")
    assert without_partial_years([part, year]) == [part, year]


@pytest.mark.parametrize("form", ["10-Q", "10-Q/A", "10-QT", "10-QT/A"])
def test_every_quarterly_form_is_read_so(form):
    # AIRJ's FY2023 ProfitLoss, its Q1 2023's, sits in a 10-Q and again in its 10-Q/A.
    year = _item("2025-01-01", "2025-12-31", 20952000, form=form, accn="q1-2026")
    assert without_partial_years([QUARTER, year]) == [QUARTER]
    assert QUARTERLY_FORMS == {"10-Q", "10-Q/A", "10-QT", "10-QT/A"}


@pytest.mark.parametrize("form", ["10-K", "10-K/A", "10-KT", "20-F", "40-F", "8-K", "6-K", "S-1", "S-4", None])
def test_no_other_form_is_dropped(form):
    # WMB's 2018 8-K recast puts FY2015 operating income at its Q1's 227M against the 10-Ks' 226M: a real recast.
    year = _item("2025-01-01", "2025-12-31", 20952000, form=form, accn="other")
    assert without_partial_years([QUARTER, year]) == [QUARTER, year]


def test_order_identity_and_every_unreadable_item_are_kept():
    unreadable = ["not an item", {"val": 20952000, "form": "10-Q"}, {**QUARTER, "start": "bad"},
                  {**QUARTER, "val": True}, {**QUARTER, "val": "20952000"}, {**QUARTER, "end": None}]
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    kept = without_partial_years([*unreadable, QUARTER, year, ANNUAL])
    assert kept == [*unreadable, QUARTER, ANNUAL] and all(a is b for a, b in zip(kept, [*unreadable, QUARTER, ANNUAL]))
    assert without_partial_years([]) == []


# --- the readers, on SEC's own payloads --------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def payloads():
    return {name: json.loads((FIXTURES / f"{name}.json").read_text()) for name in ("CBAN", "FIX")}


def _fy2025(facts):
    return {fact["concept"]: (fact["value"], fact["accession"]) for fact in facts
            if fact["period_end"] == END and fact["fiscal_period"] == "FY"}


def _q4_2025(facts):
    return {fact["concept"]: fact["value"] for fact in facts if fact["period_end"] == END and fact["fiscal_period"] == "Q4"}


def test_the_collector_reads_cbans_fy2025_from_its_10k_and_derives_its_q4(payloads):
    facts, _meta = normalize_companyfacts(1, payloads["CBAN"], financial_sic=True)
    assert {concept: fy for concept, fy in _fy2025(facts).items() if concept in (
        "net_income", "net_interest_income", "noninterest_income", "eps_diluted")} == {
        "net_income": (28253000.0, CBAN_10K), "net_interest_income": (91901000.0, CBAN_10K),
        "noninterest_income": (40280000.0, CBAN_10K), "eps_diluted": (1.59, CBAN_10K)}  # the 10-Q read 0.38
    assert {k: v for k, v in _q4_2025(facts).items() if k in ("net_income", "net_interest_income")} == {
        "net_income": 7843000.0, "net_interest_income": 25865000.0}  # incompatible vintages withheld both


def test_the_collector_reads_fixs_fy2025_from_its_10k_and_derives_its_q4(payloads):
    facts, _meta = normalize_companyfacts(2, payloads["FIX"])
    fy = _fy2025(facts)
    assert {concept: fy[concept] for concept in ("revenue", "gross_profit", "operating_income")} == {
        "revenue": (9101641000.0, FIX_10K), "gross_profit": (2195899000.0, FIX_10K),
        "operating_income": (1314589000.0, FIX_10K)}  # the 10-Q read 1,831,286,000 / 403,416,000 / 209,098,000
    assert round(fy["net_margin"][0], 4) == 11.2349  # not 55.8382: the 10-K's net income over the 10-Q's revenue
    assert _q4_2025(facts)["revenue"] == 2646067000.0


@pytest.mark.parametrize("name, financial, expected", [
    ("CBAN", True, {"net_income": 28253000.0}),  # the 10-Q's 6,613,000 would replace a fresh 10-K parse
    ("FIX", False, {"revenue": 9101641000.0, "net_income": 1022558000.0}),  # the 10-Q's revenue: 1,831,286,000
])
def test_the_cross_checks_authority_is_the_10ks(payloads, name, financial, expected):
    authority = extract_authoritative_values(payloads[name], financial=financial)
    assert {concept: value for (concept, end), value in authority.items() if end == END} == expected


def test_the_per_filing_fallback_drops_the_year_against_another_filings_quarter():
    # CBAN's net interest income shape: the Q1 2026 10-Q carries Q1 2025 only as a year; the quarter is the Q1 2025
    # 10-Q's own. So the rule runs before the fallback narrows the items to the filing it reads.
    items = [_item("2025-01-01", "2025-03-31", 100, accn="0000000000-25-000001", filed="2025-05-09"),
             _item("2025-01-01", "2025-12-31", 400, form="10-K", accn="0000000000-26-000002", filed="2026-03-13"),
             _item("2026-01-01", "2026-03-31", 120, accn="0000000000-26-000003"),
             _item("2025-01-01", "2025-12-31", 100, accn="0000000000-26-000003")]
    payload = {"facts": {"us-gaap": {"NetIncomeLoss": {"units": {"USD": items}}}}}
    points = parse_company_facts(payload, "0000000000-26-000003")["net_income"]
    assert [(point["period"], point["value"]) for point in points] == [("2026-03-31", 120)]


@pytest.mark.parametrize("name, accession, metric", [("CBAN", CBAN_10Q, "net_income"), ("FIX", FIX_10Q, "revenue")])
def test_the_per_filing_fallback_reads_no_year_from_the_10q(payloads, name, accession, metric):
    points = parse_company_facts(payloads[name], accession)[metric]
    assert points and all(point["period"] != "2025-12-31" for point in points)  # was a Q4-labelled Q1 value
    assert {point.get("period_start") for point in points if point["period"] == "2025-03-31"} == {"2025-01-01"}


# --- the gate (CLAUDE.md rule 12): every companyfacts reader goes through the rule ------------------------------------

READERS = {"admitted_items", "without_partial_years"}  # admitted_items calls the rule for every duration list
EXEMPT = {
    ("app/services/facts/currency.py", "payload_view"): "reads each filing's form and filed date, never a value",
    ("app/services/facts/reporting_basis.py", "_items"): "counts each basis's items by form, never a value",
    ("app/services/proxy_fact_repair.py", "proxy_items"): "reads proxy statements' items, which no rule here admits",
    ("app/services/edgar/instance/financial_revenue.py", "_choose"):
        "builds a companyfacts-shaped map of one filing's own facts for fi_revenue, which reads it via admitted_items",
    ("scripts/restatement_census.py", "_accession_index"):
        "indexes what each filing carries, as evidence; its winners come from _collect_companyfacts_values",
    ("scripts/native_delivery_probe.py", "plan"): "an eval unit manifest's units, not companyfacts",
    ("scripts/native_delivery_probe.py", "run"): "an eval unit manifest's units, not companyfacts",
}


def _reads_units(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Subscript) and isinstance(sub.slice, ast.Constant) and sub.slice.value == "units":
            return True
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in ("get", "setdefault")
                and sub.args and isinstance(sub.args[0], ast.Constant) and sub.args[0].value == "units"):
            return True
    return False


def _unit_readers() -> dict[tuple[str, str], set[str]]:
    """Each function in app/ or scripts/ (the Ops steps' code) that reads a ``units`` map, with the rule's names it
    uses."""
    found = {}
    for path in sorted([*(BACKEND / "app").rglob("*.py"), *(BACKEND / "scripts").rglob("*.py")]):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _reads_units(node):
                names = {sub.id if isinstance(sub, ast.Name) else sub.attr for sub in ast.walk(node)
                         if isinstance(sub, (ast.Name, ast.Attribute))}
                found[(str(path.relative_to(BACKEND)), node.name)] = names & READERS
    return found


def test_every_function_reading_companyfacts_units_reads_them_through_the_rule():
    readers = _unit_readers()
    unruled = {key for key, names in readers.items() if not names and key not in EXEMPT}
    assert not unruled, f"read companyfacts items through admitted_items or without_partial_years: {sorted(unruled)}"
    assert set(EXEMPT) <= set(readers), f"stale exemptions: {sorted(set(EXEMPT) - set(readers))}"
    assert {("app/services/facts/reconcile.py", "extract_authoritative_values"),
            ("app/services/edgar/xbrl_companyfacts.py", "select_fact_data_with_concept"),
            ("app/services/facts/companyfacts.py", "_collect_companyfacts_values")} <= set(readers)


def test_the_gate_sees_a_new_reader(tmp_path, monkeypatch):
    tree = ast.parse('def peek(node):\n    return node.get("units")\n')
    assert _reads_units(tree.body[0])
    assert not _reads_units(ast.parse('def peek(node):\n    return {"units": node}\n').body[0])  # a literal key
