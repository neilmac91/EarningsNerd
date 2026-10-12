"""Deterministic wording diff of one filing section against its prior-period twin.

Pure functions, no I/O, no model: ``diff_sections(prior_text, later_text)`` turns two stored
section texts (``filing_section_service`` extracts and persists them) into a change list a reader
can review paragraph by paragraph. Everything here is filing text only (CLAUDE.md rule 2); the
output quotes the filings and nothing else.

Pipeline
1. ``split_paragraphs``: blank-line blocks → cleaned paragraphs. Page furniture is dropped and
   counted by class (bare page numbers, running headers such as "Apple Inc. | 2025 Form 10-K | 7",
   "Table of Contents", a repeated company-name banner, the section's own "Item 1A. Risk Factors"
   heading). Filing agents that emit one block per *line* (every line ends in a trailing space
   before the blank line) are re-flowed back into paragraphs, so a 10-K typeset that way still
   pairs with its unwrapped predecessor.
2. Exact pairing on a normalized key (NFKC, soft hyphens and zero-width characters removed,
   curly quotes and dashes straightened, whitespace collapsed, a leading bullet glyph ignored), so
   a re-typeset paragraph is "unchanged", never "modified". Out-of-order exact pairs are "moved".
3. Fuzzy pairing of the remainder: global best-first on ``difflib`` word similarity
   (``PAIR_THRESHOLD``), a Jaccard prefilter keeping it quadratic-cheap. Each pair becomes a
   "modified" item with word-level ops; what stays unpaired is "added" or "removed".

Items come back in later-section reading order, each with a content-addressed ``id`` that is
stable across re-extraction while the two paragraphs' wording is unchanged (a review label can
hang on it). ``counts``/``words`` summarize the section for lists and gates: ``words.changed_ratio``
is (inserted + deleted) / later words, the noise measure the corpus gate reads.

The only tunables are module constants; ``ENGINE_VERSION`` changes whenever the output for the
same input could change (persisted summaries carry it and are recomputed when it moves).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Optional

ENGINE_VERSION = 1

# Minimum difflib word-sequence ratio for two paragraphs to count as one edited paragraph.
PAIR_THRESHOLD = 0.6
# Cheap set-overlap floor below which the ratio is not even computed.
_JACCARD_PREFILTER = 0.25
# Blocks of at most this many characters are checked for furniture patterns.
_SHORT_BLOCK = 120
# A short block repeated verbatim at least this often inside one section is a running banner.
_REPEAT_BANNER_MIN = 3

_ZERO_WIDTH = dict.fromkeys(map(ord, "­​‌‍⁠﻿"), None)
_QUOTES_DASHES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "…": "...",
})
_BULLETS = "•·▪●○◦▪■□‣⁃*"
_BULLET_PREFIX = re.compile(rf"^[{re.escape(_BULLETS)}]\s*")
_SPACES = re.compile(r"[ \t   ]+")
_INNER_NEWLINES = re.compile(r"\s*\n\s*")
_BLOCK_SEPARATOR = re.compile(r"\n[ \t ]*\n")
_TERMINAL = re.compile(r"""[.!?:;]["'”’)\]]*$""")
# Arabic page numbers (any case for "Page"), or a lowercase roman numeral (front-matter style).
_PAGE_NUMBER = re.compile(
    r"^(?:[Pp]age\s*)?\d{1,4}$|^(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})$"
)
_RUNNING_HEADER = re.compile(r"form\s+10-[kq]\b", re.I)
_TRAILING_NUMBER = re.compile(r"\d\s*$")
_TOC_OR_PART = re.compile(r"^(?:table\s+of\s+contents|part\s+[ivx]+\.?)$", re.I)
_SECTION_HEADING = re.compile(r"^item\s*1a\.?\s*[-.:\u2013\u2014]?\s*risk\s+factors\.?$", re.I)
_HAS_LETTER = re.compile(r"[^\W\d_]")
_WORD_PUNCT = re.compile(r"^[^\w]+|[^\w]+$")


