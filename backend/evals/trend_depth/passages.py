"""Filing passages that state why figures moved: MD&A and selected notes, each with its EDGAR location.

A passage is one prose paragraph of a 10-K (tables are left to the XBRL facts), located by accession,
section (``Item 7`` or ``Note <n>. <title>``), the nearest heading above it, its paragraph index and
character offset in the parsed text, and a text-fragment link that opens the filing at the passage in
a browser. A passage qualifies when it states a cause ("primarily due to", "driven by", "offset by",
"decreased ... compared to") or gives forward guidance with a figure; it ranks higher when it names a
driver (a product, segment or cost line) or carries figures, and lower when it reads as boilerplate.
Many filers state causes without figures (the figures sit in the MD&A tables), so a figure is a bonus,
not a requirement.

Some filers write table-scale dollars in prose ("increased SG&A expenses by $126", in millions; Costco). A
passage records the scale its section declares (``table_scale``) and keeps its text as filed; the render
shows it through ``with_units`` ("$126 million"), so a sentence does not repeat a bare "$126".
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Optional
from urllib.parse import quote

_CAUSAL = re.compile(
    r"\b(primarily|mainly|largely|partly|partially)?\s*(due to|driven by|attributable to|as a result of|"
    r"resulting from|resulted from|reflect(?:s|ed|ing)?|because of|offset by|caused by|owing to|"
    r"was impacted by|were impacted by|benefit(?:ed)? from|contributed to|led to|higher|lower)\b",
    re.IGNORECASE,
)
_STRONG_CAUSAL = re.compile(
    r"\b(due to|driven by|attributable to|as a result of|offset by|primarily|resulted from|reflect|"
    r"(?:increased|decreased|grew|declined|rose|fell|improved)\b[^.]{0,80}\bcompared (?:to|with))",
    re.IGNORECASE,
)
_GUIDANCE = re.compile(
    r"\b((we|management|the firm|the company) (currently )?(expects?|anticipates?|estimates?)|guidance|outlook|"
    r"we plan to|we intend to)\b",
    re.IGNORECASE,
)
_CAPITAL = re.compile(r"\b(CET1|common equity tier 1|tier 1 (capital|leverage)|supplementary leverage|capital ratios?)\b", re.IGNORECASE)
_BOILERPLATE = re.compile(
    r"\b(may|could|might|risk factors|forward-looking|we recognize|critical accounting|estimates? (?:and|or) assumptions|"
    r"in accordance with|is subject to|are subject to|there can be no assurance)\b",
    re.IGNORECASE,
)
_FIGURE = re.compile(r"(\$\s?\d[\d,.]*|\d[\d,.]*\s?(%|percent|million|billion|basis points|bps))", re.IGNORECASE)
_NOTE_HEAD = re.compile(r"\n(\d{1,2})\.\s+([A-Z][^\n]{3,90})\n")
_NOTE_KEEP = re.compile(
    r"segment|revenue|product|sales|collaborat|disaggregat|debt|borrow|stockholders|shareholders|equity|"
    r"repurchase|income tax|restructur|acquisition|business combination|loans|deposits|allowance|credit loss|"
    r"leases|goodwill|impairment|insurance|reserves|losses and loss adjustment",
    re.IGNORECASE,
)
_COST_WORDS = (
    "research and development", "selling, general and administrative", "cost of goods", "cost of sales",
    "cost of revenue", "gross margin", "gross profit", "operating margin", "collaboration", "royalt",
    "effective tax rate", "income tax", "interest expense", "net interest income", "noninterest",
    "provision for credit losses", "efficiency", "deposits", "loans", "share repurchase", "dividend",
    "free cash flow", "operating activities", "capital expenditures", "impairment", "restructuring",
    "pricing", "volume", "mix", "foreign currency", "membership", "comparable sales", "units", "margin",
)
_DECLARED_SCALE = re.compile(r"\bin (millions|thousands|billions)\b", re.IGNORECASE)
_BARE_DOLLAR = re.compile(r"(?<![\w.$])\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?P<cents>\.\d+)?(?![\d,]*\d|\.\d)")
# What follows a figure, the other end of a range ("$18-19 billion", "$3 to $5 per share") skipped first.
_RANGE_END = r"\s?(?:(?:-|–|to)\s?\$?\s?[\d,]+(?:\.\d+)?\s?)?"
_SCALED_AFTER = re.compile(_RANGE_END + r"(?:million|billion|thousand|trillion|mn|bn|mm|[mbk])\b", re.I)
_PER_UNIT_AFTER = re.compile(_RANGE_END + r"(?:per\b|an? (?:\w+ )?share\b|each\b|apiece\b|/)", re.I)
_CLAUSE_BREAK = re.compile(r"[,;:(]|\.(?=\s)")
_PRICE_NOUN = re.compile(r"\b(?:fees?|prices?|priced|deposits?|upgrades?|rewards?|dues|wages?|salar(?:y|ies)|tuition|tickets?|stipends?)\b", re.I)
_AMOUNT_NOUN = re.compile(r"\b(?:revenues?|sales|expenses?|income|margins?|cash|earnings|profits?|costs?|assets|liabilities|debt)\b", re.I)
# Text between two figures that makes the second the same kind as the first: a range, or a comparison in the same
# sentence ("from $120 to $130", "averaged $65 per barrel for the full-year 2025, compared to $76 in 2024").
_LINKED = re.compile(r"(?:\bto|\band|\bor|-|–|\bcompared (?:to|with)|\bversus|\bvs\.|\bfrom)\s*$", re.I)
_SENTENCE_END = re.compile(r"[.;](?=\s)")


def declared_scale(text: str) -> str:
    """"million" when a filing section declares its amounts in millions ("(in millions)", "amounts in millions,
    except per share data") and at least 80% of its scale declarations say so, else "". Only millions: a section
    whose tables are in thousands writes its prose in millions, with the unit ("$305.0 million") or, by a slip,
    without it (Snap's FY2019 "decreased $385.0"), so a declared thousands says nothing about a bare figure."""
    counts = Counter(scale.lower() for scale in _DECLARED_SCALE.findall(text))
    total = sum(counts.values())
    return "million" if total and counts["millions"] >= 0.8 * total else ""


def with_units(text: str, scale: str) -> str:
    """The passage with ``scale`` after each bare dollar figure ("$126" -> "$126 million"), for a section that
    declares its amounts in that scale. A figure is left as filed when it already has a scale or is a price
    (cents, "per", "a share", "each"); when it is linked to the figure before it in the same sentence (a range, a
    comparison) it reads as that figure does; otherwise it is left as filed when it is the amount of a price noun in
    its clause with no amount noun between ("membership fee of $65", "deposit of $100"; but "fee changes to increase
    revenues approximately $370" is in millions). Leaving a figure as filed is the safe error: it reads as it did
    in version 1."""
    if not scale:
        return text
    out, cursor = [], 0
    previous: Optional[tuple[int, bool]] = None  # (end, given the unit) of the figure before
    for match in _BARE_DOLLAR.finditer(text):
        tail = text[match.end():match.end() + 40]
        gap = text[previous[0]:match.start()] if previous else ""
        if _SCALED_AFTER.match(tail) or _PER_UNIT_AFTER.match(tail) or len(match.group("cents") or "") == 3:
            unit = False  # ".90": a price or a per-share amount
        elif previous is not None and _LINKED.search(gap) and not _SENTENCE_END.search(gap):
            unit = previous[1]
        else:
            head = text[:match.start()]
            breaks = [b.end() for b in _CLAUSE_BREAK.finditer(head)]
            clause = head[breaks[-1] if breaks else 0:]
            nouns = list(_PRICE_NOUN.finditer(clause))
            unit = not (nouns and not _AMOUNT_NOUN.search(clause, nouns[-1].end()))
        previous = (match.end(), unit)
        if unit:
            out.append(text[cursor:match.end()] + f" {scale}")
            cursor = match.end()
    return "".join(out) + text[cursor:]


def _paragraphs(text: str) -> list[tuple[int, str]]:
    """(char offset, paragraph) over blank-line separated blocks."""
    out = []
    for match in re.finditer(r"(?:[^\n]|\n(?!\s*\n))+", text):
        block = match.group(0).strip()
        if block:
            out.append((match.start(), block))
    return out


def _is_prose(block: str) -> bool:
    if len(block) < 90:
        return False
    letters = sum(ch.isalpha() for ch in block)
    return letters / max(len(block), 1) > 0.6 and block.count(".") >= 1


def _is_heading(block: str) -> bool:
    return 3 <= len(block) <= 90 and not block.endswith(".") and sum(ch.isalpha() for ch in block) > 2 \
        and not _FIGURE.search(block)


def fragment_url(document_url: str, passage: str) -> str:
    """A text-fragment link (``#:~:text=start,end``) to the passage's first and last words."""
    words = re.sub(r"\s+", " ", passage).strip().split(" ")
    start = " ".join(words[:6])
    end = " ".join(words[-4:]) if len(words) > 12 else ""
    fragment = quote(start, safe="")
    if end:
        fragment += "," + quote(end, safe="")
    return f"{document_url}#:~:text={fragment}"


def _trim(block: str, limit: int = 1100) -> str:
    if len(block) <= limit:
        return block
    sentences = re.split(r"(?<=[.;])\s+", block)
    kept, size = [], 0
    for sentence in sentences:
        if size + len(sentence) > limit and kept:
            break
        kept.append(sentence)
        size += len(sentence) + 1
    return " ".join(kept)


def score(block: str, drivers: Iterable[str]) -> tuple[float, str]:
    """(score, kind): kind is "causal" (states why a figure moved) or "guidance" (forward statement)."""
    low = block.lower()
    strong = len(_STRONG_CAUSAL.findall(block))
    causal = len(_CAUSAL.findall(block))
    guidance = bool(_GUIDANCE.search(block))
    figures = len(_FIGURE.findall(block))
    named = sum(1 for name in drivers if name and name.lower() in low)
    cost = sum(1 for word in _COST_WORDS if word in low)
    boiler = min(len(_BOILERPLATE.findall(block)), 3)
    if strong:
        kind = "causal"
    elif guidance and figures:
        kind = "guidance"
    elif _CAPITAL.search(block) and figures:
        kind = "capital"  # regulatory capital is stated, not explained, and only text carries it
    else:
        return 0.0, ""
    value = strong * 2.0 + causal * 0.5 + min(figures, 4) * 0.5 + named * 2.0 + min(cost, 4) - boiler
    if kind in ("guidance", "capital"):
        value += 2.0
    return max(value, 0.0), kind


def _note_spans(full: str) -> list[tuple[str, int, int]]:
    """(title, start, end) of each note after the last 'Notes to ... Financial Statements' heading."""
    anchors = [m.start() for m in re.finditer(r"Notes to (the )?Consolidated Financial Statements", full, re.I)]
    base = anchors[-1] if anchors else 0
    heads = [(m.start() + base, f"Note {m.group(1)}. {m.group(2).strip()}") for m in _NOTE_HEAD.finditer(full[base:])]
    spans = []
    for i, (start, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(full)
        spans.append((title, start, end))
    return spans


def candidates(filing: dict[str, Any], parsed: dict[str, Any], fiscal_year: str, drivers: list[str]) -> list[dict[str, Any]]:
    """Every scored prose passage of one 10-K's MD&A and selected notes."""
    out: list[dict[str, Any]] = []
    full = parsed.get("full") or ""
    document_scale = declared_scale(full)

    def add(section: str, text: str, base_offset: int, source: str) -> None:
        # The section's own declaration ("(in millions)" in its tables), else the document's (CAT's early MD&As
        # declare none and follow the statements' millions).
        scale = declared_scale(text) or document_scale
        heading = ""
        for index, (offset, block) in enumerate(_paragraphs(text)):
            if _is_heading(block):
                heading = block
                continue
            if not _is_prose(block):
                continue
            value, kind = score(block, drivers)
            if value <= 0:
                continue
            passage = _trim(block)
            out.append({
                "text": passage,
                "score": value,
                "kind": kind,
                "fiscal_year": fiscal_year,
                "accession": filing["accession"],
                "form": filing["form"],
                "filed": filing["filed"],
                "section": section,
                "heading": heading,
                "paragraph": index,
                "offset": base_offset + offset,
                "offset_basis": source,
                "document_url": filing["document_url"],
                "url": fragment_url(filing["document_url"], passage),
                **({"table_scale": scale} if scale else {}),
            })

    if parsed.get("mda"):
        if parsed.get("mda_source") == "EX-13":
            exhibit = {**filing, "document_url": parsed["mda_url"]}
            before = len(out)
            add("Exhibit 13 (Annual Report): Management's Discussion and Analysis", parsed["mda"], 0, "mda")
            for passage in out[before:]:
                passage["document_url"] = exhibit["document_url"]
                passage["url"] = fragment_url(exhibit["document_url"], passage["text"])
        else:
            add("Item 7. Management's Discussion and Analysis", parsed["mda"], 0, "mda")
    for title, start, end in _note_spans(full):
        if _NOTE_KEEP.search(title):
            add(title, full[start:end], start, "full")
    return out


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", text.lower()))


def select(pool: list[dict[str, Any]], latest_year: str, inflection_years: set[str], cap: int = 90) -> list[dict[str, Any]]:
    """Rank and cap passages: deep on the latest 10-K, focused on inflection years elsewhere."""
    per_year_cap = {latest_year: 34}
    chosen: list[dict[str, Any]] = []
    seen: list[set[str]] = []
    counts: dict[str, int] = {}
    years = sorted({p["fiscal_year"] for p in pool})
    recency = {year: i / max(len(years) - 1, 1) for i, year in enumerate(years)}

    def weight(p: dict[str, Any]) -> float:
        # Newer filings win ties and near-duplicates: the latest MD&A explains the latest year, and a
        # boilerplate paragraph repeated across years should be cited from its most recent filing.
        w = p["score"] * (1.0 + 0.5 * recency[p["fiscal_year"]])
        if p["fiscal_year"] == latest_year:
            w *= 1.5
        elif p["fiscal_year"] in inflection_years:
            w *= 1.4
        return w

    ranked = sorted(pool, key=weight, reverse=True)
    for passage in ranked:
        year = passage["fiscal_year"]
        limit = per_year_cap.get(year, 12 if year in inflection_years else 6)
        if counts.get(year, 0) >= limit:
            continue
        tokens = _tokens(passage["text"])
        if any(len(tokens & other) / max(len(tokens | other), 1) > 0.7 for other in seen):
            continue  # boilerplate repeated across years
        chosen.append(passage)
        seen.append(tokens)
        counts[year] = counts.get(year, 0) + 1
        if len(chosen) >= cap:
            break
    chosen.sort(key=lambda p: (p["fiscal_year"], p["section"], p["paragraph"]), reverse=True)
    for n, passage in enumerate(chosen, start=1):
        passage["id"] = f"P{n}"
    return chosen
