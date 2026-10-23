"""The review gate (rule 12 for the review-wait lesson and the closing-keyword lesson): the decision is
pure, pinned offline, and the workflow that publishes it runs on every pull-request event without write
permissions. It never skips that job, because a skipped job counts as passing; a draft fails it instead."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from scripts import review_gate

ROOT = Path(__file__).resolve().parents[3]
HEAD = "a834193192d007ed9b5c35e895aa532dcbb757bc"


CODEX_USER = {"login": "chatgpt-codex-connector[bot]", "type": "Bot", "id": 199175422}


CREATED = "2026-09-15T18:40:00Z"
# The gate's clock in these cases: ten minutes after the fixtures' last activity, so every start in them is
# younger than the one-hour abandonment age unless a case sets ``now`` itself (F58 call 1).
NOW = datetime(2026, 9, 15, 19, 10, tzinfo=timezone.utc)
EDITOR = {"login": "chatgpt-codex-connector", "__typename": "Bot", "databaseId": 199175422}


def _body(head=HEAD, status="completed", at="2026-09-15T18:54:47Z", trigger="PR opened", unresolved=False):
    marker = {"code_review": {"commit_sha": head, "status": status,
                              "has_unresolved_findings": unresolved}, "security_review": {"status": None}}
    return ("<!-- codex-pull-request-review-summary -->\n"
            + "<!-- codex-review-state:v1 " + json.dumps(marker) + " -->\n"
            + "| Review | Status | Commit | Review trigger |\n| --- | --- | --- | --- |\n"
            + f'| 📝 **Code Review** | **{status.title()}** <relative-time datetime="{at}">{at}</relative-time> '
            + f'| `{head[:7]}` | {trigger} |\n')


def _edit(body, at="2026-09-15T18:55:00Z", editor=EDITOR):
    return {"diff": body, "editedAt": at, "editor": editor}


def _summary(status: str, commit: str, user: dict = CODEX_USER) -> dict:
    head = HEAD if HEAD.startswith(commit) else commit.ljust(40, "0")
    state = next(x for x in ("completed", "running", "failed") if x in status.lower())
    body = _body(head, state)
    running = _body(head, "running", "2026-09-15T18:50:38Z", unresolved=None)
    return {"id": 1, "node_id": "IC_1", "created_at": CREATED, "updated_at": "2026-09-15T18:55:00Z",
            "user": user, "body": body, "review_history": [_edit(body), _edit(running, "2026-09-15T18:50:39Z")]}


def _decide(*args, **kwargs):
    kwargs.setdefault("now", NOW)
    kwargs.setdefault("pr_created_at", CREATED)
    kwargs.setdefault("pr_timeline", [])
    kwargs.setdefault("pr_head", HEAD)
    return review_gate.decide(*args, **kwargs)


def _state(comments, body, commits, draft, title=None, messages=()):
    return review_gate.State(comments, body, commits, draft, title, messages, CREATED, [], HEAD)


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
    verdict, message = _decide(head, comments, body, commits, resolve, pr_draft=draft)
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


OVERRIDE_LINE = "Review override: Codex bot out of credits; two independent lenses reviewed the diff.\n"


CLOSING_CASES = [
    # The 2026-10-09 incident: #1136's body named #1156 this way, and its merge left #1156 closed, unmerged.
    ("the-1136-incident", "", "Wave 0, built, reviewed and fixed: #1156 and #1157-#1162.", (), False, "fixed: #1156"),
    ("a-conditional-instruction", "", "Close #686 only when this and #695 supersede it.", (), False, "Close #686"),  # #694
    ("uppercase", "", "FIXES #12", (), False, "FIXES #12"),
    ("closed", "", "the closed #12", (), False, "closed #12"),  # every keyword form counts
    ("bare-fix", "", "fix #12", (), False, "fix #12"),
    ("bare-resolve", "", "resolve #12", (), False, "resolve #12"),
    ("in-the-title", "test: close #1177's open findings", "", (), False, "title: \"close #1177\""),  # #1243
    ("in-a-commit-message", "", "", (("b" * 40, "fix: tidy\n\nResolves #12"),), False, "commit bbbbbbb: \"Resolves #12\""),
    ("cross-repository", "", "resolves neilmac91/EarningsNerd#1156", (), False, "neilmac91/EarningsNerd#1156"),
    ("a-pull-request-url", "", "fixes https://github.com/neilmac91/EarningsNerd/pull/1156", (), False, "pull/1156"),
    ("a-gh-reference", "", "resolved GH-12", (), False, "GH-12"),
    ("no-space", "", "resend-success fixed#1082.", (), False, "fixed#1082"),  # #1255
    ("bold", "", "**Fixes:** #12", (), False, "Fixes:** #12"),
    ("a-code-span", "", "`fixes #12`", (), False, "fixes #12"),
    ("a-line-break", "", "Everything here is fixed:\n#12", (), False, "fixed: #12"),
    ("a-link-text", "", "fixes [#12](https://github.com/o/r/issues/12)", (), False, "fixes [#12"),
    ("a-backtick-separator", "", "`fixes` #12", (), False, "fixes` #12"),
    ("strikethrough", "", "fixes ~~#12~~", (), False, "fixes ~~#12"),
    ("a-quote-marker", "", "fixes\n> #12", (), False, "fixes > #12"),
    ("crlf", "", "fixed:\r\n#12", (), False, "fixed: #12"),  # the web editor's line endings
    ("underscore-emphasis", "", "_Fixes #12_", (), False, "Fixes #12"),  # _ is a word character to \b
    ("double-underscore", "", "__Fixes:__ #12", (), False, "Fixes:__ #12"),
    ("underscored-keyword", "", "_Fixes_ #12", (), False, "Fixes_ #12"),  # the trailing edge too
    # GitHub reads the rendered text, where an escaped number sign or an entity is a plain one.
    ("a-backslash-escape", "", "reviewed and fixed: \\#1156", (), False, "fixed: #1156"),
    ("an-escaped-separator", "", "fixed\\: #12", (), False, "fixed: #12"),
    ("an-html-entity", "", "Fixes &#35;12", (), False, "Fixes #12"),
    ("a-non-breaking-space", "", "Fixes&nbsp;#12", (), False, "Fixes #12"),
    ("an-autolink", "", "fixes <https://github.com/o/r/issues/12>", (), False, "issues/12"),
    ("an-http-issues-url", "", "fixes http://github.com/o/r/issues/12", (), False, "issues/12"),
    ("a-www-url", "", "fixes https://www.github.com/my-org/my.repo/pull/12", (), False, "my.repo/pull/12"),
    ("a-dotted-owner-and-repo", "", "resolves my-org/my.repo#12", (), False, "my-org/my.repo#12"),
    ("lowercase-gh", "", "resolved gh-12", (), False, "gh-12"),
    ("despite-an-override", "", OVERRIDE_LINE + "Fixes #12", (), False, "Fixes #12"),  # an override excuses only the wait
    ("on-a-draft", "", "Fixes #12", (), True, "Fixes #12"),  # reported before the draft failure, so it is fixed early
    ("fixed-in", "", "Fixed in #1156.", (), False, None),  # a word between keyword and reference links nothing
    ("inside-other-words", "", "unresolved #12, prefixes #3, fixtures #4, closer #5", (), False, None),
    ("a-parenthesis", "", "the audit fix (#665)", (), False, None),  # #674: closed nothing at the merge
    ("a-semicolon", "", "the Checkout fix; #1285 held", (), False, None),  # #1306: #1285 stayed open
    ("no-number-sign", "", "fixes 12 flaky tests", (), False, None),
    ("the-reference-first", "", "#1156 carries the fix; #1157 resolved it.", (), False, None),
    ("a-path-that-starts-with-a-keyword", "", "see docs/fix-notes/README.md#1-intro", (), False, None),
    # Dependabot's release notes put a keyword before an HTML link to an upstream issue (#1283).
    ("dependabot-release-notes", "", 'Fix <a href="https://redirect.github.com/o/r/issues/233">#233</a>', (), False,
     None),
]


@pytest.mark.parametrize("case, title, body, messages, draft, expected", CLOSING_CASES,
                         ids=[row[0] for row in CLOSING_CASES])
def test_a_closing_keyword_before_a_reference_fails_the_gate_draft_or_not_and_override_or_not(
        case, title, body, messages, draft, expected):
    comments = [_summary(COMPLETED, "a834193")]  # the head is reviewed, so only the text decides
    resolve = lambda short: HEAD if HEAD.startswith(short) else None  # noqa: E731
    verdict, message = _decide(HEAD, comments, body, [HEAD], resolve, pr_draft=draft, pr_title=title,
                                          pr_commit_messages=messages)
    if expected is None:
        assert verdict == "pass", message
    else:
        assert verdict == "fail", message
        assert "closing keyword" in message and expected in message and "after the merge" in message


def test_the_failure_lists_every_closing_reference_in_the_title_body_and_commits():
    verdict, message = _decide(
        HEAD, [_summary(COMPLETED, "a834193")], "Fixes #1 and closes #2.", [HEAD], pr_draft=False,
        pr_title="close #3", pr_commit_messages=(("c" * 40, "resolved #4"),))
    assert verdict == "fail"
    for reference in ('title: "close #3"', 'body: "Fixes #1"', 'body: "closes #2"', 'commit ccccccc: "resolved #4"'):
        assert reference in message


def test_every_commit_message_is_read_not_only_the_first_or_the_head():
    messages = (("1abcdef" + "0" * 33, "chore: first"), ("2abcdef" + "0" * 33, "fix: middle\n\nfixes #12"),
                ("3abcdef" + "0" * 33, "chore: head"))
    verdict, message = _decide(HEAD, [_summary(COMPLETED, "a834193")], "body", [HEAD], pr_draft=False,
                                          pr_commit_messages=messages)
    assert verdict == "fail" and 'commit 2abcdef: "fixes #12"' in message


@pytest.mark.parametrize("body, draft", [("body", False), (OVERRIDE_LINE, False), ("body", True), (OVERRIDE_LINE, True)],
                         ids=["ready", "override", "draft", "draft-override"])
def test_a_commit_list_at_githubs_cap_fails_closed_override_or_not_because_later_messages_are_unread(body, draft):
    """GitHub's pull-request commits endpoint lists at most 250 commits, so a 251st message is never read."""
    comments = [_summary(COMPLETED, "a834193")]
    resolve = lambda short: HEAD if HEAD.startswith(short) else None  # noqa: E731
    capped = [f"{n:040x}" for n in range(1, review_gate.COMMIT_LIST_CAP)] + [HEAD]
    verdict, message = _decide(HEAD, comments, body, capped, resolve, pr_draft=draft)
    assert verdict == "fail" and "250 commits" in message
    if body == "body" and not draft:
        assert _decide(HEAD, comments, body, capped[1:], resolve, pr_draft=draft)[0] == "pass"


