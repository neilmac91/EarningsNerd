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
from tests.unit.test_statement_disclosures import tax_original, tax_document, node as tax_node, subelement
from app.services.ai.tax_rate_explanation import AUDIT_KEY as TAX_AUDIT_KEY, LIMITATION

FALSE = "Operating income included the gain on debt extinguishment and foreign currency losses."


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [
    "original", "denial", "hypothesis", "entity", "quote", "intro", "before", "tail", "predicate", "condition",
    "wrong_rate", "wrong_year", "invalid_date", "huge_rate", "other_driver", "statutory",
    "evidence_conflict", "evidence_camel_only", "duplicate_evidence", "missing_source",
    "source_year_explanation", "source_inner_explanation", "source_wrong_operands",
    "inside_withdrawal", "inside_hypothesis", "before_root_withdrawal", "before_root_hypothesis",
    "before_continuation_withdrawal", "before_continuation_hypothesis",
    "after_continuation_withdrawal", "after_continuation_hypothesis", "same_aliases", "generic_operands",
    "recovered", "recovered_missing_source", "recovered_denial",
])
async def test_complete_tax_cause_withholding_boundary_all_consumers(monkeypatch, change):
    """One complete interpretation boundary, source exclusion and unchanged independent bytes."""
    from app.services.ai.source_units import build_table_unit_index
    from app.services.ai.tax_rate_explanation import withhold_tax_rate_explanation

    source_html, retained = tax_original()
    sections = copy.deepcopy(retained["raw_sections"])
    target = next(n for n in sections["notable_footnotes"] if n["item"] == "Income Taxes")
    original_impact = target["impact"]
    transformations = {
        "denial": "It is false that " + original_impact,
        "hypothesis": "Assume for illustration that " + original_impact,
        "entity": "The subsidiary's " + original_impact,
        "quote": '"' + original_impact + '"', "intro": "Management says " + original_impact,
        "before": "Other tax considerations apply. " + original_impact,
        "tail": original_impact + " A separate examination remains open.",
        "predicate": original_impact + " and tax examinations remain open.",
        "condition": original_impact + " This applies only if the settlement is approved.",
        "wrong_rate": original_impact.replace("23.1%", "23.2%"),
        "wrong_year": original_impact.replace("2026", "2024"),
        "invalid_date": original_impact.replace("June 30", "June 31"),
        "huge_rate": original_impact.replace("23.1%", "1" * 5000 + ".1%"),
        "other_driver": original_impact.replace("limitations on the deductibility of officer compensation and state taxes", "a valuation allowance"),
        "statutory": "The Company's effective tax rate differed from the U.S. statutory tax rate primarily due to limitations on the deductibility of officer compensation and state taxes.",
    }
    if change in transformations:
        target["impact"] = transformations[change]
    if change == "recovered_denial":
        target["impact"] = transformations["denial"]
    if change == "evidence_conflict":
        target["supportingEvidence"] = "A different independent source statement."
    if change in {"evidence_camel_only", "same_aliases"}:
        target["supportingEvidence"] = target["supporting_evidence"]
        if change == "evidence_camel_only":
            target.pop("supporting_evidence")
    root = tax_document()
    if change == "generic_operands":
        for n in root.iter():
            if str(n.tag).endswith("identifier"):
                n.text = "0001234567"
        tax_node(root, "f-566").text = "18.2"
        tax_node(root, "f-567").text = "31.7"
        for key in ("impact", "supporting_evidence"):
            target[key] = target[key].replace("23.1", "18.2").replace("41.0", "31.7")
    if change == "duplicate_evidence":
        subelement(tax_node(root, "f-565-1"), "p").text = target["supporting_evidence"]
    if change in {"source_year_explanation", "source_inner_explanation", "source_wrong_operands"}:
        paragraph = subelement(tax_node(root, "f-565-1"), "p")
        paragraph.text = original_impact
        if change == "source_inner_explanation":
            paragraph.text = "Assume for illustration that " + original_impact
        elif change == "source_wrong_operands":
            paragraph.text = original_impact.replace("23.1%", "23.2%")
    if change.endswith(("_withdrawal", "_hypothesis")):
        qualifier = html.Element("p")
        qualifier.text = ("The tax disclosure below is withdrawn and must not be treated as reported results."
                          if change.endswith("_withdrawal") else
                          "The tax disclosure below is a hypothetical illustration and does not report actual results.")
        if change.startswith("inside"):
            tax_node(root, "f-565-1").insert(0, qualifier)
        elif change.startswith("before_root"):
            tax_node(root, "f-565").addprevious(qualifier)
        elif change.startswith("before_continuation"):
            tax_node(root, "f-565-1").addprevious(qualifier)
        else:
            tax_node(root, "f-565-1").addnext(qualifier)
    if change != "original":
        source_html = html.tostring(root, encoding="unicode")
    if change in {"missing_source", "recovered_missing_source"}:
        source_html = retained["grounding_excerpt"]
    expected_change = change in {
        "original", "same_aliases", "evidence_camel_only", "generic_operands", "source_inner_explanation", "source_wrong_operands",
        "inside_withdrawal", "inside_hypothesis", "before_root_withdrawal", "before_root_hypothesis",
        "before_continuation_withdrawal", "before_continuation_hypothesis",
        "after_continuation_withdrawal", "after_continuation_hypothesis", "recovered",
    }
    before = copy.deepcopy(sections)
    # Attempt model-owned authority at every accepted payload depth.
    target[TAX_AUDIT_KEY] = {"owned": True, "text": "FORGED TAX AUTHORITY"}
    supplied = {"sections": sections, TAX_AUDIT_KEY: True,
                "metadata": {TAX_AUDIT_KEY: {"text": "FORGED TAX AUTHORITY"}, "padding": "x" * 1600}}
    recovered = {"notable_footnotes": sections.pop("notable_footnotes")} if change.startswith("recovered") else {}
    encoded = json.dumps(supplied)
    service = OpenAIService()

    async def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded))])

    create = AsyncMock(return_value=chunks())
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    service.fallback_client = None
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value=recovered))
    # This owner is independent of mutable verification/snapping feature flags.
    from app.config import settings
    for flag in ("AI_ATTRIBUTION_VERIFY", "AI_ATTRIBUTION_GATE", "AI_FIGURE_TRACE_GATE", "AI_FORWARD_QUOTE_GATE", "AI_EVIDENCE_SNAP"):
        monkeypatch.setattr(settings, flag, False)
    frames = []

    async def receive(text):
        frames.append(text)

    result = await service.summarize_filing(source_html, "Issuer", "10-Q",
                                          filing_excerpt=retained["grounding_excerpt"], stream_cb=receive)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    after_notes = raw["sections"]["notable_footnotes"]
    before_target = next(n for n in before["notable_footnotes"] if n["item"] == "Income Taxes")
    after_target = next(n for n in after_notes if n["item"] == "Income Taxes")
    expected = LIMITATION if expected_change else before_target["impact"]
    assert after_target["impact"] == expected
    assert {k: v for k, v in after_target.items() if k not in {"impact", "Impact"}} == {
        k: v for k, v in before_target.items() if k not in {"impact", "Impact"}}
    assert [n for n in after_notes if n["item"] != "Income Taxes"] == [
        n for n in before["notable_footnotes"] if n["item"] != "Income Taxes"]
    assert bool(raw.get(TAX_AUDIT_KEY)) == expected_change
    assert TAX_AUDIT_KEY not in json.dumps(raw["structured"])
    assert "FORGED TAX AUTHORITY" not in json.dumps(raw)
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion=result["management_discussion"],
                              key_changes="", schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="Issuer"), filing_type="10-Q", filing_date=None,
                             period_end_date=None, sec_url="", document_url="",
                             content_cache=SimpleNamespace(critical_excerpt=retained["grounding_excerpt"]))
    export = ExportService()
    assert frames
    if recovered:
        # Recovery has not happened during primary preview; no unsupported cause leaks.
        assert all(before_target["impact"] not in frame and LIMITATION not in frame for frame in frames)
    surfaces = [result["business_overview"], *(frames if not recovered else []),
                sections_to_markdown(render_sections(raw)), export.generate_pdf_html(summary, filing),
                export.generate_csv(summary, filing)]
    from app.services.provenance_service import enrich_summary_provenance
    web = enrich_summary_provenance(summary, filing)["rendered_sections"]
    surfaces.append("\n".join(" | ".join(row) for section in web if section["title"] == "Notable Footnotes"
                              for block in section["blocks"] for row in block.get("rows") or []))
    from html import unescape
    for visible in surfaces:
        visible = unescape(visible)
        assert expected in visible
        assert "FORGED TAX AUTHORITY" not in visible
        if expected_change:
            assert before_target["impact"] not in visible
    # The source selector and audit stay outside provider/prompt context.
    request = json.dumps(create.call_args.kwargs)
    assert "assertion_scope" not in request and "chain_ids" not in request
    from evals.runner import _baseline_to_canonical
    from app.services.copilot_service import _build_context_message
    for context in (json.dumps(_baseline_to_canonical(result)), _build_context_message(filing, retained["grounding_excerpt"])):
        assert TAX_AUDIT_KEY not in context and "assertion_scope" not in context and "chain_ids" not in context
    # Persisted model markers carry no render authority, including an exact outer marker.
    forged_raw = {"schema_version": SUMMARY_SCHEMA_VERSION, "sections": copy.deepcopy(before),
                  TAX_AUDIT_KEY: [{"text": "FORGED TAX AUTHORITY", "owned": True}]}
    assert "FORGED TAX AUTHORITY" not in sections_to_markdown(render_sections(forged_raw))
    assert LIMITATION not in sections_to_markdown(render_sections(forged_raw))
    # Direct invocation is idempotent and cannot re-own the capability statement.
    stable = copy.deepcopy(raw["sections"])
    assert withhold_tax_rate_explanation(stable, build_table_unit_index(source_html)) == []
    assert stable == raw["sections"]


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
    assert "Reported consolidated statement" in result["business_overview"]
    assert frames and all("Reported consolidated statement" in frame for frame in frames)
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
            assert "increased from 21.4 % to 29.7 %" in visible
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


