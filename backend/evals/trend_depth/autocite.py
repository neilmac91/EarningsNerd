"""Code fixes the version-2 repair loop makes to a first pass before the gate decides on a repair
(DEEPSEEK-ERRORS.md fixes 1 and 5), and the substitution test that bounds what fix 1 could license.

    cd backend && python -m evals.trend_depth.autocite                         # the substitution test, then the real failures
    cd backend && python -m evals.trend_depth.autocite --labels eval-v1 --real dev-v4

**Fix 1, auto-citation** (``autocite``). DeepSeek often states a correct figure without its own ID: it cites only
a value derived from it, or relies on an earlier sentence. For each claim the gate reads as matching nothing its
sentence cites, one ID is looked for among the values cited elsewhere in the same analysis and the inputs of a
derived value the sentence cites (of that value's own period). An ID is appended only when it is the one candidate
that both

- *reconciles*: the figure is the ID's own value at the figure's printed precision, with no qualifier's latitude
  and no difference, sum or ratio with another value (``_exact``), and the gate, with the ID appended, verifies the
  claim as that value (``_verifies_as``);
- *fits* (``_fits``):
  - the claim is of one year and the ID's period holds it: the years bound to the claim, else those the sentence
    names when it binds none of them to another figure, else those of the single-year values it cites;
  - every word of the ID's label (``metric_words``: a "% of" label's denominator and a window or peer reference
    included) stands in the run of words right before the figure, in the figure itself ("83rd percentile") or in
    the run right after it. The run before is figure talk ("was", "fell", "the") and the label's own words, and
    reaches back over a figure the claim moved from or to ("fell 3.9pp to 71.1%"); the run after is the label's
    words, "of" and articles ("the 52.4% efficiency ratio", "2.1% of revenue"). Each stops at any other word, a
    figure, a clause break, a comma, bracket or citation, and a word that opens another phrase ("and", "with",
    "against", "on") unless it joins two of the label's words ("cash and investments");
  - no word but "of" or an article stands between the label's words and the word that stopped the run before ("Data
    Center revenue" and "cost of revenue" are no total revenue, "its revenue" no company's), and neither run holds a
    reference word the label lacks ("the 0.99x median" is no company's level);
  - a figure after a movement word ("SG&A fell 30.3%") or before one ("the 45.0% cost-of-revenue rise") takes only a
    change;
  - a sentence citing a segment, product or geography line takes no company-wide value ("NEER's results, to $6.83
    billion of net income");
  - no value the sentence cites sits as near the claim (another year of a cited series sits exactly as near: a
    wrong year is as likely as an omitted ID).

The addition is then checked on its sentence: the gate with its backstops runs before and after it, and the ID
stays only if the claims it was found for are the only ones whose verdict changed (``_only_targets_changed``).
Passages and red flags are never candidates, and no figure is read as one side of a difference: the substitution
test's omission arm found the difference licensing capital expenditure printed as free cash flow (operating cash
flow less free cash flow) and a peer gap printed as the margin, and a red flag licensing its threshold as the
metric's level ("the current ratio was 1.0x"). A sentence that cites nothing is left alone (its figures are
thresholds or forecasts more often than omissions). Every addition is recorded; ``rejected`` counts the claims for
which some ID reconciled but none was appended. The output still carries every figure's own ID, so the grounding
rule does not change.

**Fix 5, retyping** (``retype``). A ``cause`` sentence that cites no passage, opens no explanatory clause
("because", "so", "as", "due to": ``explanatory``) and says nothing beyond its figures (every word is a figure,
a year, a word of a cited value's label or of a cited flag's detail, or figure talk such as "offset",
"consumed", "flat") is a margin bridge or a capital-return sentence mistyped. It becomes a ``comparison``.

**Substitution test** (``substitution_test``). Every verified claim matched to one cited value, in every recorded
output, has that value replaced by: the same series' value in the neighbouring years (``year``); values of other
series in the same unit and period (``metric``: first those cited elsewhere in the analysis, the ones
auto-citation draws from, then a sample of the rest of the pack); a figure of a red flag whose evidence holds the
value (``threshold``); and the gap between it and another value of its unit and year that the sentence cites
(``gap``). Each substitute is tried in two arms: ``kept``, with the claim's own ID still cited, and ``omitted``,
with that ID removed while the sentence still cites another (the omission fix 1 is for). The ``omitted`` arm also
counts how often the right value gets its own ID back (``control``). A substitute the gate reads as matching
nothing is one auto-citation gets to judge; it *leaks* when auto-citation appends an ID for it.

Pure: imports neither the bootstrap nor ``generate``; the command reads records and packs from disk.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.factcheck import CITATION_RE, ID_RE, Claim
from evals.trend_depth.providers import packs_dir

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
SKIP = ("judge", "causes", "semantics")  # audit and verdict folders beside the systems

_TOKEN = re.compile(r"[a-z0-9&]*[a-z][a-z0-9&]*")
_PARENS = re.compile(r"\([^)]*\)")
_LABEL_STOP = frozenset({"of", "and", "the", "a", "an", "in", "on", "to", "vs", "per", "plus", "less", "minus", "window",
                         "as", "at", "for", "by", "it", "from", "that"})
_REFERENCE = (("percentile", ("percentile",)), ("peer median", ("peer", "median")))
_REFERENCE_WORDS = frozenset({"median", "high", "low", "average", "typical", "peak", "trough", "percentile"})
_POSSESSIVE = frozenset({"its", "their"})  # "its revenue" names another entity's metric: it ends a run, as a modifier
_MOVE_GAP = re.compile(r"\s*,?\s*(?:to|from)\s*", re.I)  # "fell 3.9pp to 71.1%": the run reaches back over 3.9pp
_CHANGE_LABEL = re.compile(r"\b(?:growth|change|cagr|contribution|effect)\b|\bminus\b", re.I)
_MOVED = re.compile(
    r"\b(?:rose|risen|rises|rising|grew|grown|grows|growing|fell|fallen|falls|falling|declined|declines|declining|"
    r"decreased|increased|dropped|slipped|jumped|climbed|gained|lost|shrank|shrunk|widened|narrowed|expanded|contracted|"
    r"improved|worsened|surged|plunged|slid|sank|up|down)\s+(?:by\s+)?"
    r"(?:only\s+|just\s+|about\s+|roughly\s+|nearly\s+|almost\s+|some\s+|a further\s+|another\s+)?$", re.I)

# "because", "so", "as", "due to": the clause after one explains, and needs the passage that states the cause.
_CONNECTIVE = re.compile(r"\b(because|due to|so|as)\b", re.I)
_AS_NOT_CAUSAL_AFTER = re.compile(
    r"^\s*(?:a (?:share|percent(?:age)?|proportion|multiple) of\b|reported\b|of\b|well as\b|"
    r"(?:much|many|high|low|large|long|far|little|soon) as\b)", re.I)
_AS_NOT_CAUSAL_BEFORE = re.compile(r"\b(?:such|same|as (?:much|many|high|low|large|long|far|little|well|soon))\s*$", re.I)
_SO_NOT_CAUSAL_AFTER = re.compile(r"^\s*(?:far|much|many)\b", re.I)

# Words a sentence about figures uses without explaining them: directions, bridges, capital returns, references,
# scale and function words. A word outside this list and outside the cited labels is a claim beyond the figures.
_FIGURE_TALK = frozenset("""
a an the of and or in on at as to from by for with than that this these its it their which while whereas but then
also still only just about roughly nearly almost around over under above below against versus vs between per
each both all after before into through across within same not no was were is are be been has had have
rose rise risen rising grew grow growing growth fell fall fallen falling declined decline declining increased
increase increasing decreased decrease decreasing dropped drop slipped slip edged gained gain lost loss added add
adding took take taking contributed contribute contribution contributing offset partly partially came come
accounted account drove drive driving dragged drag consumed consume absorbed absorb returned return used use
spent paid widened widen narrowed narrow expanded expand contracted contract improved improve worsened worsen
held hold stayed stay remained remain flat unchanged steady stable essentially broadly largely mostly slightly
sharply modestly change changed level share count combined together high low higher lower median peak trough
percentile peer window year fiscal fy pp point percent percentage billion million thousand x time margin effect
line total beat exceeded trailed outpaced outran matched lagged topped
""".split())


def _norm(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _words(text: str) -> set[str]:
    return {_norm(w) for w in _TOKEN.findall(text.lower())}


def _label_stop() -> set[str]:
    """``_LABEL_STOP`` as ``_words`` spells its words ("plus" is "plu")."""
    return {_norm(w) for w in _LABEL_STOP}


def _blank_citations(text: str) -> str:
    return CITATION_RE.sub(lambda m: " " * len(m.group(0)), text)


def _spans(text: str, claims: list[Claim]) -> list[tuple[int, int, str]]:
    """(start, end, word) for every word of ``text`` that is no citation, year or figure, in order."""
    clean = factcheck._clean_for_numbers(text)
    for claim in claims:
        clean = clean[:claim.start] + " " * len(claim.text) + clean[claim.start + len(claim.text):]
    return [(m.start(), m.end(), _norm(m.group())) for m in _TOKEN.finditer(clean.lower())]


def _word_offsets(text: str, claims: list[Claim]) -> list[tuple[int, str]]:
    """(offset, word) for every word of ``text`` that is no citation, year or figure, in order."""
    return [(start, word) for start, _, word in _spans(text, claims)]


def citations(text: str) -> list[str]:
    return [i for group in CITATION_RE.findall(text) for i in ID_RE.findall(group)]


def _flags(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in pack.get("red_flags", [])}


def _expanded(ids: list[str], pack: dict[str, Any]) -> list[str]:
    """The sentence's citations and the evidence of the red flags among them: what the gate licenses."""
    flags = _flags(pack)
    return list(dict.fromkeys([*ids, *(e for i in ids if i in flags for e in flags[i]["evidence"])]))


