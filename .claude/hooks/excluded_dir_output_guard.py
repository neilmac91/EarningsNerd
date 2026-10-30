"""PostToolUse / PostToolUseFailure hook: flag a tool result that names either of the two
directories a CODE RED program keeps out of its agents' contexts (CODE RED closure 220).

A CODE RED context (a long-running chief and its agents) must never carry the contents of those
two directories, and treats printing either name -- plain, masked, cut or truncated -- as a lapse
to disclose. This hook is the machine gate behind that rule (CLAUDE.md rule 12, AGENTS.md section
4): it inspects a tool result after the tool runs and states, factually, when the result carries
any such form. It is a DETECTOR, not a filter: it never changes the result and never echoes the
text it matched.

The exclusion is a CODE RED rule only, so the hook is OPT-IN and silent for everyone else. It does
anything only when a marker file named ``code-red-excluded-dir-guard`` exists in the git common
directory of EITHER the repository that contains the event's ``cwd`` OR the one that contains
``$CLAUDE_PROJECT_DIR`` (either suffices). A CODE RED session whose ``cwd`` has moved outside any
repository, or into another clone, is therefore still guarded through the project directory, the
clone whose settings registered the hook. Turn it on with
``touch "$(git rev-parse --git-common-dir)/code-red-excluded-dir-guard"``: the common directory is
the main checkout's ``.git`` for every linked worktree (a worktree's own gitdir,
``.git/worktrees/<name>``, is the wrong place and leaves the guard off). The marker is never
committed, and other clones and other writers' sessions are untouched. The common directory is
resolved by reading files only, no subprocess: a linked worktree's ``.git`` is a file
``gitdir: <path>`` (absolute, or relative to the worktree), and ``<path>/commondir`` names the
common directory relative to it. No marker anywhere -> exit 0 with no output, whatever the input.

The two names are never written whole in this source or its test: each is built at run time from
the fragments below, so reading the hook shows no name and no form the hook flags. One directory's
last path component sits under a dated parent (``<word>-<date>/<component>``); the other is a
two-word name (``<word>-<word>``). Before matching, every scanned string is normalised: case-fold,
``\\/`` and ``%2f`` (any case) -> ``/``, and a whole-date token (one short mask run, or one bracketed
token) that stands where the date would stand is rewritten to the plain date, so every cut rule
below applies to token masks too. Each rewrite is tracked, so positions map back to the original
text. A string is flagged when it then contains either name whole; the dated name with its date
per-digit masked (the structure kept); or a cut of either name that spans a junction (the
word/date, date/component or word/word boundary), is at least eight characters long in the ORIGINAL
text (a rewritten token counts as its own characters, an escape as written), and whose two ends are
each clean. An end is clean when it is the name's own end, the text's edge, a non-path-character
border (path characters: letters, digits, ``.`` ``_`` ``-`` ``/``; an ASCII or Unicode ellipsis is
not one, so a truncation marker counts as a border -- next to the date's tolerant digits too, where
a dot of an ASCII ``...`` run is never taken for a masked digit), or -- for the left end -- a ``/``
where the cut begins at one of the name's own path-segment starts, so the name under a different
parent (git ``--stat``'s ``.../<parent>/<component>``, ``./`` and ``../`` paths) is caught while a
mid-segment look-alike is not. A listing that prints the dated parent directory's name alone is
flagged by design: a cut of the longer name cannot be told from it. The scan is linear in the
text's length (fixed-substring search to candidate junctions, a bounded walk around each; the
regular expressions have no unbounded repetition and use only bounded slices).

What is scanned: for PostToolUse, every string inside ``tool_response`` -- recursively through
objects (keys and values) and arrays, a top-level string too; for PostToolUseFailure, ``error`` and
any ``tool_response``; for an unknown event, both. Never ``tool_input``: the CODE RED git commands
carry the two names as exclusion pathspecs, so scanning inputs would flag every such command.

Output channel. The registration passes the event as an argument, one entry per event
(``--event PostToolUse`` / ``--event PostToolUseFailure``, the form secret_scan_guard.py uses with
``--session-start``), so the hook knows its event even when the input cannot be read. It takes a
valid argv event first, else the parsed input's ``hook_event_name``. The registered command
(``python3 -I -S ... || exit 1``, the form the other hooks use) maps Python's own exit 2 to shell
exit 1, so an exit-2-to-stderr warning would not reach Claude. Instead the hook writes, on exit 0,
a JSON object with ``systemMessage`` (shown to the user) and, with a known event,
``hookSpecificOutput.additionalContext`` (a system reminder for Claude, saved in the transcript,
documented for both events) carrying that event's name. Only when the event is unknown (invoked
without ``--event`` and with no readable ``hook_event_name``) does it emit ``systemMessage`` alone:
Claude Code validates ``hookSpecificOutput.hookEventName`` against the firing event and rejects a
mismatch ("Hook returned incorrect event name"), so a guessed name would be dropped, while
``systemMessage`` is a universal field accepted on either event. Doc (code.claude.com/docs/en/hooks):
the exit-code table -- "PostToolUse ... Shows stderr to Claude; the tool already ran" and
"PostToolUseFailure ... Shows stderr to Claude; the tool already failed" -- and the JSON output
fields, where ``additionalContext`` is listed for PostToolUse and PostToolUseFailure and
``systemMessage`` is universal. It never emits exit 2, a traceback, or the matched text. The hook
fails safe: opted in, any input the parser rejects (invalid JSON, or one so deeply nested or large
that json raises RecursionError or MemoryError) yields a different fixed message saying the result
could not be checked, on the same channels (so Claude sees it with a registered event); not opted
in, it stays silent.

Limits. Fail-open modes (it stays silent): not opted in; a session that loads no repository hooks
(a multi-repo cloud session, an untrusted folder, ``disableAllHooks``); and a run where Claude Code
cancels the command at the ~10 s timeout and discards its output. It is also a detector only -- it
does not mask or replace the result (containment), does not see a subagent's hand-back message or a
workflow's completion notice (text that reaches the chief outside a tool result), and does not
pre-empt a command that would read either directory. Whether a workflow agent's tool calls fire
settings hooks is undocumented, and a running session may not pick up a changed .claude/settings.json
until it restarts. These are follow-ups, not built here.

Tests: backend/tests/unit/test_excluded_dir_output_guard.py.
"""
from __future__ import annotations

