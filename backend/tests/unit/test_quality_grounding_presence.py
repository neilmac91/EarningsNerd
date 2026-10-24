"""A complete-looking summary cannot compensate for absent filing evidence."""
import ast
import inspect
import re
import textwrap
from pathlib import Path

import pytest

from app.config import settings
from app.services.summary_generation_service import assess_quality

REASON = "filing grounding unavailable: no usable excerpt or numeric XBRL data"
SUMMARY = {
    "business_overview": "The company describes its products and customers in the annual filing.",
    "financial_highlights": {"cash": "Cash resources support operations through the period."},
    "risk_factors": [{"text": "Customer concentration remains a material risk to operating results."}],
    "management_discussion": "Management describes demand and expense trends during the reporting year.",
}


@pytest.mark.parametrize("excerpt,xbrl", [
    (None, None), ("", {}), (" \n\t", {"reporting_currency": "USD", "fiscal_year": 2025}),
    ("<html><body>Raw filing content</body></html>"[:15000], {}),
    ("<div> </div>", None), ("<!DOCTYPE html>", None),
    ("<!-- metadata only -->", None), ("<?xml version='1.0'?>", None),
    (None, {"cash": {"current": {"value": True}}}),
    (None, {"cash": {"current": {"value": float("inf")}}}),
    (None, {"cash": {"series": [{"value": float("nan")} ]}}),
])
def test_absent_grounding_is_hard_partial_even_with_full_coverage(monkeypatch, excerpt, xbrl):
    monkeypatch.setattr(settings, "AI_FIGURE_TRACE_GATE", False)
    monkeypatch.setattr(settings, "AI_QUALITY_GATE", False)
    result = assess_quality(SUMMARY, xbrl, excerpt=excerpt)
    assert result["covered_count"] >= 3
    assert result["tier"] == "partial" and result["numeric_grounded"] is False
    assert result["reasons"] == [REASON]
    assert result["machine_sections_only"] is False


@pytest.mark.parametrize("excerpt,xbrl", [
    ("EXCERPT", None), ("Costs were lower than revenue < prior guidance.", {}),
    (None, {"cash": {"current": {"value": 0}}}),
    (" ", {"cash": {"prior": {"value": 100}}}),
    (None, {"cash": {"series": [{"value": -100}]}}),
])
def test_either_actual_excerpt_or_numeric_xbrl_independently_preserves_full(excerpt, xbrl):
    result = assess_quality(SUMMARY, xbrl, excerpt=excerpt)
    assert result["tier"] == "full" and result["numeric_grounded"] is True
    assert result["reasons"] == []


@pytest.mark.parametrize("xbrl,expected_tier", [({"cash": {"current": {"value": 100}}}, "full"), (None, "partial")])
def test_trace_source_corroborates_figures_without_attesting_excerpt_presence(monkeypatch, xbrl, expected_tier):
    monkeypatch.setattr(settings, "AI_FIGURE_TRACE_GATE", True)
    summary = {**SUMMARY, "raw_summary": {"sections": {"the_print": {"headline": "Capital expenditure totaled $2.2B."}}}}
    result = assess_quality(summary, xbrl, excerpt=None,
                            trace_excerpt="The filing reports capital expenditure of $2.2 billion.")
    assert result["figures_untraceable"] == []
    assert result["tier"] == expected_tier
    assert (REASON in result["reasons"]) == (xbrl is None)


def test_the_page_badge_keys_on_the_reasons_this_writes(monkeypatch):
    # SummaryDisplay.tsx gives each grounding reason the page's own words by its exact string. Reworded here alone,
    # the badge would show the server's text, "XBRL" included, where D-058 keeps acronyms out of labels.
    monkeypatch.setattr(settings, "AI_FIGURE_TRACE_GATE", False)
    display = (Path(__file__).resolve().parents[3] / "frontend/features/summaries/components/SummaryDisplay.tsx").read_text()
    keys = dict(re.findall(r"const (GROUNDING_REASON|NO_GROUNDING_REASON) = '([^']*)'", display))
    unavailable = assess_quality(SUMMARY, None, excerpt=None)["reasons"]
    ungrounded = assess_quality(SUMMARY, {"revenue": {"current": {"value": 391_035e6}}}, excerpt="Revenue grew.")["reasons"]
    assert keys["NO_GROUNDING_REASON"] in unavailable
    assert keys["GROUNDING_REASON"] in ungrounded


