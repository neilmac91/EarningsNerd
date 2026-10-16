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
  whole string: a GraphQL document (its operation keyword a whole word) or a JSON request (an object with a
  "query" key) calling a merge mutation (mergePullRequest(, enablePullRequestAutoMerge(, mergeBranch(), the
  GraphQL endpoint beside such a call, or a REST merge target (a method, then a URL, a path or a route,
  templated or with a query string, ending at a pull request's `/merge` or a repository's `/merges`). It
  reads every string the call is handed, at any depth, whatever the server names the field. A call whose
  text only mentions a merge (a file's content, a comment, a search) passes;
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
  (`$(<file)` too), and each file a plain `cat`, by name or path, quoted or escaped (`\cat`), reads, piped
  or inside `$(...)`, `<(...)` or backticks; an option quoted or escaped as a whole word ('-F',
  "--body-file=my notes.md") counts as written plain. A name is read as the shell passes it: its quoted,
  escaped and plain pieces joined, `~` expanded, and an unquoted glob expanded to its first 16 files in the
  C locale's order (to the word itself when nothing matches).
A merge's commit is its title, a blank line, then its message, so a keyword that ends the title closes a
reference that starts the message: each title and message a call types are also read joined that way (a
title's last and a message's first 1,024 characters), the last 16 of each (gh keeps a flag's last value). On
a shell line they are gh pr merge's --subject/-t and --body/-b among the line's words as the shell passes
them (a quoted value may run over lines), and among the words of a word that is itself a merge's line
(`bash -c 'gh pr merge ...'`), a value that is one file's plain `cat` or `<` (`-t "$(cat title.md)"`) read
as that file's text, and each file the line reads, each here-document and each here-string as a message; and
GitHub's field names, commit_title with commit_message, and commitHeadline with commitBody or mergeBranch's
commitMessage, as a name=value word (`-f 'commit_title=lint fix'`, `--field=...`, gh's nested
`input[commitBody]=...`, httpie's field=value; `=@file` read), a quoted value the name takes in a text, read
whole and decoded as its language reads it (a JSON or GraphQL string, its quotes escaped or not, or a
GraphQL block string; a script's dictionary or keyword argument), a JSON text, or the one a here-document
starts with, decoded, or a GraphQL variable such a word or a JSON body gives (`commitBody: $b` with
`-f b=...`). On MCP they are the same fields and variables among the call's strings, and every string of the
call in order. A decoded value is also read on its own, so a keyword after an escaped line break (`\n`)
counts.
A merge with no typed message passes: its message is the default the gate has read. Reading the whole line,
and every file it names, refuses more than a merge's own message: another command's text on the same line,
and a line that only names a merge (a comment that quotes `gh pr merge` with a closing reference). The
remedy is cheap: reword, or send such text from a file (`--body-file`), which a line that names no merge
never has read.

A refusal is a JSON deny on stdout, which Claude Code hands to Claude as the reason; anything else exits 0
with no output. A crash exits 1, which Claude Code reports as a hook error and lets the call through, as it
does a hook that outlasts its 10 s timeout; the adversarial 1 MB lines the tests keep read in about a second
or two. The registered command (`python3 -I -S`: standard library only) maps Python's own exit 2 (a script
it cannot open) to 1, so a broken install never blocks every Bash command and every GitHub call.

Not checked: text the shell or a command builds as the line runs (a variable, an ANSI-C `$'...'` escape, a
brace expansion, the output of any command but a plain `cat`, a line handed to another shell that way; a
literal `bash -c '...'` is on the line and read); a file over 1 MiB, a glob's files past its first 16, or a
file named relative to a directory the line changes into first; more than three -R/--repo options in a row
before `pr` or `merge`; a title or message past the last 16 of each a call types, a here-document past a
line's first 16, or a title's keyword and its message's reference more than 1,024 characters from where the
two meet; a typed title or message whose other half is GitHub's default (a merge commit's default title
names its branch); a merge a script or a gh alias runs, or whose URL sits in a file a command reads as its
configuration (curl's -K, wget's -i); an MCP request tool that spreads a merge's target over fields of its
own (owner, repository, number, action); a GitHub MCP server registered under a name without "github"; a
session that loads no repository hooks; and a person's own merge.
Tests: backend/tests/unit/test_closing_keyword_guard.py.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from itertools import islice
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
# fragment first, its keyword a whole word) or a JSON request (an object with a "query" key) that calls a merge
# mutation; the GraphQL endpoint, whose call then sits in another string; or a REST merge target (a method, then
# a URL, a path or a route, templated or with a query string, ending at a pull request's /merge or a
# repository's /merges).
MUTATION_CALL = re.compile(r"\b(?:mergePullRequest|enablePullRequestAutoMerge|mergeBranch)\s*\(", re.IGNORECASE)
GRAPHQL_MERGE = re.compile(
    r"\A\s*(?:#[^\n]*\n\s*)*(?:(?:query|mutation|subscription|fragment)\b|\{(?=[\s\S]*?\"query\"\s*:))[\s\S]*?"
    + MUTATION_CALL.pattern, re.IGNORECASE)
_TARGET = r"\A\s*(?:[A-Za-z]+\s+)?(?:(?:https?://)?api\.github\.com)?/?"
GRAPHQL_ENDPOINT = re.compile(_TARGET + r"graphql/?(?:\?\S*)?\s*\Z", re.IGNORECASE)
REST_MERGE = re.compile(
    _TARGET + r"(?:repos/[^/\s]+/[^/\s]+/(?:pulls/[^/\s]+/merge|merges)|pulls/[^/\s]+/merge)/?(?:\?\S*)?\s*\Z",
    re.IGNORECASE)
# gh pr merge's -b (body) or -t (subject) with its value attached, after any run of other short flags.
ATTACHED = re.compile(r"(?<!\S)(-[A-Za-z]*?[bt])(?=\S)")
# A shell word: a run of single-quoted, double-quoted, escaped and plain pieces, a quoted piece running over
# lines as the shell lets it; and each piece of one, a double-quoted piece resolving the escapes the shell does
# (each reader joins the line's continuations first).
_WORD = r"""(?:'[^']*'|"(?:[^"\\]|\\[\s\S])*"|\\[\s\S]|[^\s;&|()<>'"`\\])+"""
_VALUE = "(" + _WORD + ")"  # a file name; a lone `-` is standard input
_PIECE = re.compile(r"""'([^']*)'|"((?:[^"\\]|\\[\s\S])*)"|\\([\s\S])|([^'"\\]+|['"])""")
_DOUBLE_ESCAPE = re.compile(r"""\\([\\"$`])""")
# A word with a quoted or escaped piece, from the word's start (so a long plain word is scanned once).
_QUOTED_WORD = re.compile(
    r"""(?<![^\s;&|()<>`])(?:[^\s;&|()<>'"`\\]*(?:'[^']*'|"(?:[^"\\]|\\[\s\S])*"|\\[\s\S]))+[^\s;&|()<>'"`\\]*""")
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
# The title and message a call types, joined as GitHub writes its commit (the title, a blank line, the message):
# gh pr merge's --subject/-t and --body/-b among the line's words, with its body files and here-documents as
# messages; and GitHub's own field names, REST's commit_title and commit_message and GraphQL's commitHeadline and
# commitBody, as a word's name=value, a JSON field, a quoted value a field name or key takes in a text (JSON,
# GraphQL, a script's dictionary or keyword argument; read whole, so never from the quote-stripped line), or a
# GraphQL variable a word or a field gives. At most 16 of each, the last ones (gh keeps a flag's last value).
SUBJECT_FLAG = re.compile(r"--subject(?:=([\s\S]*))?|-[A-Za-z]*?t=?([\s\S]*)")
BODY_FLAG = re.compile(r"--body(?:=([\s\S]*))?|-[A-Za-z]*?b=?([\s\S]*)")
# gh api's -f/-F/--field/--raw-field name=value, the option attached or not (-fname=value), and httpie's field=value;
# a nested key (input[commitBody]=value, which gh sends as a field of the input variable) is named by its last key.
NAMED_WORD = re.compile(r"(?:--(?:raw-)?field=|-[A-Za-z]*?[fF]=?)?(?:\w+\]?\[)*(\w+)\]?(?:\[\])?=([\s\S]*)")
TITLE_FIELDS = ("commit_title", "commitHeadline")
MESSAGE_FIELDS = ("commit_message", "commitBody", "commitMessage")  # REST's, then GraphQL's merge and mergeBranch's
_FIELD = "(" + "|".join(TITLE_FIELDS + MESSAGE_FIELDS) + ")"
# A field's quoted value: a GraphQL block string, a JSON or GraphQL string, or a script's single-quoted string.
COMMIT_PART = re.compile(r"\b" + _FIELD + r"\b[\"']?\s*[:=]\s*"
                         r"(\"\"\"(?:[^\"\\]|\\[\s\S]|\"(?!\"\"))*\"\"\"|\"(?:[^\"\\]|\\[\s\S])*\"|'[^']*')")
COMMIT_VARIABLE = re.compile(r"\b" + _FIELD + r"\s*:\s*\$(\w+)")
MAX_PARTS = 16
# A here-document's opener (not a here-string's `<<<`); its text starts on the next line.
HEREDOC = re.compile(r"""(?<!<)<<(?!<)-?[ \t]*(?:'[^'\n]+'|"[^"\n]+"|\\?[A-Za-z_][\w.-]*)""")
MAX_HEREDOCS = 16
HERESTRING = re.compile(r"<<<[ \t]*" + _VALUE)  # a here-string's word, the text it sends on standard input
# A value the shell fills from one file: a plain cat's or a `<` redirect's in a command substitution.
SUBSTITUTED = re.compile(r"""(?:\$\(|`)\s*(?:<|(?:\\|\S*/)?(?:cat|'cat'|"cat")\s)\s*"""
                         r"""((?:'[^']*'|"[^"]*"|\\[\s\S]|[^\s()`'"\\])+)\s*(?:\)|`)""")
# The join reads a title's end and a message's start: more than any keyword, the marks after it and a reference
# (a pull request URL is about 240 characters) need, and a bound on each joined text however large its parts.
JOIN_CHARS = 1024
UNQUOTE = str.maketrans("", "", "'\"\\")
SPACE = re.compile(r"\s")
LIST_PUNCTUATION = re.compile(r"[\[\],]")  # a program's argument list: ["gh", "pr", "merge"]
MAX_FILE_BYTES = 1 << 20
MAX_GLOB_FILES = 16
GATE = Path(__file__).resolve().parents[2] / "backend" / "scripts" / "review_gate.py"
DECODER = json.JSONDecoder()


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


def _piece(match: re.Match, literal=str) -> str:
    """A piece of a shell word as the shell passes it, a quoted or escaped one through `literal`."""
    single, double, escaped, plain = match.groups()
    if plain is not None:
        return plain
    if single is not None:
        return literal(single)
    if double is not None:  # \\ \" \$ \` stand for their character
        return literal(_DOUBLE_ESCAPE.sub(r"\1", double) if "\\" in double else double)
    return literal(escaped)


def _quoted(word: str) -> bool:
    return "'" in word or '"' in word or "\\" in word


def _name(word: str) -> str:
    """A shell word as the shell passes it: its quoted, escaped and plain pieces joined."""
    return _PIECE.sub(_piece, word) if _quoted(word) else word


def _word(word: str) -> tuple[str, str]:
    """A shell word as the shell passes it, and as a glob in which only its unquoted, unescaped part is special."""
    if not _quoted(word):
        return word, word
    return _name(word), _PIECE.sub(lambda match: _piece(match, glob.escape), word)


def _dequoted(line: str) -> str:
    """The line with each quoted or escaped word written as the shell passes it ('-F' msg.md becomes -F msg.md),
    so an option quoted or escaped as a whole word is read like a plain one. A word that holds whitespace stays
    as written unless it is an option, whose whitespace is escaped ("--body-file=my notes.md")."""
    def plain(match: re.Match) -> str:
        name = _name(match.group(0))
        if not SPACE.search(name):
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
    if "merge" not in plain and "graphql" not in plain.lower():  # most lines name neither
        return None
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
    """A quoted value as the language that quotes it reads it: a JSON or GraphQL string, or a script's single-quoted
    one, with its escapes decoded (`\\n` a line break); unquoted only, for an escape JSON does not know."""
    if value.startswith('"""'):  # a GraphQL block string: raw but for its escaped triple quote
        return value[3:-3].replace('\\"""', '"""')
    body = value[1:-1]
    try:
        return json.loads(value if value[0] == '"' else '"' + body.replace('"', '\\"') + '"')
    except ValueError:
        return body


def _json_strings(text: str, prefix: bool = False) -> list[tuple[str, str]]:
    """The (name, string) pairs inside a text that is JSON (a request body sent as one string), decoded; with
    `prefix`, inside the JSON value the text starts with (a here-document's, which runs on past its end)."""
    stripped = text.strip()
    if stripped[:1] not in ("{", "["):
        return []
    if not prefix and stripped[-1:] != ("}" if stripped[0] == "{" else "]"):
        return []
    try:
        return list(_strings(DECODER.raw_decode(stripped)[0] if prefix else json.loads(stripped)))
    except (ValueError, RecursionError):
        return []


def _json_strings_of(texts: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The (name, string) pairs inside each text that is JSON."""
    return [pair for _, text in texts for pair in _json_strings(text)]


def _heredocs(text: str) -> list[str]:
    """The text of each here-document on the line (the first 16), from the line after its opener. A message is
    read joined only at its start, so where the document ends does not matter."""
    starts = (text.find("\n", match.end()) for match in islice(HEREDOC.finditer(text), MAX_HEREDOCS))
    return list(dict.fromkeys(text[start + 1:] for start in starts if start >= 0))  # openers on one line share it


def _flag_values(words: list[str], flag: re.Pattern) -> list[str]:
    """The values a gh flag is given among the line's words: `--subject x`, `--subject=x`, `-t x`, `-tx`, and
    the last flag of a run of short ones (`-st x`)."""
    values = []
    for index, word in enumerate(words):
        match = flag.fullmatch(word) if word[:1] == "-" else None
        if match is None:
            continue
        attached = match.group(1) if match.group(1) is not None else match.group(2)
        if attached:
            values.append(attached)
        elif index + 1 < len(words):
            values.append(words[index + 1])
    return values


def _last(values: list[str]) -> list[str]:
    """The last 16 distinct values, in order: gh keeps a flag's last value."""
    return list(dict.fromkeys(reversed(values)))[:MAX_PARTS][::-1]


def _commits(texts: list[tuple[str, str]], titles: list[str], messages: list[str], named: dict[str, list[str]],
             resolve=lambda value: value) -> list[tuple[str, str]]:
    """The commit a merge writes, its title's end, a blank line, then its message's start, for each title and
    message the call types: those given; GitHub's field names in `named` (a word's name=value, a field) and in its
    texts as a quoted value; and the `named` values a GraphQL variable takes. `resolve` reads a value filled from a
    file (`@file`, `$(cat file)`). Each quoted value is also read on its own, decoded as the server reads it."""
    titles, messages = list(titles), list(messages)
    fields = {field: titles for field in TITLE_FIELDS} | {field: messages for field in MESSAGE_FIELDS}
    names = [(field, field) for field in fields]  # each field named outright, then each variable a field takes
    parts = []
    for _, text in texts:
        for match in COMMIT_PART.finditer(text):
            parts.append(_part(match.group(2)))
            fields[match.group(1)].append(parts[-1])
        names += COMMIT_VARIABLE.findall(text)
    for field, name in dict.fromkeys(names):
        fields[field].extend(_last(named.get(name, [])))
    titles, messages = [resolve(title) for title in _last(titles)], [resolve(message) for message in _last(messages)]
    return [("a field's value, decoded", part) for part in dict.fromkeys(parts)] + [
        ("the commit, title then message", f"{title[-JOIN_CHARS:]}\n\n{message[:JOIN_CHARS]}")
        for title in titles for message in messages]


def _filled(value: str, cwd: object) -> str:
    """A value as gh or the shell fills it from a file: the file an `@` names (gh api's -F name=@file), or the one a
    plain cat or a `<` redirect reads in a command substitution (`$(cat title.md)`), its final line breaks dropped
    as the shell drops them; else the value itself."""
    substituted = SUBSTITUTED.fullmatch(value)
    if substituted is None and (not value.startswith("@") or value == "@-"):
        return value
    base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    name = _name(substituted.group(1)) if substituted else value[1:]
    text = _read(os.path.join(base, os.path.expanduser(name)))
    return value if text is None else text.rstrip("\n") if substituted else text


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
        kind = _merge_kind(command)
        if kind is None:
            return None
        plain = _plain(command)
        # As written, and as the shell joins it with gh's -b/-t split from an attached value.
        texts = [("this command", command), ("this command", ATTACHED.sub(r"\1 ", plain))]
        cwd = event.get("cwd")
        files = _body_files(command, cwd)
        joined = command.replace("\\\n", "")
        # The line's words as the shell passes them, and the words of each word that is itself a merge's line, one
        # level down (bash -c 'gh pr merge ...').
        lines = [[_name(word) for word in re.findall(_WORD, joined)]]
        lines += [[_name(word) for word in re.findall(_WORD, line)] for line in lines[0]
                  if SPACE.search(line) and _merge_kind(line)]
        words = [word for line in lines for word in line]
        heredocs = _heredocs(joined)
        decoded = [pair for text in [*words, *(text for _, text in files)] if "{" in text or "[" in text
                   for pair in _json_strings(text)] + [pair for text in heredocs for pair in _json_strings(text, True)]
        texts += files + [("a JSON body", text) for _, text in decoded]
        if kind == "graphql" and not any(MERGE_MUTATION.search(text) for _, text in texts):
            return None
        named: dict[str, list[str]] = {}
        pairs = (match.groups() for match in (NAMED_WORD.fullmatch(word) for word in words if "=" in word) if match)
        for name, value in [*pairs, *decoded]:
            named.setdefault(name, []).append(value)
        titles = [value for line in lines for value in _flag_values(line, SUBJECT_FLAG)]
        messages = ([value for line in lines for value in _flag_values(line, BODY_FLAG)] + [text for _, text in files]
                    + heredocs + [_name(match.group(1)) for match in HERESTRING.finditer(joined)])
        sources = [("this command", command), ("the line's words", "\n".join(words)), *texts[2:]]
        texts += _commits(sources, titles, messages, named, lambda value: _filled(value, cwd))
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
        strings = "\n\n".join(text for _, text in texts)
        texts += _json_strings_of(texts)
        named: dict[str, list[str]] = {}
        for field, text in texts:
            named.setdefault(field, []).append(text)
        texts += _commits(texts, [], [], named) + [("the call's strings, in order", strings)]
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