import bisect
import json
import os
import re
import sys

EVENTS = ("PostToolUse", "PostToolUseFailure")

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


def _segment_starts(canon: str) -> frozenset:
    """Offsets where a path segment of `canon` starts: offset 0 and each offset just after a '/'."""
    return frozenset({0} | {i + 1 for i, ch in enumerate(canon) if ch == "/"})


_N1_SEG_STARTS = _segment_starts(_C1)
_N2_SEG_STARTS = _segment_starts(_C2)

MARKER = "code-red-excluded-dir-guard"
MAX_META_BYTES = 4096  # a .git pointer file and a commondir file are tiny; never read more

# A whole-date mask: one short run of mask characters, or one bracketed token (<..>, [..], {..}).
_TOKEN = r"[#*?xn]{1,10}|<[^>\n]{0,14}>|\[[^\]\n]{0,14}\]|\{[^}\n]{0,14}\}"
# A whole-date token standing where the date stands: the word/date dash (its char on the left is the
# word's last letter, never a date-content char, so a per-digit mask's own dashes do not match),
# then one complete token, then the component slash, the text end, an ASCII '...' run, or a non-path
# non-mask character (never '-' or another mask char, which would be a per-digit mask the walk
# already handles). Rewritten to the plain date so the walk's cut rules apply to a token mask as to
# a per-digit one; the rewrite is tracked, so the eight-character minimum is measured on the
# original text. Built from fragments, so this source holds no joined form.
_DATE_TOKEN_RE = re.compile(r"(?<![-0-9#*?xn])-(?:" + _TOKEN + r")(?=/|$|\.\.\.|[^0-9a-z._/#*?-])")
_ESCAPED_SLASH_RE = re.compile(r"\\/|%2f")  # after case-folding, %2F is %2f
_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")

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


