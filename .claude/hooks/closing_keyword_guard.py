r"""PreToolUse hook: refuse an agent's merge whose typed commit title or message puts a closing keyword
before an issue or pull request reference.

The second gate for lessons/ops-closing-keywords-close-what-they-name.md. GitHub closes what a closing
keyword names (close, fix or resolve in any form, then #N, OWNER/REPO#N and the like) when a commit that
carries it reaches the default branch, a pull request included. review-gate (backend/scripts/review_gate.py)
fails a pull request whose title, body or commit messages carry one, which covers GitHub's default squash
message: the title, or the one commit's subject, then every commit message. It cannot see a message typed
at the merge itself. This hook reads that message where an agent types it, with the gate's own
`closing_references` (loaded from backend/scripts/review_gate.py, so the two share one pattern):
- a call to a GitHub MCP server (a name containing "github" in any case) that merges: a tool whose name
  contains "merge" (merge_pull_request types commit_title and commit_message), or a request handed as a
  whole string: a GraphQL document or JSON request calling a merge mutation (mergePullRequest(,
  enablePullRequestAutoMerge(, mergeBranch(), the GraphQL endpoint beside such a call, or a REST merge
  target (a method, then a URL, a path or a route, templated or with a query string, ending at a pull
  request's `/merge` or a repository's `/merges`). It reads every string the call is handed, at any depth,
  whatever the server names the field. A call whose text only mentions a merge (a file's content, a
  comment, a search) passes;
- a shell line (Bash's, or a Monitor's command) that runs or names `gh pr merge` (gh as a word or a path,
  -R/--repo before the noun or the verb, the words quoted or not), a REST merge endpoint (`/merge` or
  `/merges` with `gh api` or api.github.com), or a GraphQL call (`graphql` with `gh api` or api.github.com)
  with a merge mutation on the line or in a file it sends. It reads the whole line as written, as the shell
  joins it (quotes, backslashes and continuations removed, here-document text included, and a list's
  brackets and commas read as spaces, so `["gh", "pr", "merge"]` counts), and with gh's
  `-b`/`-t` split from a value attached to them (`-b"Fixes "#3`). It reads every file the line names to
  send or read: an option whose value is a file (gh pr merge's `--body-file`/`-F`, gh api's `--input`,
  curl's `-T`/`--upload-file` and `-K`/`--config`, wget's `--body-file`/`--post-file`), a file an `@` names
  (gh api's `-F`/`--field key=@file`, curl's `-d`/`--data`/`--json @file` and `--variable name@file`,
  httpie's `field=@file`; quoted or attached, as in `-d@file` or `-F=file`), a `<` redirect's target
  (`$(<file)` too), and each file a plain `cat`, by name or path, quoted or escaped (`\cat`), reads, piped or
  inside `$(...)`, `<(...)` or backticks; an option quoted or escaped as a whole word ('-F',
  "--body-file=my notes.md") counts as written plain. A name is read as the shell passes it: its quoted,
  escaped and plain pieces joined, `~` expanded, and an unquoted glob expanded to its first 16 files in the
  C locale's order (to the word itself when nothing matches).
A merge's commit is its title, a blank line, then its message, so a keyword that ends the title closes a
reference that starts the message: each title and message a call types are also read joined that way (gh
pr merge's --subject/-t with its --body/-b or body file; commit_title with commit_message, commitHeadline
with commitBody, wherever a call or a file it sends names them; on MCP, every string of the call in order too).
A merge with no typed message passes: its message is the default the gate has read. Reading the whole line,
and every file it names, refuses more than a merge's own message: another command's text on the same line,
and a line that only names a merge (a comment that quotes `gh pr merge` with a closing reference). The
remedy is cheap: reword, or send such text from a file (`--body-file`), which a line that names no merge
never has read.

A refusal is a JSON deny on stdout, which Claude Code hands to Claude as the reason; anything else exits 0
with no output. A crash exits 1, which Claude Code reports as a hook error and lets the call through, as it
does a hook that outlasts its 10 s timeout; the adversarial 1 MB lines the tests keep read in about a second
or two. The registered command (`python3 -I -S`: standard library only) maps Python's own exit 2 (a script it cannot
open) to 1, so a broken install never blocks every Bash command and every GitHub call.

Not checked: text the shell or a command builds as the line runs (a variable, an ANSI-C `$'...'` escape, a
brace expansion, the output of any command but a plain `cat`, a line handed to another shell that way; a
literal `bash -c '...'` is on the line and read); a file over 1 MiB, a glob's files past its first 16, or a
file named relative to a directory the line changes into first; more than three -R/--repo options in a row
before `pr` or `merge`; a merge a script or a gh alias runs, or whose URL
sits in a file a command reads as its configuration (curl's -K, wget's -i); an MCP request tool that spreads
a merge's target over fields of its own (owner, repository, number, action); a GitHub MCP server registered
under a name without "github"; a session that loads no repository hooks; and a person's own merge.
Tests: backend/tests/unit/test_closing_keyword_guard.py.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

SHELLS = ("Bash", "Monitor")  # the tools whose `command` a shell runs
# gh takes -R/--repo before the noun and before the verb; bounded, so a line of `-R gh` words reads in linear time.
_REPO = r"(?:\s+(?:-R\s*\S+|--repo(?:=|\s+)\S+)){0,3}"
GH_MERGE = re.compile(rf"(?:^|[\s/;&|(`$])gh{_REPO}\s+pr{_REPO}\s+merge\b")
MERGE_ENDPOINT = re.compile(r"/merges?\b")
GH_API = re.compile(r"(?:^|[\s/;&|(`$])gh\s+api\b")
GRAPHQL = re.compile(r"\bgraphql\b", re.IGNORECASE)
MERGE_MUTATION = re.compile(r"\b(?:mergePullRequest|enablePullRequestAutoMerge|mergeBranch)\b", re.IGNORECASE)
# An MCP string that is, as a whole, a merge request: a GraphQL document (after any comments, any operation or
# fragment first) or a JSON request that calls a merge mutation; the GraphQL endpoint, whose call then sits in
# another string; or a REST merge target (a method, then a URL, a path or a route, templated or with a query
# string, ending at a pull request's /merge or a repository's /merges).
MUTATION_CALL = re.compile(r"\b(?:mergePullRequest|enablePullRequestAutoMerge|mergeBranch)\s*\(", re.IGNORECASE)
GRAPHQL_MERGE = re.compile(
    r"\A\s*(?:#[^\n]*\n\s*)*(?:query|mutation|subscription|fragment|\{)[\s\S]*?" + MUTATION_CALL.pattern, re.IGNORECASE)
_TARGET = r"\A\s*(?:[A-Za-z]+\s+)?(?:(?:https?://)?api\.github\.com)?/?"
GRAPHQL_ENDPOINT = re.compile(_TARGET + r"graphql/?(?:\?\S*)?\s*\Z", re.IGNORECASE)
REST_MERGE = re.compile(
    _TARGET + r"(?:repos/[^/\s]+/[^/\s]+/(?:pulls/[^/\s]+/merge|merges)|pulls/[^/\s]+/merge)/?(?:\?\S*)?\s*\Z",
    re.IGNORECASE)
# gh pr merge's -b (body) or -t (subject) with its value attached, after any run of other short flags.
ATTACHED = re.compile(r"(?<!\S)(-[A-Za-z]*?[bt])(?=\S)")
# A shell word: a run of single-quoted, double-quoted, escaped and plain pieces, and each piece of one.
_WORD = r"""(?:'[^'\n]*'|"[^"\n]*"|\\.|[^\s;&|()<>'"`\\])+"""
_VALUE = "(" + _WORD + ")"  # a file name; a lone `-` is standard input
_PIECE = re.compile(r"""'([^'\n]*)'|"([^"\n]*)"|\\(.)|(.)""", re.DOTALL)
# A word with a quoted or escaped piece, from the word's start (so a long plain word is scanned once).
_QUOTED_WORD = re.compile(r"""(?<![^\s;&|()<>`])(?:[^\s;&|()<>'"`\\]*(?:'[^'\n]*'|"[^"\n]*"|\\.))+[^\s;&|()<>'"`\\]*""")
# The files a line sends, read by regular expressions, not shlex (they read a 1 MiB line in milliseconds):
# an option whose value is a file (gh pr merge's --body-file and -F, gh api's --input, curl's
# -T/--upload-file and -K/--config, wget's --body-file and --post-file; a short flag may close a run of
# others, as in -sF); a file an `@` names, which gh api's -F/--field, curl's -d/--data/--json/-F and
# --variable, and httpie's fields read (alone, after `=` or a variable's name, attached to a short option as
# in -d@file, or quoted); a `<` redirect's target; the files a plain `cat` reads. A plain -d or --field value
# is data, not a file.
FILE_ARG = re.compile(
    r"(?:^|[\s;&|(])(?:--(?:body-file|post-file|input|upload-file|config)(?:=|\s+)|-[A-Za-z]*?[FTK]=?[ \t]*)" + _VALUE)
