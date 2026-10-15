"""The review gate (rule 12 for the review-wait lesson): the decision is pure, pinned offline, and the
workflow that publishes it runs on every pull-request event without write permissions. It never
skips that job, because a skipped job counts as passing; a draft fails it instead."""
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
    # The trigger set decides where a run attaches: a trigger whose runs attach to a pull request's head
    # (pull_request_review, push, workflow_dispatch) would skip the gate job there and report success.
    # issue_comment runs attach to main's HEAD, so their skipped job never satisfies a pull request's check.
    assert set(workflow["on"]) == {"pull_request_target", "issue_comment"}
    assert set(workflow["jobs"]) == {"review-gate", "rerun-on-review-request"}
    assert "name" not in workflow["jobs"]["rerun-on-review-request"]  # no second job can carry the check's name
    assert set(job) == {"if", "runs-on", "timeout-minutes", "steps"}
    assert [sorted(step) for step in job["steps"]] == [["uses", "with"], ["uses", "with"], ["env", "name", "run"]]
    assert "permissions" not in job  # the polling job keeps the workflow-level read-only token
    assert workflow["concurrency"]["cancel-in-progress"] == "true"  # a new push supersedes the wait for the old head
    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    # Both `with` maps whole: a `repository:` input pointing at the head repository would fetch a fork's
    # branch named like the base and run the fork's copy of the gate script; `path` or a sparse checkout
    # would fail closed, but the pin leaves nothing to reason about.
    assert checkout["with"] == {"ref": "${{ github.event.pull_request.base.ref }}", "persist-credentials": "false"}  # trusted base code, never the PR's own gate
    assert job["steps"][1]["uses"].startswith("actions/setup-python@")  # not another action that could rewrite the script
    assert job["steps"][1]["with"] == {"python-version": "3.11"}
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
