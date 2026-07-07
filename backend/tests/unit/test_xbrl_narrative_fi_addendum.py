"""P0-4(b) guardrail (data-quality plan): the financial-institution prompt addendum.

The industrial checklist (working capital, current ratio, capex-driven FCF) forced fabrication
on banks — the observed failure was a confidently false "FCF negative due to high capex and
working-capital changes" on JPM, whose OCF swing is trading-flow-driven. The addendum swaps the
checklist at the point of grounding, gated on the SAME shared FI predicate as the component
NOTE, and must stay completely dormant for non-FI inputs (whose grounding block is pinned
byte-for-byte elsewhere).
"""
from app.services.ai.xbrl_narrative import build_xbrl_narrative_section


def _fi_metrics():
    return {
        "net_interest_income": {"current": {"value": 95443000000.0, "period": "FY2025"}},
        "noninterest_income": {"current": {"value": 87004000000.0, "period": "FY2025"}},
        "net_income": {"current": {"value": 57048000000.0, "period": "FY2025"}},
    }


def _non_fi_metrics():
    return {
        "revenue": {"current": {"value": 42300000000.0, "period": "FY2025"}},
        "net_income": {"current": {"value": 9000000000.0, "period": "FY2025"}},
    }


def test_fi_inputs_get_the_coverage_addendum():
    block = build_xbrl_narrative_section(_fi_metrics())
    assert "FINANCIAL-INSTITUTION COVERAGE" in block
    assert "NEVER attribute a cash-flow swing to capex or working capital" in block
    assert "provision for credit" in block
    # The component NOTE and the addendum ride together — same predicate, same block.
    assert "NO single revenue line" in block


def test_non_fi_inputs_have_no_addendum_or_note():
    block = build_xbrl_narrative_section(_non_fi_metrics())
    assert "FINANCIAL-INSTITUTION COVERAGE" not in block
    assert "NO single revenue line" not in block
