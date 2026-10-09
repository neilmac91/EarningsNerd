"""Canonical detector for an AI summary body that is not-ready placeholder filler.

A summary's ``business_overview`` sometimes holds interim/error filler ("generating summary…",
"summary temporarily unavailable", "requires OpenAI API key") instead of real analysis. Both the
dashboard feed and the watchlist need to recognize that state to label the summary "placeholder"
and offer regeneration — this is the ONE home for those tokens so the two surfaces can't drift.

Deliberately NARROW — the interim/error summary *body*. It is NOT the section-level "Not
disclosed"/"N/A" placeholders (``ai/normalize._PLACEHOLDER_STRINGS``, exact-match), the
frontend-mirrored export filter (``summary_sections.PLACEHOLDER_PATTERNS``), or the coverage
failure-detection list (``summary_generation_service``). Those are separate, context-specific
checks with their own token sets and match semantics; consolidating them here would change behavior.
"""
from typing import Optional

# Substrings that mark a summary body as interim/error filler rather than real content.
SUMMARY_PLACEHOLDER_TOKENS = (
    "generating summary",
    "summary temporarily unavailable",
    "requires openai api key",
)


def is_summary_placeholder(text: Optional[str]) -> bool:
    """True when a summary body is interim/error placeholder filler (case-insensitive substring)."""
    lowered = (text or "").lower()
    return any(token in lowered for token in SUMMARY_PLACEHOLDER_TOKENS)


# Whether the filing page shows a stored summary's body: the rule its display, its metadata
# (noindex, description), the sitemap and the company search apply, mirrored by the frontend's
# features/summaries/lib/summaryPlaceholder.ts (summaryPlaceholder.spec holds the two equal).
#
# The in-progress marker an earlier pipeline stored mid-run, matched case-sensitively as the filing
# page and the sitemap always have, so prose about "generating summary reports" stays content.
IN_PROGRESS_MARKER = "Generating summary"
# The other tokens mark a stored failure, which the page shows as its "Summary temporarily
# unavailable" card. Real analysis never carries them.
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
