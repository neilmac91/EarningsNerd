"""Replay every recorded output through the gate as it was and as it is, with and without the backstop probes.

    cd backend && python -m evals.trend_depth.replay
    cd backend && python -m evals.trend_depth.replay --base b3ed8ef --labels eval-v1,dev-v3,dev-v4,plant-sem

Calls no model. The base gate is ``factcheck.py`` as committed at ``--base`` (read with ``git show`` into a
temporary module), so the comparison needs no frozen copy in the tree. Every first pass and every final output
of every system in ``runs/<label>/`` is checked against the pack that system reads (``packs-v2/`` for the ``-p``
and ``-c`` arms), and so are the gold examples (``gold.py``); ``current`` keeps no sentences and is skipped. A
version-2 record's first pass is the model's own first output (``report.first_output``), before the code's
retyping (and, in a record made before fix 1 was removed, its auto-citation). A version-2 run decides with the gate
now and ``backstops=True``, a version-1 run made today with the gate now alone, and eval-v1 decided with the base
gate. Printed:

1. Every sentence whose result flips between the base gate and the gate now, either way, with its failures.
2. The same between the gate now and the gate now with ``backstops=True``.
3. Analyses passing under each gate, per run and system, first pass and final (an analysis with no repair
   counts its one output as both).
4. The planted errors of ``plant-sem``: each sentence that differs from the output it was planted into
   (``--plant-source``), and whether each gate fails it. The relabels were planted for the semantic audit; a
   gate that never caught them is expected to pass them.
5. Probe hits per run, system and kind (``probes.py``), in final outputs and in first passes; ``broken_debt`` reads
   the breaks the pack itself records (debt, liquidity and a peer's broken year), as the gate does, so it is silent
   on version-1 packs; the report's broken-net-cash measure reads version 2's for every arm.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, Optional

from evals.trend_depth import bootstrap, factcheck, gold, probes
from evals.trend_depth.generate import RUNS, load_pack, sentences_of
from evals.trend_depth.providers import packs_dir
from evals.trend_depth.report import first_output

LABELS = ("eval-v1", "dev-v3", "dev-v4", "plant-sem")
SKIP = ("judge", "causes", "semantics")  # audit and verdict folders beside the systems


def base_gate(commit: str) -> ModuleType:
    """``factcheck.py`` as committed at ``commit``, imported from a temporary file."""
    source = subprocess.run(["git", "show", f"{commit}:backend/evals/trend_depth/factcheck.py"], cwd=bootstrap.REPO,
                            check=True, capture_output=True, text=True).stdout
    with tempfile.TemporaryDirectory(prefix="trend-depth-gate-") as folder:
        path = Path(folder) / f"factcheck_{commit}.py"
        path.write_text(source)
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module  # its dataclasses resolve their annotations through sys.modules
        spec.loader.exec_module(module)
    return module


def _first_pass(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The model's first output when it differs from the final one: a repaired version-1 record's first pass, or a
    version-2 record's own first reply (its recorded first pass already carries the code's retyping); None otherwise."""
    if record.get("pipeline") == "v2":
        first = first_output(record)
        return first if first is not None and first != record["output"] else None
    first = record.get("first_pass_output")
    return first if isinstance(first, dict) else None


def records(labels: list[str]) -> Iterator[tuple[str, str, str, dict[str, Any], list[dict[str, Any]], Optional[list[dict[str, Any]]]]]:
    """(label, system, ticker, pack, final sentences, first-pass sentences or None when the first pass is the final
    output) for every recorded output, each against the pack its system reads, then the gold examples."""
    packs: dict[tuple[str, str], dict[str, Any]] = {}
    for label in labels:
        for folder in sorted(p for p in (RUNS / label).iterdir() if p.is_dir() and not p.name.startswith(SKIP)):
            for path in sorted(folder.glob("*.json")):
                record = json.loads(path.read_text())
                if not isinstance(record.get("output"), dict):
                    continue
                key = (packs_dir(folder.name, bootstrap.RECORDS).name, record["ticker"])
                if key not in packs:
                    packs[key] = load_pack(record["ticker"], folder.name)
                pack = packs[key]
                first = _first_pass(record)
                yield (label, folder.name, record["ticker"], pack, sentences_of(record["output"]),
                       sentences_of(first) if first is not None else None)
    for path in sorted(gold.GOLD.glob("*.md")):
        if (bootstrap.RECORDS / "packs" / f"{path.stem}.json.gz").exists():
            yield "gold", "gold", path.stem, gold.pack_with_extras(path.stem), factcheck.sentences_from_markdown(path.read_text()), None


def _by_sentence(gate: dict[str, Any]) -> dict[str, list[str]]:
    failed: dict[str, list[str]] = defaultdict(list)
    for failure in gate["failures"]:
        failed[failure["sentence"]].append(failure["failure"])
    return failed


