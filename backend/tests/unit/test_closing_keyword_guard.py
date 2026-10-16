"""Gate for `.claude/hooks/closing_keyword_guard.py`, the PreToolUse hook that refuses an agent's merge whose
typed commit title or message puts a closing keyword before an issue or pull request reference
(lessons/ops-closing-keywords-close-what-they-name.md; review-gate covers the pull request's own text).

Each case runs the hook the way `.claude/settings.json` registers it: the registered command, through the
shell, with CLAUDE_PROJECT_DIR set, on the event Claude Code sends. A refusal is a JSON deny on stdout with
exit 0; a call let through exits 0 with no output. The registration is pinned too, and a hook the shell
cannot run exits 1 (a hook error Claude Code does not block on), never Python's own exit 2. The hook matches
with review-gate's own `closing_references`, so the gate's cases are replayed through it. The gaps the
lesson names are planted as cases that pass through, so closing one is a deliberate change here.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from tests.unit.test_review_gate import CLOSING_CASES

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/closing_keyword_guard.py" || exit 1'
MATCHER = "^(Bash|mcp__.*[Gg][Ii][Tt][Hh][Uu][Bb].*)$"
MERGE = "mcp__github__merge_pull_request"


def _registered() -> list[dict]:
    """The PreToolUse entries of .claude/settings.json that run the guard."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        entry for entry in settings["hooks"]["PreToolUse"]
        if any("closing_keyword_guard.py" in hook.get("command", "") for hook in entry["hooks"])
    ]


