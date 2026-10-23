"""Rule-12 gate: both fact writers count fiscal years and trust a report's focus through one module.

The per-filing labeller (``edgar/fiscal_periods``) and the companyfacts writer (``facts/calendar``,
``facts/companyfacts``) give a period one fiscal year only while they count whole years back from an
anchor and trust an annual report's own focus alike (``lessons/sec-fact-writers-name-a-period-alike.md``).
Until 2026-10-23 the per-filing labeller held the only copy of both rules; the companyfacts writer then
needed them too, for a year chain no timely report names and for an opening balance outside every year
window, and both now call ``facts/fiscal_naming`` (``years_back``, ``focus_years``). This fails a second
copy under the two writers' packages, anywhere there but ``fiscal_naming.py``: a ``365.25``-day year, or a
``timedelta`` of 183 days (the midpoint), whether its arguments are literals or names the module binds to
constants, its days are spread over ``weeks``, ``days`` and smaller units, or ``timedelta`` is imported
under another name.

Known limits, each planted below as a gap: a copy written with other constants (``365``, ``182``, ``1461``
days to four years), with ``dateutil``'s ``relativedelta`` or a month comparison (``end.month <= 7``), with
a ``Decimal("365.25")``, or with a ``timedelta`` whose arguments are computed or imported from another
module, and any copy outside ``app/services/facts`` and ``app/services/edgar``, are review-checked; the
both-writers tests in ``test_annual_fact_fiscal_labels.py`` catch a divergence on the issuers they pin.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SERVICES = Path(__file__).resolve().parents[2] / "app" / "services"
HOME = SERVICES / "facts" / "fiscal_naming.py"
WRITER_PACKAGES = (SERVICES / "facts", SERVICES / "edgar")
# timedelta's arguments in positional order, each unit in days.
_UNITS = {"days": 1, "seconds": 1 / 86_400, "microseconds": 1 / 86_400_000_000, "milliseconds": 1 / 86_400_000,
          "minutes": 1 / 1_440, "hours": 1 / 24, "weeks": 7}


def _copies(tree: ast.AST) -> list[int]:
    """Lines that write the whole-year divisor or the 183-day midpoint."""
    bound: dict[str, set] = {}  # every constant a module or function binds to each name
    callees = {"timedelta"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            callees |= {alias.asname for alias in node.names if alias.name == "timedelta" and alias.asname}
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if isinstance(getattr(node, "value", None), ast.Constant):
            for target in targets:
                if isinstance(target, ast.Name):
                    bound.setdefault(target.id, set()).add(node.value.value)

    def numbers(node: ast.AST) -> set:
        found = {node.value} if isinstance(node, ast.Constant) else bound.get(getattr(node, "id", None), set())
        return {value for value in found if type(value) in (int, float)}

    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) is float and node.value == 365.25:
            lines.append(node.lineno)
        elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) in callees:
            given = [*zip(_UNITS, node.args), *((kw.arg, kw.value) for kw in node.keywords)]
            totals = {0.0}
            for unit, value in given:
                if unit not in _UNITS or not (options := numbers(value)):
                    break  # a computed or unknown argument: a stated gap
                totals = {total + option * _UNITS[unit] for total in totals for option in options}
            else:
                if given and any(abs(total - 183) < 1e-9 for total in totals):
                    lines.append(node.lineno)
    return sorted(lines)


def _scanned() -> dict[str, Path]:
    return {
        str(path.relative_to(SERVICES.parents[1])): path
        for package in WRITER_PACKAGES for path in sorted(package.rglob("*.py")) if path != HOME
    }


def test_only_fiscal_naming_counts_fiscal_years_or_trusts_a_focus():
    found = {
        name: lines for name, path in _scanned().items()
        if (lines := _copies(ast.parse(path.read_text(), filename=str(path))))
    }
    assert found == {}, f"count years or trust a focus through app/services/facts/fiscal_naming.py: {found}"


def test_the_scan_reads_both_writers_and_sees_the_home():
    """An empty result above means no copy, not a moved package or a blind scan: the writers' modules are
    all read, and the home itself holds both shapes."""
    assert all(package.is_dir() for package in WRITER_PACKAGES)
    assert {"app/services/facts/calendar.py", "app/services/facts/companyfacts.py",
            "app/services/edgar/fiscal_periods.py", "app/services/edgar/xbrl_instance.py"} <= set(_scanned())
    assert len(_copies(ast.parse(HOME.read_text()))) == 3


# Planted copies and the lines the scan flags: literals, and the binding forms a copy can take.
FLAGGED = {
    "literals": ("from datetime import timedelta\nyears = round(days / 365.25)\nmid = timedelta(183)\n"
                 "also = timedelta(days=183)\n", [2, 3, 4]),
    "module_attribute": ("import datetime\nmid = datetime.timedelta(days=183)\n", [2]),
    "bound_names": ("from datetime import timedelta\n_MIDPOINT_DAYS = 183\n_YEAR: float = 365.25\n"
                    "def mid(end):\n    return end - timedelta(days=_MIDPOINT_DAYS)\n", [3, 5]),
    "aliased_import": ("from datetime import timedelta as td\nmid = td(days=183)\n", [2]),
    "spread_units": ("from datetime import timedelta\na = timedelta(weeks=26, days=1)\n"
                     "b = timedelta(days=182, hours=24)\nc = timedelta(182, 86_400)\n", [2, 3, 4]),
}
# Copies the scan does not see (the header's known limits), kept so a widening is scored against them.
GAPS = {
    "other_constants": "years = round(days / 365)\nmid = timedelta(days=182)\nyears = round(days * 4 / 1461)\n",
    "relativedelta": "from dateutil.relativedelta import relativedelta\nmid = end - relativedelta(months=6)\n",
    "month_comparison": "trusted = (end.year, end.year - 1 if end.month <= 7 else end.year)\n",
    "decimal": "from decimal import Decimal\nyears = round(days / Decimal('365.25'))\n",
    "computed": "from datetime import timedelta\nmid = timedelta(days=366 // 2)\n",
    "imported_constant": "from datetime import timedelta\nfrom x import MIDPOINT_DAYS\nmid = timedelta(days=MIDPOINT_DAYS)\n",
}


@pytest.mark.parametrize("form", sorted(FLAGGED))
def test_the_scan_sees_every_planted_copy(form):
    source, lines = FLAGGED[form]
    assert _copies(ast.parse(source)) == lines


@pytest.mark.parametrize("form", sorted(GAPS))
def test_the_scans_known_gaps_stay_named(form):
    """A widening that closes one of these moves it to FLAGGED and out of the header's known limits."""
    assert _copies(ast.parse(GAPS[form])) == []
