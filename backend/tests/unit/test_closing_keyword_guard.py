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
import re
import subprocess
from pathlib import Path

import pytest

from tests.unit.test_review_gate import CLOSING_CASES

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/closing_keyword_guard.py" || exit 1'
MATCHER = "^(Bash|Monitor|mcp__.*[Gg][Ii][Tt][Hh][Uu][Bb].*)$"
MERGE = "mcp__github__merge_pull_request"


def _registered() -> list[dict]:
    """The PreToolUse entries of .claude/settings.json that run the guard."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [
        entry for entry in settings["hooks"]["PreToolUse"]
        if any("closing_keyword_guard.py" in hook.get("command", "") for hook in entry["hooks"])
    ]


def _run(stdin: str, project_dir: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the command .claude/settings.json registers, as Claude Code does (`/bin/sh -c`), within its timeout."""
    [hook] = [hook for entry in _registered() for hook in entry["hooks"]]
    env = {**os.environ, **(env or {}), "CLAUDE_PROJECT_DIR": str(project_dir)}
    return subprocess.run(["sh", "-c", hook["command"]], input=stdin, capture_output=True, text=True, env=env,
                          timeout=hook["timeout"])


def _event(tool: str, tool_input: object, cwd: Path = ROOT) -> str:
    return json.dumps({
        "session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
        "hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "tool_use_id": "toolu_1",
    })


