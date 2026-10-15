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

Closing keywords: the gate fails, draft or not and override or not, while the pull request's title,
body or any of its commit messages puts a closing keyword (close, fix or resolve in any form) before an
issue or pull request reference. GitHub closes what such a keyword names when the pull request merges
into the default branch, a pull request included: on 2026-10-09 #1136's body named #1156 that way, and
#1156 was left closed, unmerged, by that merge (``lessons/ops-closing-keywords-close-what-they-name.md``).
Editing the title or body re-runs the gate; a commit message is reworded on the branch. A deliberate
close is done by hand after the merge. The check reads text as GitHub renders it (Markdown escapes
dropped, HTML entities decoded) and fails closed: it also matches forms GitHub does not document (no
space, Markdown marks or a line break between keyword and reference, ``GH-N``, issue and pull URLs),
and it fails a pull request listing 250 commits, the most GitHub lists, whose later messages it cannot
read. A squash message typed at merge is outside any pull-request check.

Override: a line ``Review override: <reason>`` (at least ten characters of reason) in the pull
request body passes the gate with the reason echoed into the job log. That is the rule's own
escape clause, "wait, or write down why you did not", and it keeps the gate from deadlocking when
the review service is unavailable.

After pushing commits that address findings, comment ``@codex review`` right away: a push alone
re-triggers nothing here, and the gate waits for a review of the new head. If the review finishes
after the gate timed out, re-run the failed job (``gh run rerun <run-id> --failed``).

Drafts: the gate fails while the pull request is a draft, and marking it ready starts the wait. It
reads the draft flag from the pull request as it is now, never from the event that started the
run. A job skipped by its ``if`` reports success, which a required check counts as passing, and an
event can still describe a draft after the pull request was marked ready: one update that edits the
body and marks it ready fires both events, and on #1315 the draft one ran second, cancelled the
ready run before it could wait, and skipped. So the workflow never skips this job on a pull-request
event, and the job passes only on a completed review of the head or a recorded override. A re-run
keeps the workflow definition its run started with, so that holds for runs created after the change.

The workflow runs on ``pull_request_target`` and checks out the BASE branch, so a pull request can
edit neither its own gate script nor the workflow definition; and a reviewed short SHA counts only
when the repository resolves it uniquely to the head and no other commit of the pull request shares
it, so a head minted to share a reviewed prefix stays unreviewed while the reviewed object exists.

Environment (set by the workflow): ``GITHUB_TOKEN``, ``REVIEW_GATE_REPO`` (owner/name),
``REVIEW_GATE_PR`` (number), ``REVIEW_GATE_HEAD`` (full SHA), optional
``REVIEW_GATE_TIMEOUT_MINUTES`` (default 20) and ``REVIEW_GATE_POLL_SECONDS`` (default 20).
Stdlib only: this runs before any dependency install.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.request
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Tuple

SUMMARY_MARKER = "codex-pull-request-review-summary"
# The exact GitHub App identity that publishes the summary (login, account type and immutable id,
# read from its comments on 2026-09-16). A commenter whose login merely contains "codex" can copy the
# public table format, so nothing short of this triple is trusted.
CODEX_BOT = {"login": "chatgpt-codex-connector[bot]", "type": "Bot", "id": 199175422}
OVERRIDE = re.compile(r"^\s*Review override:\s*(?P<reason>\S.{9,})\s*$", re.IGNORECASE | re.MULTILINE)
ROW = re.compile(r"\*\*Code Review\*\*\s*\|\s*(?P<status>[^|]*?)\s*\|\s*`(?P<commit>[0-9a-f]{7,40})`", re.IGNORECASE)
# A closing keyword, then a reference: GitHub documents the keyword in any case with an optional colon,
# then ``#N`` or ``OWNER/REPO#N``. Between the two this also allows no space, line breaks and Markdown
# marks (``_`` included, so the keyword's edges are letters and digits, not ``\b``), and it takes ``GH-N``
# and github.com issue or pull URLs, so an undocumented form fails closed. ``(`` and ``;`` stay out: "fix
# (#665)" on #674 and "fix; #1285" on #1306 closed nothing at the merge. A tag stays out too: Dependabot's
# release notes put a keyword before an HTML link to an upstream issue (``<a href=...>#233</a>``), which
# names nothing here. The owner starts with a letter or digit, as GitHub requires, so a path such as
# ``fix-notes/README.md#1-intro`` is not one; owner and repository are bounded (GitHub allows 39 and 100
# characters), which also keeps a run such as ``fix-fix-fix-...`` linear.
CLOSING = re.compile(
    r"(?<![^\W_])(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)(?![^\W_])[\s:*_`~>\[<]*"
    r"(?:(?:[^\W_][\w.-]{0,99}/[\w.-]{1,100})?#\d+|GH-\d+"
    r"|https?://(?:www\.)?github\.com/[\w.-]{1,100}/[\w.-]{1,100}/(?:issues|pull)/\d+)",
    re.IGNORECASE)
