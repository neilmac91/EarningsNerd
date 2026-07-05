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

# Maps an AI metric-name pattern -> (standardized XBRL key produced by
# ``xbrl_service.extract_standardized_metrics``, human label). Ordered: more specific first.
# EPS and margins are intentionally excluded — the value-in-text check below is only reliable for
# large dollar figures, so we never claim "verified" for small/derived numbers (honest labeling).
_METRIC_XBRL_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Financial-institution revenue components/totals FIRST, so "Net interest income" /
    # "Non-interest income" verify against their own XBRL concept and are never shadowed by the
    # generic net-income / revenue patterns below.
    (re.compile(r"\bnet\s+interest\s+income\b"), "net_interest_income", "Net interest income"),
    (re.compile(r"\bnon[-\s]?interest\s+income\b"), "noninterest_income", "Non-interest income"),
    (re.compile(r"\bnet\s+investment\s+income\b"), "net_investment_income", "Net investment income"),
    (re.compile(r"\bpremiums?\s+earned\b"), "premiums_earned", "Premiums earned"),
    (re.compile(r"\bnet\s+(income|earnings|profit)\b"), "net_income", "Net income"),
    (re.compile(r"\bgross\s+profit\b"), "gross_profit", "Gross profit"),
    (re.compile(r"\boperating\s+income\b"), "operating_income", "Operating income"),
    (re.compile(r"\b(total\s+|net\s+)?revenue|net\s+sales|total\s+sales\b"), "revenue", "Revenue"),
    (re.compile(r"\btotal\s+assets\b"), "total_assets", "Total assets"),
    (re.compile(r"\bcash\s+(and|&)\s+(cash\s+)?equivalents\b"), "cash_and_equivalents", "Cash & equivalents"),
    (re.compile(r"\bfree\s+cash\s+flow\b"), "free_cash_flow", "Free cash flow"),
    (re.compile(r"\b(operating\s+cash\s+flow|cash\s+(flow\s+)?from\s+operations|cash\s+provided\s+by\s+operating)\b"),
     "operating_cash_flow", "Operating cash flow"),
    (re.compile(r"\b(capital\s+expenditures?|capex)\b"), "capital_expenditures", "Capital expenditures"),
    (re.compile(r"\b(shareholders|stockholders)[’'`]?s?\s+equity\b"), "shareholders_equity", "Shareholders’ equity"),
    (re.compile(r"\blong[-\s]?term\s+debt\b"), "long_term_debt", "Long-term debt"),
]
# Below this magnitude the appears-in-text rendering check is ambiguous, so we don't claim "verified".
_MIN_VERIFIABLE_XBRL_VALUE = 1e6


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


def map_metric_to_xbrl_key(metric_name: Any) -> Optional[tuple[str, str]]:
    """Return ``(standardized_key, human_label)`` for a metric name, or ``None`` if unmapped."""
    if not isinstance(metric_name, str) or not metric_name:
        return None
    name = metric_name.lower()
    for pattern, key, label in _METRIC_XBRL_PATTERNS:
        if pattern.search(name):
            return key, label
    return None


def _value_appears_in_text(value: float, text_lower: str) -> bool:
    """Whether an XBRL float value appears in text, in common renderings (billions/millions/grouped).

    Mirrors the summary generator's numeric-grounding check. Reliable only for large (million+) dollar
    figures, which is why metric verification is gated to those.
    """
    if not text_lower:
        return False
    av = abs(value)
    candidates: set[str] = set()
    if av >= 1e9:
        for d in range(0, 4):  # "383", "383.3", "383.29", "383.285"
            candidates.add(f"{av / 1e9:.{d}f}")
    if av >= 1e6:
        for d in range(0, 4):  # grouped + ungrouped millions
            candidates.add(f"{av / 1e6:.{d}f}")
            candidates.add(f"{av / 1e6:,.{d}f}")
    candidates.add(f"{int(round(av)):,}")
    return any(c in text_lower for c in candidates if len(c.replace(",", "")) >= 2)


