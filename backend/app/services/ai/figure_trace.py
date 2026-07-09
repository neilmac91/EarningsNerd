"""Deterministic "dollar figure not traceable to XBRL/filing" gate (roadmap T3.2 / plan Part 4.3.2).

Every DOLLAR amount the MODEL writes in free prose should trace to the grounded set: a standardized
XBRL value (scale-tolerant), or a figure that appears in the filing excerpt (the model's own input,
matched across scale). A dollar figure in neither is untraceable — model-invented, or model-DERIVED
(a net-cash / total-debt aggregate the pipeline should compute, not the model). The deterministic
residual the prose-floor lesson (``arch-stop-tuning-prose-know-the-floor``) assigns to a machine gate.

Scope + precision decisions (measured on the golden corpus, see the PR readout):

* **Dollar amounts only.** Percentages / ppts / bps are overwhelmingly model-DERIVED (margins, growth
  rates, ratios beyond the ~12 standardized metrics); flagging them as "not in the filing" is
  misleading, and their *consistency* is already the delta-consistency scorer's job. The clean, high
  -signal fabrication surface is a dollar amount the model could not have gotten from its input.
* **Value-based, rounding-aware matching.** Filings report raw figures ("105,819" in a millions table)
  while prose rounds + scales them ("$105.8B"); a string match on "105.8" would false-flag them, and a
  flat percentage tolerance is both too loose for a precise figure and too tight for a rounded one. So a
  prose dollar figure grounds when its VALUE is within HALF the place-value of its last significant digit
  (so "$2.2B" admits the exact 2,241M it was rounded from, but not a fabricated 2,500M) of any XBRL value
  OR any excerpt number resolved to the same scale. Measured on the corpus, this recovers the figures the
  model legitimately copied from its own input; the residual is the genuinely model-DERIVED aggregate
  (a summed "total debt", a netted "net cash") the pipeline should compute — the T5 signal.
* **Police model prose only.** The v2 renderer injects XBRL figures into the ``results_that_matter``
  table by construction, so tables, verbatim quotes, and machine-authored ``cash_flow`` /
  ``working_capital`` fields are excluded — the surface is free analytical prose.

Mirrors the eval harness's figure canonicalization app-side WITHOUT importing ``evals`` (the app keeps
parallel copies, exactly like ``_xbrl_value_appears``).
"""
from __future__ import annotations

import re
from typing import Any, Optional

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
_DOLLAR_MULT = {"b": 1e9, "m": 1e6, "t": 1e12}

# Excerpt scale words → multiplier. A number in the excerpt grounds a prose figure by VALUE, so we must
# resolve its scale: an explicit word is authoritative; a comma-grouped magnitude ("105,819") is a raw
# statement figure whose table scale (units / thousands / millions) is unknown, so we admit all three
# candidates. A BARE number (no comma, no scale word — a count, a page ref, a percentage) is NOT
# scaled up: doing so would ground a fabricated "$60B" against an incidental "60".
_EXCERPT_SCALE = {
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mn": 1e6, "m": 1e6,
    "thousand": 1e3, "k": 1e3,
}
_EXCERPT_NUM_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*"
    r"(billion|million|thousand|bn|mn|b|m|k)?\b",
    re.IGNORECASE,
)
_COMMA_SCALES = (1.0, 1e3, 1e6)

# Per-section MODEL-authored prose fields to police. Excludes: the results_that_matter table
# (XBRL-injected), forward_signals.quotes + risks.supporting_evidence (verbatim), and
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
    """Normalize a figure token to a comparable key ('$81.6 billion' -> '81.6b'). Returns None for a
    unit-less number (year/count/index)."""
    t = token.strip().lower().lstrip("$").strip()
    m = re.match(r"([\d,]*\.?\d+)\s*(.*)$", t)
    if not m:
        return None
    suffix = _SCALE_CANON.get(m.group(2).strip())
    if not suffix:
        return None
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return f"{value:g}{suffix}"


