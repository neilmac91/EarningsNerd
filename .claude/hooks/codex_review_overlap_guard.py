"""PreToolUse hook: refuse a ready mark or a Codex review request while a Codex review of the pull
request is still running, or asked for and not yet shown (lessons/ops-merge-after-the-ready-marks-own-codex-review.md).

Marking a pull request ready and commenting the review command each start a Codex review. One started
while another review of the pull request runs can strand the running one: it never completes, and
review-gate (backend/scripts/review_gate.py) then waits on its open start until that review is an hour
old, or, when it was the ready mark's own review, cannot pass until a fresh draft-to-ready transition.
On #1530 a review request 1m47s into the ready review of b72df2c4 cost two gate failures and the hour.
This hook stops such a call before it is made.

.claude/settings.json runs it before every Bash command and every call to an MCP server whose name
contains "github" in any case. It acts on:
- a GitHub MCP server's add_issue_comment whose body is the review command alone, with at most the
  attribution footer (codex_mention_guard.py's REVIEW_REQUEST: the one form that guard lets through);
- a GitHub MCP server's update_pull_request with `draft` false, the ready mark;
- a Bash line that is that review command through `gh pr comment` or `gh issue comment`
  (codex_mention_guard.py's _is_review_request_command), or that runs, as a command of the line,
  `gh pr ready` (not --undo, --help or -h) or an API call naming a pull request's `ccr/ready_for_review`,
  the ready route of Claude Code's remote sessions (`gh api`, or curl, wget or httpie naming it): a word of the
  call with no space in it that names the route as a path segment counts as its endpoint, whichever argument
  it is, and a word with a space (a request body, a --jq filter) names none.
  codex_mention_guard.py's shell reader splits the line, and a comment, which runs nothing, is dropped. The
  program is the command's own word, after assignments and the words that run the word after them (`if`,
  `!`, a subshell's `(`), or the first word naming it after a wrapper (sudo, env, timeout, nice, xargs and
  the like). Its pull request is the number (`7`, `'#7'`) or URL the command names; its repository the
  URL's, -R/--repo's, a GH_REPO= assignment's or the environment's, or else the working directory's
  `origin`; the same fills in a `gh api` route's {owner} and {repo}, as gh does.
For each, it reads the pull request through GitHub's REST API, starting no read once one 30-second budget
for the whole call is spent, and refuses at the first of these that holds:
- the newest Codex summary comment (review_gate's SUMMARY_MARKER, by the Codex app's exact identity)
  shows a review Running under the abandonment age (review_gate's _review and _open_at: F58 call 1);
- a review Codex was asked for in the last five minutes has not shown in that summary yet: a review
  command a person posted, a ready mark (the pull request's timeline), or the pull request's opening when it
  was opened ready, each newer than the review the summary's row shows (Codex shows a review some seconds
  after the call; an edit that only re-renders the summary keeps the row's time);
- where the summary's edit history can be read (GraphQL: it needs a token, and Claude Code's remote sessions
  are refused it), review_gate's own replay holds a review open (_history, _require_no_live_start): one a
  newer review's completion hides, one begun while its twin ran, or a version too young to rule one out.
Its reason names the review and when it stops counting. A pull request with no summary and nothing asked for
has no review to strand, and a ready mark on a pull request already ready starts none, unless the same line
first turns it back to draft (`gh pr ready --undo`, or `ccr/convert_to_draft`), or turns back to draft a pull
request the hook cannot name. The reads go through review_gate's own (_paged, _fetch_history), with the
hook's transport swapped in for _github and _graphql.

A gh command that names its pull request by branch or not at all, an API route that names it through a
variable, or a command naming no repository where the working directory has no `origin`, is refused too, asking
for the number or URL (and -R OWNER/REPO): the caller can always say which pull request it means. When the hook
cannot read for other reasons, it lets the call through unchecked and tells Claude so (`additionalContext`),
naming the summary to read: a repository or pull request URL on another host, an `origin` there or one git
cannot read, a GitHub MCP call without its owner, repository or number, no GitHub token (GH_TOKEN, GITHUB_TOKEN
or `gh auth token`), a read that fails or outlasts the budget, an edit history GitHub fails to serve, a newest
summary review_gate cannot parse, or an edit history it will not trust (an untrusted editor; a summary edited
between the reads, after one retry). A history GitHub refuses (GraphQL's 403, as in Claude Code's remote
sessions, unless an x-ratelimit-remaining of 0 or a retry-after marks it a rate limit's) or has none of (a
summary never edited) is skipped: the summary's own state has been read. A guard that blocked where it cannot
read would hold every ready mark and review request of a session that cannot reach GitHub; review-gate still
checks the cycles before a merge. The token goes to api.github.com only, and is dropped on a redirect to
another host or scheme; CODEX_OVERLAP_GUARD_API, the tests' loopback fake, gets none. A refusal is a JSON deny
on stdout; a call with nothing to check exits 0 with no output. A crash exits 1, which Claude Code reports as a
hook error and lets the call through, as for codex_mention_guard.py.

Not checked: a ready mark through GraphQL (`gh api graphql` with markPullRequestReadyForReview) or any route
other than those above; a command run through another shell (`bash -c '...'`, ssh), after a leading
redirection (`2>/dev/null gh ...`), in a case arm or in a function's body; a draft step inside a command
substitution, whose text the shell reader reads after the rest of its line; a line that changes
directory before naming a pull request by number alone (the event's working directory names the
repository); a repository gh takes over `origin` for a number alone or a `gh api` placeholder (an `upstream`
remote, `gh repo set-default`, a GH_REPO exported earlier on the line); a route a variable or a substitution
holds whole (`gh api -X POST "$ROUTE"`); a person's own ready mark or comment; a review a push
starts (none here); a security review (codex_mention_guard.py refuses its command); a session that loads no
repository hooks, and Codex and Astra sessions, which hold the rule by hand (AGENTS.md §5).
review_gate.py's names above are this hook's contract with the gate: a change to them changes this hook too,
so run backend/tests/unit/test_codex_review_overlap_guard.py as well.
Tests: backend/tests/unit/test_codex_review_overlap_guard.py.
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

HOOKS = Path(__file__).resolve().parent
GATE_DIR = HOOKS.parents[1] / "backend" / "scripts"  # review_gate.py, imported only when a call needs a read
sys.path.insert(0, str(HOOKS))  # -I leaves the hooks directory off sys.path
import codex_mention_guard as mention  # noqa: E402  the review command's accepted forms and the shell reader

API = "https://api.github.com"
API_ENV = "CODEX_OVERLAP_GUARD_API"  # the tests' loopback fake; it never receives the token
BUDGET = 30.0  # seconds for everything one call reads, subprocesses included; the registration's timeout is 45
REQUEST_TIMEOUT = 10.0
PENDING = timedelta(minutes=5)  # how long a review Codex was asked for counts before its summary shows it
LESSON = "lessons/ops-merge-after-the-ready-marks-own-codex-review.md"
NAME = ".claude/hooks/codex_review_overlap_guard.py"
OWNER_REPO = re.compile(r"[\w.-]+")
NUMBER = re.compile(r"#?(\d{1,9})")
# A -R/--repo or GH_REPO value: OWNER/REPO, HOST/OWNER/REPO, or a URL.
REPO_FLAG = re.compile(r"^(?:https?://)?(?:(?P<host>[^/\s]+)/)?(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$")
PR_URL = re.compile(r"^https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/(?:pull|issues)/"
                    r"(?P<number>\d{1,9})(?:[/?#].*)?$")
REMOTE = re.compile(r"github\.com[:/]+(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$")
# Claude Code's remote sessions mark a pull request ready, or turn it back to draft, through these API routes.
CCR_ROUTE = re.compile(r"(?:^|/)repos/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pulls/(?P<number>\d{1,9})"
                       r"/ccr/(?P<route>ready_for_review|convert_to_draft)(?![\w-])")
# A word naming one of them as a path segment, whether CCR_ROUTE reads it or not (a word with a space is none).
CCR_WORD = re.compile(r"(?:^|/)ccr/(?P<route>ready_for_review|convert_to_draft)(?![\w-])")
BACKQUOTE = re.compile(r"`([^`\\]*)`")  # read as $(...), so the shell reader takes its text out of the word
GH_PLACEHOLDER = re.compile(r"\{(?:owner|repo)\}")  # `gh api` fills these in from the repository it takes
API_CLIENTS = ("curl", "wget", *mention.HTTPIE)
PROGRAMS = ("gh", *API_CLIENTS)
KEYWORDS = ("(", "{", "!", "if", "then", "elif", "else", "do", "while", "until")  # each runs the word after it
WRAPPERS = ("sudo", "env", "command", "exec", "nohup", "time", "timeout", "nice", "ionice", "stdbuf", "xargs")
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
# review_gate's _latest_request reads a request so, in lower case; here any case counts, the side of waiting
REQUEST_COMMAND = re.compile(r"^@codex review(?:\s|$)", re.IGNORECASE)
REVIEW_REQUEST = "the review request"
READY_MARK = "the ready mark"


class Unchecked(Exception):
    """The hook cannot tell whether a review is open; the call goes through with a note to Claude."""


class Rephrase(Exception):
    """The command names its pull request in a way the hook cannot read and the caller can fix: refused."""


class Target(NamedTuple):
    action: str  # REVIEW_REQUEST or READY_MARK
    owner: str
    repo: str
    number: int
    after_draft: bool = False  # the same line turns the pull request back to draft first

    @property
    def name(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def _number(value: object) -> int | None:
    """A pull request number as a tool sends it: a positive int, a whole float or a string of digits."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float) and value.is_integer() and 0 < value < 10**9:
        return int(value)
    if isinstance(value, str) and (match := NUMBER.fullmatch(value.strip())) and int(match[1]) > 0:
        return int(match[1])
    return None


