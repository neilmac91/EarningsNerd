"""copilot-eval draws once per head (rule 12 for the RUNBOOK triage rule; lessons/ops-copilot-eval-red-is-triaged-never-rerun.md).

The RUNBOOK's triage rule says a red copilot-eval run is never drawn again to obtain a green result
outside a predeclared protocol. As prose it did not hold: a red run was re-run on #1148, and the green
re-run merged the PR. A gate on the attempt number alone missed the other two ways to run again on an
unchanged head, a draft-to-ready toggle and a reopen (Codex review on #1166). So the workflow's first
step after checkout, ``backend/scripts/copilot_eval_draw_gate.py``, looks for an earlier draw on the
head commit in any run or attempt. When one exists, the run reports that draw's verdict and draws
nothing, and nothing mutable after a draw (the pull request body) exempts the head. The decision is
pinned here offline, against a fake of GitHub's two reads, and the workflow is pinned so that no
later step can run without the gate's draw.
"""
import ast
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from scripts import copilot_eval_draw_gate as gate

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "copilot-eval.yml"
SCRIPT = ROOT / "backend" / "scripts" / "copilot_eval_draw_gate.py"
HEAD = "5f253ada86baeb84896a49aea2fb2801f18403e5"
JOB = "copilot-eval"
THIS_RUN, THIS_NUMBER = 500, 50


class FakeApi:
    """GitHub's two reads for one head: this workflow's runs, and each attempt's jobs."""

    def __init__(self, runs=(), jobs=None, fail=False):
        self.runs = list(runs)
        self.jobs = jobs or {}
        self.fail = fail
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)
        if self.fail:
            raise OSError("API unavailable")
        if "/actions/workflows/" in path:
            assert f"/actions/workflows/{gate.WORKFLOW_FILE}/runs?head_sha={HEAD}&" in path
            # Like the API: newest first, pages of per_page, with the total count.
            per_page = int(re.search(r"per_page=(\d+)", path).group(1))
            page = int(re.search(r"[?&]page=(\d+)", path).group(1))
            newest_first = sorted(self.runs, key=lambda r: r["run_number"], reverse=True)
            return {"total_count": len(self.runs),
                    "workflow_runs": newest_first[(page - 1) * per_page:page * per_page]}
        run_id, attempt = map(int, re.search(r"/actions/runs/(\d+)/attempts/(\d+)/jobs", path).groups())
        return {"jobs": self.jobs.get((run_id, attempt), [])}


def run(run_id, number, attempts=1):
    return {"id": run_id, "run_number": number, "run_attempt": attempts}


def job(conclusion="success", status="completed", runner=True, name=JOB):
    """The copilot-eval job of one attempt. ``runner=False``: it ended before the runner step."""
    steps = [{"name": "Draw once per head", "status": "completed", "conclusion": "success"}]
    steps.append({"name": gate.RUNNER_STEP, "status": status if runner else "completed",
                  "conclusion": conclusion if runner else "skipped"})
    return [{"name": name, "html_url": "https://github.com/o/r/actions/runs/400/job/1", "steps": steps}]


def call_gate(tmp_path, api, *, body="", attempt=1):
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"head": {"sha": HEAD}, "body": body}}))
    output = tmp_path / "output"
    env = {
        "GITHUB_EVENT_PATH": str(event), "GITHUB_OUTPUT": str(output), "GITHUB_REPOSITORY": "o/r",
        "GITHUB_RUN_ID": str(THIS_RUN), "GITHUB_RUN_NUMBER": str(THIS_NUMBER),
        "GITHUB_RUN_ATTEMPT": str(attempt), "GITHUB_TOKEN": "token",
    }
    code = gate.main(env, api)
    lines = output.read_text().splitlines() if output.exists() else []
    return code, lines


# --- The decision -----------------------------------------------------------------------------------

def test_a_head_that_never_drew_draws(tmp_path):
    api = FakeApi([run(THIS_RUN, THIS_NUMBER)])
    assert call_gate(tmp_path, api) == (0, ["draw=true"])


