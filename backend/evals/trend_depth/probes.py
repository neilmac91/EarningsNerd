"""Backstop probes: verified numbers said about the wrong thing (DEEPSEEK-ERRORS.md fix 12).

The gate (``factcheck.py``) proves that each number matches a value its sentence cites. It cannot see that the
matched value was said about another metric, basis, year or sign. These probes read the gate's own resolution
of every claim (``factcheck.analyse_sentence``) and look for the shapes those errors took in the recorded
outputs:

- ``R1``: a reference level (window median, high or low, peer median or percentile) of another ratio set against
  this ratio: "operating cash flow was 2.76x net income, above the 1.10x window median" of free cash flow. The
  ratio is the nearest ``x`` level before the reference; margins and shares are left out, because a sentence that
  names two of them ("whose medians are 25.7% operating and 16.3% net") labels each reference in words. A figure
  the words after it call a median, high or low reads as the reference the gate also matched for it, even when
  the gate settled it on a level of the same value ("below the 1.11x peer median" of free cash flow, when
  operating cash flow's own ratio is also 1.11x and cited first).
- ``R2a``: a minus sign under "net debt" ("Net debt has deepened from -$50.0 billion to -$89.6 billion"). The
  pack's net cash is negative for an indebted company. A figure's label is the one attached to it ("net cash of
  -$34.3 billion", "-3.5% net cash"); else, for a reference level, the label of the net-cash level it is set
  against ("net debt of $26.2 billion is net cash of -38.8% of revenue, against a -35.6% peer median", the
  candidate prompt's own form); else "net cash" if that label comes anywhere before the figure, so net cash's
  own sign under its own name never fires ("Net cash has fallen into deeper net debt, from -$76.2 billion");
  else the nearest label before it, else the first after it. A net cash flow is not a label.
- ``R2c``: "better" or "worse" between a company's net cash and a reference level of net cash, between or after
  the two numbers, that the signed values contradict ("Net debt is 38.8% of revenue, better than the -35.6%
  peer median": -38.8 is below -35.6).
- ``R3``: a difference of two different margins taken from two different years ("net margin 6.5pp under
  operating margin" from FY2025's net margin and FY2024's operating margin), when nothing else explains it.
- ``U1``: an unsigned fall: a CAGR or change printed with no sign whose value is negative, with no direction or
  fall word in its clause, nor in the words before a colon that introduce a list ("the three years to FY2025
  show a 5.3% CAGR" for -5.3%; not "Revenue declined three years running: 16.5% ..."). A fall printed with a
  plus sign ("a +5.3% CAGR"), whatever words surround it.
- ``unitless_dollars``: a dollar figure with no scale matched only to a passage's raw literal ("currency moves
  added $126 of expense" from a 10-K whose tables are in millions).
- ``gap_direction``: net margin said to be above (beat, exceed) or below (trail, under) operating margin against
  the sign of the same year's gap: a cited "net margin minus operating margin" value, or the difference of the two
  margins the gate matched ("Net margin was 3.4pp above operating margin" for -3.4). The sentence must name both
  margins, the comparative relating the one before it to the one after it.
- ``broken_debt`` (``broken_debt()``): total debt, net cash or net debt, or a figure built on them (their share of
  revenue, debt growth, the net-cash peer rank), stated for a year inside a span the pack's ``debt_break`` data
  checks name, in a sentence that does not disclose the break (``DISCLOSURE``). Reached through a value built on a
  broken year (the IDs version 2 withholds), or restated from the visible lines: a debt line of a broken year, alone
  or with cash, where the nearest debt words before the figure are "total debt", "net cash" or "net debt" ("Net
  cash was $8.8 billion in FY2025", cash less the one debt line left). Silent on a pack that names no break, as
  version 1 does; a measure passes version 2's breaks to read every arm alike.

``factcheck.check(..., backstops=True)`` turns these (``GATE_KINDS``) into failures. ``probe`` and
``probe_sentence`` return every kind but ``broken_debt``, which reads the whole pack's breaks and is its own
measure, not a mislabel. Three logic checks are measures only, never failures (``MEASURE_KINDS``); they were
written after reading DeepSeek's eval-v1 outputs:

- ``logic_direction``: "rose to X" (or "fell to") where X is below (above) the figure it moved "from", or, with
  no "from", its own series' value the year before (by magnitude when a negative value is printed unsigned:
  "investing outflow rose to $52.2 billion").
- ``logic_from_order``: "from A to B" where A is the later year of one series, or a rise or fall word before
  "from" disagrees with B - A as printed.
- ``logic_recover``: "recover toward A from B" where A is the worse level (lower; higher for a lower-is-better
  metric).

Pure: reads sentences and a pack, calls no model and writes nothing. Each hit is a dict with ``kind``,
``section``, ``sentence``, ``claim`` and ``detail``.
"""
from __future__ import annotations

