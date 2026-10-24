"""Summarize classify_corpus_h.py output for step 0 of PR #1551's measurement plan (offline).

Counts, per question, the first generations whose system message hashed to the first-generation
composition c221b7e3c5c2 and how many of them H's production chooser would not publish.

Usage: python -I summarize_step0.py <generations.jsonl> <run-artifacts.tsv> <runs-listed.tsv> \
           <head-code-diff.tsv> <exclusions.tsv> <window.json> <out.json> <out.md> <notes.json> <output_files...>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict

COMPOSITION = "c221b7e3c5c2"
gen_path, art_path, runs_path, diff_path, excl_path, window_path, out_json, out_md, notes_path = sys.argv[1:10]
output_files = sys.argv[10:]
notes = json.load(open(notes_path))

recs = [json.loads(line) for line in open(gen_path)]
artifacts = {}
for line in open(art_path):
    run, art, name, size, expired, sha, created = line.rstrip("\n").split("\t")
    artifacts[run] = {"artifact_id": art, "head_sha": sha, "artifact_created": created}
runs = {}
for line in open(runs_path):
    cols = line.rstrip("\n").split("\t")
    runs[cols[0]] = {"conclusion": cols[2], "created_at": cols[3], "head_sha": cols[4], "branch": cols[5],
                     "event": cols[6], "prs": cols[7], "attempt": cols[8]}
code = {}
for line in open(diff_path):
    sha, vs_h, vs_b = line.rstrip("\n").split("\t")
    code[sha] = {"differs_from_H": vs_h, "differs_from_H_base_b3d3cb11": vs_b}
exclusions = [line.rstrip("\n").split("\t", 1) for line in open(excl_path) if line.strip()]
window = json.load(open(window_path))


def run_of(report_path: str) -> str:
    match = re.search(r"/artifacts/(\d+)/", report_path)
    return match.group(1) if match else report_path


# Group generations into rows.
rows: dict[tuple, list[dict]] = defaultdict(list)
for r in recs:
    rows[(r["report"], r["ticker"], r["accession"], r["question_id"], r["run_index"])].append(r)
for gens in rows.values():
    gens.sort(key=lambda g: g["gen_index"])

reports_read = sorted({run_of(r["report"]) for r in recs}, key=int)
firsts = [gens[0] for gens in rows.values() if gens[0]["gen_index"] == 0 and not gens[0]["aggregate"]]
c221 = [g for g in firsts if g["system_sha"] == COMPOSITION]
other_comp = Counter(g["system_sha"] for g in firsts if g["system_sha"] != COMPOSITION)
reports_with_c221 = sorted({run_of(g["report"]) for g in c221}, key=int)

# Reports read but holding no c221 first generation are excluded, with their compositions named.
by_report_comp: dict[str, Counter] = defaultdict(Counter)
for g in firsts:
    by_report_comp[run_of(g["report"])][g["system_sha"]] += 1
no_first_gen = sorted(set(reports_read) - set(by_report_comp), key=int)
for run in reports_read:
    if run not in reports_with_c221:
        comps = dict(by_report_comp.get(run, {})) or "no first generation recorded"
        exclusions.append([run, f"no first generation under {COMPOSITION} (first-generation compositions: {comps})"])

evaluable = [g for g in c221 if g.get("h_evaluable")]
not_evaluable = [g for g in c221 if not g.get("h_evaluable")]


def qkey(g: dict) -> str:
    return f'{g["ticker"]} / {g["accession"]} / {g["question_id"]}'


row_of = {id(gens[0]): gens for gens in rows.values()}
per_q: dict[str, dict] = {}
for g in sorted(evaluable, key=qkey):
    q = per_q.setdefault(qkey(g), {"question": qkey(g), "n": 0, "rejected": 0, "by_reason": Counter(),
                                   "by_chooser": Counter(), "recovered_by_retry": 0, "source_text_shas": Counter(),
                                   "runs": set()})
    q["n"] += 1
    q["runs"].add(run_of(g["report"]))
    q["source_text_shas"][g["source_text_sha"]] += 1
    if g["h_rejected"]:
        q["rejected"] += 1
        q["by_reason"][g["h_label"]] += 1
        q["by_chooser"][g["h_chooser"]] += 1
        gens = row_of[id(g)]
        if len(gens) > 1 and gens[-1]["row_complete"]:
            q["recovered_by_retry"] += 1
per_question = []
for q in per_q.values():
    per_question.append({
        "question": q["question"], "n": q["n"], "rejected": q["rejected"],
        "p0": round(q["rejected"] / q["n"], 6) if q["n"] else 0.0,
        "by_reason": dict(sorted(q["by_reason"].items())),
        "by_chooser_under_H": dict(sorted(q["by_chooser"].items())),
        "rejected_then_recovered_by_retry_in_run": q["recovered_by_retry"],
        "source_text_shas": dict(sorted(q["source_text_shas"].items())),
        "reports": len(q["runs"]),
    })

trailer = [g for g in evaluable if g.get("h_rejected") and g.get("h_reason") == "Unexpected citation trailer"]
trailer_rows = [f'run {run_of(g["report"])} (head {artifacts.get(run_of(g["report"]), {}).get("head_sha", "?")[:8]}) '
                f'{g["ticker"]} {g["question_id"]} run_index={g["run_index"]}: H reason "{g["h_reason"]}" '
                f'({g["h_class"]}, chooser {g["h_chooser"]}); recorded {g["recorded_withheld"]}'
                for g in sorted(trailer, key=lambda g: (int(run_of(g["report"])), g["ticker"], g["question_id"], g["run_index"]))]

# Agreement between H's replay and the reason each run recorded, on c221 first generations.
agreement = Counter()
for g in evaluable:
    agreement[(g["h_status"], g.get("h_source", "-"), bool(g.get("recorded_agrees")))] += 1
disagreements = [
    {"run": run_of(g["report"]), "head": artifacts.get(run_of(g["report"]), {}).get("head_sha", "?")[:8],
     "row": f'{g["ticker"]} {g["question_id"]} run_index={g["run_index"]}', "h_status": g["h_status"],
     "h_reason": g.get("h_reason"), "recorded": g["recorded_withheld"]}
    for g in evaluable if not g.get("recorded_agrees")]

reports_meta = []
for run in reports_with_c221:
    meta = {**runs.get(run, {}), **artifacts.get(run, {})}
    meta["run_id"] = run
    meta["copilot_path_code"] = code.get(meta.get("head_sha", ""), {})
    meta["c221_first_generations"] = sum(1 for g in c221 if run_of(g["report"]) == run)
    reports_meta.append(meta)
    meta["c221_evaluable"] = sum(1 for g in evaluable if run_of(g["report"]) == run)
    meta["c221_rejected"] = sum(1 for g in evaluable if run_of(g["report"]) == run and g["h_rejected"])
# Roll up by how the head's Copilot-path files differ from H's base b3d3cb11 (main without the PR).
by_code: dict[str, dict] = {}
for meta in reports_meta:
    key = meta["copilot_path_code"].get("differs_from_H_base_b3d3cb11", "unknown")
    agg = by_code.setdefault(key, {"reports": 0, "n": 0, "rejected": 0, "by_reason": Counter()})
    agg["reports"] += 1
    agg["n"] += meta["c221_evaluable"]
    agg["rejected"] += meta["c221_rejected"]
    for g in evaluable:
        if run_of(g["report"]) == meta["run_id"] and g["h_rejected"]:
            agg["by_reason"][g["h_label"]] += 1
by_code_out = {k: {**v, "by_reason": dict(v["by_reason"])} for k, v in sorted(by_code.items())}
pr_files = "copilot/envelope.py,copilot/exceptions.py,copilot/prompt.py,copilot_service.py"
heads_matching_base_in_copilot_path = sum(1 for m in reports_meta
                                          if m["copilot_path_code"].get("differs_from_H_base_b3d3cb11") == "-")
heads_differing_only_in_pr_files = sum(1 for m in reports_meta
                                       if m["copilot_path_code"].get("differs_from_H") == pr_files)

total_rejected = sum(q["rejected"] for q in per_question)
# Cross-check: H's quotation check on the answer before resolution, against the recorded post-verify reason.
passed_verify = [g for g in evaluable if g.get("stage") == "verify" and g.get("verify") == "ok"]
quotation_crosscheck = Counter(
    ("agree" if (g.get("quotation_preresolve") or None) == (g["recorded_withheld"][-1] if g["recorded_withheld"] else None)
     else "differ", "rejects" if g.get("quotation_preresolve") else "passes") for g in passed_verify)
summary = {
    "pr": "neilmac91/EarningsNerd#1551", "composition_under_test": "863fb9b91a4e (trailer retry)",
    "h_code": "d4d9c5105fe81a9234c770c8e397d682e7a790c9 (app code; worktree /home/user/wt/copilot-trailer)",
    "first_generation_composition": COMPOSITION,
    "window": window,
    "runs_listed": len(runs),
    "runs_with_artifact": len(artifacts),
    "reports_read": len(reports_read),
    "reports_used": len(reports_with_c221),
    "reports_excluded": [f"{run}: {reason}" for run, reason in sorted(exclusions, key=lambda e: int(e[0]))],
    "first_generations_c221_recorded": len(c221),
    "first_generations_c221": len(evaluable),
    "first_generations_c221_not_evaluable": dict(Counter(g["h_status"] for g in not_evaluable)),
    "first_generations_other_compositions": dict(other_comp),
    "rejected_total": total_rejected,
    "p0_pooled": round(total_rejected / len(evaluable), 6) if evaluable else 0.0,
    "rejected_by_reason_pooled": dict(sorted(Counter(g["h_label"] for g in evaluable if g["h_rejected"]).items())),
    "rejected_by_chooser_under_H_pooled": dict(sorted(Counter(g["h_chooser"] for g in evaluable if g["h_rejected"]).items())),
    "per_question": per_question,
    "trailer_count": len(trailer),
    "trailer_rows": trailer_rows,
    "replay_vs_recorded": {f"{s}|{src}|agrees={a}": n for (s, src, a), n in sorted(agreement.items())},
    "replay_vs_recorded_disagreements": disagreements,
    "reports_with_c221_heads_copilot_path_equal_to_H_base": heads_matching_base_in_copilot_path,
    "reports_with_c221_heads_differing_from_H_only_in_PR_files": heads_differing_only_in_pr_files,
    "by_head_copilot_path_difference_from_H_base": by_code_out,
    "quotation_check_preresolution_vs_recorded": {f"{a}|H {b}": n for (a, b), n in sorted(quotation_crosscheck.items())},
    "rejected_then_recovered_by_retry_in_run_total": sum(q["rejected_then_recovered_by_retry_in_run"] for q in per_question),
    "method": notes["method"],
    "classifier_changes": notes["classifier_changes"],
    "caveats": notes["caveats"],
    "output_files": output_files,
    "reports": reports_meta,
}
with open(out_json, "w") as fh:
    json.dump(summary, fh, indent=1, sort_keys=False)
    fh.write("\n")

lines = [
    "# Step 0: first-generation rejections under H's code, composition c221b7e3c5c2",
    "",
    f"Window: {window['start']} to {window['end']} ({window['start_reason']}). Runs listed: {len(runs)}; "
    f"with an artifact: {len(artifacts)}; reports read: {len(reports_read)}; used: {len(reports_with_c221)}.",
    f"First generations under c221b7e3c5c2 that reached the chooser: {len(evaluable)} "
    f"(not evaluable: {dict(Counter(g['h_status'] for g in not_evaluable)) or 0}).",
    "",
    "| Question | n | Rejected | p0 | By reason |",
    "| --- | --- | --- | --- | --- |",
]
for q in per_question:
    reasons = "; ".join(f"{k}: {v}" for k, v in q["by_reason"].items()) or "none"
    lines.append(f'| {q["question"]} | {q["n"]} | {q["rejected"]} | {q["p0"]:.4f} | {reasons} |')
lines.append(f'| **All** | {len(evaluable)} | {total_rejected} | {summary["p0_pooled"]:.4f} | |')
lines += ["", f"\"Unexpected citation trailer\" under H's code: **{len(trailer)}**.", ""]
lines += [f"- {row}" for row in trailer_rows]
digest = hashlib.sha256(open(out_json, "rb").read()).hexdigest()
lines += ["", f"step0-summary.json sha256: `{digest}`. Method, classifier changes and caveats are in that file."]
with open(out_md, "w") as fh:
    fh.write("\n".join(lines) + "\n")
print(json.dumps({k: summary[k] for k in ("reports_read", "reports_used", "first_generations_c221", "rejected_total",
                                          "p0_pooled", "trailer_count")}))