def test_an_earlier_run_skipped_as_a_draft_drew_nothing(tmp_path):
    # GitHub's payload for a job skipped by its `if` carries no steps (run 37972259009 on this PR).
    skipped = [{"name": JOB, "status": "completed", "conclusion": "skipped"}]
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40)], {(400, 1): skipped})
    assert call_gate(tmp_path, api) == (0, ["draw=true"])


def test_a_toggle_or_reopen_after_a_red_draw_replays_red_without_drawing(tmp_path, capsys):
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40)], {(400, 1): job("failure")})
    assert call_gate(tmp_path, api) == (1, ["draw=false"])
    out = capsys.readouterr().out
    assert "already drew (failure: https://github.com/o/r/actions/runs/400/job/1)" in out
    assert "backend/evals/RUNBOOK.md" in out and "a new draw comes from a new push" in out


def test_a_toggle_after_a_green_draw_stays_green_without_drawing(tmp_path):
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40)], {(400, 1): job("success")})
    assert call_gate(tmp_path, api) == (0, ["draw=false"])


@pytest.mark.parametrize("display_name", ["Copilot filing fidelity", "copilot-eval (deepseek)"])
def test_a_draw_counts_whatever_the_job_is_called(tmp_path, display_name):
    # The API reports a job's display name: its `name:`, or the id plus matrix values. A cosmetic
    # workflow edit must not hide a draw (tests-and-gates review on #1166).
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40)], {(400, 1): job("failure", name=display_name)})
    assert call_gate(tmp_path, api) == (1, ["draw=false"])


@pytest.mark.parametrize(("status", "conclusion"), [("completed", "cancelled"), ("in_progress", None)])
def test_a_cancelled_or_running_draw_is_a_draw_and_not_green(tmp_path, status, conclusion):
    # Cancelling a draw that looks red (a toggle mid-run cancels it) must not buy a fresh one.
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40)], {(400, 1): job(conclusion, status)})
    assert call_gate(tmp_path, api) == (1, ["draw=false"])


@pytest.mark.parametrize(("first", "expected"), [("failure", 1), ("success", 0)])
def test_a_rerun_attempt_replays_its_run_s_first_draw(tmp_path, first, expected):
    api = FakeApi([run(THIS_RUN, THIS_NUMBER, attempts=2)], {(THIS_RUN, 1): job(first)})
    assert call_gate(tmp_path, api, attempt=2) == (expected, ["draw=false"])


def test_a_rerun_of_an_attempt_that_failed_before_its_runner_draws(tmp_path):
    api = FakeApi([run(THIS_RUN, THIS_NUMBER, attempts=2)], {(THIS_RUN, 1): job(runner=False)})
    assert call_gate(tmp_path, api, attempt=2) == (0, ["draw=true"])


def test_this_run_s_earlier_attempts_count_before_the_listing_shows_the_run(tmp_path):
    api = FakeApi([], {(THIS_RUN, 1): job("failure")})
    assert call_gate(tmp_path, api, attempt=2) == (1, ["draw=false"])


def test_the_earliest_draw_decides_whatever_order_the_listing_uses(tmp_path):
    # Newest first, as the API lists runs. Two draws on one head predate this gate (#1148's heads).
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40), run(300, 30)],
                  {(400, 1): job("success"), (300, 1): job("failure")})
    assert call_gate(tmp_path, api) == (1, ["draw=false"])


def test_a_draw_past_the_first_page_of_runs_still_counts(tmp_path):
    # A hundred and fifty replayed toggles push the head's one draw off the API's first page, which
    # lists newest first (Codex review on #1166).
    replays = [run(1000 + n, 100 + n) for n in range(150)]
    api = FakeApi([run(THIS_RUN, 300), *replays, run(400, 40)], {(400, 1): job("failure")})
    assert call_gate(tmp_path, api) == (1, ["draw=false"])
    assert sum("/actions/workflows/" in path for path in api.paths) == 2


