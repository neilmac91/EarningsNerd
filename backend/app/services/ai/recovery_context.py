"""Select bounded, labelled context from the chosen filing's already-prepared text."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from bs4 import BeautifulSoup, Comment

MAX_RECOVERY_CHARS = 30_000
_MARKUP = re.compile(r"<(?:/?[A-Za-z][\w:.-]*(?:\s[^<>]*?)?\s*/?>|!--|!DOCTYPE|\?)", re.I)
_HIDDEN_STYLE = re.compile(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\s*(?:!important\s*)?(?:;|$)", re.I)
_RECOVERED_LABELS = {
    "FINANCIAL DATA": ("financials",),
    "FINANCIAL STATEMENTS CONTEXT (recovered from filing)": ("financials",),
    "MD&A CONTEXT (recovered from filing)": ("mda",),
    "FINANCIAL & MD&A CONTEXT (recovered from filing)": ("financials", "mda"),
    "RISK & NARRATIVE CONTEXT (recovered from filing)": ("risk",),
}
_SOURCES = {
    "the_print": ("mda", "financials"),
    "results_that_matter": ("financials", "mda"),
    "earnings_quality": ("financials", "mda"),
    "value_drivers": ("financials", "mda"),
    "forward_signals": ("mda",),
    "risks": ("risk",),
    "balance_sheet_liquidity": ("financials", "mda"),
    "notable_footnotes": ("financials", "mda"),
}


@dataclass(frozen=True)
class RecoveryBlock:
    label: str
    text: str
    families: tuple[str, ...]


def clean_filing_source(text: str) -> str:
    """Preserve plain text; remove explicit hidden markup without claiming CSS visibility."""
    if not text or not text.strip():
        return ""
    if not _MARKUP.search(text):
        return text
    soup = None
    try:
        soup = BeautifulSoup(text, "html.parser")
        for tag in soup.find_all(True):
            # A previously decomposed parent also decomposes its descendants.
            if not tag.name:
                continue
            if (tag.name.lower() in {"script", "style", "template", "ix:hidden", "ix:header"}
                    or tag.has_attr("hidden") or _HIDDEN_STYLE.search(str(tag.get("style", "")))):
                tag.decompose()
        for comment in soup.find_all(string=lambda node: isinstance(node, Comment)):
            comment.extract()
        return soup.get_text(separator="\n", strip=False)
    except Exception:  # noqa: BLE001 — unavailable source is safer than a raw-HTML fallback.
        return ""
    finally:
        if soup is not None:
            soup.decompose()


def _body(text: str) -> str:
    # These are the assembler's separators, not a generic heading/paragraph rewrite.
    text = text.strip().removeprefix("=" * 50 + "\n").removesuffix("\n" + "=" * 50).strip()
    return "" if text == "=" * 50 else text


def recovery_blocks(sample: str, layout: Sequence[tuple[str, str, int]]) -> tuple[RecoveryBlock, ...]:
    """Recognize only exact generated labels, retaining repeated blocks and honest labels."""
    # The critical-section producer prefixes its first heading with this exact separator.
    # Normalize only the private recovery view; the primary excerpt remains byte-identical.
    sample = sample.removeprefix("\n\n" + "=" * 50)
    labels = {label: (family,) for family, label, _ in layout}
    labels.update(_RECOVERED_LABELS)
    pattern = re.compile(r"^(" + "|".join(re.escape(label) for label in labels) + r"):[ \t]*\r?$", re.M)
    matches = list(pattern.finditer(sample))
    blocks: list[RecoveryBlock] = []
    prefix = _body(sample[:matches[0].start()] if matches else sample)
    if prefix:
        blocks.append(RecoveryBlock("Filing excerpt", prefix, ("filing",)))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sample)
        text = _body(sample[match.end():end])
        if text:
            blocks.append(RecoveryBlock(match[1], text, labels[match[1]]))
    return tuple(blocks)


def _shares(capacities: list[int], budget: int) -> list[int]:
    """Stable water filling: short sources release their unused share to longer sources."""
    allocated = [0] * len(capacities)
    while budget > 0:
        active = [i for i, cap in enumerate(capacities) if allocated[i] < cap]
        if not active:
            break
        share = max(1, budget // len(active))
        for index in active:
            take = min(share, capacities[index] - allocated[index], budget)
            allocated[index] += take
            budget -= take
    return allocated


def _cost(block: RecoveryBlock) -> int:
    return len(block.label) + 2 + len(block.text) + 2  # colon/newline + trailing separator


def _render_family(blocks: list[RecoveryBlock], budget: int) -> str:
    selected = []
    overhead = 0
    for block in blocks:
        cost = len(block.label) + 4
        if overhead + cost + len(selected) + 1 > budget:
            break
        selected.append(block)
        overhead += cost
    shares = _shares([len(block.text) for block in selected], budget - overhead)
    return "".join(f"{block.label}:\n{block.text[:share]}\n\n" for block, share in zip(selected, shares))


def build_recovery_context(section: str, blocks: tuple[RecoveryBlock, ...], sample: str) -> str:
    """Give each available family a share before splitting that share between its blocks."""
    families: dict[str, list[RecoveryBlock]] = {}
    seen: set[str] = set()
    for family in _SOURCES.get(section, ()):
        for block in blocks:
            if family in block.families and block.text not in seen:
                families.setdefault(family, []).append(block)
                seen.add(block.text)
    if not families:
        if not sample.strip():
            return ""
        families = {"filing": [RecoveryBlock("Filing excerpt", sample.strip(), ("filing",))]}
    groups = list(families.values())
    # Reserve separators uniformly, then remove exactly the final separator.
    shares = _shares([sum(_cost(block) for block in group) for group in groups], MAX_RECOVERY_CHARS + 2)
    rendered = "".join(_render_family(group, share) for group, share in zip(groups, shares))
    return rendered[:-2] if rendered else ""