def _mcp_target(tool: str, tool_input: dict) -> Target | None:
    parts = tool.split("__")
    if len(parts) < 3 or parts[0] != "mcp" or "github" not in parts[1].lower():
        return None
    if parts[-1] == "add_issue_comment":
        body = tool_input.get("body")
        if not (isinstance(body, str) and mention.REVIEW_REQUEST.fullmatch(body)):
            return None
        action, number = REVIEW_REQUEST, _number(tool_input.get("issue_number"))
    elif parts[-1] == "update_pull_request":
        if tool_input.get("draft") not in (False, "false"):
            return None
        action, number = READY_MARK, _number(tool_input.get("pullNumber"))
    else:
        return None
    owner, repo = tool_input.get("owner"), tool_input.get("repo")
    if not (isinstance(owner, str) and isinstance(repo, str) and OWNER_REPO.fullmatch(owner)
            and OWNER_REPO.fullmatch(repo) and number):
        raise Unchecked(f"{action} names no pull request the hook can read")
    return Target(action, owner, repo, number)


def _command_words(words: list[str]) -> tuple[str | None, list[str]]:
    """A command's GH_REPO= assignment and its words from the program on. Leading assignments and the words
    that run the word after them (`if`, `!`, a subshell's `(`) are stepped over; after a wrapper that runs a
    command (sudo, env, timeout, nice, xargs and the like), the program is the first word naming gh or an API
    client, past the wrapper's options and their values."""
    gh_repo, i = None, 0
    while i < len(words) and (ASSIGNMENT.match(words[i]) or words[i] in KEYWORDS):
        if words[i].startswith("GH_REPO="):
            gh_repo = words[i][len("GH_REPO="):]
        i += 1
    if i == len(words) or words[i].rsplit("/", 1)[-1] not in WRAPPERS:
        return gh_repo, words[i:]
    for j in range(i + 1, len(words)):
        if words[j].startswith("GH_REPO="):
            gh_repo = words[j][len("GH_REPO="):]
        elif words[j].rsplit("/", 1)[-1] in PROGRAMS:
            return gh_repo, words[j:]
    return gh_repo, []


