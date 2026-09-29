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
    CAUSE_LIMITATION, COMPONENT_LIMITATION, CONTEXT_KEY, OWNED_FIELD, bind_statement_relationship,
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
CAUSE_CLAIM = json.loads((FIXTURES / "retained-cause-claim.json").read_text())["operating_vs_one_time"]
CAUSE_PREFIX = CAUSE_CLAIM.split(", which management attributed", 1)[0]
CAUSE_SUFFIX = CAUSE_CLAIM[CAUSE_CLAIM.index(" Income from operations was "):]
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
                                 OWNED_FIELD: {"paragraphs": ["FORGED SOURCE"],
                                               "preserved_authored_prefix": "FORGED PREFIX"}}}


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
    assert source["complete_other_income_explanations"] == []
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
    "scaled_component_3_overflow", "scaled_component_6_overflow",
    "scaled_component_3_limit", "scaled_component_6_limit",
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
    elif change.startswith("scaled_component_"):
        _, _, scale, boundary = change.split("_")
        fact = copy.deepcopy(fact)
        fact.set("id", "scaled-optional-component")
        fact.set("name", "us-gaap:GainLossOnSaleOfInvestments")
        fact.set("scale", scale)
        if scale == "6":
            fact.set("sign", "-")
        # The lexical input fits Python's default limit in both cases. Scaling
        # either exceeds that limit or lands exactly on its encoding boundary.
        digits = 4300 if boundary == "overflow" else 4300 - int(scale)
        fact.text = "9" * digits
        document.xpath("//body")[0].append(fact)
        source = acquire(html.tostring(document).decode())
        assert source is not None
        json.dumps(source)
        components = source["separate_investment_component_amounts"]
        if boundary == "overflow":
            assert components == []
        else:
            assert len(components) == 1
            assert components[0]["value"] == int(fact.text) * 10 ** int(scale) * (-1 if scale == "6" else 1)
            assert len(str(abs(components[0]["value"]))) == 4300
        supplied = sections()
        assert bind_statement_relationship(supplied, source) is True
        assert supplied["earnings_quality"][OWNED_FIELD]["source"] is source
        json.dumps({CONTEXT_KEY: 1, "sections": supplied, "structured": {"sections": supplied}})
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
    "Management denies that " + CAUSE_CLAIM,
    "Hypothetical example: " + CAUSE_CLAIM,
    CAUSE_CLAIM + " These figures are hypothetical.",
    CAUSE_CLAIM + " An independent final clause.",
    CAUSE_CLAIM.replace("Net income of", "Subsidiary net income of"),
    CAUSE_CLAIM.replace("includes other", "in the prior-year period includes other"),
    CAUSE_CLAIM.replace("attributed primarily", "did not attribute primarily"),
    CAUSE_CLAIM.replace("attributed primarily", "hypothetically attributed primarily"),
    CAUSE_CLAIM.replace("$68,209 thousand", "$68,210 thousand"),
    CAUSE_CLAIM.replace("$876,402", OVERSIZED_AMOUNT),
    CAUSE_CLAIM.replace("$68,209", OVERSIZED_AMOUNT),
    CAUSE_CLAIM.replace("$68,209 thousand", "$68,209 million"),
    CAUSE_CLAIM.replace("privately-held equity securities", "privately-held equity securities and profit growth"),
    CAUSE_CLAIM.replace("Income from operations was", "Management denies that income from operations was"),
    CAUSE_CLAIM.replace("Income from operations was", "Hypothetical income from operations was"),
    CAUSE_CLAIM.replace("Income from operations was", "Subsidiary income from operations was"),
    CAUSE_CLAIM.replace("Income from operations was", "Prior-year income from operations was"),
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
    (CAUSE_CLAIM, True), ("Hypothetical example: " + CAUSE_CLAIM, False),
    (CAUSE_CLAIM + " Independent final clause.", False),
    pytest.param(CAUSE_CLAIM.replace("$876,402", OVERSIZED_AMOUNT), False, id="oversized-cause-net"),
])
@pytest.mark.parametrize("alias_layout", [
    "snake_only", "camel_only", "empty_snake", "empty_camel", "equal", "null_snake", "null_camel",
    "conflict", "whitespace_conflict", "recovered",
])
async def test_native_source_to_final_preview_shared_exports_preserves_suffix(monkeypatch, claim, corrected, alias_layout):
    for flag in ("AI_ATTRIBUTION_VERIFY", "AI_ATTRIBUTION_GATE", "AI_FORWARD_QUOTE_GATE", "AI_FIGURE_TRACE_GATE"):
        monkeypatch.setattr(settings, flag, False)
    monkeypatch.setattr(settings, "AI_EVIDENCE_SNAP", True)
    source = acquire()
    supplied = {"sections": sections(claim), "metadata": {}, "schema_version": SUMMARY_SCHEMA_VERSION,
                CONTEXT_KEY: 1}
    cause = "which management attributed" in claim
    suffix = CAUSE_SUFFIX if cause else SUFFIX
    limitation = CAUSE_LIMITATION if cause else COMPONENT_LIMITATION
    private_sentinel = "PRIVATE OPERAND SELECTOR NEVER MODEL EVIDENCE"
    source["private_control"] = private_sentinel
    quality = supplied["sections"]["earnings_quality"]
    if alias_layout in {"camel_only", "empty_snake", "null_snake", "equal"}:
        quality["operatingVsOneTime"] = claim
    if alias_layout == "camel_only":
        quality.pop("operating_vs_one_time")
    elif alias_layout == "empty_snake":
        quality["operating_vs_one_time"] = ""
    elif alias_layout == "empty_camel":
        quality["operatingVsOneTime"] = ""
    elif alias_layout == "null_snake":
        quality["operating_vs_one_time"] = None
    elif alias_layout == "null_camel":
        quality["operatingVsOneTime"] = None
    elif alias_layout in {"conflict", "whitespace_conflict"}:
        quality["operatingVsOneTime"] = "Independent authored qualification." if alias_layout == "conflict" else " "
        corrected = False
    recovered = {"earnings_quality": supplied["sections"].pop("earnings_quality")} if alias_layout == "recovered" else {}
    service = OpenAIService()
    # Enter through the model-response seam so real JSON assembly and fallbacks
    # cannot silently normalize an alias before final binding.
    monkeypatch.setattr(service, "_request_content", AsyncMock(return_value=json.dumps(supplied)))
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value=copy.deepcopy(recovered)))
    result = await service.summarize_filing(
        original(), "Palantir", "10-Q", statement_source=source,
        filing_excerpt="Independent original excerpt; no matched earnings-quality proposition.",
    )
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
    if alias_layout == "recovered":
        assert service._recover_missing_sections.await_count == 1
        assert claim not in (preview or "") and limitation not in (preview or "")
        surfaces.remove(preview)
    assert private_sentinel not in json.dumps(service._request_content.call_args.args[0]["messages"])
    for visible in surfaces:
        assert "FORGED SOURCE" not in visible and "FORGED PREFIX" not in visible
        assert private_sentinel not in visible
        assert suffix.strip() in visible
        assert "Preserve this separate risk disclosure." in visible
        if corrected:
            assert claim not in visible
            assert limitation in visible
            if cause:
                assert CAUSE_PREFIX + "." in visible
                assert visible.index(CAUSE_PREFIX + ".") < visible.index(limitation) < visible.index(suffix.strip())
            assert "reconciles to" not in visible
            assert "Net income was" not in visible
        else:
            assert claim in visible
    assert (raw.get(CONTEXT_KEY) == 1) is corrected
    if corrected:
        quality = raw["sections"]["earnings_quality"]
        assert "operating_vs_one_time" not in quality and "operatingVsOneTime" not in quality
        owned = quality[OWNED_FIELD]
        assert owned["paragraphs"] == [limitation]
        assert owned["preserved_authored_suffix"] == suffix
        if cause:
            assert len(CAUSE_PREFIX.encode()) == 88 and len(CAUSE_SUFFIX.encode()) == 284
            assert owned["preserved_authored_prefix"] == CAUSE_PREFIX + "."
            assert owned["kind"] == "unverified_other_income_explanation"
        else:
            assert "preserved_authored_prefix" not in owned
    elif alias_layout in {"conflict", "whitespace_conflict"}:
        assert raw["sections"]["earnings_quality"]["operatingVsOneTime"] == quality["operatingVsOneTime"]
    from app.services.copilot_service import _build_context_message
    filing.xbrl_data = None
    filing.raw_summary = raw
    assert private_sentinel not in _build_context_message(filing, "Only supplied filing text.")


