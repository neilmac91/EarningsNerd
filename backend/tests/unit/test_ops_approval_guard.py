"""Gate for `.claude/hooks/ops_approval_guard.py`, the PreToolUse hook that refuses a session's call to
GitHub's deployment-review API, so only the founder approves an Ops apply (the `ops-apply` environment
in `.github/workflows/ops.yml`).

Each case runs the hook as `.claude/settings.json` registers it: the registered command, through the
shell, with CLAUDE_PROJECT_DIR set, on the event Claude Code sends. A refusal is a JSON deny on stdout
with exit 0; a call let through exits 0 with no output. Text that names the API passes when it
travels by a route that is not an API call on the same line.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/ops_approval_guard.py" || exit 1'
RUNS = "repos/neilmac91/EarningsNerd/actions/runs/39360634523"


def _registered() -> list[dict]:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [entry for entry in settings["hooks"]["PreToolUse"]
            if any("ops_approval_guard.py" in hook.get("command", "") for hook in entry["hooks"])]


def _decision(tool: str, tool_input: object, cwd: Path = ROOT) -> dict | None:
    [hook] = [hook for entry in _registered() for hook in entry["hooks"]]
    event = json.dumps({"session_id": "s", "cwd": str(cwd), "hook_event_name": "PreToolUse", "tool_name": tool,
                        "tool_input": tool_input, "tool_use_id": "toolu_1"})
    proc = subprocess.run(["sh", "-c", hook["command"]], input=event, capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}, timeout=hook["timeout"])
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)["hookSpecificOutput"] if proc.stdout else None


def test_the_guard_runs_before_every_bash_command():
    assert _registered() == [{"matcher": "^Bash$", "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}]}]


@pytest.mark.parametrize("command", [
    f"gh api -X POST {RUNS}/pending_deployments -F 'environment_ids[]=1' -f state=approved -f comment=ok",
    f"gh api {RUNS}/pending_deployments",  # reading one is refused too
    f"cd /tmp && gh api --method POST {RUNS}/pending_'deploy'ments -f state=rejected",  # quotes split the name
    f"curl -sS -X POST -H 'Authorization: Bearer x' https://api.github.com/{RUNS}/pending_deployments -d @body.json",
    f"wget --method=POST -O- https://api.github.com/{RUNS}/pending_deployments",
    f"http POST https://api.github.com/{RUNS}/pending_deployments state=approved",
    f"sudo /usr/bin/gh api {RUNS}/deployment_protection_rule -f environment_name=ops-apply -f state=approved",
    f"echo $(gh api -X POST {RUNS}/pending_deployments -f state=approved)",
    f"echo `gh api -X POST {RUNS}/pending_deployments -f state=approved`",
    f"EP={RUNS}/pending_deployments; gh api -X POST \"$EP\" -f state=approved",
    "gh api -X DELETE repos/neilmac91/EarningsNerd/environments/ops-apply",
    "gh api -X PUT repos/neilmac91/EarningsNerd/environments/ops-apply -F wait_timer=0",
    "gh api graphql -f query='mutation { approveDeployments(input: {workflowRunId: \"x\", environmentIds: [\"y\"]}) { clientMutationId } }'",
    "gh api graphql -f query=\"$(cat <<'EOF'\nmutation { approveDeployments(input: {}) { clientMutationId } }\nEOF\n)\"",
    "gh api graphql -F query=@- <<'EOF'\nmutation { rejectDeployments(input: {}) { clientMutationId } }\nEOF",
    "echo '{\"query\": \"mutation { approveDeployments(input: {}) { clientMutationId } }\"}' | gh api graphql --input -",
    "gh api graphql -f query='mutation { deleteEnvironment(input: {id: \"x\"}) { clientMutationId } }'",
    # Text that names the API on a line that calls it: refused, and the reason says how to send it instead.
    "gh api repos/o/r/pulls/1415/comments/1/replies -f body='Only the founder answers pending_deployments.'",
    # So is a here-document that writes the body file, with the call that sends it, on one line.
    "cat > reply.md <<'EOF' && gh api repos/o/r/issues/1/comments -F body=@reply.md\n"
    "Only the founder answers pending_deployments.\nEOF",
])
def test_a_call_to_the_deployment_review_api_is_refused(command):
    decision = _decision("Bash", {"command": command})
    assert decision == {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                        "permissionDecisionReason": decision["permissionDecisionReason"]}
    reason = decision["permissionDecisionReason"]
    assert "Only the founder approves an Ops apply" in reason
    # The way out works in the form a session reaches for: the file written first, the call on its own.
    assert "send that text from a file written by an earlier command or by the Write tool" in reason
    assert "make the API call a command of its own" in reason


# gh sends all three to the GraphQL endpoint: `/graphql` as a REST path, which names the same URL.
@pytest.mark.parametrize("path", ["graphql", "/graphql", "https://api.github.com/graphql"])
def test_a_mutation_in_a_file_the_api_call_sends_is_refused(tmp_path, path):
    (tmp_path / "q.graphql").write_text("mutation { rejectDeployments(input: {}) { clientMutationId } }")
    assert _decision("Bash", {"command": f"gh api {path} -F query=@q.graphql"}, cwd=tmp_path) is not None


def test_a_graphql_reply_whose_body_file_names_the_review_api_passes(tmp_path):
    """A file a GraphQL call sends is searched for the mutations only: a reply may name the REST paths."""
    (tmp_path / "reply.md").write_text("Only the founder answers pending_deployments on /environments/ops-apply.")
    query = ("mutation($body: String!) { addPullRequestReviewThreadReply(input: "
             "{pullRequestReviewThreadId: \"PRRT_x\", body: $body}) { comment { id } } }")
    command = f"gh api graphql -f query='{query}' -F body=@reply.md"
    assert _decision("Bash", {"command": command}, cwd=tmp_path) is None


@pytest.mark.parametrize("tool,tool_input", [
    ("Bash", {"command": 'git commit -m "docs: only the founder answers pending_deployments"'}),
    ("Bash", {"command": f"gh api {RUNS} -q .status"}),
    ("Bash", {"command": "gh pr comment 1 --body 'The apply waits on pending_deployments for the founder.'"}),
    ("Bash", {"command": "grep -rn pending_deployments .claude/hooks"}),
    ("Bash", {"command": f"cat > notes.md <<'EOF'\nThe founder runs: gh api -X POST {RUNS}/pending_deployments\nEOF"}),
])
def test_text_that_only_names_the_api_passes(tool, tool_input):
    assert _decision(tool, tool_input) is None


@pytest.mark.parametrize("command", [
    # The refused here-document's call alone, its file already written: a REST call's file gives no path.
    "gh api repos/o/r/issues/1/comments -F body=@reply.md",
    "gh pr comment 1 --body-file reply.md",  # no API call on the line
])
def test_text_that_names_the_api_passes_from_a_file(tmp_path, command):
    (tmp_path / "reply.md").write_text("The founder answers approveDeployments and pending_deployments on the run page.")
    assert _decision("Bash", {"command": command}, cwd=tmp_path) is None
