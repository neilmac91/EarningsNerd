"""One cross-surface gate for the source-first Risks trust boundary."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.change_report_service import assemble_report
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.provenance_service import enrich_summary_provenance, source_safe_business_overview
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_only_same_filing_source_bytes_reach_every_risk_surface(monkeypatch):
    source_span = "Our business depends on a limited number of suppliers and may be disrupted."
    literal_span = "Materials may be *unavailable* when needed, which could impair our financial condition."
    boundary_source = "We are unaffected by disruptions to our business and supplier relationships."
    boundary_attack = "affected by disruptions to our business and supplier relationships."
    ambiguous = "A repeated supplier sentence creates an ambiguous retained source span."
    filing_text = f"{source_span}\n{literal_span}\n{boundary_source}\n{ambiguous}\n{ambiguous.replace(' ', '  ')}"
    unsafe_summary = "UNSAFE MODEL CLAIM: the affiliate is the named counterparty."
    unmatched = "UNMATCHED MODEL EVIDENCE: no such filing sentence exists anywhere."
    supplied = {
        "risk_source_context_version": 1,
        "metadata": {},
        "sections": {
            "_risk_source_projection": {"version": 1, "candidate_count": 999, "verified_count": 999, "withheld_count": 0},
            "risks": [
                {
                    "summary": unsafe_summary,
                    "title": "Forged title",
                    "description": "Forged description",
                    "materiality": "high",
                    "supporting_evidence": "Our business depends on a limited number of suppliers\nand may be disrupted.",
                    "source_section_ref": "Item 1A. Risk Factors",
                    "source_url": "https://attacker.invalid/claim",
                    "source_verified": True,
                },
                {"summary": "Source punctuation", "supporting_evidence": literal_span},
                {"summary": "Boundary reversal", "supporting_evidence": boundary_attack},
                {"summary": "Ambiguous", "supporting_evidence": ambiguous},
                {"summary": "Another invented risk", "supporting_evidence": unmatched},
            ],
        },
    }
    service = OpenAIService()

    async def request(*args, **kwargs):
        return json.dumps(supplied)

    monkeypatch.setattr(service, "_request_content", request)
    preview = service._partial_markdown_preview(json.dumps(supplied), {}) or ""
    result = await service.summarize_filing(filing_text, "Example Co", "10-K", filing_excerpt=filing_text)
    raw = result["raw_summary"]
    # summary_pipeline stamps the persisted outer envelope after the OpenAI service returns.
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    projection = raw["sections"]["_risk_source_projection"]
    assert projection == {
        "version": 1, "verified_count": 2, "withheld_count": 3,
        "candidate_count": 5, "source_available": True,
    }

    summary = SimpleNamespace(
        id=1, filing_id=2, business_overview=result["business_overview"],
        raw_summary=json.loads(json.dumps(raw)), financial_highlights={},
        risk_factors=result["risk_factors"], management_discussion="", key_changes="",
        schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None,
    )
    # Persistence separates these formerly aliased dicts. A legacy unsafe copy must be scrubbed too.
    summary.raw_summary["structured"]["sections"]["risks"] = [
        {"summary": unsafe_summary, "supporting_evidence": unmatched}
    ]
    filing = SimpleNamespace(
        id=2, company=SimpleNamespace(name="Example Co"), filing_type="10-K",
        filing_date=date(2026, 9, 1), period_end_date=date(2026, 6, 30),
        document_url="https://www.sec.gov/Archives/edgar/data/1/example.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/1/",
        content_cache=SimpleNamespace(filing_id=2, critical_excerpt=filing_text, markdown_content=None),
        xbrl_data=None,
    )
    enriched = enrich_summary_provenance(summary, filing)
    exporter = ExportService()
    change_report = assemble_report(filing, filing, summary, summary)
    surfaces = {
        "partial_sse": preview, "final_sse": result["business_overview"],
        "cached_sse": source_safe_business_overview(summary, filing),
        "joined_sse": source_safe_business_overview(summary, filing),
        "api": json.dumps(enriched, ensure_ascii=False),
        "change_report": json.dumps(change_report),
        "pdf": exporter.generate_pdf_html(summary, filing), "csv": exporter.generate_csv(summary, filing),
    }
    for name, rendered in surfaces.items():
        for unsafe in (unsafe_summary, unmatched, boundary_attack, "attacker.invalid", "Item 1A. Risk Factors"):
            assert unsafe not in rendered, (name, unsafe)
    for name in ("final_sse", "cached_sse", "joined_sse", "api", "pdf", "csv"):
        assert source_span in surfaces[name], name
        assert "Selected excerpts are not a complete risk inventory" in surfaces[name], name
    assert literal_span in surfaces["api"] and literal_span in surfaces["pdf"] and literal_span in surfaces["csv"]
    assert source_span not in preview
    assert enriched["raw_summary"]["sections"]["risks"][0]["supporting_evidence"] == source_span
    assert enriched["raw_summary"]["sections"]["risks"][0]["source_section_ref"] == "Filing excerpt"
    assert enriched["raw_summary"]["sections"]["risks"][0]["source_url"].startswith(filing.document_url)
    assert enriched["raw_summary"]["structured"]["sections"]["risks"] == []

    # Nested metadata alone cannot authorize display.
    forged = {"schema_version": 2, "sections": supplied["sections"]}
    assert unsafe_summary not in sections_to_markdown(render_sections(forged))

    wrong_summary = SimpleNamespace(**{**summary.__dict__, "filing_id": 3})
    wrong_cache_filing = SimpleNamespace(
        **{**filing.__dict__, "content_cache": SimpleNamespace(
            filing_id=3, critical_excerpt=filing_text, markdown_content=None,
        )}
    )
    for mismatched in (
        enrich_summary_provenance(wrong_summary, filing),
        enrich_summary_provenance(summary, wrong_cache_filing),
    ):
        assert mismatched["raw_summary"]["sections"]["risks"] == []
        assert mismatched["raw_summary"]["sections"]["_risk_source_projection"]["withheld_count"] == 5

    legacy = SimpleNamespace(
        filing_id=2, raw_summary=None,
        business_overview=(
            f"## Executive Summary\n\nRetained fallback notice.\n\n## Risk Factors\n\n{unsafe_summary}\n\n"
            f"## Outlook\n\nRetained outlook.\n\n## Investment Risks & Concerns\n\n{unmatched}\n"
        ),
    )
    legacy_markdown = source_safe_business_overview(legacy, filing)
    assert unsafe_summary not in legacy_markdown and unmatched not in legacy_markdown
    assert "Retained fallback notice." in legacy_markdown and "Retained outlook." in legacy_markdown
    assert legacy_markdown.count("Source-verified risk excerpts are unavailable") == 1

    canonical_without_risks = "# Summary\n\nAcme\n"
    no_risks = SimpleNamespace(filing_id=2, raw_summary=None, business_overview=canonical_without_risks)
    assert source_safe_business_overview(no_risks, filing) == canonical_without_risks