@dataclass(frozen=True)
class Paragraph:
    """One compared paragraph: what a reader sees (``text``) and what the matcher sees."""

    index: int
    text: str
    key: str
    tokens: tuple[str, ...]        # normalized tokens, aligned 1:1 with ``text.split()``
    sim_words: tuple[str, ...]     # lowercase, punctuation-stripped tokens for similarity
    sim_set: frozenset[str]


def _clean_display(block: str) -> str:
    text = unicodedata.normalize("NFKC", block).translate(_ZERO_WIDTH)
    text = _INNER_NEWLINES.sub(" ", text.strip())
    text = _SPACES.sub(" ", text).strip()
    # "•pricing;" and "• pricing;" are the same bullet: give the glyph its own token.
    if text and text[0] in _BULLETS and len(text) > 1 and not text[1].isspace():
        text = text[0] + " " + text[1:]
    return text


def _normalize_token(token: str) -> str:
    return token.translate(_QUOTES_DASHES)


def _match_key(tokens: Iterable[str]) -> str:
    return _BULLET_PREFIX.sub("", " ".join(tokens))


def _sim_words(tokens: Iterable[str]) -> tuple[str, ...]:
    words = []
    for token in tokens:
        stripped = _WORD_PUNCT.sub("", token).lower()
        if stripped:
            words.append(stripped)
    return tuple(words)


def _paragraph(index: int, text: str) -> Paragraph:
    tokens = tuple(_normalize_token(t) for t in text.split())
    words = _sim_words(tokens)
    return Paragraph(index=index, text=text, key=_match_key(tokens), tokens=tokens,
                     sim_words=words, sim_set=frozenset(words))


def _furniture_class(text: str, repeated: Counter) -> Optional[str]:
    """The exclusion class of a cleaned block, or None when it is prose to compare."""
    if not text:
        return "blank"
    if _PAGE_NUMBER.match(text):
        return "page_number"
    if not _HAS_LETTER.search(text):
        return "no_letters"
    if len(text) > _SHORT_BLOCK:
        return None
    if _SECTION_HEADING.match(text):
        return "section_heading"
    if _TOC_OR_PART.match(text):
        return "running_header"
    if _RUNNING_HEADER.search(text) and ("|" in text or _TRAILING_NUMBER.search(text)):
        return "running_header"
    if (
        repeated[text] >= _REPEAT_BANNER_MIN
        and not _TERMINAL.search(text)
        and text[0] not in _BULLETS
    ):
        return "running_header"
    return None


def _is_wrapped_line(raw_block: str, text: str) -> bool:
    """A block that ends in whitespace (before the blank line) and in no sentence punctuation is a
    typeset line, not a paragraph: its successor continues it."""
    return bool(text) and raw_block != raw_block.rstrip(" \t ") and not _TERMINAL.search(text)


def split_paragraphs(text: str) -> tuple[list[Paragraph], dict[str, int]]:
    """Cleaned, re-flowed paragraphs of a section text plus the count of dropped blocks per class."""
    raw_blocks = _BLOCK_SEPARATOR.split(text or "")
    cleaned = [_clean_display(block) for block in raw_blocks]
    repeated = Counter(t for t in cleaned if t and len(t) <= _SHORT_BLOCK)
    excluded: Counter = Counter()
    merged: list[tuple[str, bool]] = []  # (display text, continues into the next block)
    for raw, clean in zip(raw_blocks, cleaned):
        cls = _furniture_class(clean, repeated)
        if cls is not None:
            if cls != "blank":
                excluded[cls] += 1
            continue
        wrapped = _is_wrapped_line(raw, clean)
        if merged:
            prev_text, prev_wrapped = merged[-1]
            continues = (prev_wrapped or clean[0].islower()) and not _TERMINAL.search(prev_text)
            if continues and clean[0] not in _BULLETS:
                merged[-1] = (prev_text + " " + clean, wrapped)
                continue
        merged.append((clean, wrapped))
    paragraphs = [_paragraph(i, t) for i, (t, _) in enumerate(merged)]
    return paragraphs, dict(sorted(excluded.items()))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def _ratio(a: Paragraph, b: Paragraph) -> float:
    matcher = SequenceMatcher(None, a.sim_words, b.sim_words, autojunk=False)
    if matcher.real_quick_ratio() < PAIR_THRESHOLD or matcher.quick_ratio() < PAIR_THRESHOLD:
        return 0.0
    return matcher.ratio()