AT_FILE = re.compile(r"(?:^|[\s=]|\s-[A-Za-z]+|--variable(?:=|\s+)[\w.%-]*)@" + _VALUE)
AT_QUOTED = re.compile(r"""(?:^|[\s=]|\s-[A-Za-z]+)(['"])(?:[^'"\n=]*=)?@([^'"\n]*)\1""")
REDIRECT = re.compile(r"(?<![<&])<(?![<(&>])[ \t]*" + _VALUE)
CAT = re.compile(r"""(?:^|[\s;&|(`/])\\?(?:cat|'cat'|"cat")((?:[ \t]+""" + _WORD + r")+)")
# The title and message a call types, joined as GitHub writes its commit: gh pr merge's --subject/-t and
# --body/-b, and GitHub's own field names (REST's commit_title and commit_message, GraphQL's commitHeadline and
# commitBody) as a JSON, GraphQL or field value. At most 16 of each, the last ones (gh keeps a flag's last value).
SUBJECT = re.compile(r"(?:^|[\s;&|(])(?:--subject(?:=|\s+)|-[A-Za-z]*?t=?[ \t]*)" + _VALUE)
BODY = re.compile(r"(?:^|[\s;&|(])(?:--body(?:=|\s+)|-[A-Za-z]*?b=?[ \t]*)" + _VALUE)
COMMIT_PART = re.compile(r"""\b(commit_title|commitHeadline|commit_message|commitBody)\b["']?\s*[:=]\s*"""
                         r"""("(?:[^"\\\n]|\\.)*"|'[^'\n]*'|[^\s,}"']+)""")
