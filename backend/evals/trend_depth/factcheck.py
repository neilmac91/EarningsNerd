"""Fact-check gate: every number in a generated analysis must reconcile to what its sentence cites.

Input is a list of sentences ``{section, text, type}`` (``type``: fact | comparison | cause | judgement)
whose text carries inline citations (``[F12]``, ``[D40][P7]``) into an evidence pack. For each sentence:

1. Every cited ID must exist in the pack.
2. Every number is parsed with its unit (dollars and scale, %, pp or basis points, x or times, days,
   years, shares, per-share) and qualifier ("about", "more than", "nearly").
3. A number reconciles when it matches, at its printed precision (half a unit of the last printed digit,
   five per cent for "about"), one of: a cited value; a value computed from two or more cited values
   (growth, CAGR over the periods between them, share, difference, ratio, percentage-point change, sum,
   mean); or a figure printed in a cited filing passage. Signs compare by magnitude ("fell 12%" cites -12%),
   and a direction word next to a signed change must agree with its sign. "Improved" or "worsened" reads
   inverted for a metric where lower is better (an efficiency or cost ratio). A value labelled "A minus B" (revenue
   growth minus operating-cost growth) has its sign checked only where the clause compares its sides in a form read
   with certainty (``compared_sides``), as the side it names first against the other: a move ("costs grew 0.3pp
   faster than revenue" says costs minus revenue is +0.3, "costs fell 1.2pp less than revenue" +1.2) or a standing
   of a growth rate ("revenue growth ran 4.4pp behind cost growth" -4.4, "revenue growth beat cost growth by 4.4pp"
   +4.4; of a line named without "growth" only in a year the two lines did not both fall). In every other form (an
   appositive, a passive, a side named as its fall, a participle after a comma) it is read by magnitude alone: a
   direction word beside it is one side's move, not its sign. A gap between two levels
   of one year ("net margin minus operating margin (pp, same year)") carries no direction, like the difference of
   the two margins it equals.
4. If the sentence names fiscal years, the matched value must belong to one of them.
5. Tier rules: a number with no citation fails; a ``cause`` sentence must cite a filing passage; a
   ``judgement`` sentence may restate cited numbers but never introduce one.

A run passes only with zero failures; ``check(..., backstops=True)`` also fails the backstop probes' hits
(``probes.py``: a verified number said about another ratio, basis, year or sign, or a figure built on a break the
pack names: debt, liquidity or a peer's year). Counts of periods ("three consecutive years") are recorded as
``unverified_count`` (they are not values a pack carries) and are left to the rubric judge.

``backstops=False`` is this gate without the probes, not the gate eval-v1 ran: the narrow fixes to its artefacts
(DEEPSEEK-ERRORS.md fix 7) apply either way. eval-v1's own verdicts come from the gate as committed at ``b3ed8ef``
(``replay.base_gate``, the report's ``old_gate``).
"""
from __future__ import annotations

import functools
import itertools
import math
import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, NamedTuple, Optional

CITATION_RE = re.compile(r"\[((?:[FXSDRPQ]\d{1,4})(?:\s*[,;]\s*[FXSDRPQ]\d{1,4})*)\]")
ID_RE = re.compile(r"[FXSDRPQ]\d{1,4}")
TYPE_TAG_RE = re.compile(r"\s*\{(fact|comparison|cause|judgement)\}\s*$")

_SCALE = {
    "thousand": 1e3, "k": 1e3,
    "million": 1e6, "mn": 1e6, "m": 1e6, "mm": 1e6,
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "trillion": 1e12, "tn": 1e12, "t": 1e12,
}
NUMBER_RE = re.compile(
    r"(?P<neg>[-−–](?=\$?\s?\d))?"
    r"(?P<cur>US\$|\$)?(?P<curneg>(?<=\$)[-−–](?=\d))?\s?"  # "$-147.8 billion": the sign after the currency
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s?(?P<scale>trillion|billion|million|thousand|tn|bn|mn|mm|[kmbt])\b)?"
    r"(?:\s?(?P<unit>(?:st|nd|rd|th)\s?percentile|%|percent(?:age points?)?|pp\b|ppts?\b|percentage[- ]points?|basis[- ]points?|bps\b|bp\b|x\b|×|times\b|"
    r"days\b|years?\b|shares\b|per (?:diluted |basic )?share))?",
    re.IGNORECASE,
)
_NON_FIGURES = re.compile(
    r"\b(?:FY|Q[1-4]\s?|fiscal\s+(?:year\s+)?)\d{2,4}\b|\b(?:10-K|10-Q|8-K|20-F|Form\s+\S+|Item\s+\d+[A-Z]?|Note\s+\d+|"
    r"Part\s+[IVX]+|ASU\s+\d{4}-\d{2}|ASC\s+\d+|Section\s+\d+)\b|\(\s?[ivx]+\s?\)|\b\d{4}Q[1-4]\b",
    re.IGNORECASE,
)
_QUALIFIER_WORDS = (
    ("approx", r"about|approximately|approx\.|around|roughly|some|circa|close to|~"),
    ("nearly", r"nearly|almost|just under|just shy of"),
    ("at_least", r"more than|over|above|exceeding|in excess of|at least|upwards of"),
    ("at_most", r"less than|under|below|at most|up to"),
)
_QUALIFIERS = tuple((name, re.compile(rf"\b(?:{words})\s*$", re.I)) for name, words in _QUALIFIER_WORDS)
_UP_WORDS = re.compile(r"\b(rose|rise|rising|increas\w*|grew|grow(?!th)\w*|gain\w*|expand\w*|climb\w*|up|higher|improv\w*|jump\w*|surg\w*|widen\w*)\b", re.I)
_DOWN_WORDS = re.compile(r"\b(fell|fall\w*|declin\w*|decreas\w*|drop\w*|shrank|shrink\w*|contract\w*|down|lower|compress\w*|slipp?\w*|eroded|erod\w*|narrow\w*|deteriorat\w*|worsen\w*|reduc\w*)\b", re.I)
# Words that say better or worse rather than up or down: for a metric where lower is better (a bank's efficiency
# ratio, a cost line's share of revenue) "improved" means the value fell. Keyed on the matched value's label.
_EVALUATIVE_WORDS = re.compile(r"^(?:improv\w*|deteriorat\w*|worsen\w*)$", re.I)
_LOWER_IS_BETTER = re.compile(
    r"^(?:efficiency ratio\b|(?:cost of revenue|r&d|sg&a|g&a|selling & marketing|acquired ipr&d|credit-loss provision|"
    r"losses and claims) % of\b)", re.I)
_LEVEL_PREPOSITION = re.compile(r"^\s*(?:back\s+|further\s+)?(?:to|below|above|under|over|toward|towards|beyond|past)\b", re.I)
_MULTIPLE_WORDS = {"doubled": 2.0, "tripled": 3.0, "quadrupled": 4.0, "halved": 0.5}
_YEAR_RE = re.compile(r"\b(?:FY\s?|fiscal\s+(?:year\s+)?)?((?:19|20)\d{2})\b", re.I)
_COUNT_UNITS = re.compile(r"^\s*(?:consecutive\s+|straight\s+|successive\s+)?(years?|quarters?|periods?|segments?|products?|times?|consecutive|straight)\b", re.I)


@dataclass
class Claim:
    text: str
    value: float
    unit: str  # usd | pct | pp | x | days | years | shares | usd_per_share | plain | count | multiple
    decimals: int
    scale: float
    qualifier: str = ""
    start: int = 0


@dataclass
class Candidate:
    value: float
    unit: str
    how: str
    ids: tuple[str, ...]
    periods: tuple[str, ...]
    signed: bool = False
    slack: float = 0.0  # extra absolute tolerance: display rounding of the inputs a difference was computed from


