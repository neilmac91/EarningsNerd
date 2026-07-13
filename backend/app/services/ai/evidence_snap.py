"""Evidence auto-snap — measured provenance repair for ``supporting_evidence``.

The -j/-k prompt slices measured composed evidence at the model's prompt-tuning floor
(citation_fidelity flat ~0.68 across a rule edit and a rule+worked-example edit;
lessons/arch-stop-tuning-prose-know-the-floor). The residual violations score 61–92 against the
excerpt — usually a light distortion of a REAL nearby sentence — so the repair is computed in
code, at generation time: for the two verbatim-contracted surfaces
(``results_that_matter.table[].supporting_evidence``,
``notable_footnotes[].supporting_evidence``), evidence that does not verify exactly is matched to
the best real sentence from the same excerpt the model generated from. A snapped span is
authentic filing text by construction, so T4's read-time EXACT verification (Verified badge +
``#:~:text=`` deep link), the exports, and the eval's citation_fidelity dimension all light up.

**Measure-always, act-when-armed** (the figure-trace / forward-quote-gate pattern). The
adversarial review of the first draft CONFIRMED, by execution, that fuzzy repair on the trust
surface can attach a real-but-wrong-fact sentence under a Verified badge (same-percentage moves
across P&L lines are pervasive in real MD&A; a floor + figure guard pins *a* fact, not *the
row's* fact). A false "Verified" is worse than the honest "Cited" chip the product already shows
for unverifiable evidence — so mutation is gated behind ``AI_EVIDENCE_SNAP`` (default OFF) while
the always-on audit measures the fleet: every would-snap decision records the ORIGINAL model
text and the candidate span, giving the arming decision real forensics instead of faith.

Conservative postures:

- **No source text → measure NOTHING.** Callers pass the EXCERPT (the model's true prompt
  input), never raw ``filing_text`` (the T5.4 blocking-finding rule).
- **Recovery-authored sections are skipped** (``skip_sections``): the recovery re-ask generates
  from ``extract_sections(filing_text)`` context, NOT the excerpt, so its verbatim-TRUE evidence
  can fail the excerpt exact-check — snapping would rewrite correct filing text (adversarial
  finding F3). Callers thread the recovered section keys through.
- **Two-tier relevance floor, empirically calibrated** (a flat high floor missed the exact
  composed class this module exists for — a true counterpart like "Diluted earnings per share
  increased 16% to $13.64." scores only ~74 token_set against its real sentence). Candidates are
  scored ``max(token_set_ratio, partial_ratio)``; evidence carrying NON-YEAR digit groups uses
  ``min_score`` (default 72) AND must share one of those groups (years are excluded from the
  guard — fiscal years co-occur across unrelated facts and would launder cross-metric matches);
  no-figure evidence has no guard and needs the stricter ``_NO_FIGURE_FLOOR`` (88) on text alone.
- **Length-ratio guard** (adversarial finding F2, executed): ``partial_ratio`` scores a short
  boilerplate heading ("Compared with the prior year period:") ~100 against any evidence that
  contains its words — replacing real content with a contentless fragment. A candidate must be at
  least ``_MIN_CANDIDATE_RATIO`` of the needle's length.
- **Digit-density candidate filter**: table-transcription lines in extracted text are digit-heavy;
  they are excluded from candidacy so the snap can never install the exact artifact the evidence
  contract forbids.
- **Round-trip guard**: a snap is only offered when ``verify_excerpt_in_text`` passes on the
  result — a candidate with a short inner quoted span shrinks the read-time needle below the
  verifiable minimum (real edge, pinned in tests); a repair that cannot light the badge is not a
  repair.
- **Risks** (citation-legal contract) and **§5 quotes** (attributed management statements — a
  separate decision; the forward_quote_gate owns that surface) are out of scope.

Settings-free pure leaf: callers gate ``armed`` on ``settings.AI_EVIDENCE_SNAP``, pass
``settings.EVIDENCE_SNAP_MIN_SCORE``, and run it off the event loop (the candidate scan over a
320k-char excerpt measures ~0.5s — ``run_in_threadpool`` at the call site, the repo convention
for CPU-heavy generation steps).
"""
from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from rapidfuzz import fuzz

from app.services.provenance_service import (
    _MIN_VERIFIABLE_LEN,
    extract_quoted_span,
    normalize_for_match,
    verify_excerpt_in_text,
)

# Candidate sentences longer than this are almost certainly extraction artifacts (concatenated
# headings, table blobs) — snapping evidence to a wall of text is not a repair.
_MAX_CANDIDATE_LEN = 600
# A candidate materially shorter than the needle is a fragment, not a counterpart: partial_ratio
# aligns it INSIDE the evidence at ~100, so without this guard a boilerplate lead-in replaces
# whole-sentence evidence (adversarial finding F2, executed at 97.2).
_MIN_CANDIDATE_RATIO = 0.6
# Digit-heavy lines are table transcriptions, not prose — never candidates (the evidence contract
# exists precisely to keep those OUT of supporting_evidence).
_MAX_DIGIT_DENSITY = 0.25
# No-figure evidence has no shared-figure guard to lean on, so its text floor is stricter than
# the guarded ``min_score``. Module constant, not a setting: promote only if the fleet readout
# says it needs tuning.
_NO_FIGURE_FLOOR = 88.0
# Cap stored audit strings — forensics, not archives.
_AUDIT_TEXT_CAP = 200