def flips(before: dict[str, Any], after: dict[str, Any], sentences: list[dict[str, Any]]) -> list[str]:
    """One line block per sentence whose pass or fail changed, or whose failures changed while it still fails."""
    old, new = _by_sentence(before), _by_sentence(after)
    lines = []
    for text in dict.fromkeys(s["text"] for s in sentences):
        was, now = old.get(text, []), new.get(text, [])
        if bool(was) != bool(now) or (was and sorted(was) != sorted(now)):
            arrow = "FAIL -> pass" if was and not now else "pass -> FAIL" if now and not was else "FAIL -> FAIL (changed)"
            lines.append(f"    {arrow}: {text}")
            lines += [f"        was: {f}" for f in was] + [f"        now: {f}" for f in now]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="b3ed8ef", help="the commit whose gate is the baseline")
    parser.add_argument("--labels", default=",".join(LABELS))
    parser.add_argument("--plant-label", default="plant-sem")
    parser.add_argument("--plant-source", default="dev-v4", help="the run the plant-sem outputs were planted into")
    args = parser.parse_args()
    old_gate = base_gate(args.base)
    sections: dict[str, list[str]] = {"base": [], "backstops": []}
    passing: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    hits: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    plants: list[str] = []
    replayed = 0
    for label, system, ticker, pack, final, first in records(args.labels.split(",")):
        replayed += 1
        checked: dict[str, dict[str, dict[str, Any]]] = {}
        for which, sentences in (("final", final), ("first", first)):
            if sentences is None:  # no repair: the first pass is the final output
                checked["first"] = checked["final"]
                continue
            results = checked[which] = {"base": old_gate.check(sentences, pack), "now": factcheck.check(sentences, pack),
                                        "backstops": factcheck.check(sentences, pack, backstops=True)}
            name = f"  {label} {system} {ticker} {which}"
            for section, (a, b) in (("base", ("base", "now")), ("backstops", ("now", "backstops"))):
                changed = flips(results[a], results[b], sentences)
                if changed:
                    sections[section] += [f"{name}: {'pass' if results[a]['passed'] else 'FAIL'} -> "
                                          f"{'pass' if results[b]['passed'] else 'FAIL'}", *changed]
            for hit in probes.probe(sentences, pack) + probes.broken_debt(sentences, pack):
                hits[(label, system, which)][hit["kind"]] += 1
                if first is None:
                    hits[(label, system, "first")][hit["kind"]] += 1
        for which, results in checked.items():
            tally = passing[(label, system, which)]
            tally["outputs"] += 1
            tally.update(gate for gate, result in results.items() if result["passed"])
        if label == args.plant_label:
            source = RUNS / args.plant_source / system / f"{ticker}.json"
            original = {s["text"] for s in sentences_of(json.loads(source.read_text())["output"])} if source.exists() else set()
            for sentence in (s for s in final if s["text"] not in original):
                verdicts = {gate: sentence["text"] in _by_sentence(result) for gate, result in checked["final"].items()}
                plants.append(f"  {system} {ticker}: " + ", ".join(f"{g} {'caught' if v else 'passed'}" for g, v in verdicts.items())
                              + f"\n    {sentence['text']}")
    print(f"Replayed {replayed} analyses (each final output, and its first pass when it was repaired) from {args.labels} and the gold examples.\n")
    print(f"1. Gate at {args.base} -> gate now: every sentence that flips\n")
    print("\n".join(sections["base"]) or "  none")
    print("\n2. Gate now -> gate now with backstops: every sentence that flips\n")
    print("\n".join(sections["backstops"]) or "  none")
    print("\n3. Analyses passing (base / now / now with backstops)\n")
    for (label, system, which), tally in sorted(passing.items()):
        print(f"  {label:9} {system:22} {which:5} {tally['base']:>2} / {tally['now']:>2} / {tally['backstops']:>2} of {tally['outputs']}")
    print(f"\n4. Planted sentences in {args.plant_label} (against {args.plant_source})\n")
    print("\n".join(plants) or "  none found")
    kinds = probes.GATE_KINDS + probes.MEASURE_KINDS
    print("\n5. Probe hits per run and system, claims in final outputs / in first passes\n")
    print("  " + f"{'run':9} {'system':22}" + "".join(f"{k:>18}" for k in kinds))
    for label, system in sorted({(label, system) for label, system, _ in hits}):
        in_final, in_first = hits[(label, system, "final")], hits[(label, system, "first")]
        print("  " + f"{label:9} {system:22}" + "".join(f"{f'{in_final[k]} / {in_first[k]}':>18}" for k in kinds))


if __name__ == "__main__":
    main()
