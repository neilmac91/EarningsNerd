"""PreToolUse hook: refuse an agent's merge whose typed commit title or message puts a closing keyword
before an issue or pull request reference.

The second gate for lessons/ops-closing-keywords-close-what-they-name.md. GitHub closes what a closing
keyword names (close, fix or resolve in any form, then #N, OWNER/REPO#N and the like) when a commit that
carries it reaches the default branch, a pull request included. review-gate (backend/scripts/review_gate.py)
fails a pull request whose title, body or commit messages carry one, which covers GitHub's default squash
message: the title, or the one commit's subject, then every commit message. It cannot see a message typed
at the merge itself. This hook reads that message where an agent types it, with the gate's own
`closing_references` (loaded from backend/scripts/review_gate.py, so the two share one pattern):
- a call to a GitHub MCP server (a name containing "github" in any case): every string argument of a merge
  tool (a name containing "merge"; merge_pull_request types commit_title and commit_message), at any depth,
  and any other tool's commit text under REST's or GraphQL's names in either spelling (`commit_title`,
  `commit_message`, `commitHeadline`, `commitBody`);
- a shell line (Bash's, or a Monitor's command) that runs `gh pr merge` (gh as a word or a path, -R/--repo
  before the noun or the verb, the words quoted or not), that calls a REST merge endpoint (`/merge` or
  `/merges` with `gh api` or api.github.com), or that calls the GraphQL API (`graphql` with `gh api` or
  api.github.com) with a merge mutation (mergePullRequest, enablePullRequestAutoMerge, mergeBranch) on the
  line or in a file it sends. It reads the whole line, as written and as the shell joins it (quotes,
  backslashes and continuations removed), here-document text included, and every file the line names to
  send or read: an option's file (gh pr merge's `--body-file`/`-F`, gh api's `--input` and
  `-F`/`--field key=@file`, curl's `-d`/`--data`/`--json @file` and `-T`, wget's `--body-file`), an
  `@file` word (httpie's `field=@file`), a `<` redirect's target (`$(<file)` too), and each file a plain
  `cat` reads, piped or inside `$(...)`, `<(...)` or backticks. A name is read as the shell passes it:
  escapes resolved, `~` expanded, and a glob expanded to its first 16 files.
A merge with no typed message passes: its message is the default the gate has read. Reading the whole line,
and every file it names, refuses more than the merge's own message (another command on the line that names
a closing reference); the remedy, rewording, is cheap.

A refusal is a JSON deny on stdout, which Claude Code hands to Claude as the reason; anything else exits 0
with no output. A crash exits 1, which Claude Code reports as a hook error and lets the call through. The
registered command (`python3 -I -S`: standard library only) maps Python's own exit 2 (a script it cannot
open) to 1, so a broken install never blocks every Bash command and every GitHub call.

Not checked: text the shell or a command builds as the line runs (a variable, an ANSI-C `$'...'` escape,
the output of any command but a plain `cat`, a line handed to another shell that way; a literal
`bash -c '...'` is on the line and read); a file over 1 MiB, or named relative to a directory the line
changes into first; a merge a script or a gh alias runs; a GitHub MCP server registered under a name
without "github"; a session that loads no repository hooks; and a person's own merge.
Tests: backend/tests/unit/test_closing_keyword_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import sys
from glob import iglob
from itertools import islice
from pathlib import Path

# The commit text a merge call types: REST's commit_title and commit_message, GraphQL's commitHeadline and
# commitBody, compared with underscores dropped and case folded so either spelling counts.
COMMIT_FIELDS = ("committitle", "commitmessage", "commitheadline", "commitbody")
SHELLS = ("Bash", "Monitor")  # the tools whose `command` a shell runs
_REPO = r"(?:\s+(?:-R\s*\S+|--repo(?:=|\s+)\S+))*"  # gh takes -R/--repo before the noun and before the verb
GH_MERGE = re.compile(rf"(?:^|[\s/;&|(`$])gh{_REPO}\s+pr{_REPO}\s+merge\b")
MERGE_ENDPOINT = re.compile(r"/merges?\b")
GH_API = re.compile(r"(?:^|[\s/;&|(`$])gh\s+api\b")
GRAPHQL = re.compile(r"\bgraphql\b", re.IGNORECASE)
MERGE_MUTATION = re.compile(r"\b(?:mergePullRequest|enablePullRequestAutoMerge|mergeBranch)\b", re.IGNORECASE)
# A shell word: quoted, or unquoted with backslash escapes.
_WORD = r"""(?:'[^'\n]*'|"[^"\n]*"|(?:[^\s;&|()<>'"`\\]|\\.)+)"""
# A file name: a word, a lone `-` (standard input), and never a word that starts with `-` (that is the next
# option, as in `-d --body-file msg.md`, where -d is gh pr merge's --delete-branch).
_VALUE = r"""('[^'\n]*'|"[^"\n]*"|-(?![^\s;&|()<>])|(?:[^\s;&|()<>'"`\\-]|\\.)(?:[^\s;&|()<>'"`\\]|\\.)*)"""
# The files a line sends: an option whose value is, or names with `@`, a file (gh pr merge's --body-file
# and -F, gh api's --input and -F/--field key=@file, curl's -d/--data/--data-binary/--data-ascii/--json
# @file and -T/--upload-file, wget's --body-file; a short flag may close a run of others, as in -sF), an
# `@file` word (httpie's field=@file), a `<` redirect's target, and the files a plain `cat` reads. Regular
# expressions, not shlex: they read a 1 MiB line in milliseconds.
FILE_ARG = re.compile(
    r"""(?:^|[\s;&|(])(?:--(?:body-file|input|field|data(?:-binary|-ascii)?|json|upload-file)(?:=|\s+)"""
    r"""|-[A-Za-z]*[FdT][ \t]*)""" + _VALUE)
