"""PR A (Tier-3.1) — the v2 SummaryDoc schema + render + badge dispatch, tested DARK.

Generation still emits v1; these tests exercise the v2 machinery against synthetic v2 payloads so
the cutover (PR B) lands on proven render + badge code. No live model, no eval.
"""
from __future__ import annotations

import pytest

from app.services import summary_sections
from app.services.summary_generation_service import (
    _tracked_sections_for,
    _verdict_coverage,
)
from app.services.summary_schema import (
    SECTION_META,
    TRACKED_SECTIONS_V1,
    TRACKED_SECTIONS_V2,
    SummaryDoc,
)

# A realistic, fully-populated v2 payload (matches the SummaryDoc shapes).
V2_SECTIONS = {
    "the_print": {
        "headline": "Revenue rose 14% to $42.3B on datacenter demand.",
        "key_takeaways": ["Datacenter revenue doubled YoY", "Gross margin widened to 75%"],
        "what_changed": "Guidance raised for the first time in three quarters.",
        "tone": "positive",
        "source_section_ref": "Item 2. MD&A",
    },
    "results_that_matter": {
        "table": [
            {"metric": "Revenue", "current_period": "$42.3B", "prior_period": "$37.1B",
             "change": "+14%", "commentary": "Datacenter demand"},
            {"metric": "Operating margin", "current_period": "32.5%", "prior_period": "28.1%",
             "change": "+4.4 ppts", "commentary": "Operating leverage"},
        ],
        "source_section_ref": "Item 1. Financial Statements",
    },
    "earnings_quality": {
        "operating_vs_one_time": "Reported net income of $16.6B includes $2.1B unrealized equity "
                                 "gains; operating income was $12.4B.",
        "cash_conversion": "Operating cash flow of $14.1B exceeded net income; FCF was $11.2B.",
        "red_flags": ["Receivables grew 22% vs 14% revenue growth",
                      "Unrealized gains were 13% of pretax income"],
        "source_section_ref": "Item 8",
    },
    "value_drivers": {
        "capital_allocation": "Repurchased $9.3B of stock and paid $1.0B dividends; capex up 12%.",
        "returns_on_capital": "ROIC of 34%, up from 29% a year ago.",
        "highlights": ["$9.3B buybacks", "$1.0B dividends"],
        "source_section_ref": "Item 7",
    },
    "forward_signals": {
        "guidance": "Management raised FY revenue guidance to $175-180B.",
        "known_trends": ["Datacenter backlog extends into 2027"],
        "subsequent_events": ["Announced a $2B acquisition after quarter-end"],
        "quotes": [{"speaker": "CEO", "quote": "Demand visibility extends well into next year.",
                    "context": "MD&A"}],
        "tone": "positive",
        "source_section_ref": "Item 2. MD&A",
    },
    "risks": [
        {"summary": "Customer concentration: top 2 customers are 39% of revenue",
         "supporting_evidence": "Two customers accounted for 39% of total revenue",
         "materiality": "high", "source_section_ref": "Item 1A"},
    ],
    "segments": [
        {"segment": "Datacenter", "revenue": "$30.8B", "operating_income": "$18.2B",
         "change": "+112%", "commentary": "AI demand", "source_section_ref": "Note 13"},
        {"segment": "Gaming", "revenue": "$8.1B", "operating_income": "$3.1B",
         "change": "-4%", "commentary": "Channel normalization", "source_section_ref": "Note 13"},
    ],
    "balance_sheet_liquidity": {
        "leverage": "Total debt $11.0B against $34B cash; net cash position.",
        "liquidity": "Total liquidity $34B; ample runway.",
        "working_capital": "Current ratio 3.4x, up from 3.1x.",
        "maturities_covenants": ["No maturities before 2028", "No covenants on the revolver"],
        "source_section_ref": "Item 8",
    },
    "notable_footnotes": [
        {"item": "SBC (Note 4)", "impact": "Stock-based comp of $3.5B, 8% of revenue",
         "source_section_ref": "Note 4"},
    ],
}


def _raw_v2(sections=None, schema_version=2):
    return {"sections": sections if sections is not None else V2_SECTIONS,
            "schema_version": schema_version}


def _by_title(sections):
    return {s.title: s for s in sections}


# --- SummaryDoc schema -------------------------------------------------------------------------

def test_summarydoc_validates_full_v2_payload():
    doc = SummaryDoc.model_validate({"metadata": {"company_name": "NVIDIA", "filing_type": "10-Q"},
                                     "sections": V2_SECTIONS})
    assert doc.sections.the_print.headline.startswith("Revenue rose")
    assert len(doc.sections.results_that_matter.table) == 2
    assert doc.sections.earnings_quality.red_flags[0].startswith("Receivables")
    assert doc.sections.segments[0].operating_income == "$18.2B"
    assert doc.sections.forward_signals.quotes[0].speaker == "CEO"


