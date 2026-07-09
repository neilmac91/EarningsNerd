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

from app.services import metric_delta_service
from app.services.summary_sections import render_sections_json

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


def _base_url(filing: Any) -> str:
    return getattr(filing, "document_url", None) or getattr(filing, "sec_url", None) or ""


def build_evidence(
    excerpt: Any,
    section_ref: Any,
    base_url: Optional[str],
    normalized_source: Optional[str],
) -> dict[str, Any]:
    """The Tier-4 block/row citation dict ``{excerpt, section_ref, verified, fragment_url}``.

    ``verified`` is True only when the model's (verbatim) ``excerpt`` is located in the cached filing
    text — then ``fragment_url`` is a ``#:~:text=`` deep link to it; otherwise the link is section-level
    and the chip reads "Cited". Honest labeling (never claim verified for text we cannot find) and
    filing-only (``base_url`` is THIS filing's own URL) — the same contract as :func:`build_risk_source`,
    generalized to any model claim so Print quotes / metric takeaways / footnotes cite the same way.

    Verification is EXACT (normalized substring), matching the copilot verifier: read-time enrichment
    runs on every GET over multi-MB filing text, so a per-excerpt fuzzy pass would add seconds of
    latency; a scale-tolerant (rapidfuzz) upgrade belongs on a per-section-scoped follow-up.
    """
    excerpt_str = extract_quoted_span(excerpt) if isinstance(excerpt, str) else ""
    ref = section_ref if isinstance(section_ref, str) and section_ref.strip() else None
    verified = verify_excerpt_in_text(excerpt_str, normalized_source)
    if not base_url:
        url = None
    elif verified:
        url = build_text_fragment_url(base_url, excerpt_str)
    else:
        url = base_url
    return {
        # Surface the excerpt ONLY when it's confirmed filing text — never present an unverified model
        # excerpt as if it were a quote (honest labeling). An unverified claim shows its section ref only.
        "excerpt": excerpt_str if verified else None,
        "section_ref": ref,
        "verified": verified,
        "fragment_url": url,
    }


def _enrich_forward_quotes(sections: dict, base_url: str, normalized_source: Optional[str]) -> None:
    """Attach ``evidence`` to each verbatim management quote in ``forward_signals.quotes`` (mutates the
    already-deep-copied sections). The quote text IS the excerpt (emitted verbatim), so it verifies +
    deep-links cleanly; the section ref is the block-level ``forward_signals.source_section_ref``."""
    fwd = sections.get("forward_signals")
    if not isinstance(fwd, dict):
        return
    quotes = fwd.get("quotes")
    if not isinstance(quotes, list):
        return
    section_ref = fwd.get("source_section_ref") or fwd.get("sourceSectionRef")
    for q in quotes:
        if isinstance(q, dict) and (q.get("quote") or q.get("text")):
            q["evidence"] = build_evidence(
                q.get("quote") or q.get("text"), section_ref, base_url, normalized_source
            )


def _enrich_footnotes(sections: dict, base_url: str, normalized_source: Optional[str]) -> None:
    """Attach ``evidence`` to each ``notable_footnotes`` item, verifying its model ``supporting_evidence``
    excerpt against the filing (mutates the already-deep-copied sections)."""
    footnotes = sections.get("notable_footnotes")
    if not isinstance(footnotes, list):
        return
    for fn in footnotes:
        if not isinstance(fn, dict):
            continue
        excerpt = fn.get("supporting_evidence") or fn.get("supportingEvidence")
        ref = fn.get("source_section_ref") or fn.get("sourceSectionRef")
        # Only attach a citation when there is actually something to cite — otherwise every footnote
        # would get a bare "Cited" chip pointing at the filing root, which is noise, not provenance.
        if (isinstance(excerpt, str) and excerpt.strip()) or (isinstance(ref, str) and ref.strip()):
            fn["evidence"] = build_evidence(excerpt, ref, base_url, normalized_source)


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


def _is_no_total_bank(xbrl_standardized: Optional[dict]) -> bool:
    """True when the standardized metrics describe a bank that reports NO single revenue line —
    net/non-interest income components present but no populated ``revenue`` total. Mirrors
    ``openai_service._is_no_total_bank`` (kept as a small independent copy to avoid import coupling);
    both gate the drop of a conflated bank "Revenue" row."""
    if not isinstance(xbrl_standardized, dict):
        return False
    has_components = any(
        isinstance(xbrl_standardized.get(k), dict)
        for k in ("net_interest_income", "noninterest_income")
    )
    rev = xbrl_standardized.get("revenue")
    has_revenue = (
        isinstance(rev, dict)
        and isinstance(rev.get("current"), dict)
        and rev["current"].get("value") is not None
    )
    return has_components and not has_revenue