def test_main_polls_until_the_review_completes_and_times_out_honestly(monkeypatch, capsys):
    monkeypatch.setenv("REVIEW_GATE_HEAD", HEAD)
    monkeypatch.setenv("REVIEW_GATE_TIMEOUT_MINUTES", "1")
    monkeypatch.setenv("REVIEW_GATE_POLL_SECONDS", "5")
    states = iter([([_summary(RUNNING, "a834193")], "body", [HEAD], False),
                   ([_summary(COMPLETED, "a834193")], "body", [HEAD], False)])
    sleeps = []
    ticks = iter([0.0, 0.0, 10.0])
    assert review_gate.main(fetch=lambda: _state(*next(states)), sleep=sleeps.append, clock=lambda: next(ticks, 10.0),
                            wall=lambda: NOW) == 0
    assert sleeps == [5.0]
    # Timeout: the review never completes for this head; the failure names the remedy.
    ticks = iter([0.0, 0.0, 30.0, 70.0])
    assert review_gate.main(fetch=lambda: _state([_summary(COMPLETED, "7547ef1")], "body", [HEAD], False), sleep=sleeps.append,
                            clock=lambda: next(ticks, 70.0), wall=lambda: NOW) == 1
    out = capsys.readouterr().out
    assert "timed out after 1 minutes" in out and "@codex review" in out and "Review override" in out
    # A draft, or an unreadable draft flag, fails on the first read without waiting, though the head
    # has a completed review. The clock advances, so a regression that waits times out instead of hanging.
    for draft, expected in ((True, "is a draft"), (None, "failing closed")):
        sleeps.clear()
        ticks = iter([0.0, 0.0, 70.0])
        assert review_gate.main(fetch=lambda: _state([_summary(COMPLETED, "a834193")], "body", [HEAD], draft),
                                sleep=sleeps.append, clock=lambda: next(ticks, 70.0), wall=lambda: NOW) == 1
        assert sleeps == [] and expected in capsys.readouterr().out
    # A closing keyword in the title or a commit message fails on the first read too, while the review
    # still runs: main hands decide the whole state, not only the body.
    for title, messages in (("close #12", ()), ("", (("d" * 40, "fixes #12"),))):
        sleeps.clear()
        ticks = iter([0.0, 0.0, 70.0])
        state = ([_summary(RUNNING, "a834193")], "body", [HEAD], False, title, messages)
        assert review_gate.main(fetch=lambda: _state(*state), sleep=sleeps.append, clock=lambda: next(ticks, 70.0),
                                wall=lambda: NOW) == 1
        assert sleeps == [] and "closing keyword" in capsys.readouterr().out


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
        return {**pull, "body": "body", "title": "title"}
    commits = [{"sha": "A" * 40, "commit": {"message": "first"}}, {"sha": "b" * 40, "commit": {}}]
    paged = []

    def paged_read(path, token):
        paged.append(path)
        return commits if path.endswith("/commits") else []
    monkeypatch.setattr(review_gate, "_github", github)
    monkeypatch.setattr(review_gate, "_paged", paged_read)
    assert review_gate.fetch_state("o/r", "7", "token") == (
        [], "body", ["a" * 40, "b" * 40], draft, "title", (("a" * 40, "first"), ("b" * 40, "")), None, [] if draft is False else None, None)
    # The commits come from the pull request's own list, which GitHub caps at 250, not the branch history.
    assert paged == ["repos/o/r/issues/7/comments", "repos/o/r/pulls/7/commits"] + (
        ["repos/o/r/issues/7/timeline"] if draft is False else []) + ["repos/o/r/issues/7/comments"]


def _may_publish_as_review_gate(name: str) -> bool:
    """Whether a job id or name can be published as the review-gate check. A name holding expressions
    resolves at run time (`${{ vars.JOB_NAME }}`), so each expression is read as any text and the name
    counts when its literal parts fit around review-gate; `e2e (${{ matrix.shard }})` cannot."""
    parts = re.split(r"\$\{\{.*?\}\}", name.strip(), flags=re.DOTALL)
    return re.fullmatch(".*".join(re.escape(part) for part in parts), "review-gate", re.IGNORECASE) is not None


@pytest.mark.parametrize(("name", "publishes"), [
    ("review-gate", True),
    (" Review-Gate ", True),
    ("${{ vars.JOB_NAME }}", True),
    ("review-${{ matrix.kind }}", True),
    ("${{ inputs.prefix }}-gate", True),
    ("e2e (${{ matrix.shard }})", False),
    ("review-gate-extra", False),
    ("${{ inputs.caller }} / review-gate", False),
    ("rerun-on-review-request", False),
])
def test_a_name_may_publish_as_review_gate_when_its_literal_parts_fit_around_it(name, publishes):
    assert _may_publish_as_review_gate(name) is publishes