TITLE_FIELDS = ("commit_title", "commitHeadline")
MAX_PARTS = 16
UNQUOTE = str.maketrans("", "", "'\"\\")
LIST_PUNCTUATION = re.compile(r"[\[\],]")  # a program's argument list: ["gh", "pr", "merge"]
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


def _strings(value: object, field: str | None = None):
    """Every string in a tool call's arguments, at any depth, with the name it sits under."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, field)
    elif isinstance(value, str):
        yield field or "an argument", value


def _word(word: str) -> tuple[str, str]:
    """A shell word as the shell passes it, and as a glob in which only its unquoted, unescaped part is special."""
    name, pattern = [], []
    for match in _PIECE.finditer(word):
        single, double, escaped, plain = match.groups()
        literal = next((piece for piece in (single, double, escaped) if piece is not None), None)
        name.append(plain if literal is None else literal)
        pattern.append(plain if literal is None else glob.escape(literal))
    return "".join(name), "".join(pattern)


def _dequoted(line: str) -> str:
    """The line with each quoted or escaped word written as the shell passes it ('-F' msg.md becomes -F msg.md),
    so an option quoted or escaped as a whole word is read like a plain one. A word that holds whitespace stays
    as written unless it is an option, whose whitespace is escaped ("--body-file=my notes.md")."""
    def plain(match: re.Match) -> str:
        name = _word(match.group(0))[0]
        if not any(char.isspace() for char in name):
            return name
        return re.sub(r"(\s)", r"\\\1", name) if name.startswith("-") else match.group(0)
    return _QUOTED_WORD.sub(plain, line)


def _read(path: str) -> str | None:
    """A regular file's text, or None for anything else (a pipe, a device, a directory) or a file over 1 MiB."""
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)
    except (OSError, ValueError):
        return None
    return None if len(data) > MAX_FILE_BYTES else data.decode("utf-8", errors="replace")


def _plain(command: str) -> str:
    """The line with its quotes, backslashes and line continuations removed, as the shell joins its words."""
    return command.replace("\\\n", "").translate(UNQUOTE)


