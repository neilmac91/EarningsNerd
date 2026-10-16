"""The summary pipeline's per-step budgets fit under its backstop (``PIPELINE_TIMEOUT_SECONDS``).

``summary_pipeline.py`` documents the backstop as sitting above the sum of the per-step budgets, so
the per-step timeouts stay the primary controls and the AI fallback always gets to produce a result
rather than a timeout error. The steps: the document fetch, the enrichment (the section-parse wait and
the excerpt build's floor after it, or the join alone when the parse is quick) and the provider call.
Raising one of them past the backstop fails here (CLAUDE.md rule 12).
"""
import re
from pathlib import Path

from app.services import summary_pipeline as pipeline
from app.services.ai import provider_requests

FETCH_STAGE = Path(pipeline.__file__).with_name("summary_stages") / "fetch.py"


def test_the_per_step_budgets_fit_under_the_pipeline_backstop():
    fetch_timeouts = {
        float(value) for value in
        re.findall(r"get_filing_document\(run\.filing_document_url, timeout=([\d.]+)\)", FETCH_STAGE.read_text())
    }
    assert fetch_timeouts == {15.0}, "the fetch stage's document timeouts changed; update this budget"
    enrichment = max(
        pipeline.CONTEXT_ENRICHMENT_TIMEOUT_SECONDS,
        pipeline.SECTION_PARSE_WAIT_SECONDS + pipeline.EXCERPT_BUILD_SECONDS,
    )
    worst_case = max(fetch_timeouts) + enrichment + provider_requests.SUMMARY_SECONDS
    assert worst_case < pipeline.PIPELINE_TIMEOUT_SECONDS, (
        f"fetch + enrichment + provider = {worst_case}s, not under the {pipeline.PIPELINE_TIMEOUT_SECONDS}s backstop"
    )


def test_the_section_wait_and_the_build_floor_fit_the_enrichment_deadline():
    # The excerpt build keeps EXCERPT_BUILD_SECONDS after the parse wait; a floor above the join itself
    # would make the join's own deadline meaningless.
    assert 0 < pipeline.EXCERPT_BUILD_SECONDS <= pipeline.CONTEXT_ENRICHMENT_TIMEOUT_SECONDS
    assert 0 < pipeline.SECTION_PARSE_WAIT_SECONDS <= pipeline.CONTEXT_ENRICHMENT_TIMEOUT_SECONDS
