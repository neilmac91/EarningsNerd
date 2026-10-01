"""Offline replay of the candidate predicate over the 12 retained copilot-eval.json runs (216 rows).

Zero spend: reads local JSON only. Writes replay-results.json next to this file.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

from app.services.provenance_service import normalize_for_match, verify_excerpt_in_text

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prose_quote_predicate as P  # noqa: E402

SCRATCH = os.path.dirname(HERE)
REPO = "/home/user/EarningsNerd"
AUDITS = f"{REPO}/tasks/review-evidence/pr1021-qualification-2026-10-01/audits"
MAIN_RUNS = {"36640254449", "36754723895", "36777581481", "36798834277", "36800236360", "36809122540"}

PATHS = sorted(glob.glob(f"{SCRATCH}/analysis/skeptic1021/r*/copilot-eval.json")) + \
    sorted(glob.glob(f"{SCRATCH}/copilot-36*/copilot-eval.json"))

# The audit's own fold (prose_quote_audit.py), reproduced only to cross-check the retained audit JSON.
AUDIT_FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def audit_norm(text):
    return re.sub(r"\s+", " ", (text or "").translate(AUDIT_FOLD).strip().lower())


def audit_spans(answer, source):
    ns = audit_norm(source)
    return [q for q in re.findall(r'"([^"]{8,})"', answer.translate(AUDIT_FOLD)) if audit_norm(q) not in ns]


def run_id(path):
    return re.search(r"(\d{11})", path).group(1)


def row_key(row):
    return (row["ticker"], row["question_id"], row["run_index"])


def candidate_prose(trace):
    text = "".join((trace or {}).get("candidate_deltas") or [])
    return text.split("===CITATIONS===")[0].split("===NOT_DISCLOSED===")[0].strip() if text else ""


def main():
    retained_audit = {}
    for path in sorted(glob.glob(f"{AUDITS}/*.json")):
        for report in json.load(open(path)):
            rid = run_id(os.path.basename(path))
            retained_audit[rid] = {(h["ticker"], h["question_id"], h["run_index"]): h["composed_quotes"]
                                   for h in report["composed_quote_rows"]}

    runs, rows_out, equivalence = [], [], {"checked": 0, "mismatches": []}
    for path in PATHS:
        rid = run_id(path)
        raw = open(path, "rb").read()
        report = json.loads(raw)
        run = {"run": rid, "code": "main" if rid in MAIN_RUNS else "old-prompt",
               "artifact": os.path.relpath(path, SCRATCH), "sha256": hashlib.sha256(raw).hexdigest(),
               "source_sha": report.get("source_sha"), "rows": 0, "published": 0, "error_rows": 0,
               "flagged_rows": [], "audit_rows": sorted(f"{t} {q} d{i}" for t, q, i in retained_audit.get(rid, {}))}
        for row in report["results"]:
            run["rows"] += 1
            key = row_key(row)
            source = (row.get("inputs") or {}).get("source_text")
            ns = normalize_for_match(source)
            answer = row.get("answer")
            rec = {"run": rid, "code": run["code"], "ticker": key[0], "question_id": key[1], "draw": key[2],
                   "published": answer is not None, "source_chars": len(source or ""),
                   "audit_retained": retained_audit.get(rid, {}).get(key, [])}
            if answer is None:
                run["error_rows"] += 1
                trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), dict) else {}
                prose = candidate_prose(trace)
                rec.update(error=row.get("error"), service_events=trace.get("service_events"),
                           candidate_prose=prose or None,
                           candidate_reasons=P.unsupported_prose_quotations(prose, ns) if prose else None)
                rows_out.append(rec)
                continue
            run["published"] += 1
            scan = P.scan(answer, ns)
            reasons = [s["reason"] for s in scan if s["reason"]]
            # Equivalence: for in-scope, non-elided spans, our substring check == production verifier.
            for s in scan:
                if s["span"] is not None and s["in_scope"] and not s["elided"]:
                    content = P._MARKER_RE.sub(" ", s["span"]).strip(P._EDGE_CHARS)
                    equivalence["checked"] += 1
                    if verify_excerpt_in_text(content, ns) != (s["needle"] in ns):
                        equivalence["mismatches"].append({"run": rid, "row": key, "span": s["span"]})
            recomputed_audit = audit_spans(answer, source)
            assert recomputed_audit == rec["audit_retained"], (rid, key, recomputed_audit, rec["audit_retained"])
            rec.update(answer=answer, spans=scan, reasons=reasons, flagged=bool(reasons),
                       audit_flagged=bool(recomputed_audit), passed=(row.get("score") or {}).get("passed"))
            if reasons:
                run["flagged_rows"].append({"row": f"{key[0]} {key[1]} d{key[2]}", "reasons": reasons,
                                            "spans": [s["span"] for s in scan if s["reason"]]})
            rows_out.append(rec)
        runs.append(run)

    published = [r for r in rows_out if r["published"]]
    # Confusion against the retained audit list (row level).
    confusion = {"both": [], "predicate_only": [], "audit_only": [], "neither": 0}
    span_level = {"audit_span_not_flagged": [], "flagged_span_not_in_audit": []}
    for r in published:
        tag = f'{r["run"]} {r["ticker"]} {r["question_id"]} d{r["draw"]}'
        if r["flagged"] and r["audit_flagged"]:
            confusion["both"].append(tag)
        elif r["flagged"]:
            confusion["predicate_only"].append(tag)
        elif r["audit_flagged"]:
            confusion["audit_only"].append(tag)
        else:
            confusion["neither"] += 1
        flagged_spans = [s["span"] for s in r["spans"] if s["reason"]]
        for q in r["audit_retained"]:
            if q not in flagged_spans:
                s = next(s for s in r["spans"] if s["span"] == q)
                span_level["audit_span_not_flagged"].append({"row": tag, "span": q, "needle_len": s["needle_len"],
                                                             "in_scope": s["in_scope"],
                                                             "row_still_flagged": r["flagged"]})
        for q in flagged_spans:
            if q not in r["audit_retained"]:
                span_level["flagged_span_not_in_audit"].append({"row": tag, "span": q})

    # Valid-quote controls: rows whose every quoted span is contiguous in the source.
    controls = []
    for r in published:
        spans = [s for s in r["spans"] if s["span"] is not None]
        if spans and all(s["needle"] in _nsrc(r) for s in spans):
            controls.append({"row": f'{r["run"]} {r["ticker"]} {r["question_id"]} d{r["draw"]}',
                             "spans": [(s["span"], s["needle_len"], s["in_scope"]) for s in spans],
                             "flagged": r["flagged"]})

    main_pub = [r for r in published if r["code"] == "main"]
    old_pub = [r for r in published if r["code"] != "main"]
    withheld = {
        "main_rows": len(main_pub), "main_flagged": sum(r["flagged"] for r in main_pub),
        "main_rate": sum(r["flagged"] for r in main_pub) / len(main_pub),
        "main_runs_with_flag": sorted({r["run"] for r in main_pub if r["flagged"]}),
        "old_rows_published": len(old_pub), "old_flagged": sum(r["flagged"] for r in old_pub),
        "all_published": len(published), "all_flagged": sum(r["flagged"] for r in published),
    }

    # Floor sensitivity (row level, elision rule on/off), main and all published rows.
    sensitivity = []
    for floor in (8, 10, 12, 14, 16, 18, 19, 20, 22, 24, 25, 28, 30, 36, 37):
        for elision in (True, False):
            def flags(rows):
                return {f'{r["run"]} {r["ticker"]} {r["question_id"]} d{r["draw"]}' for r in rows
                        if any(s["reason"] for s in P.scan(r["answer"], _nsrc(r),
                                                           floor=floor, check_elision=elision))}
            fa, fm = flags(published), flags(main_pub)
            audit_all = {f'{r["run"]} {r["ticker"]} {r["question_id"]} d{r["draw"]}' for r in published if r["audit_flagged"]}
            sensitivity.append({"floor": floor, "elision_rule": elision, "all_flagged": len(fa),
                                "main_flagged": len(fm), "missed_vs_audit": len(audit_all - fa),
                                "extra_vs_audit": len(fa - audit_all)})

    result = {"origin_main_sha": open(f"{HERE}/main/ORIGIN_MAIN_SHA").read().strip(),
              "parameters": {"quote_marks": [hex(ord(c)) for c in P.QUOTE_MARKS], "floor": P._MIN_VERIFIABLE_LEN,
                             "edge_chars": P._EDGE_CHARS, "marker_re": P._MARKER_RE.pattern,
                             "ellipsis_re": P._ELLIPSIS_RE.pattern, "reasons": P.REASONS},
              "runs": runs, "confusion_vs_retained_audit": confusion, "span_level": span_level,
              "valid_quote_controls": controls, "withheld": withheld, "floor_sensitivity": sensitivity,
              "verifier_equivalence": equivalence,
              "rows": [{k: v for k, v in r.items() if k != "answer"} for r in rows_out]}
    with open(f"{HERE}/replay-results.json", "w") as fh:
        json.dump(result, fh, indent=1, ensure_ascii=False, default=str)
    return result


_SOURCES = {}
_NORMALIZED = {}


def _nsrc(r):
    key = (r["run"], r["ticker"], r["question_id"], r["draw"])
    if key not in _NORMALIZED:
        _NORMALIZED[key] = normalize_for_match(_src(r))
    return _NORMALIZED[key]


def _src(r):
    key = (r["run"], r["ticker"], r["question_id"], r["draw"])
    if not _SOURCES:
        for path in PATHS:
            for row in json.load(open(path))["results"]:
                _SOURCES[(run_id(path), *row_key(row))] = (row.get("inputs") or {}).get("source_text")
    return _SOURCES[key]


if __name__ == "__main__":
    res = main()
    print("origin/main", res["origin_main_sha"])
    print(f'{"run":12} {"code":10} rows pub err flagged  audit')
    for run in res["runs"]:
        print(f'{run["run"]:12} {run["code"]:10} {run["rows"]:4} {run["published"]:3} {run["error_rows"]:3} '
              f'{len(run["flagged_rows"]):7}  {len(run["audit_rows"])}')
        for f in run["flagged_rows"]:
            print("     ", f["row"], f["reasons"], f["spans"])
    print("confusion:", {k: (v if isinstance(v, int) else len(v)) for k, v in res["confusion_vs_retained_audit"].items()})
    print("predicate_only:", res["confusion_vs_retained_audit"]["predicate_only"])
    print("audit_only:", res["confusion_vs_retained_audit"]["audit_only"])
    print("span-level audit spans not flagged:")
    for s in res["span_level"]["audit_span_not_flagged"]:
        print("     ", s)
    print("span-level flagged not in audit:", res["span_level"]["flagged_span_not_in_audit"])
    print("controls:", len(res["valid_quote_controls"]), "flagged:", sum(c["flagged"] for c in res["valid_quote_controls"]))
    for c in res["valid_quote_controls"]:
        print("     ", c["row"], c["flagged"], [(s[0][:50], s[1], s[2]) for s in c["spans"]])
    print("withheld:", res["withheld"])
    print("equivalence:", res["verifier_equivalence"]["checked"], "mismatches", res["verifier_equivalence"]["mismatches"])
    print("errors:")
    for r in res["rows"]:
        if not r["published"]:
            print("     ", r["run"], r["ticker"], r["question_id"], r["draw"], r.get("service_events"),
                  repr((r.get("candidate_prose") or "")[:80]), r.get("candidate_reasons"))
    print("sensitivity:")
    for s in res["floor_sensitivity"]:
        print("     ", s)