def metric_words(vid: str, pack: dict[str, Any]) -> frozenset[str]:
    """The words a figure's phrase must hold to be ``vid``'s own value: every word of its label, the denominator of a
    "% of" label included ("Stock-based compensation % of operating cash flow"), with "percentile" or "peer median"
    for a peer reference and "median", "high" or "low" for a window one; parentheses, "window" and function words
    aside. Empty for an ID that is no value."""
    value = pack["values"].get(vid)
    if value is None:
        return frozenset()
    base, _, reference = _PARENS.sub(" ", value["label"]).partition(":")
    words = _words(base) - _label_stop()
    for marker, needed in _REFERENCE:
        if marker in reference.lower():
            return frozenset(words | set(needed))
    return frozenset(words | (_words(reference) - _label_stop()))


_LATEST: dict[int, tuple[dict[str, Any], Optional[int]]] = {}


def _latest_year(pack: dict[str, Any]) -> Optional[int]:
    """The pack's latest year, worked out once per pack object."""
    held = _LATEST.get(id(pack))
    if held is None or held[0] is not pack:
        held = _LATEST[id(pack)] = (pack, max((int(y) for v in pack["values"].values() for y in factcheck._periods_of(v)),
                                              default=None))
    return held[1]


def with_citation(text: str, vid: str) -> str:
    """``text`` with ``[vid]`` after its closing citations, before the final punctuation."""
    end = len(text.rstrip())
    while end and text[end - 1] in ".;:!?":
        end -= 1
    joined = text[:end].endswith("]") and any(m.end() == end for m in CITATION_RE.finditer(text))
    return text[:end] + ("" if joined else " ") + f"[{vid}]" + text[end:]