# GitHub reads the rendered text: a backslash escape (``\#12``) and an HTML entity (``&#35;12``, ``&nbsp;``)
# render as the character they stand for, so both are undone before matching.
ESCAPE = re.compile(r"\\(?=[^\w\s])")
COMMIT_LIST_CAP = 250  # GitHub's pull-request commits endpoint lists at most 250 commits

Verdict = Tuple[str, str]  # ("pass" | "wait" | "fail", message)


def parse_summary(body: str) -> List[Dict[str, str]]:
    """The review rows of one Codex summary comment: [{"status": ..., "commit": ...}]."""
    rows = []
    for match in ROW.finditer(body or ""):
        status = re.sub(r"<[^>]+>", " ", match.group("status"))
        status = re.sub(r"[*\s]+", " ", status).strip()
        rows.append({"status": status, "commit": match.group("commit").lower()})
    return rows


def is_codex_bot(user: Any) -> bool:
    """Only the real Codex GitHub App: exact login, ``Bot`` account type and its immutable id."""
    return (isinstance(user, dict) and user.get("login") == CODEX_BOT["login"]
            and user.get("type") == CODEX_BOT["type"] and user.get("id") == CODEX_BOT["id"])


def override_reason(body: Optional[str]) -> Optional[str]:
    match = OVERRIDE.search(body or "")
    return match.group("reason").strip() if match else None


def closing_references(texts: Iterable[Tuple[str, Optional[str]]]) -> List[str]:
    """Every closing reference in the (where, text) pairs, read as rendered, as ``where: "keyword #N"``."""
    return [f'{where}: "{" ".join(match.group(0).split())}"'
            for where, text in texts for match in CLOSING.finditer(html.unescape(ESCAPE.sub("", text or "")))]


Resolver = Callable[[str], Optional[str]]  # short SHA -> the unique full SHA in the repository, or None


