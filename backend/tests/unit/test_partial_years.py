"""A quarterly report's year that holds only part of one never reaches a reader (E291, ``facts/fiscal_naming.py``).

CBAN's and FIX's Q1 2026 10-Qs tag their Q1 2025 comparatives with the full-year span 2025-01-01..2025-12-31, and,
filed after the 10-Ks, won FY2025 wherever the latest filed item wins. ``without_partial_years`` drops such an item
for every reader of companyfacts duration items: the collector's admission (``currency.admitted_items``), the
backfill cross-check's authority (``reconcile.extract_authoritative_values``), the per-filing fallback
(``edgar/xbrl_companyfacts.py``) and the restatement census's evidence index; the gate below pins every reader. The
fixtures are trimmed from SEC's payloads (CBAN's of 2026-11-02, FIX's of
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


@pytest.mark.parametrize("form", ["10-K", "8-K"])
def test_a_part_from_any_filing_marks_the_year(form):
    # RNGR's FY2017 profit in a 10-Q equals its first quarter as a 10-K reports it: a part counts from any filing.
    quarter = _item("2025-01-01", "2025-03-31", 20952000, form=form, accn="annual")
    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    assert without_partial_years([quarter, year]) == [quarter]


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


def test_the_restatement_census_indexes_no_partial_year():
    from scripts.restatement_census import _accession_index  # its evidence reads items as the collector does

    year = _item("2025-01-01", "2025-12-31", 20952000, accn="q1-2026")
    usgaap = {"InterestIncomeExpenseNet": {"units": {"USD": [QUARTER, ANNUAL, year]}}}
    assert dict(_accession_index(usgaap, {"q1-2026", "10k-2025"})) == {
        "10k-2025": [("InterestIncomeExpenseNet", "USD", "2025-01-01", "2025-12-31", 91901000)]}


# --- the gate (CLAUDE.md rule 12): every companyfacts reader goes through the rule ------------------------------------
#
# Every read of a ``units`` map in backend/app and backend/scripts (``x["units"]``, ``x.get``, ``setdefault`` or
# ``pop`` of "units", the same through a module constant equal to "units", or a ``case {"units": ...}`` pattern) is
# counted per scope: Class.method, outer.inner, or <module> for module-level code and its lambdas. READERS pins each
# scope's count and the shape of its code:
# - "rule": the scope calls admitted_items or without_partial_years;
# - "proxy": the scope calls is_proxy_form, so the values it reads are proxy statements', never a quarterly report's;
# - "no value": the scope reads no item's "val", and one that yields items hands them only to callers in its own
#   module that read none either, with no other module importing it.
# A new scope, a new read in a pinned scope, or a pinned scope that loses its shape fails. Named blind spots: a key
# held in a parameter or built at run time (``node.get(key)``); a read swapped for another in a pinned scope, which
# keeps its count; a pinned "rule" scope that passes instant=True for a duration list, or reads one list raw beside
# the one it rules. The collector, authority and fallback tests above hold the three readers that choose a winner.

RULE = {"admitted_items", "without_partial_years"}
READERS = {  # (path, scope): (reads, shape)
    ("app/services/edgar/instance/financial_revenue.py", "_choose"): (1, "no value"),
    ("app/services/edgar/xbrl_companyfacts.py", "select_fact_data_with_concept"): (2, "rule"),
    ("app/services/facts/companyfacts.py", "_collect_companyfacts_values"): (1, "rule"),
    ("app/services/facts/currency.py", "_filing_pick"): (1, "rule"),
    ("app/services/facts/currency.py", "payload_view"): (2, "no value"),  # each filing's accession and filed date
    ("app/services/facts/fi_revenue.py", "_by_filing"): (1, "rule"),
    ("app/services/facts/fi_revenue.py", "_items"): (1, "rule"),
    ("app/services/facts/reconcile.py", "extract_authoritative_values"): (1, "rule"),
    ("app/services/facts/reporting_basis.py", "_items"): (1, "no value"),  # its callers count items by form
    ("app/services/proxy_fact_repair.py", "proxy_items"): (1, "proxy"),
    ("scripts/financial_revenue_preview.py", "deployed_rule"): (1, "rule"),
    ("scripts/native_delivery_probe.py", "plan"): (1, "no value"),  # an eval unit manifest's units
    ("scripts/native_delivery_probe.py", "run"): (1, "no value"),
    ("scripts/restatement_census.py", "_accession_index"): (1, "rule"),
}


class _Reads(ast.NodeVisitor):
    """One module's reads of a ``units`` map per scope, each scope's node, and each named call's scope."""

    def __init__(self, tree: ast.Module):
        self.constants = {target.id for node in tree.body if isinstance(node, ast.Assign)
                          and isinstance(node.value, ast.Constant) and node.value.value == "units"
                          for target in node.targets if isinstance(target, ast.Name)}
        self.stack: list[str] = []
        self.reads: dict[str, int] = {}
        self.scopes: dict[str, ast.AST] = {"<module>": tree}
        self.calls: list[tuple[str, str]] = []
        self.visit(tree)

    def _here(self) -> str:
        return ".".join(self.stack) or "<module>"

    def _units(self, node) -> bool:
        return (isinstance(node, ast.Constant) and node.value == "units") or (
            isinstance(node, ast.Name) and node.id in self.constants)

    def _scope(self, node):
        self.stack.append(node.name)
        self.scopes.setdefault(self._here(), node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scope

    def _read(self):
        self.reads[self._here()] = self.reads.get(self._here(), 0) + 1

    def visit_Subscript(self, node):
        if isinstance(node.ctx, ast.Load) and self._units(node.slice):
            self._read()
        self.generic_visit(node)

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Attribute) and node.func.attr in ("get", "setdefault", "pop") and node.args
                and self._units(node.args[0])):
            self._read()
        if isinstance(node.func, ast.Name):
            self.calls.append((node.func.id, self._here()))
        self.generic_visit(node)

    def visit_MatchMapping(self, node):
        if any(self._units(key) for key in node.keys):
            self._read()
        self.generic_visit(node)


