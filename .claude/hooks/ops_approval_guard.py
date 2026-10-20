"""PreToolUse hook: refuse a session's call to GitHub's deployment-review API, so only the founder
approves an Ops apply.

`.github/workflows/ops.yml` holds every -apply operation (relabel-fy-apply, repair-ticker-apply,
reset-filing-summary-apply) in its approve-apply job, which runs in the `ops-apply` environment whose
required reviewer is the founder. Sessions act on GitHub through the founder's account, so GitHub would
take a session's approval for the founder's own. This hook stops a session giving one.

.claude/settings.json runs it before every Bash command. A command line is refused when one of its
commands, read as the shell reads it (codex_mention_guard.py's reader: compound lines, command
substitutions, here-documents), calls the GitHub API (`gh api`, or curl, wget or httpie naming
api.github.com) and names the deployment-review API in its words or in a file it sends: a run's
`pending_deployments` (approve or reject a wait on an environment), a `deployment_protection_rule`
review, or GraphQL's `approveDeployments` and `rejectDeployments`. Reading a pending review is refused
too; the run's own status shows it is waiting. Text that only names the API (a commit message, a
comment body) passes.

A refusal is a JSON deny on stdout; anything else exits 0 with no output. A crash exits 1, which
Claude Code reports as a hook error and lets the call through, as for codex_mention_guard.py.

Not checked: a call a program makes as it runs (a script, a variable, a command another shell runs),
a GitHub MCP tool (none reviews a deployment), a session that loads no repository hooks, Codex and
Astra sessions, and the founder's own approval, which is the point.
Tests: backend/tests/unit/test_ops_approval_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I leaves the hooks directory off sys.path
import codex_mention_guard as shell  # noqa: E402  its shell reader, shared rather than copied

REVIEW_API = re.compile(r"pending_deployments|deployment_protection_rule|approvedeployments|rejectdeployments", re.I)
CLIENTS = {"curl", "wget", *shell.HTTPIE}
REASON = (
    "Refused by .claude/hooks/ops_approval_guard.py: this command calls GitHub's deployment-review API, "
    "which approves or rejects a run waiting on an environment. Only the founder approves an Ops apply "
    "(the ops-apply environment in .github/workflows/ops.yml), on the run's page: ask them to."
)


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
    if not (REVIEW_API.search(plain) or "gh" in plain or shell.GITHUB_API in plain.lower()):
        return None  # names neither the API nor a client that could send a file naming it
    script = shell._script(command)
    calls = [words for _operator, words in shell._commands(shell._command_tokens(script)) if _calls_the_api(words)]
    if any(REVIEW_API.search(word) for words in calls for word in words):
        return REASON
    if calls and any(REVIEW_API.search(body) for body in shell._files_sent(script, event.get("cwd"))):
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
