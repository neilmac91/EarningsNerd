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

The two names are never written whole in this source or its test, and no module global holds one:
``_names()`` builds them on the first scan, each ``_Name`` joining its fragments straight onto its
own attribute, so no argument or local of any frame holds a joined name either, and a ``_Name``'s
repr is text-free. So reading the hook shows no name and no form the hook flags, and an error while
the module loads or while the names are built prints none, even under pytest's ``-l`` (which prints
module globals and frame locals). One directory's last path component sits under a dated parent
(``<word>-<date>/<component>``); the other is a two-word name (``<word>-<word>``). Before matching,
every scanned string is normalised: case-fold (``str.casefold``), ``\\/`` and ``%2f`` (any case) ->
``/``, and a whole-date token that stands where the date would stand -- one short mask run, one
bracketed token, or one ellipsis (a lone Unicode ellipsis, or a run of three to ten ASCII dots; one
followed by another dot or ellipsis, and ``..``, a parent-directory step, keep the per-digit reading
below) -- is rewritten to the plain date. So every cut rule below applies to a token mask too, and
the end of a date an ellipsis elides is also a clean border: a cut may end there.

A string is flagged when it then holds a cut of either name. Around a junction (the word/date,
date/component or word/word boundary) the scan takes the longest stretch that matches the name,
where a date digit accepts any character but ``/``, ``-`` or whitespace (a masked digit). A cut is
any part of that stretch that holds the junction, is at least eight normalised characters long, and
has two clean ends; the whole name, plain or with its date per-digit masked, is the longest one.
Only the token rewrite is tracked back for the length, so a whole-date token counts as written (one
``*`` is one character, not the ten-character date it stands for), while an escaped slash counts as
the one ``/`` it stands for and a case fold as what it folds to. An end is clean when it is the
name's own end, the text's edge, a non-path character (path characters: letters, digits, ``.``
``_`` ``-`` ``/``; an ASCII or Unicode ellipsis is not one) or an ASCII ``...`` run, or -- for the
left end -- a ``/`` where the cut begins at one of the name's own path-segment starts, so the name
under a different parent (git ``--stat``'s ``.../<parent>/<component>``, ``./`` and ``../`` paths)
is caught while a mid-segment look-alike is not. That border may itself be a character the date's
tolerance took as a masked digit, so an ASCII ``...`` run or a Unicode ellipsis inside the date both
reads as masked digits (a dotted year) and ends a cut there (Claude Code's middle-truncation marker,
an elision), wherever in the date it lands. Next to every whole-date token the per-digit reading is
kept as well, walked once more in the text before the rewrite: at the word/date junction six or nine
characters before the token's dash (that dash is then a letter-masked year's or year and month's
own, which a letter left of it lets the token claim), at the token's own dash when the character
after the token reads as a masked digit (one more digit of the date), and, after an ellipsis token,
at each date/component junction within a date's length and before the next ellipsis token (its
last dot, or a punctuation mark after it, then the date's last digit). So the dated parent before a
sibling file (``<parent>/plan.md``) is flagged, by design (over-flagging that rare shape is the safe
side), when its date is elided whole by one ellipsis or a masked digit after its first is a clean
border (a non-path character such as an ellipsis or ``*``, or the start of a ``...`` run: a dotted
year, every digit dotted, an elided month or day); with no such border (a plain date, a mask token
such as ``*`` for the whole date, a two-dot month or day, a dotted last digit, a year elided by a
Unicode ellipsis or three dots) it stays silent. A listing that prints the dated parent directory's
name alone is flagged by design too: a cut of the longer name cannot be told from it. The scan is
linear in the text's length (fixed-substring search to candidate junctions and one bounded walk
around each, and a few fixed checks, a search of a few characters and a bounded walk per hit next to
each token; the regular expressions have no unbounded repetition and use only bounded slices).

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
cancels the command at the ~10 s timeout and discards its output. The densest input measured, a
one-character whole-date token between the dated word's last letter and a punctuation mark,
repeated, costs about 3 s of CPU per MB through the registered command, so a result that holds
about 3 MB or more of it reaches that timeout. It is also a detector only -- it
does not mask or replace the result (containment), does not see a subagent's hand-back message or a
workflow's completion notice (text that reaches the chief outside a tool result), and does not
pre-empt a command that would read either directory. Whether a workflow agent's tool calls fire
settings hooks is undocumented, and a running session may not pick up a changed .claude/settings.json
until it restarts. These are follow-ups, not built here.