# Every reason the quality check writes, as written. The page's partial badge shows the first, on one line that does
# not wrap, and frontend/tests/unit/summary-quality-badge.spec.tsx counts each, as a first reason, against the
# characters measured to fit a phone: a new or reworded reason is counted there first, and given the badge's own words
# (SummaryDisplay BADGE_WORDS) if it is long.
BADGE_MEASURED_REASONS = {
    "filing grounding unavailable: no usable excerpt or numeric XBRL data",
    "financial figures not grounded in SEC XBRL data",
    "only {}/{} sections populated",
    "{} summary figure(s) not traceable to filing data",
}


def _template(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value if isinstance(part, ast.Constant) else "{}" for part in node.values)
    return ast.unparse(node)


def _written_reasons(tree: ast.AST) -> set[str]:
    """Every reason a function writes into its ``reasons`` list, in each way it may write one: a call on the list (an
    ``append`` or an ``insert`` takes its last argument, an ``extend`` each item it is handed), an augmented
    assignment (``+=``), an assignment to the list or a slice of it, a sum that holds the list on either side, however
    deep (``[...] + reasons``, ``reasons + extra + [...]``), or what a dict holds under ``"reasons"``. The list is the
    name ``reasons`` or a value's ``"reasons"`` entry (``result["reasons"].append(...)``). A value that is not a
    string or a template is kept as its source, which no measured reason equals."""

    def is_reasons(node: ast.expr) -> bool:
        if isinstance(node, ast.Subscript):
            return is_reasons(node.value) or (isinstance(node.slice, ast.Constant) and node.slice.value == "reasons")
        return isinstance(node, ast.Name) and node.id == "reasons"

    def holds_reasons(node: ast.expr) -> bool:
        return is_reasons(node) or (
            isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and (holds_reasons(node.left) or holds_reasons(node.right))
        )

    def items(node: ast.expr) -> list[str]:
        if isinstance(node, (ast.List, ast.Tuple)):
            return [_template(element) for element in node.elts]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return items(node.left) + items(node.right)
        return [] if is_reasons(node) else [ast.unparse(node)]

    written: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and is_reasons(node.func.value) and node.args:
            written.update([_template(node.args[-1])] if node.func.attr in {"append", "insert"} else items(node.args[-1]))
        elif isinstance(node, ast.AugAssign) and is_reasons(node.target):
            written.update(items(node.value))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and holds_reasons(node):
            written.update(items(node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(is_reasons(target) for target in targets):
                written.update(items(node.value))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "reasons":
                    written.update(items(value))
    return written


def test_the_reason_reader_reads_every_way_a_reason_is_written():
    planted = "\n".join([
        "reasons: list[str] = ['h']",
        "reasons.append('a')",
        "reasons += ['b', f'c {n}']",
        "reasons.extend(('d',))",
        "reasons.insert(0, 'e')",
        "reasons[:0] = ['f']",
        "reasons = reasons + ['g']",
        "reasons.append(words[n])",
        "combined = reasons + ['i']",
        "combined = ['j'] + reasons",
        "combined = reasons + ['m'] + ['n']",
        "result = {'reasons': ['k'], 'tier': 'partial'}",
        "result['reasons'].append('l')",
        "other.append('not a reason')",
        "result = {'notes': ['not a reason either']}",
    ])
    assert _written_reasons(ast.parse(planted)) == {
        "a", "b", "c {}", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "words[n]",
    }


def test_each_reason_the_badge_may_show_is_one_its_spec_measures():
    written = _written_reasons(ast.parse(textwrap.dedent(inspect.getsource(assess_quality))))
    assert written == BADGE_MEASURED_REASONS
    spec = (Path(__file__).resolve().parents[3] / "frontend/tests/unit/summary-quality-badge.spec.tsx").read_text()
    counted = re.search(r"const firsts = \[\n(.*?)\n\s*\]\n", spec, re.S)
    assert counted, "the badge spec lists the reasons it counts in `firsts`"
    # The badge shows a list's first reason, so each counted reason is the first string of an entry.
    firsts = re.findall(r"^\s*\['([^']*)'", counted.group(1), re.M)
    for reason in BADGE_MEASURED_REASONS:
        shape = re.escape(reason).replace(re.escape("{}"), r"\d+")
        assert any(re.fullmatch(shape, first) for first in firsts), f"the badge spec counts {reason!r} as a first reason"