def _tracked_sub(text: str, regex, replacement) -> tuple[str, list]:
    """Replace each match of `regex` in `text` with `replacement(match)`. Returns the new text and the
    rewrites as (new_start, new_len, old_start, old_len) in order, so a position maps back."""
    pieces, records, last, shift = [], [], 0, 0
    for match in regex.finditer(text):
        new = replacement(match)
        start, end = match.span()
        pieces.append(text[last:start])
        pieces.append(new)
        records.append((start + shift, len(new), start, end - start))
        shift += len(new) - (end - start)
        last = end
    if not records:
        return text, records
    pieces.append(text[last:])
    return "".join(pieces), records


def _fold(text: str) -> tuple[str, list]:
    """Case-fold `text`. Returns it and, when folding changed its length (a few non-ASCII
    characters fold to several), the per-character rewrites."""
    if text.isascii():
        return text.lower(), []
    folded = text.casefold()
    if len(folded) == len(text):  # every character folded to exactly one
        return folded, []
    records, shift = [], 0
    for match in _NON_ASCII_RE.finditer(text):
        new_len = len(match.group().casefold())
        if new_len != 1:
            start = match.start()
            records.append((start + shift, new_len, start, 1))
            shift += new_len - 1
    return folded, records


def _normalize(text: str) -> tuple[str, list]:
    """The text the walk reads, and the rewrites (each step's, in order) that map its positions back
    to the original: case-fold; undo the \\/ and %2f escapes of a slash; rewrite a whole-date token in
    date position to the plain date."""
    maps = []
    text, records = _fold(text)
    if records:
        maps.append(([r[0] for r in records], records))
    if "\\/" in text or "%2f" in text:
        text, records = _tracked_sub(text, _ESCAPED_SLASH_RE, lambda match: "/")
        if records:
            maps.append(([r[0] for r in records], records))
    if "-" in text:
        text, records = _tracked_sub(text, _DATE_TOKEN_RE, lambda match: "-" + _DATE)
        if records:
            maps.append(([r[0] for r in records], records))
    return text, maps


def _map_back(position: int, maps: list) -> int:
    """The original-text position of a position in the normalized text, through each rewrite step."""
    for starts, records in reversed(maps):
        i = bisect.bisect_right(starts, position) - 1
        if i >= 0:
            new_start, new_len, old_start, old_len = records[i]
            if position < new_start + new_len:
                position = old_start + min(position - new_start, old_len)
            else:
                position = old_start + old_len + (position - new_start - new_len)
    return position


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


def _in_ellipsis(text: str, i: int) -> bool:
    """The '.' at index `i` belongs to an ASCII run of three or more dots (a truncation marker)."""
    return (text[i:i + 3] == "..." or (i >= 1 and text[i - 1:i + 2] == "...")
            or (i >= 2 and text[i - 2:i + 1] == "..."))


def _border_before(text: str, i: int) -> bool:
    """A clean border ends just before index `i`: the text's start, a non-path character, or an
    ASCII '...' run (the truncation marker error strings carry)."""
    return i == 0 or not _is_path_char(text[i - 1]) or (i >= 3 and text[i - 3:i] == "...")


def _border_after(text: str, j: int) -> bool:
    return j == len(text) or not _is_path_char(text[j]) or text[j:j + 3] == "..."


def _walk(text: str, maps: list, canon: str, cm, junctions, seg_starts, tolerant) -> bool:
    """Whether `text` holds a cut of `canon` (`cm` its per-offset match, `tolerant` the offsets that
    accept any masked character) spanning one of `junctions`, at least eight characters long in the
    original text, with both ends clean. A tolerant offset never takes a dot of an ASCII '...' run,
    so the run stays a border. The right end is clean at the name's own end, the text edge, a
    non-path border, or an ASCII ellipsis. The left end is clean there too, or at a '/' where the cut
    begins at one of the name's path-segment starts. Plain and per-digit-masked whole names are the
    longest such cuts, so this covers them too."""
    n, m = len(text), len(canon)

    def matches(ci: int, ti: int) -> bool:
        ch = text[ti]
        return cm(ci, ch) and not (ch == "." and ci in tolerant and _in_ellipsis(text, ti))

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
            if not (matches(c0, t0) and matches(c0 + 1, t0 + 1) and matches(c0 + 2, t0 + 2)):
                continue
            ci, ti = c0 - 1, t0 - 1
            while ci >= 0 and ti >= 0 and matches(ci, ti):
                ci -= 1
                ti -= 1
            left_c, left_t = ci + 1, ti + 1
            ci, ti = c0 + 3, t0 + 3
            while ci < m and ti < n and matches(ci, ti):
                ci += 1
                ti += 1
            right_c, right_t = ci, ti
            if not (right_c == m or _border_after(text, right_t)):
                continue
            right_orig = _map_back(right_t, maps) if maps else right_t
            # Try the greedy left end and each segment start between it and the junction: a cut that
            # begins at a segment start preceded by '/' is the name under another parent.
            candidates = [(left_t, left_c)]
            candidates += [(left_t + (s - left_c), s) for s in seg_starts if left_c < s <= c0]
            for lt, lc in candidates:
                if right_orig - (_map_back(lt, maps) if maps else lt) < 8:
                    continue
                if lc == 0 or _border_before(text, lt) or (lc in seg_starts and lt > 0 and text[lt - 1] == "/"):
                    return True
    return False


