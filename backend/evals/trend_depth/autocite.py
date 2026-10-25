"""Code fixes the version-2 repair loop makes to a first pass before the gate decides on a repair
(DEEPSEEK-ERRORS.md fixes 1 and 5), and the substitution test that bounds what fix 1 could license.

    cd backend && python -m evals.trend_depth.autocite                         # the substitution test, then the real failures
    cd backend && python -m evals.trend_depth.autocite --labels eval-v1 --real dev-v4

**Fix 1, auto-citation** (``autocite``). DeepSeek often states a correct figure without its own ID: it cites only
a value derived from it, relies on an earlier sentence, or uses a red flag's threshold without the flag. For
each claim the gate reads as matching nothing its sentence cites, one ID is looked for among:

- the values cited elsewhere in the same analysis;
- the inputs of a derived value the sentence cites, of that value's own period;
- the red flag whose evidence the sentence cites in full (a flag licenses its evidence, so a flag the
  sentence cites only part of would license more than the one figure).

An ID *reconciles* when the claim verifies once the ID is appended to the sentence (the gate itself decides, with
its period binding and direction rules) as the ID's own value, a figure of its flag's detail, or one side of a
difference with a cited level of the same year ("beat operating margin by 1.2pp"; never two changes, and never
under a direction word, which makes the figure a change). The ID is appended only when exactly one reconciling ID
also *fits* (``_fits``):

- its period agrees with the claim's years (those bound to it, else those the sentence names, else those of the
  single-year values it cites);
- its label's metric words are attached to the claim: each stands in the clause's subject, the claim's own phrase
  or the words right after it ("the 52.4% efficiency ratio"), and one stands in the last two. A flag's metric words
  are its detail's before its first figure;
- a figure right after a movement word ("SG&A fell 30.3%") takes only a change;
- the words name the claim unmodified ("Data Center revenue" is no total revenue, "incremental operating
  margin" no operating margin), and as a reference when the phrase is one ("whose median net cash is");
- no value the sentence cites sits as near the claim (so never another year of a cited series).

Passages are never candidates: they carry no label to check against. A sentence that cites nothing is left alone
(its figures are thresholds or forecasts more often than omissions). Every addition is recorded; ``rejected``
counts the claims for which some ID reconciled but none was appended. The output still carries every figure's own
ID, so the grounding rule does not change.

**Fix 5, retyping** (``retype``). A ``cause`` sentence that cites no passage, opens no explanatory clause
("because", "so", "as", "due to": ``explanatory``) and says nothing beyond its figures (every word is a figure,
a year, a word of a cited value's label or of a cited flag's detail, or figure talk such as "offset",
"consumed", "flat") is a margin bridge or a capital-return sentence mistyped. It becomes a ``comparison``.

**Substitution test** (``substitution_test``). Every verified claim matched to one cited value, in every recorded
output, has that value replaced by the same series' value in the neighbouring years (wrong year) and by values
of other series in the same unit and period (wrong metric: first those cited elsewhere in the analysis, the
ones auto-citation draws from, then a sample of the rest of the pack). A substitute the gate reads as matching
nothing is one auto-citation gets to judge; it *leaks* when auto-citation appends an ID that makes it verify.

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
from evals.trend_depth.factcheck import CITATION_RE, ID_RE, Candidate, Claim
from evals.trend_depth.providers import packs_dir

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
SKIP = ("judge", "causes", "semantics")  # audit and verdict folders beside the systems

_TOKEN = re.compile(r"[a-z0-9&]*[a-z][a-z0-9&]*")
_PARENS = re.compile(r"\([^)]*\)")
_DENOMINATOR = re.compile(r"\s%\s+of\s.*$")  # "Net cash % of revenue": the % already names the denominator
_LABEL_STOP = frozenset({"of", "and", "the", "a", "an", "in", "on", "to", "vs", "per", "plus", "less", "minus", "window",
                         "as", "at", "for", "by", "it", "from", "that"})
_FLAG_STOP = _LABEL_STOP | {"ran", "run", "rose", "fell", "cover", "below", "above", "was", "moved", "exceeded",
                            "declined", "row", "year", "later", "first"}
_REFERENCE = (("percentile", ("percentile",)), ("peer median", ("peer", "median")))
_CHAIN_GAP = re.compile(r"\s*(?:,|,?\s*(?:and|or|to|from|then))?\s*", re.I)  # "fell 3.9pp to 71.1%", "8%, 9% and 12%"
_OF_COMPLEMENT = re.compile(r"^\s*of\b", re.I)  # "282.3% of revenue": the words after "of" name the figure before
_COMPLEMENT_END = re.compile(r"[,;]|\band\b", re.I)  # "17.0% growth and now": the words up to "and" name it too
_REFERENCE_WORDS = frozenset({"median", "high", "low"})
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


def _blank_citations(text: str) -> str:
    return CITATION_RE.sub(lambda m: " " * len(m.group(0)), text)


def _word_offsets(text: str, claims: list[Claim]) -> list[tuple[int, str]]:
    """(offset, word) for every word of ``text`` that is no citation, year or figure, in order."""
    clean = factcheck._clean_for_numbers(text)
    for claim in claims:
        clean = clean[:claim.start] + " " * len(claim.text) + clean[claim.start + len(claim.text):]
    return [(m.start(), _norm(m.group())) for m in _TOKEN.finditer(clean.lower())]


def citations(text: str) -> list[str]:
    return [i for group in CITATION_RE.findall(text) for i in ID_RE.findall(group)]


def _flags(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in pack.get("red_flags", [])}


def _expanded(ids: list[str], pack: dict[str, Any]) -> list[str]:
    """The sentence's citations and the evidence of the red flags among them: what the gate licenses."""
    flags = _flags(pack)
    return list(dict.fromkeys([*ids, *(e for i in ids if i in flags for e in flags[i]["evidence"])]))


