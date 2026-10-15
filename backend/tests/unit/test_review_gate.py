"""The review gate (rule 12 for the review-wait lesson): the decision is pure, pinned offline, and the
workflow that publishes it runs on every pull-request event without write permissions. It never
skips that job, because a skipped job counts as passing; a draft fails it instead."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import review_gate

ROOT = Path(__file__).resolve().parents[3]
HEAD = "a834193192d007ed9b5c35e895aa532dcbb757bc"


CODEX_USER = {"login": "chatgpt-codex-connector[bot]", "type": "Bot", "id": 199175422}


def _summary(status: str, commit: str, user: dict = CODEX_USER) -> dict:
    body = (
        "<!-- codex-pull-request-review-summary -->\n\n## Codex Review Summary\n\n"
        "| Review | Status | Commit | Review trigger |\n| --- | --- | --- | --- |\n"
        f"| 📝 **Code Review** | {status} | `{commit}` | PR opened |\n"
    )
    return {"user": user, "body": body}


COMPLETED = '✅ **Completed** <relative-time datetime="2026-09-15T18:54:47Z">2026-09-15T18:54:47Z</relative-time>'
RUNNING = '🔄 **Running** since <relative-time datetime="2026-09-15T18:50:38Z">2026-09-15T18:50:38Z</relative-time>'


def test_parse_summary_reads_status_and_commit_through_the_markup():
    rows = review_gate.parse_summary(_summary(COMPLETED, "a834193")["body"])
    assert len(rows) == 1 and rows[0]["commit"] == "a834193"
    assert "Completed" in rows[0]["status"] and "<relative-time" not in rows[0]["status"]


@pytest.mark.parametrize("case, expected", [
    ("completed-head", "pass"),
    ("completed-other-head", "wait"),        # the fix-commit failure mode: the review is for an older head
    ("running-head", "wait"),
    ("failed-head", "fail"),
    ("no-summary", "wait"),
    ("summary-from-a-human", "wait"),        # only the Codex bot's summary counts
    ("summary-from-a-lookalike-login", "wait"),   # a login containing "codex" copying the table format
    ("summary-from-a-user-with-the-bot-login", "wait"),  # right login, wrong account type and id
    ("override", "pass"),
    ("override-too-short", "wait"),
    ("bad-head", "fail"),
    ("short-head", "fail"),                  # only a full 40-hex head is accepted
    ("prefix-collision", "wait"),            # a head minted with the reviewed commit's 7-hex prefix
    ("prefix-resolves-elsewhere", "wait"),   # the reviewed commit was force-pushed away; the repository still resolves the prefix to it
    ("prefix-unresolvable", "wait"),         # the repository cannot resolve the prefix uniquely
    ("draft-completed-head", "fail"),        # a draft never passes, even with a completed review of its head
    ("draft-override", "fail"),              # nor with an override; marking it ready starts a new run
    ("draft-unreadable", "fail"),            # a draft flag the API did not report as a boolean fails closed
    ("draft-unreadable-override", "fail"),   # override or not
])
def test_decision_requires_a_completed_review_of_this_exact_head_or_a_recorded_override(case, expected):
    comments, body, head, commits, draft = [], "Ordinary PR body.", HEAD, [HEAD], False
    resolve = lambda short: HEAD if HEAD.startswith(short) else None  # noqa: E731 - the repository resolves the prefix to the head
    if case == "completed-head":
        comments = [_summary(COMPLETED, "a834193")]
    elif case == "completed-other-head":
        comments = [_summary(COMPLETED, "7547ef1")]
    elif case == "running-head":
        comments = [_summary(RUNNING, "a834193")]
    elif case == "failed-head":
        comments = [_summary("❌ **Failed**", "a834193")]
    elif case == "summary-from-a-human":
        comments = [_summary(COMPLETED, "a834193", user={"login": "neilmac91", "type": "User", "id": 1})]
    elif case == "summary-from-a-lookalike-login":
        comments = [_summary(COMPLETED, "a834193", user={"login": "codex-reviewer", "type": "User", "id": 2})]
    elif case == "summary-from-a-user-with-the-bot-login":
        comments = [_summary(COMPLETED, "a834193", user={"login": CODEX_USER["login"], "type": "User", "id": 3})]
    elif case == "override":
        body = "Docs only.\n\nReview override: Codex bot out of credits; two independent lenses reviewed the diff.\n"
    elif case == "override-too-short":
        body = "Review override: ok\n"
    elif case == "bad-head":
        head = "not-a-sha"
    elif case == "short-head":
        head = HEAD[:7]
    elif case == "prefix-collision":
        comments = [_summary(COMPLETED, "a834193")]
        commits = ["a834193" + "0" * 33, HEAD]  # the reviewed commit and a crafted head share the prefix
    elif case == "prefix-resolves-elsewhere":
        comments = [_summary(COMPLETED, "a834193")]
        resolve = lambda short: "a834193" + "0" * 33  # noqa: E731
    elif case == "prefix-unresolvable":
        comments = [_summary(COMPLETED, "a834193")]
        resolve = lambda short: None  # noqa: E731
    elif case == "draft-completed-head":
        comments, draft = [_summary(COMPLETED, "a834193")], True
    elif case == "draft-override":
        body, draft = "Review override: Codex bot out of credits; two independent lenses reviewed the diff.\n", True
    elif case == "draft-unreadable":
        comments, draft = [_summary(COMPLETED, "a834193")], None
    elif case == "draft-unreadable-override":
        body, draft = "Review override: Codex bot out of credits; two independent lenses reviewed the diff.\n", None
    verdict, message = review_gate.decide(head, comments, body, commits, resolve, pr_draft=draft)
    assert verdict == expected, message
    if case == "completed-other-head":
        assert "7547ef1" in message and "@codex review" in message
    if case == "override":
        assert "out of credits" in message
    if case == "prefix-collision":
        assert "ambiguous" in message
    if case in ("prefix-resolves-elsewhere", "prefix-unresolvable"):
        assert "does not resolve uniquely" in message
    if case in ("draft-completed-head", "draft-override"):
        assert "is a draft" in message and "marked ready" in message
    if case in ("draft-unreadable", "draft-unreadable-override"):
        assert "failing closed" in message


def test_main_polls_until_the_review_completes_and_times_out_honestly(monkeypatch, capsys):
    monkeypatch.setenv("REVIEW_GATE_HEAD", HEAD)
    monkeypatch.setenv("REVIEW_GATE_TIMEOUT_MINUTES", "1")
    monkeypatch.setenv("REVIEW_GATE_POLL_SECONDS", "5")
    states = iter([([_summary(RUNNING, "a834193")], "body", [HEAD], False),
                   ([_summary(COMPLETED, "a834193")], "body", [HEAD], False)])
    sleeps = []
    ticks = iter([0.0, 0.0, 10.0])
    assert review_gate.main(fetch=lambda: next(states), sleep=sleeps.append, clock=lambda: next(ticks, 10.0)) == 0
    assert sleeps == [5.0]
    # Timeout: the review never completes for this head; the failure names the remedy.
    ticks = iter([0.0, 0.0, 30.0, 70.0])
    assert review_gate.main(fetch=lambda: ([_summary(COMPLETED, "7547ef1")], "body", [HEAD], False), sleep=sleeps.append,
                            clock=lambda: next(ticks, 70.0)) == 1
    out = capsys.readouterr().out
    assert "timed out after 1 minutes" in out and "@codex review" in out and "Review override" in out
    # A draft, or an unreadable draft flag, fails on the first read without waiting, though the head
    # has a completed review. The clock advances, so a regression that waits times out instead of hanging.
    for draft, expected in ((True, "is a draft"), (None, "failing closed")):
        sleeps.clear()
        ticks = iter([0.0, 0.0, 70.0])
        assert review_gate.main(fetch=lambda: ([_summary(COMPLETED, "a834193")], "body", [HEAD], draft),
                                sleep=sleeps.append, clock=lambda: next(ticks, 70.0)) == 1
        assert sleeps == [] and expected in capsys.readouterr().out


@pytest.mark.parametrize("pull, draft", [
    ({"draft": True}, True),
    ({"draft": False}, False),
    ({}, None),                  # no draft flag at all
    ({"draft": "false"}, None),  # not a boolean
])
def test_fetch_state_reads_the_draft_flag_from_the_pull_request_now_and_reports_a_non_boolean_as_unknown(
        monkeypatch, pull, draft):
    def github(path, token):
        assert path == "repos/o/r/pulls/7"  # the pull request as it is now, not the event that started the run
        return {**pull, "body": "body"}
    monkeypatch.setattr(review_gate, "_github", github)
    monkeypatch.setattr(review_gate, "_paged", lambda path, token: [])
    assert review_gate.fetch_state("o/r", "7", "token") == ([], "body", [], draft)


def test_workflow_publishes_the_gate_on_every_pull_request_event_without_write_permissions():
    path = ROOT / ".github/workflows/review-gate.yml"
    workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    assert "pull_request" not in workflow["on"]  # the definition must come from the base branch
    assert set(workflow["on"]["pull_request_target"]["types"]) == {"opened", "synchronize", "reopened", "ready_for_review", "edited"}
    assert workflow["on"]["issue_comment"]["types"] == ["created"]  # `@codex review` re-runs the gate for an unchanged head
    assert workflow["permissions"] == {"contents": "read", "issues": "read", "pull-requests": "read"}
    job = workflow["jobs"]["review-gate"]
    # No pull-request event may skip the job: a skipped job reports success, which the required check
    # counts as passing, and an event's draft flag can be stale. The script reads the live flag.
    assert job["if"] == "github.event_name == 'pull_request_target'"
    # Nor may anything else skip or soften the gate step, which would pass the check just the same: a
    # step `if`, `continue-on-error`, a `needs:` on a job that skips, a `shell` or `defaults` that
    # never runs the script, or another step. So the whole shape is pinned.
    assert set(workflow) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert set(job) == {"if", "runs-on", "timeout-minutes", "steps"}
    assert [sorted(step) for step in job["steps"]] == [["uses", "with"], ["uses", "with"], ["env", "name", "run"]]
    assert "permissions" not in job  # the polling job keeps the workflow-level read-only token
    assert workflow["concurrency"]["cancel-in-progress"] == "true"  # a new push supersedes the wait for the old head
    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@") and checkout["with"]["ref"] == "${{ github.event.pull_request.base.ref }}"  # trusted base code, never the PR's own gate
    assert checkout["with"]["persist-credentials"] == "false"
    assert job["steps"][1]["uses"].startswith("actions/setup-python@")  # not another action that could rewrite the script
    step = job["steps"][-1]
    assert step["run"] == "python backend/scripts/review_gate.py"
    assert set(step["env"]) == {"GITHUB_TOKEN", "REVIEW_GATE_REPO", "REVIEW_GATE_PR", "REVIEW_GATE_HEAD",
                                "REVIEW_GATE_TIMEOUT_MINUTES"}  # nothing that could redirect the interpreter
    assert step["env"]["REVIEW_GATE_REPO"] == "${{ github.repository }}"
    assert step["env"]["REVIEW_GATE_PR"] == "${{ github.event.pull_request.number }}"  # this pull request's reviews, no other's
    assert step["env"]["REVIEW_GATE_HEAD"] == "${{ github.event.pull_request.head.sha }}"
    assert step["env"]["GITHUB_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
    assert int(job["timeout-minutes"]) > int(step["env"]["REVIEW_GATE_TIMEOUT_MINUTES"])
    rerun = workflow["jobs"]["rerun-on-review-request"]
    assert "issue_comment" in rerun["if"] and "@codex review" in rerun["if"] and "github.event.issue.pull_request" in rerun["if"]
    assert rerun["permissions"] == {"actions": "write", "pull-requests": "read"}  # the only write scope, on the re-run job alone
    script = rerun["steps"][-1]["run"]
    assert "review-gate.yml/runs?event=pull_request_target" in script and "/rerun" in script
    assert "actions/checkout" not in str(rerun)  # never checks out or executes pull-request code


def test_only_explicit_human_requests_rerun_and_comments_cannot_cancel_each_other():
    workflow = yaml.load((ROOT / ".github/workflows/review-gate.yml").read_text(), Loader=yaml.BaseLoader)
    condition = workflow["jobs"]["rerun-on-review-request"]["if"]
    assert " ".join(condition.split()) == (
        "github.event_name == 'issue_comment' && github.event.issue.pull_request && "
        "github.event.comment.user.type == 'User' && "
        "startsWith(github.event.comment.body, '@codex review')"
    )
    # An ignored bot event still enters workflow-level concurrency. It must not
    # cancel the human request before that request can call the rerun endpoint.
    assert workflow["concurrency"]["group"] == (
        "review-gate-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}"
    )


# A stand-in for `gh api` that filters the way the GitHub API does: runs by head_sha when asked, newest
# first, cut to per_page (30 by default), and `--jq` applied by jq itself. Every call is logged, so a test
# sees which run, if any, the re-run step asked GitHub to re-run.
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys
from urllib.parse import parse_qs, urlsplit

state = json.load(open(os.environ["FAKE_GH_STATE"]))
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if args[:1] != ["api"] or state.get("fail"):
    sys.exit("gh: HTTP 502")
method, jq, path, i = "GET", None, None, 1
while i < len(args):
    if args[i] in ("-X", "--jq"):
        method, jq = (args[i + 1], jq) if args[i] == "-X" else (method, args[i + 1])
        i += 2
    else:
        path, i = args[i], i + 1
url, repo = urlsplit(path), os.environ["REPO"]
query = parse_qs(url.query)
if method == "POST" and re.fullmatch(rf"repos/{repo}/actions/runs/\d+/rerun", url.path):
    sys.exit(0)
if method != "GET":
    sys.exit(f"gh: unexpected {method} {path}")
if url.path == f"repos/{repo}/pulls/{os.environ['PR']}":
    body = state["pull"]
elif url.path == f"repos/{repo}/actions/workflows/review-gate.yml/runs":
    runs = [r for r in state["runs"] if "head_sha" not in query or r["head_sha"] == query["head_sha"][0]]
    runs.sort(key=lambda r: r["run_number"], reverse=True)
    body = {"workflow_runs": runs[: int(query.get("per_page", ["30"])[0])]}
elif re.fullmatch(rf"repos/{repo}/actions/runs/\d+", url.path):
    body = next(r for r in state["runs"] if str(r["id"]) == url.path.rsplit("/", 1)[1])
else:
    sys.exit(f"gh: unexpected {method} {path}")
out = json.dumps(body)
if jq is not None:
    out = subprocess.run(["jq", "-r", jq], input=out, capture_output=True, text=True, check=True).stdout
sys.stdout.write(out)
'''

PR_HEAD = "c" * 40
OLDER_HEAD = "d" * 40


def _gate_run(run_id: int, run_number: int, head: str, pr: int, status: str = "completed",
              conclusion: object = "failure") -> dict:
    return {"id": run_id, "run_number": run_number, "head_sha": head, "status": status,
            "conclusion": conclusion, "pull_requests": [{"number": pr}]}


# Sixty newer gate runs of other pull requests: more than the 50 newest runs the step used to search.
NEWER_RUNS_OF_OTHER_PRS = [_gate_run(1000 + n, 200 + n, "e" * 40, 900 + n, conclusion="success") for n in range(60)]


def _run_the_rerun_step(tmp_path: Path, state: dict):
    workflow = yaml.load((ROOT / ".github/workflows/review-gate.yml").read_text(), Loader=yaml.BaseLoader)
    script = workflow["jobs"]["rerun-on-review-request"]["steps"][-1]["run"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    (tmp_path / "state.json").write_text(json.dumps(state))
    log = tmp_path / "gh.log"
    log.write_text("")
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "REPO": "o/r", "PR": "7", "GH_TOKEN": "unused",
           "FAKE_GH_STATE": str(tmp_path / "state.json"), "FAKE_GH_LOG": str(log)}
    proc = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True, timeout=60)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    return proc, [call for call in calls if call[1:3] == ["-X", "POST"]]


requires_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="the fake gh applies --jq with jq, which GitHub's runners ship")


@requires_jq
@pytest.mark.parametrize("case, runs, rerun_id, said", [
    # The pull request's run is older than the 50 newest runs repo-wide; the head SHA still finds it.
    ("beyond-the-newest-50", NEWER_RUNS_OF_OTHER_PRS + [_gate_run(55, 100, PR_HEAD, 7)], 55, "re-ran run 55 for #7"),
    # The newest by run number, whatever order the API lists them in and whatever its conclusion.
    ("newest-of-several", [_gate_run(50, 90, PR_HEAD, 7, conclusion="success"), _gate_run(51, 95, PR_HEAD, 7),
                           _gate_run(52, 93, PR_HEAD, 7)], 51, "re-ran run 51 for #7"),
    # A skip is only a run from before #1331's change; re-running it would replay the skip.
    ("skipped", [_gate_run(60, 120, PR_HEAD, 7, conclusion="skipped")], None, "old draft condition"),
    ("in-progress", [_gate_run(61, 121, PR_HEAD, 7, status="in_progress", conclusion=None)], None, "still in_progress"),
    # A run on an earlier head checks a commit the pull request no longer has.
    ("only-an-older-head", [_gate_run(62, 122, OLDER_HEAD, 7)], None, "no gate run on #7's head"),
    ("another-pr-on-this-head", [_gate_run(63, 123, PR_HEAD, 8)], None, "no gate run on #7's head"),
])
def test_codex_review_reruns_the_newest_gate_run_on_the_pull_requests_head_and_never_replays_a_skip(
        tmp_path, case, runs, rerun_id, said):
    proc, reruns = _run_the_rerun_step(tmp_path, {"pull": {"head": {"sha": PR_HEAD}}, "runs": runs})
    assert proc.returncode == 0, proc.stderr
    assert said in proc.stdout, proc.stdout
    assert reruns == ([["api", "-X", "POST", f"repos/o/r/actions/runs/{rerun_id}/rerun"]] if rerun_id else [])


@requires_jq
def test_the_rerun_step_fails_rather_than_reporting_nothing_to_rerun_when_the_api_fails(tmp_path):
    proc, reruns = _run_the_rerun_step(tmp_path, {"fail": True, "pull": {}, "runs": []})
    assert proc.returncode != 0 and reruns == []