def _run(stdin: str, project_dir: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """Run the command .claude/settings.json registers, as Claude Code does (`/bin/sh -c`), within its timeout."""
    [hook] = [hook for entry in _registered() for hook in entry["hooks"]]
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    return subprocess.run(["sh", "-c", hook["command"]], input=stdin, capture_output=True, text=True, env=env,
                          timeout=hook["timeout"])


def _event(tool: str, tool_input: object, cwd: Path = ROOT) -> str:
    return json.dumps({
        "session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
        "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_1",
    })


def _decision(tool: str, tool_input: object, cwd: Path = ROOT) -> dict | None:
    proc = _run(_event(tool, tool_input, cwd))
    assert proc.returncode == 0, proc.stderr
    if not proc.stdout:
        return None
    parsed = json.loads(proc.stdout)
    # Nothing beside the decision: a top-level "continue": false, for one, would stop Claude's turn.
    assert list(parsed) == ["hookSpecificOutput"]
    output = parsed["hookSpecificOutput"]
    assert sorted(output) == ["hookEventName", "permissionDecision", "permissionDecisionReason"]
    assert output["hookEventName"] == "PreToolUse"
    return output


def _refused(tool: str, tool_input: object, cwd: Path = ROOT) -> str:
    output = _decision(tool, tool_input, cwd)
    assert output is not None and output["permissionDecision"] == "deny", output
    reason = output["permissionDecisionReason"]
    assert "closing_keyword_guard.py" in reason and "closing keyword" in reason and "by hand after the merge" in reason
    return reason


@pytest.fixture
def bodies(tmp_path: Path) -> Path:
    (tmp_path / "msg.md").write_text("Squash of the series.\n\nFixes #3.\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("Squash of the series; #3 carries the fix.\n", encoding="utf-8")
    (tmp_path / "body.json").write_text('{"merge_method": "squash", "commit_message": "resolves #3"}', encoding="utf-8")
    return tmp_path


# The GitHub MCP server's merge tools, with the commit text a merge types.
MCP_REFUSED = {
    "a squash message": (MERGE, {"pullNumber": 5, "merge_method": "squash", "commit_message": "Reviewed and fixed: #1156"}),
    "a squash title": (MERGE, {"pullNumber": 5, "commit_title": "test: close #1177's open findings (#1243)"}),
    "an escaped number sign": (MERGE, {"pullNumber": 5, "commit_message": "fixed \\#3"}),
    "an auto-merge headline": ("mcp__github__enable_pr_auto_merge", {"pullNumber": 5, "commit_headline": "resolves #3"}),
    "an auto-merge body": ("mcp__github__enable_pr_auto_merge", {"pullNumber": 5, "commit_body": "Closes #3"}),
    "another server named for github": ("mcp__plugin_GitHub-tools__merge_pull_request", {"commit_message": "fix #3"}),
}
MCP_PASSED = {
    "no typed message": (MERGE, {"pullNumber": 5, "merge_method": "squash"}),
    "a clean message": (MERGE, {"pullNumber": 5, "commit_title": "ci: gate (#1351)", "commit_message": "#3 carries the fix"}),
    "a pull request body, which review-gate reads": ("mcp__github__update_pull_request", {"pullNumber": 5, "body": "Fixes #3"}),
    "a comment": ("mcp__github__add_issue_comment", {"issue_number": 5, "body": "closes #3 once merged"}),
}
BASH_REFUSED = (
    "gh pr merge 5 --squash --body 'Closes #3'",
    "gh pr merge 5 --squash -b \"fixed: #1156\"",
    "gh pr merge 5 --squash --subject 'close #3' --body ok",
    "gh pr merge 5 --squash -t 'resolves #3'",
    "gh -R neilmac91/EarningsNerd pr merge 5 --squash --body 'fix #3'",
    "gh pr --repo=o/r merge 5 --squash --body 'fixes o/r#3'",
    "/usr/local/bin/gh pr merge 5 -s -b 'fixes #3'",
    "sudo gh pr merge 5 -s -b 'fixes #3'",
    "gh 'pr' 'mer''ge' 5 -s -b 'fixes #3'",
    "gh pr merge 5 -s --body-file msg.md",
    "gh pr merge 5 -s -F msg.md",
    "gh pr merge 5 -s --body-file=msg.md",
    "gh pr merge 5 -s -Fmsg.md",
    "gh pr merge 5 -s --body-file - <<'EOF'\nSquash.\n\nfixes #3\nEOF",
    "cd backend && gh pr merge 5 -s -b 'resolved #3'",
    "gh api -X PUT repos/o/r/pulls/5/merge -f merge_method=squash -f commit_message='fixes #3'",
    "curl -X PUT https://api.github.com/repos/o/r/pulls/5/merge -d '{\"commit_message\": \"closes #3\"}'",
    "gh api repos/o/r/merges -f base=main -f head=topic -f commit_message='fix #3'",
    "gh api -X PUT repos/o/r/pulls/5/merge -F commit_message=@msg.md",
    "gh api -X PUT repos/o/r/pulls/5/merge --input body.json",
    "curl -X PUT -d @body.json https://api.github.com/repos/o/r/pulls/5/merge",
)
BASH_PASSED = (
    "gh pr merge 5 --squash",
    "gh pr merge 5 --squash --delete-branch",
    "gh pr merge 5 -s -b '#3 carries the fix; addressed in #4'",
    "gh pr merge 5 -s --body-file clean.md",
    "gh pr view 5 --json body | grep -c 'fixes #3'",  # not a merge: review-gate reads the pull request's own text
    "git merge origin/main -m 'fixes #3'",  # a branch commit: review-gate reads the pull request's commits
    "gh pr comment 5 --body 'closes #3 once merged'",
    "ls -la",
    "echo merge",
)
# The stated gaps: text a command builds as it runs, a server named otherwise, another shell.
GAPS = (
    ("Bash", {"command": "gh pr merge 5 -s -b \"$MSG\""}),
    ("Bash", {"command": "gh pr merge 5 -s -b \"$(cat msg.md)\""}),
    ("Bash", {"command": "bash -c \"$(printf 'gh pr merge 5 -s -F %s' msg.md)\""}),
    ("mcp__gh__merge_pull_request", {"commit_message": "fixes #3"}),
)


@pytest.mark.parametrize("tool, tool_input", MCP_REFUSED.values(), ids=list(MCP_REFUSED))
def test_a_merge_tool_call_typing_a_closing_reference_is_refused(tool: str, tool_input: dict) -> None:
    _refused(tool, tool_input)


@pytest.mark.parametrize("tool, tool_input", MCP_PASSED.values(), ids=list(MCP_PASSED))
def test_a_merge_without_one_and_every_other_github_call_go_through(tool: str, tool_input: dict) -> None:
    assert _decision(tool, tool_input) is None


@pytest.mark.parametrize("command", BASH_REFUSED)
def test_a_bash_merge_typing_a_closing_reference_is_refused(command: str, bodies: Path) -> None:
    _refused("Bash", {"command": command}, cwd=bodies)


@pytest.mark.parametrize("command", BASH_PASSED)
def test_other_bash_commands_and_clean_merges_go_through(command: str, bodies: Path) -> None:
    assert _decision("Bash", {"command": command}, cwd=bodies) is None


@pytest.mark.parametrize("tool, tool_input", GAPS)
def test_text_built_as_the_command_runs_and_a_server_named_otherwise_are_stated_gaps(
        tool: str, tool_input: dict, bodies: Path) -> None:
    assert _decision(tool, tool_input, cwd=bodies) is None


@pytest.mark.parametrize("case, title, body, messages, draft, expected", CLOSING_CASES,
                         ids=[row[0] for row in CLOSING_CASES])
def test_the_hook_reads_with_review_gates_own_pattern(case, title, body, messages, draft, expected) -> None:
    """Every case review-gate pins, typed as a squash message, gets the same verdict from the hook."""
    text = "\n\n".join([title, body, *(message for _, message in messages)]).strip()
    output = _decision(MERGE, {"pullNumber": 5, "commit_message": text})
    if expected is None:
        assert output is None, output
    else:  # the gate labels a reference by where it found it; the hook's text is one commit message
        reference = expected.split('"')[1] if '"' in expected else expected
        assert output is not None and reference in output["permissionDecisionReason"]


def test_a_large_command_is_read_inside_the_timeout() -> None:
    command = "gh pr merge 5 -s -b 'ok' && echo " + "fix-" * 250_000
    started = time.monotonic()
    assert _decision("Bash", {"command": command}) is None
    assert time.monotonic() - started < 5


@pytest.mark.parametrize("event", ["", "not json", "[]", json.dumps({"tool_name": "Bash"}),
                                   json.dumps({"tool_name": MERGE, "tool_input": "fixes #3"})])
def test_an_event_of_another_shape_goes_through(event: str) -> None:
    proc = _run(event)
    assert proc.stdout == ""
    assert proc.returncode in (0, 1)  # a hook error (1) lets the call through; 2 would refuse it


def test_a_hook_that_cannot_run_is_a_hook_error_never_a_refusal(tmp_path: Path) -> None:
    # No hook at the path: Python exits 2, which Claude Code would read as a refusal of every Bash command;
    # the registered command maps it to 1, a hook error Claude Code reports without blocking.
    proc = _run(_event("Bash", {"command": "gh pr merge 5 -s -b 'fixes #3'"}), project_dir=tmp_path)
    assert proc.returncode == 1 and proc.stdout == ""


def test_the_hook_is_registered_before_bash_and_every_github_tool() -> None:
    assert _registered() == [{"matcher": MATCHER, "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}]}]