def metric_words(vid: str, pack: dict[str, Any]) -> frozenset[str]:
    """The words a clause must contain to be about ``vid``: its label's words (the numerator of a "% of" label,
    "percentile" or "peer median" for a peer reference, "median", "high" or "low" for a window one), or a red
    flag's detail before its first figure. Empty when nothing names it."""
    if vid in pack["values"]:
        base, _, reference = _PARENS.sub(" ", pack["values"][vid]["label"]).partition(":")
        words = _words(_DENOMINATOR.sub("", base)) - _LABEL_STOP
        for marker, needed in _REFERENCE:
            if marker in reference.lower():
                return frozenset(words | set(needed))
        return frozenset(words | (_words(reference) - _LABEL_STOP))
    flag = _flags(pack).get(vid)
    if flag is None:
        return frozenset()
    detail = factcheck._clean_for_numbers(flag["detail"])
    first = re.search(r"\d", detail)
    return frozenset(_words(detail[:first.start() if first else len(detail)]) - _FLAG_STOP)


def _periods(vid: str, pack: dict[str, Any]) -> set[str]:
    values = pack["values"]
    if vid in values:
        return set(factcheck._periods_of(values[vid]))
    flag = _flags(pack).get(vid, {})
    return {p for e in flag.get("evidence", []) if e in values for p in factcheck._periods_of(values[e])}


def _latest_year(pack: dict[str, Any]) -> Optional[int]:
    return max((int(y) for v in pack["values"].values() for y in factcheck._periods_of(v)), default=None)


def with_citation(text: str, vid: str) -> str:
    """``text`` with ``[vid]`` after its closing citations, before the final punctuation."""
    end = len(text.rstrip())
    while end and text[end - 1] in ".;:!?":
        end -= 1
    joined = text[:end].endswith("]") and any(m.end() == end for m in CITATION_RE.finditer(text))
    return text[:end] + ("" if joined else " ") + f"[{vid}]" + text[end:]


