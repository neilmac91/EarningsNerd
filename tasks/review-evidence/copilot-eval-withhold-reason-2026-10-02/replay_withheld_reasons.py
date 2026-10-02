"""Offline demonstration: the patched copilot runner names each retained withheld row's reason.

No provider call, no network, no database. Run from ``backend/`` with provider keys unset::

    env -u OPENAI_API_KEY -u DEEPSEEK_API_KEY -u OPENAI_BASE_URL python \
        ../tasks/review-evidence/copilot-eval-withhold-reason-2026-10-02/replay_withheld_reasons.py \
        --out-dir OUT RUN_DIR [RUN_DIR ...]

Each RUN_DIR is a downloaded copilot-eval artifact (``copilot-eval.json`` and ``runner.log``).
For every errored row the retained candidate deltas and recorded tool results are replayed through
the runner's own ``_answer`` (so its new capture runs) and the real ``answer_filing_question``; the
captured reasons are compared, in row order, with the run's own ``runner.log`` withhold lines
(attempts run one at a time, so the k-th line belongs to the k-th withheld row). The reasons are
then put on the retained rows, and ``validate_report`` and ``_write_report`` show the label that
would appear, with errors, accepted and the derived exit code compared against the retained run.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

for key in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_BASE_URL"):
    os.environ.pop(key, None)
os.environ.update({
    "SECRET_KEY": "offline-withhold-reason-secret-key-0123456789",
    "OPENAI_API_KEY": "sk-offline-withhold-reason",
    "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
    "STRIPE_SECRET_KEY": "sk_test_offline",
    "STRIPE_WEBHOOK_SECRET": "whsec_offline",
    "SKIP_REDIS_INIT": "true",
    "PWNED_PASSWORD_CHECK_ENABLED": "false",
    "DATABASE_URL": "sqlite://",
})
sys.path.insert(0, os.getcwd())
logging.getLogger().addHandler(logging.NullHandler())  # records are still created; nothing printed

from app.services import copilot_service as cs  # noqa: E402
from app.services import copilot_tools  # noqa: E402
from evals import copilot_runner as runner  # noqa: E402

LOG_LINE = re.compile(r"Copilot candidate withheld at citation publication boundary: (.+)")


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def code_identity():
    root = os.path.dirname(os.path.abspath(runner.__file__))
    head = subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", root, "status", "--porcelain", "--untracked-files=no"],
                                         text=True).strip())
    return {"git_head": head, "git_dirty": dirty, "copilot_runner_sha256": sha256(runner.__file__),
            "copilot_service_sha256": sha256(cs.__file__)}


def snapshot(row, source_meta):
    inputs = row.get("inputs") or {}
    meta = source_meta.get(row["accession_number"], {})
    return SimpleNamespace(
        accession_number=inputs.get("accession_number") or row["accession_number"],
        period_of_report=inputs.get("period_of_report"), filing_type=meta.get("filing_type"),
        filing_date=(meta.get("metadata") or {}).get("filing_date"), document_url=meta.get("document_url"),
        sec_url=(meta.get("metadata") or {}).get("sec_url"), xbrl_data=inputs.get("xbrl_data"), company_id=None,
        cik=meta.get("cik"), content_cache=SimpleNamespace(critical_excerpt=inputs.get("source_text"), markdown_content=None),
        company=SimpleNamespace(name=(meta.get("metadata") or {}).get("company_name"), ticker=row.get("ticker")),
    )


async def replay(row, source_meta):
    """The row's retained candidate through runner._answer and the real service; returns its trace."""
    retained = row["tool_trace"]
    recorded = list(retained.get("tool_results") or [])
    every = list(recorded)
    unserved = []
    in_stream = {"on": False}

    def raw(result):
        result = copy.deepcopy(result)
        if isinstance(result, dict):
            result.pop("cite", None)
            result.pop("_marker", None)
        return result

    def run_tool(name, args, *_args, **_kwargs):
        if in_stream["on"] and recorded:
            call = recorded.pop(0)
            assert call["name"] == name and call["args"] == args, "tool replay out of order"
            return raw(call["result"])
        for call in every:  # a repair lookup the trace did not record: serve the model's own, if any
            if call["name"] == name and call["args"] == args:
                return raw(call["result"])
        unserved.append({"name": name, "args": args})
        return {"error": "unavailable_offline"}

    async def stream(messages, tools, service_run_tool, **_kwargs):
        in_stream["on"] = True
        for call in list(recorded):
            service_run_tool(call["name"], copy.deepcopy(call["args"]))
        in_stream["on"] = False
        for delta in retained["candidate_deltas"]:
            yield delta

    saved = (copilot_tools.run_tool, cs.openai_service.stream_chat_with_tools)
    copilot_tools.run_tool, cs.openai_service.stream_chat_with_tools = run_tool, stream
    trace = {}
    try:
        try:
            await runner._answer(snapshot(row, source_meta), row["question"], trace=trace)
            outcome = "published"
        except ValueError as exc:
            outcome = str(exc)
    finally:
        copilot_tools.run_tool, cs.openai_service.stream_chat_with_tools = saved
    return trace, outcome, unserved