Tests: backend/tests/unit/test_excluded_dir_output_guard.py.
"""
from __future__ import annotations

import bisect
import functools
import json
import os
import re
import sys
from collections.abc import Callable, Iterator

EVENTS = ("PostToolUse", "PostToolUseFailure")

# Fragments of the two names, joined only inside _names(); see the module docstring. Kept apart so
# this source holds no joined name and no form the hook flags.
_F1 = ("tasks/", "readi", "ness", "-", "2026", "-09-", "21", "/", "accep", "tance")
_F2 = ("tasks/", "rev", "iew", "-", "evi", "dence")


class _Name:
    """One excluded name and what the scan needs to match it: its canonical text, its date, the date's
    end and its digit and dash offsets (none for the two-word name), its junctions and its path-segment
    starts. It joins its fragments straight onto its own attributes, so no argument or local of any
    frame holds a joined name, and its repr is text-free, so a frame or container that holds it
    prints none."""

    __slots__ = ("canon", "dashes", "date", "date_end", "digits", "digits_up", "junctions", "seg_starts")

    def __init__(self, fragments: tuple[str, ...], date: tuple[int, int] | None) -> None:
        """`fragments` are the name's pieces, the fourth the dash after its first word; `date` is the
        (start, end) fragment indexes of its date, None for the two-word name."""
        self.canon = "".join(fragments)
        starts = [0]  # where each fragment starts in the name, from the fragments' lengths alone
        for fragment in fragments:
            starts.append(starts[-1] + len(fragment))
        dash = starts[3]
        # Each junction: the fixed substring to search for, the canonical offset it aligns to, and
        # the offset from a hit to the junction's start in the text.
        if date is None:
            date_start = 0
            self.date, self.date_end = "", -1  # no date, so no date end for an elision border either
            # word/word: the first word's last letter, the dash and the second word's first letter
            self.junctions = ((self.canon[dash - 1:dash + 2], dash - 1, 0),)
        else:
            date_start, date_end = starts[date[0]], starts[date[1]]
            self.date, self.date_end = self.canon[date_start:date_end], date_end
            self.junctions = (
                (self.canon[dash - 1:dash + 1], dash - 1, 0),            # word/date: the word's last letter and the dash
                (self.canon[date_end:date_end + 2], date_end - 1, -1),   # date/component: the slash and the letter after it
            )
        self.dashes = frozenset(date_start + k for k, ch in enumerate(self.date) if ch == "-")
        self.digits = frozenset(range(date_start, date_start + len(self.date))) - self.dashes
        self.digits_up = tuple(sorted(self.digits))
        self.seg_starts = frozenset({0} | {i + 1 for i, ch in enumerate(self.canon) if ch == "/"})

    def __repr__(self) -> str:
        return "<an excluded name>"

    def matches(self, ci: int, ch: str) -> bool:
        """Whether text character `ch` matches the name at offset `ci`: a date digit offset takes any
        character but '/', '-' or whitespace (a masked digit), a date dash offset a dash."""
        if ci in self.digits:
            return ch not in "/-" and not ch.isspace()
        if ci in self.dashes:
            return ch == "-"
        return ch == self.canon[ci]


@functools.cache
def _names() -> tuple[_Name, _Name]:
    """The dated name (<prefix><word>-<date>/<component>, its date fragments 4 to 6) and the two-word
    name (<prefix><word>-<word>), built from the fragments on first use, never at module scope; this
    frame binds no joined name (each _Name joins its own)."""
    return _Name(_F1, (4, 7)), _Name(_F2, None)


MARKER = "code-red-excluded-dir-guard"
MAX_META_BYTES = 4096  # a .git pointer file and a commondir file are tiny; never read more

# A whole-date mask: one short run of mask characters, or one bracketed token (<..>, [..], {..}).
_MASK_TOKEN = r"[#*?xn]{1,10}|<[^>\n]{0,14}>|\[[^\]\n]{0,14}\]|\{[^}\n]{0,14}\}"
# An ellipsis that stands for the whole date: a lone Unicode ellipsis, or a run of three to ten ASCII
# dots, not followed by another dot or ellipsis -- two ellipses, an ellipsis and dots, or eleven or
# more dots keep the per-digit reading -- and never two dots ('..' is a parent-directory step).
_ELLIPSIS_TOKEN = r"(?:\N{HORIZONTAL ELLIPSIS}|\.{3,10})(?![.\N{HORIZONTAL ELLIPSIS}])"
# A whole-date token standing where the date stands: a dash, then one complete token, then the
# component slash, the text end, an ASCII '...' run, or a non-path non-mask character, a Unicode
# ellipsis among them (never '-' or another mask char, which would be a per-digit mask the walk
# already handles). The char left of the dash is never a digit, a mask character or a dash, so a date
# masked digit by digit with those has no dash that starts a token; before an ellipsis token it is
# not a dot or an ellipsis either, so a dotted date's own dashes do not match, while a mask token
# after an elided word or the truncation marker still does. A letter-masked date's own dash (after
# its year or month, YYYY-MM-DD style) does start a token: `_per_digit_near` reads that date per digit
# again. Rewritten to the plain date so the walk's cut rules apply to a token mask as to a per-digit
# one; the rewrite is tracked, so the eight-character minimum counts the token as written. It holds
# no part of either name.
_DATE_TOKEN_RE = re.compile(r"(?<![-0-9#*?xn])-(?:" + _MASK_TOKEN + r"|(?<![.\N{HORIZONTAL ELLIPSIS}]-)"
                            + _ELLIPSIS_TOKEN + r")(?=/|$|\.\.\.|[^0-9a-z._/#*?-])")
_ESCAPED_SLASH_RE = re.compile(r"\\/|%2f")  # after case-folding, %2F is %2f

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


def _tracked_sub(text: str, regex: re.Pattern[str],
                 replacement: Callable[[re.Match[str]], str]) -> tuple[str, list]:
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


def _date_for_token(match: re.Match[str]) -> str:
    """What a whole-date token is rewritten to: the dash and the plain date."""
    return "-" + _names()[0].date


def _normalize(text: str) -> tuple[str, str, list, frozenset[int], list[tuple[int, int, bool]]]:
    """The text before the token rewrite and the text the walk reads, the rewrites that map the
    latter's positions back for the length rule, its elision borders, and each whole-date token's
    start (its dash) and end in the former, and whether it is an ellipsis: case-fold
    (``str.casefold``, so a sharp s reads as the two letters it folds to); undo the \\/ and %2f
    escapes of a slash; rewrite a whole-date token in date position to the plain date. Only the token
    step is tracked, so a cut's length counts normalised characters, a token as written. An elision
    border is the end of a date rewritten from an ellipsis token, where the ellipsis ended: a cut may
    end there, as it may at an ellipsis inside a date."""
    folded = text.casefold()
    if "\\/" in folded or "%2f" in folded:
        folded = _ESCAPED_SLASH_RE.sub("/", folded)
    text, maps, elisions, tokens = folded, [], frozenset(), []
    if "-" in folded:
        text, records = _tracked_sub(folded, _DATE_TOKEN_RE, _date_for_token)
        if records:
            maps.append(([r[0] for r in records], records))
            elisions = frozenset(new_start + new_len for new_start, new_len, old_start, _ in records
                                 if folded[old_start + 1] in ".\N{HORIZONTAL ELLIPSIS}")
            tokens = [(old_start, old_start + old_len, folded[old_start + 1] in ".\N{HORIZONTAL ELLIPSIS}")
                      for _, _, old_start, old_len in records]
    return folded, text, maps, elisions, tokens


def _map_back(position: int, maps: list) -> int:
    """The position before the tracked rewrites of a position in the normalized text, through each
    tracked step (the whole-date token step)."""
    for starts, records in reversed(maps):
        i = bisect.bisect_right(starts, position) - 1
        if i >= 0:
            new_start, new_len, old_start, old_len = records[i]
            if position < new_start + new_len:
                position = old_start + min(position - new_start, old_len)
            else:
                position = old_start + old_len + (position - new_start - new_len)
    return position


def _border_before(text: str, i: int) -> bool:
    """A clean border ends just before index `i`: the text's start, a non-path character, or an
    ASCII '...' run (the truncation marker error strings carry)."""
    return i == 0 or not _is_path_char(text[i - 1]) or (i >= 3 and text[i - 3:i] == "...")


def _border_after(text: str, j: int) -> bool:
    """A clean border starts at index `j`: the text's end, a non-path character, or an ASCII '...'
    run."""
    return j == len(text) or not _is_path_char(text[j]) or text[j:j + 3] == "..."


def _clean_start(text: str, name: _Name, lc: int, lt: int) -> bool:
    """A cut that begins at canonical offset `lc`, text index `lt`, has a clean left end: the name's
    own start, a clean border, or a '/' before one of the name's path-segment starts."""
    return lc == 0 or _border_before(text, lt) or (lc in name.seg_starts and text[lt - 1] == "/")