def decide(head_sha: str, comments: Iterable[Dict[str, Any]], pr_body: Optional[str],
           pr_commits: Optional[Iterable[str]] = None, resolve: Optional[Resolver] = None, *,
           pr_draft: Optional[bool], pr_title: Optional[str] = None,
           pr_commit_messages: Iterable[Tuple[str, str]] = ()) -> Verdict:
    """Pure decision over the pull request's comments, title, body, commits (SHAs and messages) and
    live draft flag for one head SHA.

    A closing keyword before a reference in the title, the body or a commit message fails first,
    draft or not and override or not: the merge would close what it names. So does a commit list at
    GitHub's cap, whose later messages are unread. A draft fails, override or not, and so does a draft
    flag the API did not report as a boolean (None): the check passes only for a pull request that
    can merge. Codex names the reviewed
    commit by a short SHA. It identifies the head only when the repository resolves that prefix to
    exactly the head (so a force-pushed reviewed commit that is still an object in the repository
    keeps a minted lookalike ambiguous) AND no other commit of the pull request shares it."""
    head = (head_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        return "fail", f"review-gate: invalid head SHA {head_sha!r}"
    references = closing_references([("title", pr_title), ("body", pr_body)]
                                    + [(f"commit {str(sha)[:7]}", message) for sha, message in pr_commit_messages])
    if references:
        return "fail", ("review-gate: a closing keyword names an issue or pull request, and the merge would close it: "
                        + "; ".join(references) + ". Reword each so no form of close, fix or resolve sits right before "
                        "the reference (\"addressed in #N\", or the reference first: \"#N carries the fix\"), in the "
                        "title or body (the edit re-runs this check) or by rewording the commit on the branch; close "
                        "anything you mean to close by hand after the merge")
    commits = [str(sha).lower() for sha in (pr_commits or [])]
    if len(commits) >= COMMIT_LIST_CAP:
        return "fail", (f"review-gate: the pull request lists {len(commits)} commits, the most GitHub lists, so the "
                        "messages of any later commits are unread; squash the branch to fewer commits")
    if pr_draft is None:
        return "fail", "review-gate: the pull request's draft flag could not be read; failing closed"
    if pr_draft:
        return "fail", ("review-gate: the pull request is a draft; this check fails until it is marked ready, "
                        f"which starts the wait for the Codex review of {head[:7]}")
    reason = override_reason(pr_body)
    if reason:
        return "pass", f"review-gate: override recorded in the pull request body: {reason}"
    known = set(commits) | {head}
    latest_other: Optional[str] = None
    for comment in comments:
        body = str((comment or {}).get("body") or "")
        if not is_codex_bot((comment or {}).get("user")) or SUMMARY_MARKER not in body:
            continue
        for row in parse_summary(body):
            matches = {sha for sha in known if sha.startswith(row["commit"])}
            if head in matches and len(matches) > 1:
                return "wait", (f"review-gate: reviewed commit {row['commit']} is ambiguous within this pull request "
                                f"({len(matches)} commits share the prefix); comment `@codex review` for {head[:12]}")
            if head in matches and resolve is not None:
                resolved = resolve(row["commit"])
                if resolved is None or resolved.lower() != head:
                    return "wait", (f"review-gate: reviewed commit {row['commit']} does not resolve uniquely to this head "
                                    f"in the repository; comment `@codex review` for {head[:12]}")
            if head in matches:
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


def _paged(path: str, token: str) -> List[Any]:
    items: List[Any] = []
    page = 1
    while True:
        batch = _github(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}", token)
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


class State(NamedTuple):
    comments: List[Dict[str, Any]]
    body: Optional[str]
    commits: List[str]
    draft: Optional[bool]
    title: Optional[str] = None
    commit_messages: Tuple[Tuple[str, str], ...] = ()


def fetch_state(repo: str, number: str, token: str) -> State:
    """Comments, body, commits, draft flag and title, all read now. The draft flag is None unless the
    API reports a boolean, which ``decide`` fails closed."""
    comments = _paged(f"repos/{repo}/issues/{number}/comments", token)
    pull = _github(f"repos/{repo}/pulls/{number}", token)
    items = _paged(f"repos/{repo}/pulls/{number}/commits", token)
    commits = [str(item.get("sha", "")).lower() for item in items]
    messages = tuple((sha, str((item.get("commit") or {}).get("message") or "")) for sha, item in zip(commits, items))
    draft = pull.get("draft")
    return State(comments, pull.get("body"), commits, draft if isinstance(draft, bool) else None,
                 pull.get("title"), messages)


def repository_resolver(repo: str, token: str) -> Resolver:
    """Resolve a short SHA through the repository's commit endpoint, which answers only when the
    prefix is unique among the repository's objects (force-pushed commits included while they
    exist); anything else, including an ambiguous prefix, resolves to None."""
    def resolve(short: str) -> Optional[str]:
        try:
            commit = _github(f"repos/{repo}/commits/{short}", token)
        except Exception:  # noqa: BLE001 - 404/422 (unknown or ambiguous) and transport errors all mean "not resolved"
            return None
        sha = str(commit.get("sha", "")).lower() if isinstance(commit, dict) else ""
        return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
    return resolve


def main(argv: Optional[List[str]] = None, *, fetch: Optional[Callable[[], State]] = None,
         resolve: Optional[Resolver] = None,
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
        resolve = resolve or repository_resolver(repo, token)
    started = clock()
    while True:
        state = State(*fetch())
        verdict, message = decide(head, state.comments, state.body, state.commits, resolve, pr_draft=state.draft,
                                  pr_title=state.title, pr_commit_messages=state.commit_messages)
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
