"""Canonical detector for an AI summary body that is not-ready placeholder filler.

A summary's ``business_overview`` sometimes holds interim/error filler ("generating summary…",
"summary temporarily unavailable", "requires OpenAI API key") instead of real analysis. This is the
ONE home for those tokens and for the rule the filing page shows a stored summary by
(``is_summary_ready``), which the dashboard feed and the watchlist label their summary status by
(``is_stored_summary_ready``), so the surfaces can't drift.

Deliberately NARROW — the interim/error summary *body*. It is NOT the section-level "Not
disclosed"/"N/A" placeholders (``ai/normalize._PLACEHOLDER_STRINGS``, exact-match), the
frontend-mirrored export filter (``summary_sections.PLACEHOLDER_PATTERNS``), or the coverage
failure-detection list (``summary_generation_service``). Those are separate, context-specific
checks with their own token sets and match semantics; consolidating them here would change behavior.
"""
from typing import Any, Optional

from app.services.provenance_service import source_safe_business_overview

# Substrings that mark a summary body as interim/error filler rather than real content.
SUMMARY_PLACEHOLDER_TOKENS = (
    "generating summary",
    "summary temporarily unavailable",
    "requires openai api key",
)


# Whether the filing page shows a stored summary's body: the rule its display, its metadata
# (noindex, description), the sitemap and the company search apply, mirrored by the frontend's
# features/summaries/lib/summaryPlaceholder.ts (summaryPlaceholder.spec holds the two equal).
#
# The in-progress marker an earlier pipeline stored mid-run, matched case-sensitively as the filing
# page and the sitemap always have, so prose about "generating summary reports" stays content.
IN_PROGRESS_MARKER = "Generating summary"
# The other tokens mark a stored failure, which the page shows as its stored-failure card ("This
# summary did not finish"). Real analysis never carries them.
SUMMARY_FAILURE_TOKENS = tuple(token for token in SUMMARY_PLACEHOLDER_TOKENS if token != "generating summary")


def is_summary_ready(overview: Optional[str], writer_error: object = None) -> bool:
    """True when the filing page shows this stored summary's body: a non-empty body that is neither the
    in-progress marker nor failure filler, with no ``raw_summary.writer_error``."""
    text = (overview or "").strip()
    lowered = text.lower()
    return (
        bool(text)
        and IN_PROGRESS_MARKER not in text
        and not any(token in lowered for token in SUMMARY_FAILURE_TOKENS)
        and not writer_error
    )


def is_stored_summary_ready(summary: Any) -> bool:
    """``is_summary_ready`` for a stored Summary row, on the body the filing page is served
    (``source_safe_business_overview``), its writer error read from ``raw_summary`` (E221). The watchlist insights
    label the row Ready by it, else Unavailable (``placeholder``), for the watchlist card's chip and the dashboard's
    Your companies rows; the dashboard feed labels its card's link by it (``_summary_status``), "Read summary" or
    else "Regenerate summary". Each then says what the filing page shows.

    A writer error is never ready. A body ready as stored is read as stored, since serving rewrites only its Risks
    section. Any other is read as served: an empty body is served the row's sections, rendered, or its legacy risk
    list instead, and a Risks section is replaced, whatever it carried. The body is rendered without the filing,
    whose text decides only which excerpts the Risks section quotes, never whether there is a body, so the rule
    reads the row's own columns alone, with no query. It departs from the page's reading in one case: a quoted
    excerpt that itself carries the filler or the marker, which the filing's own text would have to contain."""
    raw = getattr(summary, "raw_summary", None)
    if isinstance(raw, dict) and raw.get("writer_error"):
        return False
    body = getattr(summary, "business_overview", None)
    if is_summary_ready(body):
        return True
    return is_summary_ready(source_safe_business_overview(summary, None))