def _cut_at(text: str, maps: list, elisions: frozenset[int], name: _Name, c0: int, t0: int) -> bool:
    """Whether a qualifying cut of `name` holds the junction at canonical offset `c0` and text index
    `t0`. The walk takes the longest stretch around the junction that matches the name. The cut's
    right end is the stretch's own end when that is clean, else the date's end when it is an elision
    border (`_normalize`) after the junction, else the last masked digit after the junction that is
    itself a clean border; its left end is the first clean start: the stretch's own start, a segment
    start after a '/', or just after a masked digit before the junction that is a clean border.
    Inside the stretch only a masked digit or an elision border can be a border (every other offset
    holds a path character of the name), so only those offsets are tried. The cut must be at least
    eight characters long, counting normalised characters and a whole-date token as written."""
    n, m = len(text), len(name.canon)
    match = name.matches
    if not (match(c0, text[t0]) and match(c0 + 1, text[t0 + 1]) and match(c0 + 2, text[t0 + 2])):
        return False
    ci, ti = c0 - 1, t0 - 1
    while ci >= 0 and ti >= 0 and match(ci, text[ti]):
        ci -= 1
        ti -= 1
    left_c, left_t = ci + 1, ti + 1
    ci, ti = c0 + 3, t0 + 3
    while ci < m and ti < n and match(ci, text[ti]):
        ci += 1
        ti += 1
    right_c, right_t = ci, ti
    right = right_t
    if not (right_c == m or _border_after(text, right_t)):
        if right_c <= c0 + 3:
            return False  # the stretch took nothing after the junction, so nothing in it can end the cut
        right = -1
        if c0 + 3 <= name.date_end <= right_c and t0 + name.date_end - c0 in elisions:
            right = t0 + name.date_end - c0  # an elided date's end; a restored date has no masked digit
        else:
            for d in reversed(name.digits_up):  # a letter or digit is never a border: skip it cheaply
                if c0 + 3 <= d < right_c and not text[t0 + d - c0].isalnum() and _border_after(text, t0 + d - c0):
                    right = t0 + d - c0
                    break
        if right < 0:
            return False
    if maps:
        right = _map_back(right, maps)
    if right - (_map_back(left_t, maps) if maps else left_t) < 8:
        return False  # even the longest cut is short
    if _clean_start(text, name, left_c, left_t):
        return True
    starts = {s for s in name.seg_starts if left_c < s <= c0}
    starts.update(d + 1 for d in name.digits_up
                  if left_c <= d < c0 and not text[t0 + d - c0].isalnum())
    for lc in sorted(starts):
        lt = t0 + lc - c0
        if right - (_map_back(lt, maps) if maps else lt) < 8:
            return False  # a later start is shorter still
        if _clean_start(text, name, lc, lt):
            return True
    return False


