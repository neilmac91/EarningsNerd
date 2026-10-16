"""PreToolUse hook: refuse an agent's merge whose typed commit title or message puts a closing keyword
before an issue or pull request reference.

The second gate for lessons/ops-closing-keywords-close-what-they-name.md. GitHub closes what a closing
keyword names (close, fix or resolve in any form, then #N, OWNER/REPO#N and the like) when a commit that
carries it reaches the default branch, a pull request included. review-gate (backend/scripts/review_gate.py)
fails a pull request whose title, body or commit messages carry one, which covers GitHub's default squash
message: the title, or the one commit's subject, then every commit message. It cannot see a message typed
at the merge itself. This hook reads that message where an agent types it, with the gate's own
`closing_references` (loaded from backend/scripts/review_gate.py, so the two share one pattern):
- a call to a GitHub MCP server (a name containing "github" in any case) that carries a merge's commit
  text: `commit_title`, `commit_message`, `commit_headline` or `commit_body` (merge_pull_request,
  enable_pr_auto_merge);
- a Bash command line that runs `gh pr merge` (gh as a word or a path, -R/--repo before the noun or the
  verb, the words quoted or not), or that calls GitHub's merge endpoints (`/merge` or `/merges` with
  `gh api` or api.github.com): the whole line, as written and with its quotes removed, here-document text
  included, and the files it sends as the message (gh pr merge's `--body-file` and `-F`, gh api's
  `--input` and `-F key=@file`, curl's `-d @file`).
A merge with no typed message passes: its message is the default the gate has read. Reading the whole line
refuses more than the merge's own message (another command on the line that names a closing reference);
the remedy, rewording, is cheap.

A refusal is a JSON deny on stdout, which Claude Code hands to Claude as the reason; anything else exits 0
with no output. A crash exits 1, which Claude Code reports as a hook error and lets the call through. The
registered command (`python3 -I -S`: standard library only) maps Python's own exit 2 (a script it cannot
open) to 1, so a broken install never blocks every Bash command and every GitHub call.

Not checked: text a command builds as it runs (a variable, a command substitution's output, a message file
written by an earlier command in the same line), a body file named relative to a directory the command
changes into first, a merge run by another shell (`bash -c '...'`) or a script, a GitHub MCP server
registered under a name without "github", a session that loads no repository hooks, and a person's own
merge.
Tests: backend/tests/unit/test_closing_keyword_guard.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# The commit text a merge call types, by the names GitHub's REST and GraphQL APIs give it.
COMMIT_FIELDS = ("commit_title", "commit_message", "commit_headline", "commit_body")
_REPO = r"(?:\s+(?:-R\s*\S+|--repo(?:=|\s+)\S+))*"  # gh takes -R/--repo before the noun and before the verb
GH_MERGE = re.compile(rf"(?:^|[\s/;&|(`$])gh{_REPO}\s+pr{_REPO}\s+merge\b")
MERGE_ENDPOINT = re.compile(r"/merges?\b")
GH_API = re.compile(r"(?:^|[\s/;&|(`$])gh\s+api\b")
# An option whose value is, or names with `@`, a file the merge sends: gh pr merge's --body-file and -F, gh
# api's -F key=@file and --input, curl's -d/--data/--data-binary @file. A regular expression, not shlex: it
# reads a 1 MiB line in milliseconds.
FILE_ARG = re.compile(
    r"""(?:^|[\s;&|(])(?:--body-file(?:=|\s+)|-F[ \t]*|--input(?:=|\s+)|-d[ \t]*|--data(?:-binary)?(?:=|\s+))"""
    r"""('[^'\n]*'|"[^"\n]*"|[^\s;&|()<>'"]+)""")
UNQUOTE = str.maketrans("", "", "'\"\\")
MAX_FILE_BYTES = 1 << 20
GATE = Path(__file__).resolve().parents[2] / "backend" / "scripts" / "review_gate.py"


def _closing_references():
    """review-gate's own `closing_references`, so the hook and the gate never disagree on what closes."""
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("_review_gate", GATE)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.closing_references


def _commit_texts(value: object, field: str | None = None):
    """Every commit title or message string in a tool call's arguments, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _commit_texts(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from _commit_texts(item, field)
    elif isinstance(value, str) and field in COMMIT_FIELDS:
        yield field, value


def _merges(command: str) -> bool:
    """Whether the line runs `gh pr merge` or calls a merge endpoint, its quotes removed or not."""
    for text in (command, command.replace("\\\n", "").translate(UNQUOTE)):
        if GH_MERGE.search(text):
            return True
        if MERGE_ENDPOINT.search(text) and (GH_API.search(text) or "api.github.com" in text.lower()):
            return True
    return False


def _body_files(command: str, cwd: object) -> list[tuple[str, str]]:
    """The text of each regular file, up to 1 MiB, that the line sends as the merge's message: the value of
    --body-file, -F or --input, or the file an `@` names in a field (`commit_message=@msg.md`, `-d @body.json`)."""
    names = []
    for match in FILE_ARG.finditer(command):
        value = match.group(1).strip("'\"")
        at = value.find("@")
        names.append(value[at + 1:] if at >= 0 and (at == 0 or value[at - 1] == "=") else value)
    base = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    texts = []
    for name in dict.fromkeys(names):
        if name == "-":  # standard input: a here-document's text is in the line, which is read whole
            continue
        try:
            path = (base / Path(name).expanduser()).resolve()
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
    if tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return None
        plain = command.replace("\\\n", "").translate(UNQUOTE)  # no quotes, backslashes or continuations
        if "merge" not in plain or not _merges(command):
            return None
        texts = [("this command", command), ("this command", plain)]
        texts += _body_files(command, event.get("cwd"))
    else:
        parts = tool.split("__")
        if not (len(parts) >= 3 and parts[0] == "mcp" and "github" in parts[1].lower()):
            return None
        texts = list(_commit_texts(tool_input))
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
