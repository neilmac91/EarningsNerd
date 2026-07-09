"""Deterministic "figure not traceable to XBRL/filing" gate (roadmap T3.2 / plan Part 4.3.2).

Every financial figure the MODEL writes in free prose should trace to the grounded set:

* a standardized XBRL value (any common billions/millions rendering),
* a code-computed delta (``metric_delta_service`` — ``+85.2%`` / ``+14.4 ppts``), or
* a number that appears verbatim in the filing excerpt.

A prose figure in NONE of those is *untraceable* — the deterministic "summary figure not traceable to
XBRL/filing" residual the prose-floor lesson (``arch-stop-tuning-prose-know-the-floor``) assigns to a
machine gate rather than to prompt tuning. It reads deltas, never feeds them to the model, so it is on
the right side of ``arch-no-precomputed-deltas-in-grounding``.

Design (conservative — false positives are the billing risk, see ``assess_quality``):

* **Canonical-key set difference.** Both sides canonicalize to keys like ``'81.6b'`` / ``'85%'`` /
  ``'14.4ppt'``; a UNIT-LESS number (year, count, page/item index) yields no key and is never compared.
  Mirrors the eval harness's ``_figure_keys`` WITHOUT importing ``evals`` (the app keeps mirror copies,
  exactly like ``_xbrl_value_appears``).
* **Over-inclusive legitimate set.** Multiple scale/precision renderings per XBRL value, and BOTH the
  ``%`` and ``ppt`` delta for every metric — over-including the *allowed* set can only miss a catch,
  never manufacture a false positive.
* **Police model prose only.** The v2 renderer injects XBRL figures into the ``results_that_matter``
  table by construction, so tables, verbatim quotes, and machine-authored fields (cash_flow /
  working_capital) are excluded; the real fabrication surface is free analytical prose.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.services import metric_delta_service

# Mirror of evals/scorers.py figure canonicalization (kept app-side; evals deliberately never imports
# app, and the app keeps parallel copies — see _xbrl_value_appears "mirrors ... without importing it").
_FIGURE_RE = re.compile(
    r"\$?\s*\d[\d,]*(?:\.\d+)?\s*"
    r"(?:(?:percentage points|basis points|trillion|billion|million|ppts?|bps|bn|mn|tn|b|m|t)\b|%)?",
    re.IGNORECASE,
)
_SCALE_CANON = {
    "billion": "b", "bn": "b", "b": "b",
    "million": "m", "mn": "m", "m": "m",
    "trillion": "t", "tn": "t", "t": "t",
    "percent": "%", "%": "%",
    "percentage points": "ppt", "ppts": "ppt", "ppt": "ppt",
    "basis points": "bps", "bps": "bps",
}

# The per-section MODEL-authored prose fields to police. Excludes: the results_that_matter table
# (XBRL-injected), forward_signals.quotes + risks.supporting_evidence (verbatim from the filing), and
# balance_sheet_liquidity.cash_flow / .working_capital (machine-authored from XBRL by the filler).
_PROSE_STRING_FIELDS: dict[str, tuple[str, ...]] = {
    "the_print": ("headline", "what_changed"),
    "earnings_quality": ("operating_vs_one_time", "cash_conversion"),
    "value_drivers": ("capital_allocation", "returns_on_capital"),
    "forward_signals": ("guidance",),
    "balance_sheet_liquidity": ("leverage", "liquidity"),
}
_PROSE_LIST_FIELDS: dict[str, tuple[str, ...]] = {
    "the_print": ("key_takeaways",),
    "earnings_quality": ("red_flags",),
    "value_drivers": ("highlights",),
    "forward_signals": ("known_trends", "subsequent_events"),
    "balance_sheet_liquidity": ("maturities_covenants",),
}


def _canonical_figure(token: str) -> Optional[str]:
    """Normalize a figure token to a comparable key ('$81.6 billion' -> '81.6b', '85.0%' -> '85%').
    Returns None for a unit-less number (year/count/index) — too ambiguous to compare."""
    t = token.strip().lower().lstrip("$").strip()
    m = re.match(r"([\d,]*\.?\d+)\s*(.*)$", t)
    if not m:
        return None
    suffix = _SCALE_CANON.get(m.group(2).strip())
    if not suffix:
        return None  # unit-less — skip (drops years, counts, indices)
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return f"{value:g}{suffix}"  # %g collapses "85.0" -> "85", so "85.0%" == "85%"


def _figure_keys(text: Any) -> set[str]:
    if not isinstance(text, str) or not text:
        return set()
    keys: set[str] = set()
    for match in _FIGURE_RE.findall(text):
        key = _canonical_figure(match)
        if key:
            keys.add(key)
    return keys


def _figure_pairs(text: Any) -> list[tuple[str, str]]:
    """(canonical_key, raw_magnitude) per unit-bearing figure — the magnitude drives the excerpt
    substring check, the key drives the XBRL/delta set match."""
    out: list[tuple[str, str]] = []
    if not isinstance(text, str) or not text:
        return out
    for match in _FIGURE_RE.findall(text):
        key = _canonical_figure(match)
        if not key:
            continue
        m = re.search(r"[\d,]*\.?\d+", match)
        if m:
            out.append((key, m.group().replace(",", "")))
    return out


def _magnitude_in_excerpt(magnitude: str, excerpt_lower: str) -> bool:
    """The figure's magnitude appears verbatim in the filing excerpt (the model's own input), matched
    word-bounded so '33.7' does not match inside '133.7'/'33.75'. Requires >=3 significant digits so a
    small, ambiguous magnitude (a '$5B' -> '5') can't match a stray digit — those rely on XBRL/deltas."""
    if len(magnitude.replace(".", "")) < 3:
        return False
    return re.search(r"(?<![\d.])" + re.escape(magnitude) + r"(?![\d.])", excerpt_lower) is not None