def _gh_parts(words: list[str]) -> tuple[str | None, list[str], list[str]] | None:
    """For a command whose program is gh (`gh`, or a path ending in /gh), the -R/--repo value (else its
    GH_REPO= assignment's), the words after gh that are no option (the noun, the verb, the selector) and its
    flags. A comment's --body/-b value is its text, no word of the command."""
    gh_repo, words = _command_words(words)
    if not words or not (words[0] == "gh" or words[0].endswith("/gh")):
        return None
    repo, positional, flags, rest, i = gh_repo, [], [], words[1:], 0
    while i < len(rest):
        word = rest[i]
        if word in ("-R", "--repo", "--body", "-b"):
            if word in ("-R", "--repo") and i + 1 < len(rest):
                repo = rest[i + 1]
            i += 2
            continue
        if word.startswith("--repo="):
            repo = word[len("--repo="):]
        elif word.startswith("-R") and len(word) > 2:
            repo = word[2:]
        elif word.startswith("-"):
            flags.append(word)
        else:
            positional.append(word)
        i += 1
    return repo, positional, flags


@functools.cache
def _remote(cwd: object, deadline: float) -> tuple[str, str]:
    """The working directory's origin, which names the repository for a gh command that names none."""
    import subprocess

    directory = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    try:
        url = subprocess.run(["git", "-C", directory, "config", "--get", "remote.origin.url"], capture_output=True,
                             text=True, check=False,
                             timeout=max(0.1, min(5.0, deadline - time.monotonic()))).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise Unchecked(f"git could not read the working directory's origin ({type(exc).__name__})") from exc
    if not url:
        raise Rephrase("the working directory has no origin to name its repository: add -R OWNER/REPO")
    match = REMOTE.search(url)
    if not match:
        raise Unchecked("the working directory's origin is not on github.com")
    return match["owner"], match["repo"]