import re
from typing import Any, NamedTuple, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.factcheck import CITATION_RE, Candidate, Resolution

GATE_KINDS = ("R1", "R2a", "R2c", "R3", "U1", "unitless_dollars", "gap_direction", "broken_debt")
MEASURE_KINDS = ("logic_direction", "logic_from_order", "logic_recover")

_RATIO_UNITS = ("x",)  # R1's ratios; a margin's or share's reference is usually named in words (module docstring)
_REFERENCE_PREFIXES = ("median", "high", "low", "peer_median", "peer_pctile")
_REFERENCE_LABEL = re.compile(r"(?: window (?:median|high|low)(?: \(FY\d{4}\))?|: .+ peer median \(n=\d+\)|: percentile vs .+)$", re.I)
_CALLED_REFERENCE = re.compile(r"^\s*(?:(?:window|peer|industry|sector)\s+|[a-z&-]+\s+peer\s+)?(?:median|high|low)\b", re.I)
_NET_CASH_SERIES = ("net_cash", "net_cash_to_revenue")
_NET_ATTACHED_BEFORE = re.compile(r"\bnet (cash|debt)(?: position)?(?: of| at| was| is| to| reached)?\s*$", re.I)
_NET_ATTACHED_AFTER = re.compile(r"^\s*(?:of\s+)?net (cash|debt)\b", re.I)
_NET_LABEL = re.compile(r"\bnet (cash|debt)\b(?!\s+(?:flows?|provided|used|generated)\b)", re.I)
_COMPARATIVE = re.compile(r"\b(better|worse)\b", re.I)
_STRONG_BREAK = re.compile(r";|\bwhile\b|\bwhereas\b|\bbut\b", re.I)
_CHANGE_LABEL = re.compile(r"\bCAGR\b|\bgrowth(?:$|,)|\bchange$", re.I)
_FALL_WORDS = re.compile(
    r"\b(?:dip\w*|drag\w*|subtract\w*|negative|loss\w*|deficit|minus|shortfall|slump\w*|plung\w*|slid\w*|slide|sank|"
    r"sink\w*|cut\w*|retreat\w*|lost|weak\w*|shed)\b", re.I)
_LIST_BREAK = re.compile(r";|,\s+(?:and|but|while|whereas)\b|\bwhile\b|\bwhereas\b|\bbut\b", re.I)
_RISE, _FALL = r"rose|risen|rising|increased|grew|climbed|jumped", r"fell|fallen|falling|decreased|declined|dropped|slipped|shrank"
_MOVED_TO = re.compile(rf"\b(?:({_RISE})|({_FALL}))\s+(?:back\s+)?to\s*$", re.I)
_MOVED_FROM = re.compile(rf"\b(?:({_RISE})|({_FALL}))\s+from\s*$", re.I)
_FROM = re.compile(r"\bfrom\s*$", re.I)
_RECOVER = re.compile(r"\brecover\w*\s+(?:back\s+)?(?:toward|towards|to)\b[^0-9]{0,40}$", re.I)


def series_by_id(pack: dict[str, Any]) -> dict[str, str]:
    """Value ID -> its series: the series key without its period ("median:fcf_to_ni", "net_cash")."""
    return {vid: key.split("|")[0] for key, vid in pack.get("series_keys", {}).items()}


def _prior(pack: dict[str, Any], keys: dict[str, str], vid: str) -> Optional[dict[str, Any]]:
    """The same series' value for the year before, when the value is a single year's."""
    year = re.fullmatch(r"FY(\d{4})", str(pack["values"][vid].get("period", "")))
    prior = pack["series_keys"].get(f"{keys[vid]}|FY{int(year.group(1)) - 1}") if year and vid in keys else None
    return pack["values"].get(prior) if prior else None


