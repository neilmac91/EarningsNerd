"""Summary schema + prompt version stamps.

Every generated ``Summary`` row records the ``SUMMARY_SCHEMA_VERSION`` (the shape of
``raw_summary["sections"]`` — the sections taxonomy) and the ``SUMMARY_PROMPT_VERSION`` (the
generation prompt text) it was produced under. That lets a change to either identify and refresh
stale rows in place, instead of stranding a pre-change ``business_overview`` — the exact failure
mode behind the shipped-but-unseen ".;" fix (a serializer fix that never reached already-generated
summaries because nothing marked them stale). Mirrors ``trend_analysis_service.PROMPT_VERSION``.

Bump ``SUMMARY_SCHEMA_VERSION`` when the ``sections`` shape changes (v2 = the content
re-architecture in Tier 3). Bump ``SUMMARY_PROMPT_VERSION`` on any change to
``backend/prompts/*-agent.md`` that alters generated content. Bumping either makes prior rows
version-stale; the admin ``refresh-stale`` endpoint and the background drain regenerate them in
place (preserving ``summaries.id`` so saved-summary bookmarks survive).

NULL columns on a row (legacy / pre-stamp) are always treated as stale.
"""

# The sections taxonomy shape currently produced by the pipeline. v1 = the 9-section taxonomy
# tracked by openai_service._TRACKED_STRUCTURED_SECTIONS.
SUMMARY_SCHEMA_VERSION: int = 1

# The generation-prompt version. Bump on any content-affecting change to the *-agent.md prompts.
SUMMARY_PROMPT_VERSION: str = "summary-2026-07-a"


def is_stale(schema_version: int | None, prompt_version: str | None) -> bool:
    """A stored summary is stale when either stamp is missing or behind the current version."""
    if schema_version is None or prompt_version is None:
        return True
    return schema_version != SUMMARY_SCHEMA_VERSION or prompt_version != SUMMARY_PROMPT_VERSION
