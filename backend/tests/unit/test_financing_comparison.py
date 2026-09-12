"""Source-to-visible capital-allocation ownership through production extraction and rendering."""
import json
from types import SimpleNamespace

import pytest

from app.services.ai.financing_comparison import CAPITAL_CONTEXT_KEY, OWNED_FIELD
from app.services.copilot_service import _compact_xbrl_block
from app.services.edgar.xbrl_service import EdgarXBRLService
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.provenance_service import enrich_summary_provenance
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from tests.unit.test_financing_source import extract, instance_xml

BORROWING = "Financing activities primarily reflected net proceeds from loans payable and other financial liabilities."
PROGRAM = "The board authorized a new $1.0 billion share repurchase program."
UNSCALED = "The company intends to invest approximately $6,500 in new facilities."
FALSE = "Financing cash flow turned positive at $2.9B."
SOURCE = BORROWING + "\n\n" + PROGRAM + "\n\n" + UNSCALED


def structured():
    return {"sections": {
        "the_print": {"headline": "The company reported its annual results."},
        "results_that_matter": {"table": []},
        "earnings_quality": {"operating_vs_one_time": "Reported operating results."},
        "value_drivers": {"capital_allocation": {"filing_statements": [BORROWING, UNSCALED, FALSE]},
                          "highlights": [PROGRAM, FALSE], "analysis": FALSE,
                          OWNED_FIELD: {"comparison": FALSE}},
        "forward_signals": {"guidance": "No selected guidance."},
        "risks": [{"summary": "Credit risk."}],
        "balance_sheet_liquidity": {"liquidity": "The company reported cash."},
        "notable_footnotes": [{"item": "Accounting policies."}],
    }, "metadata": {}, CAPITAL_CONTEXT_KEY: 1, "_capital_allocation_grounding": FALSE}


def metrics(monkeypatch, **kwargs):
    raw, _filing, _xb = extract(monkeypatch, instance_xml(current=2_904_000_000, prior=1_959_000_000, **kwargs))
    return raw, EdgarXBRLService().extract_standardized_metrics(raw)


@pytest.mark.asyncio
async def test_real_instance_to_final_preview_and_four_surfaces_owns_the_comparison(monkeypatch):
    raw_xbrl, xbrl = metrics(monkeypatch)
    service = OpenAIService()
    supplied = structured()

    async def request(*args, **kwargs):
        return json.dumps(supplied)

    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing(SOURCE, "MercadoLibre", "10-K", xbrl_metrics=xbrl, filing_excerpt=SOURCE)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION  # actual orchestrator stamp
    owned = raw["sections"]["value_drivers"][OWNED_FIELD]
    assert "Both periods had net inflows." in owned["comparison"]
    assert "$2,904,000,000" in owned["comparison"] and "$1,959,000,000" in owned["comparison"]
    assert "2024-01-01 to 2024-12-31" in owned["comparison"]
    assert "2023" not in owned["comparison"]
    assert owned["filing_statements"] == [BORROWING, PROGRAM]
    assert CAPITAL_CONTEXT_KEY not in raw["structured"]
    assert "_capital_allocation_grounding" not in raw["structured"]
    assert raw[CAPITAL_CONTEXT_KEY] == 1
    assert "capital_allocation" not in raw["sections"]["value_drivers"]
    assert "highlights" not in raw["sections"]["value_drivers"]
    preview = service._partial_markdown_preview(json.dumps(supplied), xbrl)
    assert owned["comparison"] in preview
    assert BORROWING not in preview  # no excerpt is available at this callback
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion="", key_changes="",
                              schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="MercadoLibre"), filing_type="10-K",
                             filing_date=None, period_end_date=None, sec_url="", document_url="",
                             content_cache=SimpleNamespace(critical_excerpt=SOURCE))
    exporter = ExportService()
    surfaces = [json.dumps(enrich_summary_provenance(summary, filing)["rendered_sections"]),
                exporter.generate_pdf_html(summary, filing), exporter.generate_csv(summary, filing),
                sections_to_markdown(render_sections(raw)), preview, result["business_overview"]]
    for surface in surfaces:
        assert FALSE not in surface and "$6,500" not in surface
        assert "Both periods had net inflows." in surface
    # Internal XML provenance must not displace the unchanged compact Copilot context.
    without = {k: v for k, v in raw_xbrl.items() if k != "financing_comparison_source"}
    assert _compact_xbrl_block(raw_xbrl) == _compact_xbrl_block(without)