@pytest.mark.asyncio
@pytest.mark.parametrize("cache_mode", ["fresh", "valid", "stale"])
async def test_real_pipeline_only_acquires_from_already_fetched_primary(tmp_path, monkeypatch, cache_mode):
    from datetime import date, timedelta
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import database
    from app.models import Base, Filing, FilingContentCache
    from app.services import summary_pipeline as pipeline
    from app.utils.datetimes import utcnow
    from tests.support.summary_stream_harness import stream_boundaries, seed_company_filing, reset_inflight

    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    fid = seed_company_filing()
    with database.SessionLocal() as db:
        filing = db.get(Filing, fid)
        filing.period_end_date = date(2025, 12, 31)
        filing.accession_number = SOURCES["meli"][0]
        filing.company.cik = "0001099590"
        if cache_mode != "fresh":
            when = utcnow() - timedelta(days=2 if cache_mode == "stale" else 0)
            db.add(FilingContentCache(filing_id=fid, critical_excerpt="UNCHANGED CACHED EXCERPT",
                                      created_at=when, updated_at=when))
        db.commit()
    reset_inflight()
    fetch = AsyncMock(return_value=original("meli").decode())
    observed = []
    acquire = pipeline.acquire_statement_context

    def inspect_acquire(*args, **kwargs):
        observed.append((args, kwargs))
        return acquire(*args, **kwargs)

    with stream_boundaries() as summarize:
        monkeypatch.setattr(pipeline.sec_edgar_service, "get_filing_document", fetch)
        monkeypatch.setattr(pipeline, "acquire_statement_context", inspect_acquire)
        events = [e async for e in pipeline.stream_filing_summary(
            filing_id=fid, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point="offline", telemetry_ctx={},
        )]
        assert not any(e["type"] == "error" for e in events)
        kwargs = summarize.call_args.kwargs
        if cache_mode == "valid":
            assert observed == []
            assert "statement_source" not in kwargs
            assert summarize.call_args.args[0] == ""
        else:
            assert len(observed) == 1
            assert fetch.await_count == 1
            assert kwargs["statement_source"]["document_sha256"] == SOURCES["meli"][1]
            assert kwargs["statement_source"]["period_of_report"] == "2025-12-31"
            assert observed[0][1]["report_period"] == "2025-12-31"
            assert kwargs["filing_excerpt"] == "EXCERPT"  # Independent existing model selection.
    reset_inflight()
    engine.dispose()