# Sentence boundary: terminal punctuation followed by whitespace, or any newline. Extracted
# filings are markdown-ish; over-splitting is fine (a clause fragment that verifies is still a
# real span), under-splitting is not.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")

_DIGIT_GROUP_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _digit_density(text: str) -> float:
    if not text:
        return 0.0
    digits = sum(1 for ch in text if ch.isdigit() or ch == ",")
    return digits / len(text)


def _sentences(source_text: str) -> List[str]:
    """Candidate spans: sentence-ish pieces of the source — length-bounded, prose-like (digit
    density capped), original form."""
    out: List[str] = []
    for piece in _SENTENCE_SPLIT_RE.split(source_text):
        s = piece.strip()
        if (
            _MIN_VERIFIABLE_LEN <= len(s) <= _MAX_CANDIDATE_LEN
            and _digit_density(s) <= _MAX_DIGIT_DENSITY
        ):
            out.append(s)
    return out


def _digit_groups(text: str) -> set:
    """Normalized digit groups ("62,151" → "62151"; "8%" → "8")."""
    return {g.replace(",", "").rstrip(".") for g in _DIGIT_GROUP_RE.findall(text)}


def _guard_figures(text: str) -> set:
    """Digit groups that discriminate between facts: years (19xx/20xx) are dropped — fiscal
    years co-occur across unrelated sentences, so sharing one proves nothing."""
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
) -> Tuple[Optional[str], float, str]:
    """Compute the snap DECISION for one evidence value (no mutation here). Returns
    ``(candidate_or_None, score, status)`` with status one of ``exact`` (verifies as-is),
    ``matched`` (a confident counterpart exists — the caller mutates only when armed),
    ``left`` (no confident counterpart), ``skipped`` (empty/short/non-string — uncounted)."""
    if not isinstance(evidence, str) or not evidence.strip():
        return None, 0.0, "skipped"
    needle = normalize_for_match(extract_quoted_span(evidence))
    if len(needle) < _MIN_VERIFIABLE_LEN:
        return None, 0.0, "skipped"
    if needle in normalized_source:
        return None, 100.0, "exact"

    guard = _guard_figures(needle)
    floor = min_score if guard else max(_NO_FIGURE_FLOOR, min_score)
    min_cand_len = int(_MIN_CANDIDATE_RATIO * len(needle))
    best_i, best_score = -1, 0.0
    for i, cand_needle in enumerate(candidate_needles):
        if len(cand_needle) < min_cand_len:
            continue
        score = max(
            fuzz.token_set_ratio(needle, cand_needle, score_cutoff=floor),
            fuzz.partial_ratio(needle, cand_needle, score_cutoff=floor),
        )
        if score > best_score and (not guard or guard & _digit_groups(cand_needle)):
            best_i, best_score = i, score
    if best_i < 0 or best_score < floor:
        return None, best_score, "left"
    snapped = candidates[best_i]
    # Round-trip guard: only offer a repair the shared exact check will actually pass — a short
    # inner quoted span shrinks the read-time needle below _MIN_VERIFIABLE_LEN (pinned edge).
    if not verify_excerpt_in_text(snapped, normalized_source):
        return None, best_score, "left"
    return snapped, best_score, "matched"


def snap_evidence(
    sections: Dict[str, Any],
    source_text: str,
    min_score: float,
    armed: bool,
    skip_sections: FrozenSet[str] = frozenset(),
) -> Optional[Dict[str, Any]]:
    """Measure (and, when ``armed``, repair) ``supporting_evidence`` on the two contracted
    surfaces. Returns the audit dict, or ``None`` when there is nothing to measure. Mutates
    ``sections`` only when ``armed`` — unarmed runs are pure measurement, recording the original
    text and the candidate for every would-snap so the fleet false-positive rate can be judged
    from stored rows before any arming decision (adversarial finding F4)."""
    if not source_text or not isinstance(sections, dict):
        return None

    targets: List[Tuple[str, str, Dict[str, Any]]] = []
    if "results_that_matter" not in skip_sections:
        rtm = sections.get("results_that_matter")
        if isinstance(rtm, dict) and isinstance(rtm.get("table"), list):
            for row in rtm["table"]:
                if isinstance(row, dict) and "supporting_evidence" in row:
                    targets.append(
                        ("results_that_matter", str(row.get("metric") or "?")[:60], row)
                    )
    if "notable_footnotes" not in skip_sections:
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
        "would_snap": [],
        "left": [],
        "min_score": min_score,
        "armed": armed,
    }
    for surface, label, item in targets:
        original = item.get("supporting_evidence")
        candidate, score, status = snap_value(
            original, candidates, candidate_needles, normalized_source, min_score
        )
        if status == "skipped":
            continue
        audit["checked"] += 1
        if status == "exact":
            audit["exact"] += 1
        elif status == "matched":
            entry = {
                "surface": surface,
                "label": label,
                "score": round(score, 1),
                # Forensics: the model's original text AND the chosen span — without both, the
                # fleet wrong-snap rate can never be measured from stored rows.
                "original": str(original)[:_AUDIT_TEXT_CAP],
                "candidate": str(candidate)[:_AUDIT_TEXT_CAP],
            }
            if armed:
                item["supporting_evidence"] = candidate
                audit["snapped"].append(entry)
            else:
                audit["would_snap"].append(entry)
        else:
            audit["left"].append({"surface": surface, "score": round(score, 1)})
    return audit if audit["checked"] else None