def _identity(cand: Optional[Candidate], values: dict[str, Any], keys: dict[str, str]) -> Optional[tuple[str, Optional[str], str]]:
    """("level" | "reference", series, label) of the metric a matched candidate is: a cited value, or a ratio of
    two cited values ("1.11x net income" computed from operating cash flow and net income)."""
    if cand is None:
        return None
    if cand.how == "cited":
        vid = cand.ids[0]
        series, label = keys.get(vid), re.sub(r" \(FY\d{4}\)$", "", values[vid]["label"])
        prefix, _, base = (series or "").partition(":")
        if base and prefix in _REFERENCE_PREFIXES:
            return "reference", base, _REFERENCE_LABEL.sub("", values[vid]["label"])
        return "level", series, label
    if cand.how.startswith("ratio ") and len(cand.ids) == 2:
        a, b = (values[i]["label"] for i in cand.ids)
        return "level", None, f"{a} / {b}"
    return None


def _same_metric(level: tuple[str, Optional[str], str], reference: tuple[str, Optional[str], str]) -> bool:
    if level[1] and reference[1]:
        return level[1] == reference[1]
    return level[2].strip().lower() == reference[2].strip().lower()


def _hit(kind: str, sentence: dict[str, Any], claim: str, detail: str) -> dict[str, Any]:
    return {"kind": kind, "section": sentence.get("section", ""), "sentence": sentence["text"], "claim": claim, "detail": detail}


def _reading(r: Resolution, clean: str, values: dict[str, Any], keys: dict[str, str]) -> tuple[Optional[Candidate], Optional[tuple[str, Optional[str], str]]]:
    """The candidate a claim is read as, and its identity: the gate's own, unless the words after the figure call it a
    median, high or low and the gate matched a reference level for it too, in its period ("below the 1.11x peer
    median", where a level of the same value was cited first)."""
    identity = _identity(r.best, values, keys)
    if identity and identity[0] == "level" and _CALLED_REFERENCE.match(clean[r.claim.start + len(r.claim.text):]):
        named = next((c for c in r.in_period if (_identity(c, values, keys) or ("",))[0] == "reference"), None)
        if named is not None:
            return named, _identity(named, values, keys)
    return r.best, identity


def _ratio_reference(sentence: dict[str, Any], clean: str, verified: list[Resolution], values: dict[str, Any],
                     keys: dict[str, str]) -> list[dict[str, Any]]:
    """R1: a ratio reference whose metric differs from the nearest ratio level before it. A level whose metric
    cannot be named stops the search; it is never skipped for an earlier one."""
    hits = []
    read = {id(r): _reading(r, clean, values, keys) for r in verified}
    for ref in verified:
        ref_cand, ref_id = read[id(ref)]
        if not ref_id or ref_id[0] != "reference" or ref.claim.unit not in _RATIO_UNITS:
            continue
        before = [r for r in verified if r.claim.unit == ref.claim.unit and r.claim.start < ref.claim.start
                  and (read[id(r)][1] or ("level",))[0] == "level"]
        subject = max(before, key=lambda r: r.claim.start) if before else None
        level_id = read[id(subject)][1] if subject else None
        if subject and level_id and ref_cand is not None and not _same_metric(level_id, ref_id):
            hits.append(_hit("R1", sentence, ref.claim.text, f"a reference level of {ref_id[2]!r} [{ref_cand.ids[0]}] set against "
                                                               f"{subject.claim.text} of {level_id[2]!r}"))
    return hits


def _net_cash_kind(cand: Optional[Candidate], keys: dict[str, str]) -> Optional[str]:
    """"level" or "reference" for a cited net-cash value (the pack's signed basis), else None."""
    if cand is None or cand.how != "cited":
        return None
    prefix, _, base = keys.get(cand.ids[0], "").partition(":")
    if not base and prefix in _NET_CASH_SERIES:
        return "level"
    if base in _NET_CASH_SERIES and prefix in ("median", "high", "low", "peer_median"):
        return "reference"
    return None


