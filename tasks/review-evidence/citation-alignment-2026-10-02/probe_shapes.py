"""Shape probes + differential fuzz: main's CITATION scorer vs this branch's scorer vs Copilot publication.

Read-only, no network, no provider calls. Uses the same columns as ``replay_scorer_alignment.py``
(``old`` = main 06ad809a's scorer, ``new`` = this branch's scorer, ``product`` = this branch's
``_verify_citations``). Usage (keys unset):
    env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL python probe_shapes.py <out.json>
"""
from __future__ import annotations

import json
import os
import random
import sys

sys.dont_write_bytecode = True  # no __pycache__ beside the evidence
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from replay_scorer_alignment import prov, verdicts  # noqa: E402

RAW = ("For the fiscal year ending January 31, 2027 (“fiscal 2027”), we project capital expenditures will be "
       "approximately $25 billion to $27 billion. Revenue increased to $391.0 billion in fiscal 2024. "
       "“Supply chain” constraints persisted through “Q3”. Item 1A — Risk Factors: the Company’s results "
       "may fluctuate. Total net sales 416,161 391,035 383,285")
NORM = prov.normalize_for_match(RAW)
VERBATIM = "Revenue increased to $391.0 billion in fiscal 2024."

SHAPES = [
    ("fiscal-2027 inner short quoted span",
     'For the fiscal year ending January 31, 2027 ("fiscal 2027"), we project capital expenditures', "Item 7"),
    ("straight single-quote wrapped", f"'{VERBATIM}'", "Item 7"),
    ("curly single-quote wrapped", f"‘{VERBATIM}’", "Item 7"),
    ("mixed wrapper open \" close '", f"\"{VERBATIM}'", "Item 7"),
    ("double-quote wrapped (control)", f'"{VERBATIM}"', "Item 7"),
    ("outer wrap + interior quotes, all in source", '"Supply chain" constraints persisted through "Q3"', "Item 1A"),
    ("#1052 shape: invented prefix + real quoted span", f'We said "{VERBATIM}"', "Item 7"),
    ("invented suffix after real quoted span", f'"{VERBATIM}" Margins doubled.', "Item 7"),
    ("plain verbatim with whitespace drift", "Total net sales 416,161 391,035 383,285", "Item 8"),
    ("23-char needle inside wrapper (floor)", '"increased to $391.0 bil"', "Item 7"),
    *((f"verbatim excerpt, label with U+{ord(m):04X}", VERBATIM, f"Item 7 {m}MD&A{m}") for m in '"＂“”„‟'),
    *((f"verbatim excerpt, label with U+{ord(m):04X} (F's decided limit)", VERBATIM, f"Item 7 {m}MD&A{m}")
      for m in "‘«″"),
    ("verbatim excerpt, label with &quot; (displayed literally)", VERBATIM, "Item 7 &quot;MD&A&quot;"),
]


def fuzz(n=200_000, seed=1052):
    """New scorer vs product admission over generated excerpts (source substrings, invented text, quote
    wrappers, inner quote pairs, whitespace) and generated labels (every F mark and some that are not)."""
    rng = random.Random(seed)
    marks = ['"', "'", "“", "”", "‘", "’", ""]
    junk = ["We said ", "Margins doubled. ", "  ", "\n", "the ", "(", ")", " - ", "…", ""]
    labels = ["Item 7", "Item 1A — Risk Factors", "Item 7 — Management’s Discussion", None, "",
              *(f"Item 7 {m}MD&A" for m in '"＂“”„‟‘’«»″\'')]
    mismatches = []
    old_false_new_true = old_true_new_false = 0
    for _ in range(n):
        a = rng.randrange(len(RAW))
        b = min(len(RAW), a + rng.randrange(5, 90))
        core = RAW[a:b]
        if rng.random() < 0.3:
            i = rng.randrange(len(core) + 1)
            j = rng.randrange(i, len(core) + 1)
            core = core[:i] + rng.choice(['"', "“", "”"]) + core[i:j] + rng.choice(['"', "“", "”"]) + core[j:]
        if rng.random() < 0.3:
            core = rng.choice(junk) + core + rng.choice(junk)
        ex = rng.choice(marks) + core + rng.choice(marks)
        if rng.random() < 0.2:
            ex = rng.choice([" ", "\t", "\n"]) + ex + rng.choice([" ", ""])
        r = verdicts(ex, rng.choice(labels), NORM)
        if r["new"] != r["product"]:
            mismatches.append(ex)
        old_false_new_true += (not r["old"]) and r["new"]
        old_true_new_false += r["old"] and not r["new"]
    return {"cases": n, "seed": seed, "new_vs_product_mismatches": len(mismatches),
            "mismatch_examples": mismatches[:5], "old_false_new_true": old_false_new_true,
            "old_true_new_false": old_true_new_false}


if __name__ == "__main__":
    shapes = [{"shape": name, "excerpt": ex, "section": sec, **verdicts(ex, sec, NORM)} for name, ex, sec in SHAPES]
    result = {"normalized_source": NORM, "shapes": shapes, "fuzz": fuzz()}
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    for s in shapes:
        print(f"old={s['old']!s:5} new={s['new']!s:5} product={s['product']!s:5} | {s['shape']}")
    print(json.dumps(result["fuzz"], ensure_ascii=False))
