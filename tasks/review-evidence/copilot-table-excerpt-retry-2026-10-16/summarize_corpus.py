"""Summarize classify_corpus.py output: withhold subtypes, retry outcomes, and counterfactual eligibility.

Usage: python -I summarize_corpus.py <generations.jsonl> <sections_source_shas_csv> <out.json>
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

ISSUE_1052 = "2026-10-02T18:00:00"   # whole-excerpt verification (approximate merge time)
ISSUE_1111 = "2026-10-07T20:01:35"   # private regeneration + quotation guidance (merge 22:01 +02:00)

recs = [json.loads(line) for line in open(sys.argv[1])]
sections_shas = set(filter(None, sys.argv[2].split(",")))
out: dict = {}


def era(ts: str | None) -> str:
    ts = ts or ""
    if ts < ISSUE_1052:
        return "pre-1052"
    return "1052-to-1111" if ts < ISSUE_1111 else "post-1111"


def source_kind(rec: dict) -> str:
    return "sections" if rec["source_text_sha"] in sections_shas else "other"


rows: dict[tuple, list[dict]] = defaultdict(list)
for r in recs:
    rows[(r["report"], r["timestamp"], r["ticker"], r["accession"], r["question_id"], r["run_index"])].append(r)
for gens in rows.values():
    gens.sort(key=lambda g: g["gen_index"])

out["reports"] = len({r["report"] for r in recs})
out["rows"] = len(rows)
out["generations"] = len(recs)

# 1. First-generation behaviour per question, era and source: text-citation use and verify verdicts.
behaviour: dict = defaultdict(Counter)
for key, gens in rows.items():
    g = gens[0]
    bucket = f'{g["ticker"]}|{g["question_id"]}|{era(g["timestamp"])}|{source_kind(g)}|sys={g["system_sha"]}'
    c = behaviour[bucket]
    c["rows"] += 1
    if g.get("stage") == "verify":
        c["uses_text_citation"] += bool(g["text_refs"])
        c[f'verify_{g["verify"]}'] += 1
        for reason in g["failing_reasons"]:
            c[f"reason_{reason}"] += 1
    else:
        c[f'stage_{g.get("stage") or g.get("mode")}'] += 1
    c["row_published"] += bool(g["row_complete"])
out["first_generation_behaviour"] = {k: dict(v) for k, v in sorted(behaviour.items())}

# 2. Every generation that failed _verify_citations: subtype combinations, by retry eligibility.
fail_combo = Counter()
for r in recs:
    if r.get("stage") == "verify" and r["verify"] != "ok":
        fail_combo[(r["verify"], "+".join(r["failing_reasons"]), "retry-gen" if r["gen_index"] else "first-gen")] += 1
out["verify_failures"] = [{"verdict": v, "reasons": k, "generation": g, "count": n}
                          for (v, k, g), n in fail_combo.most_common()]

# 3. Retry outcomes since #1111: a first generation that failed with a regenerable mismatch and
#    whose row recorded a second generation.
retry = Counter()
for gens in rows.values():
    if len(gens) > 1 and gens[0].get("verify") == "regenerable":
        second = gens[1]
        outcome = second.get("verify") if second.get("stage") == "verify" else (second.get("stage") or second.get("mode"))
        retry[(gens[0]["ticker"], "+".join(gens[0]["failing_reasons"]), outcome, "+".join(second.get("failing_reasons") or []))] += 1
out["retry_outcomes"] = [{"ticker": t, "first_reasons": a, "second_verdict": o, "second_reasons": b, "count": n}
                         for (t, a, o, b), n in retry.most_common()]

# 4. Terminal rows on current code (post-#1111): which first-generation subtypes ended them, and
#    which candidate eligibility rules would have offered the one retry.
RULES = {
    "current": lambda reasons: reasons <= {"mismatch", "elided"},
    "+short": lambda reasons: reasons <= {"mismatch", "elided", "short"},
    "+collision": lambda reasons: reasons <= {"mismatch", "elided", "collision"},
    "+short+collision": lambda reasons: reasons <= {"mismatch", "elided", "short", "collision"},
    "+short+collision+missing": lambda reasons: reasons <= {"mismatch", "elided", "short", "collision", "missing"},
}
terminal_rows = Counter()
eligible = Counter()
for gens in rows.values():
    g = gens[0]
    if era(g["timestamp"]) != "post-1111" or g.get("stage") != "verify" or g["verify"] == "ok":
        continue
    reasons = set(g["failing_reasons"])
    final_published = bool(gens[-1]["row_complete"])
    tag = f'{g["ticker"]}|{source_kind(g)}|{"+".join(sorted(reasons))}|{"recovered" if final_published else "withheld"}'
    terminal_rows[tag] += 1
    if not final_published:
        for name, rule in RULES.items():
            eligible[(name, source_kind(g))] += bool(rule(reasons))
out["post1111_first_gen_failures"] = dict(terminal_rows.most_common())
out["post1111_withheld_rows_eligible_for_one_retry_by_rule"] = {f"{n}|{k}": c for (n, k), c in sorted(eligible.items())}

# 5. Unreferenced verified alternatives: how often a failing generation already declared a
#    verifying excerpt under another number (the model had the right span and cited the wrong one).
alt = Counter()
for r in recs:
    if r.get("stage") == "verify" and r["verify"] != "ok":
        alt["failed"] += 1
        alt["has_unreferenced_verified_declaration"] += bool(r["unreferenced_verified"])
        alt["collision_with_one_verified_declaration"] += any(
            "collision" in v["reasons"] and any(e["verified"] for e in v["excerpts"]) for v in r["per_ref"].values())
out["alternatives"] = dict(alt)

json.dump(out, open(sys.argv[3], "w"), indent=1)
print(json.dumps({k: out[k] for k in ("reports", "rows", "generations")}))

# 6. How a failed retry relates to its failed first generation (post-#1111 rows with two failures).
shape = Counter()
for gens in rows.values():
    if len(gens) == 2 and gens[0].get("verify") not in (None, "ok") and gens[1].get("stage") == "verify" \
            and gens[1]["verify"] != "ok":
        def failing(g):
            return sorted(e["text"] for v in g["per_ref"].values() if v["reasons"] for e in v["excerpts"]
                          if not e["verified"])
        a, b = failing(gens[0]), failing(gens[1])
        if a == b:
            kind = "identical excerpt"
        elif b and a and all(any(y in x for x in a) or len(y) < min(len(x) for x in a) for y in b):
            kind = "shorter excerpt"
        else:
            kind = "different excerpt"
        shape[(gens[0]["ticker"], "+".join(gens[0]["failing_reasons"]), "+".join(gens[1]["failing_reasons"]), kind)] += 1
out["failed_retry_shapes"] = [{"ticker": t, "first": a, "second": b, "relation": k, "count": n}
                              for (t, a, b, k), n in shape.most_common()]
json.dump(out, open(sys.argv[3], "w"), indent=1)
for row in out["failed_retry_shapes"]:
    print(row)