def _walk(text: str, maps: list, elisions: frozenset[int], name: _Name) -> bool:
    """Whether `text` holds a qualifying cut of `name` (`_cut_at`) at any of its junctions. Each hit
    costs one bounded walk, so the scan stays linear in the text's length."""
    n = len(text)
    for find_sub, c0, delta in name.junctions:
        start = 0
        while True:
            hit = text.find(find_sub, start)
            if hit < 0:
                break
            start = hit + 1
            t0 = hit + delta
            if 0 <= t0 and t0 + 3 <= n and _cut_at(text, maps, elisions, name, c0, t0):
                return True
    return False


def flagged(text: str) -> bool:
    """Whether a scanned string carries a form of either name. A whole-date token is also read per
    digit at the junctions next to it (`_per_digit_near`)."""
    if not isinstance(text, str) or not text:
        return False
    folded, norm, maps, elisions, tokens = _normalize(text)
    if any(_walk(norm, maps, elisions, name) for name in _names()):
        return True
    return _per_digit_near(folded, tokens)


def _per_digit_near(folded: str, tokens: list[tuple[int, int, bool]]) -> bool:
    """Whether a cut of the dated name, read per digit in the text before the token rewrite, holds a
    junction next to a whole-date token (each a start, its dash; an end; and whether it is an
    ellipsis). For every token, the word/date junction six or nine characters before its dash, where
    that dash is a letter-masked year's or year and month's own (the rewrite read it as the word's),
    and the word/date junction at its own dash when the character after it reads as a masked digit;
    after an ellipsis token, each date/component junction within a date's length of it and before the
    next ellipsis token, its last dot or a punctuation mark after it then read as the date's last
    digit. Only a run of four or more dots holds a clean border (a '...' run) before its last dot, so
    after a shorter token that search starts one character later. Each token costs a few fixed
    checks, a search of a few characters and a bounded walk per hit."""
    dated = _names()[0]
    (word_sub, word_c0, _), (comp_sub, comp_c0, _) = dated.junctions
    n = len(folded)
    next_starts = iter([start for start, _, ellipsis in tokens if ellipsis][1:] + [n])
    for start, end, ellipsis in tokens:
        for hit in (start - 6, start - 9):  # the word's last letter before a four-char year, or year and month
            if hit >= 0 and folded.startswith(word_sub, hit) and _cut_at(folded, [], frozenset(), dated, word_c0, hit):
                return True
        if (0 < start and end < n and folded[end] not in "/-" and not folded[end].isspace()
                and folded.startswith(word_sub, start - 1) and _cut_at(folded, [], frozenset(), dated, word_c0, start - 1)):
            return True
        if ellipsis:
            limit = min(end + len(dated.date) + 1, next(next_starts) + 1)
            hit = folded.find(comp_sub, end if end - start > 4 else end + 1, limit)
            while hit >= 0:
                if _cut_at(folded, [], frozenset(), dated, comp_c0, hit - 1):
                    return True
                hit = folded.find(comp_sub, hit + 1, limit)
    return False


def _iter_strings(roots: list) -> Iterator[str]:
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


def _targets(data: dict, event: str | None) -> list:
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


def _opted_in(cwd: object) -> bool:
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


def _emit(message: str, event: str | None) -> int:
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