@pytest.mark.asyncio
async def test_unknown_context_drops_comparison_but_preserves_verified_explanation(monkeypatch):
    _raw, xbrl = metrics(monkeypatch, qualifier='<scenario><qualifier>subsidiary</qualifier></scenario>')
    service = OpenAIService()

    async def request(*args, **kwargs):
        return json.dumps(structured())

    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing(SOURCE, "MercadoLibre", "10-K", xbrl_metrics=xbrl, filing_excerpt=SOURCE)
    owned = result["raw_summary"]["sections"]["value_drivers"][OWNED_FIELD]
    assert owned["comparison"] == ""
    assert owned["filing_statements"] == [BORROWING, PROGRAM]
    assert FALSE not in result["business_overview"]


@pytest.mark.parametrize("marker", [None, True, "1"])
def test_legacy_or_forged_markers_cannot_authorize_new_representation(marker):
    sections = {"value_drivers": {"capital_allocation": "Legacy source interpretation.",
                                OWNED_FIELD: {"comparison": FALSE, "filing_statements": [BORROWING]}}}
    raw = {"schema_version": SUMMARY_SCHEMA_VERSION, "sections": sections,
           "structured": {CAPITAL_CONTEXT_KEY: 1}}
    if marker is not None:
        raw[CAPITAL_CONTEXT_KEY] = marker
    rendered = sections_to_markdown(render_sections(raw))
    assert "Legacy source interpretation." in rendered
    assert FALSE not in rendered and BORROWING not in rendered


@pytest.mark.asyncio
async def test_recovered_passages_use_the_actual_recovery_context(monkeypatch):
    service = OpenAIService()
    candidate = structured()
    candidate["sections"]["value_drivers"] = {}

    async def request(*args, **kwargs):
        return json.dumps(candidate)

    recovery_quote = "Borrowings provided funding for the company's disclosed capital program."

    async def recover(*args, **kwargs):
        return {"value_drivers": {"capital_allocation": {"filing_statements": [recovery_quote, BORROWING]}}}

    monkeypatch.setattr(service, "_request_content", request)
    monkeypatch.setattr(service, "_recover_missing_sections", recover)
    monkeypatch.setattr(service, "_build_section_context", lambda *a: recovery_quote)
    result = await service.summarize_filing(SOURCE, "Issuer", "10-K", filing_excerpt=SOURCE)
    assert result["raw_summary"]["sections"]["value_drivers"][OWNED_FIELD]["filing_statements"] == [recovery_quote]


@pytest.mark.asyncio
async def test_actual_apple_program_preserves_per_share_denominations_and_dates(monkeypatch):
    # Exact retained #831 AAPL source: authorization and per-share dividend share one sentence.
    program = ("In May 2025, the Company announced a new share repurchase program of up to $100 billion "
               "and raised its quarterly dividend from $0.25 to $0.26 per share beginning in May 2025.")
    dated = "As of September\xa027, 2025, the Company’s quarterly cash dividend was $0.26 per share."
    source = program + "\n\n" + dated + "\n\n" + UNSCALED
    candidate = structured()
    candidate["sections"]["value_drivers"] = {
        "capital_allocation": {"filing_statements": [program, dated, UNSCALED]},
    }
    service = OpenAIService()

    async def request(*args, **kwargs):
        return json.dumps(candidate)

    monkeypatch.setattr(service, "_request_content", request)
    result = await service.summarize_filing(source, "Apple", "10-K", filing_excerpt=source)
    passages = result["raw_summary"]["sections"]["value_drivers"][OWNED_FIELD]["filing_statements"]
    assert passages == [program, dated]
    assert "$100 billion" in result["business_overview"]
    assert "$0.25 to $0.26 per share" in result["business_overview"]
    assert "$6,500" not in result["business_overview"]
