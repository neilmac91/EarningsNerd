"""The review gate (rule 12 for the review-wait lesson and the closing-keyword lesson): the decision is
pure, pinned offline, and the workflow that publishes it runs on every pull-request event without write
permissions. It never skips that job, because a skipped job counts as passing; a draft fails it instead."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import review_gate

ROOT = Path(__file__).resolve().parents[3]
HEAD = "a834193192d007ed9b5c35e895aa532dcbb757bc"


CODEX_USER = {"login": "chatgpt-codex-connector[bot]", "type": "Bot", "id": 199175422}


CREATED = "2026-09-15T18:40:00Z"
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
    assert review_gate.main(fetch=lambda: _state(*next(states)), sleep=sleeps.append, clock=lambda: next(ticks, 10.0)) == 0
    assert sleeps == [5.0]
    # Timeout: the review never completes for this head; the failure names the remedy.
    ticks = iter([0.0, 0.0, 30.0, 70.0])
    assert review_gate.main(fetch=lambda: _state([_summary(COMPLETED, "7547ef1")], "body", [HEAD], False), sleep=sleeps.append,
                            clock=lambda: next(ticks, 70.0)) == 1
    out = capsys.readouterr().out
    assert "timed out after 1 minutes" in out and "@codex review" in out and "Review override" in out
    # A draft, or an unreadable draft flag, fails on the first read without waiting, though the head
    # has a completed review. The clock advances, so a regression that waits times out instead of hanging.
    for draft, expected in ((True, "is a draft"), (None, "failing closed")):
        sleeps.clear()
        ticks = iter([0.0, 0.0, 70.0])
        assert review_gate.main(fetch=lambda: _state([_summary(COMPLETED, "a834193")], "body", [HEAD], draft),
                                sleep=sleeps.append, clock=lambda: next(ticks, 70.0)) == 1
        assert sleeps == [] and expected in capsys.readouterr().out
    # A closing keyword in the title or a commit message fails on the first read too, while the review
    # still runs: main hands decide the whole state, not only the body.
    for title, messages in (("close #12", ()), ("", (("d" * 40, "fixes #12"),))):
        sleeps.clear()
        ticks = iter([0.0, 0.0, 70.0])
        state = ([_summary(RUNNING, "a834193")], "body", [HEAD], False, title, messages)
        assert review_gate.main(fetch=lambda: _state(*state), sleep=sleeps.append, clock=lambda: next(ticks, 70.0)) == 1
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
                                          pr_created_at=state.created_at, pr_timeline=state.timeline, pr_head=state.head)
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
    assert review_gate.main(fetch=fetch, sleep=sleeps.append, clock=lambda: 0) == 0
    assert len(attempts) == 2 and len(sleeps) == 1
    assert "concurrent ready event" in capsys.readouterr().out