def _pool(ids: list[str], expanded: list[str], elsewhere: Iterable[str], pack: dict[str, Any]) -> list[str]:
    """The IDs auto-citation may add (module docstring), in a fixed order, none the sentence already licenses: the
    values cited elsewhere in the analysis, and the inputs of a derived value the sentence cites, of its period."""
    values = pack["values"]
    pool = [i for i in elsewhere if i in values]
    for cid in expanded:
        derived = values.get(cid) or {}
        own = factcheck._periods_of(derived) if derived else ()
        pool += [i for i in derived.get("inputs", []) if i in values and factcheck._periods_of(values[i]) == own]
    return [i for i in dict.fromkeys(pool) if i not in expanded and i not in ids]


def _is_change(vid: str, pack: dict[str, Any]) -> bool:
    return bool(_CHANGE_LABEL.search(pack["values"][vid]["label"])) if vid in pack["values"] else False


def _exact(claim: Claim, value: dict[str, Any]) -> bool:
    """The figure is ``value`` at its printed precision: the same unit, within half a unit of its last printed digit,
    by magnitude (the gate's own comparison, without a qualifier's latitude: "above 2.27x" is no 2.41x)."""
    if claim.unit in ("plain", "count", "multiple") or claim.unit != factcheck._value_unit(value["unit"]):
        return False
    return abs(abs(value["value"]) - abs(claim.value * claim.scale)) <= factcheck._tolerance(claim)


def _verifies_as(sentence: dict[str, Any], index: int, vid: str, pack: dict[str, Any]) -> bool:
    """With ``[vid]`` appended, the gate verifies the claim as ``vid``'s own value, not through anything ``vid`` forms
    with another cited value."""
    resolved = factcheck.analyse_sentence({**sentence, "text": with_citation(sentence["text"], vid)}, pack)[1][index]
    best = resolved.best
    return resolved.status == "verified" and best is not None and best.how == "cited" and best.ids == (vid,)


# What may stand between a label's words and the figure before them ("2.1% of revenue"), and what ends a phrase: a run
# stops at one of these words unless it stands between two of the label's own ("cash and investments").
_LINKS = frozenset({"of", "the", "a", "an"})
_BREAK_WORDS = frozenset(_norm(w) for w in (
    "and or but while whereas as so because then with against versus vs than on after despite behind plus minus less "
    "which where when").split())
_MOVEMENT_NOUNS = frozenset(_norm(w) for w in (  # "the 45.0% cost-of-revenue rise" states a change
    "rise increase decrease decline drop fall gain jump growth change slide cut swing shift contraction expansion "
    "improvement deterioration").split())
_PUNCTUATION = re.compile(r"[,;:()\[\]—–]")  # a comma, a bracket or a citation between two words ends a phrase
_SEGMENT_LINE = re.compile(r"\((?:segment|product|geography|other)\b", re.I)


def _segment_line(vid: str, pack: dict[str, Any]) -> bool:
    """A segment, product or geography line, or a value derived from one."""
    return vid.startswith("S") or bool(_SEGMENT_LINE.search(pack["values"].get(vid, {}).get("label", "")))


