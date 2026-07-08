"""Tier-2 Section/Block model: the metrics/callout kinds, evidence, Section.id slugs, and the
JSON projection (render_sections_json) the web's rendered_sections field consumes.
"""
from app.services.summary_sections import (
    Block,
    Section,
    render_sections,
    render_sections_json,
    sections_to_markdown,
)


def _raw(sections: dict, schema_version=None) -> dict:
    out = {"sections": sections}
    if schema_version is not None:
        out["schema_version"] = schema_version
    return out


def test_section_id_is_a_stable_slug():
    assert Section("Financial Highlights").id == "financial-highlights"
    assert Section("Forward Outlook & Investment Implications").id == "forward-outlook-investment-implications"
    # An explicit id is preserved.
    assert Section("X", id="custom").id == "custom"


def test_block_to_dict_omits_empty_fields():
    d = Block("paragraph", text="hi").to_dict()
    assert d == {"kind": "paragraph", "text": "hi"}
    d2 = Block("callout", label="Red flag", text="Receivables outpaced sales.").to_dict()
    assert d2 == {"kind": "callout", "label": "Red flag", "text": "Receivables outpaced sales."}


def test_financial_highlights_render_as_a_metrics_block_with_typed_rows():
    raw = _raw({
        "financial_highlights": {
            "table": [
                {"metric": "Revenue", "current_period": "$81.6B", "prior_period": "$44.1B",
                 "commentary": "Data-center growth."},
                {"metric": "Gross Margin", "current_period": "74.9%", "prior_period": "60.5%"},
            ],
        },
    })
    sections = render_sections(raw)
    fh = next(s for s in sections if s.title == "Financial Highlights")
    metrics = next(b for b in fh.blocks if b.kind == "metrics")
    # String projection for exports/markdown …
    assert metrics.headers[0] == "Metric"
    assert metrics.rows[0][3] == "+85.0%"          # computed amount delta
    assert metrics.rows[1][3] == "+14.4 ppts"       # computed margin delta (ppts, not relative %)
    # … plus typed rows for the web, carrying the computed change fields.
    assert len(metrics.metric_rows) == 2
    assert metrics.metric_rows[0]["change_display"] == "+85.0%"
    assert metrics.metric_rows[0]["change_tone"] == "gain"
    assert metrics.metric_rows[1]["change_display"] == "+14.4 ppts"


def test_render_sections_json_is_serializable_and_structured():
    raw = _raw({
        "executive_snapshot": {"headline": "Strong quarter.", "key_points": ["Revenue up 85%"]},
        "financial_highlights": {"table": [{"metric": "Revenue", "current_period": "$81.6B", "prior_period": "$44.1B"}]},
    })
    payload = render_sections_json(raw)
    import json
    json.dumps(payload)  # must be JSON-serializable
    assert payload[0]["id"] == "executive-assessment"
    assert payload[0]["title"] == "Executive Assessment"
    kinds = {b["kind"] for s in payload for b in s["blocks"]}
    assert "metrics" in kinds


def test_empty_or_missing_sections_render_nothing():
    assert render_sections_json({"sections": {}}) == []
    assert render_sections_json(None) == []
    assert render_sections_json({"sections": None}) == []


def test_sections_to_markdown_is_clean_gfm_with_no_scaffolding_leaks():
    # T2.2: sections_to_markdown is the DERIVED business_overview — same projection as PDF/CSV.
    raw = _raw({
        "executive_snapshot": {
            "headline": "Data-center demand drove a record quarter.",
            "tone": "confident",
            "key_points": ["Revenue up 85% YoY", "Gross margin expanded to 74.9%"],
        },
        "financial_highlights": {
            "table": [
                {"metric": "Revenue", "current_period": "$81.6B", "prior_period": "$44.1B",
                 "commentary": "Data-center growth."},
                {"metric": "Gross Margin", "current_period": "74.9%", "prior_period": "60.5%"},
            ],
        },
        "guidance_outlook": {
            "guidance": "Management expects continued sequential growth.",
            "tone": "positive",
            "drivers": ["AI infrastructure buildout"],
        },
    })
    md = sections_to_markdown(render_sections(raw))

    # H2 section titles, not the legacy "## Executive Summary" scaffold headings.
    assert "## Executive Assessment" in md
    assert "## Financial Highlights" in md
    # Metrics block renders as a GFM table (header separator row present).
    assert "| --- |" in md
    assert "| Metric |" in md
    # Figures are preserved verbatim.
    for figure in ("$81.6B", "$44.1B", "74.9%", "60.5%", "+85.0%", "+14.4 ppts"):
        assert figure in md
    # No field-name scaffolding leaks the old flatteners produced.
    for leak in ("- Guidance:", "Guidance:", "- Tone:", "Tone:", "(Evidence:", "Key Points:", "Headline:"):
        assert leak not in md
    # Tone is rendered as prose, not a raw "tone" field.
    assert "confident" in md.lower()


def test_get_response_includes_rendered_sections_computed_post_enrichment():
    # T2.3: enrich_summary_provenance (what GET /filing/{id} returns) surfaces rendered_sections,
    # computed from the ENRICHED raw_summary so its metrics rows carry the verified deltas.
    from app.models import Summary
    from app.services.provenance_service import enrich_summary_provenance

    summary = Summary(
        id=1,
        filing_id=2,
        business_overview="x",
        raw_summary={
            "sections": {
                "financial_highlights": {
                    "table": [{"metric": "Revenue", "current_period": "$81.6B", "prior_period": "$44.1B"}],
                },
            },
        },
    )
    result = enrich_summary_provenance(summary, filing=None)
    assert isinstance(result["rendered_sections"], list) and result["rendered_sections"]
    fh = next(s for s in result["rendered_sections"] if s["title"] == "Financial Highlights")
    metrics = next(b for b in fh["blocks"] if b["kind"] == "metrics")
    assert metrics["metric_rows"][0]["change_display"] == "+85.0%"