def _exact_pairs(prior: list[Paragraph], later: list[Paragraph]) -> list[tuple[int, int]]:
    """Pair identical keys in reading order (first unmatched occurrence on each side)."""
    by_key: dict[str, list[int]] = {}
    for p in prior:
        by_key.setdefault(p.key, []).append(p.index)
    pairs = []
    for lp in later:
        queue = by_key.get(lp.key)
        if queue:
            pairs.append((queue.pop(0), lp.index))
    return pairs


def _fuzzy_pairs(prior: list[Paragraph], later: list[Paragraph]) -> list[tuple[float, int, int]]:
    """Global best-first pairing of the unpaired remainder above ``PAIR_THRESHOLD``."""
    candidates: list[tuple[float, int, int]] = []
    for p in prior:
        for lp in later:
            if _jaccard(p.sim_set, lp.sim_set) < _JACCARD_PREFILTER:
                continue
            score = _ratio(p, lp)
            if score >= PAIR_THRESHOLD:
                candidates.append((score, p.index, lp.index))
    # Highest similarity first; ties resolve by position so the output is order-independent.
    candidates.sort(key=lambda c: (-c[0], c[2], c[1]))
    used_prior: set[int] = set()
    used_later: set[int] = set()
    pairs = []
    for score, i, j in candidates:
        if i in used_prior or j in used_later:
            continue
        used_prior.add(i)
        used_later.add(j)
        pairs.append((score, i, j))
    return pairs


def _in_order(pairs: list[tuple[int, int]]) -> set[tuple[int, int]]:
    """The pairs on a longest increasing subsequence of prior indices (in later order): the
    paragraphs that kept their relative position. Everything else moved."""
    ordered = sorted(pairs, key=lambda pr: pr[1])
    if not ordered:
        return set()
    tails: list[int] = []        # tails[k] = prior index ending the best chain of length k+1
    tail_pos: list[int] = []     # position in ``ordered`` of that chain end
    prev: list[int] = [-1] * len(ordered)
    for pos, (i, _) in enumerate(ordered):
        lo, hi = 0, len(tails)
        while lo < hi:
            mid = (lo + hi) // 2
            if tails[mid] < i:
                lo = mid + 1
            else:
                hi = mid
        if lo == len(tails):
            tails.append(i)
            tail_pos.append(pos)
        else:
            tails[lo] = i
            tail_pos[lo] = pos
        prev[pos] = tail_pos[lo - 1] if lo > 0 else -1
    chain = set()
    pos = tail_pos[-1]
    while pos != -1:
        chain.add(ordered[pos])
        pos = prev[pos]
    return chain


