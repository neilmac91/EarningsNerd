"""Attach exact section-owned units to existing capital-plan quotes; never rescale prose."""
from __future__ import annotations

import re
from typing import Any, Sequence

from app.services.ai.recovery_context import clean_filing_source, recovery_blocks
from app.services.provenance_service import _MIN_VERIFIABLE_LEN

# Deliberately narrow: a declaration immediately below the actual MD&A title, not a
# nearby table header. All exceptions are preserved verbatim. Unrecognized scopes abstain.
_DECLARATION = re.compile(
    r"\A(?:Table of Contents\s+)?Item[ \t\xa0]+2[ \t\xa0]*[—–-][ \t\xa0]*"
    r"Management[’']s Discussion and Analysis of Financial Condition and Results of Operations"
    r"\s*\n\s*(\(amounts in millions, except per share, share, percentages and warehouse count data\))",
)
_OTHER_SCOPE = re.compile(r"\b(?:amounts? in|in thousands|in millions|in billions)\b", re.I)
_CAPITAL_HEADING = "Capital Expenditure Plans"
_CONTEXT_KEY = "source_unit_context"


def attach_quote_unit_context(
    sections: dict[str, Any],
    offered_excerpt: str = "",
    layout: Sequence[tuple[str, str, int]] = (),
    *,
    recovered: bool = False,
) -> None:
    """Replace model annotations with source-owned final-primary context, or abstain.

    No source on preview, recovered forward section, missing section boundaries, multiple
    matches or conflicting scopes means no annotation. Quote/evidence bytes are untouched.
    Offsets are used only inside the exact cleaned representation, never as HTML locators.
    """
    forward = sections.get("forward_signals")
    quotes = forward.get("quotes") if isinstance(forward, dict) else None
    if not isinstance(quotes, list):
        return
    for quote in quotes:
        if isinstance(quote, dict):
            quote.pop(_CONTEXT_KEY, None)
    if recovered or not offered_excerpt or not layout:
        return
    source = clean_filing_source(offered_excerpt)
    blocks = recovery_blocks(source, layout)
    for quote in quotes:
        text = quote.get("quote") if isinstance(quote, dict) else None
        if not isinstance(text, str) or len(text.strip()) < _MIN_VERIFIABLE_LEN:
            continue
        # Whole raw match only: no fuzzy match, convenient inner fragment or normalized
        # indexes masquerading as source offsets. Duplicate occurrence is ambiguous.
        if source.count(text) != 1 or "$" not in text:
            continue
        candidates: list[str] = []
        for block in blocks:
            if block.families != ("mda",) or block.text.count(text) != 1:
                continue
            declaration = _DECLARATION.match(block.text)
            if declaration is None or _OTHER_SCOPE.search(block.text[declaration.end():]):
                continue
            heading = block.text.find(_CAPITAL_HEADING, declaration.end())
            if heading < 0 or block.text.count(_CAPITAL_HEADING) != 1:
                continue
            # Only the first paragraph under this exact standalone heading qualifies.
            if block.text[heading - 1:heading] != "\n":
                continue
            after_heading = heading + len(_CAPITAL_HEADING)
            if not block.text[after_heading:].startswith("\n\n"):
                continue
            paragraph_start = after_heading + 2
            paragraph_end = block.text.find("\n\n", paragraph_start)
            if paragraph_end < 0:
                continue  # an unterminated/truncated paragraph has no demonstrated boundary
            start = block.text.find(text)
            if paragraph_start <= start and start + len(text) <= paragraph_end:
                candidates.append(declaration[1])
        if len(candidates) == 1:
            quote[_CONTEXT_KEY] = candidates[0]