def _merge_kind(command: str) -> str | None:
    """"merge" when the line runs `gh pr merge` or calls a REST merge endpoint, "graphql" when it calls the
    GraphQL API (a merge only with a merge mutation), else None; read as written and with its quotes removed."""
    kind = None
    plain = _plain(command)
    for text in (command, plain, LIST_PUNCTUATION.sub(" ", plain)):
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
    dequoted = _dequoted(joined)
    views = (joined,) if dequoted == joined else (joined, dequoted)
    words = [match.group(1) for view in views for pattern in (FILE_ARG, AT_FILE, REDIRECT)
             for match in pattern.finditer(view)]
    words += [word for view in views for match in CAT.finditer(view) for word in re.findall(_WORD, match.group(1))
              if not word.startswith("-")]
    names = [_word(word) for word in dict.fromkeys(words)]
    names += [(match.group(2), glob.escape(match.group(2))) for match in AT_QUOTED.finditer(joined)]
    base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    texts = []
    for name, pattern in dict.fromkeys(names):
        if name == "-":  # standard input: a here-document is on the line, a redirect or a cat read above
            continue
        paths = [os.path.join(base, os.path.expanduser(name))]
        if any(char in pattern for char in "*?["):  # bash passes the word itself when nothing matches
            found = glob.iglob(os.path.join(glob.escape(base), os.path.expanduser(pattern)))
            paths = sorted(path for path in found if os.path.isfile(path))[:MAX_GLOB_FILES] or paths  # C order
        texts += [(f"the file {name}", text) for text in map(_read, paths) if text is not None]
    return texts


def _part(value: str) -> str:
    """A commit part's value: a JSON or GraphQL string decoded, a quoted field unquoted, a plain value as is."""
    if value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            return value[1:-1]
    return value[1:-1] if value.startswith("'") else value


def _commits(texts: list[tuple[str, str]], titles: list[str], messages: list[str]) -> list[tuple[str, str]]:
    """The commit a merge writes, its title, a blank line, then its message, for each title and message the call
    types: those given, and those its texts name by GitHub's field names."""
    titles, messages = list(titles), list(messages)
    for _, text in texts:
        for match in COMMIT_PART.finditer(text):
            (titles if match.group(1) in TITLE_FIELDS else messages).append(_part(match.group(2)))
    titles = list(dict.fromkeys(titles))[-MAX_PARTS:]
    messages = list(dict.fromkeys(messages))[-MAX_PARTS:]
    return [("the commit, title then message", f"{title}\n\n{message}") for title in titles for message in messages]


def _reason(references: list[str]) -> str:
    return (
        "Refused by .claude/hooks/closing_keyword_guard.py: this call merges or names a merge, and its text or "
        "a file it sends puts a closing keyword before an issue or pull request reference ("
        + "; ".join(references) + "). GitHub closes what it names when the commit reaches main, a pull request "
        "included. Reword each so no form of close, fix or resolve sits right before the reference (\"addressed "
        "in #N\", or the reference first: \"#N carries the fix\"), or leave the message out to merge with the "
        "default, which review-gate has read; text that only quotes a merge (a comment) can go in a --body-file "
        "instead. Close anything you mean to close by hand after the merge "
        "(lessons/ops-closing-keywords-close-what-they-name.md)."
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
        # As written, and as the shell joins it with gh's -b/-t split from an attached value.
        texts = [("this command", command), ("this command", ATTACHED.sub(r"\1 ", plain))]
        files = _body_files(command, event.get("cwd"))
        texts += files
        if kind == "graphql" and not any(MERGE_MUTATION.search(text) for _, text in texts):
            return None
        joined = command.replace("\\\n", "")
        subjects = [_word(match.group(1))[0] for match in SUBJECT.finditer(joined)]
        bodies = [_word(match.group(1))[0] for match in BODY.finditer(joined)] + [text for _, text in files]
        texts += _commits(texts, subjects, bodies)
    else:
        parts = tool.split("__")
        if not (len(parts) >= 3 and parts[0] == "mcp" and "github" in parts[1].lower()):
            return None
        texts = list(_strings(tool_input))
        # A merge tool, or a call handed a merge request as a whole string, may carry its commit text in any
        # string; text that only mentions a merge (a file's content, a comment, a search) is no merge.
        graphql_call = any(GRAPHQL_ENDPOINT.match(text) for _, text in texts) and any(
            MUTATION_CALL.search(text) for _, text in texts)
        if not ("merge" in "__".join(parts[2:]).lower() or graphql_call
                or any(GRAPHQL_MERGE.match(text) or REST_MERGE.match(text) for _, text in texts)):
            return None
        titles = [text for field, text in texts if field in TITLE_FIELDS]
        messages = [text for field, text in texts if field in ("commit_message", "commitBody")]
        commits = _commits(texts, titles, messages)
        texts += commits + [("the call's strings, in order", "\n\n".join(text for _, text in texts))]
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
