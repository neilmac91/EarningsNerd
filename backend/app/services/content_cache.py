"""Shared FilingContentCache write helper.

Both summary-generation paths — the SSE pipeline (``summary_pipeline``) and the background/cron
path (``summary_generation_service``) — persist the same cache row for a filing: its edgartools
``sections_payload`` plus the ``critical_excerpt``. The SSE path may also retain an application-built
bounded ``risk_source_text`` when excerpt extraction was unavailable. They carried a byte-identical upsert block;
this is the ONE copy so they can't drift while both paths live (the old path is flag-gated until
the S1 soak completes).

Excerpt is set on a fresh row, or on an existing row that has none yet, except that a forced run
that writes its summary (``replace_excerpt``) replaces the stored excerpt with the one it built and
was generated from, in the same commit: a forced run never stores its excerpt before then
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
            if risk_source_text and (replace_risk_source or not cache.risk_source_text):
                cache.risk_source_text = risk_source_text
            cache.sections_payload = sections_payload
    elif (excerpt or risk_source_text) and cache is None:
        session.add(FilingContentCache(
            filing_id=filing_id,
            critical_excerpt=excerpt,
            risk_source_text=risk_source_text,
        ))