def build_metric_source(
    metric_row: dict[str, Any],
    filing: Any,
    xbrl_standardized: Optional[dict],
    section_ref: Optional[str],
) -> dict[str, Any]:
    """Compute provenance for a single financial-metric row.

    Returns ``{source_section_ref, source_url, source_verified, xbrl_concept}``. ``source_verified``
    is True only when the metric maps to a standardized XBRL concept whose SEC-verified value (a
    large dollar figure) actually appears in the row's ``current_period`` rendering.
    """
    base_url = getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""
    out: dict[str, Any] = {
        "source_section_ref": section_ref,
        "source_url": base_url or None,
        "source_verified": False,
        "xbrl_concept": None,
    }

    mapping = map_metric_to_xbrl_key(metric_row.get("metric"))
    if not mapping or not isinstance(xbrl_standardized, dict):
        return out
    key, label = mapping
    entry = xbrl_standardized.get(key)
    current = entry.get("current") if isinstance(entry, dict) else None
    value = current.get("value") if isinstance(current, dict) else None
    if not isinstance(value, (int, float)) or abs(value) < _MIN_VERIFIABLE_XBRL_VALUE:
        return out

    displayed = str(metric_row.get("current_period") or "").lower()
    if _value_appears_in_text(float(value), displayed):
        out["source_verified"] = True
        out["xbrl_concept"] = label
    return out


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


def enrich_financial_highlights(
    financial_highlights: Optional[dict],
    filing: Any,
    xbrl_standardized: Optional[dict],
) -> Optional[dict]:
    """Return a deep-copied ``financial_highlights`` with per-row provenance on ``table`` entries.

    Tolerant of a missing/empty ``table``; returns the input unchanged when there is nothing to
    enrich. The block-level ``source_section_ref`` is propagated to each row.
    """
    if not isinstance(financial_highlights, dict) or not isinstance(
        financial_highlights.get("table"), list
    ):
        return financial_highlights

    section_ref = (
        financial_highlights.get("source_section_ref")
        or financial_highlights.get("sourceSectionRef")
    )
    result = copy.deepcopy(financial_highlights)
    enriched_rows: list[Any] = []
    for row in result["table"]:
        if isinstance(row, dict):
            row.update(build_metric_source(row, filing, xbrl_standardized, section_ref))
        enriched_rows.append(row)
    result["table"] = enriched_rows
    return result


def enrich_raw_summary(
    raw_summary: Optional[dict],
    filing: Any,
    normalized_source: Optional[str] = None,
    xbrl_standardized: Optional[dict] = None,
) -> Optional[dict]:
    """Non-mutating enrichment of ``raw_summary.sections`` risk factors + financial highlights.

    Tolerant of missing ``sections``/``risk_factors``/``financial_highlights``; returns the input
    unchanged if there is nothing to enrich. ``normalized_source`` (pre-normalized filing text) may
    be passed in to avoid recomputing it; when omitted it is selected from the filing here.
    """
    if not isinstance(raw_summary, dict):
        return raw_summary
    sections = raw_summary.get("sections")
    if not isinstance(sections, dict):
        return raw_summary
    has_risks = isinstance(sections.get("risk_factors"), list)
    fh = sections.get("financial_highlights")
    has_fh = isinstance(fh, dict) and isinstance(fh.get("table"), list)
    if not has_risks and not has_fh:
        return raw_summary

    if normalized_source is None:
        raw_source = _select_source_text(filing) if filing is not None else None
        normalized_source = normalize_for_match(raw_source)
    result = copy.deepcopy(raw_summary)
    if has_risks:
        result["sections"]["risk_factors"] = enrich_risk_list(
            sections.get("risk_factors"), filing, normalized_source
        )
    if has_fh:
        result["sections"]["financial_highlights"] = enrich_financial_highlights(
            fh, filing, xbrl_standardized
        )
    return result


def enrich_summary_provenance(
    summary: Any, filing: Any, xbrl_standardized: Optional[dict] = None
) -> dict[str, Any]:
    """Build a ``SummaryResponse``-shaped dict from a ``Summary`` row with provenance added.

    Enriches risk factors (verified against the cached filing text) and financial-metric rows
    (verified against the SEC XBRL values in ``xbrl_standardized``), across both ``raw_summary``
    (the UI's canonical source) and the top-level columns (used by exports). The filing text is
    normalized **once** here and threaded into every pass.
    """
    raw_source = _select_source_text(filing) if filing is not None else None
    normalized_source = normalize_for_match(raw_source)
    return {
        "id": summary.id,
        "filing_id": summary.filing_id,
        "business_overview": summary.business_overview,
        "financial_highlights": enrich_financial_highlights(
            summary.financial_highlights, filing, xbrl_standardized
        ),
        "risk_factors": enrich_risk_list(summary.risk_factors, filing, normalized_source),
        "management_discussion": summary.management_discussion,
        "key_changes": summary.key_changes,
        "raw_summary": enrich_raw_summary(
            summary.raw_summary, filing, normalized_source, xbrl_standardized
        ),
    }