def flagged(text: str) -> bool:
    """Whether a scanned string carries a form of either name."""
    if not isinstance(text, str) or not text:
        return False
    norm, maps = _normalize(text)
    if _walk(norm, maps, _C1, _cm1, _N1_JUNCTIONS, _N1_SEG_STARTS, _N1_DIGIT_POS):
        return True
    return _walk(norm, maps, _C2, _cm2, _N2_JUNCTIONS, _N2_SEG_STARTS, frozenset())


def _iter_strings(roots):
    """Every string in `roots`, recursively through dict keys and values and through lists/tuples.
    Iterative, so a deeply nested response cannot overflow the stack during extraction."""
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


def _targets(data: dict, event) -> list:
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
    """Whether the opt-in marker sits in the common directory of the cwd's repository OR of
    $CLAUDE_PROJECT_DIR's repository (either suffices), both resolved by reading files only."""
    for base in (cwd, os.environ.get("CLAUDE_PROJECT_DIR")):
        if not (isinstance(base, str) and base):
            continue
        try:
            common = _common_dir(base)
        except OSError:
            common = None
        if common and os.path.isfile(os.path.join(common, MARKER)):
            return True
    return False


def _argv_event(argv: list) -> str | None:
    """The event the registration names (``--event <name>`` or ``--event=<name>``), when valid."""
    for i, arg in enumerate(argv):
        value = argv[i + 1] if arg == "--event" and i + 1 < len(argv) else None
        if arg.startswith("--event="):
            value = arg[len("--event="):]
        if value in EVENTS:
            return value
    return None


def _emit(message: str, event) -> int:
    """Write the fixed message on exit 0. systemMessage reaches the user on either event; when the
    firing event is known, additionalContext (with its name) reaches Claude. An unknown event gets
    systemMessage alone, so Claude Code does not reject a guessed hookEventName."""
    payload = {"systemMessage": message}
    if event in EVENTS:
        payload["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": message}
    try:
        sys.stdout.write(json.dumps(payload))
    except OSError:
        pass
    return 0


def main() -> int:
    event = _argv_event(sys.argv[1:])  # the registration's event, known even when stdin is not
    try:
        raw = sys.stdin.read()
    except Exception:  # any read failure -> treat as unreadable
        raw = ""
    data = None
    try:
        parsed = json.loads(raw) if raw.strip() else None
        data = parsed if isinstance(parsed, dict) else None
    except Exception:  # invalid JSON, or input so deep/large json raises RecursionError/MemoryError
        data = None
    cwd = data.get("cwd") if data is not None else None
    if not _opted_in(cwd):  # not opted in: silent, whatever the input
        return 0
    if event is None and data is not None and data.get("hook_event_name") in EVENTS:
        event = data.get("hook_event_name")
    try:
        if data is None:  # opted in but the input was not a readable JSON object
            return _emit(UNCHECKED, event)
        for text in _iter_strings(_targets(data, event)):
            if flagged(text):
                return _emit(FLAGGED, event)
        return 0
    except Exception:  # never let a traceback reach any output
        return _emit(UNCHECKED, event)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # last resort: a guardrail must not crash into Claude's output
        sys.exit(0)