def _repository(repo: str | None, action: str, cwd: object, deadline: float) -> tuple[str, str]:
    repo = repo or os.environ.get("GH_REPO", "").strip() or None
    if repo is None:
        return _remote(cwd, deadline)
    match = REPO_FLAG.match(repo)
    if not match or (match["host"] or "github.com").lower() not in ("github.com", "www.github.com"):
        raise Unchecked(f"{action} names a repository the hook does not read ({repo})")
    return match["owner"], match["repo"]


def _bash_target(action: str, parts: tuple[str | None, list[str], list[str]], cwd: object, deadline: float) -> Target:
    repo, positional, _ = parts
    selector = positional[2] if len(positional) > 2 else None
    if selector is not None and (url := PR_URL.match(selector)):
        return Target(action, url["owner"], url["repo"], int(url["number"]))
    if selector is not None and re.match(r"https?://", selector):
        raise Unchecked(f"{action} names a pull request the hook does not read ({selector})")
    number = NUMBER.fullmatch(selector) if selector is not None else None
    if number is None or int(number[1]) == 0:
        raise Rephrase(f"{action} names its pull request by branch or not at all: name it by number or URL")
    owner, name = _repository(repo, action, cwd, deadline)
    return Target(action, owner, name, int(number[1]))


def _undoes(flags: list[str]) -> bool:
    """`gh pr ready --undo` turns the pull request back to draft; `--undo=false` does not."""
    return any(flag == "--undo" or (flag.startswith("--undo=") and flag[len("--undo="):].lower() not in ("false", "0"))
               for flag in flags)


