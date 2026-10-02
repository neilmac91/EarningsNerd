#!/usr/bin/env python3
"""Offline replay of B's hosted 70-run cohort: main versus the current-period guard branch.

Input is the retained `eval-baseline` report of CI run 36993299710 (`eval_20261002T101321Z.json`,
the report revalidated in ../pr1039-condition2-2026-10-02/). For each baseline result, each backend
re-renders in its own subprocess exactly as that folder's `revalidate.py` does:
`_apply_structured_fallbacks` on a deep copy of `raw_sections` with the result's own
`xbrl_grounding`, then `render_sections` + `sections_to_markdown`; the model-facing grounding block
is `build_xbrl_narrative_section(xbrl_grounding)`.

Counted: grounding blocks changed (must be 0), returns lines changed (expected 0), other section
fields and Markdown lines changed, the hosted line versus each re-render, and the ratio clauses
whose current point is not net income's current period (the guard's only trigger).

Usage (any cwd; real provider keys unset):

    python replay_hosted_cohort.py <eval_report.json> <out.json> --main-backend DIR --branch-backend DIR

No network: provider keys are replaced by the tests/conftest.py placeholder and every socket
connect raises. Bytecode writing is disabled so neither backend tree changes.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_current_period import PROVIDER_KEYS, offline_environment  # noqa: E402

RATIOS = ("return_on_equity", "return_on_assets")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(path: str):
    """HEAD and tracked-clean state of a git checkout; None for an archive copy."""
    def run(*args):
        proc = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True)
        return proc.stdout.strip() if proc.returncode == 0 else None
    head = run("rev-parse", "HEAD")
    return {"head": head, "tracked_clean": run("status", "--porcelain", "--untracked-files=no") == ""} if head else None


def result_key(res: dict) -> str:
    return f"{res.get('ticker')} {res.get('filing_type')} run{res.get('run')}"


def worker(backend: str, report_path: str, out_path: str) -> None:
    offline_environment()
    sys.path.insert(0, backend)
    os.chdir(backend)
    from app.services.ai.xbrl_narrative import build_xbrl_narrative_section
    from app.services.openai_service import openai_service
    from app.services.summary_sections import render_sections, sections_to_markdown
    from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION
    app_file = os.path.abspath(sys.modules["app"].__file__)
    assert app_file.startswith(os.path.abspath(backend) + os.sep), app_file

    rows = {}
    for res in json.load(open(report_path)).get("results") or []:
        if res.get("candidate", "baseline") != "baseline":
            continue
        xg = res.get("xbrl_grounding") if isinstance(res.get("xbrl_grounding"), dict) else None
        row = {"grounding": build_xbrl_narrative_section(copy.deepcopy(xg)) if xg else None,
               "line": None, "sections": None, "markdown": None}
        if isinstance(res.get("raw_sections"), dict):
            sections = copy.deepcopy(res["raw_sections"])
            openai_service._apply_structured_fallbacks(sections, {}, copy.deepcopy(xg))
            row["line"] = (sections.get("value_drivers") or {}).get("returns_on_capital")
            row["sections"] = sections
            row["markdown"] = sections_to_markdown(
                render_sections({"schema_version": SUMMARY_SCHEMA_VERSION, "sections": sections}))
        rows[result_key(res)] = row
    json.dump({"app_file": app_file, "stamp": SUMMARY_PROMPT_VERSION, "rows": rows}, open(out_path, "w"))


def render(backend: str, report_path: str, tmp: str, label: str) -> dict:
    out = os.path.join(tmp, f"{label}.json")
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", backend, report_path, out],
                          cwd=backend, capture_output=True, text=True, timeout=1800,
                          env={k: v for k, v in os.environ.items() if k not in PROVIDER_KEYS + ("PYTHONPATH",)})
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        sys.exit(2)
    return json.load(open(out))


def misaligned_clauses(xg: dict) -> list:
    """Ratios whose current period is known and differs from net income's known current period."""
    def period(key):
        cur = (xg.get(key) or {}).get("current") if isinstance(xg.get(key), dict) else None
        p = cur.get("period") if isinstance(cur, dict) else None
        return p.strip() if isinstance(p, str) and p.strip() else None
    ni = period("net_income")
    return [r for r in RATIOS if ni is not None and period(r) not in (None, ni)]