def _governing_label(clean: str, resolution: Resolution, verified: list[Resolution], keys: dict[str, str]) -> Optional[str]:
    """"cash" or "debt", the label a net-cash figure is printed under (module docstring, R2a)."""
    claim = resolution.claim
    attached = (_NET_ATTACHED_BEFORE.search(clean[max(0, claim.start - 30):claim.start])
                or _NET_ATTACHED_AFTER.match(clean[claim.start + len(claim.text):]))
    if attached:
        return attached.group(1).lower()
    if _net_cash_kind(resolution.best, keys) == "reference":
        levels = [r for r in verified if _net_cash_kind(r.best, keys) == "level" and r.claim.unit == claim.unit
                  and r.claim.start < claim.start]
        if levels:
            return _governing_label(clean, max(levels, key=lambda r: r.claim.start), verified, keys)
    before = [m.group(1).lower() for m in _NET_LABEL.finditer(clean, 0, claim.start)]
    if before:
        return "cash" if "cash" in before else before[-1]
    after = _NET_LABEL.search(clean, claim.start)
    return after.group(1).lower() if after else None


def _net_debt_sign(sentence: dict[str, Any], clean: str, verified: list[Resolution], keys: dict[str, str]) -> list[dict[str, Any]]:
    """R2a: a figure printed with a minus sign, matched to a net-cash value, under a "net debt" label."""
    return [_hit("R2a", sentence, r.claim.text, f"net cash's minus sign printed under 'net debt' [{r.best.ids[0]}]")
            for r in verified if r.claim.value < 0 and _net_cash_kind(r.best, keys)
            and _governing_label(clean, r, verified, keys) == "debt"]


def _net_cash_comparative(sentence: dict[str, Any], clean: str, verified: list[Resolution], keys: dict[str, str]) -> list[dict[str, Any]]:
    """R2c: "better" / "worse" between a net-cash level and a later net-cash reference that their signed values
    contradict. The word may sit anywhere from the level to the end of the reference's clause."""
    hits = []
    words = list(_COMPARATIVE.finditer(clean))
    for ref in (r for r in verified if words and _net_cash_kind(r.best, keys) == "reference"):
        levels = [r for r in verified if _net_cash_kind(r.best, keys) == "level" and r.claim.unit == ref.claim.unit
                  and r.claim.start < ref.claim.start]
        if not levels:
            continue
        level = max(levels, key=lambda r: r.claim.start)
        end = _STRONG_BREAK.search(clean, ref.claim.start + len(ref.claim.text))
        said = [w for w in words if level.claim.start < w.start() < (end.start() if end else len(clean))]
        better = level.best.value > ref.best.value
        if said and (said[0].group(1).lower() == "better") != better:
            hits.append(_hit("R2c", sentence, ref.claim.text,
                             f"'{said[0].group(1)}' but net cash {level.best.value:.4g} [{level.best.ids[0]}] is "
                             f"{'above' if better else 'below'} {ref.best.value:.4g} [{ref.best.ids[0]}]"))
    return hits


def _cross_year_margins(cand: Candidate, values: dict[str, Any], keys: dict[str, str]) -> bool:
    """A difference of two different margins (levels, not references or changes) of two different years."""
    if not cand.how.startswith(("pp ", "difference ")) or len(cand.ids) != 2 or not all(i in values for i in cand.ids):
        return False
    a, b = (values[i] for i in cand.ids)
    years = [factcheck._periods_of(v) for v in (a, b)]
    levels = all(":" not in keys.get(i, ":") or keys[i].startswith(("cs:", "segmargin:")) for i in cand.ids)
    return (levels and all(v["label"].lower().endswith("margin") for v in (a, b)) and a["label"] != b["label"]
            and all(len(y) == 1 for y in years) and years[0] != years[1])


def _margin_years(sentence: dict[str, Any], verified: list[Resolution], values: dict[str, Any], keys: dict[str, str]) -> list[dict[str, Any]]:
    """R3: every match in the named period(s) is a cross-year difference of two margins."""
    hits = []
    for r in verified:
        if r.claim.unit == "pp" and r.in_period and all(_cross_year_margins(c, values, keys) for c in r.in_period):
            a, b = (values[i] for i in r.best.ids)
            hits.append(_hit("R3", sentence, r.claim.text, f"{a['label']} {a['period']} minus {b['label']} {b['period']}"))
    return hits


