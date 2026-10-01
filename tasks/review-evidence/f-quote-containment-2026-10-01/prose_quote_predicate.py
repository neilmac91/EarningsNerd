"""THROWAWAY offline candidate for decision F (PR #1029): prose-quotation containment.

Not production code. Imports the production normalizer and floor from an origin/main snapshot so the
replay uses exactly the citation verifier's definition of "verbatim".

unsupported_prose_quotations(answer, normalized_source) -> list[str]
  Returns one application-owned reason code per failing quoted span, in order of appearance
  (or the single code "unbalanced_quotation"). Empty list = publishable as far as this check goes.
"""
from __future__ import annotations

import re
from typing import Optional

from app.services.provenance_service import _MIN_VERIFIABLE_LEN, normalize_for_match

# Every double-quote mark production's _TYPOGRAPHY_FOLDS folds to '"': straight, curly open/close and
# low-9. Direction is ignored, because the normalizer ignores it too. Single quotes are out of scope:
# they are indistinguishable from apostrophes ("filing's").
QUOTE_MARKS = '"“”„'
_QUOTE_MARK_RE = re.compile(f"[{QUOTE_MARKS}]")
# Same pattern as copilot_service._COPILOT_MARKER_RE: an application citation marker, not quoted text.
_MARKER_RE = re.compile(r"\[(F?\s*\d+)\]", re.IGNORECASE)
# Edge characters a writer adds around a faithful quote: whitespace (incl. NBSP), sentence punctuation
# and a truncation ellipsis. Removing them only shortens the needle.
_EDGE_CHARS = " \t\r\n .,;:!?…"
# An interior elision ("...", ". . ." or the single-character ellipsis) marks a composed quotation.
_ELLIPSIS_RE = re.compile(r"\.\s*\.\s*\.|…")

UNBALANCED = "unbalanced_quotation"
SOURCE_UNAVAILABLE = "quotation_source_unavailable"
ELIDED = "elided_quotation"
NOT_IN_SOURCE = "quotation_not_in_source"
REASONS = (UNBALANCED, SOURCE_UNAVAILABLE, ELIDED, NOT_IN_SOURCE)


def quoted_spans(answer: str) -> Optional[list[str]]:
    """Inner text of each quotation, pairing marks in order; None when the marks cannot pair."""
    marks = [m.start() for m in _QUOTE_MARK_RE.finditer(answer)]
    if len(marks) % 2:
        return None
    return [answer[start + 1:end] for start, end in zip(marks[::2], marks[1::2])]


def scan(answer: Optional[str], normalized_source: Optional[str], *,
         floor: int = _MIN_VERIFIABLE_LEN, check_elision: bool = True) -> list[dict]:
    """Per-span verdicts (replay detail). The production predicate keeps only the reason codes."""
    spans = quoted_spans(answer or "")
    if spans is None:
        return [{"span": None, "reason": UNBALANCED}]
    out = []
    for raw in spans:
        literal = raw.strip(_EDGE_CHARS)
        content = _MARKER_RE.sub(" ", raw).strip(_EDGE_CHARS)
        needle = normalize_for_match(content)
        elided = bool(check_elision and _ELLIPSIS_RE.search(content))
        in_scope = elided or len(needle) >= floor
        reason = None
        if in_scope:
            if not normalized_source:
                reason = SOURCE_UNAVAILABLE
            elif not (normalize_for_match(literal) in normalized_source or needle in normalized_source):
                reason = ELIDED if elided else NOT_IN_SOURCE
        out.append({"span": raw, "needle": needle, "needle_len": len(needle), "elided": elided,
                    "in_scope": in_scope, "reason": reason})
    return out


def unsupported_prose_quotations(answer: Optional[str], normalized_source: Optional[str]) -> list[str]:
    return [item["reason"] for item in scan(answer, normalized_source) if item["reason"]]
