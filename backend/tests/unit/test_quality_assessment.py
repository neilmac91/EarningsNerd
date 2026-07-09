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


def test_verdicts_on_fixed_9_section_taxonomy_at_4():
    """Verdict on the FIXED 9-section taxonomy at a literal 4/9 bar (a payload carrying a per_section
    snapshot). >=4 covered -> full, <4 -> partial, and a stray extra covered key can't move the bar
    (total is pinned to the 9 _TRACKED_STRUCTURED_SECTIONS, never the payload's floating
    total_count). When no per_section snapshot is present, assess_quality falls back to the legacy 7
    HIDEABLE_SECTIONS at 3/7 (covered by the tests above)."""
    from app.services import summary_generation_service as svc

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:4]), None)
    assert v["tier"] == "full" and (v["covered_count"], v["total_count"]) == (4, 9)

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:3]), None)
    assert v["tier"] == "partial" and (v["covered_count"], v["total_count"]) == (3, 9)

    v = svc.assess_quality(_snapshot_payload(_STRUCTURED_SECTIONS[:3], extra_covered=["hallucinated"]), None)
    assert (v["covered_count"], v["total_count"]) == (3, 9)  # stray key ignored


# --- T3.2 number-diff / figure-trace gate ---------------------------------------------------------

def _v2_summary_with_fabricated_figure():
    """A well-covered, grounded v2 summary whose PROSE cites a phantom $404.0B not in XBRL/excerpt."""
    return {
        "business_overview": "Apple reported revenue of $383.3 billion and net income of $96.995 billion.",
        "financial_highlights": {"revenue": "$383.3B"},
        "raw_summary": {
            "schema_version": 2,
            "sections": {
                "the_print": {"headline": "Revenue of $383.3B.",
                              "key_takeaways": ["A phantom $404.0B reserve was cited."]},
                "results_that_matter": {"table": [{"metric": "Revenue", "current_period": "$383.3B"}]},
                "earnings_quality": {"operating_vs_one_time": "Earnings quality held."},
                "forward_signals": {"guidance": "Guided higher."},
            },
            "section_coverage": {"per_section": {
                "the_print": True, "results_that_matter": True,
                "earnings_quality": True, "forward_signals": True}},
        },
    }


def test_untraceable_figures_attached_but_advisory_by_default():
    """Flag OFF (default): the untraceable figure is attached for measurement but does NOT downgrade
    the tier or add a user-facing reason — the summary is otherwise full + grounded."""
    verdict = assess_quality(_v2_summary_with_fabricated_figure(), _XBRL)
    assert verdict["figures_untraceable"] == ["404b"]
    assert verdict["tier"] == "full"
    assert not any("traceable" in r for r in verdict["reasons"])


def test_figure_trace_gate_downgrades_when_flag_on(monkeypatch):
    """Flag ON: the same untraceable figure tiers the summary partial with a reason."""
    from app.config import settings

    monkeypatch.setattr(settings, "AI_FIGURE_TRACE_GATE", True)
    verdict = assess_quality(_v2_summary_with_fabricated_figure(), _XBRL)
    assert verdict["tier"] == "partial"
    assert verdict["figures_untraceable"] == ["404b"]
    assert any("not traceable to filing data" in r for r in verdict["reasons"])


def test_clean_v2_summary_has_no_untraceable_figures(monkeypatch):
    """A grounded v2 summary whose prose figures all trace stays full with an empty list — even with the
    gate armed ON (monkeypatch, so global settings aren't polluted for later tests)."""
    from app.config import settings

    summary = _v2_summary_with_fabricated_figure()
    # Replace the phantom figure with a grounded one ($383.3B = XBRL revenue).
    summary["raw_summary"]["sections"]["the_print"]["key_takeaways"] = ["Revenue of $383.3B led."]
    monkeypatch.setattr(settings, "AI_FIGURE_TRACE_GATE", True)
    verdict = assess_quality(summary, _XBRL)
    assert verdict["figures_untraceable"] == []
    assert verdict["tier"] == "full"
