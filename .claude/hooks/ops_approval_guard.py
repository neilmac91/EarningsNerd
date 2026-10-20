"""PreToolUse hook: refuse a session's call to GitHub's deployment-review API, so only the founder
approves an Ops apply.

`.github/workflows/ops.yml` holds every -apply operation (relabel-fy-apply, repair-ticker-apply,
reset-filing-summary-apply) in its approve-apply job, which runs in the `ops-apply` environment whose
required reviewer is the founder. Sessions act on GitHub through the founder's account, so GitHub would
take a session's approval for the founder's own. This hook stops a session giving one.

.claude/settings.json runs it before every Bash command. A command line is refused when one of its
commands, read as the shell reads it (codex_mention_guard.py's reader: compound lines, command
substitutions, backquotes), calls the GitHub API (`gh api`, or curl, wget or httpie naming
api.github.com), and the line, here-documents, substitutions and variables included, names the
deployment-review or environment API: a run's `pending_deployments` (approve or reject a wait on an
environment), a `deployment_protection_rule` review, an `/environments` path (which could drop the
environment's reviewer), or GraphQL's `approveDeployments`, `rejectDeployments`,
`createEnvironment`, `updateEnvironment` or `deleteEnvironment`; or when a GraphQL call (gh's
`graphql` or `/graphql` path, or a URL naming api.github.com/graphql) sends a file that names one of
those mutations. A file's other text passes, so a GraphQL reply whose body names `pending_deployments`
goes through. Reading those paths is refused too; the run's own status shows it is waiting. A line
that makes no API call passes whatever it names (a commit message, a here-document written to a file,
`gh pr comment --body-file`). On a line that makes one, a name anywhere refuses the line, in a
comment's text or in a here-document that writes the file the call sends, so the refusal says how to
send such text instead: write the file in an earlier Bash call or with the Write tool, then send it
in a Bash call of its own.

A refusal is a JSON deny on stdout; anything else exits 0 with no output. A crash exits 1, which
Claude Code reports as a hook error and lets the call through, as for codex_mention_guard.py.

Not checked: a call a program makes as it runs (a script, or a command another shell runs with
`bash -c`), a GraphQL query read from a file that an earlier command on the same line writes (the
hook reads a file before the line runs), a GitHub MCP tool (none reviews a deployment), a session
that loads no repository hooks, Codex and Astra sessions, and the founder's own approval, which is
the point.
Tests: backend/tests/unit/test_ops_approval_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I leaves the hooks directory off sys.path
import codex_mention_guard as shell  # noqa: E402  its shell reader, shared rather than copied

MUTATIONS = r"(?:approve|reject)Deployments|(?:create|update|delete)Environment"  # GraphQL's
REVIEW_NAMES = re.compile(
    r"pending_deployments|deployment_protection_rule|/environments(?![A-Za-z0-9_-])|" + MUTATIONS, re.I)
SENT_MUTATIONS = re.compile(MUTATIONS, re.I)  # what a file a GraphQL call sends is searched for
CLIENTS = {"curl", "wget", *shell.HTTPIE}
REASON = (
    "Refused by .claude/hooks/ops_approval_guard.py: this command calls GitHub's deployment-review or "
    "environment API, which approves or rejects a run waiting on an environment or changes who must approve. "
    "Only the founder approves an Ops apply (the ops-apply environment in .github/workflows/ops.yml), on the "
    "run's page: ask them to. If this line only names the API in text, write that text to a file in an "
    "earlier Bash call or with the Write tool, then send it in a Bash call of its own (`gh api … -F "
    "body=@file.md`, `gh pr comment --body-file`), or send it through a GitHub MCP tool."
)


def _is_graphql(words: list[str]) -> bool:
    """gh sends both `graphql` and `/graphql` to the GraphQL endpoint; a URL can name it too."""
    return any(word in ("graphql", "/graphql") or f"{shell.GITHUB_API}/graphql" in word.lower() for word in words)


def _calls_the_api(words: list[str]) -> bool:
    """`gh ... api`, or an HTTP client naming api.github.com, wherever it stands (`sudo gh api`)."""
    names = [word.rsplit("/", 1)[-1] for word in words]
    if "gh" in names and "api" in names[names.index("gh") + 1:]:
        return True
    return any(name in CLIENTS for name in names) and any(shell.GITHUB_API in word.lower() for word in words)


def refusal(event: object) -> str | None:
    """Why this tool call must not run, or None to let it through."""
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return None
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return None
    plain = command.replace("\\\n", "").translate(shell.UNQUOTE)  # no quotes, backslashes or continuations
    if "gh" not in plain and shell.GITHUB_API not in plain.lower():
        return None  # no GitHub API client on the line
    script = shell._script(command)
    calls = [words for _operator, words in shell._commands(shell._command_tokens(script)) if _calls_the_api(words)]
    if not calls:
        return None
    # The whole line: a path or a query can arrive through a variable, a pipe or a here-document.
    if REVIEW_NAMES.search(plain):
        return REASON
    graphql = any(_is_graphql(words) for words in calls)
    if graphql and any(SENT_MUTATIONS.search(body) for body in shell._files_sent(script, event.get("cwd"))):
        return REASON
    return None


def main() -> int:
    reason = refusal(json.load(sys.stdin.buffer))
    if reason is not None:
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
        json.dump({"hookSpecificOutput": decision}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
