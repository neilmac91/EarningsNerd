"""Tests for the semantic quality verdict (roadmap S4)."""
from app.services.summary_generation_service import assess_quality

_XBRL = {
    "revenue": {"current": {"value": 383_285_000_000.0}},
    "net_income": {"current": {"value": 96_995_000_000.0}},
}


def _full_summary(business_overview: str):
    return {
        "business_overview": business_overview,
        "financial_highlights": {"revenue": "$383.3B", "net_income": "$96.995B"},
        "risk_factors": [{"text": "Concentration in iPhone revenue is a material risk to results."}],
        "management_discussion": "Management cited gross-margin expansion and disciplined opex control across the year.",
        "key_changes": "Capital returns continued via buybacks and a raised dividend this fiscal year.",
    }


def test_full_when_covered_and_grounded():
    summary = _full_summary("Apple reported revenue of $383.3 billion and net income of $96.995 billion.")
    verdict = assess_quality(summary, _XBRL)
    assert verdict["tier"] == "full"
    assert verdict["numeric_grounded"] is True
    assert verdict["reasons"] == []


def test_partial_when_financials_not_grounded():
    # Well-covered prose, but neither the text nor the highlights match the XBRL ground truth.
    summary = {
        "business_overview": "Apple reported solid revenue of $999.9 billion and strong profit growth.",
        "financial_highlights": {"revenue": "$999.9B", "net_income": "$500.0B"},
        "risk_factors": [{"text": "Concentration in iPhone revenue is a material risk to results."}],
        "management_discussion": "Management cited gross-margin expansion and disciplined opex control across the year.",
        "key_changes": "Capital returns continued via buybacks and a raised dividend this fiscal year.",
    }
    verdict = assess_quality(summary, _XBRL)
    assert verdict["tier"] == "partial"
    assert verdict["numeric_grounded"] is False
    assert any("XBRL" in r for r in verdict["reasons"])


def test_partial_when_thin_coverage():
    summary = {
        "business_overview": "A reasonably detailed overview of the company and its results this period.",
        "financial_highlights": {"revenue": "Not disclosed"},
        "risk_factors": [],
        "management_discussion": "n/a",
        "key_changes": "",
    }
    verdict = assess_quality(summary, None)
    assert verdict["tier"] == "partial"
    assert any("sections populated" in r for r in verdict["reasons"])


def test_no_xbrl_does_not_force_partial_on_grounding():
    summary = _full_summary("A detailed multi-section overview of the business and its annual results.")
    verdict = assess_quality(summary, None)
    assert verdict["numeric_grounded"] is True  # nothing to contradict
    assert verdict["tier"] == "full"