def _dollar_figures(text: Any) -> list[tuple[float, str]]:
    """(value, canonical_key) for DOLLAR-scale figures (b/m/t) in the text — excludes %/ppt/bps and
    unit-less numbers. The value carries the scale ('$105.9B' -> 105.9e9)."""
    out: list[tuple[float, str]] = []
    if not isinstance(text, str) or not text:
        return out
    for match in _FIGURE_RE.findall(text):
        key = _canonical_figure(match)
        if not key or key[-1] not in _DOLLAR_MULT:
            continue
        try:
            value = float(key[:-1]) * _DOLLAR_MULT[key[-1]]
        except ValueError:
            continue
        out.append((value, key))
    return out


def _raw_value(entry: Any, period: str) -> Optional[float]:
    block = entry.get(period) if isinstance(entry, dict) else None
    value = block.get("value") if isinstance(block, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def xbrl_values(xbrl_metrics: Optional[dict]) -> list[float]:
    """All standardized XBRL magnitudes (current/prior/series) as raw floats — the code-grounded set a
    prose dollar figure is matched against, scale-tolerantly."""
    values: list[float] = []
    if not isinstance(xbrl_metrics, dict):
        return values
    for entry in xbrl_metrics.values():
        if not isinstance(entry, dict):
            continue
        for period in ("current", "prior"):
            v = _raw_value(entry, period)
            if v is not None:
                values.append(v)
        series = entry.get("series")
        if isinstance(series, list):
            for point in series:
                pv = point.get("value") if isinstance(point, dict) else None
                if isinstance(pv, (int, float)) and not isinstance(pv, bool):
                    values.append(float(pv))
    return values


def _rounding_tol(value: float, key: str) -> float:
    """Half the place-value of the prose figure's last significant digit — the widest a correctly
    -rounded prose figure can sit from the exact value it was rounded from. '$2.2B' (one decimal) →
    ±0.05B; '$105.8B' → ±0.05B; '$43,890M' (integer mantissa) → ±0.5M. Plus a float-noise epsilon."""
    mantissa = key[:-1]
    decimals = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
    return 0.5 * (10.0 ** (-decimals)) * _DOLLAR_MULT[key[-1]] + abs(value) * 1e-9


def excerpt_values(excerpt: Optional[str]) -> list[float]:
    """Every magnitude in the filing excerpt, resolved to a value. An explicit scale word is
    authoritative; a comma-grouped raw figure admits units / thousands / millions (unknown table scale);
    a bare number is taken as-written only (never scaled up — that would ground fabrications against
    incidental counts). This is the excerpt half of the grounded set the model's prose is matched to."""
    values: list[float] = []
    if not excerpt:
        return values
    for match in _EXCERPT_NUM_RE.finditer(excerpt):
        try:
            base = float(match.group(1).replace(",", "") + (match.group(2) or ""))
        except ValueError:
            continue
        scale_word = (match.group(3) or "").lower()
        if scale_word:
            values.append(base * _EXCERPT_SCALE[scale_word])
        elif "," in match.group(1):
            values.extend(base * m for m in _COMMA_SCALES)
        else:
            values.append(base)
    return values


def _grounded(value: float, key: str, grounded_vals: list[float]) -> bool:
    tol = _rounding_tol(value, key)
    return any(abs(value - g) <= tol for g in grounded_vals)


def _prose_blob(sections: Any) -> str:
    """Model-authored analytical prose (per the allowlists) — never tables, verbatim quotes, or
    machine-authored fields. Defensive: a malformed section must not crash the gate."""
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
    """Model-prose DOLLAR figures whose value grounds in NEITHER the standardized XBRL values NOR any
    excerpt number (both matched value-based, rounding-aware). Returns sorted canonical keys; empty when
    every dollar figure grounds. The residual is the genuinely model-DERIVED aggregate or fabrication."""
    figures = _dollar_figures(_prose_blob(sections))
    if not figures:
        return []
    grounded_vals = xbrl_values(xbrl_metrics) + excerpt_values(excerpt)
    untraceable: set[str] = set()
    for value, key in figures:
        if not _grounded(value, key, grounded_vals):
            untraceable.add(key)
    return sorted(untraceable)
