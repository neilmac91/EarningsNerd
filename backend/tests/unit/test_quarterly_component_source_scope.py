"""The five held source-scope counterexamples never authorize financial reconstruction.

The held tests and snapshot remain unchanged in their original branch. This new
contract permits only the capability limitation, not the previous statement prose.
"""
import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from lxml import html
import pytest

from app.services.ai.statement_relationship import CAUSE_LIMITATION, COMPONENT_LIMITATION, OWNED_FIELD
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from tests.unit.test_quarterly_component_withholding import (
    CAUSE_CLAIM, CAUSE_PREFIX, CAUSE_SUFFIX, CLAIM, SUFFIX, acquire, original, sections,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("location", [
    "heading_tail", "before_heading", "enclosing_block", "wrapper_tail", "before_page_hr",
])
@pytest.mark.parametrize("claim,suffix,limitation", [
    (CLAIM, SUFFIX, COMPONENT_LIMITATION), (CAUSE_CLAIM, CAUSE_SUFFIX, CAUSE_LIMITATION),
])
async def test_governing_source_qualifications_only_allow_explicit_withholding(location, claim, suffix, limitation):
    document = html.fromstring(original().encode())
    table = document.xpath('/html/body/div[56]/table')[0]
    wrapper = table.getparent()
    heading = wrapper.getprevious()
    hypothetical = "The following statement is hypothetical and does not report actual results."
    if location == "heading_tail":
        heading.tail = hypothetical
    elif location == "before_heading":
        qualifier = html.Element("div")
        qualifier.text = hypothetical
        heading.addprevious(qualifier)
    elif location == "enclosing_block":
        parent = wrapper.getparent()
        region = html.Element("section")
        region.text = "The following statement has been withdrawn and must not be treated as reported results."
        parent.insert(parent.index(heading), region)
        region.append(heading)
        region.append(wrapper)
    elif location == "wrapper_tail":
        wrapper.tail = "The preceding statement has been withdrawn and must not be treated as reported results."
    else:
        boundary = heading.getprevious()
        assert boundary.tag == "hr"
        qualifier = html.Element("div")
        qualifier.text = "The statement on the following page is hypothetical and does not report actual results."
        boundary.addprevious(qualifier)
    changed = html.tostring(document).decode()
    context = acquire(changed)
    assert context is not None  # matching is possible; assertion authority is not established
    assert context["assertion_scope"] == "not_established"
    service = OpenAIService()
    supplied = {"sections": sections(claim), "metadata": {}}
    service.generate_structured_summary = AsyncMock(return_value=copy.deepcopy(supplied))
    result = await service.summarize_filing(changed, "Palantir", "10-Q", statement_source=context)
    raw = result["raw_summary"]
    from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    preview = service._partial_markdown_preview(json.dumps(supplied), None, statement_source=context)
    owned = raw["sections"]["earnings_quality"][OWNED_FIELD]
    assert owned["paragraphs"] == [limitation]
    assert owned["preserved_authored_suffix"] == suffix
    for visible in [result["business_overview"], result["management_discussion"], preview,
                    sections_to_markdown(render_sections(raw))]:
        assert limitation in visible
        assert claim not in visible
        assert suffix.strip() in visible
        if claim == CAUSE_CLAIM:
            assert CAUSE_PREFIX + "." in visible
            assert owned["preserved_authored_prefix"] == CAUSE_PREFIX + "."
        assert "Net income was" not in visible
        assert "reconciles to" not in visible
        assert "Unaudited consolidated statement" not in visible


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "quarterly", "quarterly_qualified", "quarterly_cause_exclusion", "annual", "absent", "unknown_kind", "no_kind", "empty",
])
async def test_actual_judge_and_acceptance_consumers_omit_only_quarterly_operands(monkeypatch, case):
    from app.services.edgar.statement_context import acquire_statement_context
    from evals import acceptance_ai_decision, judge, runner
    from tests.unit.test_statement_relationship_source import SOURCES, original as annual_original

    if case.startswith("quarterly"):
        document = html.fromstring(original().encode())
        if case == "quarterly_qualified":
            document.xpath('/html/body/div[56]/table')[0].getparent().getprevious().tail = (
                "The following statement is hypothetical and does not report actual results."
            )
        if case == "quarterly_cause_exclusion":
            paragraph = html.Element("div")
            paragraph.text = CAUSE_CLAIM.removesuffix(CAUSE_SUFFIX)
            document.xpath("//body")[0].append(paragraph)
        source = acquire(html.tostring(document).decode())
        assert source is not None and source["assertion_scope"] == "not_established"
        if case == "quarterly_cause_exclusion":
            assert source["complete_other_income_explanations"] == [{"component": "gain", "asset": "privately-held"}]
    elif case == "annual":
        source = acquire_statement_context(
            annual_original("meli").decode(), accession=SOURCES["meli"][0],
            document_url="https://example.test/primary.htm", form="10-K", report_period="2025-12-31",
        )
        assert source is not None
    else:
        source = {"absent": None, "empty": {},
                  "unknown_kind": {"kind": "legacy_other", "assertion_scope": "not_established"},
                  "no_kind": {"legacy": "source"}}[case]
    excerpt = "ORIGINAL GENERATOR EXCERPT"
    canonical = {"business_overview": "Review control"}
    payload = runner._baseline_to_canonical(canonical)
    filing = SimpleNamespace(company_name="Issuer", filing_type="10-Q" if case.startswith("quarterly") else "10-K")
    # Preexisting annex bytes, independent of the new shared eligibility helper.
    expected_excerpt = excerpt
    if source and not case.startswith("quarterly"):
        expected_excerpt += (
            "\n\n[APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE; independent of the generator excerpt]\n"
            + json.dumps(source, ensure_ascii=False, sort_keys=True)
            + "\n[END APPLICATION-OWNED PRIMARY-STATEMENT EVIDENCE]"
        )
    expected_messages = judge.build_judge_messages(payload, "Issuer", filing.filing_type, expected_excerpt, "")
    spy = AsyncMock(return_value=judge.JudgeVerdict(verdict="PASS"))
    monkeypatch.setattr(runner, "judge_summary", spy)
    await runner._maybe_judge(
        "offline-spy", payload, filing, {"excerpt": excerpt, "xbrl_metrics": None, "statement_source": source},
    )
    spy.assert_awaited_once()
    assert judge.build_judge_messages(*spy.call_args.args) == expected_messages
    grounding = {"summarizer_calls": [{
        "args": ["ignored-source", "Issuer", filing.filing_type],
        "kwargs": {"filing_excerpt": excerpt, "statement_source": source, "xbrl_metrics": None},
    }]}
    assert acceptance_ai_decision._judge_input_sha(canonical, grounding) == hashlib.sha256(
        expected_messages[1].encode()
    ).hexdigest()
