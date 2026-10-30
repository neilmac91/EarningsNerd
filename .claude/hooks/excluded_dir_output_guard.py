"""PostToolUse / PostToolUseFailure hook: flag a tool result that names either of the two
directories a CODE RED program keeps out of its agents' contexts (CODE RED closure 220).

A CODE RED context (a long-running chief and its agents) must never carry the contents of those
two directories, and treats printing either name -- plain, masked, cut or truncated -- as a lapse
to disclose. This hook is the machine gate behind that rule (CLAUDE.md rule 12, AGENTS.md section
4): it inspects a tool result after the tool runs and states, factually, when the result carries
any such form, so no leak goes unnoticed. It is a DETECTOR, not a filter: it never changes the
result and never echoes the text it matched.

The exclusion is a CODE RED rule only, so the hook is OPT-IN and silent for everyone else. It does
anything only when a marker file named ``code-red-excluded-dir-guard`` exists in the git common
directory of the repository that contains the event's ``cwd`` (``$CLAUDE_PROJECT_DIR`` when ``cwd``
is absent). The marker lives inside ``.git`` -- never committed, per clone, shared by every linked
worktree (they share one common directory) -- so other clones and other writers' sessions are
untouched. The common directory is resolved by reading files only, no subprocess: a linked
worktree's ``.git`` is a file ``gitdir: <path>``, and ``<path>/commondir`` names the common
directory relative to it. No marker -> exit 0 with no output, whatever the input.

The two names are never written whole in this source or its test: each is built at run time from
the fragments below, so reading the hook shows no name and no form the hook flags. One directory's
last path component sits under a dated parent (``<word>-<date>/<component>``); the other is a
two-word name (``<word>-<word>``). Before matching, every scanned string is normalised: case-fold,
``\\/`` -> ``/``, ``%2f`` (any case) -> ``/``. A string is flagged when it then contains either
name whole; the dated name with its date masked (each digit replaced, the structure kept, or the
whole date replaced by one short mask run or one bracketed token); or a cut of either name at least
eight characters long that spans a junction (the word/date, date/component or word/word boundary)
and whose two ends are each the name's own end, a non-path-character border, or the text's edge
(path characters: letters, digits, ``.`` ``_`` ``-`` ``/``). A listing that prints the dated
parent directory's name alone is flagged by design: a cut of the longer name cannot be told from
it. The scan is linear in the text's length (fixed-substring search to candidate junctions, a
bounded walk around each; the one regular expression has no unbounded repetition).

What is scanned: for PostToolUse, every string inside ``tool_response`` -- recursively through
objects (keys and values) and arrays, a top-level string too; for PostToolUseFailure, ``error`` and
any ``tool_response``. Never ``tool_input``: the CODE RED git commands carry the two names as
exclusion pathspecs, so scanning inputs would flag every such command.

Output channel. The registered command (``python3 -I -S ... || exit 1``, the form the other hooks
use) maps Python's own exit 2 to shell exit 1, so an exit-2-to-stderr warning would not reach
Claude. Instead, on a flag the hook writes -- on exit 0 -- a JSON object with
``hookSpecificOutput.additionalContext`` (a system reminder, saved in the transcript, documented
for both PostToolUse and PostToolUseFailure) and ``systemMessage`` (shown to the user). It never
emits exit 2, a traceback, or the matched text. Doc (code.claude.com/docs/en/hooks): the exit-code
table -- "PostToolUse ... Shows stderr to Claude; the tool already ran" and "PostToolUseFailure ...
Shows stderr to Claude; the tool already failed" -- and the JSON output fields, where
``additionalContext`` is listed for PostToolUse and PostToolUseFailure and ``systemMessage`` is a
universal field shown to the user. The hook fails safe: opted in, a stdin that is not readable JSON
(or any unexpected error while checking) yields a different fixed message saying the result could
not be checked; not opted in, it stays silent.

Limits (follow-ups, not built here): it does not mask or replace the result (containment), does not
see a subagent's hand-back message or a workflow's completion notice (text that reaches the chief
outside a tool result), and does not pre-empt a command that would read either directory. Whether a
workflow agent's tool calls fire settings hooks is undocumented, and a running session may not pick
up a changed .claude/settings.json until it restarts.

Tests: backend/tests/unit/test_excluded_dir_output_guard.py.
"""
from __future__ import annotations

import json
import os
import re
import sys

# Fragments of the two names, joined only at run time; see the module docstring. Kept apart so this
# source holds no joined name and no form the hook flags.
_F1 = ("tasks/", "readi", "ness", "-", "2026", "-09-", "21", "/", "accep", "tance")
_F2 = ("tasks/", "rev", "iew", "-", "evi", "dence")