def _uncommented(script: str) -> str:
    """The shell reader's script without its comments: from a `#` that starts a word outside quotes to the end
    of its line. The shared reader keeps a comment's words, for codex_mention_guard.py refuses a mention there
    too; here they run nothing, and an unquoted `#7` leaves its command naming no pull request."""
    out, i, quoted, start = [], 0, False, True
    while i < len(script):
        char = script[i]
        if quoted:
            quoted = char != "'"
        elif char == "\\":
            out.append(script[i:i + 2])
            i, start = i + 2, False
            continue
        elif char == "#" and start:
            end = script.find("\n", i)
            i = len(script) if end < 0 else end
            continue
        elif char == "'":
            quoted = True
        out.append(char)
        start = not quoted and char in mention.WORD_START
        i += 1
    return "".join(out)


def _api_route(word: str, gh: bool, gh_repo: str | None, cwd: object, deadline: float) -> tuple[str, Target] | None:
    """The ccr route a word of an API call names as its endpoint, with its pull request, or None: a word with a
    space in it (a request body, a --jq filter) is no endpoint. `gh api` fills in {owner} and {repo} itself; a
    route the hook still cannot read (a variable) is refused, asking for it written out."""
    named = CCR_WORD.search(word)
    if named is None or re.search(r"\s", word):
        return None
    if gh and GH_PLACEHOLDER.search(word):
        try:
            owner, repo = _repository(gh_repo, READY_MARK, cwd, deadline)
        except Rephrase as exc:  # `gh api` takes no -R
            raise Rephrase(f"an API call names ccr/{named['route']} through {{owner}}/{{repo}} where the working "
                           "directory has no origin: write the repository out") from exc
        word = word.replace("{owner}", owner).replace("{repo}", repo)
    route = CCR_ROUTE.search(word)
    if route is None:
        raise Rephrase(f"an API call names ccr/{named['route']} with its repository or number in a form the hook "
                       "cannot read: write them out")
    return route["route"], Target(READY_MARK, route["owner"], route["repo"], int(route["number"]))


def _key(target: Target) -> tuple[str, str, int]:
    return target.owner.lower(), target.repo.lower(), target.number  # GitHub reads a name in any case


def _bash_targets(command: str, cwd: object, deadline: float) -> list[Target | Unchecked | Rephrase]:
    """The calls this line makes that start a Codex review, in the line's order, each flagged when an earlier
    command of the line turns its pull request back to draft; or why one cannot be read."""
    found: list[Target | Unchecked | Rephrase] = []
    if "gh" not in command and "ccr/" not in command:
        return found
    if mention.MENTION.search(command) and mention._is_review_request_command(command):
        parts = _gh_parts(mention._tokens(command))
        if parts is not None:
            try:
                found.append(_bash_target(REVIEW_REQUEST, parts, cwd, deadline))
            except (Unchecked, Rephrase) as exc:
                found.append(exc)
        return found
    if not (re.search(r"\bready\b", command) or "ccr/" in command):
        return found
    drafts: set[tuple[str, str, int]] = set()  # the pull requests an earlier command turned back to draft
    unplaced = False  # an earlier command turned back to draft a pull request the hook cannot name: any, maybe
    script = mention._script(BACKQUOTE.sub(r"$(\1)", command))
    for _, words in mention._commands(mention._command_tokens(_uncommented(script))):
        gh_repo, program = _command_words(words)
        if not program:
            continue
        name = program[0].rsplit("/", 1)[-1]
        if name in API_CLIENTS or (name == "gh" and program[1:2] == ["api"]):
            for word in program:
                try:
                    route = _api_route(word, name == "gh", gh_repo, cwd, deadline)
                except (Unchecked, Rephrase) as exc:  # raised only for a word CCR_WORD names
                    if CCR_WORD.search(word)["route"] == "convert_to_draft":
                        unplaced = True  # it starts no review, but a later ready mark may then start one
                    else:
                        found.append(exc)
                    continue
                if route is None:
                    continue
                kind, target = route
                if kind == "convert_to_draft":
                    drafts.add(_key(target))
                else:
                    found.append(target._replace(after_draft=unplaced or _key(target) in drafts))
            continue
        parts = _gh_parts(words)
        if parts is None or parts[1][:2] != ["pr", "ready"] or {"--help", "-h"} & set(parts[2]):
            continue
        undo = _undoes(parts[2])
        try:
            target = _bash_target(READY_MARK, parts, cwd, deadline)
        except (Unchecked, Rephrase) as exc:
            if undo:
                unplaced = True  # it starts no review, but a later ready mark may then start one
            else:
                found.append(exc)
            continue
        if undo:
            drafts.add(_key(target))
        else:
            found.append(target._replace(after_draft=unplaced or _key(target) in drafts))
    return found