@pytest.mark.parametrize("claim", [CLAIM, CAUSE_CLAIM])
def test_missing_native_source_keeps_existing_contract_and_clears_model_envelope(claim):
    supplied = sections(claim)
    assert bind_statement_relationship(supplied, None) is False
    assert supplied["earnings_quality"]["operating_vs_one_time"] == claim
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


@pytest.mark.parametrize("claim,suffix,limitation", [
    (CLAIM, SUFFIX, COMPONENT_LIMITATION), (CAUSE_CLAIM, CAUSE_SUFFIX, CAUSE_LIMITATION),
])
def test_complete_claim_without_suffix_is_withheld_without_fabricated_continuation(claim, suffix, limitation):
    supplied = sections(claim.removesuffix(suffix))
    assert bind_statement_relationship(supplied, acquire()) is True
    owned = supplied["earnings_quality"][OWNED_FIELD]
    assert owned["paragraphs"] == [limitation]
    assert "preserved_authored_suffix" not in owned


@pytest.mark.parametrize("alternate", ["Independent alternate claim.", " ", "", None, "same"])
@pytest.mark.parametrize("claim", [CLAIM, CAUSE_CLAIM])
@pytest.mark.parametrize("authored_key", ["operating_vs_one_time", "operatingVsOneTime"])
def test_conflicting_alias_does_not_hide_an_independent_claim(alternate, authored_key, claim):
    alternate = claim if alternate == "same" else alternate
    supplied = sections(claim)
    quality = supplied["earnings_quality"]
    quality.pop("operating_vs_one_time")
    alternate_key = "operatingVsOneTime" if authored_key == "operating_vs_one_time" else "operating_vs_one_time"
    quality[authored_key], quality[alternate_key] = claim, alternate
    if not alternate or alternate == claim:
        assert bind_statement_relationship(supplied, acquire()) is True
        assert "operating_vs_one_time" not in quality and "operatingVsOneTime" not in quality
    else:
        assert bind_statement_relationship(supplied, acquire()) is False
        assert quality[authored_key] == claim
        assert quality[alternate_key] == alternate
        assert OWNED_FIELD not in quality