def test_no_job_in_any_other_workflow_publishes_a_check_named_review_gate():
    # Branch protection matches the required check by name, across every workflow. A job elsewhere whose
    # id or name is review-gate would publish a second check under it, and a skipped one reports success,
    # which a required check counts as passing: the bypass #1331 closed for this workflow's own job. A name
    # built from expressions counts when it can resolve to review-gate.
    workflows = sorted((ROOT / ".github/workflows").glob("*.y*ml"))
    assert ROOT / ".github/workflows/review-gate.yml" in workflows
    publishers = []
    for path in workflows:
        jobs = (yaml.load(path.read_text(), Loader=yaml.BaseLoader) or {}).get("jobs") or {}
        for job_id, job in jobs.items():
            names = {job_id, job.get("name", job_id)} if isinstance(job, dict) else {job_id}
            if any(_may_publish_as_review_gate(name) for name in names):
                publishers.append(f"{path.name}:{job_id}")
    assert publishers == ["review-gate.yml:review-gate"], publishers


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
    assert rerun["steps"][-1]["env"] == {"GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}", "REPO": "${{ github.repository }}",
                                         "PR": "${{ github.event.issue.number }}"}  # the commented pull request, no other
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


# A stand-in for `gh api` that filters the way the GitHub API does: runs by head_sha when asked, cut to the
# newest per_page (30 by default), and `--jq` applied by jq itself. GitHub documents no order for that list,
# so the fake moves each page's newest run to second place: a step that took the first or the last run
# instead of the newest fails. `fail` names the one call that answers HTTP 502 (pull, runs or rerun). Every
# call is logged, so a test sees which run, if any, the step asked GitHub to re-run, and what it listed.
FAKE_GH = r"""#!/usr/bin/env python3
import json, os, re, subprocess, sys
from urllib.parse import parse_qs, urlsplit

state = json.load(open(os.environ["FAKE_GH_STATE"]))
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as log:
    log.write(json.dumps(args) + "\n")
if args[:1] != ["api"]:
    sys.exit("gh: unexpected command")
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
    sys.exit("gh: HTTP 502" if state.get("fail") == "rerun" else 0)
if method != "GET":
    sys.exit(f"gh: unexpected {method} {path}")
if url.path == f"repos/{repo}/pulls/{os.environ['PR']}":
    endpoint, body = "pull", state["pull"]
elif url.path == f"repos/{repo}/actions/workflows/review-gate.yml/runs":
    runs = [r for r in state["runs"] if "head_sha" not in query or r["head_sha"] == query["head_sha"][0]]
    page = sorted(runs, key=lambda r: r["run_number"], reverse=True)[: int(query.get("per_page", ["30"])[0])]
    endpoint, body = "runs", {"workflow_runs": page[1:2] + page[:1] + page[2:]}
else:
    sys.exit(f"gh: unexpected {method} {path}")
if state.get("fail") == endpoint:
    sys.exit("gh: HTTP 502")
out = json.dumps(body)
if jq is not None:
    out = subprocess.run(["jq", "-r", jq], input=out, capture_output=True, text=True, check=True).stdout
sys.stdout.write(out)
"""

PR_HEAD = "c" * 40
OLDER_HEAD = "d" * 40
PULL = {"head": {"sha": PR_HEAD, "ref": "fix-7", "repo": {"id": 1, "full_name": "o/r"}}}
FORK_PULL = {"head": {"sha": PR_HEAD, "ref": "patch-1", "repo": {"id": 2, "full_name": "someone/r"}}}


def _gate_run(run_id: int, run_number: int, *, head: str = PR_HEAD, branch: str = "fix-7", repo: object = 1,
              status: str = "completed", conclusion: object = "failure", pull_requests: tuple = (7,)) -> dict:
    # The API's shape: `pull_requests` lists every open pull request whose head commit or branch matches the
    # run's, and none for a fork's run, so it cannot tell two pull requests on one commit apart.
    return {"id": run_id, "run_number": run_number, "head_sha": head, "head_branch": branch,
            "head_repository": None if repo is None else {"id": repo}, "status": status, "conclusion": conclusion,
            "pull_requests": [{"number": n} for n in pull_requests]}


# 150 newer gate runs of other pull requests: more than the newest 100 one listing returns, so only the
# server-side head_sha filter finds this pull request's run.
NEWER_RUNS_OF_OTHER_PRS = [_gate_run(1000 + n, 200 + n, head=f"{n:040x}", branch=f"other-{n}", conclusion="success",
                                     pull_requests=(900 + n,)) for n in range(150)]
LIST_RUNS = f"repos/o/r/actions/workflows/review-gate.yml/runs?event=pull_request_target&head_sha={PR_HEAD}&per_page=100"


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
    return proc, [call[1] for call in calls if call[1] != "-X"], [call for call in calls if call[1:3] == ["-X", "POST"]]


# GitHub's runners ship jq; a machine without it skips these locally, never in CI.
requires_jq = pytest.mark.skipif(shutil.which("jq") is None and not os.environ.get("CI"),
                                 reason="the fake gh applies --jq with jq")
SKIP_REMEDY = "push or edit #7 to start a new run"
NONE_FOUND = f"review-gate: no gate run on #7's head {PR_HEAD[:12]} yet; push or edit the pull request to start one\n"


@requires_jq
@pytest.mark.parametrize("case, pull, runs, rerun_id, said", [
    # The pull request's run is older than the newest 100 runs repo-wide; the head SHA still finds it.
    ("beyond-the-newest-100", PULL, NEWER_RUNS_OF_OTHER_PRS + [_gate_run(55, 100)], 55,
     f"review-gate: re-ran run 55 for #7 at head {PR_HEAD[:12]}\n"),
    # The newest by run number, whatever order the API lists them in and whatever its conclusion.
    ("newest-of-several", PULL, [_gate_run(50, 90, conclusion="success"), _gate_run(51, 95), _gate_run(52, 93)], 51,
     f"review-gate: re-ran run 51 for #7 at head {PR_HEAD[:12]}\n"),
    # A skip is only a run from before #1331's change; re-running it would replay the skip.
    ("skipped", PULL, [_gate_run(60, 120, conclusion="skipped")], None,
     f"review-gate: run 60 skipped under the gate's old draft condition, and a re-run would skip again; {SKIP_REMEDY}\n"),
    ("in-progress", PULL, [_gate_run(61, 121, status="in_progress", conclusion=None)], None,
     "review-gate: run 61 is still in_progress; it will observe the re-requested review itself\n"),
    ("queued", PULL, [_gate_run(62, 122, status="queued", conclusion=None)], None,
     "review-gate: run 62 is still queued; it will observe the re-requested review itself\n"),
    # A run on an earlier head checks a commit the pull request no longer has.
    ("only-an-older-head", PULL, [_gate_run(63, 123, head=OLDER_HEAD)], None, NONE_FOUND),
    ("no-run-at-all", PULL, [], None, NONE_FOUND),
    # #8 shares the head commit from another branch; both runs list both pull requests, and #8's is newer.
    ("another-pr-on-this-head", PULL, [_gate_run(64, 124, pull_requests=(7, 8)),
                                       _gate_run(65, 130, branch="fix-8", pull_requests=(7, 8))], 64,
     f"review-gate: re-ran run 64 for #7 at head {PR_HEAD[:12]}\n"),
    # A fork's run lists no pull request; a base-repository branch of the same name on that commit is not it.
    ("a-fork", FORK_PULL, [_gate_run(66, 126, branch="patch-1", repo=2, pull_requests=()),
                           _gate_run(67, 127, branch="patch-1", pull_requests=(9,))], 66,
     f"review-gate: re-ran run 66 for #7 at head {PR_HEAD[:12]}\n"),
    # A deleted fork leaves the pull request no head repository, and its runs none: nothing matches.
    ("a-deleted-fork", {"head": {**FORK_PULL["head"], "repo": None}},
     [_gate_run(69, 129, branch="patch-1", repo=None, pull_requests=())], None, NONE_FOUND),
    # The branch name is the author's, and git allows jq and shell syntax in one; it reaches jq as data.
    ("a-branch-name-in-jq-syntax", {"head": {**PULL["head"], "ref": 'fix-"7"|$(x)'}},
     [_gate_run(68, 128, branch='fix-"7"|$(x)')], 68, f"review-gate: re-ran run 68 for #7 at head {PR_HEAD[:12]}\n"),
])
def test_codex_review_reruns_the_newest_gate_run_on_the_pull_requests_head_and_never_replays_a_skip(
        tmp_path, case, pull, runs, rerun_id, said):
    proc, listed, reruns = _run_the_rerun_step(tmp_path, {"pull": pull, "runs": runs})
    assert (proc.returncode, proc.stdout) == (0, said), proc.stderr
    assert listed == ["repos/o/r/pulls/7", LIST_RUNS]  # filtered by the server, never from a page of every run
    assert reruns == ([["api", "-X", "POST", f"repos/o/r/actions/runs/{rerun_id}/rerun"]] if rerun_id else [])