@dataclass
class _Place:
    """Where a claim sits in its clause (the gate's ``_CLAUSE_BREAK``s bound it): the clause's words with their
    offsets; the words between the claim and the figure or clause head before it (``before``: over a figure it moved
    from or to, "fell 3.9pp to 71.1%"), each with whether a comma, bracket or citation follows it; the words between it
    and the next figure or the clause's end (``after``), each with whether one precedes it; the words of the figure
    itself (``own``: "83rd percentile"); the one year it may be of; and whether a movement word stands right before it
    ("grew 45.0%")."""
    positions: list[tuple[int, str]]
    start: int
    before: list[tuple[str, bool]]
    after: list[tuple[str, bool]]
    own: set[str]
    year: Optional[str]
    moved: bool

    def runs(self, words: frozenset[str]) -> tuple[list[str], list[str], Optional[str], Optional[str]]:
        """The run right before the claim (in text order: ``words`` and figure talk), the run right after it
        (``words``, "of" and articles), the word that ended each (None at a figure, a phrase's end or a break word).
        A run ends at a comma, bracket or citation, and at a break word that does not join two of ``words``."""
        def joins(word: str, outer: Optional[str], inner: Optional[str]) -> bool:
            return word in _BREAK_WORDS and outer in words and inner in words

        taken: list[str] = []
        stop = None
        for i in range(len(self.before) - 1, -1, -1):
            word, cut = self.before[i]
            if cut or (word in _BREAK_WORDS and not joins(word, self.before[i - 1][0] if i else None,
                                                           taken[-1] if taken else None)):
                break
            if word in words or word in _BREAK_WORDS or (word in _FIGURE_TALK and word not in _POSSESSIVE):
                taken.append(word)
                continue
            stop = word
            break
        ahead: list[str] = []
        after_stop = None
        for i, (word, cut) in enumerate(self.after):
            if cut:
                break
            if word in words or word in _LINKS or joins(word, ahead[-1] if ahead else None,
                                                        self.after[i + 1][0] if i + 1 < len(self.after) else None):
                ahead.append(word)
                continue
            after_stop = None if word in _BREAK_WORDS else word
            break
        return taken[::-1], ahead, stop, after_stop

    def attached(self, words: frozenset[str]) -> bool:
        """Every word stands in the run right before the claim, the figure itself or the run right after it."""
        before, after, _, _ = self.runs(words)
        return words <= set(before) | set(after) | self.own

    def modified(self, words: frozenset[str]) -> bool:
        """The word that ended the run before stands right before the label's words, or before "of" and them: the
        phrase names a narrower metric ("Data Center revenue", "cost of revenue") or another entity's ("its
        revenue")."""
        before, _, stop, _ = self.runs(words)
        first = next((i for i, word in enumerate(before) if word in words), None)
        return stop is not None and first is not None and all(word in _LINKS for word in before[:first])

    def references(self, words: frozenset[str]) -> set[str]:
        """The reference words ("median", "percentile") in either run or the figure itself that ``words`` lacks."""
        before, after, _, _ = self.runs(words)
        return (set(before) | set(after) | self.own) & _REFERENCE_WORDS - words

    def changed(self, words: frozenset[str]) -> bool:
        """A movement word follows the figure's phrase ("the 45.0% cost-of-revenue rise"): the figure is a change."""
        return self.runs(words)[3] in _MOVEMENT_NOUNS

    def distance(self, words: frozenset[str]) -> Optional[int]:
        """How many words from the claim the farthest of ``words`` sits, each where it is nearest; None when one
        is missing from the clause."""
        before = sum(1 for at, _ in self.positions if at < self.start)
        farthest = 0
        for word in words:
            found = [i for i, (_, token) in enumerate(self.positions) if token == word]
            if not found:
                return None
            farthest = max(farthest, min(before - i if i < before else i - before + 1 for i in found))
        return farthest


def _place(text: str, clean: str, claims: list[Claim], claim: Claim, spans: list[tuple[int, int, str]],
           year: Optional[str]) -> _Place:
    """The claim's ``_Place``. Its clause is the gate's (``factcheck._clause_of``); ``text`` is the sentence with its
    citations, ``clean`` without them."""
    heads = [m.end() for m in factcheck._CLAUSE_BREAK.finditer(clean, 0, claim.start)]
    tail = factcheck._CLAUSE_BREAK.search(clean, claim.start + len(claim.text))
    a, b = (heads[-1] if heads else 0), (tail.start() if tail else len(clean))
    others = sorted((c for c in claims if c is not claim and a <= c.start < b), key=lambda c: c.start)
    head, current = a, claim
    for prev in reversed([c for c in others if c.start + len(c.text) <= claim.start]):
        if not _MOVE_GAP.fullmatch(clean[prev.start + len(prev.text):current.start]):
            head = prev.start + len(prev.text)
            break
        current = prev
    end = claim.start + len(claim.text)
    following = [c.start for c in others if c.start >= end]
    stop = following[0] if following else b
    inside = [(s, e, w) for s, e, w in spans if a <= s < b]
    ahead = [(s, e, w) for s, e, w in inside if head <= s < claim.start]
    behind = [(s, e, w) for s, e, w in inside if end <= s < stop]
    before = [(w, bool(_PUNCTUATION.search(text[e:ahead[i + 1][0] if i + 1 < len(ahead) else claim.start])))
              for i, (s, e, w) in enumerate(ahead)]
    after = [(w, bool(_PUNCTUATION.search(text[behind[i - 1][1] if i else end:s]))) for i, (s, e, w) in enumerate(behind)]
    return _Place([(s, w) for s, _, w in inside], claim.start, before, after, _words(claim.text), year,
                  bool(_MOVED.search(clean[max(a, claim.start - 40):claim.start])))


def _fits(vid: str, place: _Place, cited: list[str], pack: dict[str, Any]) -> bool:
    """A reconciling ID fits when the claim is of one year that the ID's period holds; its label's words are attached
    to the figure (``_Place.attached``), unmodified, and as no reference it is not; a movement word before or after the
    figure finds a change; a sentence citing a segment line takes no company-wide value ("NEER's results, to $6.83
    billion of net income"); and no value the sentence cites sits as near the claim (another year of a cited series
    sits exactly as near: a wrong year is as likely as an omitted ID)."""
    words = metric_words(vid, pack)
    if not words or place.year is None or place.year not in factcheck._periods_of(pack["values"][vid]):
        return False
    if not place.attached(words) or place.modified(words) or place.references(words):
        return False
    if (place.moved or place.changed(words)) and not _is_change(vid, pack):
        return False
    if any(_segment_line(c, pack) for c in cited) and not _segment_line(vid, pack):
        return False
    mine = place.distance(words - place.own) or 0
    return not any(near is not None and near <= mine
                   for near in (place.distance(metric_words(other, pack)) for other in cited if metric_words(other, pack)))


