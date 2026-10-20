"""PreToolUse hook: refuse a session's call to GitHub's deployment-review API, so only the founder
approves an Ops apply.

`.github/workflows/ops.yml` holds every -apply operation (relabel-fy-apply, repair-ticker-apply,
reset-filing-summary-apply) in its approve-apply job, which runs in the `ops-apply` environment whose
required reviewer is the founder. Sessions act on GitHub through the founder's account, so GitHub would
take a session's approval for the founder's own. This hook stops a session giving one.

.claude/settings.json runs it before every Bash command. A command line is refused when one of its
commands, read as the shell reads it (codex_mention_guard.py's reader: compound lines, command
substitutions, backquotes), calls the GitHub API (`gh api`, or curl, wget or httpie on a line that
names api.github.com), and the line, here-documents, substitutions and variables included, names the
deployment-review or environment API: a run's `pending_deployments` (approve or reject a wait on an
environment), a `deployment_protection_rule` review, an `/environments` path (which could drop the
environment's reviewer), or GraphQL's `approveDeployments`, `rejectDeployments`,
`createEnvironment`, `updateEnvironment` or `deleteEnvironment`. Reading those paths is refused too;
the run's own status shows it is waiting. A line that makes no API call passes whatever it names (a
commit message, a here-document written to a file, `gh pr comment --body-file`). On a line that makes
one, a name anywhere refuses the line, in a comment's text or in a here-document that writes the file
the call sends, so the refusal says how to send such text instead: write the file in an earlier Bash
call or with the Write tool, then send it in a Bash call of its own.

A GraphQL call (gh's `graphql` or `/graphql` path, a URL naming api.github.com/graphql, or any API call
on a line whose text names graphql) sends a query, free text in which the line could build a mutation's
name, so the hook lets one through only when it has read all of that text. It refuses one when a file
the call sends names one of those mutations (a file's other text passes, so a GraphQL reply whose body
names `pending_deployments` goes through), and fails closed when:
- the shell builds text on the line as it runs (a variable, a command substitution or backquotes,
  arithmetic, `$'...'` or `$"..."`) anywhere but in single quotes, a comment or a here-document whose
  word is quoted: `A=approve; B=Deployments; ... $A$B`, `-f query="$(cat q.graphql)"`, `--input $S/q.json`;
- the call reads standard input piped from anything but a plain cat: a body a program writes;
- a file the call sends (gh's --input or an @file value such as -F query=@q.graphql, curl's @file or
  -T, wget's --post-file or --body-file, a `<` redirect into a call that reads standard input, the files
  a plain cat pipes in) is missing before the line runs, larger than 1 MiB, not a regular file or under
  /proc, /sys or /dev: a file the line writes first, a process substitution, a path relative to a
  directory the line changes into.

A refusal is a JSON deny on stdout; anything else exits 0 with no output. A crash exits 1, which
Claude Code reports as a hook error and lets the call through, as for codex_mention_guard.py.

The hook holds the rule at the calls a session writes; no check of a command's text stops a session set
on getting past it. Not checked: a REST path the shell assembles from parts (`.../pending_$X`), since
routine reads build their paths from variables (`actions/runs/$id/jobs`); a call a program makes as it
runs (a script, `python3 -c`, a command another shell runs with `bash -c` or `eval`); a GitHub client
named through a variable (`$GH api`); a GraphQL file that a command earlier on the line rewrites (the
hook reads it as it stands before the line runs); a GitHub MCP tool (none reviews a deployment); a
session that loads no repository hooks; Codex and Astra sessions; and the founder's own approval, which
is the point.
Tests: backend/tests/unit/test_ops_approval_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I leaves the hooks directory off sys.path
import codex_mention_guard as shell  # noqa: E402  its shell reader, shared rather than copied

MUTATIONS = r"(?:approve|reject)Deployments|(?:create|update|delete)Environment"  # GraphQL's
REVIEW_NAMES = re.compile(
    r"pending_deployments|deployment_protection_rule|/environments(?![A-Za-z0-9_-])|" + MUTATIONS, re.I)
SENT_MUTATIONS = re.compile(MUTATIONS, re.I)  # what a file a GraphQL call sends is searched for
GRAPHQL = re.compile(r"\bgraphql\b", re.I)
CLIENTS = {"curl", "wget", *shell.HTTPIE}
# What the shell replaces as the line runs: a variable or special parameter, ${...}, $(...) and $((...)),
# $[...], $'...' and $"...", and backquotes.
EXPANSION = re.compile(r"\$[\w{(\[@*#?!$'\"-]|`")
# Options whose value is a file the call sends: gh's --input, curl's -T and --upload-file, wget's
# --post-file and --body-file. An @file value (gh's -F key=@file, curl's -d @file) is one too.
FILE_OPTIONS = ("--input", "-T", "--upload-file", "--post-file", "--body-file")
REASON = (
    "Refused by .claude/hooks/ops_approval_guard.py: this command calls GitHub's deployment-review or "
    "environment API, which approves or rejects a run waiting on an environment or changes who must approve. "
    "Only the founder approves an Ops apply (the ops-apply environment in .github/workflows/ops.yml), on the "
    "run's page: ask them to. If this line only names the API in text, write that text to a file in an "
    "earlier Bash call or with the Write tool, then send it in a Bash call of its own (`gh api … -F "
    "body=@file.md`, `gh pr comment --body-file`), or send it through a GitHub MCP tool."
)
UNREAD = (
    "Refused by .claude/hooks/ops_approval_guard.py: this line makes a GitHub GraphQL call whose query the "
    "hook cannot read before the line runs (text the shell builds as it runs, such as a variable, a command "
    "substitution or backquotes; a body piped from a program; or a file that is not there yet or cannot be "
    "read), so it cannot rule out a mutation that approves or rejects an Ops apply or changes its environment. "
    "Write the query, and every value the line passes, as the call is to send them: in single quotes, in a "
    "here-document whose word is quoted that feeds the call itself (`-F query=@- <<'EOF'`; a "
    "`\"$(cat <<'EOF' …)\"` substitution is text the shell builds), or in a file written in an earlier Bash "
    "call or with the Write tool and named by its path (`-F query=@q.graphql`, `--input q.json`). Only the "
    "founder approves an Ops apply (the ops-apply environment in .github/workflows/ops.yml), on the run's page."
)


def _is_graphql(words: list[str]) -> bool:
    """gh sends both `graphql` and `/graphql` to the GraphQL endpoint; a URL can name it too."""
    return any(word in ("graphql", "/graphql") or f"{shell.GITHUB_API}/graphql" in word.lower() for word in words)


def _calls_the_api(words: list[str], names_api: bool) -> bool:
    """`gh ... api` wherever it stands (`sudo gh api`), or an HTTP client on a line that names api.github.com,
    in its own words or in a variable it reads."""
    names = [word.rsplit("/", 1)[-1] for word in words]
    if "gh" in names and "api" in names[names.index("gh") + 1:]:
        return True
    return names_api and any(name in CLIENTS for name in names)


def _expands(command: str) -> bool:
    """Whether the shell replaces any of this line's text as it runs, anywhere but in single quotes, a
    comment or a here-document whose word is quoted."""
    i, double, waiting = 0, False, []
    while i < len(command):
        char = command[i]
        if char == "\\":  # an escaped character expands nothing
            i += 2
        elif EXPANSION.match(command, i):
            return True
        elif char == '"':
            double, i = not double, i + 1
        elif double:
            i += 1
        elif char == "'":
            end = command.find("'", i + 1)
            i = len(command) if end < 0 else end + 1
        elif char == "#" and (i == 0 or command[i - 1] in shell.WORD_START):
            end = command.find("\n", i)
            i = len(command) if end < 0 else end
        elif command.startswith("<<<", i):
            i += 3
        elif command.startswith("<<", i) and (word := shell.HEREDOC_WORD.match(command, i + 2)):
            waiting.append(word)
            i = word.end()
        elif char == "\n" and waiting:
            i = _past_here_documents(command, i + 1, waiting)
            if i < 0:
                return True
            waiting = []
        else:
            i += 1
    return False


def _past_here_documents(command: str, i: int, words: list[re.Match[str]]) -> int:
    """Where the line goes on past the text of these here-documents, each read from where the last ended up
    to the line that is its word (after its leading tabs, for <<-) or one that starts with its word, blanks
    and a `)`; -1 when the text of one whose word is unquoted expands (its quotes are plain characters)."""
    for word in words:
        end = next(part for part in word.groups()[1:] if part is not None)
        quoted = word.group(4) is None or command[word.start(4) - 1] == "\\"
        while i < len(command):
            newline = command.find("\n", i)
            newline = len(command) if newline < 0 else newline
            line = command[i:newline]
            text = line.lstrip("\t") if word.group(1) else line
            if text == end:
                i = newline + 1
                break
            if text.startswith(end) and shell.PAREN_END.match(text, len(end)):
                i += len(line) - len(text) + len(end)  # its `)` and the rest of its line are commands
                break
            if not quoted and EXPANSION.search(re.sub(r"\\.", "", line)):
                return -1
            i = newline + 1
    return i


def _sent(words: list[str]) -> tuple[list[str], bool]:
    """The files this call sends, and whether it reads standard input: a `-`, /dev/stdin or /dev/fd/0 named
    as one of them, or httpie, which reads it unasked; then a `<` redirect's file is sent too."""
    files, redirects = [], []
    for index, word in enumerate(words):
        if word in FILE_OPTIONS and index + 1 < len(words):
            files.append(words[index + 1])
        files += [word[len(option) + 1:] for option in FILE_OPTIONS if word.startswith(option + "=")]
        if at_file := shell.AT_FILE.match(word):
            files.append(at_file.group(1))
        if word == "<" and index + 1 < len(words):
            redirects.append(words[index + 1])
    stdin = any(name in shell.STDIN for name in files) or any(
        word.rsplit("/", 1)[-1] in shell.HTTPIE for word in words)
    return [name for name in files if name not in shell.STDIN] + (redirects if stdin else []), stdin


