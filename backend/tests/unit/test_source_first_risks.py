"""One cross-surface gate for the source-first Risks trust boundary."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.change_report_service import assemble_report
from app.services.content_cache import upsert_content_cache
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.provenance_service import enrich_summary_provenance, source_safe_business_overview
from app.services.summary_pipeline import _finalize_summary_projection
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_only_same_filing_source_bytes_reach_every_risk_surface(monkeypatch):
    source_span = "Our business depends on a limited number of suppliers and may be disrupted."
    literal_span = r"Materials A | Materials B may be *unavailable* at C:\supply during disruptions."
    boundary_source = "We are unaffected by disruptions to our business and supplier relationships."
    boundary_attack = "affected by disruptions to our business and supplier relationships."
    ambiguous = "A repeated supplier sentence creates an ambiguous retained source span."
    wrapped_span = "Supplier concentration may disrupt operations and increase costs."
    wrapped_evidence = f'Item 1A: "{wrapped_span}"'
    filing_text = (
        f"{source_span}\n{literal_span}\n{boundary_source}\n{ambiguous}\n"
        f"{ambiguous.replace(' ', '  ')}\n{wrapped_span}"
    )
    unsafe_summary = "UNSAFE MODEL CLAIM: the affiliate is the named counterparty."
    unmatched = "UNMATCHED MODEL EVIDENCE: no such filing sentence exists anywhere."
    supplied = {
        "risk_source_context_version": 1,
        "metadata": {},
        "sections": {
            "_risk_source_projection": {"version": 1, "candidate_count": 999, "verified_count": 999, "withheld_count": 0},
            "risk_factors": [{"summary": unsafe_summary, "supporting_evidence": unmatched}],
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
                {"summary": "Historical wrapper", "supporting_evidence": wrapped_evidence},
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
        "version": 1, "verified_count": 4, "withheld_count": 2,
        "candidate_count": 6, "source_available": True,
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

    # Supported degraded primary path: no precomputed excerpt, but generation uses filing_text.
    degraded_html = filing_text.replace(
        source_span,
        "Our business depends on a limited <span>number of suppliers</span> and may be disrupted.",
    )
    degraded = await service.summarize_filing(
        degraded_html, "Example Co", "10-K", filing_excerpt=None
    )
    degraded_source_for_cache = degraded["_risk_source_grounding"]
    _, degraded_raw, degraded_sections, _ = _finalize_summary_projection(
        degraded, None, degraded["status"], source_text=degraded_html,
        filing_document_url=filing.document_url,
    )
    assert degraded_sections["_risk_source_projection"]["verified_count"] == 4
    degraded_evidence = degraded_sections["risks"][0]["supporting_evidence"]
    assert " ".join(degraded_evidence.split()) == source_span
    assert "<span>" not in degraded_evidence
    for private_key in ("_risk_source_candidates", "_risk_source_grounding"):
        assert private_key not in degraded and private_key not in degraded_raw

    # A later cached read deterministically decodes same-filing raw HTML rather than reverting to
    # raw-markup matching and withholding the excerpt that was valid at fresh finalization.
    degraded_summary = SimpleNamespace(
        id=11, filing_id=2, business_overview=degraded["business_overview"],
        raw_summary=json.loads(json.dumps(degraded_raw)), financial_highlights={},
        risk_factors=degraded["risk_factors"], management_discussion="", key_changes="",
        schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None,
    )
    class CacheSession:
        def __init__(self): self.added = []
        def add(self, value): self.added.append(value)

    cache_session = CacheSession()
    upsert_content_cache(
        cache_session, 2, None, excerpt=None, sections_payload=degraded_sections,
        risk_source_text=degraded_source_for_cache,
    )
    assert len(cache_session.added) == 1
    persisted_cache = cache_session.added[0]
    assert persisted_cache.critical_excerpt is None
    assert persisted_cache.risk_source_text == degraded_source_for_cache
    assert persisted_cache.markdown_content is None
    degraded_filing = SimpleNamespace(
        **{**filing.__dict__, "content_cache": persisted_cache}
    )
    degraded_cached = enrich_summary_provenance(degraded_summary, degraded_filing)
    cached_evidence = degraded_cached["raw_summary"]["sections"]["risks"][0]["supporting_evidence"]
    assert " ".join(cached_evidence.split()) == source_span
    assert "<span>" not in cached_evidence

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

    # Exercise the router's ordinary existing-summary SSE short circuit, which precedes the shared
    # pipeline cache paths.
    from app.routers import summaries as summaries_router

    class FakeQuery:
        def __init__(self, value): self.value = value
        def options(self, *args): return self
        def filter(self, *args): return self
        def first(self): return self.value

    class FakeDb:
        def __init__(self, filing_value, summary_value):
            self.filing_value, self.summary_value, self.closed = filing_value, summary_value, False
        def query(self, model):
            return FakeQuery(self.filing_value if model.__name__ == "Filing" else self.summary_value)
        def close(self): self.closed = True

    route_summary = SimpleNamespace(**{
        **summary.__dict__,
        "id": 9,
        "business_overview": f"## Risks\n\n{unsafe_summary}\n",
    })
    route_db = FakeDb(filing, route_summary)
    monkeypatch.setattr(summaries_router, "enforce_rate_limit", lambda *args, **kwargs: None)
    route_response = await summaries_router.generate_summary_stream(
        2, SimpleNamespace(client=SimpleNamespace(host="offline")),
        current_user=SimpleNamespace(id=7), db=route_db,
    )
    route_body = b"".join([
        chunk if isinstance(chunk, bytes) else chunk.encode()
        async for chunk in route_response.body_iterator
    ]).decode()
    surfaces["router_cached_sse"] = route_body
    assert route_db.closed is True
    for name, rendered in surfaces.items():
        for unsafe in (
            unsafe_summary, unmatched, boundary_attack, "attacker.invalid",
            "Item 1A. Risk Factors", "Item 1A:",
        ):
            assert unsafe not in rendered, (name, unsafe)
    for name in ("final_sse", "cached_sse", "joined_sse", "router_cached_sse", "api", "pdf", "csv"):
        assert source_span in surfaces[name], name
        assert "Selected excerpts are not a complete risk inventory" in surfaces[name], name
    assert literal_span in surfaces["pdf"] and literal_span in surfaces["csv"]
    assert enriched["raw_summary"]["sections"]["risks"][1]["supporting_evidence"] == literal_span
    assert enriched["raw_summary"]["sections"]["risks"][3]["supporting_evidence"] == wrapped_span
    assert source_span not in preview
    assert enriched["raw_summary"]["sections"]["risks"][0]["supporting_evidence"] == source_span
    assert enriched["raw_summary"]["sections"]["risks"][0]["source_section_ref"] == "Filing excerpt"
    assert enriched["raw_summary"]["sections"]["risks"][0]["source_url"].startswith(filing.document_url)
    assert enriched["raw_summary"]["structured"]["sections"]["risks"] == []
    assert "risk_factors" not in enriched["raw_summary"]["sections"]
    assert "risk_factors" not in enriched["raw_summary"]["structured"]["sections"]

    # Nested metadata alone cannot authorize display.
    forged = {"schema_version": 2, "sections": supplied["sections"]}
    forged_markdown = sections_to_markdown(render_sections(forged))
    assert unsafe_summary not in forged_markdown and unmatched not in forged_markdown

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
        assert mismatched["raw_summary"]["sections"]["_risk_source_projection"]["withheld_count"] == 6

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

    # Legacy compatibility-only rows retain matching excerpts on every shared surface.
    legacy_good = SimpleNamespace(
        id=10, filing_id=2, raw_summary={"sections": {}},
        business_overview="## Legacy Overview\n\nOperating history remains visible.\n",
        financial_highlights={}, risk_factors=[{
            "summary": unsafe_summary, "supporting_evidence": source_span,
        }], management_discussion="", key_changes="", schema_version=1, prompt_version=None,
    )
    legacy_enriched = enrich_summary_provenance(legacy_good, filing)
    legacy_surfaces = (
        source_safe_business_overview(legacy_good, filing),
        json.dumps(legacy_enriched),
        exporter.generate_pdf_html(legacy_good, filing),
        exporter.generate_csv(legacy_good, filing),
    )
    for rendered in legacy_surfaces:
        assert source_span in rendered and unsafe_summary not in rendered
    assert "Operating history remains visible." in legacy_enriched["business_overview"]
    assert legacy_enriched["rendered_sections"] == []