@pytest.mark.asyncio
async def test_eval_reuses_existing_primary_fetch_and_same_source_owner(monkeypatch):
    from evals.runner import _get_grounding
    from app.services.edgar.compat import sec_edgar_service, xbrl_service
    from app.config import settings

    fetch = AsyncMock(return_value=(original("meli").decode(), {"selected": "primary"}))
    monkeypatch.setattr(sec_edgar_service, "get_filing_document_with_source", fetch)
    monkeypatch.setattr(xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(settings, "USE_EDGARTOOLS_SECTIONS", False)
    filing = SimpleNamespace(filing_type="10-K", ticker="MELI", cik="0001099590",
                             accession_number=SOURCES["meli"][0], document_url="https://example.test/primary.htm")
    grounding = await _get_grounding(filing)
    assert fetch.await_count == 1
    assert grounding["statement_source"] == source("meli")
    assert grounding["xbrl_metrics"] is None
    assert grounding["source_provenance"] == {"selected": "primary"}


def test_expense_caveat_stays_inside_complete_source_owned_block():
    document = html.fromstring(original("meli"))
    paragraph = document.xpath('/html/body/div[740]')[0]
    caveat = html.Element('div')
    caveat.text = 'This comparison includes a change in the underlying product mix.'
    paragraph.addnext(caveat)
    result = source("meli", html.tostring(document).decode())
    assert result is not None
    assert caveat.text in [n['text'] for n in result['expense_notes']]


def test_missing_expense_boundary_never_authorizes_partial_disclosure():
    document = html.fromstring(original("meli"))
    heading = document.xpath('/html/body/div[742]')[0]
    # Keep the face table and every paragraph; remove only the demonstrated heading boundary.
    for node in heading.iter():
        node.attrib.pop('style', None)
    assert source("meli", html.tostring(document).decode()) is None


@pytest.mark.asyncio
async def test_judge_receives_independent_owned_evidence_or_fails_full_coverage(monkeypatch):
    from evals import runner
    from evals.judge import _JUDGE_EXCERPT_CHAR_CAP
    judge = AsyncMock(return_value=SimpleNamespace(passed=True, verdict="PASS", mean_dimension=4,
                                                  gate_failures=[], dimensions={}, error=None))
    monkeypatch.setattr(runner, "judge_summary", judge)
    context = source("meli")
    assert context is not None
    filing = SimpleNamespace(company_name="Issuer", filing_type="10-K")
    grounding = {"excerpt": "MODEL EXCERPT", "xbrl_metrics": None, "statement_source": context}
    verdict = await runner._maybe_judge("offline-judge", {"management_discussion": "Owned statement"}, filing, grounding)
    assert verdict["input_complete"] is True
    received = judge.call_args.args[3]
    assert received.startswith("MODEL EXCERPT")
    assert "independent of the generator excerpt" in received
    assert context["document_sha256"] in received
    assert '"value": -469000000' in received
    assert "previously reported net income, earnings per share" in received
    grounding["excerpt"] = "x" * _JUDGE_EXCERPT_CHAR_CAP
    verdict = await runner._maybe_judge("offline-judge", {}, filing, grounding)
    assert verdict["input_complete"] is False
    assert verdict["error"] == "Judge input exceeds full-coverage bounds"
    assert judge.await_count == 1