def _decision(tool: str, tool_input: object, cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict | None:
    proc = _run(_event(tool, tool_input, cwd), env=env)
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


def _refused(tool: str, tool_input: object, cwd: Path = ROOT, env: dict[str, str] | None = None) -> str:
    output = _decision(tool, tool_input, cwd, env)
    assert output is not None and output["permissionDecision"] == "deny", output
    reason = output["permissionDecisionReason"]
    assert "closing_keyword_guard.py" in reason and "closing keyword" in reason and "by hand after the merge" in reason
    return reason


@pytest.fixture
def bodies(tmp_path: Path) -> Path:
    (tmp_path / "msg.md").write_text("Squash of the series.\n\nFixes #3.\n", encoding="utf-8")
    (tmp_path / "my notes.md").write_text("Closes #3.\n", encoding="utf-8")
    (tmp_path / "COMMIT_MSG.md").write_text("Fixes #3.\n", encoding="utf-8")  # capitals after an attached -F
    (tmp_path / "clean.md").write_text("Squash of the series; #3 carries the fix.\n", encoding="utf-8")
    (tmp_path / "body.json").write_text('{"merge_method": "squash", "commit_message": "resolves #3"}', encoding="utf-8")
    (tmp_path / "automerge.graphql").write_text(
        'mutation { enablePullRequestAutoMerge(input: {pullRequestId: "X", commitBody: "resolves #3"}) '
        "{ clientMutationId } }\n", encoding="utf-8")
    (tmp_path / "notes[1].md").write_text("Fixes #3.\n", encoding="utf-8")  # a glob's text, quoted or escaped
    (tmp_path / "notes1.md").write_text("#3 carries the fix.\n", encoding="utf-8")  # what the glob matches
    (tmp_path / "odd[2].md").write_text("Fixes #3.\n", encoding="utf-8")  # a glob that matches nothing
    (tmp_path / "curl.cfg").write_text('data = "{\\"commit_message\\": \\"fixes #3\\"}"\n', encoding="utf-8")
    (tmp_path / "merge.cfg").write_text(
        'url = "https://api.github.com/repos/o/r/pulls/5/merge"\nrequest = "PUT"\n'
        'data = "{\\"commit_message\\": \\"fixes #3\\"}"\n', encoding="utf-8")
    (tmp_path / "urls.txt").write_text("https://api.github.com/repos/o/r/pulls/5/merge\n", encoding="utf-8")
    (tmp_path / "note.md").write_text("Try `gh pr merge 5 -s -b 'fixes #3'`: the hook refuses it.\n", encoding="utf-8")
    (tmp_path / "query.json").write_text(
        '{"query": "mutation { mergePullRequest(input: {pullRequestId: \\"X\\", commitHeadline: \\"fixes #3\\"}) '
        '{ clientMutationId } }"}', encoding="utf-8")
    return tmp_path


# The GitHub MCP server's merge tools, with the commit text a merge types.
MCP_REFUSED = {
    "a squash message": (MERGE, {"pullNumber": 5, "merge_method": "squash", "commit_message": "Reviewed and fixed: #1156"}),
    "a squash title": (MERGE, {"pullNumber": 5, "commit_title": "test: close #1177's open findings (#1243)"}),
    "an escaped number sign": (MERGE, {"pullNumber": 5, "commit_message": "fixed \\#3"}),
    "a GraphQL-named headline": (MERGE, {"pullNumber": 5, "commitHeadline": "resolves #3"}),
    "a GraphQL runner handed a merge mutation": ("mcp__github__run_graphql", {
        "query": "mutation($input: MergePullRequestInput!) { mergePullRequest(input: $input) { clientMutationId } }",
        "variables": {"input": {"pullRequestId": "X", "commitBody": "Closes #3"}}}),
    "another server named for github": ("mcp__plugin_GitHub-tools__merge_pull_request", {"commit_message": "fix #3"}),
    "a merge tool's field under another name": (MERGE, {"pullNumber": 5, "message": "fixes #3"}),
    "a request whose query names a merge mutation": ("mcp__github__api_request", {
        "query": "mutation($input: MergePullRequestInput!) { mergePullRequest(input: $input) { clientMutationId } }",
        "variables": {"input": {"pullRequestId": "X", "commitHeadline": "fixes #3"}}}),
    "a request tool's REST merge path": ("mcp__github__api_request", {
        "method": "PUT", "path": "/repos/o/r/pulls/5/merge", "body": {"commit_message": "fixes #3"}}),
    "a request tool's merges endpoint": ("mcp__github__api_request", {
        "endpoint": "POST repos/o/r/merges", "body": {"base": "main", "head": "t", "commit_message": "fixes #3"}}),
    "a request tool's GraphQL field": ("mcp__github__api_request", {
        "graphql": '# merge\nmutation { mergePullRequest(input: {pullRequestId: "X", commitHeadline: "fixes #3"}) { clientMutationId } }'}),
    "a GraphQL tool's document": ("mcp__github__graphql", {
        "document": 'mutation { mergePullRequest(input: {pullRequestId: "X", commitHeadline: "fixes #3"}) { clientMutationId } }'}),
}
MCP_PASSED = {
    "no typed message": (MERGE, {"pullNumber": 5, "merge_method": "squash"}),
    "auto-merge, which types no message": ("mcp__github__enable_pr_auto_merge", {"pullNumber": 5, "mergeMethod": "SQUASH"}),
    "a clean message": (MERGE, {"pullNumber": 5, "commit_title": "ci: gate (#1351)", "commit_message": "#3 carries the fix"}),
    "a pull request body, which review-gate reads": ("mcp__github__update_pull_request", {"pullNumber": 5, "body": "Fixes #3"}),
    "a comment": ("mcp__github__add_issue_comment", {"issue_number": 5, "body": "closes #3 once merged"}),
    "a search, not a merge tool": ("mcp__github__search_pull_requests", {"query": "is:merged fixes #3"}),
    "a GraphQL runner without a merge mutation": ("mcp__github__run_graphql", {
        "query": 'mutation { addComment(input: {subjectId: "X", body: "closes #3 once merged"}) { clientMutationId } }'}),
    "a branch commit, which review-gate reads": (
        "mcp__github__create_or_update_file", {"path": "a.md", "content": "x", "message": "fixes #3", "branch": "t"}),
    # A mutation's name outside a GraphQL request is text, not a merge: a file's content, a comment.
    "a file that names a merge mutation": ("mcp__github__create_or_update_file", {
        "path": "t.py", "content": "mergePullRequest(commitHeadline: 'fixes #3')", "message": "test", "branch": "t"}),
    "a comment that names a merge mutation": ("mcp__github__add_issue_comment", {
        "issue_number": 5, "body": "A mergePullRequest with commitHeadline 'fixes #3' is refused."}),
    "a file whose text holds a merge document": ("mcp__github__create_or_update_file", {
        "path": "t.py", "branch": "t", "message": "test",
        "content": 'CASE = "mutation { mergePullRequest(input: {commitHeadline: \\"fixes #3\\"}) { clientMutationId } }"'}),
    "a comment that names a merge endpoint": ("mcp__github__add_issue_comment", {
        "issue_number": 5, "body": "PUT /repos/o/r/pulls/5/merge with 'fixes #3' is refused."}),
    "a search whose query names a merge mutation": ("mcp__github__search_code", {"query": "mergePullRequest fixes #3"}),
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
    "echo 5 | xargs gh pr merge -s -b 'fixes #3'",
    "(gh pr merge 5 -s -b 'fixes #3')",
    "out=$(gh pr merge 5 -s -b 'fixes #3')",
    "echo `gh pr merge 5 -s -b 'fixes #3'`",
    "gh 'pr' 'mer''ge' 5 -s -b 'fixes #3'",
    "gh pr merge 5 -s -b 'clo''ses #3'",  # the keyword is whole only once the shell removes the quotes
    "gh pr merge 5 -s -b fi\"x\"ed\\ \\#3",
    "gh pr merge 5 -s -b fix\\\nes\\ \\#3",  # a line continuation the shell joins inside the keyword
    "gh pr merge 5 -s -b\"Fixes \"#3",  # a value attached to -b or -t, after any run of short flags
    "gh pr merge 5 -s -bFixes\\ \\#3",
    "gh pr merge 5 -sbFixes\\ \\#3",
    "gh pr merge 5 -s -tFixes\\ \\#3 -b ok",
    # Naming a merge is enough: a comment that quotes one is refused too, and the reason says to send such
    # text from a file (the --body-file look-alike below passes).
    "gh pr comment 5 --body \"try gh pr merge 5 -s -b 'fixes #3'\"",
    "gh pr merge 5 -s --body-file msg.md",
    "gh pr merge 5 -s -F msg.md",
    "gh pr merge 5 -s --body-file=msg.md",
    "gh pr merge 5 -s -Fmsg.md",
    "gh pr merge 5 -sF msg.md",
    "gh pr merge 5 -s -FCOMMIT_MSG.md",  # the option is the first F, T or K, not the last
    "gh pr merge 5 -sFCOMMIT_MSG.md",
    "gh pr merge 5 -s '-F' msg.md",  # an option quoted or escaped as a whole word
    "gh pr merge 5 -s \"--body-file=msg.md\"",
    "gh pr merge 5 -s -\\F msg.md",
    "'cat' msg.md | gh pr merge 5 -s -F -",
    "gh pr merge 5 -s -d --body-file msg.md",  # -d is --delete-branch, never the value of the next option
    "gh pr merge 5 -s -d -F msg.md",
    "gh pr merge 5 -s -F - < msg.md",
    "gh pr merge 5 -s --body-file /dev/stdin < msg.md",
    "cat msg.md | gh pr merge 5 -s -F -",
    "cat clean.md msg.md | gh pr merge 5 -s -F -",  # each file a plain cat reads, wherever it sits
    "/bin/cat msg.md | gh pr merge 5 -s -F -",
    "gh pr merge 5 -s -b \"$(cat msg.md)\"",
    "gh pr merge 5 -s -b \"`cat msg.md`\"",
    "gh pr merge 5 -s --body-file <(cat msg.md)",
    "gh pr merge 5 -s -b \"$(<msg.md)\"",
    "gh pr merge 5 -s -F my\\ notes.md",  # a name as the shell passes it: escapes resolved, globs expanded
    "gh pr merge 5 -s -F 'my notes.md'",
    "gh pr merge 5 -s -F 'my notes'.md",  # a word of quoted and plain pieces
    "gh pr merge 5 -s -F ./\"msg.md\"",
    "gh pr merge 5 -s -F 'notes[1].md'",  # a quoted or escaped glob character is literal
    "gh pr merge 5 -s -F notes\\[1\\].md",
    "gh pr merge 5 -s -F odd[2].md",  # a glob that matches nothing is passed as written
    "gh pr merge 5 -s --body-file \\\nmsg.md",
    "gh pr merge 5 -s -F m*.md",
    "gh pr merge 5 -s --body-file - <<'EOF'\nSquash.\n\nfixes #3\nEOF",
    "cd backend && gh pr merge 5 -s -b 'resolved #3'",
    "bash -c 'gh pr merge 5 -s -b \"fixes #3\"'",  # another shell, handed the line as written
    "gh api -X PUT repos/o/r/pulls/5/merge -f merge_method=squash -f commit_message='fixes #3'",
    "curl -X PUT https://api.github.com/repos/o/r/pulls/5/merge -d '{\"commit_message\": \"closes #3\"}'",
    "gh api repos/o/r/merges -f base=main -f head=topic -f commit_message='fix #3'",
    "gh api -X PUT repos/o/r/pulls/5/merge -F commit_message=@msg.md",
    "gh api -X PUT repos/o/r/pulls/5/merge --field commit_message=@msg.md",
    "gh api -X PUT repos/o/r/pulls/5/merge --input body.json",
    "gh api -X PUT repos/o/r/pulls/5/merge --input=body.json",
    "gh api -X PUT repos/o/r/pulls/5/merge '--input' body.json",
    "curl -X PUT \"-d@body.json\" https://api.github.com/repos/o/r/pulls/5/merge",
    "gh api -X PUT repos/o/r/pulls/5/merge --input - < body.json",
    "curl -X PUT -d @body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT -d@body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT -d '@body.json' https://api.github.com/repos/o/r/pulls/5/merge",
    "gh api -X PUT repos/o/r/pulls/5/merge -F 'commit_message=@my notes.md'",
    "gh api -X PUT repos/o/r/pulls/5/merge --field=\"commit_message=@my notes.md\"",
    "curl -X PUT --upload-file=body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --data @body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --data-binary @body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --json @body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT -T body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT https://API.GitHub.com/repos/o/r/pulls/5/merge -d '{\"commit_message\": \"closes #3\"}'",
    "gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"X\", commitHeadline: \"fixes #3\"}) "
    "{ clientMutationId } }'",
    "gh api graphql -F query=@automerge.graphql",
    "curl -X POST -d @query.json https://api.github.com/graphql",
    "http PUT api.github.com/repos/o/r/pulls/5/merge commit_message=@msg.md",
    "wget --method=PUT --body-file=body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "wget --post-file=query.json https://api.github.com/graphql",
    "curl -X PUT -K curl.cfg https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --config curl.cfg https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --variable msg@msg.md --expand-data '{{msg}}' https://api.github.com/repos/o/r/pulls/5/merge",
    "python3 -c \"import requests; requests.put('https://api.github.com/repos/o/r/pulls/5/merge', "
    "json={'commit_message': 'fixes #3'})\"",
)
BASH_PASSED = (
    "gh pr merge 5 --squash",
    "gh pr merge 5 --squash --delete-branch",
    "gh pr merge 5 -s -d",
    # A plain -d or --field value is the data itself, not a file: curl sends "body.json", not its text.
    "curl -X PUT -d body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "gh api -X PUT repos/o/r/pulls/5/merge --field commit_message=msg.md",
    "gh pr merge 5 -s -b '#3 carries the fix; addressed in #4'",
    "gh pr merge 5 -s --body-file clean.md",
    "gh pr merge 5 -s -F notes[1].md",  # the glob matches notes1.md, the file the shell passes
    "gh pr comment 5 --body-file note.md",  # text that quotes a merge, sent from a file
    "gh pr view 5 --json body | grep -c 'fixes #3'",  # not a merge: review-gate reads the pull request's own text
    "git merge origin/main -m 'fixes #3'",  # a branch commit: review-gate reads the pull request's commits
    "gh pr comment 5 --body 'closes #3 once merged'",
    # GraphQL without a merge mutation: a query, and a comment that names a reference.
    "gh api graphql -f query='query { repository(owner: \"o\", name: \"r\") { issue(number: 3) { title } } }'",
    "gh api graphql -f query='mutation { addComment(input: {subjectId: \"X\", body: \"closes #3 once merged\"}) "
    "{ clientMutationId } }'",
    "ls -la",
    "echo merge",
)
# The stated gaps, one per form the hook's docstring names: text the shell or a command builds as the line
# runs (a variable, an ANSI-C escape, any command's output but a plain cat's, a line handed to another shell
# that way), a file named relative to a directory the line changes into, a script, a gh alias, a server named
# otherwise, a merge whose URL sits in a file a command reads as its configuration. A file over 1 MiB and a
# glob's files past its first 16 have tests of their own.
GAPS = (
    ("Bash", {"command": "gh pr merge 5 -s -b \"$MSG\""}),
    ("Bash", {"command": "gh pr merge 5 -s -b $'fixes \\x233'"}),
    ("Bash", {"command": "gh pr merge 5 -s -b \"$(head -n 5 msg.md)\""}),
    ("Bash", {"command": "sed 's/x/y/' msg.md | gh pr merge 5 -s -F -"}),
    ("Bash", {"command": "bash -c \"$(printf 'gh pr merge 5 -s -F %s' msg.md)\""}),
    ("Bash", {"command": "cd .. && gh pr merge 5 -s -F {here}/msg.md"}),  # {here}: the body files' directory
    ("Bash", {"command": "./merge.sh 5"}),
    ("Bash", {"command": "gh m 5 -s -b 'fixes #3'"}),  # `gh alias set m 'pr merge'`
    ("Bash", {"command": "curl -K merge.cfg"}),
    ("Bash", {"command": "wget -i urls.txt --method=PUT --body-file=body.json"}),
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
    if "command" in tool_input:
        tool_input = {"command": tool_input["command"].replace("{here}", bodies.name)}
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


def test_a_monitor_runs_its_command_through_the_shell_as_bash_does(bodies: Path) -> None:
    monitor = {"command": "gh pr merge 5 -s -F msg.md", "description": "merge", "timeout_ms": 1000}
    _refused("Monitor", monitor, cwd=bodies)
    assert _decision("Monitor", {**monitor, "command": "gh pr merge 5 -s"}, cwd=bodies) is None


def test_a_glob_is_read_to_its_first_16_files_in_the_c_locales_order(bodies: Path) -> None:
    for number in range(40):
        (bodies / f"part{number}.md").write_text(f"Fixes #{100 + number}.\n", encoding="utf-8")
    reason = _refused("Bash", {"command": "gh pr merge 5 -s -F part*.md"}, cwd=bodies)
    first = {int(name[4:-3]) for name in sorted(f"part{number}.md" for number in range(40))[:16]}
    assert {number for number in range(40) if f"#{100 + number}" in reason} == first


def test_a_glob_under_a_directory_whose_name_has_glob_characters_is_read(bodies: Path) -> None:
    here = bodies / "dir[x]"
    here.mkdir()
    (here / "msg.md").write_text("Fixes #3.\n", encoding="utf-8")
    _refused("Bash", {"command": "gh pr merge 5 -s -F m*.md"}, cwd=here)


def test_a_body_file_under_home_is_read(bodies: Path) -> None:
    _refused("Bash", {"command": "gh pr merge 5 -s --body-file ~/msg.md"}, env={"HOME": str(bodies)})


def test_a_file_just_under_the_cap_is_read_to_its_end(bodies: Path) -> None:
    tail = "\nFixes #3.\n"
    (bodies / "long.md").write_text("x" * ((1 << 20) - len(tail)) + tail, encoding="utf-8")
    assert (bodies / "long.md").stat().st_size == 1 << 20
    _refused("Bash", {"command": "gh pr merge 5 -s -F long.md"}, cwd=bodies)


def test_a_file_over_the_cap_and_a_pipe_are_not_read(bodies: Path) -> None:
    (bodies / "big.md").write_text("Fixes #3.\n" + "x" * (1 << 20), encoding="utf-8")
    assert _decision("Bash", {"command": "gh pr merge 5 -s -F big.md"}, cwd=bodies) is None
    os.mkfifo(bodies / "pipe.md")  # opened, it would wait for a writer past the hook's timeout
    assert _decision("Bash", {"command": "gh pr merge 5 -s -F pipe.md"}, cwd=bodies) is None


def test_a_large_command_is_read_inside_the_hooks_timeout() -> None:
    # _run gives the hook the timeout .claude/settings.json registers; a slower read fails with TimeoutExpired.
    command = "gh pr merge 5 -s -b 'ok' && echo " + "fix-" * 250_000
    assert _decision("Bash", {"command": command}) is None


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
    # Claude Code tests a matcher holding regex characters as an unanchored regular expression, as re.search
    # does: it reaches every tool the cases above send, and no tool that runs nothing.
    matcher = re.compile(MATCHER)
    reached = {"Bash", "Monitor", *(tool for tool, _ in [*MCP_REFUSED.values(), *MCP_PASSED.values()])}
    assert sorted(tool for tool in reached if not matcher.search(tool)) == []
    assert [tool for tool in ("Edit", "Write", "Read", "BashOutput", "mcp__Claude_Docs__update") if matcher.search(tool)] == []