AT_FILE = re.compile(r"(?:^|[\s=])@" + _VALUE)
REDIRECT = re.compile(r"(?<![<&])<(?![<(&>])[ \t]*" + _VALUE)
CAT = re.compile(r"(?:^|[\s;&|(`])cat((?:[ \t]+" + _WORD + r")+)")
UNQUOTE = str.maketrans("", "", "'\"\\")
MAX_FILE_BYTES = 1 << 20
MAX_GLOB_FILES = 16
GATE = Path(__file__).resolve().parents[2] / "backend" / "scripts" / "review_gate.py"


def _closing_references():
    """review-gate's own `closing_references`, so the hook and the gate never disagree on what closes."""
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("_review_gate", GATE)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.closing_references


def _commit_texts(value: object, field: str | None = None, every: bool = False):
    """Every commit title or message string in a tool call's arguments, at any depth (`every`: every string)."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _commit_texts(item, key, every)
    elif isinstance(value, list):
        for item in value:
            yield from _commit_texts(item, field, every)
    elif isinstance(value, str) and (every or (
            isinstance(field, str) and field.replace("_", "").lower() in COMMIT_FIELDS)):
        yield field or "an argument", value


def _name(word: str) -> str:
    """A shell word as the shell passes it: quotes stripped, backslash escapes resolved."""
    if word[:1] in ("'", '"'):
        return word[1:-1]
    return re.sub(r"\\(.)", r"\1", word, flags=re.DOTALL)


def _plain(command: str) -> str:
    """The line with its quotes, backslashes and line continuations removed, as the shell joins its words."""
    return command.replace("\\\n", "").translate(UNQUOTE)


def _merge_kind(command: str) -> str | None:
    """"merge" when the line runs `gh pr merge` or calls a REST merge endpoint, "graphql" when it calls the
    GraphQL API (a merge only with a merge mutation), else None; read as written and with its quotes removed."""
    kind = None
    for text in (command, _plain(command)):
        api = bool(GH_API.search(text)) or "api.github.com" in text.lower()
        if GH_MERGE.search(text) or (api and MERGE_ENDPOINT.search(text)):
            return "merge"
        if api and GRAPHQL.search(text):
            kind = "graphql"
    return kind


def _body_files(command: str, cwd: object) -> list[tuple[str, str]]:
    """The text of each regular file, up to 1 MiB, that the line sends or reads: an option's file, one an `@`
    names (`commit_message=@msg.md`, `-d @body.json`), a `<` redirect's target, and each file a plain `cat`
    reads, wherever it sits on the line."""
    joined = command.replace("\\\n", "")  # a continuation can split an option from its file
    names = []
    for match in FILE_ARG.finditer(joined):
        value = _name(match.group(1))
        at = value.find("@")
        names.append(value[at + 1:] if at >= 0 and (at == 0 or value[at - 1] == "=") else value)
    names += [_name(match.group(1)) for pattern in (AT_FILE, REDIRECT) for match in pattern.finditer(joined)]
    names += [_name(word) for match in CAT.finditer(joined) for word in re.findall(_WORD, match.group(1))
              if not word.startswith("-")]
    base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    texts = []
    for name in dict.fromkeys(names):
        if name == "-":  # standard input: a here-document is on the line, a redirect or a cat read above
            continue
        pattern = os.path.join(base, os.path.expanduser(name))
        found = islice(iglob(pattern), MAX_GLOB_FILES) if any(char in name for char in "*?[") else (pattern,)
        try:
            for candidate in found:
                path = Path(candidate).resolve()
                if str(path).startswith(("/proc/", "/sys/", "/dev/")):
                    continue
                if path.is_file() and path.stat().st_size <= MAX_FILE_BYTES:
                    texts.append((f"the file {name}", path.read_text(encoding="utf-8", errors="replace")))
        except (OSError, RuntimeError, ValueError):
            continue
    return texts


def _reason(references: list[str]) -> str:
    return (
        "Refused by .claude/hooks/closing_keyword_guard.py: this merge's commit text puts a closing keyword "
        "before an issue or pull request reference (" + "; ".join(references) + "). GitHub closes what it "
        "names when the commit reaches main, a pull request included. Reword each so no form of close, fix or "
        "resolve sits right before the reference (\"addressed in #N\", or the reference first: \"#N carries "
        "the fix\"), or leave the message out to merge with the default, which review-gate has read; close "
        "anything you mean to close by hand after the merge (lessons/ops-closing-keywords-close-what-they-name.md)."
    )


def refusal(event: object) -> str | None:
    """Why this tool call must not run, or None to let it through."""
    if not isinstance(event, dict):
        return None
    tool, tool_input = event.get("tool_name"), event.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return None
    if tool in SHELLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return None
        plain = _plain(command)
        if "merge" not in plain and "graphql" not in plain.lower():
            return None
        kind = _merge_kind(command)
        if kind is None:
            return None
        texts = [("this command", command), ("this command", plain)]
        texts += _body_files(command, event.get("cwd"))
        if kind == "graphql" and not any(MERGE_MUTATION.search(text) for _, text in texts):
            return None
    else:
        parts = tool.split("__")
        if not (len(parts) >= 3 and parts[0] == "mcp" and "github" in parts[1].lower()):
            return None
        # A merge tool's every string may carry its commit text, whatever a server names the field.
        texts = list(_commit_texts(tool_input, every="merge" in "__".join(parts[2:]).lower()))
        if not texts:
            return None
    references = list(dict.fromkeys(_closing_references()(texts)))
    return _reason(references) if references else None


def main() -> int:
    reason = refusal(json.load(sys.stdin.buffer))
    if reason is not None:
        decision = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}
        json.dump({"hookSpecificOutput": decision}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
