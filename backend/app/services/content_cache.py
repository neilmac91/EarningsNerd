"""Shared FilingContentCache write helper.

Both summary-generation paths — the SSE pipeline (``summary_pipeline``) and the background/cron
path (``summary_generation_service``) — persist the same cache row for a filing: its edgartools
``sections_payload`` plus the ``critical_excerpt``. The SSE path may also retain an application-built
bounded ``risk_source_text`` when excerpt extraction was unavailable. They carried a byte-identical upsert block;
this is the ONE copy so they can't drift while both paths live (the old path is flag-gated until
the S1 soak completes).

Excerpt is set only on a fresh row, or on an existing row that has none yet — an existing excerpt
is never overwritten here. Deliberate excerpt recomputation/overwrite is owned by
``summary_generation_service.get_or_cache_excerpt`` and is intentionally NOT routed through this
helper (different semantics). The caller commits.
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
            if excerpt and not cache.critical_excerpt:
                cache.critical_excerpt = excerpt
            if risk_source_text and not cache.risk_source_text:
                cache.risk_source_text = risk_source_text
            cache.sections_payload = sections_payload
    elif (excerpt or risk_source_text) and cache is None:
        session.add(FilingContentCache(
            filing_id=filing_id,
            critical_excerpt=excerpt,
            risk_source_text=risk_source_text,
        ))
