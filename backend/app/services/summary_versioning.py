"""Summary schema + prompt version stamps.

Every generated ``Summary`` row records the ``SUMMARY_SCHEMA_VERSION`` (the shape of
``raw_summary["sections"]`` — the sections taxonomy) and the ``SUMMARY_PROMPT_VERSION`` (the
generation prompt text) it was produced under. That lets a change to either identify and refresh
stale rows in place, instead of stranding a pre-change ``business_overview`` — the exact failure
mode behind the shipped-but-unseen ".;" fix (a serializer fix that never reached already-generated
summaries because nothing marked them stale). Mirrors ``trend_analysis_service.PROMPT_VERSION``.

Bump ``SUMMARY_SCHEMA_VERSION`` when the ``sections`` shape changes (v2 = the content
re-architecture in Tier 3). Bump ``SUMMARY_PROMPT_VERSION`` on any content-affecting change to the
generation prompt — whether the per-form ``backend/prompts/*-agent.md`` preambles OR the shared
inline Rules/schema block assembled in ``app/services/openai_service.py`` (both feed the same
prompt). Bumping either makes prior rows version-stale; the admin ``refresh-stale`` endpoint and
the background drain regenerate them in place (preserving ``summaries.id`` so saved-summary
bookmarks survive).

NULL columns on a row (legacy / pre-stamp) are always treated as stale.
"""

# The sections taxonomy shape currently produced by the pipeline. v2 = the Tier-3.1 content
# architecture (summary_schema.TRACKED_SECTIONS_V2: the_print, results_that_matter, earnings_quality,
# value_drivers, forward_signals, risks, segments, balance_sheet_liquidity, notable_footnotes). v1
# rows (the prior 9-section data-dump taxonomy) still render via summary_sections' v1 builders and
# are counted against the frozen TRACKED_SECTIONS_V1 by the badge.
SUMMARY_SCHEMA_VERSION: int = 2

# The generation-prompt version. Bump on any content-affecting change to the generation prompt
# (the *-agent.md preambles or the shared Rules/schema block in openai_service.py).
# summary-2026-07-c: Tier-3.1 v2 cutover — schema_template rewritten to the nine v2 sections.
# summary-2026-07-d: Tier-4 — schema_template asks for a verbatim `supporting_evidence` excerpt on
#   metric-takeaway rows + footnotes (the citation surface). Taxonomy shape unchanged (still v2).
# summary-2026-07-e: Tier-5.1 — earnings_quality.cash_conversion removed from the schema/re-ask (the
#   model no longer authors it); it is now machine-authored from XBRL (NI-vs-CFO + FCF). ONE-HOME
#   note reworded to match. Taxonomy shape unchanged (still v2).
# summary-2026-07-f: Tier-5.2 — the segments table removed from the schema/re-ask; it is now
#   machine-authored from the filing's XBRL segment dimensions (per-segment revenue / operating income
#   / YoY change + a deterministic mix read). ONE-HOME note reworded. Taxonomy shape unchanged (v2).
# summary-2026-07-g: Tier-5.2b — segments returns to the schema as COMMENTARY-ONLY rows keyed to the
#   REPORTABLE SEGMENTS grounding list (figures stay machine-authored; the filler merges the model's
#   qualitative driver onto the code rows by exact label). Taxonomy shape unchanged (still v2).
# summary-2026-07-h: Tier-5.3 — value_drivers machine feeds: `returns_on_capital` removed from the
#   schema/re-ask (code authors ROE/ROA level + prior; the old ask was ROIC, which the grounding
#   cannot support); `capital_allocation` reworded to the qualitative value read (the new
#   machine-authored `shareholder_returns` carries the dividends/buybacks/capex dollars); grounding
#   gains Dividends Paid + Share Repurchases. Taxonomy shape unchanged (still v2).
SUMMARY_PROMPT_VERSION: str = "summary-2026-07-h"


def is_stale(schema_version: int | None, prompt_version: str | None) -> bool:
    """A stored summary is stale when either stamp is missing or behind the current version."""
    if schema_version is None or prompt_version is None:
        return True
    return schema_version != SUMMARY_SCHEMA_VERSION or prompt_version != SUMMARY_PROMPT_VERSION
