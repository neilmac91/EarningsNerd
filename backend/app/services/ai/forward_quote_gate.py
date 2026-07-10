"""Generation-time verbatim gate for §5 forward-looking quotes (T5.4).

``forward_signals.quotes`` are prompt-contracted as verbatim, attributed filing text — and every
other guard treats them as such: figure_trace EXEMPTS them from dollar policing *because* they are
verbatim, and T4's read-time enrichment uses the quote text itself as its evidence excerpt. This
module is the enforcement that assumption was missing: each quote is checked against the same
filing text the model generated from (exact substring under ``normalize_for_match`` — the ONE
shared definition of verbatim across T4 evidence, copilot citations, and this gate; see
lessons/arch-guard-every-model-facing-surface.md). Failures are ALWAYS measured (the audit feeds
the pipeline's greppable ``forward_quote_unverified`` counter and persists on the row); they are
DROPPED from the section only when ``AI_FORWARD_QUOTE_GATE`` is armed (advisory-first, the
figure-trace precedent — the flag ships off while the fleet false-positive rate is measured).

Conservative by design, mirroring figure_trace:
- No source text (excerpt AND filing text both empty) → measure/drop NOTHING — a degraded
  generation must never lose content to a pipeline failure upstream of it.
- Quotes shorter than the shared ``_MIN_VERIFIABLE_LEN`` floor are unverifiable-by-construction →
  pass uncounted.
- Malformed entries (non-dict items, non-string quote text) pass untouched.
- ``rapidfuzz`` scores failing quotes as TELEMETRY only (near_miss ≥ NEAR_MISS_SCORE means
  lightly-paraphrased; below it means fabrication-class): the drop criterion stays the exact
  shared match — quotation marks assert exactness, so a 95%-similar quote is still not verbatim.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from rapidfuzz import fuzz

from app.services.provenance_service import (
    _MIN_VERIFIABLE_LEN,
    extract_quoted_span,
    normalize_for_match,
)

# Unverified quotes at/above this partial_ratio (on normalized text) are "near misses" — the model
# lightly paraphrased or elided real filing text. Below it, the quote has no close counterpart in
# the filing at all. The split is the arming signal: a near-miss-dominated failure population wants
# prompt tuning (T4 follow-up); a fabrication-dominated one wants the gate armed.
NEAR_MISS_SCORE = 92.0


def gate_forward_quotes(
    sections: Dict[str, Any], source_text: str, armed: bool
) -> Optional[Dict[str, Any]]:
    """Verify every ``forward_signals.quotes[].quote`` against ``source_text``; drop failures
    when ``armed``. Mutates ``sections`` in place (armed only). Returns the audit dict, or None
    when there was nothing to measure (no quotes, no source basis, or none long enough to verify).

    ``source_text`` is the RAW filing excerpt/text (the same ``filing_excerpt or filing_text`` the
    model generated from); it is normalized once here. Callers gate ``armed`` on
    ``settings.AI_FORWARD_QUOTE_GATE`` — this module stays settings-free (pure leaf, the
    figure_trace shape).
    """
    fs = sections.get("forward_signals")
    if not isinstance(fs, dict):
        return None
    quotes = fs.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        return None
    normalized_source = normalize_for_match(source_text)
    if not normalized_source:
        return None

    checked = 0
    unverified: list[Dict[str, Any]] = []
    near_miss = 0
    dropped: list[Dict[str, Any]] = []
    surviving: list[Any] = []
    for item in quotes:
        text = item.get("quote") if isinstance(item, dict) else None
        if not isinstance(text, str) or not text.strip():
            surviving.append(item)  # malformed → untouched (render already skips empties)
            continue
        # extract_quoted_span strips literal quote marks the model may have wrapped the text in.
        needle = normalize_for_match(extract_quoted_span(text))
        if len(needle) < _MIN_VERIFIABLE_LEN:
            surviving.append(item)  # unverifiable-by-construction → pass uncounted
            continue
        checked += 1
        if needle in normalized_source:
            surviving.append(item)
            continue
        score = round(float(fuzz.partial_ratio(needle, normalized_source)), 1)
        if score >= NEAR_MISS_SCORE:
            near_miss += 1
        speaker = str(item.get("speaker") or "").strip()
        unverified.append({"speaker": speaker, "score": score})
        if armed:
            dropped.append({"speaker": speaker, "quote": text})
        else:
            surviving.append(item)

    if not checked:
        return None
    if armed:
        fs["quotes"] = surviving
    return {
        "checked": checked,
        "verified": checked - len(unverified),
        "unverified": unverified,
        "near_miss": near_miss,
        "dropped": dropped,
        "armed": armed,
    }