def analyse(run_dir, out_dir):
    path = os.path.join(run_dir, "copilot-eval.json")
    report = json.load(open(path))
    run_id = re.search(r"(\d{11})", os.path.abspath(run_dir)).group(1)
    logged = [m.group(1) for m in map(LOG_LINE.search, open(os.path.join(run_dir, "runner.log"))) if m]
    source_meta = {s["accession_number"]: s for s in (report.get("preparation") or {}).get("sources", [])}
    rows, replayed = [], []
    for row in report["results"]:
        slim = {k: row[k] for k in ("ticker", "accession_number", "question_id", "run_index", "terminal_complete")}
        for k in ("score", "error"):
            if k in row:
                slim[k] = copy.deepcopy(row[k])
        if "error" in row:
            trace, outcome, unserved = asyncio.run(replay(row, source_meta))
            same_event = trace["service_events"] == row["tool_trace"]["service_events"]
            if trace["withheld_reasons"]:
                slim["error"]["withheld_reason"] = trace["withheld_reasons"][0]
            replayed.append({"row": f'{row["ticker"]} {row["question_id"]} d{row["run_index"]}',
                             "replay_outcome": outcome, "same_service_events": same_event,
                             "unserved_lookups": unserved, "withheld_reasons": trace["withheld_reasons"]})
        rows.append(slim)
    labelled = {k: copy.deepcopy(report[k]) for k in ("runs", "planned_attempts", "summary", "requested_model")}
    labelled["results"] = rows
    labelled["failures"] = runner.validate_report(labelled, expected_plan=report["planned_attempts"])
    labelled["accepted"] = not labelled["failures"]
    target = os.path.join(out_dir, run_id)
    runner._write_report(labelled, Path(target))
    retained_failures = runner.validate_report(
        {k: report[k] for k in ("runs", "planned_attempts", "results", "summary")}, expected_plan=report["planned_attempts"])
    return {
        "run": run_id, "source_sha": report.get("source_sha"), "report_sha256": sha256(path),
        "errored_rows": replayed,
        "captured_in_row_order": [r["withheld_reasons"][0] if r["withheld_reasons"] else None for r in replayed],
        "runner_log_in_order": logged,
        "captured_equals_runner_log": [r["withheld_reasons"][0] if r["withheld_reasons"] else None for r in replayed] == logged,
        "retained": {"errors": report["summary"]["errors"], "failures": report["failures"], "accepted": report["accepted"],
                     "exit_code": 0 if report["accepted"] else 1, "revalidated_failures": retained_failures},
        "labelled": {"errors": sum(bool(r.get("error")) for r in rows), "failures": labelled["failures"],
                     "accepted": labelled["accepted"], "exit_code": 0 if labelled["accepted"] else 1},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("runs", nargs="+")
    args = parser.parse_args()
    result = {"code": code_identity(), "runs": [analyse(run, args.out_dir) for run in args.runs]}
    ok = all(r["captured_equals_runner_log"] and all(x["same_service_events"] and not x["unserved_lookups"]
                                                     for x in r["errored_rows"])
             and r["labelled"]["errors"] == r["retained"]["errors"] and r["labelled"]["accepted"] is False
             and r["labelled"]["exit_code"] == r["retained"]["exit_code"] == 1 for r in result["runs"])
    result["result"] = "PASS" if ok else "FAIL"
    print(json.dumps(result, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