@requires_jq
@pytest.mark.parametrize("failing", ["pull", "runs", "rerun"])
def test_the_rerun_step_fails_rather_than_reporting_nothing_to_rerun_when_the_api_fails(tmp_path, failing):
    proc, _, reruns = _run_the_rerun_step(tmp_path, {"fail": failing, "pull": PULL, "runs": [_gate_run(55, 100)]})
    assert proc.returncode != 0, proc.stdout
    assert proc.stdout == ("::error::review-gate: GitHub refused to re-run run 55 (it re-runs a run only within 30 days "
                           f"of its first attempt, and at most 50 times); {SKIP_REMEDY}\n" if failing == "rerun" else "")
    assert len(reruns) == (failing == "rerun")


# F58: distinct, timestamped review cycles, not a completed word borrowed from an earlier run.
READY = "2026-09-15T19:00:00Z"
READY_EVENTS = [{"event": "ready_for_review", "created_at": READY}]
OTHER = "b" * 40


def _cycle(head=HEAD, trigger="Draft marked ready", start="2026-09-15T19:00:01Z",
           finish="2026-09-15T19:02:00Z", unresolved=False):
    return [_edit(_body(head, "completed", finish, trigger, unresolved), finish),
            _edit(_body(head, "running", start, trigger, None), start)]


def _comment(edits, **changes):
    return {"id": 1, "node_id": "IC_1", "created_at": CREATED, "updated_at": edits[0]["editedAt"],
            "user": CODEX_USER, "body": edits[0]["diff"], "review_history": edits, **changes}


def _request(at="2026-09-15T19:03:00Z", **changes):
    return {"id": 3, "body": "@codex review\n", "user": {"type": "User", "login": "reviewer", "id": 5},
            "created_at": at, "updated_at": at, **changes}


def _verdict(comments, **kwargs):
    return _decide(HEAD, comments, "body", [HEAD], lambda short: HEAD, pr_draft=False,
                   pr_timeline=kwargs.pop("pr_timeline", READY_EVENTS), **kwargs)


def test_ready_mark_waits_for_its_own_cycle_and_resolution_not_the_draft_completion():
    draft = _cycle(trigger="Manual request", start="2026-09-15T18:50:00Z", finish="2026-09-15T18:52:00Z")
    assert _verdict([_comment(draft)])[0] == "wait"
    ready = _cycle(unresolved=True)
    assert _verdict([_comment(ready + draft)])[0] == "fail"
    clean_update = _edit(_body(at="2026-09-15T19:02:00Z", trigger="Draft marked ready"), "2026-09-15T19:02:30Z")
    assert _verdict([_comment([clean_update] + ready + draft)])[0] == "pass"


@pytest.mark.parametrize("change", [
    "no-marker", "broken-json", "duplicate-marker", "short-machine-head", "missing-unresolved", "null-unresolved",
    "string-unresolved", "row-head-mismatch", "row-status-mismatch", "missing-row-time", "unknown-trigger",
    "no-history", "history-rest-disagreement", "untrusted-editor", "wrong-editor-id", "missing-start",
    "start-before-ready", "start-after-completion", "mismatched-start-head", "mismatched-start-trigger",
    "newer-mismatched-start", "overlapping-starts", "out-of-order-edits", "missing-timeline", "missing-created",
])
def test_incomplete_or_contradictory_evidence_never_passes(change):
    edits = _cycle()
    kwargs = {}
    if change in ("no-marker", "broken-json", "duplicate-marker", "short-machine-head", "missing-unresolved",
                  "null-unresolved", "string-unresolved", "row-head-mismatch", "row-status-mismatch",
                  "missing-row-time", "unknown-trigger"):
        body = edits[0]["diff"]
        if change == "no-marker":
            body = re.sub(r"<!-- codex-review-state:.*?-->", "", body)
        elif change == "broken-json":
            body = body.replace('"code_review":', '"code_review"')
        elif change == "duplicate-marker":
            body += re.search(r"<!-- codex-review-state:.*?-->", body)[0]
        elif change == "short-machine-head":
            body = body.replace(HEAD, HEAD[:7])
        elif change == "missing-unresolved":
            body = body.replace(', "has_unresolved_findings": false', '')
        elif change == "null-unresolved":
            body = body.replace('"has_unresolved_findings": false', '"has_unresolved_findings": null')
        elif change == "string-unresolved":
            body = body.replace('"has_unresolved_findings": false', '"has_unresolved_findings": "false"')
        elif change == "row-head-mismatch":
            body = body.replace(f'`{HEAD[:7]}`', '`abcdef0`')
        elif change == "row-status-mismatch":
            body = body.replace('**Completed**', '**Running**')
        elif change == "missing-row-time":
            body = re.sub(r'<relative-time.*?</relative-time>', '', body)
        elif change == "unknown-trigger":
            body = body.replace('Draft marked ready', 'Mystery trigger')
        edits[0]["diff"] = body
    elif change == "untrusted-editor":
        edits[1]["editor"] = {**EDITOR, "__typename": "User"}
    elif change == "wrong-editor-id":
        edits[1]["editor"] = {**EDITOR, "databaseId": 1}
    elif change == "missing-start":
        edits = edits[:1]
    elif change == "start-before-ready":
        edits = _cycle(start="2026-09-15T18:59:59Z")
    elif change == "start-after-completion":
        edits[1]["diff"] = _body(status="running", at="2026-09-15T19:04:00Z", trigger="Draft marked ready")
    elif change == "mismatched-start-head":
        edits[1]["diff"] = edits[1]["diff"].replace(HEAD, OTHER).replace(HEAD[:7], OTHER[:7])
    elif change == "mismatched-start-trigger":
        edits[1]["diff"] = edits[1]["diff"].replace('Draft marked ready', 'Manual request')
    elif change == "newer-mismatched-start":
        edits.insert(1, _edit(_body(OTHER, 'running', '2026-09-15T19:01:00Z', 'Manual request'), '2026-09-15T19:01:00Z'))
    elif change == "overlapping-starts":
        edits += [_edit(_body(status='running', at='2026-09-15T19:00:00Z', trigger='Draft marked ready'), READY)]
    elif change == "out-of-order-edits":
        edits[1]["editedAt"] = "2026-09-15T19:05:00Z"
    elif change == "missing-timeline":
        kwargs["pr_timeline"] = None
    elif change == "missing-created":
        kwargs["pr_created_at"] = None
    comment = _comment(edits)
    if change == "no-history":
        comment.pop("review_history")
    elif change == "history-rest-disagreement":
        comment["body"] += "\nChanged after the REST read"
    verdict, message = _verdict([comment], **kwargs)
    assert verdict != "pass", (change, message)


def test_html_encoded_state_and_security_only_edits_do_not_hide_the_code_cycle():
    edits = _cycle()
    security_update = _edit(edits[0]["diff"].replace('"security_review": {"status": null}',
                                                   '"security_review": {"status": "running"}'),
                            "2026-09-15T19:02:10Z")
    comment = _comment([security_update] + edits)
    for item in comment["review_history"]:
        item["diff"] = item["diff"].replace('{', '&#123;').replace('}', '&#125;')
    comment["body"] = comment["review_history"][0]["diff"]
    assert _verdict([comment])[0] == "pass"