def _raw_value(entry: Any, period: str) -> Optional[float]:
    block = entry.get(period) if isinstance(entry, dict) else None
    value = block.get("value") if isinstance(block, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _amount_keys(value: float) -> set[str]:
    """Canonical keys for a monetary value at billions/millions across 0-2 decimals — covers the
    renderings the model realistically writes ('$81.6B', '$81,630M', '$82B')."""
    keys: set[str] = set()
    av = abs(value)
    for scale, suffix in ((1e9, "B"), (1e6, "M")):
        if av >= scale:
            for d in range(0, 3):
                key = _canonical_figure(f"{av / scale:.{d}f}{suffix}")
                if key:
                    keys.add(key)
    return keys


def legitimate_keys(xbrl_metrics: Optional[dict]) -> set[str]:
    """The code-grounded figure keys: XBRL values (current/prior/series renderings) ∪ code-computed
    deltas (both % and ppt per metric — over-inclusive on purpose). Filing-text grounding is handled
    separately by a per-figure magnitude substring match in :func:`untraceable_figures`."""
    keys: set[str] = set()
    if not isinstance(xbrl_metrics, dict):
        return keys
    for entry in xbrl_metrics.values():
        if not isinstance(entry, dict):
            continue
        cur, prior = _raw_value(entry, "current"), _raw_value(entry, "prior")
        for v in (cur, prior):
            if v is not None:
                keys |= _amount_keys(v)
        series = entry.get("series")
        if isinstance(series, list):
            for point in series:
                pv = point.get("value") if isinstance(point, dict) else None
                if isinstance(pv, (int, float)) and not isinstance(pv, bool):
                    keys |= _amount_keys(float(pv))
        # Deltas: allow BOTH interpretations (amount % and ratio ppts) — over-inclusion is safe.
        # Route the display through _figure_keys (not _canonical_figure) so the leading +/− sign is
        # stripped by _FIGURE_RE first ("+85.0%" -> "85%", "−14.4 ppts" -> "14.4ppt").
        if cur is not None and prior is not None:
            for is_ratio in (False, True):
                display = metric_delta_service.compute(cur, prior, is_ratio=is_ratio).display
                if display:
                    keys |= _figure_keys(display)
    return keys


def _prose_blob(sections: Any) -> str:
    """Collect the model-authored analytical prose (per the allowlists) — never tables, verbatim
    quotes, or machine-authored fields. Defensive: a malformed section must not crash the gate."""
    if not isinstance(sections, dict):
        return ""
    parts: list[str] = []

    def _add(value: Any) -> None:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)

    for key, fields in _PROSE_STRING_FIELDS.items():
        data = sections.get(key)
        if isinstance(data, dict):
            for field in fields:
                _add(data.get(field))
    for key, fields in _PROSE_LIST_FIELDS.items():
        data = sections.get(key)
        if isinstance(data, dict):
            for field in fields:
                _add(data.get(field))
    # segments + notable_footnotes are lists of dicts: police commentary/impact prose, not the figures.
    segments = sections.get("segments")
    if isinstance(segments, list):
        for seg in segments:
            if isinstance(seg, dict):
                _add(seg.get("commentary"))
    footnotes = sections.get("notable_footnotes")
    if isinstance(footnotes, list):
        for note in footnotes:
            if isinstance(note, dict):
                _add(note.get("item"))
                _add(note.get("impact"))
    return "\n".join(parts)


def untraceable_figures(
    sections: Any, xbrl_metrics: Optional[dict], excerpt: Optional[str]
) -> list[str]:
    """Model-prose figures traceable to NEITHER the XBRL/delta key set NOR the filing excerpt (by a
    word-bounded magnitude substring — the excerpt IS the model's input, so a figure whose magnitude
    is absent from it and from XBRL/deltas is model-invented or model-derived). Returns sorted
    canonical keys; empty when every prose figure grounds."""
    pairs = _figure_pairs(_prose_blob(sections))
    if not pairs:
        return []
    legit = legitimate_keys(xbrl_metrics)
    excerpt_lower = (excerpt or "").lower()
    untraceable: set[str] = set()
    for key, magnitude in pairs:
        if key in legit or _magnitude_in_excerpt(magnitude, excerpt_lower):
            continue
        untraceable.add(key)
    return sorted(untraceable)