def test_a_listing_longer_than_the_page_cap_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "MAX_PAGES", 1)
    api = FakeApi([run(THIS_RUN, 300), *[run(1000 + n, 100 + n) for n in range(150)]])
    assert call_gate(tmp_path, api) == (1, ["draw=false"])


@pytest.mark.parametrize("line", [
    # A real, committed preregistration: the line an author could add once a draw came back red.
    "Copilot-eval protocol: tasks/review-evidence/prompt-candidate-2026-10-02/PREREGISTRATION.md",
    "Review override: re-draw after a flaky withhold",
])
def test_nothing_in_the_pull_request_body_buys_another_draw(tmp_path, line):
    # The body can be edited after a draw (Codex review on #1166), so no line in it exempts a head.
    api = FakeApi([run(THIS_RUN, THIS_NUMBER), run(400, 40)], {(400, 1): job("failure")})
    assert call_gate(tmp_path, api, body=f"Measurement notes.\n\n{line}\n") == (1, ["draw=false"])


def test_a_failed_read_fails_closed(tmp_path, capsys):
    assert call_gate(tmp_path, FakeApi(fail=True)) == (1, ["draw=false"])
    assert "re-run it once the API answers" in capsys.readouterr().out


def test_the_api_read_is_authenticated_and_versioned(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b'{"jobs": []}'

    def urlopen(request, timeout):
        seen.update(url=request.full_url, headers=dict(request.header_items()), timeout=timeout)
        return Response()

    monkeypatch.setattr(gate.urllib.request, "urlopen", urlopen)
    assert gate.api_fetch("https://api.github.com/", "tok")("/repos/o/r/actions/runs/1/attempts/1/jobs") == {"jobs": []}
    assert seen["url"] == "https://api.github.com/repos/o/r/actions/runs/1/attempts/1/jobs"
    assert seen["headers"]["Authorization"] == "Bearer tok"
    assert seen["headers"]["X-github-api-version"] == "2022-11-28"


# --- The workflow ----------------------------------------------------------------------------------

def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf8"))


def test_the_gate_runs_first_on_every_attempt_and_nothing_installs_or_spends_without_its_draw():
    data = _workflow()
    assert WORKFLOW.name == gate.WORKFLOW_FILE
    assert list(data["jobs"]) == [JOB]
    assert data["permissions"] == {"contents": "read", "actions": "read"}
    steps = data["jobs"][JOB]["steps"]
    assert steps[0]["uses"].startswith("actions/checkout@")
    draw = steps[1]
    assert draw["id"] == "draw"
    assert draw["run"].strip() == "python3 backend/scripts/copilot_eval_draw_gate.py"
    assert "if" not in draw and "continue-on-error" not in draw
    assert draw["env"] == {"GITHUB_TOKEN": "${{ github.token }}"}
    # Every later step either waits for the draw or only shows and keeps evidence (test_copilot_gate
    # pins those two as always(); without a draw they find no report and upload nothing).
    evidence = {"Show the readable report on the run page", "Retain source, output and failure evidence"}
    assert {step.get("name") for step in steps[2:] if step.get("if") == "always()"} == evidence
    for step in steps[2:]:
        if step.get("name") in evidence:
            assert "evals." not in step.get("run", "") and "pip " not in step.get("run", "") and "env" not in step
            continue
        assert step.get("if", "").replace(" ", "") == "steps.draw.outputs.draw=='true'", step
        assert "continue-on-error" not in step


def test_only_the_runner_step_holds_the_provider_key_and_the_gate_knows_its_name():
    steps = _workflow()["jobs"][JOB]["steps"]
    holders = [step for step in steps if "OPENAI_API_KEY" in str(step)]
    assert [step["name"] for step in holders] == [gate.RUNNER_STEP]
    assert "evals.copilot_runner" in holders[0]["run"]


def test_the_gate_is_stdlib_only_so_it_runs_before_any_install():
    tree = ast.parse(SCRIPT.read_text(encoding="utf8"))
    modules = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    modules |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert modules <= set(sys.stdlib_module_names) | {"__future__"}, modules
