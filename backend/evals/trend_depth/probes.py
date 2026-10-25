"""Backstop probes: verified numbers said about the wrong thing (DEEPSEEK-ERRORS.md fix 12).

The gate (``factcheck.py``) proves that each number matches a value its sentence cites. It cannot see that the
matched value was said about another metric, basis, year or sign. These probes read the gate's own resolution
of every claim (``factcheck.analyse_sentence``) and look for the shapes those errors took in the recorded
outputs:

- ``R1``: a reference level (window median, high or low, peer median or percentile) of another ratio set against
  this ratio: "operating cash flow was 2.76x net income, above the 1.10x window median" of free cash flow. The
  ratio is the nearest ``x`` level before the reference; margins and shares are left out, because a sentence that
  names two of them ("whose medians are 25.7% operating and 16.3% net") labels each reference in words.
- ``R2a``: a minus sign under "net debt" ("Net debt has deepened from -$50.0 billion to -$89.6 billion"). The
  pack's net cash is negative for an indebted company. A figure's label is the one attached to it ("net cash of
  -$34.3 billion", "-3.5% net cash"), else the sentence's subject, so net cash's own sign under its own name
  never fires ("Net cash has fallen into deeper net debt, from -$76.2 billion").
- ``R2c``: "better" or "worse" between a company's net cash and a reference level of net cash, between or after
  the two numbers, that the signed values contradict ("Net debt is 38.8% of revenue, better than the -35.6%
  peer median": -38.8 is below -35.6).
- ``R3``: a difference of two different margins taken from two different years ("net margin 6.5pp under
  operating margin" from FY2025's net margin and FY2024's operating margin), when nothing else explains it.
- ``U1``: an unsigned fall: a CAGR or change printed with no sign whose value is negative, with no direction or
  fall word in its clause, nor in the words before a colon that introduce a list ("the three years to FY2025
  show a 5.3% CAGR" for -5.3%; not "Revenue declined three years running: 16.5% ...").
- ``unitless_dollars``: a dollar figure with no scale matched only to a passage's raw literal ("currency moves
  added $126 of expense" from a 10-K whose tables are in millions).

``factcheck.check(..., backstops=True)`` turns these (``GATE_KINDS``) into failures. Three logic checks are
measures only, never failures (``MEASURE_KINDS``); they were written after reading DeepSeek's eval-v1 outputs:

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
from typing import Any, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.factcheck import CITATION_RE, Candidate, Resolution

GATE_KINDS = ("R1", "R2a", "R2c", "R3", "U1", "unitless_dollars")
MEASURE_KINDS = ("logic_direction", "logic_from_order", "logic_recover")

_RATIO_UNITS = ("x",)  # R1's ratios; a margin's or share's reference is usually named in words (module docstring)
_REFERENCE_PREFIXES = ("median", "high", "low", "peer_median", "peer_pctile")
_REFERENCE_LABEL = re.compile(r"(?: window (?:median|high|low)(?: \(FY\d{4}\))?|: .+ peer median \(n=\d+\)|: percentile vs .+)$", re.I)
_NET_CASH_SERIES = ("net_cash", "net_cash_to_revenue")
_NET_ATTACHED_BEFORE = re.compile(r"\bnet (cash|debt)(?: position)?(?: of| at| was| is| to| reached)?\s*$", re.I)
_NET_ATTACHED_AFTER = re.compile(r"^\s*(?:of\s+)?net (cash|debt)\b", re.I)
_NET_LABEL = re.compile(r"\bnet (cash|debt)\b", re.I)
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


def _ratio_reference(sentence: dict[str, Any], verified: list[Resolution], values: dict[str, Any], keys: dict[str, str]) -> list[dict[str, Any]]:
    """R1: a ratio reference whose metric differs from the nearest ratio level before it. A level whose metric
    cannot be named stops the search; it is never skipped for an earlier one."""
    hits = []
    for ref in verified:
        ref_id = _identity(ref.best, values, keys)
        if not ref_id or ref_id[0] != "reference" or ref.claim.unit not in _RATIO_UNITS:
            continue
        before = [r for r in verified if r.claim.unit == ref.claim.unit and r.claim.start < ref.claim.start
                  and (_identity(r.best, values, keys) or ("level",))[0] == "level"]
        subject = max(before, key=lambda r: r.claim.start) if before else None
        level_id = _identity(subject.best, values, keys) if subject else None
        if subject and level_id and not _same_metric(level_id, ref_id):
            hits.append(_hit("R1", sentence, ref.claim.text, f"a reference level of {ref_id[2]!r} [{ref.best.ids[0]}] set against "
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


def _governing_label(clean: str, resolution: Resolution) -> Optional[str]:
    """"cash" or "debt": the net-cash or net-debt label attached to the figure, else the sentence's subject."""
    claim = resolution.claim
    attached = (_NET_ATTACHED_BEFORE.search(clean[max(0, claim.start - 30):claim.start])
                or _NET_ATTACHED_AFTER.match(clean[claim.start + len(claim.text):]))
    if attached:
        return attached.group(1).lower()
    first = _NET_LABEL.search(clean)
    return first.group(1).lower() if first else None


def _net_debt_sign(sentence: dict[str, Any], clean: str, verified: list[Resolution], keys: dict[str, str]) -> list[dict[str, Any]]:
    """R2a: a figure printed with a minus sign, matched to a net-cash value, under a "net debt" label."""
    return [_hit("R2a", sentence, r.claim.text, f"net cash's minus sign printed under 'net debt' [{r.best.ids[0]}]")
            for r in verified if r.claim.value < 0 and _net_cash_kind(r.best, keys) and _governing_label(clean, r) == "debt"]


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
    over a colon to the words that introduce a list. A bound ("below 80%") is not a statement of the change."""
    hits = []
    for r in verified:
        claim = r.claim
        if claim.value < 0 or r.direction is not None or claim.qualifier in ("at_least", "at_most", "multiple"):
            continue
        if clean[max(0, claim.start - 1):claim.start] == "+" or not r.in_period or not all(_is_fall(c, values) for c in r.in_period):
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
    """Every probe hit in one sentence. ``resolved`` is the gate's reading of its claims (computed when absent)."""
    if resolved is None:
        resolved = factcheck.analyse_sentence(sentence, pack)[1]
    keys = series_by_id(pack) if keys is None else keys
    values = pack["values"]
    clean = CITATION_RE.sub(lambda m: " " * len(m.group(0)), sentence["text"])
    verified = sorted((r for r in resolved if r.status == "verified" and r.best is not None), key=lambda r: r.claim.start)
    return (_ratio_reference(sentence, verified, values, keys) + _net_debt_sign(sentence, clean, verified, keys)
            + _net_cash_comparative(sentence, clean, verified, keys) + _margin_years(sentence, verified, values, keys)
            + _unsigned_falls(sentence, clean, verified, values) + _unitless_dollars(sentence, verified)
            + _moved_to(sentence, clean, verified, pack, keys) + _from_to(sentence, clean, verified, values, keys)
            + _recover(sentence, clean, verified, values))


def probe(sentences: list[dict[str, Any]], pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Every probe hit in an analysis, gate kinds and measures alike, in sentence order."""
    keys = series_by_id(pack)
    return [hit for sentence in sentences for hit in probe_sentence(sentence, pack, keys=keys)]