def test_summarydoc_is_lenient_missing_sections_and_extra_keys():
    # A 6-K may carry only §1 + §5; extra/unknown keys are ignored, not an error.
    doc = SummaryDoc.model_validate({
        "sections": {"the_print": {"headline": "Interim update."},
                     "forward_signals": {"guidance": "Reaffirmed FY targets."},
                     "some_future_section": {"x": 1}},
    })
    assert doc.sections.the_print.headline == "Interim update."
    assert doc.sections.results_that_matter is None
    assert doc.sections.risks == []
    assert not hasattr(doc.sections, "some_future_section")


def test_summarydoc_rejects_wrong_type():
    with pytest.raises(Exception):
        SummaryDoc.model_validate({"sections": {"the_print": ["not", "an", "object"]}})


def test_summarydoc_list_sections_coerce_null_to_empty():
    # A model rendering "no items" as null is "missing", not a wrong type — validate to [] rather
    # than raising (which in PR B would spuriously route a good payload into json-repair).
    doc = SummaryDoc.model_validate(
        {"sections": {"risks": None, "segments": None, "notable_footnotes": None}}
    )
    assert doc.sections.risks == []
    assert doc.sections.segments == []
    assert doc.sections.notable_footnotes == []
    # A genuinely wrong type still rejects.
    with pytest.raises(Exception):
        SummaryDoc.model_validate({"sections": {"risks": "a string"}})


def test_tracked_sections_v2_matches_meta_and_field_names():
    assert set(TRACKED_SECTIONS_V2) == set(SECTION_META)
    assert set(TRACKED_SECTIONS_V2) == set(SummaryDoc().sections.model_dump().keys())
    assert len(TRACKED_SECTIONS_V2) == 9


# --- render dispatch ---------------------------------------------------------------------------

def test_builders_for_dispatches_on_schema_version():
    assert summary_sections._builders_for(2) is summary_sections._BUILDERS_V2
    for v1_like in (1, None, "1", 3, "nonsense"):
        assert summary_sections._builders_for(v1_like) is summary_sections._BUILDERS


def test_render_sections_v2_produces_all_nine_in_order():
    rendered = summary_sections.render_sections(_raw_v2())
    titles = [s.title for s in rendered]
    assert titles == [SECTION_META[k]["title"] for k in TRACKED_SECTIONS_V2]
    # ids are stable slugs for the TOC
    assert _by_title(rendered)["The Print"].id == "the-print"


def test_render_v2_the_print():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["The Print"]
    assert section.tone == "positive"
    kinds = [b.kind for b in section.blocks]
    assert kinds == ["paragraph", "paragraph", "bullets"]  # headline, what_changed, key_takeaways
    assert section.blocks[0].text.startswith("Revenue rose")
    assert "Guidance raised" in section.blocks[1].text
    assert section.blocks[2].items == ["Datacenter revenue doubled YoY", "Gross margin widened to 75%"]


def test_render_v2_results_is_metrics_table():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["Results That Matter"]
    assert len(section.blocks) == 1
    block = section.blocks[0]
    assert block.kind == "metrics"
    assert block.headers == ["Metric", "Current Period", "Prior Period", "Change", "Investor Takeaway"]
    assert [r[0] for r in block.rows] == ["Revenue", "Operating margin"]
    assert len(block.metric_rows) == 2  # typed rows the web renders richly


def test_render_v2_earnings_quality_red_flags_are_callouts():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["Earnings Quality & Cash Conversion"]
    kinds = [b.kind for b in section.blocks]
    assert kinds == ["paragraph", "paragraph", "callout", "callout"]
    callouts = [b for b in section.blocks if b.kind == "callout"]
    assert all(b.label == "Red flag" for b in callouts)
    assert "Receivables grew 22%" in callouts[0].text


def test_render_v2_forward_signals_quote_and_lists():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["Forward Signals"]
    assert section.tone == "positive"
    kinds = [b.kind for b in section.blocks]
    assert kinds == ["paragraph", "bullets", "bullets", "quote"]
    quote = section.blocks[-1]
    assert quote.speaker == "CEO"
    assert quote.text.startswith("Demand visibility")


def test_render_v2_risks_role_and_table():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["Risks"]
    assert section.role == "risks"
    assert section.blocks[0].kind == "table"
    assert section.blocks[0].headers == ["#", "Risk", "Supporting Evidence"]