@dataclass
class Search:
    """One claim the gate read as matching nothing: the IDs that reconcile it, those that also fit, and the one
    to append (when exactly one fits)."""
    index: int
    claim: str
    reconciling: list[str]
    fitting: list[str]

    @property
    def accepted(self) -> Optional[str]:
        return self.fitting[0] if len(self.fitting) == 1 else None


def search(sentence: dict[str, Any], pack: dict[str, Any], elsewhere: Iterable[str]) -> list[Search]:
    """Auto-citation's search for every claim of ``sentence`` that matches nothing it cites. ``elsewhere`` is the
    IDs the rest of the analysis cites."""
    ids = citations(sentence["text"])
    if not ids:
        return []
    resolved = factcheck.analyse_sentence(sentence, pack)[1]
    misses = [i for i, r in enumerate(resolved) if r.status == "no_match"]
    if not misses:
        return []
    values = pack["values"]
    expanded = _expanded(ids, pack)
    cited = [c for c in expanded if c in values]
    pool = _pool(ids, expanded, elsewhere, pack)
    clean = _blank_citations(sentence["text"])
    claims = [r.claim for r in resolved]
    latest = _latest_year(pack)
    bound = factcheck.bind_periods(clean, claims, latest)
    named = {y for y in factcheck.sentence_periods(sentence["text"]) if latest is None or int(y) <= latest}
    dated = {p[0] for p in (factcheck._periods_of(values[c]) for c in cited) if len(p) == 1}
    spans = _spans(sentence["text"], claims)
    out = []
    for index in misses:
        claim = claims[index]
        # A year the sentence names for another figure says nothing of this one's: then only the cited values' years do.
        others = {year for j, years in bound.items() if j != index for year in years}
        anchors = bound.get(index) or (set() if others else named) or dated
        place = _place(sentence["text"], clean, claims, claim, spans, next(iter(anchors)) if len(anchors) == 1 else None)
        reconciling = [v for v in pool if _exact(claim, values[v]) and _verifies_as(sentence, index, v, pack)]
        out.append(Search(index, claim.text, reconciling, [v for v in reconciling if _fits(v, place, cited, pack)]))
    return out


def _only_targets_changed(before: dict[str, Any], after: dict[str, Any], targets: list[int], pack: dict[str, Any]) -> bool:
    """The appended ID verifies the claims it was found for and changes nothing else: every other claim keeps its
    verdict, and the gate with its backstops fails the sentence for exactly what it failed it for before, less those
    claims' "matches nothing" (so no backstop starts or stops firing on any claim, the targets included)."""
    was, now = factcheck.analyse_sentence(before, pack)[1], factcheck.analyse_sentence(after, pack)[1]
    if len(was) != len(now) or any(now[i].status != "verified" for i in targets):
        return False
    if any(a.status != b.status for i, (a, b) in enumerate(zip(was, now)) if i not in targets):
        return False
    expected = Counter(f["failure"] for f in factcheck.check([before], pack, backstops=True)["failures"])
    expected -= Counter(f"'{was[i].claim.text}' matches nothing the sentence cites" for i in targets)
    return Counter(f["failure"] for f in factcheck.check([after], pack, backstops=True)["failures"]) == expected


def cite_sentence(sentence: dict[str, Any], pack: dict[str, Any], elsewhere: Iterable[str],
                  found: Optional[list[Search]] = None) -> tuple[str, list[tuple[int, str, str]], int]:
    """Fix 1 on one sentence: its text with the IDs appended, each addition as (claim index, claim, ID), and how many
    claims were rejected (an ID reconciled, none was appended). ``found`` is ``search``'s result when the caller has
    it."""
    found = search(sentence, pack, elsewhere) if found is None else found
    rejected = sum(1 for s in found if s.reconciling and not s.accepted)
    targets: dict[str, list[Search]] = {}
    for s in found:
        if s.accepted:
            targets.setdefault(s.accepted, []).append(s)
    text, added = sentence["text"], []
    for vid, searches in targets.items():
        widened = with_citation(text, vid)
        if _only_targets_changed({**sentence, "text": text}, {**sentence, "text": widened}, [s.index for s in searches], pack):
            text = widened
            added += [(s.index, s.claim, vid) for s in searches]
        else:
            rejected += len(searches)
    return text, added, rejected


