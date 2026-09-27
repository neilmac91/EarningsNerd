"""Tier-2 Section/Block model: the metrics/callout kinds, evidence, Section.id slugs, and the
JSON projection (render_sections_json) the web's rendered_sections field consumes.
"""
import copy
import json
from types import SimpleNamespace

import pytest

from app.services import metric_delta_service
from app.services.export_service import ExportService
from app.services.fallback_summary import generate_xbrl_summary
from app.services.openai_service import OpenAIService
from app.services.provenance_service import enrich_raw_summary
from app.services.summary_pipeline import _finalize_summary_projection
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


@pytest.mark.asyncio
async def test_exact_xbrl_operands_own_rendered_delta_only_after_identity_checks(monkeypatch):
    """Rounded display strings cannot change a bound exact delta; conflicts and qualifiers abstain."""
    section = {
        "table": [
            {"metric": "Total net sales", "current_period": "$416.2B", "prior_period": "$391.0B",
             "change": "model says 99%", "change_display": "+99.0%"},
            {"metric": "Net income", "current_period": "$11.3B", "prior_period": "$8.5B"},
            {"metric": "Adjusted net income", "current_period": "$11.3B", "prior_period": "$8.5B",
             "change_display": "+99.0%"},
            {"metric": "Revenue", "current_period": "$417.0B", "prior_period": "$391.0B"},
            {"metric": "Gross margin", "current_period": "74.9%", "prior_period": "60.5%"},
        ],
    }
    metrics = {
        "revenue": {
            "current": {"period": "2025-09-27", "period_start": "2024-09-29", "form": "10-K",
                        "currency": "USD",
                        "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                        "value": 416_161_000_000},
            "prior": {"period": "2024-09-28", "period_start": "2023-10-01", "form": "10-K",
                      "currency": "USD",
                      "raw_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
                      "value": 391_035_000_000},
        },
        "net_income": {
            "current": {"period": "2025-12-31", "period_start": "2025-01-01", "form": "10-K",
                        "currency": "USD", "raw_tag": "us-gaap:NetIncomeLoss", "value": 11_308_000_000},
            "prior": {"period": "2024-12-31", "period_start": "2024-01-01", "form": "10-K",
                      "currency": "USD", "raw_tag": "us-gaap:NetIncomeLoss", "value": 8_480_000_000},
        },
        "gross_margin": {
            "current": {"period": "2026-04-26", "period_start": "2026-01-26", "form": "10-Q",
                        "value": 74.9},
            "prior": {"period": "2025-04-27", "period_start": "2025-01-27", "form": "10-Q",
                      "value": 60.5},
        },
        "operating_income": {
            "current": {"period": "2025-12-31", "period_start": "2025-01-01", "form": "10-K",
                        "currency": "USD", "raw_tag": "us-gaap:OperatingIncomeLoss",
                        "value": 13_305_000_000},
            "prior": {"period": "2024-12-31", "period_start": "2024-01-01", "form": "10-K",
                      "currency": "USD", "raw_tag": "us-gaap:OperatingIncomeLoss",
                      "value": 12_322_000_000},
        },
    }
    bound = metric_delta_service.bind_exact_xbrl_deltas(section, metrics)
    assert [row.get("change_display") for row in bound["table"]] == [
        "+6.4%", "+33.3%", None, None, "+14.4 ppts",
    ]

    for raw in (
        _raw({"financial_highlights": bound}),
        _raw({"results_that_matter": bound}, schema_version=2),
    ):
        raw[metric_delta_service.EXACT_CONTEXT_KEY] = metric_delta_service.EXACT_CONTEXT_VERSION
        block = next(b for s in render_sections(raw) for b in s.blocks if b.kind == "metrics")
        assert [row[3] for row in block.rows] == [
            "+6.4%", "+33.3%", "+32.9%", "+6.6%", "+14.4 ppts",
        ]
        assert block.metric_rows[0]["change"] == "model says 99%"

    forged = _raw({"financial_highlights": bound})
    forged[metric_delta_service.EXACT_CONTEXT_KEY] = True
    forged_block = next(b for s in render_sections(forged) for b in s.blocks if b.kind == "metrics")
    assert forged_block.rows[1][3] == "+32.9%"  # bool is not the application-owned integer marker
    assert forged_block.metric_rows[1]["change_display"] == "+32.9%"

    # A conflicting raw tag or period refuses exact binding and leaves the rounded-string fallback.
    conflicting = copy.deepcopy(metrics)
    conflicting["revenue"]["prior"]["raw_tag"] = "us-gaap:SalesRevenueNet"
    conflicting["net_income"]["prior"]["period"] = "2025-12-31"
    rejected = metric_delta_service.bind_exact_xbrl_deltas(section, conflicting)
    assert rejected["table"][0].get("change_display") is None

    leading_decimal = {"table": [
        {"metric": "Revenue", "current_period": "$.5B", "prior_period": "$.4B"},
    ]}
    wrong_bucket = copy.deepcopy(metrics)
    wrong_bucket["revenue"]["current"]["value"] = 900_000_000
    wrong_bucket["revenue"]["prior"]["value"] = 800_000_000
    assert metric_delta_service.bind_exact_xbrl_deltas(
        leading_decimal, wrong_bucket,
    )["table"][0].get("change_display") is None

    ambiguous_currency = {"table": [
        {"metric": "Revenue", "current_period": "¥100.0B", "prior_period": "¥80.0B"},
    ]}
    yen_shaped_usd = copy.deepcopy(metrics)
    yen_shaped_usd["revenue"]["current"]["value"] = 100_000_000_000
    yen_shaped_usd["revenue"]["prior"]["value"] = 80_000_000_000
    assert metric_delta_service.bind_exact_xbrl_deltas(
        ambiguous_currency, yen_shaped_usd,
    )["table"][0].get("change_display") is None

    cached = _raw({"results_that_matter": {"table": [copy.deepcopy(bound["table"][1])]}}, schema_version=2)
    cached[metric_delta_service.EXACT_CONTEXT_KEY] = metric_delta_service.EXACT_CONTEXT_VERSION
    preserved = enrich_raw_summary(cached, None, xbrl_standardized=None)
    preserved_block = next(b for s in render_sections(preserved) for b in s.blocks if b.kind == "metrics")
    assert preserved_block.rows[0][3] == "+33.3%"

    # A best-effort reload can be empty or contain only unrelated metrics. The generation marker
    # keeps each unavailable row's application-owned delta, while a complete contradictory pair
    # still re-enters strict validation and is scrubbed back to the rounded-display fallback.
    assert next(
        b for s in render_sections(enrich_raw_summary(cached, None, xbrl_standardized={}))
        for b in s.blocks if b.kind == "metrics"
    ).rows[0][3] == "+33.3%"
    cached_two = _raw({"results_that_matter": {"table": [
        copy.deepcopy(bound["table"][0]), copy.deepcopy(bound["table"][1]),
    ]}}, schema_version=2)
    cached_two[metric_delta_service.EXACT_CONTEXT_KEY] = metric_delta_service.EXACT_CONTEXT_VERSION
    partial_reload = enrich_raw_summary(
        cached_two, None, xbrl_standardized={"revenue": copy.deepcopy(metrics["revenue"])}
    )
    partial_block = next(b for s in render_sections(partial_reload) for b in s.blocks if b.kind == "metrics")
    assert [row[3] for row in partial_block.rows] == ["+6.4%", "+33.3%"]
    conflicting_reload = {"net_income": copy.deepcopy(metrics["net_income"])}
    conflicting_reload["net_income"]["prior"]["raw_tag"] = "us-gaap:ProfitLoss"
    contradicted = enrich_raw_summary(cached, None, xbrl_standardized=conflicting_reload)
    contradicted_block = next(
        b for s in render_sections(contradicted) for b in s.blocks if b.kind == "metrics"
    )
    assert contradicted_block.rows[0][3] == "+32.9%"

    forged_cached = copy.deepcopy(cached)
    forged_cached[metric_delta_service.EXACT_CONTEXT_KEY] = True
    forged_cached["sections"]["results_that_matter"]["table"][0]["change_display"] = "+99.0%"
    scrubbed = enrich_raw_summary(forged_cached, None, xbrl_standardized=None)
    scrubbed_block = next(b for s in render_sections(scrubbed) for b in s.blocks if b.kind == "metrics")
    assert scrubbed_block.rows[0][3] == "+32.9%"

    # Exercise the production extraction/render path and its streaming-preview projection. These
    # retained operands reproduce the AAPL and PGR rounding boundaries that exposed display-string
    # arithmetic; the service must bind the exact values before either surface renders the table.
    candidate = {
        "sections": {
            "the_print": {"headline": "Reported annual results."},
            "results_that_matter": copy.deepcopy(section),
            "earnings_quality": {"operating_vs_one_time": "Reported operating results."},
            "value_drivers": {"analysis": "Reported business drivers."},
            "forward_signals": {"guidance": "No selected guidance."},
            "risks": [{"summary": "Reported risk."}],
            "balance_sheet_liquidity": {"liquidity": "Reported liquidity."},
            "notable_footnotes": [{"item": "Reported accounting policy."}],
        },
        "metadata": {},
    }
    candidate["sections"]["results_that_matter"]["table"].append({
        "metric": "Operating income", "current_period": "$13.3B",
        "prior_period": "Not disclosed", "commentary": "Reported operating income.",
    })

    async def request(*args, **kwargs):
        return json.dumps(candidate)

    service = OpenAIService()
    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing(
        "Selected filing source.", "Selected issuer", "10-K",
        xbrl_metrics=metrics, filing_excerpt="Selected filing source.",
    )
    final = result["business_overview"]
    preview = service._partial_markdown_preview(json.dumps(candidate), metrics) or ""
    normalized_row = result["raw_summary"]["sections"]["results_that_matter"]["table"][-1]
    assert normalized_row["prior_period"] == "$12,322,000,000"
    assert normalized_row["change_display"] == "+8.0%"
    for surface in (final, preview):
        assert "+6.4%" in surface and "+33.3%" in surface
        assert "$12,322,000,000" in surface and "+8.0%" in surface
        assert "+6.5%" not in surface and "+33.4%" not in surface

    # The timeout generator bypasses OpenAIService, so the shared post-generation boundary must
    # bind and stamp its structured projection before persistence. Its existing SSE markdown stays
    # byte-identical, while PDF/CSV consume the corrected stored projection.
    fallback = generate_xbrl_summary(
        {"net_income": copy.deepcopy(metrics["net_income"])},
        "PGR", "2026-01-01", filing_type="10-K",
    )
    original_fallback_markdown = fallback["business_overview"]
    fallback_markdown, fallback_raw, _, fallback_financial = _finalize_summary_projection(
        fallback, {"net_income": copy.deepcopy(metrics["net_income"])}, "partial"
    )
    assert fallback_raw[metric_delta_service.EXACT_CONTEXT_KEY] == metric_delta_service.EXACT_CONTEXT_VERSION
    assert fallback["business_overview"] == fallback_markdown == original_fallback_markdown
    assert fallback["raw_summary"] == fallback_raw
    assert fallback_financial["table"][1]["change_display"] == "+33.3%"
    summary = SimpleNamespace(raw_summary=fallback_raw)
    filing = SimpleNamespace(
        filing_date=None, period_end_date=None, sec_url="https://sec.example/filing",
        filing_type="10-K", company=SimpleNamespace(name="PGR"),
    )
    surfaces = (
        ExportService().generate_pdf_html(summary, filing),
        ExportService().generate_csv(summary, filing),
    )
    for surface in surfaces:
        assert "+33.3%" in surface
        assert "+32.9%" not in surface
    assert rejected["table"][1].get("change_display") is None
    conflicting["revenue"]["prior"]["raw_tag"] = (
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    )
    conflicting["revenue"]["prior"]["period_start"] = "2024-06-30"
    rejected = metric_delta_service.bind_exact_xbrl_deltas(section, conflicting)
    assert rejected["table"][0].get("change_display") is None
    conflicting["revenue"]["prior"]["period_start"] = "2023-10-01"
    conflicting["revenue"]["current"]["currency"] = "EUR"
    conflicting["revenue"]["prior"]["currency"] = "EUR"
    rejected = metric_delta_service.bind_exact_xbrl_deltas(section, conflicting)
    assert rejected["table"][0].get("change_display") is None


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
    # Tone is a Section Badge (T1.2 treatment), NOT a prose sentence — so it must not pollute the
    # derived markdown (which leads the homepage-hero excerpt).
    assert "disclosed tone" not in md.lower()
    assert "outlook tone" not in md.lower()


def test_tone_rides_on_the_section_as_a_badge_not_prose():
    raw = _raw({
        "executive_snapshot": {"headline": "Record quarter.", "tone": "Confident"},
        "guidance_outlook": {"guidance": "Sequential growth expected.", "tone": "positive"},
    })
    sections = render_sections(raw)
    exec_section = next(s for s in sections if s.title == "Executive Assessment")
    outlook = next(s for s in sections if s.title == "Forward Outlook & Investment Implications")
    assert exec_section.tone == "confident"
    assert outlook.tone == "positive"
    # No block carries the old "tone was ..." sentence.
    assert all("tone was" not in (b.text or "").lower() for b in exec_section.blocks)
    # A neutral tone is suppressed entirely (schema field name, not user copy).
    neutral = render_sections(_raw({"executive_snapshot": {"headline": "Flat.", "tone": "neutral"}}))
    assert next(s for s in neutral if s.title == "Executive Assessment").tone == ""


def test_risks_section_carries_an_explicit_role():
    raw = _raw({
        "_risk_source_projection": {
            "version": 1, "verified_count": 1, "withheld_count": 0,
        },
        "risk_factors": [
            {"summary": "Filing excerpt", "source_verified": True,
             "supporting_evidence": "Item 1A: dependent on TSMC."},
        ],
    })
    raw["risk_source_context_version"] = 1
    risks = next(s for s in render_sections(raw) if s.title == "Investment Risks & Concerns")
    assert risks.role == "risks"
    assert risks.to_dict()["role"] == "risks"


def test_inline_markdown_is_stripped_at_the_projection():
    # The model is primed to emit markdown inside JSON string fields; the structured page renders raw
    # text, so inline markup is normalized ONCE here so every surface agrees.
    raw = _raw({
        "executive_snapshot": {
            "headline": "Revenue **surged** 85% on `AI` demand, see [outlook](http://x.co).",
            "key_points": ["Margin *expanded* to 74.9%"],
        },
        "financial_highlights": {
            "table": [{"metric": "Revenue", "current_period": "$81.6B", "prior_period": "$44.1B",
                       "commentary": "Driven by **data-center** growth."}],
        },
    })
    sections = render_sections(raw)
    exec_section = next(s for s in sections if s.title == "Executive Assessment")
    headline = exec_section.blocks[0].text
    assert headline == "Revenue surged 85% on AI demand, see outlook."
    bullets = next(b for b in exec_section.blocks if b.kind == "bullets")
    assert bullets.items[0] == "Margin expanded to 74.9%"
    # Both the string projection (exports) and the typed metric_rows (web) are normalized.
    fh = next(s for s in sections if s.title == "Financial Highlights")
    metrics = next(b for b in fh.blocks if b.kind == "metrics")
    assert metrics.rows[0][4] == "Driven by data-center growth."
    assert metrics.metric_rows[0]["commentary"] == "Driven by data-center growth."
    # And the derived markdown carries no stray markup either.
    md = sections_to_markdown(sections)
    for artifact in ("**", "`AI`", "](http"):
        assert artifact not in md


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