def _net_minus_operating(cand: Optional[Candidate], values: dict[str, Any], keys: dict[str, str]) -> Optional[float]:
    """Net margin minus operating margin of one year, when that is what the candidate is: the cited gap (packs-v2's
    ``margin_gap:net_minus_operating``), or the difference of the two margins of the same year, either way round."""
    if cand is None or not all(i in values for i in cand.ids):
        return None
    if len(cand.ids) == 1 and keys.get(cand.ids[0]) == "margin_gap:net_minus_operating" and cand.how in (
            "cited", f"reversed {cand.ids[0]}"):
        return values[cand.ids[0]]["value"]
    if not cand.how.startswith(("pp ", "difference ")) or len(cand.ids) != 2:
        return None
    first, second = (keys.get(i) for i in cand.ids)
    years = [factcheck._periods_of(values[i]) for i in cand.ids]
    if {first, second} != {"net_margin", "operating_margin"} or len(years[0]) != 1 or years[0] != years[1]:
        return None
    gap = values[cand.ids[0]]["value"] - values[cand.ids[1]]["value"]
    return gap if first == "net_margin" else -gap


_MARGIN_NAMES = {"net": re.compile(r"\bnet margin\b", re.I), "operating": re.compile(r"\boperating margin\b", re.I)}
_ABOVE, _BELOW = r"above|over|higher|ahead of|more than", r"below|under|lower|behind|short of|less than"
_GAP_AFTER = re.compile(rf"^\s*(?:({_ABOVE})|({_BELOW}))\b", re.I)
_GAP_VERB = re.compile(r"\b(?:(beat\w*|exceed\w*|outpac\w*|top(?:s|ped|ping)?|outr[au]n\w*)|(trail\w*|lag\w*|(?:fell|falls|fall) short of))\b"
                       r"(?P<between>[^0-9]*?)\bby\s*$", re.I)


def _margin_named(text: str, last: bool = False) -> Optional[str]:
    """"net" or "operating": the margin the text names first (or last)."""
    found = sorted((m.start(), name) for name, pattern in _MARGIN_NAMES.items() for m in pattern.finditer(text))
    return (found[-1] if last else found[0])[1] if found else None


def _gap_direction(sentence: dict[str, Any], clean: str, verified: list[Resolution], values: dict[str, Any],
                   keys: dict[str, str]) -> list[dict[str, Any]]:
    """gap_direction: "<margin> was Npp above / below <margin>" or "<margin> beat / trailed <margin> by Npp" against
    the sign of the same year's net margin minus operating margin. Both margins must be named in the claim's clause,
    one before the comparative and the other after it; anything else is left alone."""
    hits = []
    for r in verified:
        gap = _net_minus_operating(r.best, values, keys) if r.claim.unit == "pp" else None
        if not gap:
            continue
        start, end = factcheck.clause_span(clean, r.claim)
        rest = clean[r.claim.start + len(r.claim.text):end]
        after = _GAP_AFTER.match(rest)
        verb = _GAP_VERB.search(clean[start:r.claim.start])
        if after:
            said, subject, other = (1 if after.group(1) else -1), _margin_named(clean[start:r.claim.start], last=True), \
                _margin_named(rest[after.end():])
        elif verb:
            said, subject, other = (1 if verb.group(1) else -1), _margin_named(clean[start:start + verb.start()], last=True), \
                _margin_named(verb.group("between"))
        else:
            continue
        if subject is None or other is None or subject == other:
            continue
        says = said if subject == "net" else -said
        if (gap > 0) != (says > 0):
            hits.append(_hit("gap_direction", sentence, r.claim.text,
                             f"says net margin is {'above' if says > 0 else 'below'} operating margin; "
                             f"{r.best.how} gives net minus operating = {gap:.4g}"))
    return hits


def _is_fall(cand: Candidate, values: dict[str, Any]) -> bool:
    """A negative CAGR or change: a cited growth, change or CAGR, or one computed from two cited levels."""
    if cand.value >= 0:
        return False
    if cand.how.startswith(("CAGR ", "growth ")):
        return True
    if cand.how != "cited":
        return False
    label = values[cand.ids[0]]["label"]
    return bool(_CHANGE_LABEL.search(label)) and " minus " not in label and "size of loss" not in label


