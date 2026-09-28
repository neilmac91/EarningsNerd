"""The five held source-scope counterexamples never authorize financial reconstruction.

The held tests and snapshot remain unchanged in their original branch. This new
contract permits only the capability limitation, not the previous statement prose.
"""
import copy
import json
from unittest.mock import AsyncMock

from lxml import html
import pytest

from app.services.ai.statement_relationship import COMPONENT_LIMITATION, OWNED_FIELD
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from tests.unit.test_quarterly_component_withholding import CLAIM, SUFFIX, acquire, original, sections


@pytest.mark.asyncio
@pytest.mark.parametrize("location", [
    "heading_tail", "before_heading", "enclosing_block", "wrapper_tail", "before_page_hr",
])
async def test_governing_source_qualifications_only_allow_explicit_withholding(location):
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
    supplied = {"sections": sections(), "metadata": {}}
    service.generate_structured_summary = AsyncMock(return_value=copy.deepcopy(supplied))
    result = await service.summarize_filing(changed, "Palantir", "10-Q", statement_source=context)
    raw = result["raw_summary"]
    from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    preview = service._partial_markdown_preview(json.dumps(supplied), None, statement_source=context)
    owned = raw["sections"]["earnings_quality"][OWNED_FIELD]
    assert owned["paragraphs"] == [COMPONENT_LIMITATION]
    assert owned["preserved_authored_suffix"] == SUFFIX
    for visible in [result["business_overview"], result["management_discussion"], preview,
                    sections_to_markdown(render_sections(raw))]:
        assert COMPONENT_LIMITATION in visible
        assert CLAIM not in visible
        assert SUFFIX.strip() in visible
        assert "Net income was" not in visible
        assert "reconciles to" not in visible
        assert "Unaudited consolidated statement" not in visible