def _located(output: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """(section key, sentence) for every sentence of an output, in order; the sentence is the output's own dict."""
    for section in output.get("sections", []):
        if not isinstance(section, dict):
            continue
        for sentence in section.get("sentences", []):
            if isinstance(sentence, dict) and isinstance(sentence.get("text"), str):
                yield section.get("key", ""), sentence


def autocite(output: dict[str, Any], pack: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fix 1 over a whole analysis: a copy of ``output`` with the IDs appended, and ``{"added": [{section, sentence,
    claim, id}], "rejected": n}`` (``sentence`` is the text before the addition). ``output`` is not changed."""
    fixed = copy.deepcopy(output)
    located = list(_located(fixed))
    cited = [citations(s["text"]) for _, s in located]
    added: list[dict[str, Any]] = []
    rejected = 0
    for i, (key, sentence) in enumerate(located):
        elsewhere = [c for j, ids in enumerate(cited) if j != i for c in ids]
        text, new, refused = cite_sentence({"section": key, "text": sentence["text"], "type": sentence.get("type", "")},
                                           pack, elsewhere)
        rejected += refused
        added += [{"section": key, "sentence": sentence["text"], "claim": claim, "id": vid} for _, claim, vid in new]
        sentence["text"] = text
    return fixed, {"added": added, "rejected": rejected}


def explanatory(text: str) -> Optional[str]:
    """The first "because", "so", "as" or "due to" that opens an explanation ("so conversion is diluted"), or None.
    Fixed phrases are not ("as a share of", "as reported", "such as", "as well as", "so far")."""
    clean = _blank_citations(text)
    for found in _CONNECTIVE.finditer(clean):
        word, before, after = found.group(1).lower(), clean[:found.start()], clean[found.end():]
        if word == "as" and (_AS_NOT_CAUSAL_AFTER.match(after) or _AS_NOT_CAUSAL_BEFORE.search(before)):
            continue
        if word == "so" and _SO_NOT_CAUSAL_AFTER.match(after):
            continue
        return word
    return None


def beyond_figures(text: str, pack: dict[str, Any]) -> list[str]:
    """The words of ``text`` that are neither figures, years, figure talk, nor words of what it cites (a value's
    label, a red flag's detail)."""
    ids = citations(text)
    named: set[str] = set()
    for vid in ids:
        if vid in pack["values"]:
            named |= _words(pack["values"][vid]["label"])
        elif vid in _flags(pack):
            named |= _words(_flags(pack)[vid]["detail"])
    return [w for _, w in _word_offsets(text, factcheck.parse_claims(text)) if w not in named and w not in _FIGURE_TALK]


def retype(output: dict[str, Any], pack: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fix 5's code: a copy of ``output`` in which each figures-only ``cause`` sentence citing no passage is a
    ``comparison``, and ``[{section, sentence, from, to}]`` for each one changed."""
    fixed = copy.deepcopy(output)
    passages = {p["id"] for p in pack.get("passages", [])}
    changed = []
    for key, sentence in _located(fixed):
        text = sentence["text"]
        if (sentence.get("type") != "cause" or any(i in passages for i in citations(text)) or explanatory(text)
                or beyond_figures(text, pack)):
            continue
        sentence["type"] = "comparison"
        changed.append({"section": key, "sentence": text, "from": "cause", "to": "comparison"})
    return fixed, changed


# The substitution test --------------------------------------------------------------------------------------------

_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
KINDS = ("year", "metric", "threshold", "gap")
ARMS = ("kept", "omitted")


def _printed(claim: Claim, value: float) -> Optional[str]:
    """``value`` printed where ``claim`` stands, at its precision and scale; None when it prints as the claim does."""
    raw = _NUMBER.search(claim.text)
    if raw is None or claim.scale <= 0:
        return None
    magnitude = abs(value) / claim.scale
    number = f"{magnitude:,.{claim.decimals}f}" if "," in raw.group(0) else f"{magnitude:.{claim.decimals}f}"
    if number == raw.group(0) or float(number.replace(",", "")) == 0:
        return None
    return claim.text[:raw.start()] + number + claim.text[raw.end():]


def without(text: str, vid: str) -> str:
    """``text`` with ``vid`` taken out of its citations; a bracket left empty goes."""
    def strip(found: re.Match) -> str:
        ids = ID_RE.findall(found.group(1))
        return found.group(0) if vid not in ids else "".join(f"[{i}]" for i in ids if i != vid)

    return CITATION_RE.sub(strip, text)


def _slots(sentence: dict[str, Any], pack: dict[str, Any]) -> Iterator[tuple[int, Claim, str]]:
    """(claim index, claim, ID) for every verified claim of ``sentence`` matched to one cited value of a series with
    one period."""
    series = {vid: key.split("|") for key, vid in pack.get("series_keys", {}).items()}
    for index, r in enumerate(factcheck.analyse_sentence(sentence, pack)[1]):
        if r.status != "verified" or r.best is None or r.best.how != "cited" or r.claim.unit in ("count", "multiple"):
            continue
        vid = r.best.ids[0]
        if vid in series and len(series[vid]) == 2:
            yield index, r.claim, vid


def substitutes(sentence: dict[str, Any], pack: dict[str, Any], elsewhere: list[str],
                sample: int = 4) -> Iterator[tuple[str, int, str, str, str]]:
    """(kind, claim index, own ID, substituted sentence text, substituted claim) for every slot of ``sentence``
    (``_slots``): that value's series in the year before and after ("year"); other series' values in the same unit
    and period ("metric": every one cited elsewhere in the analysis, then up to ``sample`` of the rest); each figure
    of a red flag whose evidence holds the value ("threshold", printed in the claim's unit when it has it, else as
    the flag prints it: "80%"); and the gap between the value and each other value the sentence cites of its unit and
    single year ("gap": operating cash flow less free cash flow printed as free cash flow)."""
    values, keys = pack["values"], pack.get("series_keys", {})
    series = {vid: key.split("|") for key, vid in keys.items()}
    ids = citations(sentence["text"])
    text = sentence["text"]
    for index, claim, vid in _slots(sentence, pack):
        name, period = series[vid]
        unit = values[vid]["unit"]
        swaps: list[tuple[str, Optional[str]]] = []
        year = re.fullmatch(r"FY(\d{4})", period)
        if year:
            swaps += [("year", _printed(claim, values[keys[f"{name}|FY{y}"]]["value"]))
                      for y in (int(year.group(1)) - 1, int(year.group(1)) + 1) if f"{name}|FY{y}" in keys]
        same = [i for i, v in values.items() if v["unit"] == unit and v.get("period") == period and i in series
                and series[i][0] != name]
        cited = [i for i in same if i in set(elsewhere)]
        rest = [i for i in same if i not in set(cited)]
        step = max(1, len(rest) // sample) if rest else 1
        swaps += [("metric", _printed(claim, values[i]["value"])) for i in cited + rest[::step][:sample]]
        for flag in pack.get("red_flags", []):
            if vid in flag["evidence"]:
                for figure in factcheck.parse_claims(flag["detail"]):
                    if figure.unit in ("count", "plain", "multiple"):
                        continue
                    same_unit = figure.unit == claim.unit
                    swaps.append(("threshold", _printed(claim, figure.value * figure.scale) if same_unit else figure.text))
        own = factcheck._periods_of(values[vid])
        for other in ids:
            if other != vid and other in values and values[other]["unit"] == unit and len(own) == 1 \
                    and factcheck._periods_of(values[other]) == own:
                swaps.append(("gap", _printed(claim, values[other]["value"] - values[vid]["value"])))
        for kind, printed in swaps:
            if printed is not None and printed != claim.text:
                yield kind, index, vid, text[:claim.start] + printed + text[claim.start + len(claim.text):], printed


def _licensed(sentence: dict[str, Any], pack: dict[str, Any], elsewhere: list[str], printed: str) -> tuple[str, Optional[str]]:
    """How auto-citation treats the substituted claim ``printed``: ``gate_reads_otherwise`` (the gate does not read it
    as matching nothing), ``refused`` (an ID reconciled, none was appended), ``licensed`` (an ID was appended for it,
    which is returned) or ``nothing`` (no ID reconciled)."""
    found = search(sentence, pack, elsewhere)
    mine = [s for s in found if s.claim == printed]
    if not mine:
        return "gate_reads_otherwise", None
    _, added, _ = cite_sentence(sentence, pack, elsewhere, found)
    vid = next((v for index, _, v in added if index == mine[0].index), None)
    if vid:
        return "licensed", vid
    return ("refused" if mine[0].reconciling else "nothing"), None


def substitution_test(outputs: Iterable[tuple[str, dict[str, Any], dict[str, Any]]], sample: int = 4) -> dict[str, Any]:
    """Run ``substitutes`` over every sentence of every output ((name, output, pack)) in both arms (module docstring)
    and count, per arm and kind, the substitutes the gate reads as matching nothing and those auto-citation then
    licenses, with each leak; and, in the omitted arm, how often the right value gets its own ID back."""
    counts: dict[str, dict[str, Counter]] = {arm: {kind: Counter() for kind in KINDS} for arm in ARMS}
    control: Counter = Counter()
    leaks: dict[str, list[str]] = {arm: [] for arm in ARMS}
    for name, output, pack in outputs:
        located = list(_located(output))
        cited = [citations(s["text"]) for _, s in located]
        for i, (key, sentence) in enumerate(located):
            elsewhere = [c for j, ids in enumerate(cited) if j != i for c in ids]
            base = {"section": key, "text": sentence["text"], "type": sentence.get("type", "")}
            others = set(citations(base["text"]))
            for index, claim, vid in _slots(base, pack):
                if not others - {vid}:
                    continue  # with its own ID out, the sentence would cite nothing, which auto-citation leaves alone
                omitted = {**base, "text": without(base["text"], vid)}
                state, got = _licensed(omitted, pack, elsewhere, claim.text)
                control["slots"] += 1
                control[{"gate_reads_otherwise": "verified otherwise", "licensed": "recovered" if got == vid else
                         "another ID", "refused": "refused", "nothing": "not recovered"}[state]] += 1
                if state == "licensed" and got != vid:
                    leaks["omitted"].append(f"  {name} [control] '{claim.text}' +[{got}] (own {vid}): {omitted['text']}")
            for kind, index, vid, text, printed in substitutes(base, pack, elsewhere, sample):
                for arm in ARMS:
                    arm_text = text if arm == "kept" else without(text, vid)
                    if arm == "omitted" and not set(citations(arm_text)):
                        continue
                    tally = counts[arm][kind]
                    tally["substitutes"] += 1
                    state, got = _licensed({**base, "text": arm_text}, pack, elsewhere, printed)
                    tally[state] += 1
                    if state != "gate_reads_otherwise":
                        tally["matches_nothing"] += 1
                    if state == "licensed":
                        leaks[arm].append(f"  {name} [{kind}] '{printed}' +[{got}] (own {vid}): {arm_text}")
    return {"counts": {arm: {kind: dict(c) for kind, c in kinds.items()} for arm, kinds in counts.items()},
            "control": dict(control), "leaks": leaks}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == ".gz" else json.loads(path.read_text())


def _pack(records: Path, system: str, ticker: str, packs: dict) -> dict[str, Any]:
    folder = packs_dir(system, records)
    if (folder, ticker) not in packs:
        packed = folder / f"{ticker}.json.gz"
        packs[(folder, ticker)] = _load(packed if packed.exists() else folder / f"{ticker}.json")
    return packs[(folder, ticker)]


def recorded(records: Path, labels: list[str],
             systems: Optional[list[str]] = None) -> Iterator[tuple[str, dict[str, Any], dict[str, Any]]]:
    """(name, record, pack) for every generation record under ``runs/<label>/`` with an output."""
    packs: dict = {}
    for label in labels:
        for folder in sorted(p for p in (records / "runs" / label).iterdir() if p.is_dir() and not p.name.startswith(SKIP)):
            if systems and folder.name not in systems:
                continue
            for path in sorted(folder.glob("*.json")):
                record = json.loads(path.read_text())
                if isinstance(record.get("output"), dict):
                    yield f"{label}/{folder.name}/{record['ticker']}", record, _pack(records, folder.name, record["ticker"], packs)


def _sentences(output: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"section": key, "text": s["text"], "type": s.get("type", "")} for key, s in _located(output)]


def real_failures(records: Path, labels: list[str], system: str) -> list[str]:
    """Each first pass of ``system`` that fails the gate or its backstops, through retyping and auto-citation: what
    was added, and what remains; then how many first passes would still go to a repair."""
    lines, tally = [], Counter()
    for name, record, pack in recorded(records, labels, [system]):
        first = record.get("first_pass_output") or record["output"]
        tally["first passes"] += 1
        before = factcheck.check(_sentences(first), pack, backstops=True)
        if before["passed"]:
            continue
        fixed, retyped = retype(first, pack)
        fixed, cited = autocite(fixed, pack)
        after = factcheck.check(_sentences(fixed), pack, backstops=True)
        plain = [f for f in after["failures"] if not f["failure"].startswith("backstop ")]
        tally.update({"failing": 1, "failing after the code fixes": not after["passed"],
                      "failing the gate alone": any(not f["failure"].startswith("backstop ") for f in before["failures"]),
                      "failing the gate alone after the code fixes": bool(plain)})
        lines.append(f"{name}: {len(before['failures'])} failure(s) -> {len(after['failures'])} "
                     f"({len(plain)} of the gate itself); rejected {cited['rejected']}")
        lines += [f"    was: {f['failure']} | {f['sentence']}" for f in before["failures"]]
        lines += [f"    retyped: {r['sentence']}" for r in retyped]
        lines += [f"    +[{a['id']}] for '{a['claim']}' ({a['id']} = {pack['values'].get(a['id'], {}).get('label', 'red flag')}, "
                  f"{pack['values'].get(a['id'], {}).get('period', '')})" for a in cited["added"]]
        lines += [f"    still: {f['failure']} | {f['sentence']}" for f in after["failures"]]
    lines.append("  " + "; ".join(f"{key}: {count}" for key, count in tally.items()))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--labels", default="eval-v1,dev-v3,dev-v4", help="runs whose outputs the substitution test reads")
    parser.add_argument("--real", default="eval-v1,dev-v4", help="runs whose first passes are replayed")
    parser.add_argument("--system", default="deepseek-flash", help="the system whose first passes are replayed")
    parser.add_argument("--sample", type=int, default=4, help="wrong-metric values per claim beyond those cited elsewhere")
    args = parser.parse_args()
    outputs = ((name, record["output"], pack) for name, record, pack in recorded(RECORDS, args.labels.split(",")))
    result = substitution_test(outputs, args.sample)
    print(f"1. Substitution test over {args.labels}\n")
    for arm in ARMS:
        print(f"  {arm}: the claim's own ID {'kept' if arm == 'kept' else 'removed, another still cited'}")
        for kind, counts in result["counts"][arm].items():
            judged = counts.get("matches_nothing", 0)
            rate = counts.get("licensed", 0) / judged if judged else 0.0
            print(f"    {kind:9} substitutes {counts.get('substitutes', 0):6}  read otherwise by the gate "
                  f"{counts.get('gate_reads_otherwise', 0):6}  matching nothing {judged:6}  refused {counts.get('refused', 0):5}  "
                  f"licensed {counts.get('licensed', 0):4}  leak rate {rate:.2%}")
    control = result["control"]
    print(f"\n  omitted, the right value (recall): {control.get('slots', 0)} own IDs removed; "
          + "; ".join(f"{key} {control.get(key, 0)}" for key in ("recovered", "another ID", "refused", "not recovered",
                                                                 "verified otherwise")))
    for arm in ARMS:
        print(f"\n  Leaks, {arm}:\n" + ("\n".join(result["leaks"][arm]) or "  none"))
    print(f"\n2. {args.system}'s failing first passes in {args.real}, through retyping and auto-citation\n")
    print("\n".join(real_failures(RECORDS, args.real.split(","), args.system)) or "  none")


if __name__ == "__main__":
    main()
