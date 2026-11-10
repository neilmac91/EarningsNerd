"""Read an exact-run founder approval for the five beta operations, never write one.

The optional route is off unless both its repository variable and dispatch input are
true. The normal environment approval remains available. Agents must not author the
approval comment: the API establishes its owner account, not the human using it.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode

REPOSITORY = "neilmac91/EarningsNerd"
OWNER_ID = 212895734
APPROVAL_ISSUE = 1954  # Existing private-beta acceptance/coordination PR; no new issue per run.
OPERATIONS = frozenset({"feedback-media-provision-apply", "feedback-media-verify-apply",
                       "feedback-media-enable-apply", "feedback-media-disable-apply", "complimentary-access-apply"})
WAIT_SECONDS = 900
POLL_SECONDS = 10


class Refused(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Refused(message)


def api(endpoint: str, *arguments: str):
    """GitHub reads only; never echo API bodies, credentials or subprocess stderr."""
    try:
        result = subprocess.run(["gh", "api", endpoint, *arguments], check=True, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        raise Refused("GitHub approval state unavailable; no cloud action is authorized") from None


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise Refused("GitHub approval timestamp is unreadable") from None
    require(parsed.tzinfo is not None, "GitHub approval timestamp has no timezone")
    return parsed


def request(env: dict[str, str]) -> dict[str, str]:
    require(env.get("BETA_COMMENT_APPROVAL") == "true"
            and env.get("BETA_COMMENT_APPROVAL_ENABLED") == "true", "Beta comment approval is disabled")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY
            and env.get("GITHUB_REF") == "refs/heads/main"
            and env.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/.github/workflows/ops.yml@refs/heads/main",
            "Beta approval requires the committed main Ops workflow")
    run_id, sha = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_SHA", "")
    require(bool(re.fullmatch(r"[1-9][0-9]{0,19}", run_id)) and env.get("GITHUB_RUN_ATTEMPT") == "1"
            and bool(re.fullmatch(r"[0-9a-f]{40}", sha)), "Beta approval requires an exact first-attempt run")
    operation, digest = env.get("OP", ""), env.get("CONFIRM_DIGEST", "")
    require(operation in OPERATIONS, "Operation is outside the beta approval route")
    require(bool(re.fullmatch(r"[0-9a-f]{64}", digest)) if operation == "complimentary-access-apply" else digest == "",
            "Approval digest differs from the operation's required input")
    return {"repository": REPOSITORY, "run": run_id, "attempt": "1", "sha": sha,
            "operation": operation, "confirm_digest": digest or "none"}


def approval_text(wanted: dict[str, str]) -> str:
    return "APPROVE EARNINGSNERD BETA OPERATION\n" + "\n".join(f"{key}: {value}" for key, value in wanted.items())


def statement(body: str) -> str:
    # A browser form stores CRLF line endings and the API stores what it is sent; the words are the approval.
    # Only that pair is folded, and blank space around the whole statement is dropped as before: a lone carriage
    # return, a code fence or any other added character inside it still differs.
    return body.replace("\r\n", "\n").strip()


def run_context(wanted: dict[str, str]) -> datetime:
    try:
        checkout = subprocess.run(["git", "rev-parse", "HEAD"], check=True, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        raise Refused("Checked-out source identity is unavailable") from None
    require(checkout == wanted["sha"], "Checked-out source differs from the approval request")
    repo = api("repos/" + REPOSITORY)
    require(repo.get("owner", {}).get("id") == OWNER_ID and repo.get("owner", {}).get("type") == "User",
            "The repository owner differs from the configured founder")
    run = api(f"repos/{REPOSITORY}/actions/runs/{wanted['run']}")
    require(run.get("id") == int(wanted["run"]) and run.get("run_attempt") == 1
            and run.get("event") == "workflow_dispatch" and run.get("head_branch") == "main"
            and run.get("head_sha") == wanted["sha"]
            and run.get("path", "").split("@", 1)[0] == ".github/workflows/ops.yml",
            "GitHub run identity differs from the approval request")
    main = api(f"repos/{REPOSITORY}/git/ref/heads/main")
    require(main.get("object", {}).get("sha") == wanted["sha"], "Main advanced; dispatch a fresh run")
    return timestamp(run.get("created_at"))


def matches(comment: dict, wanted: dict[str, str], created: datetime) -> bool:
    """Treat comments as data: only an exact statement from the founder can match."""
    if (comment.get("user", {}).get("id") != OWNER_ID or comment.get("user", {}).get("type") != "User"
            or comment.get("author_association") != "OWNER" or comment.get("performed_via_github_app") is not None
            or comment.get("issue_url") != f"https://api.github.com/repos/{REPOSITORY}/issues/{APPROVAL_ISSUE}"
            or not isinstance(comment.get("body"), str) or statement(comment["body"]) != approval_text(wanted)
            or type(comment.get("id")) is not int or comment["id"] < 1):
        return False
    posted = timestamp(comment.get("created_at"))
    return (created <= posted <= datetime.now(timezone.utc)
            and comment.get("updated_at") == comment.get("created_at"))


def unedited(comment: dict) -> None:
    # REST timestamps have only second precision. GraphQL lastEditedAt also catches
    # an edit made during the creation second, rather than calling equal times immutable.
    node_id = comment.get("node_id")
    require(isinstance(node_id, str) and 0 < len(node_id) <= 256, "Approval comment identity is unreadable")
    result = api("graphql", "-f", "query=query($id: ID!) { node(id: $id) { ... on IssueComment { id lastEditedAt isMinimized } } }",
                 "-f", "id=" + node_id)
    require(not result.get("errors"), "Approval edit history is unavailable")
    node = result.get("data", {}).get("node")
    require(isinstance(node, dict) and node.get("id") == node_id and "lastEditedAt" in node
            and node["lastEditedAt"] is None and node.get("isMinimized") is False,
            "Approval comment was edited, hidden or is unreadable")


def verify(wanted: dict[str, str], comment_id: str) -> None:
    require(bool(re.fullmatch(r"[1-9][0-9]{0,19}", comment_id)), "No exact approval comment was recorded")
    created = run_context(wanted)
    comment = api(f"repos/{REPOSITORY}/issues/comments/{comment_id}")
    require(comment.get("id") == int(comment_id) and matches(comment, wanted, created),
            "Exact founder approval is absent, deleted, edited or differs")
    unedited(comment)
    print(f"Founder comment {comment_id} approves this exact run and operation.")


def wait(wanted: dict[str, str]) -> str:
    created = run_context(wanted)
    text = approval_text(wanted)
    notice = (f"The founder must personally post this exact comment at https://github.com/{REPOSITORY}/pull/{APPROVAL_ISSUE}#issuecomment-new.\n"
              "Agents must not post or edit the approval. No cloud credentials have been acquired by this approval job.\n\n"
              f"```text\n{text}\n```\n")
    print(notice, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(notice)
    query = urlencode({"since": created.isoformat(), "per_page": 100})
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        comments = api(f"repos/{REPOSITORY}/issues/{APPROVAL_ISSUE}/comments?{query}")
        require(isinstance(comments, list) and len(comments) < 100, "Approval comment inventory is unreadable or exceeds its bound")
        for comment in comments:
            require(isinstance(comment, dict), "Approval comment inventory is unreadable")
            if matches(comment, wanted, created):
                comment_id = str(comment["id"])
                verify(wanted, comment_id)
                return comment_id
        time.sleep(POLL_SECONDS)
    raise Refused("No exact founder approval arrived within 15 minutes; dispatch a fresh run")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("wait", "verify"))
    args = parser.parse_args()
    wanted = request(dict(os.environ))
    if args.mode == "verify":
        verify(wanted, os.environ.get("APPROVAL_COMMENT_ID", ""))
    else:
        comment_id = wait(wanted)
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
            handle.write("comment_id=" + comment_id + "\n")


if __name__ == "__main__":
    try:
        main()
    except (Refused, KeyError, TypeError, AttributeError, OSError) as error:
        raise SystemExit(str(error) if isinstance(error, Refused) else "Approval input is unreadable; no cloud action is authorized") from None