# --- The dated name (N1): <prefix><word>-<date>/<component> ---------------------------------------
_PREFIX1 = _F1[0]
_WORD1 = _F1[1] + _F1[2]
_DATE = _F1[4] + _F1[5] + _F1[6]
_COMPONENT1 = _F1[8] + _F1[9]
_C1 = _PREFIX1 + _WORD1 + "-" + _DATE + "/" + _COMPONENT1
_DASH1 = len(_PREFIX1) + len(_WORD1)          # index of the word/date dash
_DATE_START = _DASH1 + 1
_DATE_END = _DATE_START + len(_DATE)          # index of the date/component slash
# Within the date: which offsets are its internal dashes, which are its digits.
_N1_DASH_POS = frozenset(_DATE_START + k for k, ch in enumerate(_DATE) if ch == "-")
_N1_DIGIT_POS = frozenset(_DATE_START + k for k in range(len(_DATE))) - _N1_DASH_POS
# Junctions of N1: the word/date boundary (its fixed part is the word's last letter and the dash)
# and the date/component boundary (its fixed part is the slash and the component's first letter).
_J1_START = _DASH1 - 1
_J2_START = _DATE_END - 1

# --- The two-word name (N2): <prefix><word>-<word> ------------------------------------------------
_PREFIX2 = _F2[0]
_WORD2A = _F2[1] + _F2[2]
_WORD2B = _F2[4] + _F2[5]
_C2 = _PREFIX2 + _WORD2A + "-" + _WORD2B
_J3_START = len(_PREFIX2) + len(_WORD2A) - 1  # the word/word boundary

MARKER = "code-red-excluded-dir-guard"
MAX_META_BYTES = 4096  # a .git pointer file and a commondir file are tiny; never read more

# A whole-date mask that replaces the entire date with one token: a short run of mask characters, or
# one bracketed token. (A per-digit mask keeps the date's structure and is matched by the walk.)
_TOKEN = r"(?:[#*?xn]{1,10}|<[^>\n]{0,14}>|\[[^\]\n]{0,14}\]|\{[^}\n]{0,14}\})"
# N1 with the date as one token, as a factual full name: with its own prefix (valid anywhere, as the
# name's own start) or, without the prefix, only at a non-path-character border. The component ends
# the name, so what follows it does not matter. Built from fragments; no joined literal here.
_TOKEN_RE = re.compile(
    "(?:" + re.escape(_PREFIX1) + re.escape(_WORD1) + "-" + _TOKEN + "/" + re.escape(_COMPONENT1) + ")"
    + "|(?:(?<![a-z0-9._/-])" + re.escape(_WORD1) + "-" + _TOKEN + "/" + re.escape(_COMPONENT1) + ")"
)

FLAGGED = (
    "Excluded-directory guard: this tool result contains a form of a directory name that CODE RED "
    "contexts keep out of their context (plain, masked, cut or truncated). The result is unchanged. "
    "A CODE RED context records this as a lapse with the tool call's time and does not repeat the text."
)
UNCHECKED = (
    "Excluded-directory guard: the guard could not check this tool result, because its input could "
    "not be read as JSON. The result is unchanged. A CODE RED context treats an unchecked result as "
    "a possible lapse and records it with the tool call's time."
)


def _is_path_char(ch: str) -> bool:
    """A character that can be part of a path, so a cut bordered by it is not a clean name end."""
    return ch.isalnum() or ch in "._-/"


def _normalize(text: str) -> str:
    """Case-fold, then undo the two escapings of a path slash the chief's masking can leave."""
    text = text.casefold()
    if "\\/" in text:
        text = text.replace("\\/", "/")
    if "%2f" in text:  # already case-folded, so %2F is covered
        text = text.replace("%2f", "/")
    return text


def _cm1(ci: int, ch: str) -> bool:
    """Whether text character `ch` matches canonical N1 at offset `ci`, with the date tolerant: any
    character but a slash, a dash or whitespace at a digit offset; a dash at a date-dash offset."""
    if ci in _N1_DIGIT_POS:
        return ch not in "/-" and not ch.isspace()
    if ci in _N1_DASH_POS:
        return ch == "-"
    return ch == _C1[ci]


def _cm2(ci: int, ch: str) -> bool:
    return ch == _C2[ci]


# Each junction: the fixed substring to search for, the canonical offset it aligns to, and the
# offset from a hit to the junction's start in the text.
_N1_JUNCTIONS = (
    (_C1[_J1_START:_J1_START + 2], _J1_START, 0),      # the word/date boundary; its tolerant 3rd char is checked
    (_C1[_DATE_END:_DATE_END + 2], _J2_START, -1),     # the date/component boundary; tolerant 1st char
)
_N2_JUNCTIONS = ((_C2[_J3_START:_J3_START + 3], _J3_START, 0),)