def _own(scope: ast.AST):
    """A scope's own nodes: its nested functions and classes are scopes of their own, its lambdas are not."""
    todo = list(ast.iter_child_nodes(scope))
    while todo:
        node = todo.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            todo.extend(ast.iter_child_nodes(node))


def _calls(scope: ast.AST, names: set[str]) -> bool:
    return any(isinstance(node, ast.Call) and (getattr(node.func, "id", None) in names
                                               or getattr(node.func, "attr", None) in names) for node in _own(scope))


def _reads_value(scope: ast.AST) -> bool:
    def val(key):
        return isinstance(key, ast.Constant) and key.value == "val"
    return any((isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and val(node.slice))
               or (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in ("get", "pop") and node.args and val(node.args[0])) for node in _own(scope))


def _scan(root: Path, dirs: tuple[str, ...]) -> dict[tuple[str, str], tuple[int, str]]:
    """{(path, scope): (reads, shape)} over the .py files under ``dirs``: the shape is "raw" where none applies."""
    modules = {path: ast.parse(path.read_text()) for name in dirs for path in sorted((root / name).rglob("*.py"))}
    found = {}
    for path, tree in modules.items():
        reads, module = _Reads(tree), ".".join(path.relative_to(root).with_suffix("").parts)
        for scope, count in reads.reads.items():
            node, shape = reads.scopes[scope], "no value"
            if _calls(node, RULE):
                shape = "rule"
            elif _calls(node, {"is_proxy_form"}):
                shape = "proxy"
            elif _reads_value(node):
                shape = "raw"
            elif any(isinstance(sub, (ast.Yield, ast.YieldFrom)) for sub in _own(node)):
                name = scope.rsplit(".", 1)[-1]
                callers = [reads.scopes[caller] for callee, caller in reads.calls if callee == name]
                imported = any(isinstance(sub, ast.ImportFrom) and sub.module == module
                               and any(alias.name == name for alias in sub.names)
                               for other in modules.values() if other is not tree for sub in ast.walk(other))
                if imported or any(_reads_value(caller) for caller in callers):
                    shape = "raw"
            found[(str(path.relative_to(root)), scope)] = (count, shape)
    return found


def test_every_companyfacts_reader_is_pinned_with_its_shape():
    found = _scan(BACKEND, ("app", "scripts"))
    drift = {key: (found.get(key), READERS.get(key)) for key in found.keys() | READERS.keys()
             if found.get(key) != READERS.get(key)}
    assert not drift, f"route each companyfacts read through admitted_items or without_partial_years, then pin it " \
                      f"in READERS ((found, pinned) per scope): {drift}"


PLANTED = """
UNITS = "units"


def mixed(node_a, node_b):  # a rule call beside a raw read
    admitted_items(node_a["units"]["USD"], instant=False)
    return max(node_b["units"]["USD"], key=len)


class Annual:  # two methods of one name
    def values(self, node):
        return node["units"]["USD"][0]["val"]


class Quarterly:
    def values(self, node):
        return without_partial_years(node["units"]["USD"])


def by_constant(node):
    return node[UNITS]["USD"][0]["val"]


def popped(node):
    return node.pop("units")["USD"][0].get("val")


def matched(node):
    match node:
        case {"units": {"USD": items}}:
            return items[0]["val"]


peek = lambda node: node.get("units")["USD"][0]["val"]


def _every(node):  # an iterator that reads no value itself
    yield from node["units"]["USD"]


def picks(node):  # but whose caller does
    return max(_every(node), key=lambda item: item["filed"])["val"]


def counts(node):
    return sum(1 for item in _every(node) if item.get("form") == "10-K")


def by_parameter(node, key):  # a named blind spot: the key held in a parameter
    return node.get(key)["USD"][0]["val"]
"""


def test_the_gate_reads_each_planted_reader(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "planted.py").write_text(PLANTED)
    found = {scope: shape for (_path, scope), shape in _scan(tmp_path, ("scripts",)).items()}
    assert found == {"mixed": (2, "rule"), "Annual.values": (1, "raw"), "Quarterly.values": (1, "rule"),
                     "by_constant": (1, "raw"), "popped": (1, "raw"), "matched": (1, "raw"), "<module>": (1, "raw"),
                     "_every": (1, "raw")}  # "mixed" is pinned nowhere; pinned at one read, its second fails
    (tmp_path / "scripts" / "planted.py").write_text(PLANTED.replace("    return max(_every(node), key=lambda item: "
                                                                     "item[\"filed\"])[\"val\"]\n", "    pass\n"))
    assert _scan(tmp_path, ("scripts",))[("scripts/planted.py", "_every")] == (1, "no value")


def test_a_yielding_reader_imported_elsewhere_is_raw(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "lister.py").write_text("def _every(node):\n    yield from node[\"units\"][\"USD\"]\n")
    (tmp_path / "scripts" / "user.py").write_text("from scripts.lister import _every\n")
    assert _scan(tmp_path, ("scripts",)) == {("scripts/lister.py", "_every"): (1, "raw")}