def _pool(ids: list[str], expanded: list[str], elsewhere: Iterable[str], pack: dict[str, Any]) -> list[str]:
    """The IDs auto-citation may add (module docstring), in a fixed order, none the sentence already licenses."""
    values = pack["values"]
    pool = [i for i in elsewhere if i in values]
    for cid in expanded:
        derived = values.get(cid) or {}
        own = factcheck._periods_of(derived) if derived else ()
        pool += [i for i in derived.get("inputs", []) if i in values and factcheck._periods_of(values[i]) == own]
    pool += [fid for fid, flag in _flags(pack).items() if flag["evidence"] and set(flag["evidence"]) <= set(expanded)]
    return [i for i in dict.fromkeys(pool) if i not in expanded and i not in ids]


def _is_change(vid: str, pack: dict[str, Any]) -> bool:
    return bool(_CHANGE_LABEL.search(pack["values"][vid]["label"])) if vid in pack["values"] else False


def _allowed(cand: Candidate, vid: str, expanded: list[str], pack: dict[str, Any]) -> bool:
    """The ways ``vid`` may reconcile a claim: as its own value, as a figure of its red flag's detail, or as one
    side of a difference with a cited level of the same single year ("beat operating margin by 1.2pp")."""
    if cand.ids == (vid,):
        return cand.how == "cited" or cand.how.startswith("reversed ") or vid in _flags(pack)
    if cand.how.startswith(("pp ", "difference ")) and len(cand.ids) == 2 and vid in cand.ids:
        values = pack["values"]
        other = cand.ids[1] if cand.ids[0] == vid else cand.ids[0]
        years = [factcheck._periods_of(values[i]) for i in cand.ids if i in values]
        return (other in expanded and len(years) == 2 and len(years[0]) == 1 and years[0] == years[1]
                and not any(_is_change(i, pack) for i in cand.ids))
    return False


def _could_match(claim: Claim, expanded: list[str], vid: str, pack: dict[str, Any], cache: dict) -> bool:
    """A quick screen: a candidate ``vid`` adds in an allowed way matches the claim. The gate decides
    (``_reconciles``)."""
    key = (tuple(expanded), vid)
    if key not in cache:
        cache[key] = [c for c in factcheck.candidates([*expanded, vid], pack) if _allowed(c, vid, expanded, pack)]
    as_pct = Claim(claim.text, claim.value, "pct", claim.decimals, claim.scale, claim.qualifier, claim.start)
    return any(factcheck.matches(claim, c) or (claim.unit == "pp" and c.how == "cited" and factcheck.matches(as_pct, c))
               for c in cache[key])


def _reconciles(sentence: dict[str, Any], index: int, vid: str, expanded: list[str], pack: dict[str, Any]) -> bool:
    """The claim verifies, in an allowed way, once ``[vid]`` is appended to the sentence. A difference of two
    metrics of one year is no reading of a claim a direction word governs ("edged up 5.5pp" is a change)."""
    resolved = factcheck.analyse_sentence({**sentence, "text": with_citation(sentence["text"], vid)}, pack)[1][index]
    return resolved.status == "verified" and any(_allowed(c, vid, expanded, pack) and (len(c.ids) == 1 or resolved.direction is None)
                                                 for c in resolved.in_period)


