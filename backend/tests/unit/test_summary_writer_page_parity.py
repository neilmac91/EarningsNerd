"""No summary writer stores a body the filing page would show as empty (decision C, 2026-10-09).

The filing page strips leading internal notices and a leading "Executive Summary" heading before it
renders a summary (frontend/lib/stripInternalNotices.ts, stripLeadingExecutiveHeading.ts), and shows
the "Summary temporarily unavailable" card when nothing is left. The backend's readiness rule
(summary_placeholders.is_summary_ready: the sitemap, the company search's summary_ready and the
summary route's unready refresh) does not strip notices. The two agree only while no writer emits a
body that is notices and headings alone, so this test drives every writer over degenerate inputs and
holds that invariant: an output is empty, or the page still has something to show.

The page's cleaning is mirrored here from the TypeScript sources, whose notice patterns are read
from the file itself, so a new notice there cannot slip past this check.
"""
import re
from pathlib import Path

import pytest

from app.services.fallback_summary import generate_xbrl_summary
from app.services.openai_service import openai_service
from app.services.provenance_service import replace_business_overview_risks
from app.services.summary_placeholders import is_summary_ready
from app.services.summary_sections import render_sections, sections_to_markdown

FRONTEND_LIB = Path(__file__).resolve().parents[3] / "frontend" / "lib"


def _notice_patterns() -> list[re.Pattern]:
    source = (FRONTEND_LIB / "stripInternalNotices.ts").read_text(encoding="utf8")
    # The array literal, one regex literal per line, up to its closing bracket on a line of its own.
    block = re.search(r"disclaimerPatterns = \[\n(.*?)\n\s*\]\n", source, re.S)
    assert block, "stripInternalNotices.ts: disclaimerPatterns array"
    lines = [line.strip() for line in block.group(1).splitlines() if line.strip()]
    literals = [re.fullmatch(r"/(.+)/([a-z]*),?", line) for line in lines]
    assert lines and all(literals), f"stripInternalNotices.ts: unreadable notice patterns {lines!r}"
    return [re.compile(m.group(1), re.I if "i" in m.group(2) else 0) for m in literals]


def _exec_heading_pattern() -> re.Pattern:
    source = (FRONTEND_LIB / "stripLeadingExecutiveHeading.ts").read_text(encoding="utf8")
    match = re.search(r"/(\^#\{1,6\}.*?)/([a-z]*)\.test", source)
    assert match, "stripLeadingExecutiveHeading.ts: heading regex literal"
    return re.compile(match.group(1), re.I if "i" in match.group(2) else 0)


NOTICES = _notice_patterns()
EXEC_HEADING = _exec_heading_pattern()


def page_markdown(markdown: str) -> str:
    """cleanSummaryMarkdown: stripLeadingExecutiveHeading(stripInternalNotices(markdown))."""
    lines = (markdown or "").split("\n")
    start = 0
    while start < len(lines):
        trimmed = lines[start].strip()
        if not trimmed or any(p.search(trimmed) for p in NOTICES):
            start += 1
            continue
        break
    lines = lines[start:]
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and EXEC_HEADING.search(lines[i].strip()):
        del lines[i]
    return "\n".join(lines)


def test_the_mirror_cleans_as_the_page_does():
    # The frontend spec's own empty case (summaryPlaceholder.spec.ts) and a body with content.
    assert page_markdown("*Auto-generated from structured data*\n\n## Executive Summary\n").strip() == ""
    assert page_markdown("## Executive Summary\n\nApple designs devices.").strip() == "Apple designs devices."
    assert page_markdown("## Financials\n- Revenue").startswith("## Financials")


def _structured(**sections):
    return {"metadata": {"company_name": "Acme", "filing_type": "10-K"}, "sections": sections}


STRUCTURED_INPUTS = [
    {},
    _structured(),
    _structured(executive_snapshot={"headline": "   "}),
    _structured(executive_snapshot=["not", "a", "dict"], financial_highlights="nor this"),
    _structured(executive_snapshot={"headline": "Revenue grew.", "key_points": "One point"}),
]

V2_ENVELOPES = [
    {"schema_version": 2, "sections": {}},
    {"schema_version": 2, "sections": {"the_print": {}, "risks": []}},
    {"schema_version": 2, "sections": {"the_print": {"headline": "  ", "summary": ""}}},
    {"schema_version": 2, "sections": {"the_print": {"headline": "Revenue grew 12%."}}},
]

XBRL_INPUTS = [
    None,
    {},
    {"revenue": {"current": {"value": 1_000_000_000, "period": "FY2025"}}},
]


def _writer_outputs():
    for index, payload in enumerate(STRUCTURED_INPUTS):
        for reason in (None, "schema mismatch"):
            yield f"structured[{index}] reason={reason}", openai_service._build_structured_markdown(payload, reason)
    for index, envelope in enumerate(V2_ENVELOPES):
        yield f"sections[{index}]", sections_to_markdown(render_sections(envelope))
    for index, xbrl in enumerate(XBRL_INPUTS):
        yield f"xbrl[{index}]", generate_xbrl_summary(xbrl, "Acme", filing_type="10-Q")["business_overview"]


@pytest.mark.parametrize(("name", "markdown"), list(_writer_outputs()))
def test_every_writer_body_is_empty_or_shows_content(name, markdown):
    # _finalize_summary_projection passes every writer's body through the risk projection.
    for body in (markdown, replace_business_overview_risks(markdown, None)):
        shown = page_markdown(body).strip()
        assert body.strip() == "" or shown, f"{name}: the page would show nothing for {body!r}"
        assert is_summary_ready(body) == bool(shown), f"{name}: backend and page readiness disagree"
