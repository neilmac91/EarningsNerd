"""The code the version-2 repair loop runs on a first pass before the gate decides on a repair: fix 5's retyping
(DEEPSEEK-ERRORS.md), and the code-only replay of recorded first passes through it.

    cd backend && python -m evals.trend_depth.retype                    # eval-v1's and dev-v4's DeepSeek first passes
    cd backend && python -m evals.trend_depth.retype --labels eval-v1 --system deepseek-flash

**Retyping** (``retype``). A ``cause`` sentence that cites no passage, opens no explanatory clause ("because", "so",
"as", "due to": ``explanatory``) and says nothing beyond its figures (every word is a figure, a year, a word of a
cited value's label or of a cited flag's detail, or figure talk such as "offset", "consumed", "flat") is a margin
bridge or a capital-return sentence mistyped. It becomes a ``comparison``. ``first_pass`` is the whole code step: the
retyping, then the gate with its backstops on what it leaves. ``generate.fix_first_pass`` records it, and
``real_failures`` replays the model's own first outputs (``records.first_output``; a version-2 record's
``first_pass_output`` already carries the retyping) through the same function, so the replay decides as a run would.

**No auto-citation.** Fix 1 appended a figure's missing own ID by code; it was removed. Reviews 6, 7 and 8 each found
a new class of wrong number its rules licensed (a wrong year, metric, threshold, sign, from-level or base year), while
over all 187 recorded outputs it appended 3 IDs and turned none of the 25 recorded DeepSeek first passes of eval-v1
and dev-v4 from failing to passing. The patch repair that fixes the same omission costs about $0.0005 and 1-3 s by
DEEPSEEK-ERRORS.md §2's estimate (§3 step 1 measures it). An omitted own ID is a gate failure ("matches nothing the
sentence cites") that the repair fixes and the report counts among the first-try gate errors. A record made before
the removal carries ``autocite``: another build (``records.pipeline_of``).

Pure: imports neither the bootstrap nor ``generate``; the command reads records and packs from disk.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterator, Optional

from evals.trend_depth import factcheck
from evals.trend_depth.factcheck import CITATION_RE, ID_RE, Claim
from evals.trend_depth.providers import packs_dir
from evals.trend_depth.records import first_output

RECORDS = Path(__file__).resolve().parents[3] / "tasks" / "analysis-depth-2026-10"
SKIP = ("judge", "causes", "semantics")  # audit and verdict folders beside the systems

_TOKEN = re.compile(r"[a-z0-9&]*[a-z][a-z0-9&]*")

# "because", "so", "as", "due to": the clause after one explains, and needs the passage that states the cause.
_CONNECTIVE = re.compile(r"\b(because|due to|so|as)\b", re.I)
_AS_NOT_CAUSAL_AFTER = re.compile(
    r"^\s*(?:a (?:share|percent(?:age)?|proportion|multiple) of\b|reported\b|of\b|well as\b|"
    r"(?:much|many|high|low|large|long|far|little|soon) as\b)", re.I)
_AS_NOT_CAUSAL_BEFORE = re.compile(r"\b(?:such|same|as (?:much|many|high|low|large|long|far|little|well|soon))\s*$", re.I)
_SO_NOT_CAUSAL_AFTER = re.compile(r"^\s*(?:far|much|many)\b", re.I)

# Words a sentence about figures uses without explaining them: directions, bridges, capital returns, references,
# scale and function words. A word outside this list and outside the cited labels is a claim beyond the figures. The
# last line holds the words of a product's contribution to growth with no passage (dev-v5: C's REGN "The FY2021 surge
# came from REGEN-COV, which contributed 66.4pp", and five more REGEN-COV sentences on record); "lift" stays out, as
# "lifting" in REGN's wrong days-sales-outstanding sentence says more than its figures.
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
spike surge reversal collapse collapsed collapsing zero disappearance whose s sale
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


def _located(output: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """(section key, sentence) for every sentence of an output, in order; the sentence is the output's own dict."""
    for section in output.get("sections", []):
        if not isinstance(section, dict):
            continue
        for sentence in section.get("sentences", []):
            if isinstance(sentence, dict) and isinstance(sentence.get("text"), str):
                yield section.get("key", ""), sentence


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


def _sentences(output: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"section": key, "text": s["text"], "type": s.get("type", "")} for key, s in _located(output)]


def first_pass(output: dict[str, Any], pack: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Version 2's code before any repair, on a first pass: a copy of ``output`` retyped (``retype``), the retypes, and
    the gate's verdict with its backstops on it, which decides the repair. ``output`` is not changed."""
    fixed, retyped = retype(output, pack)
    return fixed, retyped, factcheck.check(_sentences(fixed), pack, backstops=True)


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


def real_failures(records: Path, labels: list[str], system: str) -> list[str]:
    """Each first pass of ``system`` that fails the gate or its backstops, through version 2's code (``first_pass``):
    what was retyped, and what remains; then how many first passes would still go to a repair, by the gate with its
    backstops (as a run decides) and by the gate alone.

    A first pass is the model's own first output (``records.first_output``): a version-1 record's
    ``first_pass_output`` (its ``output`` when no repair ran), and a version-2 record's first valid reply, read from its
    attempts, as its ``first_pass_output`` and its unrepaired ``output`` are the copy the code already retyped. Read
    from them, a first pass that passed only after retyping would not count as failing, and its retypes would not be
    listed (review 9, repair-loop [0])."""
    lines, tally = [], Counter()
    for name, record, pack in recorded(records, labels, [system]):
        first = first_output(record)
        tally["first passes"] += 1
        if first is None:
            tally["first passes with no readable reply"] += 1
            lines.append(f"{name}: no first reply parses, so nothing is replayed")
            continue
        before = factcheck.check(_sentences(first), pack, backstops=True)
        if before["passed"]:
            continue
        _, retyped, after = first_pass(first, pack)
        plain = [f for f in after["failures"] if not f["failure"].startswith("backstop ")]
        tally.update({"failing": 1, "failing after retyping": not after["passed"],
                      "failing the gate alone": any(not f["failure"].startswith("backstop ") for f in before["failures"]),
                      "failing the gate alone after retyping": bool(plain)})
        lines.append(f"{name}: {len(before['failures'])} failure(s) -> {len(after['failures'])} ({len(plain)} of the gate itself)")
        lines += [f"    was: {f['failure']} | {f['sentence']}" for f in before["failures"]]
        lines += [f"    retyped: {r['sentence']}" for r in retyped]
        lines += [f"    still: {f['failure']} | {f['sentence']}" for f in after["failures"]]
    lines.append("  " + "; ".join(f"{key}: {count}" for key, count in tally.items()))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--labels", default="eval-v1,dev-v4", help="runs whose first passes are replayed, each on its own")
    parser.add_argument("--system", default="deepseek-flash", help="the system whose first passes are replayed")
    args = parser.parse_args()
    for label in args.labels.split(","):
        print(f"{args.system}'s failing first passes in {label}, through retyping\n")
        print("\n".join(real_failures(RECORDS, [label], args.system)) + "\n")


if __name__ == "__main__":
    main()