def test_latest_ready_event_and_latest_summary_are_binding_even_with_an_older_success():
    older = _comment(_cycle())
    later_ready = READY_EVENTS + [{"event": "ready_for_review", "created_at": "2026-09-15T19:03:00Z"}]
    assert _verdict([older], pr_timeline=later_ready)[0] == "wait"
    new = _comment(_cycle(OTHER), id=2, created_at="2026-09-15T19:01:00Z")
    assert _verdict([older, new])[0] == "wait"
    assert _verdict([new, older])[0] == "wait"


@pytest.mark.parametrize("ready_head, ready_unresolved, expected", [
    (HEAD, False, "pass"), (HEAD, True, "wait"), (OTHER, False, "pass"), (OTHER, True, "pass"),
])
def test_manual_review_can_follow_completed_ready_cycle_and_new_head_can_fix_its_findings(
        ready_head, ready_unresolved, expected):
    manual = _cycle(trigger="Manual request", start="2026-09-15T19:03:01Z", finish="2026-09-15T19:05:00Z")
    ready = _cycle(ready_head, unresolved=ready_unresolved)
    assert _verdict([_comment(manual + ready), _request()])[0] == expected


@pytest.mark.parametrize("case", ["missing-ready", "ready-running", "manual-started-before-ready-completed",
                                  "newer-request", "request-after-start", "no-human-request", "edited-request"])
def test_manual_completion_does_not_substitute_missing_ready_or_unanswered_request(case):
    manual = _cycle(trigger="Manual request", start="2026-09-15T19:03:01Z", finish="2026-09-15T19:05:00Z")
    ready = _cycle(OTHER)
    request = _request()
    if case == "missing-ready":
        ready = []
    elif case == "ready-running":
        ready = ready[1:]
    elif case == "manual-started-before-ready-completed":
        manual = _cycle(trigger="Manual request", start="2026-09-15T19:01:00Z", finish="2026-09-15T19:05:00Z")
        request = _request("2026-09-15T19:00:30Z")
    elif case == "newer-request":
        request = _request("2026-09-15T19:06:00Z")
    elif case == "request-after-start":
        request = _request("2026-09-15T19:03:02Z")
    elif case == "no-human-request":
        request = _request(user=CODEX_USER)
    elif case == "edited-request":
        request["updated_at"] = "2026-09-15T19:03:02Z"
    assert _verdict([_comment(manual + ready), request])[0] == "wait"


def test_ready_and_immediate_manual_request_coalesced_as_manual_does_not_prove_ready_cycle():
    # #1484: ready Running is immediately overwritten by manual Running, then manual Completed;
    # there is no completed ready cycle to borrow from either the live summary or its history.
    manual = _cycle(trigger="Manual request", start="2026-09-15T19:00:12Z", finish="2026-09-15T19:03:13Z")
    ready_running = _edit(_body(status="running", at="2026-09-15T19:00:08Z", trigger="Draft marked ready"),
                          "2026-09-15T19:00:08Z")
    assert _verdict([_comment(manual + [ready_running]), _request("2026-09-15T19:00:01Z")])[0] == "wait"


def test_opened_ready_uses_creation_and_still_waits_for_a_new_manual_request():
    opened = _cycle(trigger="PR opened")
    assert _verdict([_comment(opened)], pr_timeline=[])[0] == "pass"
    assert _verdict([_comment(opened), _request()], pr_timeline=[])[0] == "wait"
    manual = _cycle(trigger="Manual request", start="2026-09-15T19:03:01Z", finish="2026-09-15T19:05:00Z")
    assert _verdict([_comment(manual + opened), _request()], pr_timeline=[])[0] == "pass"