@functools.cache
def _token(deadline: float) -> str | None:
    """The session's GitHub token: GH_TOKEN, GITHUB_TOKEN, else the one gh holds."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    import shutil
    import subprocess

    gh = shutil.which("gh")
    if gh:
        try:
            out = subprocess.run([gh, "auth", "token", "--hostname", "github.com"], capture_output=True, text=True,
                                 check=False, timeout=max(0.1, min(5.0, deadline - time.monotonic())))
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def _same_host_redirects():
    """urllib's redirect handler, dropping the Authorization header on a redirect to another host or scheme."""
    import urllib.parse
    import urllib.request

    class SameHostRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # urllib's signature
            new = super().redirect_request(req, fp, code, msg, headers, newurl)
            moved, asked = urllib.parse.urlsplit(newurl), urllib.parse.urlsplit(req.full_url)
            if new is not None and (moved.scheme, moved.netloc) != (asked.scheme, asked.netloc):
                new.remove_header("Authorization")
            return new

    return SameHostRedirect


class _Reader:
    """GitHub reads for one call: the token goes to api.github.com only, and no request starts once the call's
    budget is spent; each waits on its socket at most REQUEST_TIMEOUT or what the budget had left."""

    def __init__(self, token: str | None, deadline: float) -> None:
        import urllib.request

        self.base = os.environ.get(API_ENV, "").rstrip("/") or API
        self.token = token if self.base == API else None
        self.deadline = deadline
        self.opener = urllib.request.build_opener(_same_host_redirects())

    def request(self, path: str, payload: dict | None = None) -> object:
        import urllib.request

        left = self.deadline - time.monotonic()
        if left <= 0:
            raise Unchecked(f"GitHub did not answer within {BUDGET:g} seconds")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "earningsnerd-codex-review-overlap-guard"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(f"{self.base}/{path}", data=data, headers=headers,
                                         method="POST" if data is not None else "GET")
        # nosec B310: api.github.com, or the tests' loopback fake named by CODEX_OVERLAP_GUARD_API
        with self.opener.open(request, timeout=min(REQUEST_TIMEOUT, left)) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))


def _when(value: object, gate: object) -> datetime | None:
    try:
        return gate._timestamp(value)
    except gate.EvidenceError:
        return None


def _pending(target: Target, comments: list[dict], shown: datetime | None, reader: _Reader, gate: object,
             now: datetime) -> str | None:
    """A review Codex was asked for in the last PENDING that its summary does not show yet, as a reason. `shown`
    is the time of the review the summary's row shows, None with no summary: an edit that only re-renders the
    summary (a finding resolved) keeps it."""

    def waiting(at: datetime | None) -> bool:
        return at is not None and (shown is None or at > shown) and now - at < PENDING

    def counts_until(at: datetime) -> str:
        return (at + PENDING).strftime("%Y-%m-%dT%H:%M:%SZ")

    for comment in sorted(comments, key=lambda item: str(item.get("created_at")), reverse=True):
        at = _when(comment.get("created_at"), gate)
        body = str(comment.get("body") or "")
        if (comment.get("user") or {}).get("type") == "User" and REQUEST_COMMAND.match(body) and waiting(at):
            return (f"a review request posted at {at:%H:%M:%S}Z has not shown in Codex's summary yet; it stops counting "
                    f"at {counts_until(at)}")
    path = f"repos/{target.owner}/{target.repo}"
    events = gate._paged(f"{path}/issues/{target.number}/timeline", reader.token)
    marks = [at for event in events if isinstance(event, dict) and event.get("event") == "ready_for_review"
             and (at := _when(event.get("created_at"), gate)) is not None]
    if marks and waiting(max(marks)):
        at = max(marks)
        return (f"the ready mark at {at:%H:%M:%S}Z has not shown its review in Codex's summary yet; it stops counting "
                f"at {counts_until(at)}")
    if shown is None and not marks and not any(isinstance(e, dict) and e.get("event") == "convert_to_draft"
                                                for e in events):
        pull = reader.request(f"{path}/pulls/{target.number}")
        opened = _when(pull.get("created_at"), gate) if isinstance(pull, dict) else None
        if isinstance(pull, dict) and pull.get("draft") is False and waiting(opened):
            return (f"the pull request opened ready at {opened:%H:%M:%S}Z has not shown its review in Codex's summary "
                    f"yet; it stops counting at {counts_until(opened)}")
    return None


