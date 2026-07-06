"""Shared citation-marker group knowledge — what makes a bracket group a CITATION rather than
prose, and how to split a multi-reference group into the single-marker brackets the resolvers
expect. Used by the trend-analysis resolver (inline group expansion) and the copilot resolver
(pre-pass normalization), so the tricky classification lives in exactly one place.

Every regex here is deliberately LINEAR — no lazy quantifiers, no overlapping alternations:
these patterns scan model-generated (semi-adversarial) output on the event loop, and an
ambiguous form in an early version measured O(n²)-to-exponential on degenerate outputs.
"""
import re
from typing import Callable, Optional

# Every bracket group; whether it is a citation (vs prose) is decided in code.
MARKER_GROUP_RE = re.compile(r"\[([^\[\]]*)\]")
# A dataset F-reference ("F12", case/space tolerant). Copilot additionally has plain [n] text
# citations — pass a different ref regex where needed.
MARKER_REF_RE = re.compile(r"F\s*(\d+)", re.IGNORECASE)
# What may legally surround the references inside one bracket group: list/range/comparison
# connector words and punctuation ("F1, F2", "F1..F10", "F1-F2", "F1 vs F2", "F1 and F2",
# "F1 through F10", "F9 versus F10", "F1 or F2"). Validated in two LINEAR passes (strip the
# refs, strip whole connector words, then a single character class).
MARKER_CONNECTOR_WORD_RE = re.compile(r"\b(?:versus|vs|through|and|to|or)\b", re.IGNORECASE)
MARKER_SEPARATOR_CHARS_RE = re.compile(r"^[\s,;&/.·–—-]*$")


def is_citation_group(content: str, ref_re: re.Pattern[str] = MARKER_REF_RE) -> bool:
    """True when a bracket group's content is references + connectors/separators ONLY — i.e. a
    citation group a model emitted, not prose that happens to contain a ref-shaped token."""
    residue = ref_re.sub("", content)
    residue = MARKER_CONNECTOR_WORD_RE.sub("", residue)
    return MARKER_SEPARATOR_CHARS_RE.match(residue) is not None


def expand_citation_marker_groups(
    text: str,
    ref_re: re.Pattern[str] = MARKER_REF_RE,
    normalize: Callable[[str], str] = lambda ref: f"F{int(ref)}",
    require_re: Optional[re.Pattern[str]] = None,
) -> str:
    """Split every MULTI-reference citation group into adjacent single-marker brackets:
    ``[F1, F2]`` / ``[F1..F3]`` / ``[F1 vs F2]`` → ``[F1] [F2]`` / ``[F1] [F3]`` (ranges keep
    their written endpoints — expansion never invents members). Single-marker brackets and
    prose brackets pass through untouched, so a resolver that only understands single markers
    (copilot) can run downstream unchanged.

    ``ref_re`` must capture the reference identity in group(1); ``normalize`` renders a captured
    identity back into marker text (dedup within a group happens on the normalized form).
    ``require_re``: when set, a group is only expanded if this pattern matches its content —
    copilot passes the F-ref pattern here so an all-plain-number group (which could be a
    bracketed thousands figure like ``[1,234]``) is never touched.
    """
    pieces: list[str] = []
    cursor = 0
    for match in MARKER_GROUP_RE.finditer(text):
        content = match.group(1)
        refs = ref_re.findall(content)
        if len(refs) < 2 or not is_citation_group(content, ref_re):
            continue  # single marker, or prose — leave the original text untouched
        if require_re is not None and not require_re.search(content):
            continue
        normalized: list[str] = []
        for ref in refs:
            marker = normalize(ref)
            if marker not in normalized:
                normalized.append(marker)
        pieces.append(text[cursor:match.start()])
        pieces.append(" ".join(f"[{marker}]" for marker in normalized))
        cursor = match.end()
    pieces.append(text[cursor:])
    return "".join(pieces)