def _unsigned_falls(sentence: dict[str, Any], clean: str, verified: list[Resolution], values: dict[str, Any]) -> list[dict[str, Any]]:
    """U1: a fall printed with no sign, no direction word and no fall word in its scope: its clause, reaching back
    over a colon to the words that introduce a list; or printed with a plus sign. A bound ("below 80%") is not a
    statement of the change."""
    hits = []
    for r in verified:
        claim = r.claim
        if claim.value < 0 or claim.qualifier in ("at_least", "at_most", "multiple"):
            continue
        if not r.in_period or not all(_is_fall(c, values) for c in r.in_period):
            continue
        if clean[max(0, claim.start - 1):claim.start] == "+":
            hits.append(_hit("U1", sentence, claim.text, f"printed with a plus sign; {r.best.how} = {r.best.value:.4g}"))
            continue
        if r.direction is not None:
            continue
        head = [m.end() for m in _LIST_BREAK.finditer(clean, 0, claim.start)]
        tail = _LIST_BREAK.search(clean, claim.start + len(claim.text))
        scope = clean[head[-1] if head else 0:tail.start() if tail else len(clean)]
        if factcheck._UP_WORDS.search(scope) or factcheck._DOWN_WORDS.search(scope) or _FALL_WORDS.search(scope):
            continue
        hits.append(_hit("U1", sentence, claim.text, f"stated without a sign; {r.best.how} = {r.best.value:.4g}"))
    return hits


def _unitless_dollars(sentence: dict[str, Any], verified: list[Resolution]) -> list[dict[str, Any]]:
    """A dollar figure with no scale word whose only matches are a passage's raw, unscaled literals."""
    return [_hit("unitless_dollars", sentence, r.claim.text,
                 f"matches only the raw literal of {r.best.ids[0]}; the filing's tables may be in millions")
            for r in verified if r.claim.unit == "usd" and r.claim.scale == 1.0 and abs(r.claim.value) >= 1
            and r.in_period and all(c.how == f"passage {c.ids[0]}" for c in r.in_period)]


DEBT_LINES = ("debt_noncurrent", "long_term_debt", "debt_current", "short_term_borrowings")  # what total debt sums
# A sentence that says the debt figures rest on a break: the report's disclosure wording, the forms the recorded
# disclosures took ("total debt shows only a $1.0 billion current portion", "equals short-term borrowings alone",
# "long-term debt is untagged after FY2020", "so it is not comparable with FY2023's net debt"), and the data check's
# own words, which the candidate prompt asks to state in the sentence that uses the figure.
DISCLOSURE = re.compile(
    r"\b(?:unreliable|incomplete|overstat\w*|understat\w*|not reported|reported only|only through|no (?:long-term )?debt line|"
    r"missing|omit\w*|drops? out|data (?:gap|break|quality)|debt break|artefact|artifact|last year the pack reports|"
    r"cannot be (?:assessed|compared)|needs? restating|rests? on (?:the |an )?incomplete|(?:that|this|the) break|"
    r"not comparable|untagged|no longer (?:reported|tagged|shown)|not (?:shown|tagged|disclosed|given)|withheld|left out|"
    r"leaves? (?:them |it |those )?out|does(?: not|n't) (?:report|show|include|carry)|not (?:in|part of) (?:the|this) pack|"
    r"unavailable|(?:line|debt) (?:stops|ends)|(?:excludes?|excluding|without) (?:the )?long-term debt|"
    r"(?:borrowings|portion) (?:alone|only)|only (?:a |the )?(?:\$?[\d.,]+ ?(?:billion|million|bn|m) )?(?:current portion|short-term borrowings))\b",
    re.I)
# Debt words a figure can be said under: a total (group 1) or one line of it.
_DEBT_NAME = re.compile(r"\b(?:(net cash|net debt|total debt|total borrowings)|short-term borrowings|current portion|"
                        r"commercial paper|long-term debt|borrowings|notes|debt)\b(?!\s+(?:flows?|provided|used|generated)\b)", re.I)


class Breaks(NamedTuple):
    """The years inside a pack's debt breaks, and the IDs built on them."""
    years: frozenset[str]
    ids: frozenset[str]


def debt_breaks(pack: dict[str, Any], breaks: Optional[list[dict[str, Any]]] = None) -> Breaks:
    """The years ``breaks`` name (the pack's own ``debt_break`` data checks when None) and every ID of ``pack`` built
    on them: total debt and net cash of those years, each value computed from one of them (their share of revenue,
    debt growth across the break, the peer rank), a peer median whose peer rank is one, and a red flag citing one.
    The rule is ``derived.withheld``'s, read from the pack's own inputs, so it gives version 2's withheld IDs on a
    version-2 pack and the same IDs on a version-1 pack given version 2's breaks."""
    checks = pack.get("data_checks", []) if breaks is None else breaks
    years = frozenset(p.strip() for c in checks if c.get("kind") == "debt_break" for p in str(c.get("period", "")).split(",")
                      if p.strip())
    by_key = pack.get("series_keys", {})
    tainted = {vid for year in years for key in ("total_debt", "net_cash") if (vid := by_key.get(f"{key}|{year}"))}
    grew = bool(tainted)
    while grew:
        grew = False
        for vid, value in pack["values"].items():
            if vid not in tainted and tainted.intersection(value.get("inputs") or ()):
                tainted.add(vid)
                grew = True
    for key, vid in by_key.items():
        series, _, period = key.partition("|")
        if series.startswith("peer_median:") and by_key.get(f"peer_pctile:{series.split(':', 1)[1]}|{period}") in tainted:
            tainted.add(vid)
    tainted |= {f["id"] for f in pack.get("red_flags", []) if tainted.intersection(f.get("evidence", []))}
    return Breaks(years, frozenset(tainted))