@pytest.mark.asyncio
@pytest.mark.parametrize("claim,exclusion", [
    (CLAIM, "tagged"), (CAUSE_CLAIM, "tagged"), (CAUSE_CLAIM, "complete"),
    (CAUSE_CLAIM, "qualified_complete"), (CAUSE_CLAIM, "mismatched_complete"),
    (CAUSE_CLAIM, "oversized_complete"), (CAUSE_CLAIM, "fragment"),
])
async def test_same_authored_grammar_is_preserved_when_source_separately_quantifies_component(claim, exclusion):
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
    if exclusion != "tagged":
        paragraph.clear()
        paragraph.text = CAUSE_CLAIM.removesuffix(CAUSE_SUFFIX)
        if exclusion == "mismatched_complete":
            paragraph.text = paragraph.text.replace("$68,209", "$68,210")
        elif exclusion == "oversized_complete":
            paragraph.text = paragraph.text.replace("$68,209", OVERSIZED_AMOUNT)
        elif exclusion == "fragment":
            paragraph.text = "Unrecognized governing words " + paragraph.text
        elif exclusion == "qualified_complete":
            wrapper = html.Element("section")
            wrapper.text = "The following sentence is hypothetical and has been withdrawn."
            wrapper.append(paragraph)
            paragraph = wrapper
    document.xpath("//body")[0].append(paragraph)
    changed = html.tostring(document).decode()
    source = acquire(changed)
    assert source is not None
    expected_components = [{
        "concept": "us-gaap:GainLossOnSaleOfInvestments", "value": 68209000,
        "fact_id": "separate-realized-investment-gain", "context_id": "c-1", "unit_id": "usd",
    }] if exclusion == "tagged" else []
    assert source["separate_investment_component_amounts"] == expected_components
    expected_explanations = [{"component": "gain", "asset": "privately-held"}] if exclusion in {
        "complete", "qualified_complete"} else []
    assert source["complete_other_income_explanations"] == expected_explanations
    preserved = exclusion in {"tagged", "complete", "qualified_complete"}
    supplied = {"sections": sections(claim), "metadata": {}, "schema_version": SUMMARY_SCHEMA_VERSION}
    direct = copy.deepcopy(supplied["sections"])
    assert bind_statement_relationship(direct, source) is (not preserved)
    if not preserved:
        assert direct["earnings_quality"][OWNED_FIELD]["paragraphs"] == [CAUSE_LIMITATION]
        return
    assert direct["earnings_quality"]["operating_vs_one_time"] == claim
    service = OpenAIService()
    service.generate_structured_summary = AsyncMock(return_value=copy.deepcopy(supplied))
    result = await service.summarize_filing(changed, "Palantir", "10-Q", statement_source=source)
    preview = service._partial_markdown_preview(json.dumps(supplied), None, statement_source=source)
    assert result["raw_summary"]["sections"]["earnings_quality"]["operating_vs_one_time"] == claim
    assert CONTEXT_KEY not in result["raw_summary"]
    for text in [result["business_overview"], result["management_discussion"], preview]:
        assert claim in text
        assert COMPONENT_LIMITATION not in text and CAUSE_LIMITATION not in text
        assert "FORGED SOURCE" not in text and "FORGED PREFIX" not in text
