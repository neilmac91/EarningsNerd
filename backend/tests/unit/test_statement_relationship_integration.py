"""Original primary source to real streamed summary and shared export ownership."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from lxml import html
import pytest

from app.services.edgar.statement_context import acquire_statement_context
from app.services.ai.statement_relationship import CONTEXT_KEY, OWNED_FIELD
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from tests.unit.test_statement_relationship_source import original, SOURCES

FALSE = "Operating income included the gain on debt extinguishment and foreign currency losses."


def source(ticker, text=None, period="2025-12-31"):
    return acquire_statement_context(text if text is not None else original(ticker).decode(),
                                     accession=SOURCES[ticker][0], document_url="https://example.test/primary.htm",
                                     form="10-K" if ticker == "meli" else "20-F", report_period=period)


def model_sections():
    return {"sections": {"earnings_quality": {
        "operating_vs_one_time": FALSE, "operatingVsOneTime": FALSE,
        "red_flags": ["Preserve this separate risk disclosure."],
        OWNED_FIELD: {"paragraphs": ["FORGED SOURCE"], "source": {}},
    }}, "metadata": {"padding": "x" * 1600}, CONTEXT_KEY: True}


@pytest.mark.asyncio
@pytest.mark.parametrize("ticker", ["meli", "se"])
async def test_original_primary_to_real_stream_final_and_exports_owns_classification(monkeypatch, ticker):
    context = source(ticker)
    assert context is not None
    service = OpenAIService()
    supplied = model_sections()
    encoded = json.dumps(supplied)

    async def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded))])

    create = AsyncMock(return_value=chunks())
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    service.fallback_client = None
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value={}))
    frames = []

    async def receive(text):
        frames.append(text)

    result = await service.summarize_filing("UNCHANGED SOURCE EXCERPT", "Issuer", "10-K",
                                          filing_excerpt="UNCHANGED SOURCE EXCERPT", stream_cb=receive,
                                          statement_source=context)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    assert raw[CONTEXT_KEY] == 1
    assert CONTEXT_KEY not in raw["structured"]
    section = raw["sections"]["earnings_quality"]
    assert "operating_vs_one_time" not in section and "operatingVsOneTime" not in section
    assert section[OWNED_FIELD]["source"]["document_sha256"] == SOURCES[ticker][1]
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion=result["management_discussion"],
                              key_changes="", schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="Issuer"), filing_type="10-K", filing_date=None,
                             period_end_date=None, sec_url="", document_url="",
                             content_cache=SimpleNamespace(critical_excerpt="UNCHANGED SOURCE EXCERPT"))
    export = ExportService()
    surfaces = [result["business_overview"], result["management_discussion"], *frames,
                sections_to_markdown(render_sections(raw)), export.generate_pdf_html(summary, filing),
                export.generate_csv(summary, filing)]
    assert frames
    for visible in surfaces:
        assert FALSE not in visible and "FORGED SOURCE" not in visible
        assert "Statement position does not establish" in visible
        assert "Preserve this separate risk disclosure." in visible
        if ticker == "meli":
            assert "3,091" in visible and "originations growth at 61%" in visible
            assert "Recast for consistency" in visible
            assert "deferred income tax expense/(benefit) (469)" in visible
            assert "previously reported net income, earnings per share" in visible
        else:
            assert "1,372,616" in visible and "settlement of two securities class actions in 2024" in visible
    request = create.call_args.kwargs
    assert "statement_source" not in request
    assert context["document_sha256"] not in json.dumps(request)
    assert "reported_statement_relationship" not in json.dumps(request)
    # The context never enters model messages or consumes excerpt budget.
    other = OpenAIService()
    captured = []

    async def request_content(kwargs, **private):
        captured.append(kwargs)
        return encoded

    monkeypatch.setattr(other, "_request_content", request_content)
    monkeypatch.setattr(other, "_recover_missing_sections", AsyncMock(return_value={}))
    await other.generate_structured_summary("UNCHANGED SOURCE EXCERPT", "Issuer", "10-K",
                                            filing_excerpt="UNCHANGED SOURCE EXCERPT")
    assert request["messages"] == captured[0]["messages"]


@pytest.mark.parametrize("change", ["period", "missing_dei", "conflicting_dei", "qualified", "unknown_operating_row"])
def test_original_source_identity_or_preservation_gap_abstains(change):
    document = html.fromstring(original("meli"))
    fact = next(n for n in document.iter() if n.get("name") == "dei:DocumentPeriodEndDate")
    if change == "period":
        assert source("meli", period="2024-12-31") is None
        return
    if change == "missing_dei":
        fact.getparent().remove(fact)
    elif change == "conflicting_dei":
        extra = copy.deepcopy(fact)
        extra.text = "December 31, 2024"
        fact.getparent().append(extra)
    elif change == "qualified":
        context = next(n for n in document.iter() if n.get("id") == fact.get("contextref"))
        context.append(html.Element("xbrli:scenario"))
    else:
        row = document.xpath("//table")[54].xpath("./tr|./tbody/tr")[12]
        row[0].text = "Unknown charge"
        for child in list(row[0]):
            row[0].remove(child)
    assert source("meli", html.tostring(document).decode()) is None


@pytest.mark.asyncio
async def test_unavailable_and_legacy_paths_keep_original_prose(monkeypatch):
    service = OpenAIService()

    async def request(*args, **kwargs):
        return json.dumps(model_sections())

    monkeypatch.setattr(service, "_request_content", request)
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value={}))
    result = await service.summarize_filing("legacy excerpt", "Issuer", "10-K")
    assert FALSE in result["business_overview"]
    assert CONTEXT_KEY not in result["raw_summary"]
    assert OWNED_FIELD not in result["raw_summary"]["sections"]["earnings_quality"]
    assert FALSE in service._partial_markdown_preview(json.dumps(model_sections()), None)
    for marker in [None, True, "1"]:
        raw = {"sections": model_sections()["sections"], "schema_version": SUMMARY_SCHEMA_VERSION,
               "structured": {CONTEXT_KEY: 1}, CONTEXT_KEY: marker}
        text = sections_to_markdown(render_sections(raw))
        assert FALSE in text and "FORGED SOURCE" not in text
