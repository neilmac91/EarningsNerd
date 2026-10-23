"""Rule-12 gate: both fact writers count fiscal years and trust a report's focus through one module.

The per-filing labeller (``edgar/fiscal_periods``) and the companyfacts writer (``facts/calendar``,
``facts/companyfacts``) give a period one fiscal year only while they count whole years back from an
anchor and trust an annual report's own focus alike (``lessons/sec-fact-writers-name-a-period-alike.md``).
Until 2026-10-23 the per-filing labeller held the only copy of both rules; the companyfacts writer then
needed them too, for a year chain no timely report names and for an opening balance outside every year
window, and both now call ``facts/fiscal_naming`` (``years_back``, ``focus_years``). This fails a second
copy under the two writers' packages: a ``365.25``-day year, or a ``timedelta`` of 183 days (the
midpoint), anywhere there but ``fiscal_naming.py``.

Known limits: a copy written with other constants (``365``, ``182``), or outside ``app/services/facts``
and ``app/services/edgar``, is review-checked; the both-writers tests in
``test_annual_fact_fiscal_labels.py`` catch a divergence on the issuers they pin.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SERVICES = Path(__file__).resolve().parents[2] / "app" / "services"
HOME = SERVICES / "facts" / "fiscal_naming.py"
WRITER_PACKAGES = (SERVICES / "facts", SERVICES / "edgar")


def _copies(tree: ast.AST) -> list[int]:
    """Lines that write the whole-year divisor or the 183-day midpoint."""
    lines = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) is float and node.value == 365.25:
            lines.append(node.lineno)
        elif isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None)) == "timedelta":
            days = [kw.value for kw in node.keywords if kw.arg == "days"] + node.args[:1]
            if any(isinstance(value, ast.Constant) and value.value == 183 for value in days):
                lines.append(node.lineno)
    return sorted(lines)


def test_only_fiscal_naming_counts_fiscal_years_or_trusts_a_focus():
    found = {
        str(path.relative_to(SERVICES.parents[1])): lines
        for package in WRITER_PACKAGES for path in sorted(package.rglob("*.py"))
        if path != HOME and (lines := _copies(ast.parse(path.read_text(), filename=str(path))))
    }
    assert found == {}, f"count years or trust a focus through app/services/facts/fiscal_naming.py: {found}"


def test_the_scan_sees_both_shapes():
    """An empty result above means no copy, not a blind scan: the home itself holds both shapes."""
    assert len(_copies(ast.parse(HOME.read_text()))) == 3
    source = "from datetime import timedelta\nyears = round(days / 365.25)\nmid = timedelta(183)\nalso = timedelta(days=183)\n"
    assert _copies(ast.parse(source)) == [2, 3, 4]
