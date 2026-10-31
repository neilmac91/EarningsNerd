"""The FilingContentCache write of the one summary orchestrator's finalize stage.

Finalize (``summary_stages.finalize``, which the SSE endpoint and the background/cron path both reach
through ``summary_pipeline.stream_filing_summary``) is this helper's only caller. It persists a filing's
cache row in the commit that writes the summary: the edgartools ``sections_payload``, the
``critical_excerpt``, and an application-built bounded ``risk_source_text`` when excerpt extraction was
unavailable.

Excerpt is set on a fresh row, or on an existing row that has none yet, except that a forced run
that writes its summary (``replace_excerpt``) stores the excerpt it was generated from in place of the
stored one, in the same commit: a stored excerpt is what citation verification, the Risks projection
and Copilot read the summary against. A forced run that ends with no excerpt (its excerpt thread
raised, its build returned nothing, or the enrichment join dropped it) keeps the stored one, the same
filing's text and the grounding it would have reused, unless it was asked to rebuild that excerpt
(``clear_stale_excerpt``: a forced precompute's ``rebuild_excerpt``, whose stored excerpt an older
extraction built); that run clears it. A forced run never stores its excerpt before then
(``get_or_cache_excerpt(persist=False)``). An unforced run's excerpt is cached by
``summary_generation_service.get_or_cache_excerpt`` when it is built. A successful forced summary
refresh explicitly replaces its bounded Risks source; an ordinary write fills that source only when
absent. The caller commits.
"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import FilingContentCache


def upsert_content_cache(
    session: Session,
    filing_id: int,
    cache: Optional[FilingContentCache],
    *,
    excerpt: Optional[str],
    sections_payload: Optional[Any],
    risk_source_text: Optional[str] = None,
    replace_risk_source: bool = False,
    replace_excerpt: bool = False,
    clear_stale_excerpt: bool = False,
) -> None:
    """Attach or refresh application-owned fields on a filing's FilingContentCache row.

    ``cache`` is the filing's currently-loaded ``content_cache`` (or None). No row is created when
    there is nothing to persist (no sections payload and either no excerpt or an excerpt already
    cached) — matching the previously-inlined behavior exactly.
    """
    if sections_payload:
        if cache is None:
            session.add(
                FilingContentCache(
                    filing_id=filing_id,
                    critical_excerpt=excerpt,
                    sections_payload=sections_payload,
                    risk_source_text=risk_source_text,
                )
            )
        else:
            if excerpt and (replace_excerpt or not cache.critical_excerpt):
                cache.critical_excerpt = excerpt
            elif clear_stale_excerpt and not excerpt:
                cache.critical_excerpt = None
            if risk_source_text and (replace_risk_source or not cache.risk_source_text):
                cache.risk_source_text = risk_source_text
            cache.sections_payload = sections_payload
    elif (excerpt or risk_source_text) and cache is None:
        session.add(FilingContentCache(
            filing_id=filing_id,
            critical_excerpt=excerpt,
            risk_source_text=risk_source_text,
        ))