def _open_review(target: Target, reader: _Reader, gate: object) -> str | None:
    """Why a review of the pull request may still be running, or None when none is."""
    path = f"repos/{target.owner}/{target.repo}"
    if target.action == READY_MARK and not target.after_draft:
        pull = reader.request(f"{path}/pulls/{target.number}")
        draft = pull.get("draft") if isinstance(pull, dict) else None
        if not isinstance(draft, bool):
            raise Unchecked("GitHub did not say whether the pull request is a draft")
        if not draft:
            return None  # already ready: the mark starts no review
    for attempt in (1, 2):
        now = datetime.now(timezone.utc)
        comments = gate._paged(f"{path}/issues/{target.number}/comments", reader.token)
        summaries = [comment for comment in comments if gate.is_codex_bot(comment.get("user"))
                     and gate.SUMMARY_MARKER in str(comment.get("body") or "")]
        latest = (max(summaries, key=lambda c: (gate._timestamp(c.get("created_at")), c.get("id", 0)))
                  if summaries else None)
        current = None
        if latest is not None:
            try:
                current = gate._review(str(latest.get("body") or ""))
            except gate.EvidenceError as exc:
                raise Unchecked(f"review-gate cannot read the summary's newest version: {exc}") from exc
            if current.status == "running" and gate._open_at(current, now):
                return (f"a Codex review of {current.short} ({current.trigger}) started at {current.at:%H:%M:%S}Z "
                        f"has not completed; it counts as abandoned from {gate._abandoned_from(current)}")
        pending = _pending(target, comments, current.at if current is not None else None, reader, gate, now)
        if pending is not None:
            return pending
        if latest is None or not (reader.token or reader.base != API):
            return None  # nothing more to read: GraphQL needs a token
        if not isinstance(latest.get("node_id"), str) or not latest["node_id"]:
            raise Unchecked("the Codex summary comment has no GitHub node id")
        try:
            history = gate._fetch_history(latest["node_id"], reader.token)
        except Exception as exc:  # noqa: BLE001 - every failure but GraphQL's refusal is noted
            headers = getattr(exc, "headers", None)
            limited = headers is not None and (headers.get("x-ratelimit-remaining") == "0" or headers.get("retry-after"))
            if getattr(exc, "code", None) == 403 and not limited:
                return None  # GraphQL refused, as Claude Code's remote sessions are: the summary's own state was read
            if isinstance(exc, Unchecked):
                raise
            raise Unchecked(f"the summary shows no review running, but its edit history, where a newer review's "
                            f"completion can hide one, could not be read ({type(exc).__name__}: {exc})") from exc
        if not history:
            return None  # never edited: its one version is the body read above
        latest["review_history"] = history
        try:
            states = gate._history(latest)
        except gate.EvidenceError as exc:
            if attempt == 1 and "disagrees with the current REST comment" in str(exc):
                continue  # Codex edited the summary between the two reads: read both again once
            raise Unchecked(f"review-gate would not trust the summary's history: {exc}") from exc
        try:
            gate._require_no_live_start(states, now)
        except gate.EvidenceError as exc:
            return str(exc)
        return None
    return None


