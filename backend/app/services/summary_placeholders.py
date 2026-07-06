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
