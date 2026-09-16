#!/usr/bin/env python3
"""Review gate: pass only when the Codex review for the pull request's CURRENT head has completed,
or when the pull request body records an explicit override with a reason.

This is the rule-12 machine gate for ``lessons/ops-a-review-you-triggered-is-a-review-you-wait-for.md``.
Codex publishes no check run of its own; the only machine-observable record of a review is its
"Codex Review Summary" issue comment, whose table row names the reviewed commit (short SHA) and a
status (Running / Completed / Failed). This script polls that comment for the head under test and
publishes its verdict through the ``review-gate`` job of ``.github/workflows/review-gate.yml``.
Requiring that check in a ruleset on ``main`` (a founder decision) makes the rule binding; a
required status check needs no approver, so it cannot lock a solo-administrator repository.

Override: a line ``Review override: <reason>`` (at least ten characters of reason) in the pull
request body passes the gate with the reason echoed into the job log. That is the rule's own
escape clause, "wait, or write down why you did not", and it keeps the gate from deadlocking when
the review service is unavailable.

After pushing commits that address findings, comment ``@codex review`` right away: a push alone
re-triggers nothing here, and the gate waits for a review of the new head. If the review finishes
after the gate timed out, re-run the failed job (``gh run rerun <run-id> --failed``).

Environment (set by the workflow): ``GITHUB_TOKEN``, ``REVIEW_GATE_REPO`` (owner/name),
``REVIEW_GATE_PR`` (number), ``REVIEW_GATE_HEAD`` (full SHA), optional
``REVIEW_GATE_TIMEOUT_MINUTES`` (default 20) and ``REVIEW_GATE_POLL_SECONDS`` (default 20).
Stdlib only: this runs before any dependency install.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SUMMARY_MARKER = "codex-pull-request-review-summary"
CODEX_LOGIN_FRAGMENT = "codex"
OVERRIDE = re.compile(r"^\s*Review override:\s*(?P<reason>\S.{9,})\s*$", re.IGNORECASE | re.MULTILINE)
ROW = re.compile(r"\*\*Code Review\*\*\s*\|\s*(?P<status>[^|]*?)\s*\|\s*`(?P<commit>[0-9a-f]{7,40})`", re.IGNORECASE)

Verdict = Tuple[str, str]  # ("pass" | "wait" | "fail", message)


def parse_summary(body: str) -> List[Dict[str, str]]:
    """The review rows of one Codex summary comment: [{"status": ..., "commit": ...}]."""
    rows = []
    for match in ROW.finditer(body or ""):
        status = re.sub(r"<[^>]+>", " ", match.group("status"))
        status = re.sub(r"[*\s]+", " ", status).strip()
        rows.append({"status": status, "commit": match.group("commit").lower()})
    return rows


def override_reason(body: Optional[str]) -> Optional[str]:
    match = OVERRIDE.search(body or "")
    return match.group("reason").strip() if match else None


def decide(head_sha: str, comments: Iterable[Dict[str, Any]], pr_body: Optional[str]) -> Verdict:
    """Pure decision over the pull request's comments and body for one head SHA."""
    head = (head_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{7,40}", head):
        return "fail", f"review-gate: invalid head SHA {head_sha!r}"
    reason = override_reason(pr_body)
    if reason:
        return "pass", f"review-gate: override recorded in the pull request body: {reason}"
    latest_other: Optional[str] = None
    for comment in comments:
        login = str(((comment or {}).get("user") or {}).get("login") or "").lower()
        body = str((comment or {}).get("body") or "")
        if CODEX_LOGIN_FRAGMENT not in login or SUMMARY_MARKER not in body:
            continue
        for row in parse_summary(body):
            if head.startswith(row["commit"]):
                status = row["status"].lower()
                if "completed" in status:
                    return "pass", f"review-gate: Codex review completed for {row['commit']}"
                if "failed" in status or "error" in status:
                    return "fail", f"review-gate: Codex review {row['status']} for {row['commit']}; re-request with @codex review or record an override"
                return "wait", f"review-gate: Codex review {row['status']} for {row['commit']}"
            latest_other = row["commit"]
    if latest_other:
        return "wait", (f"review-gate: the latest Codex review is for {latest_other}, not this head {head[:7]}; "
                        "comment `@codex review` (a push does not re-trigger a review) or record an override")
    return "wait", f"review-gate: no Codex review summary yet for {head[:7]}"


def _github(path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "earningsnerd-review-gate"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - fixed https host, no user-supplied scheme
        return json.loads(response.read().decode("utf-8"))


def fetch_state(repo: str, number: str, token: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    comments: List[Dict[str, Any]] = []
    page = 1
    while True:
        batch = _github(f"repos/{repo}/issues/{number}/comments?per_page=100&page={page}", token)
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    pull = _github(f"repos/{repo}/pulls/{number}", token)
    return comments, pull.get("body")


def main(argv: Optional[List[str]] = None, *, fetch: Optional[Callable[[], Tuple[List[Dict[str, Any]], Optional[str]]]] = None,
         sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> int:
    env = os.environ
    head = env.get("REVIEW_GATE_HEAD", "")
    timeout = float(env.get("REVIEW_GATE_TIMEOUT_MINUTES", "20")) * 60
    poll = float(env.get("REVIEW_GATE_POLL_SECONDS", "20"))
    if fetch is None:
        repo, number, token = env.get("REVIEW_GATE_REPO", ""), env.get("REVIEW_GATE_PR", ""), env.get("GITHUB_TOKEN", "")
        if not (repo and number and token):
            print("review-gate: REVIEW_GATE_REPO, REVIEW_GATE_PR and GITHUB_TOKEN are required")
            return 1
        fetch = lambda: fetch_state(repo, number, token)  # noqa: E731
    started = clock()
    while True:
        comments, body = fetch()
        verdict, message = decide(head, comments, body)
        print(message)
        if verdict == "pass":
            return 0
        if verdict == "fail":
            return 1
        if clock() - started >= timeout:
            print(f"review-gate: timed out after {timeout / 60:g} minutes waiting for a completed Codex review of "
                  f"{head[:7]}. Comment `@codex review`, wait for it to complete, then re-run this job; or add a "
                  "`Review override: <reason>` line to the pull request body.")
            return 1
        sleep(poll)


if __name__ == "__main__":
    sys.exit(main())