def _check(target: Target, deadline: float) -> str | None:
    """Why `target` must wait, or None to let it through; Unchecked when the hook cannot tell."""
    if str(GATE_DIR) not in sys.path:
        sys.path.insert(0, str(GATE_DIR))
    import review_gate as gate

    token = _token(deadline)
    reader = _Reader(token, deadline)
    if reader.base == API and not token:
        raise Unchecked("no GitHub token (GH_TOKEN, GITHUB_TOKEN or `gh auth token`) reads the pull request")

    def rest(path: str, _token: str | None) -> object:
        return reader.request(path)

    def graphql(query: str, variables: dict, _token: str | None) -> object:
        result = reader.request("graphql", {"query": query, "variables": variables})
        if not isinstance(result, dict) or result.get("errors"):
            raise gate.EvidenceError("GitHub could not read the summary edit history")
        return result.get("data")

    gate._github, gate._graphql = rest, graphql  # the gate's reads, through this call's transport and budget
    try:
        return _open_review(target, reader, gate)
    except Unchecked:
        raise
    except Exception as exc:  # noqa: BLE001 - HTTP, network, JSON and evidence failures all leave it unknown
        raise Unchecked(f"the read failed ({type(exc).__name__}: {exc})") from exc


def verdict(event: object) -> tuple[str, str] | None:
    """("deny", reason) to refuse the call, ("note", text) to let it through with a note to Claude, or None."""
    if not isinstance(event, dict):
        return None
    tool, tool_input = event.get("tool_name"), event.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return None
    deadline = time.monotonic() + BUDGET  # one budget for every read and subprocess of this call
    if tool == "Bash":
        command = tool_input.get("command")
        found = _bash_targets(command, event.get("cwd"), deadline) if isinstance(command, str) else []
    else:
        try:
            target = _mcp_target(tool, tool_input)
        except Unchecked as exc:
            target = exc
        found = [target] if target is not None else []
    rephrase, notes = [], []
    for item in found:
        if isinstance(item, Rephrase):
            rephrase.append(str(item))
            continue
        if isinstance(item, Unchecked):
            notes.append(str(item))
            continue
        try:
            reason = _check(item, deadline)
        except Unchecked as exc:
            notes.append(f"{item.action} on {item.name}: {exc}")
            continue
        if reason is not None:  # the first overlap decides: no later read can unmake it
            return "deny", (
                f"Refused by {NAME}: {item.action} on {item.name} would start a Codex review while another may "
                f"still be running: {reason}. A review started while another runs can strand it: review-gate then "
                "waits on the stranded review until it is an hour old, or cannot pass until a fresh draft-to-ready "
                f"transition ({LESSON}). Send it once Codex's summary shows that review completed, or from the time "
                "named, when it stops counting.")
    if rephrase:
        return "deny", (
            f"Refused by {NAME}: " + "; ".join(rephrase) + ". Before a ready mark or a review request it reads the "
            "pull request's Codex summary, which needs the pull request's number or URL, and its repository where "
            f"the working directory's origin is not on github.com ({LESSON}). Send it again so.")
    if notes:
        return "note", (
            f"{NAME} let this call through unchecked: " + "; ".join(notes) + ". Read the pull request's Codex "
            "summary comment: a review it showed Running when this call went through can be stranded, and "
            f"review-gate would then wait on it until it is an hour old ({LESSON}).")
    return None


def main() -> int:
    result = verdict(json.load(sys.stdin.buffer))
    if result is not None:
        kind, text = result
        output: dict[str, str] = {"hookEventName": "PreToolUse"}
        if kind == "deny":
            output.update(permissionDecision="deny", permissionDecisionReason=text)
        else:
            output["additionalContext"] = text
        json.dump({"hookSpecificOutput": output}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
