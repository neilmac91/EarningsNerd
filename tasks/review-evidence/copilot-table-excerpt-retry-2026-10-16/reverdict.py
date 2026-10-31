"""Compare main's and the change's citation verdicts on every retained generation (offline).

Inputs are two classify_corpus.py outputs over the same reports, one produced with main's code and one
with the change. A generation's verdict is publish-at-this-check ("ok") or a withhold ("regenerable",
"terminal"); answer_filing_question regenerates only after a FIRST generation, so a verdict change on a
retry generation cannot change what the service does. Prints the transition table and exits non-zero
if any generation moves between publish and withhold or any verdict moves other than terminal ->
regenerable.

Usage: python -I reverdict.py <main.jsonl> <change.jsonl>
"""
from __future__ import annotations

import json
import sys
from collections import Counter


def key(rec: dict) -> tuple:
    return (rec["report"], rec["timestamp"], rec["ticker"], rec["accession"], rec["question_id"],
            rec["run_index"], rec["gen_index"])


def verdict(rec: dict) -> str:
    return rec.get("verify") or rec.get("stage") or rec.get("mode")


main = {key(r): r for r in map(json.loads, open(sys.argv[1]))}
change = {key(r): r for r in map(json.loads, open(sys.argv[2]))}
assert main.keys() == change.keys(), "the two classifications cover different generations"

transitions = Counter()
first_gen_gains_retry = []
bad = []
for k, before in main.items():
    after = change[k]
    a, b = verdict(before), verdict(after)
    transitions[(a, b, "first" if k[-1] == 0 else "retry")] += 1
    if a != b:
        if (a, b) != ("terminal", "regenerable"):
            bad.append((k, a, b))
        elif k[-1] == 0:
            first_gen_gains_retry.append((before["ticker"], before["timestamp"][:10], before["run_index"],
                                          "+".join(before["failing_reasons"])))
    if a == "ok" and before.get("per_ref") != after.get("per_ref"):
        bad.append((k, "published payload changed", ""))

print(f"generations compared: {len(main)}")
for (a, b, gen), n in sorted(transitions.items()):
    print(f"  {gen:5s} {a:12s} -> {b:12s} {n:5d}")
print(f"first generations that newly earn the one regeneration: {len(first_gen_gains_retry)}")
for row in sorted(first_gen_gains_retry, key=lambda r: r[1]):
    print("   ", *row)
print(f"forbidden transitions: {len(bad)}")
for row in bad[:20]:
    print("   ", row)
sys.exit(1 if bad else 0)
