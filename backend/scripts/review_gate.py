#!/usr/bin/env python3
"""Review gate: pass only when the Codex review for the pull request's CURRENT head has completed,
or when the pull request body records an explicit override with a reason.

This is the rule-12 machine gate for ``lessons/ops-a-review-you-triggered-is-a-review-you-wait-for.md``.
Codex publishes no check run of its own; the only machine-observable record of a review is its
"Codex Review Summary" issue comment. F58 also requires its full-SHA machine state to be completed
with unresolved findings false. Trusted GitHub ready events and bot-authored edit history prove the
ready mark's own running/completed cycle; a draft-era completion cannot pass the ready check. A later
manual review may supersede a completed ready cycle on a different head, including fixes to its
findings. On the same head the ready cycle must itself be clean. The newest human review request
must be covered, even before the bot publishes Running. Missing history, malformed state and API errors
never pass. The bot exposes no run id, so the history is replayed: a completion pairs with the open start of
its head and trigger, never with one begun while another of them was open, and any start still open blocks
the pass until it completes or is an hour old, when it counts as abandoned (F58 call 1). This script polls
that comment for the head under test and
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
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Tuple, Union

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
MAX_PAGES = 10  # bounded reads; incomplete evidence never passes
STATE_MARKER = re.compile(r"<!--\s*codex-review-state:v1\s+(.*?)\s*-->", re.DOTALL)
CYCLE_ROW = re.compile(
    r"\*\*Code Review\*\*\s*\|\s*(?P<status>[^|]+)\|\s*`(?P<commit>[0-9a-f]{7,40})`\s*\|\s*(?P<trigger>[^|]+)\|",
    re.IGNORECASE,
)
COMMIT_LIST_CAP = 250  # GitHub's pull-request commits endpoint lists at most 250 commits
# F58 call 1 (the founder, 2026-10-23: "Call 1 approved"): a review start still open this long counts as
# abandoned. All 242 single Codex runs on PRs 1380-1486 finished within 21 minutes, and 34 of 35 superseded
# runs never finished (review 6341504879), so a run open for the hour is taken to be hung: from then on it
# no longer blocks the gate, and a completion is never paired with it.
ABANDON_AFTER = timedelta(minutes=60)

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


class EvidenceError(ValueError):
    """Missing or contradictory evidence must not become a successful check."""


class SnapshotChanged(EvidenceError):
    """A concurrent PR update requires a fresh poll, not mixed evidence."""


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", value):
        raise EvidenceError("missing or malformed GitHub/review timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvidenceError("invalid GitHub/review timestamp") from exc


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError("duplicate key in Codex state")
        result[key] = value
    return result


class Unreadable(NamedTuple):
    """A summary version with no readable code state (a version from before the machine marker, or a
    malformed one), at its edit time. It may hide a review start, so while it is younger than
    ``ABANDON_AFTER`` no completion pairs past it and the gate waits; older, it is history."""
    at: datetime


class Review(NamedTuple):
    head: str
    short: str
    status: str
    unresolved: Optional[bool]
    at: datetime
    trigger: str

    def cycle_state(self) -> tuple:
        # Findings can be resolved without running the review again. Security-review edits also
        # repeat this code state; neither is a new start or completion.
        return self.head, self.status, self.at, self.trigger


def _review(body: str) -> Review:
    decoded = html.unescape(body)
    markers = STATE_MARKER.findall(decoded)
    rows = list(CYCLE_ROW.finditer(decoded))
    if len(markers) != 1 or len(rows) != 1:
        raise EvidenceError("expected one Codex code-state marker and one review row")
    try:
        code = json.loads(markers[0], object_pairs_hook=_unique_object)["code_review"]
        head, status, unresolved = code["commit_sha"], code["status"], code["has_unresolved_findings"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise EvidenceError("malformed Codex code state") from exc
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise EvidenceError("Codex state must name a full head SHA")
    if status not in ("running", "completed", "failed", "error"):
        raise EvidenceError("unknown Codex code status")
    if unresolved is not None and type(unresolved) is not bool:
        raise EvidenceError("unresolved-findings state is not a boolean")
    if status == "completed" and type(unresolved) is not bool:
        raise EvidenceError("completed review has no unresolved-findings verdict")
    row = rows[0]
    statuses = re.findall(r"\*\*(Running|Completed|Failed|Error)\*\*", row["status"], re.IGNORECASE)
    times = re.findall(r'<relative-time\s+datetime="([^"]+)"', row["status"])
    if len(statuses) != 1 or statuses[0].lower() != status or len(times) != 1:
        raise EvidenceError("Codex row and machine status disagree or lack a review time")
    short = row["commit"].lower()
    if not head.startswith(short):
        raise EvidenceError("Codex row and machine head disagree")
    trigger = row["trigger"].strip()
    if trigger not in ("PR opened", "Draft marked ready", "Manual request"):
        raise EvidenceError("unknown Codex review trigger")
    return Review(head, short, status, unresolved, _timestamp(times[0]), trigger)


Entry = Union["Review", Unreadable]  # one summary version, newest first in a history


def _history(comment: Dict[str, Any]) -> List[Entry]:
    history = comment.get("review_history")
    if not isinstance(history, list) or not history:
        raise EvidenceError("Codex summary edit history is unavailable")
    if html.unescape(str(history[0].get("diff", ""))) != html.unescape(str(comment.get("body", ""))):
        raise EvidenceError("latest summary history disagrees with the current REST comment; retry the read")
    states: List[Entry] = []
    previous = datetime.max.replace(tzinfo=timezone.utc)
    for item in history:
        editor = item.get("editor") or {}
        if (editor.get("login") != "chatgpt-codex-connector" or editor.get("__typename") != "Bot"
                or editor.get("databaseId") != CODEX_BOT["id"]):
            raise EvidenceError("summary history has an untrusted or missing editor")
        edited = _timestamp(item.get("editedAt"))
        if edited > previous:
            raise EvidenceError("summary history is not newest first")
        previous = edited
        try:
            states.append(_review(item.get("diff") or ""))
        except EvidenceError:
            # An old pre-marker version is irrelevant once it is past the abandonment age; younger,
            # it may hide a start (``_replay``).
            states.append(Unreadable(edited))
    return states


class Replay(NamedTuple):
    starts: Dict[int, Review]   # completion index (newest-first) -> the start it is paired with
    open: List[Entry]           # starts no completion closed, and unreadable versions, oldest first


def _open_at(entry: Entry, moment: datetime) -> bool:
    """Whether a start, or an unreadable version that may hide one, still counts at ``moment``: it is under the
    abandonment age then (F58 call 1). One stamped after ``moment`` counts too, so clock skew never hides it."""
    return moment - entry.at < ABANDON_AFTER


def _replay(states: List[Entry]) -> Replay:
    """Replay the summary history oldest first (F58 call 1; B1 in review 6341504879). The summary shows only
    the newest review and carries no run id, so a start is a version reading Running and a completion one
    reading Completed, Failed or Error; a version repeating any earlier code state (a security-review edit,
    a finding resolved) is that start or completion again, not a new one. A start stays open until a
    completion closes it or it is an hour old, when it counts as abandoned.

    A start that begins while another start of its head and trigger is open, or while an unreadable version
    that may hide one is under the hour, overlaps it: a later completion could be either run's, so none ever
    pairs with the overlapping start, which stays open and holds the gate until its hour is up. That is the
    machine gate (rule 12) for "no ready mark or review request while a review runs". So at most one open
    start of a head and trigger can take a completion, and it does; an earlier completion that took the
    older start when the newer finished first leaves no start the newer run's could wrongly claim. An
    unreadable version under the hour at a completion may hide its start, so that completion pairs with
    nothing. The one case the replay cannot tell apart is a run that completes more than an hour after it
    began, while a later run of its head and trigger, begun once the hour was up, is still going: its
    completion pairs with the later start. The gate accepts that risk; no run in PRs 1380-1486 took more
    than 21 minutes."""
    starts: Dict[int, Review] = {}
    pending: List[Entry] = []
    overlapping: List[Review] = []
    # Every code state seen so far; a completion's maps to the start it closed. A version repeating one of
    # them, adjacent or not, is a re-render of that start or completion, never a new run.
    seen: Dict[tuple, Optional[Review]] = {}
    for index in range(len(states) - 1, -1, -1):
        state = states[index]
        if isinstance(state, Unreadable):
            pending.append(state)
            continue
        key = state.cycle_state()
        if key in seen:
            if seen[key] is not None:
                starts[index] = seen[key]
            continue
        seen[key] = None
        live = [entry for entry in pending if _open_at(entry, state.at)]
        hidden = any(isinstance(entry, Unreadable) for entry in live)
        rivals = [entry for entry in live if isinstance(entry, Review)
                  and entry.head == state.head and entry.trigger == state.trigger]
        if state.status == "running":
            if hidden or rivals:
                overlapping.append(state)
            pending.append(state)
            continue
        if hidden:
            continue  # a hidden start may own this completion; it pairs with nothing
        match = next((entry for entry in rivals if entry.at <= state.at and entry not in overlapping), None)
        if match is not None:
            pending.remove(match)
            starts[index] = seen[key] = match
    return Replay(starts, pending)


# The one way out once a completion cannot be placed: a review that starts with nothing else open pairs.
FRESH_TRANSITION = ("make one fresh draft-to-ready transition, its two steps a few seconds apart, with no manual "
                    "request, and let that review complete; reserve copilot-eval first when its paths match")


def _cycle_start(states: List[Entry], index: int) -> Review:
    completed = states[index]
    if not isinstance(completed, Review) or completed.status != "completed":
        raise EvidenceError("review completion is missing")
    start = _replay(states).starts.get(index)
    if start is None:
        raise EvidenceError("review completion has no start to pair with: its running state is missing, names "
                            "another head or trigger, began while another review of its head and trigger was "
                            "open, is an hour or more before it, or sits within the hour after an unreadable "
                            f"summary version. No later poll can pair it; with no review open, {FRESH_TRANSITION}")
    return start


def _abandoned_from(entry: Entry) -> str:
    """The first whole second at which ``entry`` counts as abandoned."""
    moment = entry.at + ABANDON_AFTER
    if moment.microsecond:
        moment = moment.replace(microsecond=0) + timedelta(seconds=1)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_no_live_start(states: List[Entry], now: datetime) -> None:
    """Pass only with no review still running: a start no completion closed blocks until the abandonment
    age, and so does an unreadable version that may hide one (F58 call 1)."""
    for entry in reversed(_replay(states).open):
        if _open_at(entry, now):
            if isinstance(entry, Unreadable):
                raise EvidenceError(f"an unreadable summary version from {entry.at:%H:%M:%S}Z may hide a running "
                                    f"review; it stops counting at {_abandoned_from(entry)}")
            raise EvidenceError(f"a Codex review of {entry.short} ({entry.trigger}) started at {entry.at:%H:%M:%S}Z "
                                f"has not completed; it counts as abandoned from {_abandoned_from(entry)}")


def _review_evidence(head: str, comments: List[Dict[str, Any]], created_at: Optional[str],
                     timeline: Optional[List[Dict[str, Any]]]) -> Tuple[Review, List[Entry], Optional[datetime]]:
    summaries = [c for c in comments if is_codex_bot(c.get("user")) and SUMMARY_MARKER in str(c.get("body") or "")]
    if not summaries:
        raise EvidenceError(f"no Codex review summary yet for {head[:7]}")
    # Do not search older comments for a passing result after a new canonical summary was posted.
    latest = max(summaries, key=lambda c: (_timestamp(c.get("created_at")), c.get("id", 0)))
    current = _review(latest.get("body") or "")
    states = _history(latest)
    created = _timestamp(created_at)
    if timeline is None:
        raise EvidenceError("complete ready-for-review timeline is unavailable")
    ready = [_timestamp(e.get("created_at")) for e in timeline if e.get("event") == "ready_for_review"]
    drafts = [_timestamp(e.get("created_at")) for e in timeline if e.get("event") == "convert_to_draft"]
    anchor = max(ready) if ready else created
    if anchor < created or (drafts and max(drafts) >= anchor):
        raise EvidenceError("ready timeline disagrees with the live non-draft state")
    return current, states, max(ready) if ready else None


def _latest_request(comments: List[Dict[str, Any]], anchor: datetime) -> Optional[datetime]:
    requests = []
    for comment in comments:
        if ((comment.get("user") or {}).get("type") == "User"
                and re.match(r"^@codex review(?:\s|$)", str(comment.get("body") or ""))):
            created = _timestamp(comment.get("created_at"))
            if created >= anchor:
                requests.append((created, comment))
    if not requests:
        return None
    created, latest = max(requests, key=lambda item: (item[0], item[1].get("id", 0)))
    # A newer unedited command supersedes an older edited request. Only the request this cycle
    # must answer needs creation-time evidence; an edit never proves the command existed then.
    if latest.get("updated_at") != latest.get("created_at"):
        raise EvidenceError("edited review request cannot establish a creation-time trigger")
    return created


def _after_github_second(start: datetime, event: datetime) -> bool:
    """REST creation/event timestamps expose only the second containing the event. A bot start
    anywhere in that second, even with fractional precision, may precede it. Only the next whole
    second or later proves the start followed this request, ready mark or PR creation."""
    return start >= event.replace(microsecond=0) + timedelta(seconds=1)


def _prove_cycles(current: Review, states: List[Entry], ready: Optional[datetime],
                  created: datetime, request: Optional[datetime], now: datetime) -> None:
    _require_no_live_start(states, now)
    start = _cycle_start(states, 0)
    anchor = ready or created
    if not _after_github_second(start.at, anchor):
        raise EvidenceError(f"review start does not provably follow the current ready/creation second (its completion "
                            f"pairs with the review started at {start.at:%H:%M:%S}Z); with no review open, "
                            f"{FRESH_TRANSITION}")
    if request is not None and (current.trigger != "Manual request" or not _after_github_second(start.at, request)):
        raise EvidenceError("latest manual @codex review request has not completed its own cycle")
    if current.trigger == "Manual request" and request is None:
        raise EvidenceError("manual review has no matching human @codex review request")
    if ready is None:
        if current.trigger not in ("PR opened", "Manual request"):
            raise EvidenceError("ready-trigger review has no trusted ready event")
        return
    if current.trigger == "Draft marked ready":
        return
    if current.trigger != "Manual request":
        raise EvidenceError("the ready mark's own review has not completed")
    for index, state in enumerate(states):
        if (isinstance(state, Review) and state.trigger == "Draft marked ready" and state.status == "completed"
                and state.at >= ready):
            ready_start = _cycle_start(states, index)
            if not _after_github_second(ready_start.at, ready) or state.at > start.at:
                raise EvidenceError("ready cycle did not complete before the later manual review started")
            if state.head == current.head and state.unresolved is not False:
                raise EvidenceError("same-head manual review cannot replace unresolved ready-cycle findings")
            # A different-head clean review can fix findings from the completed ready cycle.
            return
    raise EvidenceError("no completed cycle for the latest ready mark; a manual review cannot replace it")


def decide(head_sha: str, comments: Iterable[Dict[str, Any]], pr_body: Optional[str],
           pr_commits: Optional[Iterable[str]] = None, resolve: Optional[Resolver] = None, *,
           pr_draft: Optional[bool], pr_title: Optional[str] = None,
           pr_commit_messages: Iterable[Tuple[str, str]] = (),
           pr_created_at: Optional[str] = None, pr_timeline: Optional[List[Dict[str, Any]]] = None,
           pr_head: Optional[str] = None, now: Optional[datetime] = None) -> Verdict:
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
    if not isinstance(pr_head, str) or not re.fullmatch(r"[0-9a-f]{40}", pr_head):
        return "fail", "review-gate: live pull-request head is unavailable; failing closed"
    if pr_head != head:
        return "fail", "review-gate: this job's head is stale; wait for the gate on the live pull-request head"
    reason = override_reason(pr_body)
    if reason:
        return "pass", f"review-gate: override recorded in the pull request body: {reason}"
    known = set(commits) | {head}
    comments = list(comments)
    try:
        current, states, ready = _review_evidence(head, comments, pr_created_at, pr_timeline)
        if current.head != head:
            return "wait", (f"review-gate: the latest Codex review is for {current.short}, not this head {head[:7]}; "
                            "comment `@codex review` or record an override")
        matches = {sha for sha in known if sha.startswith(current.short)}
        if len(matches) > 1:
            return "wait", f"review-gate: reviewed commit {current.short} is ambiguous within this pull request"
        if resolve is not None and resolve(current.short) != head:
            return "wait", f"review-gate: reviewed commit {current.short} does not resolve uniquely to this head"
        if current.status in ("failed", "error"):
            return "fail", "review-gate: Codex review failed; re-request @codex review or record an override"
        if current.unresolved is True:
            return "fail", "review-gate: current-head Codex review has unresolved findings"
        moment = now or datetime.now(timezone.utc)
        if current.status != "completed":
            if not _open_at(current, moment):
                return "wait", (f"review-gate: the Codex review of {current.short} has shown Running since "
                                f"{current.at:%H:%M:%S}Z, past the one-hour abandonment age, so it counts as abandoned "
                                f"(F58 call 1); {FRESH_TRANSITION}")
            return "wait", (f"review-gate: Codex review {current.status} for {current.short} since "
                            f"{current.at:%H:%M:%S}Z; if it never completes it counts as abandoned from "
                            f"{_abandoned_from(current)}")
        created = _timestamp(pr_created_at)
        request = _latest_request(comments, ready or created)
        _prove_cycles(current, states, ready, created, request, moment)
    except EvidenceError as exc:
        return "wait", f"review-gate: {exc}; waiting for complete trusted review evidence"
    return "pass", f"review-gate: current-head Codex cycle completed with no unresolved findings for {current.short}"


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
    while page <= MAX_PAGES:
        batch = _github(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise EvidenceError("GitHub pagination did not return a list")
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    else:
        raise EvidenceError("GitHub pagination limit reached; evidence is incomplete")
    return items


def _graphql(query: str, variables: Dict[str, Any], token: str) -> Any:
    request = urllib.request.Request(
        "https://api.github.com/graphql", data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "earningsnerd-review-gate"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310 - fixed GitHub HTTPS endpoint
        result = json.loads(response.read().decode("utf-8"))
    if result.get("errors"):
        raise EvidenceError("GitHub could not read the summary edit history")
    return result.get("data")


def _fetch_history(node_id: str, token: str) -> List[Dict[str, Any]]:
    query = """query($id: ID!, $after: String) {
      node(id: $id) { ... on IssueComment {
        userContentEdits(first: 100, after: $after) {
          nodes { editedAt diff editor { login __typename ... on Bot { databaseId } } }
          pageInfo { hasNextPage endCursor }
        }
      } }
    }"""
    edits: List[Dict[str, Any]] = []
    cursor = None
    for _ in range(MAX_PAGES):
        data = _graphql(query, {"id": node_id, "after": cursor}, token)
        try:
            connection = data["node"]["userContentEdits"]
            nodes, page = connection["nodes"], connection["pageInfo"]
            if not isinstance(nodes, list) or type(page["hasNextPage"]) is not bool:
                raise EvidenceError("malformed summary history page")
            edits.extend(nodes)
            if not page["hasNextPage"]:
                return edits
            following = page["endCursor"]
            if not isinstance(following, str) or not following or following == cursor:
                raise EvidenceError("summary history pagination did not advance")
            cursor = following
        except (KeyError, TypeError) as exc:
            raise EvidenceError("summary history is unavailable") from exc
    raise EvidenceError("summary history pagination limit reached; evidence is incomplete")


class State(NamedTuple):
    comments: List[Dict[str, Any]]
    body: Optional[str]
    commits: List[str]
    draft: Optional[bool]
    title: Optional[str] = None
    commit_messages: Tuple[Tuple[str, str], ...] = ()
    created_at: Optional[str] = None
    timeline: Optional[List[Dict[str, Any]]] = None
    head: Optional[str] = None


def fetch_state(repo: str, number: str, token: str) -> State:
    """Comments, body, commits, draft flag and title, all read now. The draft flag is None unless the
    API reports a boolean, which ``decide`` fails closed."""
    comments = _paged(f"repos/{repo}/issues/{number}/comments", token)
    pull = _github(f"repos/{repo}/pulls/{number}", token)
    items = _paged(f"repos/{repo}/pulls/{number}/commits", token)
    commits = [str(item.get("sha", "")).lower() for item in items]
    messages = tuple((sha, str((item.get("commit") or {}).get("message") or "")) for sha, item in zip(commits, items))
    draft = pull.get("draft")
    # Old guards and the explicit override remain usable even when review evidence is unavailable.
    timeline = None
    if draft is False and not override_reason(pull.get("body")):
        timeline = _paged(f"repos/{repo}/issues/{number}/timeline", token)
        summaries = [c for c in comments if is_codex_bot(c.get("user")) and SUMMARY_MARKER in str(c.get("body") or "")]
        if summaries:
            latest = max(summaries, key=lambda c: (_timestamp(c.get("created_at")), c.get("id", 0)))
            if not latest.get("node_id"):
                raise EvidenceError("current summary has no GitHub node id")
            latest["review_history"] = _fetch_history(latest["node_id"], token)
    # History and the timeline take separate calls. Refresh the comments so a manual request
    # posted during those reads is a barrier too; never attach one comment's history to another.
    histories = {c["id"]: c["review_history"] for c in comments if "review_history" in c}
    fresh_comments = _paged(f"repos/{repo}/issues/{number}/comments", token)
    for comment in fresh_comments:
        if comment.get("id") in histories:
            comment["review_history"] = histories[comment["id"]]
    final_pull = _github(f"repos/{repo}/pulls/{number}", token)
    fields = ("draft", "created_at", "title", "body", "updated_at")
    head = (pull.get("head") or {}).get("sha")
    if (head != (final_pull.get("head") or {}).get("sha")
            or any(pull.get(key) != final_pull.get(key) for key in fields)):
        raise SnapshotChanged("pull request changed during the evidence read; polling a fresh snapshot")
    return State(fresh_comments, pull.get("body"), commits, draft if isinstance(draft, bool) else None,
                 pull.get("title"), messages, pull.get("created_at"), timeline, head)


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
         sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
         wall: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> int:
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
        try:
            state = State(*fetch())
        except SnapshotChanged as exc:
            verdict, message = "wait", f"review-gate: {exc}"
        except Exception as exc:  # noqa: BLE001 - API failures never publish success; retries are F57, not F58
            print(f"review-gate: failed to read trusted GitHub evidence: {type(exc).__name__}", flush=True)
            return 1
        else:
            verdict, message = decide(head, state.comments, state.body, state.commits, resolve, pr_draft=state.draft,
                                      pr_title=state.title, pr_commit_messages=state.commit_messages,
                                      pr_created_at=state.created_at, pr_timeline=state.timeline, pr_head=state.head,
                                      now=wall())
        print(message, flush=True)
        if verdict == "pass":
            return 0
        if verdict == "fail":
            return 1
        if clock() - started >= timeout:
            print(f"review-gate: timed out after {timeout / 60:g} minutes waiting for trusted, clean review evidence "
                  f"for {head[:7]}. Read the preceding reason. Let pending reviews settle (a review open an hour counts as "
                  "abandoned), then re-run this job. "
                  "For an unreviewed new head, request @codex review and wait; do not add a manual request at a "
                  "ready mark, which already triggers its own review. If that ready cycle is missing or its history "
                  "was lost, let pending reviews settle or turn an hour old before a fresh draft-to-ready transition. Normal fix pushes "
                  "stay ready. If the review service is unavailable, record the substitute review in a "
                  "`Review override: <reason>` line under the repository's override rule.", flush=True)
            return 1
        sleep(poll)


if __name__ == "__main__":
    sys.exit(main())