@dataclass
class _Place:
    """Where a claim sits in its clause, by the clause's words (with their offsets): the words before the clause's
    first figure (its subject), the words of the claim's own phrase, the words after it up to the next figure, and
    the years it may be of; ``moved`` when a movement word stands right before it ("grew 45.0%")."""
    positions: list[tuple[int, str]]
    start: int
    subject: set[str]
    own: set[str]
    after: list[str]
    anchors: set[str]
    moved: bool

    def phrase(self, words: frozenset[str]) -> set[str]:
        """The claim's own phrase and the run of words right after it, as long as ``words``."""
        return self.own | set(self.after[:len(words)])

    def attached(self, words: frozenset[str]) -> bool:
        """Every word stands in the clause's subject, the claim's own phrase or the run right after it ("the 52.4%
        efficiency ratio"), and one of them in the last two."""
        phrase = self.phrase(words)
        return all(w in self.subject or w in phrase for w in words) and bool(words & phrase)

    def modified(self, words: frozenset[str]) -> bool:
        """A word before the claim follows a word that is neither one of ``words`` nor figure talk: the phrase names
        a narrower metric ("Data Center revenue", "EMEA operating income") or another one ("operating cash flow" is
        no net cash)."""
        after = set(self.after[:len(words)])
        tokens = [word for at, word in self.positions if at < self.start]
        for word in words - after:
            found = [i for i, token in enumerate(tokens) if token == word]
            if found and found[-1] and tokens[found[-1] - 1] not in words and tokens[found[-1] - 1] not in _FIGURE_TALK:
                return True
        return False

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


def _place(clean: str, claims: list[Claim], claim: Claim, tokens: list[tuple[int, str]], anchors: set[str]) -> _Place:
    """The claim's ``_Place``. Its clause is the gate's (``factcheck._clause_of``). Its own phrase runs from the figure
    before it, reaching back over figures chained or listed with it ("Gross margin fell 3.9pp to 71.1%") and past
    the words that name that figure: its "of" complement to the next comma ("282.3% of revenue, from $22.7 billion"),
    else what precedes the first comma or "and" ("17.0% growth and now is 10.6%"), to the claim."""
    heads = [m.end() for m in factcheck._CLAUSE_BREAK.finditer(clean, 0, claim.start)]
    tail = factcheck._CLAUSE_BREAK.search(clean, claim.start + len(claim.text))
    a, b = (heads[-1] if heads else 0), (tail.start() if tail else len(clean))
    others = sorted((c for c in claims if c is not claim and a <= c.start < b), key=lambda c: c.start)
    head, current = a, claim
    for prev in reversed([c for c in others if c.start + len(c.text) <= claim.start]):
        gap = clean[prev.start + len(prev.text):current.start]
        if not _CHAIN_GAP.fullmatch(gap):
            head = prev.start + len(prev.text)
            cut = re.search(r"[,;]", gap) if _OF_COMPLEMENT.match(gap) else _COMPLEMENT_END.search(gap)
            head += cut.end() if cut else len(gap) if _OF_COMPLEMENT.match(gap) else 0
            break
        current = prev
    end = claim.start + len(claim.text)
    following = [c.start for c in others if c.start >= end]
    stop = following[0] if following else b
    first = min([claim.start, *(c.start for c in others)])
    positions = [(at, word) for at, word in tokens if a <= at < b]
    return _Place(positions, claim.start, {w for at, w in positions if at < first},
                  {w for at, w in positions if head <= at < claim.start},
                  [w for at, w in positions if end <= at < stop], anchors,
                  bool(_MOVED.search(clean[max(a, claim.start - 40):claim.start])))


def _fits(vid: str, place: _Place, cited: list[str], pack: dict[str, Any]) -> bool:
    """A reconciling ID fits when its period agrees with the claim's years and its metric words are attached to the
    claim. A value must also be a change when a movement word governs the claim ("SG&A fell 30.3%" is no share of
    revenue); its words must name the claim unmodified ("Data Center revenue" is no total revenue, "incremental
    operating margin" no operating margin) and as a reference when the phrase is one ("whose median net cash is" is
    no company's level); and no value the sentence cites may sit as near the claim (another year of a cited series
    sits exactly as near: a wrong year is as likely as an omitted ID)."""
    words = metric_words(vid, pack)
    if not words or not _periods(vid, pack) & place.anchors or not place.attached(words):
        return False
    if vid in _flags(pack):
        return True  # the sentence cites its evidence in full: it is about the sentence's own metric
    if place.moved and not _is_change(vid, pack) or place.modified(words) or place.phrase(words) & _REFERENCE_WORDS - words:
        return False
    mine = place.distance(words)
    return not any(near is not None and near <= mine
                   for near in (place.distance(metric_words(other, pack)) for other in cited if metric_words(other, pack)))