# F58 call 1 (approved 2026-10-23): the history is replayed, a completion pairs with the open start of its head
# and trigger, never with one begun while another of them was open, any start still open blocks, and a start
# open for the hour counts as abandoned.
def _at(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _state_edit(status, at, trigger="Draft marked ready", head=HEAD, unresolved=None, edited=None):
    if status == "completed" and unresolved is None:
        unresolved = False
    return _edit(_body(head, status, at, trigger, unresolved), edited or at)


def _b1_history():
    """Review 6341504879's B1: a manual review runs on the draft, the first ready mark's review R1 starts, the
    manual review completes, a draft flip starts the second ready mark's review R2, and R1 then completes."""
    return [_state_edit("completed", "2026-09-15T19:01:00Z"),                     # R1 finishes
            _state_edit("running", "2026-09-15T18:58:01Z"),                       # R2, the latest ready mark's
            _state_edit("completed", "2026-09-15T18:56:00Z", "Manual request"),   # M finishes
            _state_edit("running", "2026-09-15T18:55:01Z"),                       # R1
            _state_edit("running", "2026-09-15T18:50:00Z", "Manual request")]     # M


B1_TIMELINE = [{"event": "ready_for_review", "created_at": "2026-09-15T18:55:00Z"},
               {"event": "convert_to_draft", "created_at": "2026-09-15T18:57:00Z"},
               {"event": "ready_for_review", "created_at": "2026-09-15T18:58:00Z"}]


@pytest.mark.parametrize("now, words", [
    ("2026-09-15T19:02:00Z", ["started at 18:58:01Z while another review", "no completion can count for it",
                              "holds the gate until 2026-09-15T19:58:01Z", "fresh draft-to-ready transition"]),
    ("2026-09-15T20:00:00Z", ["does not provably follow", "review started at 18:55:01Z", "fresh draft-to-ready"]),
])
def test_b1_a_completion_never_pairs_past_an_older_open_start_of_its_head_and_trigger(now, words):
    # main before F58 call 1 paired R1's completion with R2's start and passed while R2 still ran. Replayed,
    # R2 began while R1 was open, so the completion pairs with R1 and R2 stays open: the gate waits for it, and
    # once R2 is past the hour it still waits, since R1 began before the latest ready mark.
    verdict, message = _verdict([_comment(_b1_history())], pr_timeline=B1_TIMELINE, now=_at(now))
    assert verdict == "wait", message
    assert all(word in message for word in words), message


def test_b1_recovers_with_one_fresh_transition_once_the_unpaired_start_is_past_the_hour():
    fresh = [_state_edit("completed", "2026-09-15T20:03:00Z"), _state_edit("running", "2026-09-15T20:00:01Z")]
    timeline = B1_TIMELINE + [{"event": "convert_to_draft", "created_at": "2026-09-15T19:59:56Z"},
                              {"event": "ready_for_review", "created_at": "2026-09-15T20:00:00Z"}]
    verdict, message = _verdict([_comment(fresh + _b1_history())], pr_timeline=timeline, now=_at("2026-09-15T20:10:00Z"))
    assert verdict == "pass", message


def _hung_ready_then_fresh(flip_at):
    """The ready mark's own review hangs from 19:00:01 (#1496, #1519); one fresh draft-to-ready transition at
    ``flip_at`` starts a review five seconds later that completes clean two minutes after it."""
    flip = _at(flip_at)
    start = flip.replace(second=5)
    finish = start + timedelta(minutes=2)
    iso = lambda moment: moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    history = [_state_edit("completed", iso(finish)), _state_edit("running", iso(start)),
               _state_edit("running", "2026-09-15T19:00:01Z")]
    timeline = READY_EVENTS + [{"event": "convert_to_draft", "created_at": iso(flip.replace(second=0))},
                               {"event": "ready_for_review", "created_at": iso(flip.replace(second=4))}]
    return history, timeline, finish


@pytest.mark.parametrize("flip_at, expected", [("2026-09-15T20:05:00Z", "pass"), ("2026-09-15T19:30:00Z", "wait")])
def test_a_hung_ready_review_past_the_hour_stops_blocking_a_fresh_transition(flip_at, expected):
    # Past the hour the hung start is abandoned, so the fresh ready mark's review pairs and passes (main waited:
    # two starts before one completion). A flip inside the hour leaves the hung start live at the completion,
    # which then pairs with it, before the latest ready mark, so the gate keeps waiting.
    history, timeline, finish = _hung_ready_then_fresh(flip_at)
    verdict, message = _verdict([_comment(history)], pr_timeline=timeline, now=finish + timedelta(minutes=3))
    assert verdict == expected, message


def _hung_manual_history(third_at, second_hang="2026-09-15T21:44:05Z"):
    """#1475's shape (there from 09:47 and 11:44): after a clean ready cycle two manual runs on one head hung, and
    a third request, made at ``third_at``, completed in six minutes."""
    third = _at(third_at)
    iso = lambda moment: moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    history = [_state_edit("completed", iso(third + timedelta(minutes=6)), "Manual request"),
               _state_edit("running", iso(third.replace(second=5)), "Manual request"),
               _state_edit("running", second_hang, "Manual request"),
               _state_edit("running", "2026-09-15T19:47:05Z", "Manual request"),
               _state_edit("completed", "2026-09-15T19:43:00Z"),
               _state_edit("running", "2026-09-15T19:40:01Z")]
    timeline = [{"event": "ready_for_review", "created_at": "2026-09-15T19:40:00Z"}]
    return [_comment(history), _request(third_at)], timeline, third + timedelta(minutes=10)


@pytest.mark.parametrize("third_at, second_hang, expected", [
    ("2026-09-15T22:45:00Z", "2026-09-15T21:44:05Z", "pass"),   # both hangs an hour old when the third starts
    ("2026-09-15T22:43:00Z", "2026-09-15T21:44:05Z", "wait"),   # #1475's own timing: 59 minutes after the second
    ("2026-09-15T22:45:00Z", "2026-09-15T22:06:05Z", "wait"),   # the second hang 39 minutes old
])
def test_hung_manual_reviews_let_a_request_made_once_they_are_an_hour_old_pass(third_at, second_hang, expected):
    # A request made while a hung run of its head and trigger is under the hour overlaps it: its completion could
    # be the hung run's, so it never pairs, and the gate waits for the hour and then for one more review.
    comments, timeline, now = _hung_manual_history(third_at, second_hang)
    verdict, message = _verdict(comments, pr_timeline=timeline, now=now)
    assert verdict == expected, message


def test_a_start_still_open_blocks_the_pass_until_it_completes_or_turns_an_hour_old():
    # The ready cycle completed clean, but another review (another head's, requested while it ran) is still open.
    other = _state_edit("running", "2026-09-15T19:01:30Z", "Manual request", head=OTHER)
    history = [_state_edit("completed", "2026-09-15T19:02:00Z", edited="2026-09-15T19:02:00Z"), other,
               _state_edit("running", "2026-09-15T19:00:01Z")]
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T19:10:00Z"))
    assert verdict == "wait", message
    assert f"review of {OTHER[:7]} (Manual request) started at 19:01:30Z" in message
    assert "abandoned from 2026-09-15T20:01:30Z" in message
    assert _verdict([_comment(history)], now=_at("2026-09-15T20:01:31Z"))[0] == "pass"


@pytest.mark.parametrize("unreadable_at, now, expected", [
    ("2026-09-15T19:01:00Z", "2026-09-15T19:10:00Z", "wait"),
    ("2026-09-15T19:01:00Z", "2026-09-15T21:30:00Z", "wait"),   # that completion never pairs, the hour over or not
    ("2026-09-15T17:30:00Z", "2026-09-15T19:10:00Z", "pass"),
])
def test_an_unreadable_version_inside_the_hour_may_hide_a_start(unreadable_at, now, expected):
    edits = _cycle()
    edits.append(_edit("pre-marker summary text", unreadable_at)) if unreadable_at < "2026-09-15T19:00:01Z" \
        else edits.insert(1, _edit("pre-marker summary text", unreadable_at))
    verdict, message = _verdict([_comment(edits)], now=_at(now))
    assert verdict == expected, message
    if now > "2026-09-15T20:01:00Z" and expected == "wait":
        assert "No later poll can pair it" in message and "fresh draft-to-ready transition" in message, message


@pytest.mark.parametrize("trigger, timeline_case", [("Draft marked ready", "ready"), ("Manual request", "manual")])
def test_a_completion_an_hour_or_more_after_its_start_pairs_with_nothing_and_names_the_way_out(trigger, timeline_case):
    # A run open for the hour counts as abandoned, so a completion exactly an hour after it began cannot be placed,
    # at any later poll; a fresh transition's review is the way out. No run in PRs 1380-1486 took over 21 minutes.
    late = [_state_edit("completed", "2026-09-15T20:05:01Z", trigger), _state_edit("running", "2026-09-15T19:05:01Z", trigger)]
    comments = [_comment(late + _cycle(start="2026-09-15T19:00:01Z", finish="2026-09-15T19:02:00Z"))]
    if timeline_case == "manual":
        comments.append(_request("2026-09-15T19:05:00Z"))
    verdict, message = _verdict(comments, now=_at("2026-09-15T23:00:00Z"))
    assert verdict == "wait" and "no start to pair with" in message, message
    assert "No later poll can pair it" in message and "fresh draft-to-ready transition" in message, message


def _flip_timeline(*events):
    return [{"event": event, "created_at": at} for event, at in events]


OVERLAPS = {
    # A draft flip while the first ready mark's review R1 runs: R2, the latest mark's own, fails first, then R1
    # completes clean. Pairing oldest first gave R1's completion to R2, so the gate passed on a run begun before
    # the latest ready mark (the correctness lens on this change; main waited).
    "flip, newer fails first": (
        [_state_edit("completed", "2026-09-15T19:04:00Z"), _state_edit("failed", "2026-09-15T19:03:00Z"),
         _state_edit("running", "2026-09-15T19:01:05Z"), _state_edit("running", "2026-09-15T19:00:01Z")],
        _flip_timeline(("ready_for_review", "2026-09-15T19:00:00Z"), ("convert_to_draft", "2026-09-15T19:01:00Z"),
                       ("ready_for_review", "2026-09-15T19:01:04Z")),
        (), "2026-09-15T19:05:00Z", "wait"),
    # The same on the manual path: after a clean ready cycle, M2 (the newest request's) fails, then M1 completes.
    "two requests, newer fails first": (
        [_state_edit("completed", "2026-09-15T19:08:00Z", "Manual request"),
         _state_edit("failed", "2026-09-15T19:07:00Z", "Manual request"),
         _state_edit("running", "2026-09-15T19:05:01Z", "Manual request"),
         _state_edit("running", "2026-09-15T19:03:01Z", "Manual request"),
         _state_edit("completed", "2026-09-15T19:02:00Z"), _state_edit("running", "2026-09-15T19:00:01Z")],
        READY_EVENTS, ("2026-09-15T19:05:00Z", "2026-09-15T19:03:00Z"), "2026-09-15T19:09:00Z", "wait"),
    # A flip inside the hour while R1 runs; R1 completes just past its hour while R2 still runs. R2 overlapped
    # R1, so the completion pairs with nothing, and the gate waits rather than pass on R2's behalf.
    "flip inside the hour, late completion": (
        [_state_edit("completed", "2026-09-15T20:00:30Z"), _state_edit("running", "2026-09-15T19:30:05Z"),
         _state_edit("running", "2026-09-15T19:00:01Z")],
        _flip_timeline(("ready_for_review", "2026-09-15T19:00:00Z"), ("convert_to_draft", "2026-09-15T19:30:00Z"),
                       ("ready_for_review", "2026-09-15T19:30:04Z")),
        (), "2026-09-15T20:01:00Z", "wait"),
    # The accepted risk, named in _replay: the flip made once R1 is an hour old, as the lesson says, and R1 then
    # completes more than an hour after it began while R2 runs. The replay cannot tell the two runs apart.
    "flip after the hour, late completion (accepted risk)": (
        [_state_edit("completed", "2026-09-15T20:06:00Z"), _state_edit("running", "2026-09-15T20:05:05Z"),
         _state_edit("running", "2026-09-15T19:00:01Z")],
        _flip_timeline(("ready_for_review", "2026-09-15T19:00:00Z"), ("convert_to_draft", "2026-09-15T20:05:00Z"),
                       ("ready_for_review", "2026-09-15T20:05:04Z")),
        (), "2026-09-15T20:07:00Z", "pass"),
}


@pytest.mark.parametrize("case", list(OVERLAPS))
def test_a_start_begun_while_another_of_its_head_and_trigger_was_open_never_takes_a_completion(case):
    history, timeline, requests, now, expected = OVERLAPS[case]
    comments = [_comment(history)] + [_request(at, id=3 + number) for number, at in enumerate(requests)]
    verdict, message = _verdict(comments, pr_timeline=timeline, now=_at(now))
    assert verdict == expected, message


@pytest.mark.parametrize("started, now, expected, named", [
    ("2026-09-15T19:01:31.5Z", "2026-09-15T20:01:31.4Z", "wait", "2026-09-15T20:01:32Z"),
    ("2026-09-15T19:01:31.5Z", "2026-09-15T20:01:32Z", "pass", None),
    ("2026-09-15T19:01:31Z", "2026-09-15T20:01:30.9Z", "wait", "2026-09-15T20:01:31Z"),
    ("2026-09-15T19:01:31Z", "2026-09-15T20:01:31Z", "pass", None),        # exactly an hour: abandoned
])
def test_a_start_counts_as_abandoned_from_the_second_its_wait_message_names(started, now, expected, named):
    # A start at 19:01:31.5 is an hour old at 20:01:31.5, so the message names the next whole second, 20:01:32,
    # and from that second on the start no longer blocks; a whole-second start stops blocking at its hour exactly.
    other = _state_edit("running", started, "Manual request", head=OTHER)
    history = [_state_edit("completed", "2026-09-15T19:02:00Z", edited="2026-09-15T19:02:00Z"), other,
               _state_edit("running", "2026-09-15T19:00:01Z")]
    verdict, message = _verdict([_comment(history)], now=_at(now))
    assert verdict == expected, message
    if named:
        assert f"abandoned from {named}" in message, message


def test_a_running_review_begun_during_another_says_at_once_that_it_cannot_count():
    # #1496's shape: a draft flip while the ready review runs. The new run can never pass, so the Running message
    # says so and names the way out, rather than promising its completion will count.
    history = [_state_edit("running", "2026-09-15T19:30:05Z"), _state_edit("running", "2026-09-15T19:00:01Z")]
    timeline = READY_EVENTS + [{"event": "convert_to_draft", "created_at": "2026-09-15T19:30:00Z"},
                               {"event": "ready_for_review", "created_at": "2026-09-15T19:30:04Z"}]
    verdict, message = _verdict([_comment(history)], pr_timeline=timeline, now=_at("2026-09-15T19:35:00Z"))
    assert verdict == "wait", message
    assert all(words in message for words in ("begun while another review", "its completion cannot count",
                                              "holds the gate until 2026-09-15T20:30:05Z",
                                              "fresh draft-to-ready transition")), message
    single = _verdict([_comment(history[1:])], now=_at("2026-09-15T19:35:00Z"))[1]
    assert "if it never completes it counts as abandoned from 2026-09-15T20:00:01Z" in single, single


def test_every_open_start_blocks_not_only_the_oldest():
    # One hung run long abandoned and another in flight: the one in flight still blocks.
    hung = _state_edit("running", "2026-09-15T17:30:00Z", "Manual request", head=OTHER)
    flight = _state_edit("running", "2026-09-15T19:01:30Z", "Manual request", head=OTHER)
    history = [_state_edit("completed", "2026-09-15T19:02:00Z", edited="2026-09-15T19:02:00Z"), flight,
               _state_edit("running", "2026-09-15T19:00:01Z"), hung]
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T19:10:00Z"))
    assert verdict == "wait" and "started at 19:01:30Z has not completed" in message, message


def test_an_unreadable_version_after_the_completion_blocks_until_its_hour_is_up():
    # A version the gate cannot read may hide a start, even after a clean completion and its security re-render.
    edits = _cycle()
    rerender = _edit(edits[0]["diff"], "2026-09-15T19:06:00Z")
    history = [rerender, _edit("pre-marker summary text", "2026-09-15T19:05:00Z")] + edits
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T19:10:00Z"))
    assert verdict == "wait" and "may hide a running review" in message, message
    assert _verdict([_comment(history)], now=_at("2026-09-15T20:05:00Z"))[0] == "pass"


def test_a_running_version_rendered_again_is_the_same_start():
    # A security review that starts while the code review runs re-renders its Running row; it is no second start.
    edits = _cycle()
    rerender = _edit(edits[1]["diff"], "2026-09-15T19:00:30Z")
    history = [edits[0], rerender, edits[1]]
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T19:10:00Z"))
    assert verdict == "pass", message


def test_a_start_begun_within_the_hour_after_an_unreadable_version_never_takes_a_completion():
    # The version at 19:00:30 may hide a start; the run begun at 19:59 could be that one's rival, so its completion,
    # just over the version's hour, cannot be placed: the run stays open for its hour, and the completion never pairs.
    history = [_state_edit("completed", "2026-09-15T20:01:00Z"), _state_edit("running", "2026-09-15T19:59:00Z"),
               _edit("pre-marker summary text", "2026-09-15T19:00:30Z")]
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T20:10:00Z"))
    assert verdict == "wait" and "started at 19:59:00Z while another review" in message, message
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T21:05:00Z"))
    assert verdict == "wait" and "no start to pair with" in message, message


def test_a_start_stamped_after_the_gates_clock_still_blocks():
    # A runner clock behind Codex's must not read a review that has just started as over.
    other = _state_edit("running", "2026-09-15T19:01:30Z", "Manual request", head=OTHER)
    history = [_state_edit("completed", "2026-09-15T19:02:00Z", edited="2026-09-15T19:02:00Z"), other,
               _state_edit("running", "2026-09-15T19:00:01Z")]
    verdict, message = _verdict([_comment(history)], now=_at("2026-09-15T19:01:20Z"))
    assert verdict == "wait" and "started at 19:01:30Z has not completed" in message, message


@pytest.mark.parametrize("now, words", [
    ("2026-09-15T19:30:00Z", ["since 19:00:01Z", "abandoned from 2026-09-15T20:00:01Z"]),
    ("2026-09-15T20:00:00.9Z", ["abandoned from 2026-09-15T20:00:01Z"]),
    ("2026-09-15T20:00:01Z", ["past the one-hour abandonment age"]),        # exactly an hour
    ("2026-09-15T20:05:00Z", ["past the one-hour abandonment age", "fresh draft-to-ready transition",
                              "no manual request"]),
])
def test_a_running_summary_names_when_it_counts_as_abandoned_and_the_remedy_after(now, words):
    running = [_state_edit("running", "2026-09-15T19:00:01Z")]
    verdict, message = _verdict([_comment(running)], now=_at(now))
    assert verdict == "wait"
    assert all(word in message for word in words), message


def test_main_judges_with_the_wall_clock_at_each_poll(monkeypatch, capsys):
    comment = _comment([_state_edit("running", "2026-09-15T19:00:01Z")])
    state = review_gate.State([comment], "body", [HEAD], False, None, (), CREATED, READY_EVENTS, HEAD)
    ticks = iter([0.0, 0.0, 10_000.0])
    monkeypatch.setenv("REVIEW_GATE_HEAD", HEAD)
    code = review_gate.main(fetch=lambda: state, resolve=lambda short: HEAD, sleep=lambda _: None,
                            clock=lambda: next(ticks), wall=lambda: _at("2026-09-15T20:05:00Z"))
    assert code == 1
    assert "past the one-hour abandonment age" in capsys.readouterr().out
    ticks = iter([0.0, 0.0, 10_000.0])
    code = review_gate.main(fetch=lambda: state, resolve=lambda short: HEAD, sleep=lambda _: None,
                            clock=lambda: next(ticks), wall=lambda: _at("2026-09-15T19:30:00Z"))
    assert code == 1
    assert "abandoned from 2026-09-15T20:00:01Z" in capsys.readouterr().out


def test_fetch_state_reads_trusted_timeline_and_only_current_summary_history(monkeypatch):
    latest = _comment(_cycle(), id=2, node_id="IC_latest", created_at="2026-09-15T18:45:00Z")
    older = _summary(COMPLETED, HEAD[:7])
    comments = [latest, older]
    calls = []
    monkeypatch.setattr(review_gate, "_github", lambda *a: {"draft": False, "created_at": CREATED})
    def paged(path, token):
        calls.append(path)
        return comments if path.endswith('/comments') else READY_EVENTS if path.endswith('/timeline') else []
    def history(node, token):
        assert (node, token) == ('IC_latest', 'token')
        return latest['review_history']
    monkeypatch.setattr(review_gate, '_paged', paged)
    monkeypatch.setattr(review_gate, '_fetch_history', history)
    state = review_gate.fetch_state('o/r', '7', 'token')
    assert state.created_at == CREATED and state.timeline == READY_EVENTS
    assert 'repos/o/r/issues/7/timeline' in calls


def test_history_pagination_is_complete_and_bounded_and_never_swallows_api_failure(monkeypatch):
    bodies = _cycle()
    calls = []
    def graphql(query, variables, token):
        assert 'userContentEdits(first: 100, after: $after)' in query and 'databaseId' in query
        calls.append(variables)
        index = 0 if variables['after'] is None else 1
        return {'node': {'userContentEdits': {'nodes': bodies[index:index+1], 'pageInfo': {
            'hasNextPage': index == 0, 'endCursor': 'next' if index == 0 else None}}}}
    monkeypatch.setattr(review_gate, '_graphql', graphql)
    assert review_gate._fetch_history('IC_1', 'token') == bodies
    assert calls == [{'id': 'IC_1', 'after': None}, {'id': 'IC_1', 'after': 'next'}]
    monkeypatch.setattr(review_gate, 'MAX_PAGES', 1)
    with pytest.raises(review_gate.EvidenceError, match='limit'):
        review_gate._fetch_history('IC_1', 'token')
    monkeypatch.setattr(review_gate, '_graphql', lambda *a: {'node': None})
    with pytest.raises(review_gate.EvidenceError):
        review_gate._fetch_history('IC_1', 'token')


def test_rest_pagination_limit_and_transport_failure_fail_closed(monkeypatch, capsys):
    monkeypatch.setattr(review_gate, 'MAX_PAGES', 1)
    monkeypatch.setattr(review_gate, '_github', lambda *a: [{}] * 100)
    with pytest.raises(review_gate.EvidenceError, match='limit'):
        review_gate._paged('path', 'token')
    monkeypatch.setenv('REVIEW_GATE_HEAD', HEAD)
    def unreadable():
        raise OSError('offline')
    assert review_gate.main(fetch=unreadable) == 1
    assert 'failed to read trusted GitHub evidence' in capsys.readouterr().out


@pytest.mark.parametrize("live", [None, "short", OTHER])
@pytest.mark.parametrize("body", ["body", OVERRIDE_LINE])
def test_live_head_must_match_job_even_with_an_override(live, body):
    verdict, message = _decide(HEAD, [_comment(_cycle())], body, [HEAD], pr_draft=False,
                               pr_timeline=READY_EVENTS, pr_head=live)
    assert verdict == "fail" and ("live" in message or "stale" in message)


def test_a_new_unedited_request_supersedes_an_old_edited_request():
    manual = _cycle(trigger="Manual request", start="2026-09-15T19:03:01Z", finish="2026-09-15T19:05:00Z")
    old = _request("2026-09-15T19:02:30Z", updated_at="2026-09-15T19:03:30Z", id=2)
    assert _verdict([_comment(manual + _cycle()), old, _request()])[0] == "pass"


def _mock_snapshot(monkeypatch, *, final_changes=None, fresh_extra=()):
    initial = {"draft": False, "created_at": CREATED, "head": {"sha": HEAD}, "title": "title", "body": "body",
               "updated_at": "2026-09-15T19:02:00Z"}
    pulls = iter([initial, {**initial, **(final_changes or {})}])
    monkeypatch.setattr(review_gate, "_github", lambda *a: next(pulls))
    comment = _comment(_cycle())
    comment_reads = iter([[comment], [{**comment}, *fresh_extra]])
    def paged(path, token):
        if path.endswith("/comments"):
            return next(comment_reads)
        return READY_EVENTS if path.endswith("/timeline") else [{"sha": HEAD}]
    monkeypatch.setattr(review_gate, "_paged", paged)
    monkeypatch.setattr(review_gate, "_fetch_history", lambda *a: comment["review_history"])


@pytest.mark.parametrize("change", [{"head": {"sha": OTHER}}, {"draft": True}, {"body": "new body"},
                                    {"title": "new title"}, {"updated_at": "2026-09-15T19:04:00Z"}])
def test_fetch_never_combines_old_head_or_ready_metadata_with_new_evidence(monkeypatch, change):
    _mock_snapshot(monkeypatch, final_changes=change)
    with pytest.raises(review_gate.SnapshotChanged):
        review_gate.fetch_state("o/r", "7", "token")


def test_manual_request_arriving_during_history_read_is_a_barrier(monkeypatch):
    _mock_snapshot(monkeypatch, fresh_extra=[_request()])
    state = review_gate.fetch_state("o/r", "7", "token")
    assert state.head == HEAD
    verdict, message = review_gate.decide(HEAD, state.comments, state.body, state.commits, pr_draft=state.draft,
                                          pr_created_at=state.created_at, pr_timeline=state.timeline, pr_head=state.head,
                                          now=NOW)
    assert verdict == "wait" and "latest manual" in message


def test_changed_snapshot_polls_again_but_api_errors_still_fail(monkeypatch, capsys):
    monkeypatch.setenv("REVIEW_GATE_HEAD", HEAD)
    attempts = []
    def fetch():
        attempts.append(1)
        if len(attempts) == 1:
            raise review_gate.SnapshotChanged("concurrent ready event")
        return _state([_summary(COMPLETED, HEAD[:7])], "body", [HEAD], False)
    sleeps = []
    assert review_gate.main(fetch=fetch, sleep=sleeps.append, clock=lambda: 0, wall=lambda: NOW) == 0
    assert len(attempts) == 2 and len(sleeps) == 1
    assert "concurrent ready event" in capsys.readouterr().out


@pytest.mark.parametrize("second, expected", [("00Z", "wait"), ("00.999999Z", "wait"), ("01Z", "pass")],
                         ids=["same-second-exact", "same-second-fractional", "next-second"])
@pytest.mark.parametrize("boundary", ["manual", "current-ready", "historical-ready", "opened-ready"])
def test_review_start_must_follow_the_whole_github_event_second(boundary, second, expected):
    """GitHub's recorded T can mean an event at T+.999999. A start at T or T+.999999 cannot prove
    it belongs to that event; T+1 can. This includes the ready cycle borrowed by a later new-head
    manual review, and uses the same conservative precision rule for a PR opened ready."""
    if boundary == "manual":
        cycle = _cycle(trigger="Manual request", start="2026-09-15T19:03:" + second,
                       finish="2026-09-15T19:05:00Z")
        comments = [_comment(cycle + _cycle()), _request()]
        verdict, message = _verdict(comments)
    elif boundary == "current-ready":
        verdict, message = _verdict([_comment(_cycle(start="2026-09-15T19:00:" + second))])
    elif boundary == "historical-ready":
        manual = _cycle(trigger="Manual request", start="2026-09-15T19:03:01Z", finish="2026-09-15T19:05:00Z")
        ready = _cycle(OTHER, start="2026-09-15T19:00:" + second)
        verdict, message = _verdict([_comment(manual + ready), _request()])
    else:
        opened = _cycle(trigger="PR opened", start="2026-09-15T18:40:" + second,
                        finish="2026-09-15T18:42:00Z")
        verdict, message = _verdict([_comment(opened)], pr_timeline=[])
    assert verdict == expected, message