def refusal(event: object) -> str | None:
    """Why this tool call must not run, or None to let it through."""
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return None
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return None
    plain = command.replace("\\\n", "").translate(shell.UNQUOTE)  # no quotes, backslashes or continuations
    names_api = shell.GITHUB_API in plain.lower()
    if "gh" not in plain and not names_api:
        return None  # no GitHub API client on the line
    commands = shell._commands(shell._command_tokens(shell._script(command)))
    calls = [(index, operator, words) for index, (operator, words) in enumerate(commands)
             if _calls_the_api(words, names_api)]
    if not calls:
        return None
    # The whole line: a path or a query can arrive through a variable, a pipe or a here-document.
    if REVIEW_NAMES.search(plain):
        return REASON
    graphql = [call for call in calls if _is_graphql(call[2])] or (calls if GRAPHQL.search(plain) else [])
    if graphql and _expands(command):
        return UNREAD
    for index, operator, words in graphql:
        files, stdin = _sent(words)
        if stdin and operator in ("|", "|&"):
            source = commands[index - 1][1]
            if source[:1] != ["cat"]:
                return UNREAD  # a body a program writes
            files += [word for word in source[1:] if not word.startswith("-")]
        texts = [shell._read_sent(name, event.get("cwd")) for name in files]
        if None in texts:
            return UNREAD
        if any(SENT_MUTATIONS.search(text) for text in texts):
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