@dataclass
class Search:
    """One claim the gate read as matching nothing: the IDs that reconcile it, those that also fit, and the one
    appended (when exactly one fits)."""
    index: int
    claim: str
    reconciling: list[str]
    fitting: list[str]

    @property
    def accepted(self) -> Optional[str]:
        return self.fitting[0] if len(self.fitting) == 1 else None


def search(sentence: dict[str, Any], pack: dict[str, Any], elsewhere: Iterable[str],
           cache: Optional[dict] = None) -> list[Search]:
    """Auto-citation's search for every claim of ``sentence`` that matches nothing it cites. ``elsewhere`` is the
    IDs the rest of the analysis cites; ``cache`` may be shared across calls on one pack."""
    ids = citations(sentence["text"])
    if not ids:
        return []
    resolved = factcheck.analyse_sentence(sentence, pack)[1]
    misses = [i for i, r in enumerate(resolved) if r.status == "no_match"]
    if not misses:
        return []
    cache = {} if cache is None else cache
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
    tokens = _word_offsets(sentence["text"], claims)
    out = []
    for index in misses:
        claim = claims[index]
        place = _place(clean, claims, claim, tokens, bound.get(index) or named or dated)
        reconciling = [v for v in pool
                       if _could_match(claim, expanded, v, pack, cache) and _reconciles(sentence, index, v, expanded, pack)]
        out.append(Search(index, claim.text, reconciling, [v for v in reconciling if _fits(v, place, cited, pack)]))
    return out


