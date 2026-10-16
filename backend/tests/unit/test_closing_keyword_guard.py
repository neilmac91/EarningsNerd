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
import signal
import subprocess
import uuid
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


def _run(stdin: str, project_dir: Path = ROOT, env: dict[str, str] | None = None,
         command: str | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    """Run the command .claude/settings.json registers, as Claude Code does (`/bin/sh -c`), within its timeout.

    The shell starts a session of its own, and a timeout kills that whole process group: killing only the shell
    would leave the hook it started running, holding a CPU, after the test has failed."""
    [hook] = [hook for entry in _registered() for hook in entry["hooks"]]
    env = {**os.environ, **(env or {}), "CLAUDE_PROJECT_DIR": str(project_dir)}
    with subprocess.Popen(["sh", "-c", command or hook["command"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, env=env, start_new_session=True) as proc:
        try:
            stdout, stderr = proc.communicate(stdin, timeout=timeout or hook["timeout"])
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)


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
    (tmp_path / "ref-first.md").write_text("#3 carries the rest.\n", encoding="utf-8")  # a message after a title
    (tmp_path / "title.md").write_text("ci: lint fix\n", encoding="utf-8")  # a title before such a message
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
    # GitHub writes the commit as its title, a blank line, then its message.
    "a title that ends in a keyword before a message that starts with a reference": (
        MERGE, {"pullNumber": 5, "commit_title": "ci: lint fix", "commit_message": "#12 carries the rest"}),
    "the message typed before the title": (
        MERGE, {"pullNumber": 5, "commit_message": "#12 carries the rest", "commit_title": "ci: lint fix"}),
    "a server's own names for title and message, in order": (
        MERGE, {"pullNumber": 5, "title": "ci: lint fix", "message": "#12 carries the rest"}),
    "GraphQL's headline and body in variables": ("mcp__github__run_graphql", {
        "query": "mutation($input: MergePullRequestInput!) { mergePullRequest(input: $input) { clientMutationId } }",
        "variables": {"input": {"pullRequestId": "X", "commitHeadline": "lint fix", "commitBody": "#3 carries the rest"}}}),
    "GraphQL variables that give the headline and body, the body's first": ("mcp__github__run_graphql", {
        "query": "mutation($b: String!, $h: String!) { mergePullRequest(input: {pullRequestId: \"X\", commitBody: $b, "
                 "commitHeadline: $h}) { clientMutationId } }",
        "variables": {"b": "#3 carries the rest", "h": "lint fix"}}),
    "a GraphQL body as a JSON string, with a headline and body": ("mcp__github__api_request", {
        "method": "POST", "path": "/graphql", "body": json.dumps({"query": (
            'mutation { mergePullRequest(input: {pullRequestId: "X", commitHeadline: "lint fix", '
            'commitBody: "#3 carries the rest"}) { clientMutationId } }')})}),
    # A field's quoted value read as GraphQL decodes it, on its own: a keyword after an escaped line break.
    "an escaped line break before a keyword in a GraphQL body": ("mcp__github__run_graphql", {
        "query": 'mutation { mergePullRequest(input: {pullRequestId: "X", commitBody: "Squash of the series.\\n\\n'
                 'Fixes #3"}) { clientMutationId } }'}),
    "the same in a JSON-string request body": ("mcp__github__api_request", {
        "method": "POST", "path": "/graphql", "body": json.dumps({"query": (
            'mutation { mergePullRequest(input: {pullRequestId: "X", commitBody: "Squash of the series.\\n\\n'
            'Fixes #3"}) { clientMutationId } }')})}),
    "a JSON body's title and message": ("mcp__github__api_request", {
        "method": "PUT", "path": "/repos/o/r/pulls/5/merge",
        "body": '{"commit_title": "lint fix", "commit_message": "#3 carries the rest"}'}),
    "a REST URL without its scheme": ("mcp__github__api_request", {
        "method": "PUT", "url": "api.github.com/repos/o/r/pulls/5/merge", "body": {"commit_message": "fixes #3"}}),
    "a request whose query names a merge mutation": ("mcp__github__api_request", {
        "query": "mutation($input: MergePullRequestInput!) { mergePullRequest(input: $input) { clientMutationId } }",
        "variables": {"input": {"pullRequestId": "X", "commitHeadline": "fixes #3"}}}),
    "a request tool's REST merge path": ("mcp__github__api_request", {
        "method": "PUT", "path": "/repos/o/r/pulls/5/merge", "body": {"commit_message": "fixes #3"}}),
    "a request tool's merges endpoint": ("mcp__github__api_request", {
        "endpoint": "POST repos/o/r/merges", "body": {"base": "main", "head": "t", "commit_message": "fixes #3"}}),
    "a request tool's GraphQL field": ("mcp__github__api_request", {
        "graphql": '# merge\nmutation { mergePullRequest(input: {pullRequestId: "X", commitHeadline: "fixes #3"}) { clientMutationId } }'}),
    # A request tool's merge in the shapes GitHub's docs and clients write it.
    "a request tool's templated route": ("mcp__github__api_request", {
        "route": "PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge", "owner": "o", "repo": "r", "pull_number": 5,
        "commit_message": "fixes #3"}),
    "a request tool's URL with a query string": ("mcp__github__api_request", {
        "method": "PUT", "url": "https://api.github.com/repos/o/r/pulls/5/merge?x=1", "body": {"commit_message": "fixes #3"}}),
    "a request tool's path below its repository": ("mcp__github__api_request", {
        "owner": "o", "repo": "r", "method": "PUT", "path": "pulls/5/merge", "body": {"commit_message": "fixes #3"}}),
    "a request tool's GraphQL body as a JSON string": ("mcp__github__api_request", {
        "method": "POST", "path": "/graphql", "body": '{"query": "mutation { mergePullRequest(input: {pullRequestId: \\"X\\", commitHeadline: \\"fixes #3\\"}) { clientMutationId } }"}'}),
    "a JSON request with no endpoint": ("mcp__github__api_request", {
        "method": "POST", "body": '{"query": "mutation { mergePullRequest(input: {pullRequestId: \\"X\\", commitHeadline: \\"fixes #3\\"}) { clientMutationId } }"}'}),
    "a batched GraphQL request beside the endpoint": ("mcp__github__api_request", {
        "url": "https://api.github.com/graphql", "data": '[{"query": "mutation { mergePullRequest(input: {pullRequestId: \\"X\\", commitHeadline: \\"fixes #3\\"}) { clientMutationId } }"}]'}),
    "a GraphQL document with a fragment first": ("mcp__github__run_graphql", {
        "query": 'fragment F on PullRequest { id }\nmutation { mergePullRequest(input: {pullRequestId: "X", '
                 'commitHeadline: "fixes #3"}) { clientMutationId } }'}),
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
    "a search that starts with a GraphQL keyword but calls nothing": (
        "mcp__github__search_code", {"query": "query mergePullRequest closes #3"}),
    "a comment that names the GraphQL endpoint and a merge call": ("mcp__github__add_issue_comment", {
        "issue_number": 5, "body": "POST /graphql with mergePullRequest(commitHeadline: 'fixes #3') is refused."}),
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
    # A title that ends in a keyword before a message that starts with a reference, joined as GitHub joins them.
    "gh pr merge 5 -s --subject 'review-gate fix' --body '#12 carries the rest'",
    "gh pr merge 5 -s --body '#12 carries the rest' --subject 'lint fix'",
    "gh pr merge 5 -s -t'lint fix' -b'#12 carries the rest'",
    "bash -c 'gh pr merge 5 -s -t \"lint fix\" -b \"#12 carries the rest\"'",  # a word that is itself a line
    "gh pr merge 5 -s -t 'lint fix' -F ref-first.md",
    "gh api -X PUT repos/o/r/pulls/5/merge -f commit_title='lint fix' -f commit_message='#3 carries the rest'",
    "curl -X PUT https://api.github.com/repos/o/r/pulls/5/merge "
    "-d '{\"commit_title\": \"lint fix\", \"commit_message\": \"#3 carries the rest\"}'",
    "gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"X\", commitHeadline: \"lint fix\", "
    "commitBody: \"#3 carries the rest\"}) { clientMutationId } }'",
    # The message as an agent types one: over several lines, quoted or in a here-document.
    "gh pr merge 5 -s -t 'lint fix' -b \"$(cat <<'EOF'\n#3 carries the rest.\n\nMore detail.\nEOF\n)\"",
    "gh pr merge 5 -s -t 'lint fix' --body-file - <<'EOF'\n#3 carries the rest.\nEOF",
    "gh pr merge 5 -s -t 'lint fix' -F - <<-EOF\n\t#3 carries the rest.\n\tEOF",
    "gh pr merge 5 -s --subject 'lint fix' --body '#3 carries the rest.\n\nMore detail.'",
    "gh pr merge 5 -s --subject \"lint fix\" --body \"#3 carries the rest.\n\nMore detail.\"",
    # A field's name=value read as the shell passes the word, quoted whole or escaped, the option attached or not.
    "gh api -X PUT repos/o/r/pulls/5/merge -f 'commit_title=lint fix' -f 'commit_message=#3 carries the rest'",
    "gh api -X PUT repos/o/r/pulls/5/merge --field=\"commit_title=lint fix\" --field=\"commit_message=#3 carries the rest\"",
    "gh api -X PUT repos/o/r/pulls/5/merge -f commit_title=lint\\ fix -f commit_message=\\#3\\ carries\\ the\\ rest",
    "gh api -X PUT repos/o/r/pulls/5/merge -F commit_title=@title.md -f commit_message='#3 carries the rest'",
    "http PUT api.github.com/repos/o/r/pulls/5/merge 'commit_title=lint fix' 'commit_message=#3 carries the rest'",
    # JSON and GraphQL strings with their quotes escaped, decoded; GraphQL variables a field or a JSON body gives.
    "curl -X PUT https://api.github.com/repos/o/r/pulls/5/merge "
    "-d \"{\\\"commit_title\\\": \\\"lint fix\\\", \\\"commit_message\\\": \\\"#3 carries the rest\\\"}\"",
    "gh api graphql -f query=\"mutation { mergePullRequest(input: {pullRequestId: \\\"X\\\", commitHeadline: \\\"lint fix\\\", "
    "commitBody: \\\"#3 carries the rest\\\"}) { clientMutationId } }\"",
    "gh api graphql -f query='mutation($h: String!, $b: String!) { mergePullRequest(input: {pullRequestId: \"X\", "
    "commitHeadline: $h, commitBody: $b}) { clientMutationId } }' -f h='lint fix' -f b='#3 carries the rest'",
    "gh api graphql -f query='mutation($h: String!, $b: String!) {\n  mergePullRequest(input: {pullRequestId: \"X\", "
    "commitHeadline: $h, commitBody: $b}) {\n    clientMutationId\n  }\n}' -f h='lint fix' -f b='#3 carries the rest'",
    "curl -X POST https://api.github.com/graphql -d '{\"query\": \"mutation($h: String!) { mergePullRequest(input: "
    "{pullRequestId: \\\"X\\\", commitHeadline: $h, commitBody: \\\"#3 carries the rest\\\"}) { clientMutationId } }\", "
    "\"variables\": {\"h\": \"lint fix\"}}'",
    "python3 -c \"import requests; requests.put('https://api.github.com/repos/o/r/pulls/5/merge', "
    "json={'commit_title': 'lint fix', 'commit_message': '#3 carries the rest'})\"",
    "python3 -c \"import requests; requests.put('https://api.github.com/repos/o/r/pulls/5/merge', "
    "json=dict(commit_title='lint fix', commit_message='#3 carries the rest'))\"",
    # A field's quoted value read as its language decodes it, on its own: a keyword after an escaped line break.
    "gh api graphql -f query='mutation { mergePullRequest(input: {pullRequestId: \"X\", "
    "commitBody: \"Squash of the series.\\n\\nFixes #3\"}) { clientMutationId } }'",
    "python3 -c \"import requests; requests.put('https://api.github.com/repos/o/r/pulls/5/merge', "
    "json={'commit_message': 'Squash of the series.\\n\\nFixes #3'})\"",
    # gh api's nested key for a field of a GraphQL input variable.
    "gh api graphql -f query='mutation($input: MergePullRequestInput!) { mergePullRequest(input: $input) "
    "{ clientMutationId } }' -f 'input[pullRequestId]=X' -f 'input[commitHeadline]=lint fix' "
    "-f 'input[commitBody]=#3 carries the rest'",
    # A here-string's text as a message; a value filled from one file a plain cat or `<` reads.
    "gh pr merge 5 -s -t 'lint fix' --body-file - <<< '#3 carries the rest'",
    "gh pr merge 5 -s -t \"$(cat title.md)\" -b '#3 carries the rest'",
    "gh pr merge 5 -s -t \"$(<title.md)\" -b '#3 carries the rest'",
    "gh api -X PUT repos/o/r/pulls/5/merge -f commit_title=\"$(cat title.md)\" -f commit_message='#3 carries the rest'",
    # gh keeps a flag's last value: a title given first and last, with 16 others between.
    "gh pr merge 5 -s -t 'lint fix' " + " ".join(f"-t t{n}" for n in range(16)) + " -t 'lint fix' -b '#3 carries the rest'",
    "gh pr merge 5 -s -F=msg.md",  # pflag drops an `=` after a short option
    "gh pr merge 5 -sF=msg.md",
    "gh pr merge 5 -sFCOMMIT_MSG.md",
    "gh pr merge 5 -s '-F' msg.md",  # an option quoted or escaped as a whole word
    "gh pr merge 5 -s \"--body-file=msg.md\"",
    "gh pr merge 5 -s \"--body-file=my notes.md\"",
    "gh pr merge 5 -s -\\F msg.md",
    "'cat' msg.md | gh pr merge 5 -s -F -",
    "gh pr merge 5 -s -b \"$(\\cat msg.md)\"",  # a cat that skips an alias, inside a quoted substitution
    "gh pr merge 5 -s -b \"$('cat' msg.md)\"",
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
    "http PUT api.github.com/repos/o/r/pulls/5/merge commit_message=\"@my notes.md\"",  # quoted after `=`
    "wget --method=PUT --body-file=body.json https://api.github.com/repos/o/r/pulls/5/merge",
    "wget --post-file=query.json https://api.github.com/graphql",
    "curl -X PUT -K curl.cfg https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --config curl.cfg https://api.github.com/repos/o/r/pulls/5/merge",
    "curl -X PUT --variable msg@msg.md --expand-data '{{msg}}' https://api.github.com/repos/o/r/pulls/5/merge",
    "python3 -c \"import requests; requests.put('https://api.github.com/repos/o/r/pulls/5/merge', "
    "json={'commit_message': 'fixes #3'})\"",
    "python3 -c 'import subprocess; subprocess.run([\"gh\", \"pr\", \"merge\", \"5\", \"-b\", \"fixes #3\"])'",
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
    "gh pr merge 5 -s --subject 'ci: lint' --body '#12 carries the fix'",  # the title does not end in a keyword
    # A title with a space before its end, read whole: "Fix the parser (#12)" then "#3 ..." closes nothing.
    "gh api -X PUT repos/o/r/pulls/5/merge -f commit_title='Fix the parser (#12)' -f commit_message='#3 follows up on it'",
    "curl -X PUT https://api.github.com/repos/o/r/pulls/5/merge "
    "-d '{\"commit_title\": \"Fix the parser (#12)\", \"commit_message\": \"#3 follows up on it\"}'",
    "gh pr merge 5 -s -t 'Fix the parser (#12)' -b \"$(cat <<'EOF'\n#3 follows up on it.\nEOF\n)\"",
    "python3 -c \"import requests; requests.put('https://api.github.com/repos/o/r/pulls/5/merge', "
    "json={'commit_title': 'Fix the parser (#12)', 'commit_message': '#3 follows up on it'})\"",
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
# otherwise, a merge whose URL sits in a file a command reads as its configuration, an MCP request tool that
# spreads a merge's target over fields, a brace expansion, more than three -R in a row, a title past the last 16
# a call types, a keyword and a reference more than 1,024 characters from where a title and its message meet, a
# typed half whose other half is GitHub's default. A file over 1 MiB and a glob's files past its first 16 have tests
# of their own.
GAPS = (
    ("Bash", {"command": "gh pr merge 5 -s -b \"$MSG\""}),
    ("Bash", {"command": "gh pr merge 5 -s -b $'fixes \\x233'"}),
    ("Bash", {"command": "gh pr merge 5 -s -b \"$(head -n 5 msg.md)\""}),
    ("Bash", {"command": "sed 's/x/y/' msg.md | gh pr merge 5 -s -F -"}),
    ("Bash", {"command": "bash -c \"$(printf 'gh pr merge 5 -s -F %s' msg.md)\""}),
    ("Bash", {"command": "cd .. && gh pr merge 5 -s -F {here}/msg.md"}),  # {here}: the body files' directory
    ("Bash", {"command": "./merge.sh 5"}),
    ("Bash", {"command": "gh m 5 -s -b 'fixes #3'"}),  # `gh alias set m 'pr merge'`
    ("Bash", {"command": "gh pr merge 5 -s -F {msg,clean}.md"}),  # a brace expansion
    ("Bash", {"command": "gh -R a -R b -R c -R d pr merge 5 -s -b 'fixes #3'"}),  # more than three -R in a row
    ("Bash", {"command": "gh pr merge 5 -s -t 'lint fix' " + " ".join(f"-t t{n}" for n in range(16))
              + " -b '#3 carries the rest'"}),  # a title past the last 16; gh writes the last
    ("Bash", {"command": "gh pr merge 5 -s -t 'lint fix' -b '" + " " * 1100 + "#3 carries the rest'"}),  # past 1,024
    ("Bash", {"command": "gh pr merge 5 --merge --body '#3 carries the rest'"}),  # GitHub's default title
    (MERGE, {"pullNumber": 5, "commit_title": "lint fix"}),  # GitHub's default message
    ("Bash", {"command": "curl -K merge.cfg"}),
    ("Bash", {"command": "wget -i urls.txt --method=PUT --body-file=body.json"}),
    ("mcp__github__api_request", {  # a request tool that spreads the merge's target over fields of its own
        "method": "PUT", "owner": "o", "repo": "r", "pull_number": 5, "action": "merge", "commit_message": "fixes #3"}),
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


def test_a_glob_counts_only_files_toward_its_first_16(bodies: Path) -> None:
    for number in range(20):
        (bodies / f"d{number:02}.md").mkdir()  # directories that sort before the one file
    (bodies / "z.md").write_text("Fixes #3.\n", encoding="utf-8")
    _refused("Bash", {"command": "gh pr merge 5 -s -F [dz]*.md"}, cwd=bodies)


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


# Lines of about 1 MB built to make a reader backtrack, each read inside the hook's registered timeout (_run's
# subprocess timeout), or the call would go through as a hook error. A merge line runs every file reader; a
# line that names "merge" but no merge makes each detector search all of it.
MERGE_LINE = "gh pr merge 5 -s -b ok"
ADVERSARIAL = {
    "fix-": MERGE_LINE + " && echo " + "fix-" * 250_000,
    "options": MERGE_LINE + " -" * 500_000,
    "redirects": MERGE_LINE + " <" * 500_000,
    "quotes": MERGE_LINE + " 'a'" * 250_000,
    "quoted options": MERGE_LINE + " '-F' x" * 150_000,
    "cat words": MERGE_LINE + " cat x" * 200_000,
    "attached values": MERGE_LINE + " -sbx" * 250_000,
    "quoted @ fields": MERGE_LINE + " 'k=@" * 250_000,
    "backslashes": MERGE_LINE + " \\" * 500_000,
    "@ words": MERGE_LINE + " @" * 500_000,
    "one long word": MERGE_LINE + " " + "a" * 1_000_000,
    "distinct titles and bodies": MERGE_LINE + "".join(f" -t t{n} -b b{n}" for n in range(60_000)),
    "here-documents": MERGE_LINE + " <<a\n" * 200_000,
    "here-strings": MERGE_LINE + " <<<a" * 200_000,
    "multi-line quotes": MERGE_LINE + " '\n" * 300_000,
    "words with spaces": MERGE_LINE + " 'a b'" * 200_000,
    "words that are merge lines": MERGE_LINE + " 'gh pr merge -t x'" * 50_000,
    # 16 titles by 16 here-documents of nearly 1 MB each, in HTML entities review-gate decodes: only each title's
    # end and each message's start are joined (all of each took over 30 s).
    "titles and here-documents": MERGE_LINE + "".join(f" -t t{n} <<w{n}\n" for n in range(16)) + "&lt;\n" * 190_000,
    "JSON words": MERGE_LINE + " {x}" * 250_000,
    "commit strings": MERGE_LINE + ' commitBody: "x"' * 60_000,
    "fields": MERGE_LINE + "".join(f" -f commit_title=t{n} -f commit_message=@m{n}" for n in range(30_000)),
    "GraphQL variables": "gh api graphql -f query='mutation { mergePullRequest(input: {" + "commitBody: $b " * 60_000
                         + "}) }'" + " -f b=x" * 20_000,
    "-R words, no merge": "echo merge; gh" + " -R gh" * 170_000,
    "gh api words, no merge": "echo merge; gh api" + " gh api x" * 100_000,
    "graphql words, no mutation": "echo graphql; gh api graphql" + " -f q=graphql" * 80_000,
}


# Merges of about 1 MB that close an issue, each refused inside the hook's timeout, so a hook that skipped a large
# line or call would fail here: the commonest long merge is a squash message typed in a here-document.
LARGE_REFUSED = {
    "a here-document message": ("Bash", {"command": "gh pr merge 5 --squash --body-file - <<'EOF'\n"
                                                    + "Squash of the series.\n" * 45_000 + "Fixes #3.\nEOF"}),
    "a quoted body": ("Bash", {"command": "gh pr merge 5 -s -b '" + "x " * 500_000 + "fixes #3'"}),
    "a field after many": ("Bash", {"command": "gh api -X PUT repos/o/r/pulls/5/merge" + " -f k=v" * 140_000
                                               + " -f commit_message='fixes #3'"}),
    "16 titles by 16 here-documents, then a closing line": ("Bash", {"command": MERGE_LINE + "".join(
        f" -t t{n} <<w{n}\n" for n in range(16)) + "&lt;\n" * 190_000 + "Fixes #3\n"}),
    "an MCP squash message": (MERGE, {"pullNumber": 5, "commit_message": "Squash of the series.\n" * 45_000
                                      + "Fixes #3."}),
    "an MCP GraphQL body with escaped line breaks": ("mcp__github__run_graphql", {
        "query": 'mutation { mergePullRequest(input: {pullRequestId: "X", commitBody: "' + "Squash.\\n" * 100_000
                 + 'Fixes #3"}) { clientMutationId } }'}),
}


@pytest.mark.parametrize("command", ADVERSARIAL.values(), ids=list(ADVERSARIAL))
def test_a_large_command_is_read_inside_the_hooks_timeout(command: str, tmp_path: Path) -> None:
    assert _decision("Bash", {"command": command}, cwd=tmp_path) is None  # an empty directory: no file to read


@pytest.mark.parametrize("tool, tool_input", LARGE_REFUSED.values(), ids=list(LARGE_REFUSED))
def test_a_large_merge_is_read_to_its_end_inside_the_hooks_timeout(tool: str, tool_input: dict, tmp_path: Path) -> None:
    _refused(tool, tool_input, cwd=tmp_path)


@pytest.mark.parametrize("event", ["", "not json", "[]", json.dumps({"tool_name": "Bash"}),
                                   json.dumps({"tool_name": MERGE, "tool_input": "fixes #3"})])
def test_an_event_of_another_shape_goes_through(event: str) -> None:
    proc = _run(event)
    assert proc.stdout == ""
    assert proc.returncode in (0, 1)  # a hook error (1) lets the call through; 2 would refuse it


def test_a_timed_out_hook_is_stopped_with_its_shell() -> None:
    # A hook past its timeout is killed with the shell that started it, so a slow mutant or regression fails
    # its test without leaving a process behind to starve the rest of the run.
    marker = f"closing-guard-timeout-{uuid.uuid4().hex}"
    with pytest.raises(subprocess.TimeoutExpired):
        _run("", command=f"python3 -c 'import time; time.sleep(60)' {marker} || exit 1", timeout=1)
    processes = subprocess.run(["ps", "-eww", "-o", "args"], capture_output=True, text=True, check=True).stdout
    assert marker not in processes


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
