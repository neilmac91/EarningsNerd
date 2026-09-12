"""Select one attributed financing passage from already labelled filing context.

Ranking establishes relevance only, never a cause, numerical relationship or source fact.
No text is assembled, rewritten or fetched; an uncertain source boundary abstains.
"""
from __future__ import annotations

import re
from typing import Callable

from app.services.ai.extraction import _ExtractionMixin
from app.services.ai.recovery_context import recovery_blocks

# Reuse the actual assembler's labels, including risk labels so they terminate allowed blocks.
_LAYOUT = tuple(dict.fromkeys(
    row for layout in _ExtractionMixin._SECTION_LAYOUT.values() for row in layout
))
_FINANCING = re.compile(r"\b(?:financ(?:ing|ed)|fund(?:ing|ed)|borrow(?:ing|ings|ed)|indebtedness|proceeds)\b", re.I)
_TOPICS = (
    re.compile(r"\b(?:borrow(?:ing|ings|ed)|indebtedness|loans?|debt)\b", re.I),
    re.compile(r"\b(?:financ(?:ing|ed)|fund(?:ing|ed)|proceeds)\b", re.I),
    re.compile(r"\b(?:cash|liquidity)\b", re.I),
    re.compile(r"\b(?:credit|receivables|lending)\b", re.I),
    re.compile(r"\b(?:operations?|operating|activities)\b", re.I),
)
# These surface forms rank topical relevance only; they are not a causality/tense proof.
_FINANCING_RELATION = re.compile(
    r"(?:cash\s+(?:used\s+in|provided\s+by)\s+financing|"
    r"financing\s+activities.{0,100}\b(?:provided|generated|reflected|increased|decreased)|"
    r"indebtedness\s+to\s+finance)", re.I,
)
_ACTION_WORD = re.compile(r"\b(?:used|uses|funded|financed|provided|generated|resulted|reflected|reflects)\b", re.I)
_WORD = re.compile(r"\b[A-Za-z][A-Za-z’'-]*\b")


def fallback_capital_passages(source_text: str, qualifies: Callable[[str], bool]) -> list[str]:
    """One internal verbatim source passage, restricted to labelled financial/MD&A source.

    Only internal physical source lines qualify: wrapped prose and tables are not joined.
    Block-edge lines can be clipped by extraction/recovery before a synthetic separator;
    exclude both edges even when they end at a sentence. This is not HTML-paragraph proof.
    ``qualifies`` is the binder's existing unique-source/length/number-denomination guard.
    """
    ranked: list[tuple[int, int, str]] = []
    for block in recovery_blocks(source_text, _LAYOUT):
        if not block.families or not set(block.families) <= {"financials", "mda"}:
            continue
        lines = [line for line in block.text.splitlines() if line.strip()]
        for line in lines[1:-1]:
            paragraph = line.strip()
            if (not 25 <= len(paragraph) <= 2000 or not paragraph[0].isupper()
                    or not paragraph.endswith((".", ".”", '."'))
                    or len(_WORD.findall(paragraph)) < 12):
                continue
            # Source text must supply both boundaries. Do not accept a suffix of a larger line.
            occurrences = list(re.finditer(re.escape(paragraph), source_text))
            if len(occurrences) != 1:
                continue
            start, end = occurrences[0].span()
            before = source_text[source_text.rfind("\n", 0, start) + 1:start]
            if before.strip() or end == len(source_text) or source_text[end:].split("\n", 1)[0].strip():
                continue
            if (not _FINANCING.search(paragraph) or not _ACTION_WORD.search(paragraph)
                    or not _FINANCING_RELATION.search(paragraph)):
                continue
            matched = [bool(pattern.search(paragraph)) for pattern in _TOPICS]
            if not (matched[2] and matched[4]) or not qualifies(paragraph):
                continue
            # Distinct topics, not repeated keywords; source order resolves equal relevance.
            ranked.append((sum(matched), -start, paragraph))
    if not ranked:
        return []
    return [max(ranked, key=lambda candidate: candidate[:2])[2]]
