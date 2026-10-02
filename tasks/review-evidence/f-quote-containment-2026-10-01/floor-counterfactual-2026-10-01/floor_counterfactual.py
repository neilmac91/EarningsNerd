"""Offline floor counterfactual for item F (zero spend).

Runs the production predicate `unsupported_prose_quotations` from the F worktree, varying ONLY the
module-level floor `_MIN_VERIFIABLE_LEN` at runtime. It compares the result against the #1021 audit
definition: a double-quoted span of at least 8 characters that is not contiguous in the row's
retained source_text.

Input: the 13 retained copilot-eval.json runs, which are scratch exports and not committed:
- 6 skeptic runs under analysis/skeptic1021/r*/;
- 7 main-code runs copilot-36*/, including D8 36870677818.

Run it from the F scratch dir (PYTHONPATH=. so `offline_env` is importable); offline_env points at the F worktree backend.
Produced `results.json` against F head c69504d7.
"""
import glob, json, logging, os, re
import offline_env  # noqa: F401
logging.disable(logging.CRITICAL)
from app.services import copilot_service as c
from app.services.provenance_service import normalize_for_match

S = os.path.dirname(os.getcwd())
PATHS = sorted(glob.glob(f"{S}/analysis/skeptic1021/r*/copilot-eval.json")) + sorted(glob.glob(f"{S}/copilot-36*/copilot-eval.json"))
MAIN = {"36640254449", "36754723895", "36777581481", "36798834277", "36800236360", "36809122540", "36870677818"}
FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def an(t):
    return re.sub(r"\s+", " ", (t or "").translate(FOLD).strip().lower())


rows = []
for p in PATHS:
    rid = re.search(r"(\d{11})", p).group(1)
    for r in json.load(open(p))["results"]:
        ans, src = r.get("answer") or "", (r.get("inputs") or {}).get("source_text") or ""
        if ans and src:
            audit = bool([q for q in re.findall(r'"([^"]{8,})"', ans.translate(FOLD)) if an(q) not in an(src)])
            rows.append((rid, r.get("ticker"), r.get("question_id"), r.get("run_index"), ans, normalize_for_match(src), audit))
out = {"runs": len(PATHS), "rows": len(rows), "audit_flagged": sum(r[6] for r in rows), "floors": {}}
for floor in (24, 20, 16, 12, 8):
    c._MIN_VERIFIABLE_LEN = floor
    agree = rule_only = audit_only = 0; main_rows = 0; main_runs = set(); misses = []
    for rid, t, q, ri, ans, ns, audit in rows:
        flag = bool(c.unsupported_prose_quotations(ans, ns))
        agree += flag and audit; rule_only += flag and not audit
        if audit and not flag:
            audit_only += 1; misses.append([rid, t, q, ri])
        if rid in MAIN and flag:
            main_rows += 1; main_runs.add(rid)
    out["floors"][floor] = {"agree": agree, "rule_only": rule_only, "audit_only": audit_only, "audit_only_rows": misses,
                            "main_code_withheld_rows": main_rows, "main_code_rows": sum(r[0] in MAIN for r in rows),
                            "main_code_runs_with_withheld": len(main_runs), "main_code_runs": 7}
print(json.dumps(out, indent=1))
