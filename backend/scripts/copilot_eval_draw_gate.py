#!/usr/bin/env python3
"""copilot-eval draws once per pull-request head (backend/evals/RUNBOOK.md, triage rule for a red
copilot-eval run).

A red copilot-eval run is triaged and recorded, never drawn again to obtain a green result. GitHub
offers three ways to run the workflow again on an unchanged head: a re-run attempt, a draft-to-ready
toggle and a close/reopen. The last two fire a new run whose attempt number is 1, so a gate on the
attempt number alone misses them (Codex review on #1166). This script is the workflow's first step
after checkout. It looks for an earlier draw on the same head commit: an attempt of this workflow, in
any run, whose runner step started. When one exists, this run does not draw. It reports that draw's
verdict (green only when the draw succeeded) and the job's later steps are skipped. A head with no
earlier draw draws, including a re-run of an attempt that failed before its runner step.

Nothing exempts a head: anything mutable after a draw, such as the pull request body, could be edited
to buy another draw once the result was known (Codex review on #1166). A new draw comes from a new
push. A predeclared protocol that needs several draws of the same code (as the prompt candidate's
PREREGISTRATION.md drew Q1 to Q3) gives each draw its own head, a commit that changes only its own
evidence folder, and its preregistration says so.

Environment (Actions sets all but the token): GITHUB_TOKEN (actions: read), GITHUB_REPOSITORY,
GITHUB_RUN_ID, GITHUB_RUN_NUMBER, GITHUB_RUN_ATTEMPT, GITHUB_EVENT_PATH, GITHUB_OUTPUT, and
optionally GITHUB_API_URL. Stdlib only: it runs before any dependency install, and holds no provider
credential. A failed read of the earlier runs fails closed (no draw). That attempt drew nothing, so
a re-run of it may draw once the API answers.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

WORKFLOW_FILE = "copilot-eval.yml"
JOB_NAME = "copilot-eval"
RUNNER_STEP = "Run every verified question three times"
RUNBOOK = "backend/evals/RUNBOOK.md, triage rule for a red copilot-eval run"
PER_PAGE = 100
MAX_PAGES = 50  # 5,000 runs on one head: past this the listing is not trusted, and the gate fails closed

Fetch = Callable[[str], Dict[str, Any]]


def api_fetch(api_url: str, token: str) -> Fetch:
    def fetch(path: str) -> Dict[str, Any]:
        request = urllib.request.Request(
            api_url.rstrip("/") + path,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - fixed https API host
            return json.load(response)

    return fetch


def attempt_draw(fetch: Fetch, repo: str, run_id: int, attempt: int) -> Optional[Dict[str, str]]:
    """This attempt's draw, if its runner step started (finished, failed, cancelled or still running):
    {"conclusion": ..., "url": ...}. An attempt skipped as a draft, or one that failed before the runner
    step, drew nothing."""
    jobs = fetch(f"/repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100").get("jobs") or []
    for job in jobs:
        if job.get("name") != JOB_NAME:
            continue
        for step in job.get("steps") or []:
            if step.get("name") != RUNNER_STEP:
                continue
            if step.get("status") in ("in_progress", "completed") and step.get("conclusion") != "skipped":
                return {
                    "conclusion": step.get("conclusion") or step.get("status"),
                    "url": job.get("html_url") or f"run {run_id} attempt {attempt}",
                }
    return None


def head_runs(fetch: Fetch, repo: str, head_sha: str) -> list:
    """Every run of this workflow on ``head_sha``, all pages. The API lists newest first, so a draw that
    many replayed runs have pushed past the first page must still be found (Codex review on #1166)."""
    runs: list = []
    for page in range(1, MAX_PAGES + 1):
        data = fetch(f"/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/runs"
                     f"?head_sha={head_sha}&per_page={PER_PAGE}&page={page}")
        batch = data.get("workflow_runs") or []
        runs.extend(batch)
        if len(batch) < PER_PAGE or len(runs) >= int(data.get("total_count") or len(runs) + 1):
            return runs
    raise RuntimeError(f"more than {MAX_PAGES} pages of runs on one head")


def first_draw(fetch: Fetch, repo: str, head_sha: str, run_id: int, run_number: int,
               run_attempt: int) -> Optional[Dict[str, str]]:
    """The earliest draw on ``head_sha`` before this attempt, across this workflow's runs, or None."""
    listed = head_runs(fetch, repo, head_sha)
    attempts: Dict[int, tuple] = {}
    for run in listed:
        attempts[int(run["id"])] = (int(run.get("run_number") or 0), int(run.get("run_attempt") or 1))
    # This run's earlier attempts count, even before the listing shows this run.
    attempts[run_id] = (run_number, run_attempt - 1)
    for rid, (_, last) in sorted(attempts.items(), key=lambda item: (item[1][0], item[0])):
        for attempt in range(1, last + 1):
            draw = attempt_draw(fetch, repo, rid, attempt)
            if draw:
                return draw
    return None


def write_output(env: Mapping[str, str], draw: bool) -> None:
    with open(env["GITHUB_OUTPUT"], "a", encoding="utf8") as handle:
        handle.write(f"draw={'true' if draw else 'false'}\n")


def main(env: Mapping[str, str] = os.environ, fetch: Optional[Fetch] = None) -> int:
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf8"))
    head_sha = (event.get("pull_request") or {})["head"]["sha"]

    fetch = fetch or api_fetch(env.get("GITHUB_API_URL") or "https://api.github.com", env["GITHUB_TOKEN"])
    try:
        draw = first_draw(fetch, env["GITHUB_REPOSITORY"], head_sha, int(env["GITHUB_RUN_ID"]),
                          int(env["GITHUB_RUN_NUMBER"]), int(env["GITHUB_RUN_ATTEMPT"]))
    except Exception as exc:  # noqa: BLE001 - any failed read fails closed
        print(f"::error::copilot-eval could not read this head's earlier runs ({type(exc).__name__}: {exc}), "
              "so it does not draw. This attempt drew nothing: re-run it once the API answers.")
        write_output(env, False)
        return 1

    if draw is None:
        print(f"No earlier draw on {head_sha[:12]}: this run draws.")
        write_output(env, True)
        return 0

    write_output(env, False)
    if draw["conclusion"] == "success":
        print(f"::notice::{head_sha[:12]} already drew green ({draw['url']}). copilot-eval draws once per "
              f"head ({RUNBOOK}), so this run reports that verdict and does not draw.")
        return 0
    print(f"::error::{head_sha[:12]} already drew ({draw['conclusion']}: {draw['url']}). copilot-eval draws once "
          f"per head and is never drawn again to obtain a green result ({RUNBOOK}). Triage and record that "
          "run; a new draw comes from a new push.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
