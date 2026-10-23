"""A complete-looking summary cannot compensate for absent filing evidence."""
import re
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