def _walk(text: str, canon: str, cm, junctions) -> bool:
    """Whether `text` holds a cut of `canon` (`cm` its per-offset match) spanning one of `junctions`,
    at least eight characters long, each end the name's own end, a non-path border, or the text edge.
    Plain and per-digit-masked whole names are the longest such cuts, so this covers them too."""
    n, m = len(text), len(canon)
    for find_sub, c0, delta in junctions:
        start = 0
        while True:
            hit = text.find(find_sub, start)
            if hit < 0:
                break
            start = hit + 1
            t0 = hit + delta
            if t0 < 0 or t0 + 3 > n:
                continue
            if not (cm(c0, text[t0]) and cm(c0 + 1, text[t0 + 1]) and cm(c0 + 2, text[t0 + 2])):
                continue
            ci, ti = c0 - 1, t0 - 1
            while ci >= 0 and ti >= 0 and cm(ci, text[ti]):
                ci -= 1
                ti -= 1
            left_c, left_t = ci + 1, ti + 1
            ci, ti = c0 + 3, t0 + 3
            while ci < m and ti < n and cm(ci, text[ti]):
                ci += 1
                ti += 1
            right_c, right_t = ci, ti
            if right_t - left_t < 8:
                continue
            left_ok = left_c == 0 or left_t == 0 or not _is_path_char(text[left_t - 1])
            right_ok = right_c == m or right_t == n or not _is_path_char(text[right_t])
            if left_ok and right_ok:
                return True
    return False


def flagged(text: str) -> bool:
    """Whether a scanned string carries a form of either name."""
    if not isinstance(text, str) or not text:
        return False
    norm = _normalize(text)
    if _TOKEN_RE.search(norm) is not None:
        return True
    if _walk(norm, _C1, _cm1, _N1_JUNCTIONS):
        return True
    if _walk(norm, _C2, _cm2, _N2_JUNCTIONS):
        return True
    return False


def _iter_strings(roots):
    """Every string in `roots`, recursively through dict keys and values and through lists/tuples.
    Iterative, so a deeply nested response cannot overflow the stack."""
    stack = list(roots)
    while stack:
        cur = stack.pop()
        if isinstance(cur, str):
            yield cur
        elif isinstance(cur, dict):
            for key, value in cur.items():
                if isinstance(key, str):
                    yield key
                stack.append(value)
        elif isinstance(cur, (list, tuple)):
            stack.extend(cur)


def _targets(data: dict, event: str) -> list:
    """What to scan for this event: tool_response for PostToolUse; error and tool_response for
    PostToolUseFailure. Never tool_input. An unknown event scans both, never tool_input."""
    if event == "PostToolUse":
        return [data.get("tool_response")]
    if event == "PostToolUseFailure":
        return [data.get("error"), data.get("tool_response")]
    return [data.get("tool_response"), data.get("error")]


def _read_small(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read(MAX_META_BYTES)


def _common_dir(start: str) -> str | None:
    """The git common directory of the repository that contains `start`, by reading files only."""
    directory = os.path.abspath(start)
    for _ in range(100):  # a repository is never a hundred levels deep; also guards link loops
        dot_git = os.path.join(directory, ".git")
        if os.path.isdir(dot_git):
            return dot_git
        if os.path.isfile(dot_git):
            git_dir = None
            for line in _read_small(dot_git).splitlines():
                stripped = line.strip()
                if stripped.startswith("gitdir:"):
                    git_dir = stripped[len("gitdir:"):].strip()
                    break
            if not git_dir:
                return None
            if not os.path.isabs(git_dir):
                git_dir = os.path.abspath(os.path.join(directory, git_dir))
            common_file = os.path.join(git_dir, "commondir")
            if os.path.isfile(common_file):
                common = _read_small(common_file).strip()
                if not common:
                    return git_dir
                return common if os.path.isabs(common) else os.path.abspath(os.path.join(git_dir, common))
            return git_dir
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent
    return None


def _opted_in(cwd) -> bool:
    """Whether the opt-in marker exists in the common directory for `cwd` (or $CLAUDE_PROJECT_DIR)."""
    base = cwd if isinstance(cwd, str) and cwd else os.environ.get("CLAUDE_PROJECT_DIR")
    if not base:
        return False
    try:
        common = _common_dir(base)
    except OSError:
        return False
    return bool(common) and os.path.isfile(os.path.join(common, MARKER))


def _emit(event: str, message: str) -> int:
    payload = {
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": message},
        "systemMessage": message,
    }
    try:
        sys.stdout.write(json.dumps(payload))
    except OSError:
        pass
    return 0


def main() -> int:
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        raw = ""
    data = None
    try:
        parsed = json.loads(raw) if raw.strip() else None
        data = parsed if isinstance(parsed, dict) else None
    except ValueError:
        data = None
    cwd = data.get("cwd") if data is not None else None
    if not _opted_in(cwd):  # not opted in: silent, whatever the input
        return 0
    event = data.get("hook_event_name") if data is not None else None
    if not isinstance(event, str) or not event:
        event = "PostToolUse"
    try:
        if data is None:  # opted in but the input was not a readable JSON object (empty, invalid, list, scalar)
            return _emit(event, UNCHECKED)
        for text in _iter_strings(_targets(data, event)):
            if flagged(text):
                return _emit(event, FLAGGED)
        return 0
    except Exception:  # never let a traceback reach any output
        return _emit(event, UNCHECKED)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # last resort: a guardrail must not crash into Claude's output
        sys.exit(0)
