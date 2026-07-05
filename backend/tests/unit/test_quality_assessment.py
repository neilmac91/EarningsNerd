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


def test_million_scale_decimals_are_grounded():
    """Million-scale figures with decimals (e.g. $120.5M) must match (parity with eval harness)."""
    xbrl = {
        "revenue": {"current": {"value": 120_500_000.0}},
        "net_income": {"current": {"value": 12_250_000.0}},
    }
    summary = {
        "business_overview": "Revenue was $120.5 million and net income was $12.25 million.",
        "financial_highlights": {"revenue": "$120.5M", "net_income": "$12.25M"},
        "risk_factors": [{"text": "Customer concentration remains a material risk to results."}],
        "management_discussion": "Management noted steady margin improvement through the period.",
        "key_changes": "The company initiated a modest share-repurchase program this year.",
    }
    verdict = assess_quality(summary, xbrl)
    assert verdict["numeric_grounded"] is True
    assert verdict["tier"] == "full"


# --- S1 decision #2: the 9-section taxonomy verdict is FLAG-GATED + pinned to a fixed literal bar --

_STRUCTURED_SECTIONS = (
    "executive_snapshot", "financial_highlights", "risk_factors",
    "management_discussion_insights", "segment_performance",
    "liquidity_capital_structure", "guidance_outlook", "notable_footnotes", "three_year_trend",
)


def _snapshot_payload(covered_names, *, extra_covered=None):
    """A payload whose raw_summary.section_coverage carries a 9-section per_section map (+ optional
    stray keys), mirroring what openai_service attaches. business_overview is substantive so the
    legacy 7-section fallback still resolves — isolating the taxonomy switch to the flag."""
    per_section = {s: (s in covered_names) for s in _STRUCTURED_SECTIONS}
    for k in (extra_covered or []):
        per_section[k] = True
    return {
        "business_overview": "A detailed multi-paragraph overview of the business and its annual results this period.",
        "financial_highlights": {"revenue": "$1B"},
        "raw_summary": {"section_coverage": {"per_section": per_section}},
    }


def test_flag_on_verdicts_on_fixed_9_section_taxonomy_at_4(monkeypatch):
    """Flag ON: verdict on the FIXED 9-section taxonomy at a literal 4/9 bar. >=4 covered -> full,
    <4 -> partial, and a stray extra covered key can't move the bar (total is pinned to the 9
    _TRACKED_STRUCTURED_SECTIONS, never the payload's floating total_count)."""
    from app.services import summary_generation_service as svc
    monkeypatch.setattr(svc.settings, "USE_PIPELINE_FOR_BACKGROUND", True)

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:4]), None)
    assert v["tier"] == "full" and (v["covered_count"], v["total_count"]) == (4, 9)

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:3]), None)
    assert v["tier"] == "partial" and (v["covered_count"], v["total_count"]) == (3, 9)

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:3], extra_covered=["hallucinated"]), None)
    assert (v["covered_count"], v["total_count"]) == (3, 9)  # stray key ignored


def test_flag_off_ignores_snapshot_uses_legacy_7_section(monkeypatch):
    """Flag OFF (current production): the 9-snapshot branch is inert — assess_quality verdicts on the
    legacy 7 HIDEABLE_SECTIONS, so the user-facing SSE verdict is unchanged until the soak flips the
    flag. total_count == 7 proves the snapshot was ignored."""
    from app.services import summary_generation_service as svc
    monkeypatch.setattr(svc.settings, "USE_PIPELINE_FOR_BACKGROUND", False)

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:4]), None)
    assert v["total_count"] == 7
