"""Narrow ambiguous-component withholding on actual source; no financial reconstruction."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from lxml import etree, html
import pytest

from app.config import settings
from app.services.ai.statement_relationship import (
    COMPONENT_LIMITATION, CONTEXT_KEY, OWNED_FIELD, bind_statement_relationship,
)
from app.services.edgar.statement_context import acquire_statement_context
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from app.utils.sec_urls import build_sec_archive_url

FIXTURES = Path(__file__).parents[1] / "fixtures" / "quarterly_statement"
ACCESSION = "0001321655-26-000028"
URL = build_sec_archive_url("1321655", ACCESSION) + "pltr-20260331.htm"
SOURCE_SHA = "b8702d982190b1815c6bcb450fd337273c1b104d187328b05012a1ddf0c852a1"
CLAIM = json.loads((FIXTURES / "retained-claim.json").read_text())["operating_vs_one_time"]
SUFFIX = CLAIM[CLAIM.index(" Stock-based compensation"):]
OVERSIZED_AMOUNT = "$9" + ",999" * 1500


def original():
    raw = gzip.decompress((FIXTURES / "pltr-20260331.html.gz").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    return raw.decode()


def acquire(text=None, **kwargs):
    return acquire_statement_context(original() if text is None else text, accession=ACCESSION,
                                     document_url=URL, form="10-Q", report_period=kwargs.get("period", "2026-03-31"))


def node(document, identifier):
    return document.xpath("//*[@id=$identifier]", identifier=identifier)[0]


def sections(claim=CLAIM):
    return {"earnings_quality": {"operating_vs_one_time": claim,
                                 "red_flags": ["Preserve this separate risk disclosure."],
                                 OWNED_FIELD: {"paragraphs": ["FORGED SOURCE"]}}}


def test_actual_source_has_signed_aggregate_facts_and_full_duration():
    source = acquire()
    assert source is not None
    assert source["document_sha256"] == SOURCE_SHA
    assert source["issuer_cik"] == "1321655" and source["currency"] == "USD"
    assert (source["current"]["start"], source["current"]["end"]) == ("2026-01-01", "2026-03-31")
    assert (source["prior"]["start"], source["prior"]["end"]) == ("2025-01-01", "2025-03-31")
    assert source["current"]["rows"]["other"]["value"] == 68209000
    assert source["prior"]["rows"]["other"]["value"] == -3173000
    assert source["current"]["rows"]["other"]["concept"] == "us-gaap:OtherNonoperatingIncomeExpense"
    supplied = sections()
    assert bind_statement_relationship(supplied, source) is True
    owned = supplied["earnings_quality"][OWNED_FIELD]
    assert owned["preserved_authored_suffix"] == SUFFIX
    assert all(SUFFIX not in p for p in owned["paragraphs"])
    assert owned["paragraphs"] == [COMPONENT_LIMITATION]
    assert owned["kind"] == "unverified_component_breakdown"
    assert owned["source"]["assertion_scope"] == "not_established"


@pytest.mark.parametrize("change", [
    "different_start", "all_different_start", "different_entity", "dimension", "currency", "sign",
    "untagged", "wrong_concept", "row_alias", "duplicate_context", "duplicate_unit", "duplicate_fact_id",
    "conflicting_repeat", "retracted_title", "caption", "wrapper_prose", "extra_bridge_row", "period_header",
    "namespace", "nested_namespace", "different_report", "wrong_form",
    "prose_before_bridge", "prose_after_bridge", "prose_in_other_row",
    "one_row_header", "two_row_header", "leap_day_comparison",
    "oversized_current_fact", "oversized_prior_fact", "oversized_repeat", "oversized_component",
    "oversized_visible_same_cell", "oversized_visible_other_cell",
])
def test_actual_source_adverse_boundaries_abstain(change):
    document = html.fromstring(original().encode())
    table = document.xpath('/html/body/div[56]/table')[0]
    fact = node(document, "f-129")
    report_period = "2026-03-31"
    if change in {"different_start", "different_entity", "dimension"}:
        context = copy.deepcopy(node(document, "c-1"))
        context.set("id", "adverse-context")
        node(document, "c-1").addnext(context)
        fact.set("contextref", "adverse-context")
        if change == "different_start":
            next(n for n in context.iter() if n.tag == "xbrli:startdate").text = "2025-07-01"
        elif change == "different_entity":
            next(n for n in context.iter() if n.tag == "xbrli:identifier").text = "0000000001"
        else:
            context.append(html.Element("xbrli:scenario"))
    elif change == "all_different_start":
        next(n for n in node(document, "c-1").iter() if n.tag == "xbrli:startdate").text = "2025-07-01"
    elif change == "currency":
        node(document, "usd")[0].text = "iso4217:EUR"
    elif change == "sign":
        node(document, "f-130").attrib.pop("sign")
    elif change == "untagged":
        etree.strip_tags(table, "ix:nonfraction")
    elif change == "wrong_concept":
        fact.set("name", "us-gaap:GainLossOnSaleOfInvestments")
    elif change == "row_alias":
        cell = fact.xpath("ancestor::tr")[0][0]
        cell.clear()
        cell.text = "Realized gain"
    elif change in {"duplicate_context", "duplicate_unit", "duplicate_fact_id"}:
        target = node(document, {"duplicate_context": "c-1", "duplicate_unit": "usd", "duplicate_fact_id": "f-129"}[change])
        target.addnext(copy.deepcopy(target))
    elif change == "conflicting_repeat":
        extra = copy.deepcopy(fact)
        extra.set("id", "adverse-repeat")
        extra.text = "99,999"
        document.xpath("//body")[0].append(extra)
    elif change == "oversized_visible_same_cell":
        fact.tail = " " + OVERSIZED_AMOUNT[1:]
    elif change == "oversized_visible_other_cell":
        fact.xpath("ancestor::td")[0].getnext().text = OVERSIZED_AMOUNT[1:]
    elif change in {"oversized_current_fact", "oversized_prior_fact", "oversized_repeat", "oversized_component"}:
        if change == "oversized_prior_fact":
            fact = node(document, "f-130")
        elif change in {"oversized_repeat", "oversized_component"}:
            fact = copy.deepcopy(fact)
            fact.set("id", "oversized-fact")
            if change == "oversized_component":
                fact.set("name", "us-gaap:GainLossOnSaleOfInvestments")
            document.xpath("//body")[0].append(fact)
        fact.text = OVERSIZED_AMOUNT[1:]
        if change == "oversized_component":
            # Optional components already ignore invalid fact values. Preserve
            # that contract while declining the oversized component itself.
            source = acquire(html.tostring(document).decode())
            assert source is not None
            assert source["separate_investment_component_amounts"] == []
            return
    elif change == "retracted_title":
        table.getparent().getprevious().append(html.fromstring("<p>The above statement is withdrawn.</p>"))
    elif change == "caption":
        table.insert(0, html.fromstring("<caption>Hypothetical example only</caption>"))
    elif change == "wrapper_prose":
        table.addprevious(html.fromstring("<p>Hypothetical example only</p>"))
    elif change == "extra_bridge_row":
        fact.xpath("ancestor::tr")[0].addnext(html.fromstring("<tr><td>Other component omitted</td></tr>"))
    elif change == "period_header":
        header = table.xpath('./tr')[1]
        for part in header.iter():
            if part.text and "Three Months" in part.text:
                part.text = part.text.replace("Three Months", "Six Months")
    elif change == "namespace":
        document.set("xmlns:us-gaap", "http://example.invalid/not-us-gaap")
    elif change == "nested_namespace":
        fact.set("xmlns:us-gaap", "http://example.invalid/not-us-gaap")
    elif change in {"prose_before_bridge", "prose_after_bridge"}:
        table.insert(3 if change == "prose_before_bridge" else len(table),
                     html.fromstring("<tr><td>The following figures are hypothetical.</td></tr>"))
    elif change == "prose_in_other_row":
        node(document, "f-111").tail = " This statement is withdrawn."
    elif change == "different_report":
        assert acquire(period="2025-03-31") is None
        return
    elif change in {"one_row_header", "two_row_header"}:
        # The expected tokens do not establish the required three-row header.
        table.clear()
        header = ("<tr><td>Three Months Ended March 31,</td>"
                  + ("</tr><tr>" if change == "two_row_header" else "")
                  + "<td>2026</td><td>2025</td></tr>")
        table.extend(html.fragments_fromstring(header))
    elif change == "leap_day_comparison":
        # Valid source dates, but the finite grammar cannot match the same
        # prior-year day. Decline without constructing the invalid 2023-02-29.
        replacements = {"2026-03-31": "2024-02-29", "2026-01-01": "2023-12-01",
                        "2025-03-31": "2023-02-28", "2025-01-01": "2022-12-01",
                        "March 31, 2026": "February 29, 2024",
                        "Three Months Ended March 31,": "Three Months Ended February 29,"}
        for part in document.iter():
            if part.text:
                for old, new in replacements.items():
                    part.text = part.text.replace(old, new)
        for part in table.iter():
            if part.text in {"2026", "2025"}:
                part.text = {"2026": "2024", "2025": "2023"}[part.text]
        report_period = "2024-02-29"
    else:
        node(document, "f-1").text = "10-K"
    assert acquire(html.tostring(document).decode(), period=report_period) is None


@pytest.mark.parametrize("claim", [
    "Management denies that " + CLAIM,
    "Hypothetical example: " + CLAIM,
    CLAIM + " These figures are hypothetical.",
    CLAIM.replace("Net income of", "Subsidiary net income of"),
    CLAIM.replace("prior-year period", "2024 period"),
    CLAIM.replace("$68,209 thousand", "$68,210 thousand"),
    pytest.param(CLAIM.replace("$876,402", OVERSIZED_AMOUNT), id="oversized-net"),
    pytest.param(CLAIM.replace("$68,209", OVERSIZED_AMOUNT), id="oversized-other"),
    pytest.param(CLAIM.replace("$(3,173)", "$(" + OVERSIZED_AMOUNT[1:] + ")"), id="oversized-prior"),
    CLAIM.replace("privately-held equity securities", "privately-held equity securities and caused profit growth"),
    CLAIM.replace("Stock-based compensation expense was", "The Company denies that stock-based compensation expense was"),
    "A tax benefit of $774 million increased net income.",
])
def test_complete_authored_boundary_preserves_unsupported_claims(claim):
    supplied = sections(claim)
    assert bind_statement_relationship(supplied, acquire()) is False
    assert supplied["earnings_quality"]["operating_vs_one_time"] == claim
    assert OWNED_FIELD not in supplied["earnings_quality"]


@pytest.mark.asyncio
@pytest.mark.parametrize("claim,corrected", [
    (CLAIM, True), ("Hypothetical example: " + CLAIM, False),
    pytest.param(CLAIM.replace("$876,402", OVERSIZED_AMOUNT), False, id="oversized-net"),
])
@pytest.mark.parametrize("alias_layout", ["snake_only", "camel_only", "empty_snake", "empty_camel", "equal"])
async def test_native_source_to_final_preview_shared_exports_preserves_suffix(monkeypatch, claim, corrected, alias_layout):
    for flag in ("AI_ATTRIBUTION_VERIFY", "AI_ATTRIBUTION_GATE", "AI_FORWARD_QUOTE_GATE", "AI_FIGURE_TRACE_GATE"):
        monkeypatch.setattr(settings, flag, False)
    monkeypatch.setattr(settings, "AI_EVIDENCE_SNAP", True)
    source = acquire()
    supplied = {"sections": sections(claim), "metadata": {}, "schema_version": SUMMARY_SCHEMA_VERSION}
    quality = supplied["sections"]["earnings_quality"]
    if alias_layout in {"camel_only", "empty_snake", "equal"}:
        quality["operatingVsOneTime"] = claim
    if alias_layout == "camel_only":
        quality.pop("operating_vs_one_time")
    elif alias_layout == "empty_snake":
        quality["operating_vs_one_time"] = ""
    elif alias_layout == "empty_camel":
        quality["operatingVsOneTime"] = ""
    service = OpenAIService()
    # Enter through the model-response seam so real JSON assembly and fallbacks
    # cannot silently normalize an alias before final binding.
    monkeypatch.setattr(service, "_request_content", AsyncMock(return_value=json.dumps(supplied)))
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value={}))
    result = await service.summarize_filing(original(), "Palantir", "10-Q", statement_source=source)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    preview = service._partial_markdown_preview(json.dumps(supplied), None, statement_source=source)
    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion=result["management_discussion"],
                              key_changes="", schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="Palantir"), filing_type="10-Q", filing_date=None,
                             period_end_date=None, sec_url=URL, document_url=URL, content_cache=None)
    exporter = ExportService()
    surfaces = [result["business_overview"], result["management_discussion"], preview,
                sections_to_markdown(render_sections(raw)), exporter.generate_pdf_html(summary, filing),
                exporter.generate_csv(summary, filing)]
    for visible in surfaces:
        assert "FORGED SOURCE" not in visible
        assert SUFFIX.strip() in visible
        assert "Preserve this separate risk disclosure." in visible
        if corrected:
            assert claim not in visible
            assert COMPONENT_LIMITATION in visible
            assert "reconciles to" not in visible
            assert "Net income was" not in visible
        else:
            assert claim in visible
    assert (raw.get(CONTEXT_KEY) == 1) is corrected
    if corrected:
        quality = raw["sections"]["earnings_quality"]
        assert "operating_vs_one_time" not in quality and "operatingVsOneTime" not in quality


def test_missing_native_source_keeps_existing_contract_and_clears_model_envelope():
    supplied = sections()
    assert bind_statement_relationship(supplied, None) is False
    assert supplied["earnings_quality"]["operating_vs_one_time"] == CLAIM
    assert OWNED_FIELD not in supplied["earnings_quality"]


def test_actual_supported_explanation_and_separately_quantified_components_are_preserved():
    # Actual unmodified source passage, not a fabricated positive claim.
    source_passage = (
        "Other income (expense), net changed by $71 million for the three months ended "
        "March 31, 2026 compared to the same period in 2025 primarily due to a realized "
        "gain on privately-held equity securities."
    )
    text = " ".join(html.fromstring(original().encode()).itertext())
    assert source_passage in text
    # This is a separate synthetic control with an explicit component amount. The
    # finite ambiguous grammar must not swallow it even when aggregate amounts match.
    quantified = CLAIM.replace("a realized gain on", "a realized gain of $60,000 thousand on")
    for claim in (source_passage, quantified):
        supplied = sections(claim)
        assert bind_statement_relationship(supplied, acquire()) is False
        assert supplied["earnings_quality"]["operating_vs_one_time"] == claim
        assert OWNED_FIELD not in supplied["earnings_quality"]


def test_complete_claim_without_suffix_is_withheld_without_fabricated_continuation():
    supplied = sections(CLAIM.removesuffix(SUFFIX))
    assert bind_statement_relationship(supplied, acquire()) is True
    owned = supplied["earnings_quality"][OWNED_FIELD]
    assert owned["paragraphs"] == [COMPONENT_LIMITATION]
    assert "preserved_authored_suffix" not in owned


@pytest.mark.parametrize("alternate", ["Independent alternate claim.", " ", "", None, CLAIM])
@pytest.mark.parametrize("authored_key", ["operating_vs_one_time", "operatingVsOneTime"])
def test_conflicting_alias_does_not_hide_an_independent_claim(alternate, authored_key):
    supplied = sections()
    quality = supplied["earnings_quality"]
    quality.pop("operating_vs_one_time")
    alternate_key = "operatingVsOneTime" if authored_key == "operating_vs_one_time" else "operating_vs_one_time"
    quality[authored_key], quality[alternate_key] = CLAIM, alternate
    if not alternate or alternate == CLAIM:
        assert bind_statement_relationship(supplied, acquire()) is True
        assert "operating_vs_one_time" not in quality and "operatingVsOneTime" not in quality
    else:
        assert bind_statement_relationship(supplied, acquire()) is False
        assert quality[authored_key] == CLAIM
        assert quality[alternate_key] == alternate
        assert OWNED_FIELD not in quality


@pytest.mark.asyncio
async def test_same_authored_grammar_is_preserved_when_source_separately_quantifies_component():
    document = html.fromstring(original().encode())
    # Synthetic positive control: keep the accepted authored field byte-identical
    # and add a complete separately tagged component disclosure to the real source.
    # This is not alleged to be a disclosure in the original actual PLTR filing.
    fact = copy.deepcopy(node(document, "f-129"))
    fact.set("id", "separate-realized-investment-gain")
    fact.set("name", "us-gaap:GainLossOnSaleOfInvestments")
    paragraph = html.Element("div")
    paragraph.text = "The Company recognized a realized gain on privately-held equity securities of $"
    paragraph.append(fact)
    fact.tail = " thousand for the three months ended March 31, 2026."
    document.xpath("//body")[0].append(paragraph)
    changed = html.tostring(document).decode()
    source = acquire(changed)
    assert source is not None
    assert source["separate_investment_component_amounts"] == [{
        "concept": "us-gaap:GainLossOnSaleOfInvestments", "value": 68209000,
        "fact_id": "separate-realized-investment-gain", "context_id": "c-1", "unit_id": "usd",
    }]
    supplied = {"sections": sections(), "metadata": {}, "schema_version": SUMMARY_SCHEMA_VERSION}
    direct = copy.deepcopy(supplied["sections"])
    assert bind_statement_relationship(direct, source) is False
    assert direct["earnings_quality"]["operating_vs_one_time"] == CLAIM
    service = OpenAIService()
    service.generate_structured_summary = AsyncMock(return_value=copy.deepcopy(supplied))
    result = await service.summarize_filing(changed, "Palantir", "10-Q", statement_source=source)
    preview = service._partial_markdown_preview(json.dumps(supplied), None, statement_source=source)
    assert result["raw_summary"]["sections"]["earnings_quality"]["operating_vs_one_time"] == CLAIM
    assert CONTEXT_KEY not in result["raw_summary"]
    for text in [result["business_overview"], result["management_discussion"], preview]:
        assert CLAIM in text
        assert COMPONENT_LIMITATION not in text
        assert "FORGED SOURCE" not in text
