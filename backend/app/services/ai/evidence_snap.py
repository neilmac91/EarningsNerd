"""Deterministic evidence auto-snap — provenance repair for ``supporting_evidence``.

The -j/-k prompt slices measured composed evidence at the model's prompt-tuning floor
(citation_fidelity flat ~0.68 across a rule edit and a rule+worked-example edit;
lessons/arch-stop-tuning-prose-know-the-floor). The residual violations score 61–92 against the
excerpt — the composed sentence is almost always a light distortion of a REAL nearby sentence. So
the remaining gap is closed in code, at generation time: evidence on the two verbatim-contracted
surfaces (``results_that_matter.table[].supporting_evidence``,
``notable_footnotes[].supporting_evidence``) that does not verify exactly is SNAPPED to the
best-matching real sentence from the same excerpt the model generated from. The snapped span is
authentic filing text by construction, so T4's read-time EXACT verification (Verified badge +
``#:~:text=`` deep link), the exports, and the eval's citation_fidelity dimension all improve —
with zero prompt change and zero read-path latency (read-time enrichment stays exact-only; its
docstring explicitly reserved the rapidfuzz upgrade for a write-side follow-up — this module).

Conservative postures (the forward_quote_gate conventions):

- **No source text → snap NOTHING.** Callers pass the EXCERPT (the model's true prompt input),
  never raw ``filing_text`` — on the excerpt-miss path filing_text is raw HTML while the model
  saw tag-stripped text, and fuzzy-matching against HTML would snap to markup-mangled spans (the
  T5.4 blocking-finding rule, applied here).
- **Repair-only, never destructive.** Below the relevance floor the original evidence is left in
  place: read-time enrichment already suppresses unverifiable excerpts (nulled excerpt, no
  badge), so keeping the model's text costs nothing user-facing and preserves forensics. Because
  no content is ever dropped, ``AI_EVIDENCE_SNAP`` ships default-ON as a kill switch — unlike the
  quote gate's armed mode, there is no destructive action to stage behind measurement.
- **Two-tier relevance floor + figure guard** (empirically calibrated — a flat high floor missed
  the exact composed class this module exists for: a true counterpart like "Diluted earnings per
  share increased 16% to $13.64." scores only ~74 token_set against its real sentence). Candidates
  are scored ``max(token_set_ratio, partial_ratio)`` on normalized text. When the evidence carries
  NON-YEAR digit groups, the floor is ``min_score`` (default 72) AND the candidate must share at
  least one of those groups — the shared figure pins the candidate to the same fact, supplying the
  precision the lower floor gives up. Year-like groups (19xx/20xx) are excluded from the guard:
  fiscal years co-occur across unrelated facts, so "2025/2024 in common" proves nothing (and would
  have laundered a cross-metric match straight through the guard). Evidence with no non-year
  figures gets no guard, so it needs the conservative ``_NO_FIGURE_FLOOR`` (88) on text alone.
- **Original casing/typography out.** The snapped value is the candidate sentence exactly as it
  appears in the source, so downstream exact search succeeds — the round-trip
  (snapped ⇒ ``verify_excerpt_in_text`` passes) is the module's core invariant.
- **Scope.** Risks evidence is excluded (its contract allows citations/XBRL references — not
  spans). ``forward_signals.quotes`` are excluded: programmatically rewording an ATTRIBUTED
  management statement is a separate decision; that surface belongs to the forward_quote_gate.

Settings-free pure leaf: callers gate on ``settings.AI_EVIDENCE_SNAP`` and pass
``settings.EVIDENCE_SNAP_MIN_SCORE``.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from app.services.provenance_service import (
    _MIN_VERIFIABLE_LEN,
    extract_quoted_span,
    normalize_for_match,
    verify_excerpt_in_text,
)

# Candidate sentences longer than this are almost certainly extraction artifacts (table blobs,
# concatenated headings) — snapping evidence to a wall of text is not a repair.
_MAX_CANDIDATE_LEN = 600

# Sentence boundary: terminal punctuation followed by whitespace, or any newline. Filings are
# markdown-ish extracted text; this deliberately over-splits rather than under-splits (a clause
# fragment that verifies is still a real span — the goal is locatable authenticity, not grammar).
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

_DIGIT_GROUP_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# No-figure evidence has no shared-figure guard to lean on, so its text-similarity floor is
# deliberately stricter than the guarded ``min_score``. A module constant, not a setting: promote
# to config only if the fleet readout ever says it needs tuning (fewer knobs until then).
_NO_FIGURE_FLOOR = 88.0


def _sentences(source_text: str) -> List[str]:
    """Candidate spans: sentence-ish pieces of the source, length-bounded, original form."""
    out: List[str] = []
    for piece in _SENTENCE_SPLIT_RE.split(source_text):
        s = piece.strip()
        if _MIN_VERIFIABLE_LEN <= len(s) <= _MAX_CANDIDATE_LEN:
            out.append(s)
    return out


def _digit_groups(text: str) -> set:
    """Normalized digit groups ("62,151" → "62151"; "8%"→"8") for the shared-figure guard."""
    return {g.replace(",", "").rstrip(".") for g in _DIGIT_GROUP_RE.findall(text)}


def _guard_figures(text: str) -> set:
    """Digit groups that actually discriminate between facts: years (19xx/20xx) are dropped —
    fiscal years co-occur across unrelated sentences, so sharing one proves nothing."""
    return {
        g for g in _digit_groups(text)
        if not (len(g) == 4 and g.isdigit() and g[:2] in ("19", "20"))
    }


def snap_value(
    evidence: Any,
    candidates: List[str],
    candidate_needles: List[str],
    normalized_source: str,
    min_score: float,
) -> Tuple[Any, float, str]:
    """Snap one evidence value. Returns ``(value, score, status)`` with status one of
    ``exact`` (verifies as-is, untouched), ``snapped`` (replaced with a real span),
    ``left`` (no confident counterpart, untouched), ``skipped`` (nothing verifiable to measure —
    empty/short/non-string, untouched and uncounted)."""
    if not isinstance(evidence, str) or not evidence.strip():
        return evidence, 0.0, "skipped"
    needle = normalize_for_match(extract_quoted_span(evidence))
    if len(needle) < _MIN_VERIFIABLE_LEN:
        return evidence, 0.0, "skipped"
    if needle in normalized_source:
        return evidence, 100.0, "exact"

    guard = _guard_figures(needle)
    floor = min_score if guard else max(_NO_FIGURE_FLOOR, min_score)
    best_i, best_score = -1, 0.0
    for i, cand_needle in enumerate(candidate_needles):
        score = max(
            fuzz.token_set_ratio(needle, cand_needle, score_cutoff=floor),
            fuzz.partial_ratio(needle, cand_needle, score_cutoff=floor),
        )
        if score > best_score and (not guard or guard & _digit_groups(cand_needle)):
            best_i, best_score = i, score
    if best_i < 0 or best_score < floor:
        return evidence, best_score, "left"
    snapped = candidates[best_i]
    # Round-trip guard: only snap when the result will actually verify downstream via the SAME
    # shared check the badge/deep-link/eval use. Real edge (pinned in tests): a candidate with a
    # short inner quoted span makes ``extract_quoted_span`` shrink the read-time needle below
    # ``_MIN_VERIFIABLE_LEN`` — a repair that cannot light the badge is not a repair, so the
    # original text is kept instead (no next-best fallback; simplicity over a rare edge).
    if not verify_excerpt_in_text(snapped, normalized_source):
        return evidence, best_score, "left"
    return snapped, best_score, "snapped"


def snap_evidence(
    sections: Dict[str, Any], source_text: str, min_score: float
) -> Optional[Dict[str, Any]]:
    """Repair ``supporting_evidence`` on the two verbatim-contracted surfaces in place.

    Returns the audit dict, or ``None`` when there is nothing to measure (no source basis or no
    evidence values on the contracted surfaces). Mutates ``sections`` — callers run this on the
    same object the coverage snapshot and renderer read, so stored sections, markdown, and
    read-time enrichment agree about the repaired text.
    """
    if not source_text or not isinstance(sections, dict):
        return None

    targets: List[Tuple[str, str, Dict[str, Any]]] = []  # (surface, label, item-dict)
    rtm = sections.get("results_that_matter")
    if isinstance(rtm, dict) and isinstance(rtm.get("table"), list):
        for row in rtm["table"]:
            if isinstance(row, dict) and "supporting_evidence" in row:
                targets.append(("results_that_matter", str(row.get("metric") or "?"), row))
    footnotes = sections.get("notable_footnotes")
    if isinstance(footnotes, list):
        for fn in footnotes:
            if isinstance(fn, dict) and "supporting_evidence" in fn:
                targets.append(("notable_footnotes", str(fn.get("item") or "?")[:60], fn))
    if not targets:
        return None

    normalized_source = normalize_for_match(source_text)
    candidates = _sentences(source_text)
    candidate_needles = [normalize_for_match(c) for c in candidates]

    audit: Dict[str, Any] = {
        "checked": 0,
        "exact": 0,
        "snapped": [],
        "left": [],
        "min_score": min_score,
    }
    for surface, label, item in targets:
        value, score, status = snap_value(
            item.get("supporting_evidence"),
            candidates,
            candidate_needles,
            normalized_source,
            min_score,
        )
        if status == "skipped":
            continue
        audit["checked"] += 1
        if status == "exact":
            audit["exact"] += 1
        elif status == "snapped":
            item["supporting_evidence"] = value
            audit["snapped"].append(
                {"surface": surface, "label": label, "score": round(score, 1)}
            )
        else:
            audit["left"].append({"surface": surface, "score": round(score, 1)})
    return audit if audit["checked"] else None