def enrich_financial_highlights(
    financial_highlights: Optional[dict],
    filing: Any,
    xbrl_standardized: Optional[dict],
    normalized_source: Optional[str] = None,
) -> Optional[dict]:
    """Return a deep-copied ``financial_highlights`` with per-row provenance on ``table`` entries.

    Tolerant of a missing/empty ``table``; returns the input unchanged when there is nothing to
    enrich. The block-level ``source_section_ref`` is propagated to each row. As a read-time safety
    net for summaries generated before the generation-time guard shipped, a conflated ``revenue`` row
    is dropped for a no-total bank (:func:`_is_no_total_bank`) so a wrong figure never renders.

    ``build_metric_source`` verifies the row's NUMBER against SEC XBRL (the ``source_*``/``xbrl_concept``
    chip). Distinct from that, when ``normalized_source`` is supplied (the v2 path), the row's
    Investor-Takeaway is cited too: its model ``supporting_evidence`` excerpt is text-verified into a
    separate ``commentary_evidence`` dict (T4.2 — the founder's direct ask), so the number and the
    takeaway carry independent, honestly-labeled provenance.
    """
    if not isinstance(financial_highlights, dict) or not isinstance(
        financial_highlights.get("table"), list
    ):
        return financial_highlights

    section_ref = (
        financial_highlights.get("source_section_ref")
        or financial_highlights.get("sourceSectionRef")
    )
    base_url = _base_url(filing)
    result = copy.deepcopy(financial_highlights)
    rows = result["table"]
    if _is_no_total_bank(xbrl_standardized):
        rows = [
            r for r in rows
            if not (
                isinstance(r, dict)
                and (map_metric_to_xbrl_key(r.get("metric")) or (None,))[0] == "revenue"
            )
        ]
    enriched_rows: list[Any] = []
    for row in rows:
        if isinstance(row, dict):
            row.update(build_metric_source(row, filing, xbrl_standardized, section_ref))
            # Single delta policy: ship the computed change display/direction/tone so the table
            # renders one canonical string (ppts for margins) and does no client-side math (T1.5).
            row.update(metric_delta_service.row_delta_fields(row))
            if normalized_source is not None:
                excerpt = row.get("supporting_evidence") or row.get("supportingEvidence")
                if isinstance(excerpt, str) and excerpt.strip():
                    row["commentary_evidence"] = build_evidence(
                        excerpt,
                        row.get("source_section_ref") or section_ref,
                        base_url,
                        normalized_source,
                    )
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

    Version-aware: v2 rows (``schema_version >= 2``) carry ``risks`` / ``results_that_matter``; legacy
    v1 rows carry ``risk_factors`` / ``financial_highlights``. The enrichment helpers are shape-generic
    (a risk-row list, a ``{table:[...]}`` dict), so only the section-key names differ by version — the
    per-row ``source_url`` / ``source_verified`` / ``xbrl_concept`` provenance is added the same way for
    both. Tolerant of missing sections; returns the input unchanged if there is nothing to enrich.
    ``normalized_source`` (pre-normalized filing text) may be passed in to avoid recomputing it.
    """
    if not isinstance(raw_summary, dict):
        return raw_summary
    sections = raw_summary.get("sections")
    if not isinstance(sections, dict):
        return raw_summary
    try:
        version = int(raw_summary.get("schema_version") or 1)
    except (TypeError, ValueError):
        version = 1
    risk_key = "risks" if version >= 2 else "risk_factors"
    metrics_key = "results_that_matter" if version >= 2 else "financial_highlights"
    risks = sections.get(risk_key)
    has_risks = isinstance(risks, list)
    fh = sections.get(metrics_key)
    has_fh = isinstance(fh, dict) and isinstance(fh.get("table"), list)
    # v2 quotes/footnotes are independent citable surfaces (T4): a summary with only those (no risks
    # list, no metrics table — e.g. a degraded generation or a form that populates forward signals but
    # no standardized table) must still get its citation enrichment, not short-circuit here.
    has_v2_cite = version >= 2 and (
        isinstance(sections.get("forward_signals"), dict)
        or isinstance(sections.get("notable_footnotes"), list)
    )
    if not has_risks and not has_fh and not has_v2_cite:
        return raw_summary

    if normalized_source is None:
        raw_source = _select_source_text(filing) if filing is not None else None
        normalized_source = normalize_for_match(raw_source)
    result = copy.deepcopy(raw_summary)
    if has_risks:
        result["sections"][risk_key] = enrich_risk_list(risks, filing, normalized_source)
    if has_fh:
        # v2 metric rows carry a model Investor-Takeaway excerpt to cite; v1 rows don't, so only the
        # v2 path threads normalized_source (which turns on commentary_evidence).
        result["sections"][metrics_key] = enrich_financial_highlights(
            fh, filing, xbrl_standardized, normalized_source if version >= 2 else None
        )
    if version >= 2:
        # T4.1: generalize trace-to-source beyond risks/metrics to the other citable v2 surfaces.
        # Quotes verify verbatim (the quote is the excerpt); footnotes verify their supporting excerpt.
        base_url = _base_url(filing)
        _enrich_forward_quotes(result["sections"], base_url, normalized_source)
        _enrich_footnotes(result["sections"], base_url, normalized_source)
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
    enriched_raw = enrich_raw_summary(
        summary.raw_summary, filing, normalized_source, xbrl_standardized
    )
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
        "raw_summary": enriched_raw,
        # The one structured projection the web renders (T2.3): computed on read from the ENRICHED
        # raw_summary, so its metrics rows carry the verified deltas + provenance. Same Section/Block
        # model feeds the PDF/CSV exports — one source of truth for web + exports.
        "rendered_sections": render_sections_json(enriched_raw),
        # Version stamps pass through so the client can tell a stale (NULL/behind) summary from a
        # current one; enrichment never regenerates, so the stamps reflect the stored row.
        "schema_version": getattr(summary, "schema_version", None),
        "prompt_version": getattr(summary, "prompt_version", None),
    }