def word_ops(before: Paragraph, after: Paragraph) -> list[list[str]]:
    """Word-level segments ``[kind, text]`` with kind ``equal`` / ``delete`` / ``insert``.

    The prior paragraph is the ``equal`` + ``delete`` segments in order, the later one the
    ``equal`` + ``insert`` segments: a client reconstructs both from the ops alone.
    """
    matcher = SequenceMatcher(None, before.tokens, after.tokens, autojunk=False)
    a_words = before.text.split()
    b_words = after.text.split()
    ops: list[list[str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ops.append(["equal", " ".join(b_words[j1:j2])])
            continue
        if tag in ("delete", "replace"):
            ops.append(["delete", " ".join(a_words[i1:i2])])
        if tag in ("insert", "replace"):
            ops.append(["insert", " ".join(b_words[j1:j2])])
    return ops


def _item_id(kind: str, before: Optional[str], after: Optional[str]) -> str:
    digest = hashlib.sha256(f"{kind}\x1f{before or ''}\x1f{after or ''}".encode("utf-8")).hexdigest()
    return digest[:16]


def diff_sections(prior_text: str, later_text: str) -> dict[str, Any]:
    """Compare a section's prior-period text with its later text; see the module docstring."""
    prior, prior_excluded = split_paragraphs(prior_text)
    later, later_excluded = split_paragraphs(later_text)

    exact = _exact_pairs(prior, later)
    paired_prior = {i for i, _ in exact}
    paired_later = {j for _, j in exact}
    fuzzy = _fuzzy_pairs(
        [p for p in prior if p.index not in paired_prior],
        [lp for lp in later if lp.index not in paired_later],
    )
    all_pairs = exact + [(i, j) for _, i, j in fuzzy]
    kept_order = _in_order(all_pairs)
    similarity = {(i, j): score for score, i, j in fuzzy}
    for _, i, j in fuzzy:
        paired_prior.add(i)
        paired_later.add(j)

    items: list[tuple[tuple[float, int, int], dict[str, Any]]] = []
    unchanged = moved = 0
    for i, j in all_pairs:
        p, lp = prior[i], later[j]
        in_order = (i, j) in kept_order
        if (i, j) in similarity:
            ops = word_ops(p, lp)
            item = {
                "id": _item_id("modified", p.key, lp.key),
                "kind": "modified",
                "index": j,
                "prior_index": i,
                "similarity": round(similarity[(i, j)], 3),
                "moved": not in_order,
                "ops": ops,
            }
            items.append(((j, 0, i), item))
        elif in_order:
            unchanged += 1
        else:
            moved += 1
            items.append(((j, 0, i), {
                "id": _item_id("moved", p.key, lp.key), "kind": "moved", "index": j, "prior_index": i, "after": lp.text,
            }))
    for lp in later:
        if lp.index not in paired_later:
            items.append(((lp.index, 0, -1), {
                "id": _item_id("added", None, lp.key), "kind": "added", "index": lp.index, "after": lp.text,
            }))
    # A removed paragraph is anchored just after the later position of the nearest paired prior
    # paragraph before it, so it reads where it used to sit.
    later_of_prior = {i: j for i, j in all_pairs}
    anchor = -1
    for p in prior:
        if p.index in later_of_prior:
            anchor = later_of_prior[p.index]
        else:
            items.append(((anchor, 1, p.index), {
                "id": _item_id("removed", p.key, None), "kind": "removed", "prior_index": p.index, "before": p.text,
            }))
    items.sort(key=lambda entry: entry[0])
    ordered = [item for _, item in items]

    counts = Counter(item["kind"] for item in ordered)
    inserted = deleted = 0
    for item in ordered:
        if item["kind"] == "modified":
            for kind, segment in item["ops"]:
                n = len(segment.split())
                if kind == "insert":
                    inserted += n
                elif kind == "delete":
                    deleted += n
        elif item["kind"] == "added":
            inserted += len(item["after"].split())
        elif item["kind"] == "removed":
            deleted += len(item["before"].split())
    later_words = sum(len(lp.tokens) for lp in later)
    return {
        "engine_version": ENGINE_VERSION,
        "paragraphs": {
            "prior": len(prior),
            "later": len(later),
            "prior_excluded": prior_excluded,
            "later_excluded": later_excluded,
        },
        "counts": {
            "unchanged": unchanged,
            "modified": counts.get("modified", 0),
            "added": counts.get("added", 0),
            "removed": counts.get("removed", 0),
            "moved": moved,
        },
        "words": {
            "later_total": later_words,
            "inserted": inserted,
            "deleted": deleted,
            "changed_ratio": round((inserted + deleted) / later_words, 4) if later_words else 0.0,
        },
        "has_changes": bool(ordered),
        "items": ordered,
    }
