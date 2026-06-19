"""Trace-to-Source provenance for AI-generated summaries.

Surfaces *verifiable* provenance for AI claims (the "single-origin / traceable" brand promise from
``docs/competitive-strategy-roadmap-2026.md``). For each risk factor we already have an AI-emitted
``supporting_evidence`` excerpt plus a ``source_section_ref``; this module turns that into a deep link
back to the original SEC filing and an honest verified/cited label.

Design notes
------------
* **Honest labeling.** We only mark a claim ``source_verified=True`` when its evidence excerpt can be
  located in the cached filing text. When verified, we build a ``#:~:text=`` fragment link so the
  browser scrolls to / highlights the exact quote; otherwise we link to the filing (section-level) and
  mark it merely "cited". We never claim "verified" for text we cannot actually find.
* **Non-mutating + tolerant.** Helpers deep-copy their inputs and degrade gracefully on missing
  structures, so enrichment is safe to run at serialization time over arbitrary historical summaries.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Optional
from urllib.parse import quote

# An excerpt shorter than this (after normalization) is too generic to verify reliably, so we never
# claim it as "verified in filing".
_MIN_VERIFIABLE_LEN = 24
# Keep text-fragment snippets short: long fragments are brittle (any whitespace/markup drift breaks
# the match), whereas a leading phrase is robust and still lands the user on the right passage.
_FRAGMENT_MAX_WORDS = 10
_FRAGMENT_MAX_CHARS = 120

_WS_RE = re.compile(r"\s+")
# Match a span wrapped in straight or curly double-quotes (e.g. Item 1A: "Supply chain ...").
_QUOTED_RE = re.compile(r"[\"“”]([^\"“”]{8,})[\"“”]")


def normalize_for_match(text: Optional[str]) -> str:
    """Lowercase and collapse all whitespace, for whitespace/case-insensitive substring matching."""
    return _WS_RE.sub(" ", (text or "").strip().lower())


def extract_quoted_span(evidence: Any) -> str:
    """Return the most quotable span of an evidence string.

    AI evidence often looks like ``Item 1A: "Supply chain constraints persisted through Q3."`` — the
    quoted span is the part that actually appears verbatim in the filing, so we prefer it. If there is
    no quoted span, fall back to the whole string.
    """
    if not isinstance(evidence, str) or not evidence:
        return ""
    match = _QUOTED_RE.search(evidence)
    if match:
        return match.group(1).strip()
    return evidence.strip()


def verify_excerpt_in_text(excerpt: str, normalized_source: Optional[str]) -> bool:
    """True when ``excerpt`` can be located in ``normalized_source``.

    ``normalized_source`` must already be normalized via :func:`normalize_for_match`. Callers
    normalize the (potentially multi-megabyte) filing text **once** per request rather than once per
    risk factor, so the large-string lowercasing/regex pass stays off the hot path.
    """
    if not excerpt or not normalized_source:
        return False
    needle = normalize_for_match(extract_quoted_span(excerpt))
    if len(needle) < _MIN_VERIFIABLE_LEN:
        return False
    return needle in normalized_source


def build_text_fragment_url(base_url: str, excerpt: str) -> str:
    """Append a percent-encoded ``#:~:text=`` fragment pointing at the start of ``excerpt``.

    Uses only a leading snippet (not a start,end range) to stay robust against minor text drift, and
    avoids the fragment's reserved ``-`` / ``,`` characters by percent-encoding the whole snippet.
    """
    if not base_url:
        return base_url
    span = extract_quoted_span(excerpt)
    words = span.split()
    snippet = " ".join(words[:_FRAGMENT_MAX_WORDS])[:_FRAGMENT_MAX_CHARS].strip()
    if not snippet:
        return base_url
    return f"{base_url}#:~:text={quote(snippet, safe='')}"


def build_risk_source(
    risk: dict[str, Any],
    filing: Any,
    normalized_source: Optional[str],
) -> dict[str, Any]:
    """Compute provenance metadata for a single risk factor.

    Returns ``{source_section_ref, source_url, source_verified}``. ``source_url`` is a text-fragment
    deep link when the evidence is verified, otherwise the plain filing document URL.
    ``normalized_source`` is the filing text pre-normalized by :func:`normalize_for_match`.
    """
    section_ref = risk.get("source_section_ref") or risk.get("sourceSectionRef")
    evidence = (
        risk.get("supporting_evidence")
        or risk.get("supportingEvidence")
        or risk.get("evidence")
        or ""
    )
    base_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""

    verified = verify_excerpt_in_text(evidence, normalized_source)
    if not base_url:
        url = None
    elif verified:
        url = build_text_fragment_url(base_url, evidence)
    else:
        url = base_url

    return {
        "source_section_ref": section_ref,
        "source_url": url,
        "source_verified": verified,
    }


def _select_source_text(filing: Any) -> Optional[str]:
    """Pick the best cached filing text to verify excerpts against (no network fetch)."""
    cache = getattr(filing, "content_cache", None)
    if cache is None:
        return None
    return getattr(cache, "critical_excerpt", None) or getattr(cache, "markdown_content", None)


def enrich_risk_list(
    risks: Optional[list],
    filing: Any,
    normalized_source: Optional[str],
) -> Optional[list]:
    """Return a deep-copied risk list with provenance fields added to each dict entry."""
    if not isinstance(risks, list):
        return risks
    enriched: list[Any] = []
    for risk in risks:
        if isinstance(risk, dict):
            item = copy.deepcopy(risk)
            item.update(build_risk_source(item, filing, normalized_source))
            enriched.append(item)
        else:
            enriched.append(risk)
    return enriched


def enrich_raw_summary(
    raw_summary: Optional[dict],
    filing: Any,
    normalized_source: Optional[str] = None,
) -> Optional[dict]:
    """Non-mutating enrichment of ``raw_summary.sections.risk_factors`` with provenance.

    Tolerant of missing ``sections`` / ``risk_factors``; returns the input unchanged if there is
    nothing to enrich. ``normalized_source`` (pre-normalized filing text) may be passed in to avoid
    recomputing it; when omitted it is selected from the filing and normalized once here.
    """
    if not isinstance(raw_summary, dict):
        return raw_summary
    sections = raw_summary.get("sections")
    if not isinstance(sections, dict) or not isinstance(sections.get("risk_factors"), list):
        return raw_summary

    if normalized_source is None:
        raw_source = _select_source_text(filing) if filing is not None else None
        normalized_source = normalize_for_match(raw_source)
    result = copy.deepcopy(raw_summary)
    result["sections"]["risk_factors"] = enrich_risk_list(
        sections.get("risk_factors"), filing, normalized_source
    )
    return result


def enrich_summary_provenance(summary: Any, filing: Any) -> dict[str, Any]:
    """Build a ``SummaryResponse``-shaped dict from a ``Summary`` row with provenance added.

    Enriches both ``raw_summary.sections.risk_factors`` (the UI's canonical source) and the top-level
    ``risk_factors`` list (used by exports). The filing text is selected and normalized **once** here
    and threaded into both enrichment passes, so a multi-MB filing is never re-normalized per risk.
    """
    raw_source = _select_source_text(filing) if filing is not None else None
    normalized_source = normalize_for_match(raw_source)
    return {
        "id": summary.id,
        "filing_id": summary.filing_id,
        "business_overview": summary.business_overview,
        "financial_highlights": summary.financial_highlights,
        "risk_factors": enrich_risk_list(summary.risk_factors, filing, normalized_source),
        "management_discussion": summary.management_discussion,
        "key_changes": summary.key_changes,
        "raw_summary": enrich_raw_summary(summary.raw_summary, filing, normalized_source),
    }