def _on_break(r: Resolution, clean: str, pack: dict[str, Any], breaks: Breaks, keys: dict[str, str]) -> Optional[str]:
    """Why a verified claim states a debt figure of a broken year, or None."""
    values = pack["values"]
    built = [i for i in r.best.ids if i in breaks.ids] if r.best else []
    if built:
        what = values[built[0]] if built[0] in values else None
        return (f"rests on {built[0]}" + (f" ({what['label']}, {what['period']})" if what else "")
                + ", built on a debt-break year")
    lines = [i for i in r.best.ids if keys.get(i) in DEBT_LINES and values[i].get("period") in breaks.years] if r.best else []
    if not lines:
        return None
    start, _ = factcheck.clause_span(clean, r.claim)
    names = list(_DEBT_NAME.finditer(clean, start, r.claim.start))
    if not names or not names[-1].group(1):
        return None
    return (f"'{names[-1].group(1)}' from {r.best.how}, a debt line of {values[lines[0]]['period']}, inside a debt break, "
            "where total debt omits a line")


def broken_debt_sentence(sentence: dict[str, Any], pack: dict[str, Any], resolved: Optional[list[Resolution]],
                         breaks: Breaks, keys: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
    """broken_debt in one sentence; ``resolved`` is the gate's reading of its claims (computed when absent)."""
    if not breaks.years:
        return []
    clean = CITATION_RE.sub(lambda m: " " * len(m.group(0)), sentence["text"])
    if DISCLOSURE.search(clean):
        return []
    if resolved is None:
        resolved = factcheck.analyse_sentence(sentence, pack)[1]
    keys = series_by_id(pack) if keys is None else keys
    hits = []
    for r in sorted((r for r in resolved if r.status == "verified" and r.best is not None), key=lambda r: r.claim.start):
        reason = _on_break(r, clean, pack, breaks, keys)
        if reason:
            hits.append(_hit("broken_debt", sentence, r.claim.text, reason))
    return hits


def broken_debt(sentences: list[dict[str, Any]], pack: dict[str, Any],
                breaks: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    """broken_debt over an analysis: total debt, net cash or net debt (or a figure built on them) stated for a year
    inside a debt break without saying so (module docstring). ``breaks`` are ``debt_break`` data checks, the pack's
    own when None; a measure passes version 2's for every arm, version-1 packs included."""
    found = debt_breaks(pack, breaks)
    keys = series_by_id(pack)
    return [hit for sentence in sentences for hit in broken_debt_sentence(sentence, pack, None, found, keys)]


def _printed(r: Resolution) -> float:
    return r.claim.value * r.claim.scale


def _moved_to(sentence: dict[str, Any], clean: str, verified: list[Resolution], pack: dict[str, Any], keys: dict[str, str]) -> list[dict[str, Any]]:
    """logic_direction: "rose to X" / "fell to X" against the figure it moved from, else the year before's value."""
    hits = []
    for i, r in enumerate(verified):
        moved = _MOVED_TO.search(clean[max(0, r.claim.start - 30):r.claim.start])
        if not moved:
            continue
        start = next((o for o in verified[i + 1:i + 2] if o.claim.unit == r.claim.unit
                      and _FROM.search(clean[r.claim.start + len(r.claim.text):o.claim.start])), None)
        if start is not None:
            now, then, what = _printed(r), _printed(start), f"from {start.claim.text}"
        else:
            prior = _prior(pack, keys, r.best.ids[0]) if r.best.how == "cited" else None
            if prior is None:
                continue
            now, then = pack["values"][r.best.ids[0]]["value"], prior["value"]
            if r.claim.value >= 0 and now < 0:  # "investing outflow rose to $52.2 billion": a magnitude
                now, then = abs(now), abs(then)
            what = f"{prior['period']} was {prior['value']:.6g}"
        if now != then and (now > then) != bool(moved.group(1)):
            hits.append(_hit("logic_direction", sentence, r.claim.text, f"says it {moved.group(1) or moved.group(2)}; {what}"))
    return hits


def _from_to(sentence: dict[str, Any], clean: str, verified: list[Resolution], values: dict[str, Any], keys: dict[str, str]) -> list[dict[str, Any]]:
    """logic_from_order: "from A to B" running from the later year of one series, or against its rise or fall word."""
    hits = []
    for a, b in zip(verified, verified[1:]):
        if " ".join(clean[a.claim.start + len(a.claim.text):b.claim.start].split()) != "to" or not _FROM.search(clean[:a.claim.start]):
            continue
        same = a.best.how == b.best.how == "cited" and keys.get(a.best.ids[0]) is not None and keys.get(a.best.ids[0]) == keys.get(b.best.ids[0])
        ya, yb = (factcheck._periods_of(values[r.best.ids[0]]) if r.best.how == "cited" else () for r in (a, b))
        moved = _MOVED_FROM.search(clean[max(0, a.claim.start - 30):a.claim.start])
        if same and len(ya) == len(yb) == 1 and ya[0] > yb[0]:
            hits.append(_hit("logic_from_order", sentence, a.claim.text, f"'from' the later year FY{ya[0]} to FY{yb[0]}"))
        elif moved and a.claim.unit == b.claim.unit and _printed(a) != _printed(b) and (_printed(b) > _printed(a)) != bool(moved.group(1)):
            hits.append(_hit("logic_from_order", sentence, a.claim.text, f"'{moved.group(1) or moved.group(2)}' from {a.claim.text} to {b.claim.text}"))
    return hits


def _recover(sentence: dict[str, Any], clean: str, verified: list[Resolution], values: dict[str, Any]) -> list[dict[str, Any]]:
    """logic_recover: "recover toward A from B" where A is the worse of the two levels."""
    hits = []
    for i, r in enumerate(verified):
        if not _RECOVER.search(clean[max(0, r.claim.start - 60):r.claim.start]):
            continue
        start = next((o for o in verified[i + 1:] if o.claim.unit == r.claim.unit
                      and _FROM.search(clean[max(0, o.claim.start - 12):o.claim.start])), None)
        if start is None:
            continue
        lower_better = start.best.how == "cited" and factcheck.lower_is_better(start.best, values)
        if (_printed(r) > _printed(start)) if lower_better else (_printed(r) < _printed(start)):
            hits.append(_hit("logic_recover", sentence, r.claim.text, f"'recover' toward {r.claim.text} from {start.claim.text}, the worse level"))
    return hits


def probe_sentence(sentence: dict[str, Any], pack: dict[str, Any], resolved: Optional[list[Resolution]] = None,
                   keys: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
    """Every probe hit in one sentence but ``broken_debt`` (``broken_debt_sentence``). ``resolved`` is the gate's
    reading of its claims (computed when absent)."""
    if resolved is None:
        resolved = factcheck.analyse_sentence(sentence, pack)[1]
    keys = series_by_id(pack) if keys is None else keys
    values = pack["values"]
    clean = CITATION_RE.sub(lambda m: " " * len(m.group(0)), sentence["text"])
    verified = sorted((r for r in resolved if r.status == "verified" and r.best is not None), key=lambda r: r.claim.start)
    return (_ratio_reference(sentence, clean, verified, values, keys) + _net_debt_sign(sentence, clean, verified, keys)
            + _net_cash_comparative(sentence, clean, verified, keys) + _margin_years(sentence, verified, values, keys)
            + _gap_direction(sentence, clean, verified, values, keys)
            + _unsigned_falls(sentence, clean, verified, values) + _unitless_dollars(sentence, verified)
            + _moved_to(sentence, clean, verified, pack, keys) + _from_to(sentence, clean, verified, values, keys)
            + _recover(sentence, clean, verified, values))


def probe(sentences: list[dict[str, Any]], pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Every probe hit in an analysis, gate kinds and measures alike, in sentence order; ``broken_debt`` is its own
    function."""
    keys = series_by_id(pack)
    return [hit for sentence in sentences for hit in probe_sentence(sentence, pack, keys=keys)]