@dataclass
class SentenceResult:
    section: str
    text: str
    type: str
    citations: list[str]
    claims: list[dict[str, Any]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def _clean_for_numbers(text: str) -> str:
    text = CITATION_RE.sub(lambda m: " " * len(m.group(0)), text)
    return _NON_FIGURES.sub(lambda m: " " * len(m.group(0)), text)


def parse_claims(text: str) -> list[Claim]:
    clean = _clean_for_numbers(text)
    claims: list[Claim] = []
    for match in NUMBER_RE.finditer(clean):
        raw = match.group("num")
        start = match.start("num")
        before = clean[max(0, start - 1):start]
        lead = clean[max(0, match.start() - 1):match.start()]
        range_end = False
        if match.group("neg") and lead and (lead.isalnum() or lead in "-/"):
            if not lead.isdigit():
                continue  # a hyphenated identifier ("COVID-19"), not a negative figure
            range_end = True  # "$18-19 billion": the upper end of a range, not a negative figure
        signed = bool(match.group("neg") or match.group("curneg"))
        if before and (before.isalpha() or before in "/") or (before in "-–−" and not signed):
            continue  # part of an identifier ("H.R. 1", "1/3")
        after = clean[match.end("num"):match.end("num") + 1]
        if after and after.isalpha() and not (match.group("scale") or match.group("unit")):
            continue  # "3rd", "2nd"
        number = float(raw.replace(",", ""))
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        cur = match.group("cur")
        scale_word = (match.group("scale") or "").lower()
        unit_word = (match.group("unit") or "").lower()
        scale = _SCALE.get(scale_word, 1.0)
        if scale_word in ("m", "b", "t", "k") and not cur and clean[match.end("num"):match.end("num") + 1].isspace():
            scale = 1.0  # a spaced lone letter is not a scale; "$4.9B" and "440.9m" are
        if cur:
            unit = "usd_per_share" if unit_word.startswith("per ") else "usd"
        elif unit_word in ("%", "percent") or unit_word.endswith("percentile"):
            unit = "pct"
        elif unit_word.startswith(("pp", "ppt", "percentage point", "percentage-point", "percent")):
            unit = "pp"
        elif unit_word.startswith("basis") or unit_word in ("bps", "bp"):
            unit, number, decimals = "pp", number / 100.0, decimals + 2
        elif unit_word in ("x", "×", "times"):
            unit = "x"
        elif unit_word == "days":
            unit = "days"
        elif unit_word.startswith("year"):
            unit = "years" if decimals else "count"
        elif unit_word == "shares":
            unit = "shares"
        elif unit_word.startswith("per "):
            unit = "usd_per_share"
        else:
            unit = "plain"
        if unit == "plain":
            if decimals == 0 and scale == 1.0 and 1900 <= number <= 2100:
                continue  # a calendar year
            tail = clean[match.end():match.end() + 25]
            if decimals == 0 and scale == 1.0 and number <= 50 and _COUNT_UNITS.match(tail):
                unit = "count"
            elif decimals == 0 and scale == 1.0 and number < 10:
                unit = "count"  # "two products", "3 segments": small bare counts
        if signed and not range_end:
            number = -number
        qualifier = ""
        prefix = clean[max(0, match.start() - 30):match.start()]
        for name, pattern in _QUALIFIERS:
            if pattern.search(prefix):
                qualifier = name
                break
        lead_space = len(match.group(0)) - len(match.group(0).lstrip())
        text, begin = match.group(0).strip(), match.start() + lead_space
        if range_end:
            text, begin = text[1:], begin + 1  # the hyphen is the range's separator
        claims.append(Claim(text, number, unit, decimals, scale, qualifier, begin))
    _propagate_list_units(clean, claims)
    low = text.lower()
    for word, factor in _MULTIPLE_WORDS.items():
        for found in re.finditer(rf"\b{word}\b", low):
            qualifier = ""
            prefix = low[max(0, found.start() - 30):found.start()]
            for name, pattern in _QUALIFIERS:
                if pattern.search(prefix):
                    qualifier = name
            claims.append(Claim(word, factor, "multiple", 0, 1.0, qualifier or "multiple", found.start()))
    return claims


def _propagate_list_units(clean: str, claims: list[Claim]) -> None:
    """"100 and 90 basis points", "8% and 12%": a bare number listed right before a unit-bearing one
    takes that number's unit and scale ("$4.9 and $14.3 billion" likewise takes the scale, and in
    "$18-19 billion" both ends are dollars in billions)."""
    for i in range(len(claims) - 2, -1, -1):
        first, second = claims[i], claims[i + 1]
        gap = " ".join(clean[first.start + len(first.text):second.start].split())
        if (gap in ("-", "–", "to") and first.unit == "usd" and first.scale == 1.0 and second.unit == "plain"
                and second.scale != 1.0):
            # "$18-19 billion": both ends are dollars at the second end's scale
            claims[i + 1] = Claim(second.text, second.value, "usd", second.decimals, second.scale, second.qualifier, second.start)
            claims[i] = Claim(first.text, first.value, "usd", first.decimals, second.scale, first.qualifier, first.start)
            continue
        if gap not in ("and", "to", ",", "or", "-", "–", "and to") or second.unit in ("plain", "count"):
            continue
        if first.unit in ("plain", "count"):
            value = first.value / 100.0 if second.unit == "pp" and "basis" in second.text.lower() else first.value
            decimals = first.decimals + (2 if value != first.value else 0)
            claims[i] = Claim(first.text, value, second.unit, decimals, second.scale, first.qualifier, first.start)
        elif first.unit == second.unit == "usd" and first.scale == 1.0 and second.scale != 1.0:
            claims[i] = Claim(first.text, first.value, "usd", first.decimals, second.scale, first.qualifier, first.start)


def _periods_of(value: dict[str, Any]) -> tuple[str, ...]:
    """Years a value belongs to: the year its label names (a window high or low), else every year of a
    window period ("FY2016..FY2025": a median or CAGR holds across it), else the years in its period."""
    named = re.search(r"\(FY((?:19|20)\d{2})\)", str(value.get("label", "")))
    if named:
        return (named.group(1),)
    years = re.findall(r"(?:19|20)\d{2}", str(value.get("period", "")))
    if ".." in str(value.get("period", "")) and len(years) == 2 and 0 < int(years[1]) - int(years[0]) <= 30:
        return tuple(str(y) for y in range(int(years[0]), int(years[1]) + 1))
    return tuple(years)


def _value_unit(unit: str) -> str:
    return {"pctile": "pct"}.get(unit, unit)


def _year_span(a: dict[str, Any], b: dict[str, Any]) -> Optional[int]:
    ya, yb = _periods_of(a), _periods_of(b)
    if len(ya) != 1 or len(yb) != 1:
        return None
    span = abs(int(ya[0]) - int(yb[0]))
    return span or None


def _passage_numbers(passage: dict[str, Any]) -> list[Candidate]:
    out = []
    for claim in parse_claims(passage["text"]):
        if claim.unit in ("count",):
            continue
        if claim.unit == "plain" and claim.scale >= 1e3:  # "2,860.1M" in code-written text is an amount
            out.append(Candidate(claim.value * claim.scale, "usd", f"passage {passage['id']}", (passage["id"],), ()))
        if claim.unit == "usd" and claim.scale == 1.0 and abs(claim.value) >= 1:
            # Filings print table-scale dollars in prose ("Net sales increased $27,335", in millions).
            for scale in (1e3, 1e6):
                out.append(Candidate(claim.value * scale, "usd", f"passage {passage['id']} (x{scale:g})", (passage["id"],), ()))
        # No period constraint: a FY2025 10-K quotes 2026 guidance and prior-year comparatives.
        out.append(Candidate(claim.value * claim.scale, claim.unit, f"passage {passage['id']}", (passage["id"],), ()))
    return out


# A gap between two levels of one year (packs-v2's "Net margin minus operating margin (pp, same year)") is a level, not
# a change: like the difference of the two margins it equals, which an arm reading packs/ cites, it carries no
# direction, so "the gap narrowed to 3.4pp" is read by magnitude on either pack, and the backstop ``gap_direction``
# reads which margin the sentence puts above, for both.
_SAME_YEAR_GAP = re.compile(r"\bsame year\b", re.I)


def candidates(ids: Iterable[str], pack: dict[str, Any]) -> list[Candidate]:
    """Every value the cited IDs license: the values, their pairwise derivations, passage figures."""
    values = pack["values"]
    passages = {p["id"]: p for p in pack["passages"]}
    cited = [i for i in dict.fromkeys(ids) if i in values]
    out: list[Candidate] = []
    for vid in cited:
        v = values[vid]
        label = v["label"].lower()
        signed = v["unit"] == "pp" and not _SAME_YEAR_GAP.search(label) or vid.startswith("D") and bool(
            re.search(r"\bgrowth\b|\bchange$|contribution", label))
        out.append(Candidate(v["value"], _value_unit(v["unit"]), "cited", (vid,), _periods_of(v), signed))
    for a_id, b_id in itertools.permutations(cited, 2):
        a, b = values[a_id], values[b_id]
        ua, ub = a["unit"], b["unit"]
        periods = tuple(dict.fromkeys(_periods_of(a) + _periods_of(b)))
        ya, yb = _periods_of(a), _periods_of(b)
        # A change runs from the earlier value to the later one; the reverse order is not a change the
        # sentence could mean, and keeping it would let any direction word pass.
        dated = len(ya) == 1 and len(yb) == 1 and ya != yb
        forward = not dated or ya[0] > yb[0]
        signed = dated
        if ua == ub and b["value"]:
            ratio = a["value"] / b["value"]
            if ua in ("usd", "shares", "usd_per_share", "x", "days") and forward:
                out.append(Candidate((ratio - 1) * 100.0, "pct", f"growth {a_id}/{b_id}", (a_id, b_id), periods, signed))
                out.append(Candidate(ratio, "x", f"ratio {a_id}/{b_id}", (a_id, b_id), periods))
                out.append(Candidate(ratio, "multiple", f"multiple {a_id}/{b_id}", (a_id, b_id), periods))
                out.append(Candidate(ratio * 100.0, "pct", f"share {a_id}/{b_id}", (a_id, b_id), periods))
                span = _year_span(a, b)
                if span and ratio > 0 and forward:
                    out.append(Candidate((ratio ** (1 / span) - 1) * 100.0, "pct", f"CAGR {b_id}->{a_id} over {span}y",
                                         (a_id, b_id), periods, True))
                if ua == "usd" and a["value"] > 0 and b["value"] < 0:
                    out.append(Candidate(a["value"] / -b["value"], "years", f"cover {a_id}/{b_id}", (a_id, b_id), periods))
                if ua == "usd":
                    out.append(Candidate(a["value"] / b["value"], "years", f"cover {a_id}/{b_id}", (a_id, b_id), periods))
            if ua == "pct" and forward:
                # The pack prints percentages to one decimal, so a difference of two printed values may be
                # off by up to 0.1pp from the difference of the raw values.
                out.append(Candidate(a["value"] - b["value"], "pp", f"pp {a_id}-{b_id}", (a_id, b_id), periods, signed, 0.1))
                out.append(Candidate((ratio - 1) * 100.0, "pct", f"relative {a_id}/{b_id}", (a_id, b_id), periods, signed))
            if forward:
                slack = 0.1 if ua in ("pct", "pp") else 0.0
                out.append(Candidate(a["value"] - b["value"], _value_unit(ua), f"difference {a_id}-{b_id}", (a_id, b_id), periods, signed, slack))
        if {ua, ub} == {"usd", "usd"} or (ua == "usd" and ub == "usd"):
            out.append(Candidate(a["value"] + b["value"], "usd", f"sum {a_id}+{b_id}", (a_id, b_id), periods))
    by_unit: dict[str, list[str]] = {}
    for vid in cited:
        by_unit.setdefault(values[vid]["unit"], []).append(vid)
    for unit, group in by_unit.items():
        if 3 <= len(group) <= 12:
            vals = [values[i]["value"] for i in group]
            periods = tuple(dict.fromkeys(p for i in group for p in _periods_of(values[i])))
            out.append(Candidate(sum(vals) / len(vals), _value_unit(unit), "mean of cited", tuple(group), periods))
            if unit == "usd":
                out.append(Candidate(sum(vals), "usd", "sum of cited", tuple(group), periods))
            if unit in ("pct", "x", "usd", "days"):
                out.append(Candidate(max(vals) - min(vals), "pp" if unit == "pct" else _value_unit(unit), "range of cited", tuple(group), periods))
        if len(group) >= 3 and unit in ("usd", "pct"):
            for trio in itertools.combinations(group, 3):
                if unit == "usd":
                    out.append(Candidate(sum(values[i]["value"] for i in trio), "usd", "sum of three", trio,
                                         tuple(dict.fromkeys(p for i in trio for p in _periods_of(values[i])))))
    for pid in ids:
        if pid in passages:
            out.extend(_passage_numbers(passages[pid]))
    flags = {f["id"]: f for f in pack.get("red_flags", [])}
    for fid in ids:
        if fid in flags:  # figures the code wrote into a red-flag candidate's own detail
            out.extend(_passage_numbers({"id": fid, "text": flags[fid]["detail"]}))
    return out


_COMPATIBLE = {
    "usd": {"usd", "usd_per_share"}, "usd_per_share": {"usd_per_share", "usd"}, "pct": {"pct"}, "pp": {"pp"},
    "x": {"x", "multiple"}, "multiple": {"multiple", "x"}, "days": {"days"}, "years": {"years"},
    "shares": {"shares", "plain"}, "plain": {"x", "plain", "pct", "pp", "days", "years", "usd_per_share", "shares", "usd", "multiple"},
}


def _tolerance(claim: Claim) -> float:
    return 0.5 * claim.scale * 10.0 ** (-claim.decimals) + 1e-9


def matches(claim: Claim, cand: Candidate) -> bool:
    if cand.unit not in _COMPATIBLE.get(claim.unit, set()):
        return False
    target = abs(claim.value * claim.scale)
    value = abs(cand.value)
    tol = _tolerance(claim) + cand.slack
    if claim.unit == "plain" and cand.unit == "usd":
        # A bare number next to a dollar figure ("$4.9 billion to 14.3 billion") inherits no scale; try common scales.
        return any(abs(value - target * s) <= tol * s for s in (1e6, 1e9))
    if claim.qualifier == "multiple" or claim.unit == "multiple":
        if claim.qualifier in ("at_least",):
            return value >= claim.value * 0.98
        if claim.qualifier in ("nearly",):
            return claim.value * 0.85 <= value <= claim.value * 1.02
        return abs(value - claim.value) <= claim.value * 0.08
    if claim.qualifier == "approx":
        return abs(value - target) <= max(tol, 0.05 * target)
    if claim.qualifier == "nearly":
        return target * 0.9 - tol <= value <= target + tol
    if claim.qualifier == "at_least":
        return value >= target - tol
    if claim.qualifier == "at_most":
        return value <= target + tol
    return abs(value - target) <= tol


# A figure's own movement noun after it, at most two words on ("a 14.7% operating-income decline", "a 14.7% fall in
# operating income"), after "a" or "an" before it (dev-v5: C's CAT "Rising debt alongside a 14.7% operating-income
# decline", where the rise is debt's).
_NOUN_STOP = r"(?:to|in|of|from|on|for|by|at|after|before|against|despite|with|than|and|or|while|as|alongside|amid)"
_NOUN_UP = r"rises?|gains?|increases?|jumps?|rebounds?|recover(?:y|ies)|expansions?|surges?|climbs?"
_NOUN_DOWN = r"declines?|drops?|falls?|decreases?|slumps?|collapses?|contractions?|plunges?|reductions?|dips?|slides?"
_OWN_NOUN = re.compile(rf"^\s*(?:(?!{_NOUN_STOP}\b)[a-z&-]+\s+){{0,2}}(?:({_NOUN_UP})|({_NOUN_DOWN}))\b", re.I)
_ARTICLE_BEFORE = re.compile(r"\b(?:a|an)\s+(?:further\s+|combined\s+|cumulative\s+)?$", re.I)
# A change placed against the year before right after it ("net margin of 15.4% sat 3.3pp below the prior year": dev-v5,
# C's COP).
_PRIOR_YEAR = r"(?:the\s+)?(?:prior|previous|preceding)\s+year|a\s+year\s+(?:earlier|before|ago)|the\s+year\s+before"
_AGAINST_PRIOR = re.compile(
    rf"^\s*(?:(above|over|higher\s+than|ahead\s+of)|(below|under|lower\s+than|short\s+of))\s+(?:{_PRIOR_YEAR})\b", re.I)


def _direction(text: str, claim: Claim) -> tuple[Optional[int], bool]:
    """(+1 / -1 if a direction word governs the claim, else None; whether every such word is evaluative, so a
    lower-is-better metric reads it inverted): the six words before the number, within its clause (a
    direction word further back usually belongs to another figure). Two readings after the number come first:

    - a position against the year before, right after it ("3.3pp below the prior year", "1.2pp higher than a year
      earlier"), gives the direction whatever the words before say;
    - where a direction word stands before it, the figure's own movement noun after it, after "a" or "an" ("Rising
      debt alongside a 14.7% operating-income decline", "a 14.7% fall in operating income"), overrides that word,
      which belongs to another noun. With no word before, the noun is not read: "a 1.6pp gain" may be a gain in
      a lower-is-better ratio (eval-v1 Haiku CVX's cost-of-revenue share), so its sign is left to the magnitude."""
    end = claim.start + len(claim.text)
    after = CITATION_RE.sub(" ", text[end:end + 80])
    against = _AGAINST_PRIOR.match(after)
    if against:
        return (1 if against.group(1) else -1), False
    found, evaluative = _words_before(text, claim)
    if found is not None and _ARTICLE_BEFORE.search(text[max(0, claim.start - 20):claim.start]):
        noun = _OWN_NOUN.match(after)
        if noun:
            return (1 if noun.group(1) else -1), False
    return found, evaluative


def _words_before(text: str, claim: Claim) -> tuple[Optional[int], bool]:
    """``_direction``'s reading of the words before the number."""
    window = text[max(0, claim.start - 70):claim.start]
    window = re.split(r"[;:,.]\s|\bwhile\b|\bwhereas\b|\bbut\b|\band\b", window)[-1]
    window = re.split(r"\d", window)[-1]  # a word before an earlier figure belongs to that figure
    window = " ".join(window.split()[-6:])
    ups, downs = _UP_WORDS.findall(window), _DOWN_WORDS.findall(window)
    last = max((m.end() for m in (*_UP_WORDS.finditer(window), *_DOWN_WORDS.finditer(window))), default=None)
    if last is not None and _LEVEL_PREPOSITION.search(window[last:]):
        # "growth fell back to 6.8%", "dropping below the 65.5%": the number is a level the metric moved to
        # or past, so its printed sign is the claim.
        return (1 if claim.value >= 0 else -1), False
    evaluative = all(_EVALUATIVE_WORDS.match(w) for w in ups + downs)
    if ups and not downs:
        return 1, evaluative
    if downs and not ups:
        return -1, evaluative
    return None, False


def _said_otherwise(cand: Candidate, said: dict[tuple[str, tuple[str, ...]], Optional[int]], direction: Optional[int],
                    evaluative: bool, values: dict[str, Any]) -> bool:
    """A signed match whose sign the sentence contradicts: for a cited "A minus B" value, the sign its clause gives it
    (``said``; None outside the certain forms, read by magnitude), else the direction word's."""
    sign = said.get((cand.how, cand.ids), direction)
    return sign is not None and _contradicts(cand, sign, evaluative and (cand.how, cand.ids) not in said, values)


# A cost line's effect on operating margin: positive when the line's share of revenue fell. Said through the line's own
# move ("Cost of revenue fell 1.1pp to 45.0% of revenue", "lower SG&A adding 2.0pp"), its sign is the inverse of the
# direction word's (dev-v5: P's SNAP; dev-v3 Sonnet REGN; eval-v1 Haiku-low ORCL).
_EFFECT_LABEL = re.compile(r"^Operating-margin effect of (?P<line>.+?) \(pp\)$")
_LINE_MOVED = (r"(?:rose|risen|rising|rises|grew|increased|climbed|jumped|fell|fallen|falling|falls|declined|decreased|"
               r"dropped|slipped|shrank|eased)")
_LINE_SAID = r"(?:lower|higher|reduced|increased|falling|rising)"


def line_moved(text: str, claim: Claim, cand: Candidate, values: dict[str, Any]) -> bool:
    """Whether the direction word before a cited operating-margin effect is said of its cost line, not of the margin:
    the line is the word's subject ("Cost of revenue fell 1.1pp", "R&D has risen 0.4pp") or the word qualifies it
    ("lower SG&A adding 2.0pp", "higher R&D took 4.7pp"), in the figure's clause. "Operating margin fell 1.1pp on cost
    of revenue" says the margin's move, so the effect's own sign reads it."""
    if cand.how != "cited" or cand.ids[0] not in values:
        return False
    found = _EFFECT_LABEL.match(values[cand.ids[0]]["label"])
    if not found:
        return False
    line = re.escape(found.group("line")).replace(r"\ ", r"[\s-]+")
    window = re.split(r"[;:,.]\s|\bwhile\b|\bwhereas\b|\bbut\b|\band\b", text[max(0, claim.start - 70):claim.start])[-1]
    return bool(re.search(rf"\b{line}\s+(?:has\s+|have\s+)?{_LINE_MOVED}\b", window, re.I)
                or re.search(rf"\b{_LINE_SAID}\s+{line}\b", window, re.I))


def _read(text: str, claim: Claim, cand: Candidate, direction: Optional[int], values: dict[str, Any]) -> Optional[int]:
    """The direction the words before ``claim`` give ``cand``: the inverse where they say its cost line's move."""
    return -direction if direction is not None and line_moved(text, claim, cand, values) else direction


def lower_is_better(cand: Candidate, values: dict[str, Any]) -> bool:
    """Every pack value the candidate was computed from is a metric where lower is better."""
    labels = [values[i]["label"] for i in cand.ids if i in values]
    return bool(labels) and all(_LOWER_IS_BETTER.match(label) for label in labels)


def _contradicts(cand: Candidate, direction: int, evaluative: bool, values: dict[str, Any]) -> bool:
    """A signed match whose sign the direction word contradicts ("improved" for a lower-is-better metric says
    it fell)."""
    if not cand.signed or cand.value == 0:
        return False
    says = -direction if evaluative and lower_is_better(cand, values) else direction
    return (cand.value > 0) != (says > 0)


def sentence_periods(text: str) -> set[str]:
    clean = CITATION_RE.sub(" ", text)
    return set(_YEAR_RE.findall(clean))


_RANGE_RE = re.compile(
    r"(?:FY\s?)?((?:19|20)\d{2})\s*(?:to|through|-|–|—|and)\s*(?:FY\s?)?((?:19|20)\d{2})", re.I)


def year_mentions(text: str) -> list[tuple[int, int, set[str]]]:
    """(start, end, years) for every year or year range named in the text; ranges are inclusive."""
    mentions: list[tuple[int, int, set[str]]] = []
    taken: list[tuple[int, int]] = []
    for match in _RANGE_RE.finditer(text):
        first, last = int(match.group(1)), int(match.group(2))
        if 0 < last - first <= 30:
            mentions.append((match.start(), match.end(), {str(y) for y in range(first, last + 1)}))
            taken.append((match.start(), match.end()))
    for match in _YEAR_RE.finditer(text):
        if any(a <= match.start() < b for a, b in taken):
            continue
        mentions.append((match.start(), match.end(), {match.group(1)}))
    return mentions


_OF_METRIC_IN = re.compile(r"of [a-z][a-z -]* (?:in|for)", re.I)
# A movement word and "from" between a year and the figure after it, with at most two words before it. Any other
# word before "from" ("the FY2026 gain came from 1.2pp", "benefited from") names a source, not a level.
_METRIC_WORDS = r"(?:(?!(?:and|or|but|to|as|then|while)\b)[a-z][a-z&-]* ){0,2}"
# "FY2025 net margin fell from 9.2%": the figure is where that year's move started, the year before's level.
_VERB_FROM = re.compile(
    _METRIC_WORDS + r"(?:fell|rose|declined|dropped|slid|slipped|dipped|climbed|grew|increased|decreased|jumped|"
    r"recovered|rebounded|eased|shrank|expanded|contracted|widened|narrowed|improved|deteriorated|worsened) from", re.I)
# "extend the FY2025 slide from 9.2%" (the slide's start, FY2024's level: DeepSeek CVX), "reverse the FY2025 recovery
# from 34.8%" (the level it would fall away from, FY2025's own: Haiku-low VRTX): after a movement noun both readings
# occur, so the figure may be the year's or the year before's.
_NOUN_FROM = re.compile(
    _METRIC_WORDS + r"(?:slide|decline|drop|fall|rise|gain|recovery|rebound|dip|jump|increase|decrease|climb|slump|"
    r"improvement|deterioration|expansion|contraction|widening|narrowing)s? from", re.I)
# "1.7pp of the FY2023 gain of 6.0pp": a year after "of the" or "in the" names the whole the figure before it is a
# part of, so it binds that figure as well as the one after it.
_PARTITIVE = (["of", "the"], ["in", "the"])
# "5.7pp better than FY2024": a year right after one of these words is a comparison's base, not the period of the
# figure before it (``bind_periods``, its one reader).
BASE_WORDS = ("than", "from", "since", "versus", "vs", "vs.")
# A year followed by one of these words opens another clause, so it binds no figure after it (dev-v5: P's REGN "the
# highest since FY2016 and far above the 20.1% peer median"; dev-v3 Haiku-low REGN "after none in FY2024 and diluted
# shares down 5.6%").
_JOINED = (["and"], ["but"], ["while"], ["whereas"])
# A figure right after a bare "from" is a level the metric moved from (dev-v5: C's NEE "D&A rose to 25.5% of revenue
# from 23.2%" in FY2025); after these words "from" names a source ("the FY2026 gain came from 1.2pp of pricing").
_FROM_BEFORE = re.compile(r"(?:\b([a-z]+)\s+)?\bfrom\s*$", re.I)
_SOURCE_VERBS = frozenset("came come comes coming derived derives stemmed stems resulted results arose arises benefited "
                          "benefitted benefits benefiting".split())
# A year written right after a from-level dates it ("from 23.2% in FY2024").
_YEAR_AFTER = re.compile(r"\s*(?:(?:in|for|at)\s+)?(?:fiscal\s+(?:year\s+)?|FY\s?)?(?:19|20)\d{2}\b", re.I)


def _forward_years(years: set[str], gap_after: str) -> set[str]:
    """The years a year binds to the figure after it: the year before after "<year> <metric> fell from", the year or
    the year before after "<year> <movement noun> from", else the year itself."""
    if len(years) != 1:
        return years
    prior = str(int(next(iter(years))) - 1)
    if _VERB_FROM.fullmatch(gap_after):
        return {prior}
    if _NOUN_FROM.fullmatch(gap_after):
        return years | {prior}
    return years


def bind_periods(text: str, claims: list[Claim], latest_year: Optional[int]) -> dict[int, set[str]]:
    """Which years each claim is tied to (claim index -> years); unbound claims have no constraint.

    A year binds to the figure right before it ("1.83x in FY2017": at most a short connective between,
    no comma), with any figures listed with it ("8.7%, 16.7% and 42.4% in FY2023 to FY2025"), or else to
    the figure right after it ("the FY2021 high of 55.7%"). A year opening the sentence ("In FY2025,")
    is the default for figures no other year binds. Years after the pack's latest year (a "watch"
    item's FY2026) are not periods any value belongs to and bind nothing. A year after "than", "from",
    "since" or "versus" is the base of a comparison, not the period of the figure before it
    ("5.7pp better than FY2024"), and binds only forward. "Of <metric> in" may sit between a figure and
    its year ("$596.3 million of net debt in FY2025"); a list chain ("8.7%, 16.7% and 42.4% in FY2023 to
    FY2025") links figures of one unit only. A year after "the" that names the figure after it ("19.4%
    matched the FY2021 high of 19.6%") binds that figure only; with no figure after it, it still binds back
    ("$14.3 billion was the FY2025 high"). After "of the" or "in the" the year names the whole a figure is part
    of and binds the figures on both sides ("1.7pp of the FY2023 gain of 6.0pp"). A figure after "<year>
    <metric> fell from" is the year before's level; after "<year> <movement noun> from" ("the FY2025 slide from
    9.2%") it is the year's or the year before's (``_forward_years``). A year followed by "and", "but", "while" or
    "whereas" binds nothing forward ("the highest since FY2016 and far above the 20.1% peer median"). A from-level
    right after a bare "from", with no year written after it and bound to one year, may be that year's or the
    year before's ("D&A rose to 25.5% of revenue from 23.2%" in FY2025, "in FY2026 from $9,496 million a year
    earlier"), unless "from" names a source ("came from") or the year's "fell from" already dated it.
    """
    bound: dict[int, set[str]] = {}
    default: set[str] = set()
    moved_from: set[int] = set()  # dated by "<year> <metric> fell from": the year before, nothing else
    spans = [(c.start, c.start + len(c.text)) for c in claims]
    for a, b, years in year_mentions(text):
        if latest_year is not None:
            years = {y for y in years if int(y) <= latest_year}
        if not years:
            continue
        # Claims come back grouped by kind ("doubled" after the figures), so order them by position in the text.
        before = sorted((i for i, (_, e) in enumerate(spans) if e <= a), key=lambda i: spans[i][0])
        after = sorted((i for i, (st, _) in enumerate(spans) if st >= b), key=lambda i: spans[i][0])
        gap_before = " ".join(text[spans[before[-1]][1]:a].split()) if before else None
        gap_after = " ".join(text[b:spans[after[0]][0]].split()) if after else None
        base_year = gap_before is not None and (gap_before.lower().split() or [""])[-1] in BASE_WORDS
        close_before = gap_before is not None and "," not in gap_before and (
            len(gap_before) <= 12 or (len(gap_before) <= 28 and _OF_METRIC_IN.fullmatch(gap_before) is not None))
        close_after = gap_after is not None and len(gap_after) <= 24 and "," not in gap_after and ";" not in gap_after
        partitive = gap_before is not None and gap_before.lower().split()[-2:] in _PARTITIVE
        names_next = close_after and not partitive and gap_before is not None and gap_before.lower().split()[-1:] == ["the"]
        joined = (gap_after or "").lower().split()[:1] in _JOINED  # "since FY2016 and far above the 20.1% ...": not its year
        if close_before and not base_year and not names_next:
            chain = [before[-1]]
            for i in reversed(before[:-1]):
                link = " ".join(text[spans[i][1]:spans[chain[-1]][0]].split())
                if link in (",", "and", ", and", "/", "to", "-", "–") and claims[i].unit == claims[chain[-1]].unit:
                    chain.append(i)
                else:
                    break
            for i in chain:
                bound.setdefault(i, set()).update(years)
            if partitive and close_after and not joined:
                bound.setdefault(after[0], set()).update(_forward_years(years, gap_after or ""))
        elif close_after:
            if not joined:
                bound.setdefault(after[0], set()).update(_forward_years(years, gap_after or ""))
                if _VERB_FROM.fullmatch(gap_after or ""):
                    moved_from.add(after[0])
        elif not before and a <= 12:
            default = years
    if default:
        for i in range(len(claims)):
            bound.setdefault(i, set(default))
    for i, (start, end) in enumerate(spans):
        years = bound.get(i, set())
        source = _FROM_BEFORE.search(text[max(0, start - 40):start])
        if (len(years) == 1 and i not in moved_from and source and (source.group(1) or "").lower() not in _SOURCE_VERBS
                and not _YEAR_AFTER.match(text[end:])):
            bound[i] = years | {str(int(next(iter(years))) - 1)}  # a from-level: the year's or the year before's
    return bound


_CLAUSE_BREAK = re.compile(r"[;:]|,\s+(?:and|but|while|whereas)\b|\bwhile\b|\bwhereas\b|\bbut\b", re.I)
_MINUS_LABEL = re.compile(r"^(?P<a>.+?) minus (?P<b>.+?)(?:\s*\([^)]*\))?$", re.I)


_OF_THE_BEFORE = re.compile(r"^\s*of\s+(?:the\s+)?$", re.I)
_TOTAL_AFTER = re.compile(r"^\s*total\b", re.I)
_REVENUE_GROWTH = re.compile(r"^revenue growth(?:,|$)", re.I)


def clause_span(text: str, claim: Claim) -> tuple[int, int]:
    """Where the clause holding the claim starts and ends: the last clause break before it, the next one after it."""
    head = [m.end() for m in _CLAUSE_BREAK.finditer(text, 0, claim.start)]
    tail = _CLAUSE_BREAK.search(text, claim.start + len(claim.text))
    return head[-1] if head else 0, tail.start() if tail else len(text)


def _clause_of(text: str, claim: Claim) -> str:
    """The clause holding the claim: from the last clause break before it to the next one after it."""
    start, end = clause_span(text, claim)
    return text[start:end]


# Which side of an "A minus B" value a clause puts ahead (``compared_sides``), read only in the forms below and nowhere
# else. The sides go by their key nouns, as a sentence names them in its own words: revenue as sales or the top line, a
# cost as costs, expenses, spending or opex, each with or without "operating"; any other side by its whole phrase ("net
# margin", so "operating income" is not "operating margin").
_SIDE_NOUNS = ((re.compile(r"\brevenue\b", re.I), r"(?:net\s+)?(?:revenues?|sales|top[- ]line)"),
               (re.compile(r"\b(?:costs?|expenses?)\b", re.I), r"(?:operating[- ])?(?:costs?|expenses?|spending|opex)"))
# A move of one side against the other: more ("0.3pp faster than revenue", "1.2pp further than"), or less.
_MORE = r"faster|quicker|further|deeper|steeper|more(?:\s+(?:steeply|sharply|quickly|rapidly|strongly))?"
_LESS = r"slower|more\s+slowly|less(?:\s+(?:steeply|sharply|quickly|rapidly|strongly))?"
# A standing: a position after the figure ("ran 4.4pp ahead of", "came in 10.3pp short of"), or an outpacing before it
# ("outgrew operating costs by 4.4pp", "trailed ... by"); "top" alone is no verb ("top-line growth trailed").
ABOVE, BELOW = r"above|over|higher|ahead\s+of", r"below|under|lower|behind|short\s+of"
_OUTPACE_UP = r"beat(?:s|ing)?|exceed(?:s|ed|ing)?|outpac(?:e|es|ed|ing)|outgr(?:ew|ow|ows|own|owing)|top(?:s|ped|ping)|outr(?:an|un|uns|unning)"
_OUTPACE_DOWN = r"trail(?:s|ed|ing)?|lag(?:s|ged|ging)?|(?:fell|falls?|falling)\s+short\s+of"
_OUTGREW = re.compile(r"^outgr", re.I)  # "outgrew" says grew more: a growth rate, whatever the side is called
_RISE = r"rose|ris(?:e|es|en|ing)|gr(?:ew|ow|ows|own|owing)|increas(?:e|ed|es|ing)|climb(?:s|ed|ing)?|jump(?:s|ed|ing)?|expand(?:s|ed|ing)?|gain(?:s|ed|ing)?"
_FALL = r"fell|fall(?:s|en|ing)?|declin(?:e|ed|es|ing)|decreas(?:e|ed|es|ing)|drop(?:s|ped|ping)?|shr(?:ank|unk|ink|inks|inking)|contract(?:s|ed|ing)?|sl(?:id|ide|ides|iding)|slip(?:s|ped|ping)?|dip(?:s|ped|ping)?"
_RISE_VERB = re.compile(rf"^(?:{_RISE})$", re.I)
# A verb that only places a side ("was", "ran", "came in"): after it "more" or "less" says where the side stands.
_PLACED = (r"was|were|is|are|(?:has|have|had)\s+been|ran|runs?|running|st(?:ood|ands?|anding)|s(?:at|its?|itting)|"
           r"c(?:ame|omes?|oming)(?:\s+in)?|end(?:s|ed)|remain(?:s|ed)|stay(?:s|ed)|land(?:s|ed)|h(?:eld|olds?)|"
           r"finish(?:es|ed)|settl(?:es|ed)")
_PLACED_VERB = re.compile(rf"^(?:{_PLACED})$", re.I)
_FALL_NOUNS = r"declines?|drops?|falls?|reductions?|cuts?|contractions?|shrinkage|decreases?"
# A figure as a sentence prints it, in "net margin of 13.1%" or "the 16.5% operating margin".
_FIGURE = (r"[-−–+]?(?:US)?\$?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|pp\b|percentage\s+points?|percent\b|basis\s+points?|bps\b|"
           r"trillion|billion|million|thousand|bn\b|mn\b|[mbk]\b|x\b))?")
_QUALIFIER = "|".join(words for _, words in _QUALIFIER_WORDS)
# A side after one of these words is an object ("the decline in revenue", "cost of revenue"), not the subject.
_OBJECT_OF = re.compile(r"\b(?:in|of|on|to|from|than|against|versus|vs\.?|for|by|over|under|below|above|behind|at|into|"
                        r"between|across|per|about|toward|towards|within|without)\s+(?:(?:the|its|their)\s+)?$", re.I)
# What may stand between a side and its verb besides "of <figure>" and an adverb, as it only dates or quantifies the
# subject (review 9): the year ("revenue growth in FY2026 outpaced", "net margin in FY2025 was") and the side's own figure
# in brackets ("revenue growth (3.3%) outpaced"). A rise or fall verb may take "has", "have" or "had" ("operating costs
# have grown 1.4pp faster than revenue").
_SUBJECT_YEAR = r"(?:in|for|during)\s+(?:fiscal\s+(?:year\s+)?|FY\s?)?(?:19|20)\d{2}"
_AUX = r"(?:(?:has|have|had)\s+)?"
_ADVERBS = r"also|only|still|just|again"  # one may stand between a side and its verb


class _Forms(NamedTuple):
    """The certain forms for one order of the sides (X named first, Y the other), as regular expressions over the words
    before the figure (anchored at their end) and after it (anchored at their start). ``moved`` is a rise or fall verb
    right before the figure, whoever its subject; ``outpacing`` an outpacing verb before "Y by" the figure, whoever its
    subject (the readings of a gap of two levels, ``_level_standing``)."""
    move: re.Pattern[str]
    move_rest: re.Pattern[str]
    move_before: re.Pattern[str]
    placed: re.Pattern[str]
    placed_rest: re.Pattern[str]
    outpaced: re.Pattern[str]
    moved: re.Pattern[str]
    outpacing: re.Pattern[str]


def _side(side: str) -> tuple[str, bool]:
    """(how a sentence names one side of an "A minus B" label, by ``_SIDE_NOUNS`` or its whole phrase, without
    "growth"; whether the side is a growth rate)."""
    words = side.lower().split()
    growth = len(words) > 1 and words[-1] == "growth"
    words = words[:-1] if growth else words
    nouns = next((body for names, body in _SIDE_NOUNS if names.search(" ".join(words))), None)
    return nouns or r"\s+".join(re.escape(w).replace(r"\-", "[- ]") for w in words), growth


@functools.lru_cache(maxsize=None)
def _forms(x: str, y: str) -> _Forms:
    subject = (rf"\b(?P<x>{x})(?P<xg>\s+growth)?(?:\s+of\s+(?:an?\s+)?{_FIGURE})?(?:\s+{_SUBJECT_YEAR})?"
               rf"(?:\s*\(\s*{_FIGURE}\s*\))?(?:\s+(?:{_ADVERBS}))?")
    other = (rf"(?:(?:the|its|their)\s+)?(?:{_FIGURE}\s+)?(?P<y>{y})(?P<yg>(?:['’]s)?\s+growth)?"
             rf"(?P<yfall>(?:['’]s)?\s+(?:{_FALL_NOUNS}))?(?![\w'’-])")
    comparative = rf"(?:(?P<more>{_MORE})|(?P<less>{_LESS}))\s+than"
    end = rf"(?:\s+(?:{_QUALIFIER}))?\s*$"
    outpace = rf"(?:(?P<up>{_OUTPACE_UP})|(?P<down>{_OUTPACE_DOWN}))\s+{other}\s+by{end}"
    return _Forms(
        move=re.compile(rf"{subject}\s+{_AUX}(?P<v>{_RISE}|{_FALL})(?:\s+by)?{end}", re.I),
        move_rest=re.compile(rf"^\s*{comparative}\s+{other}", re.I),
        move_before=re.compile(rf"{subject}\s+{_AUX}(?P<v>{_RISE}|{_FALL})\s+{comparative}\s+{other}\s+by{end}", re.I),
        # The verb may be missing: "with revenue growth 2.1pp ahead of operating-cost growth" places the side as "was".
        placed=re.compile(rf"{subject}(?:\s+(?P<v>{_PLACED}|{_AUX}(?:{_RISE}|{_FALL})(?:\s+to)?))?{end}", re.I),
        placed_rest=re.compile(rf"^\s*(?:(?P<above>{ABOVE})|(?P<below>{BELOW})|{comparative})(?:\s+than)?\s+{other}", re.I),
        outpaced=re.compile(rf"{subject}(?:\s+(?:has|have|had))?\s+{outpace}", re.I),
        moved=re.compile(rf"\b{_AUX}(?:{_RISE}|{_FALL})(?:\s+by)?{end}", re.I),
        outpacing=re.compile(rf"\b{outpace}", re.I),
    )


def _subject(found: Optional[re.Match[str]], lead: str) -> Optional[re.Match[str]]:
    """``found`` when its side X is the subject, not an object after a preposition (``_OBJECT_OF``)."""
    return None if found is None or _OBJECT_OF.search(lead[:found.start("x")]) else found


def _says(forms: _Forms, lead: str, rest: str, growth: bool, lines_fell: Optional[bool]) -> Optional[int]:
    """+1 when the clause, in one of the certain forms (``compared_sides``), puts X ahead of Y, -1 behind; else None."""
    rate = not growth or lines_fell is False  # a standing of X without "growth" can only be its rate's
    if growth:
        found = _subject(forms.move.search(lead), lead)
        comparative = forms.move_rest.match(rest) if found else None
        if found and comparative and not found["xg"]:
            return _moved(found["v"], comparative)
        found = _subject(forms.move_before.search(lead), lead)
        if found and not found["xg"]:
            return _moved(found["v"], found)
    found = _subject(forms.placed.search(lead), lead)
    where = forms.placed_rest.match(rest) if found else None
    if found and where and not where["yfall"] and (found["xg"] or rate):
        placed = found["v"] is None or bool(_PLACED_VERB.match(found["v"]))
        if where["above"] or where["below"]:
            return (1 if where["above"] else -1) if placed or not growth else None
        return (1 if where["more"] else -1) if placed else None
    found = _subject(forms.outpaced.search(lead), lead)
    if found and not found["yfall"] and (found["xg"] or rate or (found["up"] and _OUTGREW.match(found["up"]))):
        return 1 if found["up"] else -1
    return None


def _named_last(text: str, sides: tuple[str, str]) -> Optional[int]:
    """Which of two sides (0 the first, 1 the second) ``text`` names last, not after a preposition (``_OBJECT_OF``)."""
    found = [(m.start(), i) for i, side in enumerate(sides) for m in re.finditer(rf"\b{side}\b", text, re.I)
             if not _OBJECT_OF.search(text[:m.start()])]
    return max(found)[1] if found else None


def _level_standing(lead: str, rest: str, a: str, b: str) -> Optional[tuple[int, int]]:
    """``compared_sides`` for a gap of two levels of one year (net margin minus operating margin), which is where one
    level stands against the other, whatever either did: a level gap has no both-fell reading, so the side the clause
    names last before the figure, not after a preposition, is the one placed, in any wording (review 9: "held net margin
    at 31.4%, 6.5pp below the 24.9% operating margin", "Net margin was 31.4%, 6.5pp below", "left net margin 6.5pp under
    operating margin", "Net margin in FY2025 was 6.5pp below", the verbless "net margin 5.2pp below operating margin").
    Read: a position ("above", "below", "over", "short of", "higher than") or "more than" / "less than" after the
    figure, then the other side; or an outpacing verb before "<other side> by" the figure, the side named last before
    the verb placed by it. Not read: "more than" or "less than" right after a rise or fall verb, a move of two levels
    and not their gap ("net margin fell 3.4pp more than operating margin"); the other side named as its fall ("3.4pp
    below the operating margin decline"); and the passive ("net margin was exceeded by operating margin by 3.4pp"), whose
    subject is the side outpaced: there "by", not the other side, follows the verb."""
    last = _named_last(lead, (a, b))
    for first, x, y in ((1, a, b), (-1, b, a)):
        forms = _forms(x, y)
        where = forms.placed_rest.match(rest)
        if where and last == (0 if first == 1 else 1) and not where["yfall"]:
            if (where["more"] or where["less"]) and forms.moved.search(lead):
                return None
            return first, (1 if where["above"] or where["more"] else -1)
        verb = forms.outpacing.search(lead)
        if verb and _named_last(lead[:verb.start()], (a, b)) == (0 if first == 1 else 1):
            return first, (1 if verb["up"] else -1)
    return None


def _moved(verb: str, comparative: re.Match[str]) -> Optional[int]:
    """X's move against Y's: its direction (rose +1, fell -1) times more (+1) or less (-1). Y named as its fall ("than
    the revenue decline") is a fall's size, read only after a fall verb."""
    rise = bool(_RISE_VERB.match(verb))
    if comparative["yfall"] and rise:
        return None
    return (1 if rise else -1) * (1 if comparative["more"] else -1)


def both_fell(value: dict[str, Any], values: dict[str, Any]) -> Optional[bool]:
    """Whether both lines of a gap of two growth rates fell in its year, by the pack's own record: the revenue its first
    two inputs name (the year's and the year before's, as ``derived`` records "revenue growth minus operating-cost
    growth") gives revenue growth, and revenue growth less the gap is cost growth. None when they are not two revenues."""
    found = [values.get(i) for i in (value.get("inputs") or [])[:2] if i]
    if len(found) != 2 or not all(f and f["label"] == "Revenue" and f["value"] for f in found):
        return None
    growth = (found[0]["value"] / found[1]["value"] - 1.0) * 100.0
    return growth < 0 and growth - value["value"] < 0


def compared_sides(text: str, claim: Claim, side_a: str, side_b: str,
                   lines_fell: Optional[bool] = None) -> Optional[tuple[int, int]]:
    """How the claim's clause compares the two sides of an "A minus B" value, in the certain forms only: (1 when the
    side it names first is A, -1 when B; +1 when that side is ahead of the other by the figure, -1 behind). None in
    every other form, where the value is read by its magnitude alone, with no direction verdict.

    The certain forms of a gap of two growth rates (revenue growth minus operating-cost growth). The side named first,
    X, is the subject: named by its nouns (``_SIDE_NOUNS``) right before its verb, with at most "of <figure>" ("revenue
    growth of 3.3%"), its year ("in FY2026"), its figure in brackets ("(3.3%)") and one adverb ("also", "only",
    "still", "just", "again") between, and not after a preposition ("the decline in revenue", "cost of revenue":
    ``_OBJECT_OF``). So nothing else stands between them: no comma, appositive or other figure, no passive ("was
    outpaced by"), no fall noun ("the revenue decline", "revenue's decline"). The other side, Y, follows the
    comparative in the same clause, at most after "the", "its", "their" and a figure.

    - a move: X, without "growth", is the subject of a rise or fall verb (after "has", "have" or "had" or none) right
      before the figure ("by" and a qualifier aside), and "faster", "more", "further", "deeper", "steeper" or their
      opposites ("slower", "less", "more slowly") and "than Y" follow the figure ("costs fell 1.2pp less than revenue":
      costs minus revenue is +1.2), or stand before "than Y by" it ("costs grew faster than revenue by 0.3pp"). The
      sign is the verb's (rose +1, fell -1) times the comparative's (more +1, less -1). Y may be named as its fall after
      a fall verb ("fell 1.2pp less than the revenue decline");
    - a standing: placed by a verb that only places ("was", "ran", "came in": ``_PLACED``), or by none ("with revenue
      growth 2.1pp ahead of operating-cost growth"), right before the figure, with a position ("ahead of", "behind",
      "above", "over", "below", "short of", "higher than") or "more than" / "less than" after it ("revenue growth ran
      4.4pp behind operating-cost growth"); or the subject of an active outpacing verb before "Y by" the figure
      ("revenue growth beat operating-cost growth by 4.4pp", "trailed", "lagged", "fell short of"). X is named with
      "growth", a rate, whose place holds when both lines fell; or without it in a year the pack shows the two lines
      did not both fall (``lines_fell`` False, by ``both_fell``), where its place can only be its rate's ("revenue
      trailed operating costs by 4.4pp", REGN). "Outgrew" says grew more, so X may go without "growth" there in any
      year ("costs outgrew sales by 2.1pp").

    A gap of two levels of one year (net margin minus operating margin) is where one level stands against the other,
    which no both-fell reading touches: it is read in the wider forms of ``_level_standing`` (the side named last before
    the position or the outpacing verb, in any wording, the passive and a move of two levels aside).

    Everything else is read by magnitude: an appositive after a comma ("revenue fell 4.6%, 1.2pp more than operating
    costs"), a participle whose subject is another clause's ("..., outpacing the cost decline by 0.4pp"), the passive
    ("revenue growth was outpaced by cost growth by 0.3pp"), a side named as its fall ("the revenue decline outran cost
    reduction by 1.2pp"), a standing of two lines named without "growth" in a year both fell, or one the pack does not
    tell ("revenue trailed costs by 1.2pp", CVX, which may compare the size of two falls), a move of a growth rate
    ("revenue growth fell 1.2pp more than", which may be the change in each rate), one side unnamed ("costs grew 0.3pp
    faster"), and a side another metric names ("operating income grew 0.3pp slower than revenue"). The semantic audit
    sees each such value with its sign (``semantics._describe``)."""
    start, end = clause_span(text, claim)
    lead, rest = text[start:claim.start], text[claim.start + len(claim.text):end]
    (a, a_growth), (b, b_growth) = _side(side_a), _side(side_b)
    if not (a_growth or b_growth):
        return _level_standing(lead, rest, a, b)
    for first, x, y in ((1, a, b), (-1, b, a)):
        said = _says(_forms(x, y), lead, rest, a_growth and b_growth, lines_fell)
        if said is not None:
            return first, said
    return None


def _of_the_total(clean: str, claims: list[Claim], claim: Claim) -> bool:
    """"60.2pp of the 65.5pp total": a contribution's total written in pp is the growth it is a part of."""
    earlier = [c for c in claims if c.start + len(c.text) <= claim.start and c.unit == "pp"]
    if claim.unit != "pp" or not earlier:
        return False
    previous = max(earlier, key=lambda c: c.start)
    return bool(_OF_THE_BEFORE.match(clean[previous.start + len(previous.text):claim.start])
                and _TOTAL_AFTER.match(clean[claim.start + len(claim.text):]))


@dataclass
class Resolution:
    """How the gate read one claim: its status, the candidate that settled it, and every candidate that matched
    it in the period(s) the sentence names (the backstop probes read these)."""
    claim: Claim
    status: str
    best: Optional[Candidate] = None
    in_period: list[Candidate] = field(default_factory=list)
    direction: Optional[int] = None


def check_sentence(sentence: dict[str, Any], pack: dict[str, Any]) -> SentenceResult:
    return analyse_sentence(sentence, pack)[0]


def analyse_sentence(sentence: dict[str, Any], pack: dict[str, Any]) -> tuple[SentenceResult, list[Resolution]]:
    text = sentence["text"]
    kind = sentence.get("type", "fact")
    citations = [i for group in CITATION_RE.findall(text) for i in ID_RE.findall(group)]
    result = SentenceResult(sentence.get("section", ""), text, kind, citations)
    resolved: list[Resolution] = []
    values = pack["values"]
    known = set(pack["values"]) | {p["id"] for p in pack["passages"]} | {f["id"] for f in pack.get("red_flags", [])}
    unknown = [c for c in citations if c not in known]
    if unknown:
        result.failures.append(f"unknown citation(s): {', '.join(unknown)}")
    flag_ids = {f["id"]: f for f in pack.get("red_flags", [])}
    expanded = list(citations)
    for cid in citations:
        if cid in flag_ids:  # a red-flag citation licenses its own evidence
            expanded.extend(flag_ids[cid]["evidence"])
    cands = candidates(expanded, pack)
    latest_year = max((int(y) for v in pack["values"].values() for y in _periods_of(v)), default=None)
    claims = parse_claims(text)
    clean_text = CITATION_RE.sub(lambda m: " " * len(m.group(0)), text)
    numeric = [c for c in claims if c.unit != "count"]
    passage_ids = {p["id"] for p in pack["passages"]}
    if kind == "cause" and not any(c in passage_ids for c in citations):
        result.failures.append("cause sentence cites no filing passage")
    if numeric and not expanded:
        result.failures.append("number(s) with no citation: " + ", ".join(c.text for c in numeric))
    bindings = bind_periods(clean_text, claims, latest_year)
    label_numbers = {n for cid in expanded if cid in pack["values"]
                     for n in re.findall(r"\d+(?:\.\d+)?", pack["values"][cid]["label"])}
    for index, claim in enumerate(claims):
        record: dict[str, Any] = {"claim": claim.text, "value": claim.value, "unit": claim.unit, "qualifier": claim.qualifier}
        if claim.unit in ("plain", "count") and claim.text in label_numbers:
            record["status"] = "name"  # a number in a cited value's own name ("Lower 48")
            result.claims.append(record)
            resolved.append(Resolution(claim, "name"))
            continue
        if claim.unit == "count":
            record["status"] = "unverified_count"
            result.claims.append(record)
            resolved.append(Resolution(claim, "unverified_count"))
            continue
        hits = [c for c in cands if matches(claim, c)]
        if not hits and _of_the_total(clean_text, claims, claim):
            as_pct = Claim(claim.text, claim.value, "pct", claim.decimals, claim.scale, claim.qualifier, claim.start)
            hits = [c for c in cands if c.how == "cited" and _REVENUE_GROWTH.match(values[c.ids[0]]["label"])
                    and matches(as_pct, c)]
        direction, evaluative = _direction(text, claim)
        # A cited "A minus B" value is read as the side the clause names first minus the other, against the sign the
        # clause gives it, in the certain forms only (``compared_sides``); in any other form by magnitude, with no
        # direction verdict (None): a direction word beside it is one side's move, not the gap's sign.
        said: dict[tuple[str, tuple[str, ...]], Optional[int]] = {}
        for i, c in enumerate(hits):
            sides = _MINUS_LABEL.match(values[c.ids[0]]["label"]) if c.how == "cited" else None
            if not sides:
                continue
            reading = compared_sides(clean_text, claim, sides.group("a"), sides.group("b"), both_fell(values[c.ids[0]], values))
            if reading and reading[0] < 0:
                hits[i] = c = replace(c, value=-c.value, how=f"reversed {c.ids[0]}")
            said[(c.how, c.ids)] = reading[1] if reading else None
        mentioned = bindings.get(index, set())
        if mentioned:
            in_period = [c for c in hits if not c.periods or set(c.periods) & mentioned]
        else:
            in_period = hits
        if not hits:
            record["status"] = "no_match"
            result.failures.append(f"'{claim.text}' matches nothing the sentence cites")
            resolved.append(Resolution(claim, "no_match"))
        elif not in_period:
            record["status"] = "period_mismatch"
            record["matched"] = hits[0].how
            result.failures.append(f"'{claim.text}' matches {hits[0].how} but not in the period(s) named ({', '.join(sorted(mentioned))})")
            resolved.append(Resolution(claim, "period_mismatch", hits[0]))
        else:
            ranked = sorted(in_period, key=lambda c: (c.how != "cited", len(c.ids)))
            # Any match whose sign agrees with the sentence settles it; only if every signed match contradicts it is
            # the claim a direction error. But where the clause compares the two sides of a cited "A minus B" value in
            # a certain form, the figure is that value: the unsigned difference of the two growths cited beside it
            # (the same quantity, "pp D373-D358") cannot settle a sign the clause gives the other way (review 9: the
            # candidate prompt's comparison with both growths added).
            certain = [c for c in ranked if said.get((c.how, c.ids)) is not None]
            best = next((c for c in certain or ranked
                         if not _said_otherwise(c, said, _read(text, claim, c, direction, values), evaluative, values)),
                        (certain or ranked)[0])
            if _said_otherwise(best, said, _read(text, claim, best, direction, values), evaluative, values) and claim.value >= 0:
                record["status"] = "direction_mismatch"
                record["matched"] = best.how
                result.failures.append(f"'{claim.text}' matches {best.how} = {best.value:.4g} but the sentence says it went the other way")
            else:
                record["status"] = "verified"
                record["matched"] = best.how
                record["ids"] = list(best.ids)
            resolved.append(Resolution(claim, record["status"], best, in_period, direction))
        result.claims.append(record)
    return result, resolved


def check(sentences: list[dict[str, Any]], pack: dict[str, Any], *, backstops: bool = False) -> dict[str, Any]:
    """The gate over a whole analysis. ``backstops=True`` also fails every hit of the backstop probes' gate kinds
    (``probes.GATE_KINDS``: a verified number said about another ratio, basis, year or sign, or a figure the pack's
    own record names broken, undisclosed in its sentence: a total debt, net cash or cash and investments of a year
    inside a debt or liquidity break its data checks name, or an ID it withholds for one of those or for a peer's
    broken year; ``probes.broken_debt``, so never on a version-1 pack); their logic measures never fail a run."""
    analysed = [analyse_sentence(s, pack) for s in sentences]
    results = [result for result, _ in analysed]
    backstop_failures = 0
    if backstops:
        from evals.trend_depth import probes  # probes reads this module's resolutions, so it imports it

        keys = probes.series_by_id(pack)
        breaks = probes.debt_breaks(pack)
        for sentence, (result, resolved) in zip(sentences, analysed):
            hits = probes.probe_sentence(sentence, pack, resolved, keys) + probes.broken_debt_sentence(
                sentence, pack, resolved, breaks, keys)
            for hit in hits:
                if hit["kind"] in probes.GATE_KINDS:
                    result.failures.append(f"backstop {hit['kind']}: '{hit['claim']}' {hit['detail']}")
                    backstop_failures += 1
    claims = [c for r in results for c in r.claims]
    failures = [{"section": r.section, "sentence": r.text, "type": r.type, "failure": f} for r in results for f in r.failures]
    verified = sum(1 for c in claims if c["status"] == "verified")
    by_type: dict[str, int] = {}
    for r in results:
        by_type[r.type] = by_type.get(r.type, 0) + 1
    out = {
        "passed": not failures,
        "sentences": len(results),
        "sentence_types": by_type,
        "claims": len(claims),
        "verified": verified,
        "unverified_counts": sum(1 for c in claims if c["status"] == "unverified_count"),
        "names": sum(1 for c in claims if c["status"] == "name"),
        "failed_claims": sum(1 for c in claims if c["status"] not in ("verified", "unverified_count", "name")),
        "failures": failures,
        "detail": [r.__dict__ for r in results],
    }
    if backstops:
        out["backstop_failures"] = backstop_failures
    return out


def sentences_from_markdown(markdown: str) -> list[dict[str, Any]]:
    """Gold-example format: ``## Section`` headings; each sentence ends with ``{type}`` after its citations."""
    out = []
    section = ""
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            continue
        if not stripped or stripped.startswith(">"):
            continue
        stripped = re.sub(r"^[-*]\s+|^\d+\.\s+", "", stripped)
        for part in re.split(r"(?<=\})\s+", stripped):
            part = part.strip()
            if not part:
                continue
            tag = TYPE_TAG_RE.search(part)
            kind = tag.group(1) if tag else "untyped"
            text = TYPE_TAG_RE.sub("", part).strip()
            out.append({"section": section, "text": text, "type": kind})
    return out


def is_finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)