def main() -> int:
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        worker(*sys.argv[2:])
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("out")
    ap.add_argument("--main-backend", required=True)
    ap.add_argument("--branch-backend", required=True)
    args = ap.parse_args()
    report_path, out_path = os.path.abspath(args.report), os.path.abspath(args.out)
    with tempfile.TemporaryDirectory() as tmp:
        main_run = render(os.path.abspath(args.main_backend), report_path, tmp, "main")
        branch_run = render(os.path.abspath(args.branch_backend), report_path, tmp, "branch")

    c = {"results": 0, "results_with_returns_line": 0, "grounding_identical": 0, "grounding_changed": 0,
         "returns_lines_changed": 0, "other_section_fields_changed": 0,
         "markdown_lines_changed_outside_returns_line": 0, "hosted_line_equals_main_rerender": 0,
         "hosted_line_equals_branch_rerender": 0, "ratio_clauses_in_lines": 0,
         "ratio_current_not_net_income_current": 0}
    changed, misaligned = [], []
    for res in json.load(open(report_path)).get("results") or []:
        if res.get("candidate", "baseline") != "baseline":
            continue
        key = result_key(res)
        m, b = main_run["rows"][key], branch_run["rows"][key]
        c["results"] += 1
        hosted = ((res.get("raw_sections") or {}).get("value_drivers") or {}).get("returns_on_capital")
        c["hosted_line_equals_main_rerender"] += hosted == m["line"]
        c["hosted_line_equals_branch_rerender"] += hosted == b["line"]
        c["grounding_identical" if m["grounding"] == b["grounding"] else "grounding_changed"] += 1
        if b["line"]:
            c["results_with_returns_line"] += 1
            c["ratio_clauses_in_lines"] += b["line"].count(" not annualized: ")
        if m["line"] != b["line"]:
            c["returns_lines_changed"] += 1
            changed.append({"key": key, "main": m["line"], "branch": b["line"]})
        ms, bs = m["sections"] or {}, b["sections"] or {}
        for sec in sorted(set(ms) | set(bs)):
            x, y = ms.get(sec), bs.get(sec)
            if isinstance(x, dict) and isinstance(y, dict):
                c["other_section_fields_changed"] += sum(
                    1 for f in set(x) | set(y)
                    if (sec, f) != ("value_drivers", "returns_on_capital") and x.get(f) != y.get(f))
            elif x != y:
                c["other_section_fields_changed"] += 1
        drop = {m["line"], b["line"]} - {None}
        if ([ln for ln in (m["markdown"] or "").splitlines() if ln not in drop]
                != [ln for ln in (b["markdown"] or "").splitlines() if ln not in drop]):
            c["markdown_lines_changed_outside_returns_line"] += 1
        xg = res.get("xbrl_grounding") if isinstance(res.get("xbrl_grounding"), dict) else {}
        for ratio in misaligned_clauses(xg):
            c["ratio_current_not_net_income_current"] += 1
            misaligned.append({"key": key, "ratio": ratio})

    out = {
        "purpose": "Offline replay of the hosted 70-run cohort: main versus the returns current-period guard.",
        "report": {"path": report_path, "sha256": sha256_file(report_path)},
        "renderers": {"main": {"app_file": main_run["app_file"], "stamp": main_run["stamp"],
                               "git": git_head(args.main_backend)},
                      "branch": {"app_file": branch_run["app_file"], "stamp": branch_run["stamp"],
                                 "git": git_head(args.branch_backend)}},
        "script_sha256": sha256_file(os.path.abspath(__file__)),
        "counts": c, "changed_returns_lines": changed, "misaligned_ratio_clauses": misaligned,
    }
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    print(json.dumps(c))
    return 1 if c["grounding_changed"] else 0


if __name__ == "__main__":
    sys.exit(main())