def _located(output: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """(section key, sentence) for every sentence of an output, in order; the sentence is the output's own dict."""
    for section in output.get("sections", []):
        if not isinstance(section, dict):
            continue
        for sentence in section.get("sentences", []):
            if isinstance(sentence, dict) and isinstance(sentence.get("text"), str):
                yield section.get("key", ""), sentence


def autocite(output: dict[str, Any], pack: dict[str, Any], cache: Optional[dict] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fix 1 over a whole analysis: a copy of ``output`` with the IDs appended, and ``{"added": [{section, sentence,
    claim, id}], "rejected": n}`` (``sentence`` is the text before the addition). ``output`` is not changed."""
    fixed = copy.deepcopy(output)
    located = list(_located(fixed))
    cited = [citations(s["text"]) for _, s in located]
    added: list[dict[str, Any]] = []
    rejected = 0
    cache = {} if cache is None else cache
    for i, (key, sentence) in enumerate(located):
        elsewhere = [c for j, ids in enumerate(cited) if j != i for c in ids]
        found = search({"section": key, "text": sentence["text"], "type": sentence.get("type", "")}, pack, elsewhere, cache)
        new = [s for s in found if s.accepted]
        rejected += sum(1 for s in found if s.reconciling and not s.accepted)
        added += [{"section": key, "sentence": sentence["text"], "claim": s.claim, "id": s.accepted} for s in new]
        for vid in dict.fromkeys(s.accepted for s in new):
            sentence["text"] = with_citation(sentence["text"], vid)
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


def substitutes(sentence: dict[str, Any], pack: dict[str, Any], elsewhere: list[str],
                sample: int = 4) -> Iterator[tuple[str, str, str]]:
    """(kind, substituted sentence text, substituted claim) for every verified claim of ``sentence`` matched to one
    cited value: that value's series in the year before and after ("year"), and other series' values in the same
    unit and period ("metric"): every one cited elsewhere in the analysis, then up to ``sample`` of the rest."""
    values, keys = pack["values"], pack.get("series_keys", {})
    series = {vid: key.split("|") for key, vid in keys.items()}
    resolved = factcheck.analyse_sentence(sentence, pack)[1]
    for r in resolved:
        if r.status != "verified" or r.best is None or r.best.how != "cited" or r.claim.unit in ("count", "multiple"):
            continue
        vid = r.best.ids[0]
        if vid not in series or len(series[vid]) != 2:
            continue
        name, period = series[vid]
        year = re.fullmatch(r"FY(\d{4})", period)
        swaps: list[tuple[str, str]] = []
        if year:
            swaps += [("year", keys[f"{name}|FY{y}"]) for y in (int(year.group(1)) - 1, int(year.group(1)) + 1)
                      if f"{name}|FY{y}" in keys]
        unit = values[vid]["unit"]
        same = [i for i, v in values.items() if v["unit"] == unit and v.get("period") == period and i in series
                and series[i][0] != name]
        cited = [i for i in same if i in set(elsewhere)]
        rest = [i for i in same if i not in set(cited)]
        step = max(1, len(rest) // sample) if rest else 1
        swaps += [("metric", i) for i in cited + rest[::step][:sample]]
        for kind, other in swaps:
            printed = _printed(r.claim, values[other]["value"])
            if printed is None:
                continue
            text = sentence["text"][:r.claim.start] + printed + sentence["text"][r.claim.start + len(r.claim.text):]
            yield kind, text, printed


def substitution_test(outputs: Iterable[tuple[str, dict[str, Any], dict[str, Any]]], sample: int = 4) -> dict[str, Any]:
    """Run ``substitutes`` over every sentence of every output ((name, output, pack)) and count, per kind, the
    substitutes the gate reads as matching nothing and those auto-citation then licenses, with each leak."""
    counts: dict[str, Counter] = {"year": Counter(), "metric": Counter()}
    leaks: list[str] = []
    caches: dict[int, dict] = {}
    for name, output, pack in outputs:
        cache = caches.setdefault(id(pack), {})
        located = list(_located(output))
        cited = [citations(s["text"]) for _, s in located]
        for i, (key, sentence) in enumerate(located):
            elsewhere = [c for j, ids in enumerate(cited) if j != i for c in ids]
            base = {"section": key, "text": sentence["text"], "type": sentence.get("type", "")}
            for kind, text, printed in substitutes(base, pack, elsewhere, sample):
                counts[kind]["substitutes"] += 1
                changed = {**base, "text": text}
                found = [s for s in search(changed, pack, elsewhere, cache) if s.claim == printed]
                if not found:
                    counts[kind]["gate_reads_otherwise"] += 1  # it verifies by another route, or fails on period or sign
                    continue
                counts[kind]["matches_nothing"] += 1
                if found[0].reconciling and not found[0].accepted:
                    counts[kind]["refused"] += 1
                if found[0].accepted:
                    counts[kind]["licensed"] += 1
                    leaks.append(f"  {name} [{kind}] '{printed}' +[{found[0].accepted}]: {text}")
    return {"counts": {k: dict(v) for k, v in counts.items()}, "leaks": leaks}


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
    for kind, counts in result["counts"].items():
        judged = counts.get("matches_nothing", 0)
        rate = counts.get("licensed", 0) / judged if judged else 0.0
        print(f"  {kind:6} substitutes {counts.get('substitutes', 0):6}  read otherwise by the gate "
              f"{counts.get('gate_reads_otherwise', 0):6}  matching nothing {judged:6}  refused {counts.get('refused', 0):5}  "
              f"licensed {counts.get('licensed', 0):4}  leak rate {rate:.2%}")
    print("\n  Leaks:\n" + ("\n".join(result["leaks"]) or "  none"))
    print(f"\n2. {args.system}'s failing first passes in {args.real}, through retyping and auto-citation\n")
    print("\n".join(real_failures(RECORDS, args.real.split(","), args.system)) or "  none")


if __name__ == "__main__":
    main()