def test_render_v2_segments_has_operating_income_column():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["Segments"]
    block = section.blocks[0]
    assert block.headers == ["Segment", "Revenue", "Operating Income", "Change", "Commentary"]
    assert block.rows[0] == ["Datacenter", "$30.8B", "$18.2B", "+112%", "AI demand"]


def test_render_v2_balance_sheet_paragraphs_and_covenants():
    section = _by_title(summary_sections.render_sections(_raw_v2()))["Balance Sheet & Liquidity"]
    paras = [b.text for b in section.blocks if b.kind == "paragraph"]
    assert any(p.startswith("Leverage:") for p in paras)
    assert any(p.startswith("Working capital:") for p in paras)
    bullets = [b for b in section.blocks if b.kind == "bullets"]
    assert bullets and bullets[0].text == "Maturities & covenants"


def test_render_v2_drops_empty_sections():
    partial = {"the_print": {"headline": "Only the lead."},
               "earnings_quality": {},            # empty object → dropped
               "segments": [],                     # empty list → dropped
               "forward_signals": {"guidance": "Reaffirmed."}}
    titles = [s.title for s in summary_sections.render_sections(_raw_v2(partial))]
    assert titles == ["The Print", "Forward Signals"]


def test_v2_markdown_is_clean_no_scaffolding():
    md = summary_sections.sections_to_markdown(summary_sections.render_sections(_raw_v2()))
    assert "## The Print" in md
    assert "## Earnings Quality & Cash Conversion" in md
    assert "## Value Drivers & Capital Allocation" in md
    # No raw field names leak into the rendered markdown.
    for field_name in ("operating_vs_one_time", "red_flags", "key_takeaways", "what_changed",
                       "maturities_covenants", "returns_on_capital", "source_section_ref"):
        assert field_name not in md
    # The red-flag callouts render with their label, not as a JSON list.
    assert "**Red flag:**" in md


# --- quality badge dispatch --------------------------------------------------------------------

def test_tracked_sections_for_dispatch():
    assert _tracked_sections_for(2) == TRACKED_SECTIONS_V2
    # v1 arm returns the FROZEN literal, NOT openai's mutable generation constant (PR B re-points
    # that to v2; the badge's v1 taxonomy must stay v1 for legacy rows). Asserting against the frozen
    # literal — not the same import the code uses — is what makes this non-tautological.
    for v1_like in (1, None, "1", 3, "x"):
        assert _tracked_sections_for(v1_like) == TRACKED_SECTIONS_V1


def test_tracked_sections_v1_is_frozen_literal():
    # Pin the exact historical v1 names so a drive-by edit can't silently move the badge's legacy bar.
    # This is a self-contained literal (not compared to openai's generation constant, which PR B
    # re-points to v2) — the badge's "what a v1 row should contain" is historical fact.
    assert TRACKED_SECTIONS_V1 == (
        "executive_snapshot", "financial_highlights", "risk_factors",
        "management_discussion_insights", "segment_performance", "liquidity_capital_structure",
        "guidance_outlook", "notable_footnotes", "three_year_trend",
    )
    assert TRACKED_SECTIONS_V1 != TRACKED_SECTIONS_V2


def test_verdict_coverage_counts_v2_taxonomy():
    per_section = {k: True for k in TRACKED_SECTIONS_V2[:6]}   # 6 of 9 populated
    per_section.update({k: False for k in TRACKED_SECTIONS_V2[6:]})
    summary_data = {"raw_summary": {"schema_version": 2,
                                    "section_coverage": {"per_section": per_section}}}
    covered, total, min_full = _verdict_coverage(summary_data)
    assert (covered, total, min_full) == (6, 9, 4)


def test_verdict_coverage_v2_ignores_stray_v1_keys():
    # A v2 row must count ONLY v2 keys — a leftover v1 key in per_section can't inflate the count.
    per_section = {k: True for k in TRACKED_SECTIONS_V2}
    per_section["executive_snapshot"] = True   # stray v1 key
    summary_data = {"raw_summary": {"schema_version": 2,
                                    "section_coverage": {"per_section": per_section}}}
    covered, total, _ = _verdict_coverage(summary_data)
    assert (covered, total) == (9, 9)


def test_verdict_coverage_v1_unchanged():
    # Build per_section from the FROZEN v1 literal (not openai's mutable constant) so this stays
    # meaningful after PR B re-points the generation tuple to v2.
    per_section = {k: True for k in TRACKED_SECTIONS_V1[:5]}
    summary_data = {"raw_summary": {"schema_version": 1,
                                    "section_coverage": {"per_section": per_section}}}
    covered, total, min_full = _verdict_coverage(summary_data)
    assert (covered, total, min_full) == (5, 9, 4)
