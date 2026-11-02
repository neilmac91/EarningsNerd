"""Gate for `.claude/hooks/excluded_dir_output_guard.py`, the PostToolUse / PostToolUseFailure hook
that flags a tool result naming either of the two directories a CODE RED program keeps out of its
agents' contexts (CODE RED closure 220; CLAUDE.md rule 12, AGENTS.md section 4).

Each case runs the hook the way `.claude/settings.json` registers it: the registered command for the
event (which passes the event as `--event <name>`), through the shell (`/bin/sh -c`, as Claude Code
runs it), on the event Claude Code sends, within the registered timeout. The hook opts in when EITHER
the event's `cwd` repository OR $CLAUDE_PROJECT_DIR's carries the marker, so no case ever uses the host
clone as CLAUDE_PROJECT_DIR (its marker would leak into the result): every case names a "kit" -- a
temporary project directory that holds the hook (a symlink) with or without the marker -- and `_run`
refuses the host clone. Opt-in through the cwd uses temporary repositories with or without the marker.

The hook is a detector: on a match it writes, on exit 0, a JSON object whose systemMessage and (the
event being known, through `--event` or the input) hookSpecificOutput.additionalContext carry one fixed
factual message and never the matched text; anything else exits 0 with no output; an opted-in but
unreadable input yields a different fixed "could not check" message on the same channels. Every check
parses the JSON and compares it to the exact expected payload, and checks that stderr is empty.

The two names are never written whole here: every case string is built from the fragments below at
run time, so this source holds no name and no form the hook flags (proven by
test_neither_source_is_flagged). No scanned text reaches a failure report:
- the parametrize id is the case id, never the scanned value;
- no test function binds scanned text to a local, which `-l` would print: each case hands `_run` a
  builder (a lambda), and `_run` resolves the registration and checks the project dir before it
  builds the input, binds the input to no name, and turns a timeout or a command that cannot start
  into a text-free error, so the standard library's frames, which hold the input, never show;
- the helpers whose arguments hold scanned text or a run's streams hide their frames from pytest's
  traceback: `_run`, the input builders (`_post_event`, `_failure_event`, `_event_stdin`,
  `_tool_input_only_stdin`, `_unknown_event_stdin`), the checks (`_flagged`, `_unchecked`, `_silent`,
  `_expect`) and the stream readers (`_json`, `_shape`);
- a failed check reports only a run's shape (exit status, JSON keys, stream lengths, whether a stream
  carries a form), never stream text.
test_a_broken_copy_prints_no_scanned_text pins this on copies with the registrations removed (every
case, every shown frame's locals printed), with a hook that ignores the opt-in and echoes the match,
and with a hook that sleeps past its registered timeout (every frame shown, frame hiding off).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
HOOK = ROOT / ".claude" / "hooks" / "excluded_dir_output_guard.py"
EVENTS = ("PostToolUse", "PostToolUseFailure")
# -I -S: no PYTHON* variables, user site or site-packages reach the hook; --event names the event.
COMMANDS = {event: f'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/excluded_dir_output_guard.py" --event {event} || exit 1'
            for event in EVENTS}
MARKER = "code-red-excluded-dir-guard"

# The hook module: its two fixed messages (they contain no directory name, and are pinned below by
# their content too) and its file-only common-directory resolver. Importing runs no __main__ block.
_spec = importlib.util.spec_from_file_location("excluded_dir_output_guard", HOOK)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)
FLAGGED_MSG = _hook.FLAGGED
UNCHECKED_MSG = _hook.UNCHECKED

# Fragments of the two names, joined only at run time (as the hook keeps them). N1 is the dated name
# <prefix><word>-<date>/<component>; N2 is the two-word name <prefix><word>-<word>.
_F1 = ("tasks/", "readi", "ness", "-", "2026", "-09-", "21", "/", "accep", "tance")
_F2 = ("tasks/", "rev", "iew", "-", "evi", "dence")
N1 = "".join(_F1)
N2 = "".join(_F2)
PREFIX1 = _F1[0]
WORD1 = _F1[1] + _F1[2]                 # the dated parent's word
DATE = _F1[4] + _F1[5] + _F1[6]         # the parent's date
COMPONENT1 = _F1[8] + _F1[9]            # the last path component
PARENT1 = PREFIX1 + WORD1 + "-" + DATE  # the dated parent directory, with its prefix
PARENT_BARE = WORD1 + "-" + DATE        # the dated parent directory's own name (as a listing prints it)
HEAD1 = PREFIX1 + WORD1 + "-"           # N1 up to its date
PREFIX2 = _F2[0]
WORD2A = _F2[1] + _F2[2]                # N2's first word
WORD2B = _F2[4] + _F2[5]                # N2's second word
DOTTED = "".join("." if ch.isdigit() else ch for ch in DATE)  # the date with every digit a dot

BACKSLASH = chr(92)
SHARP_S = "ß"                      # case-folds to the two letters "ss"
TRUNC = "... [42 characters truncated] ..."  # the middle-truncation marker of an error string
TRUNC4 = "...." + TRUNC[3:-3] + "...."       # the same marker drawn with four dots


def _registered(event: str) -> list[dict]:
    """The entries of `event` in .claude/settings.json that run the guard."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [entry for entry in settings["hooks"].get(event, [])
            if any("excluded_dir_output_guard.py" in hook.get("command", "") for hook in entry["hooks"])]


def _registered_hook(event: str) -> dict:
    """The guard's one registered hook for `event`. It takes no scanned text, so if the registration
    is broken the frames pytest prints hold none."""
    [entry] = _registered(event)
    [hook] = entry["hooks"]
    return hook


def _bare_command(event: str) -> str:
    """The registered command without its event argument: the hook as an older or manual registration
    would run it, which must fall back to the input's hook_event_name."""
    command = _registered_hook(event)["command"]
    bare = command.replace(f" --event {event}", "")
    assert bare != command, "the registration carries no --event argument"
    return bare


def _run(build: Callable[[], str], *, project_dir: Path, event: str = "PostToolUse",
         command: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the registered command for `event` (or `command`) as Claude Code does (`/bin/sh -c`), with
    CLAUDE_PROJECT_DIR set to `project_dir` -- never the host clone, whose marker would opt it in --
    within the registered timeout, on the input `build()` returns. The registration is resolved and
    the project dir checked before the input exists, and the input is bound to no name, so no frame
    here holds scanned text. A timeout or a command that cannot start becomes a text-free
    AssertionError raised `from None`: the standard library's frames hold the input."""
    __tracebackhide__ = True  # this frame builds the scanned input
    hook = _registered_hook(event)
    assert _hook._common_dir(str(project_dir)) != _hook._common_dir(str(ROOT)), "project dir is the host clone"
    try:
        return subprocess.run(["sh", "-c", command or hook["command"]], input=build(), capture_output=True,
                              text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
                              cwd=str(project_dir), timeout=hook["timeout"])
    except subprocess.TimeoutExpired:
        raise AssertionError(f"the hook did not finish within its registered {hook['timeout']} s timeout") from None
    except OSError:
        raise AssertionError("the registered command could not be started") from None


def _post_event(tool_response: object, cwd: Path) -> str:
    __tracebackhide__ = True
    return json.dumps({
        "session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
        "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
        "tool_response": tool_response, "tool_use_id": "toolu_1",
    })


def _failure_event(error: object, cwd: Path, tool_response: object = None) -> str:
    __tracebackhide__ = True
    payload = {
        "session_id": "s", "cwd": str(cwd), "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
        "tool_input": {"command": "ls"}, "error": error, "is_interrupt": False, "duration_ms": 1,
    }
    if tool_response is not None:
        payload["tool_response"] = tool_response
    return json.dumps(payload)


def _event_stdin(form: object, cwd: Path, event: str) -> str:
    __tracebackhide__ = True
    return _post_event(form, cwd) if event == "PostToolUse" else _failure_event(form, cwd)


def _tool_input_only_stdin(event: str, cwd: Path) -> str:
    """Both names only in tool_input, as a CODE RED git command's exclusion pathspecs carry them."""
    __tracebackhide__ = True
    payload = {
        "session_id": "s", "cwd": str(cwd), "hook_event_name": event, "tool_name": "Bash",
        "tool_input": {"command": f"git status -- . ':!{N1}/' ':!{N2}/'"}, "tool_use_id": "t",
    }
    if event == "PostToolUse":
        payload["tool_response"] = {"stdout": "nothing to commit", "stderr": ""}
    else:
        payload["error"] = "exit status 1"
        payload["tool_response"] = {"stdout": "", "stderr": "nothing to commit"}
    return json.dumps(payload)


def _unknown_event_stdin(field: str | None, cwd: Path) -> str:
    """A readable object with no hook_event_name, N1 under `field` (None: only in tool_input)."""
    __tracebackhide__ = True
    payload = {"session_id": "s", "cwd": str(cwd), "tool_name": "Bash", "tool_input": {"command": "ls"}}
    if field is None:
        payload["tool_input"] = {"command": f"ls {N1}"}
    else:
        payload[field] = {"stdout": N1} if field == "tool_response" else N1
    return json.dumps(payload)


def _json(stdout: str) -> object:
    __tracebackhide__ = True  # `stdout` is a run's stream
    try:
        return json.loads(stdout)
    except ValueError:
        return None


def _payload(message: str, event: str | None) -> dict:
    """The hook's output for `message`: systemMessage, plus additionalContext under the event's name
    when the event is known."""
    expected: dict = {"systemMessage": message}
    if event is not None:
        expected["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": message}
    return expected


def _shape(proc: subprocess.CompletedProcess[str]) -> str:
    """What a failing case may print about a run: its exit status, its stdout's JSON keys, and each
    stream's length and whether it carries a form -- never the streams' text, which a regressed hook
    could fill with the very form it matched."""
    __tracebackhide__ = True  # `proc` holds both streams
    payload = _json(proc.stdout)
    keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
    return (f"exit {proc.returncode}; stdout {len(proc.stdout)} chars, JSON keys {keys}, carries a form "
            f"{_hook.flagged(proc.stdout)}; stderr {len(proc.stderr)} chars, carries a form "
            f"{_hook.flagged(proc.stderr)}")


def _expect(proc: subprocess.CompletedProcess[str], expected: dict | None, case: str) -> None:
    """Exit 0, an empty stderr, and a stdout that is exactly `expected` as JSON (None: no output at
    all). Only a boolean reaches the assert, and its message is `_shape`'s, so the report shows no
    stream text."""
    __tracebackhide__ = True  # `proc` holds both streams; pytest must never print its repr
    stdout_ok = proc.stdout == "" if expected is None else _json(proc.stdout) == expected
    ok = proc.returncode == 0 and proc.stderr == "" and stdout_ok
    assert ok, f"{case}: {_shape(proc)}"


def _flagged(proc: subprocess.CompletedProcess[str], case: str, event: str | None) -> None:
    """The flag, on exactly the channels the hook documents: systemMessage, and additionalContext with
    the event's name when the event is known; empty stderr."""
    __tracebackhide__ = True
    _expect(proc, _payload(FLAGGED_MSG, event), case)


def _unchecked(proc: subprocess.CompletedProcess[str], case: str, event: str | None) -> None:
    """The could-not-check notice: to Claude (additionalContext) as well as the user when the event is
    known, which `--event` makes true even for an unreadable input; systemMessage alone otherwise."""
    __tracebackhide__ = True
    _expect(proc, _payload(UNCHECKED_MSG, event), case)


def _silent(proc: subprocess.CompletedProcess[str], case: str) -> None:
    __tracebackhide__ = True
    _expect(proc, None, case)


# ----- Opt-in repositories (event cwd) and kit directories (CLAUDE_PROJECT_DIR), file-only ----------

@pytest.fixture
def opted_repo(tmp_path: Path) -> Path:
    """A main checkout whose git common directory (`.git`) holds the marker."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / MARKER).write_text("", encoding="utf-8")
    (repo / "sub").mkdir()
    return repo


@pytest.fixture
def plain_repo(tmp_path: Path) -> Path:
    """A main checkout with no marker."""
    repo = tmp_path / "plain"
    (repo / ".git").mkdir(parents=True)
    return repo


@pytest.fixture
def opted_worktree(tmp_path: Path) -> Path:
    """A linked worktree: its `.git` is a file naming an absolute gitdir whose `commondir` names the
    common directory, where the marker sits."""
    common = tmp_path / "wtrepo" / ".git"
    git_dir = common / "worktrees" / "wt"
    git_dir.mkdir(parents=True)
    (git_dir / "commondir").write_text("../..\n", encoding="utf-8")
    (common / MARKER).write_text("", encoding="utf-8")
    checkout = tmp_path / "wt"
    checkout.mkdir()
    (checkout / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    return checkout


@pytest.fixture
def opted_worktree_relative(tmp_path: Path) -> Path:
    """A linked worktree whose `.git` file names a RELATIVE gitdir (git 2.48+ worktree.useRelativePaths),
    exercising the hook's relative-gitdir branch."""
    common = tmp_path / "relrepo" / ".git"
    git_dir = common / "worktrees" / "wt"
    git_dir.mkdir(parents=True)
    (git_dir / "commondir").write_text("../..\n", encoding="utf-8")
    (common / MARKER).write_text("", encoding="utf-8")
    checkout = tmp_path / "relwt"
    checkout.mkdir()
    relative = os.path.relpath(git_dir, checkout)  # e.g. ../relrepo/.git/worktrees/wt
    assert not os.path.isabs(relative)
    (checkout / ".git").write_text(f"gitdir: {relative}\n", encoding="utf-8")
    return checkout


@pytest.fixture
def no_repo_dir(tmp_path: Path) -> Path:
    """A directory with no repository at or above it (a scratch folder), checked, not assumed."""
    scratch = tmp_path / "scratch" / "deep"
    scratch.mkdir(parents=True)
    assert _hook._common_dir(str(scratch)) is None, "a repository sits above the temp directory"
    return scratch


def _make_kit(base: Path, opted: bool) -> Path:
    """A project directory that holds the hook (a symlink) in its own repository, with or without the
    marker: what every case uses as CLAUDE_PROJECT_DIR."""
    (base / ".claude" / "hooks").mkdir(parents=True)
    (base / ".git").mkdir()
    (base / ".claude" / "hooks" / HOOK.name).symlink_to(HOOK)
    if opted:
        (base / ".git" / MARKER).write_text("", encoding="utf-8")
    return base


@pytest.fixture(scope="session")
def plain_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_kit(tmp_path_factory.mktemp("kit_off"), opted=False)


@pytest.fixture(scope="session")
def opted_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_kit(tmp_path_factory.mktemp("kit_on"), opted=True)


# ----- The forms that must be flagged, each built from fragments --------------------------------

FLAGGED = {
    "N1 alone": N1,
    "N1 then /x.md in a sentence": f"The file {N1}/x.md was written.",
    "N2 alone": N2,
    "N2 then a slash at a line's end": f"listing:\n{N2}/\nnext",
    "N1 with its slashes written as backslash-slash": N1.replace("/", BACKSLASH + "/"),
    "N2 with its slash written as %2F": N2.replace("/", "%2F"),
    "N2 with its slash written as %2f": N2.replace("/", "%2f"),
    "N1 upper-cased": N1.upper(),
    "N1 date all eight digits as hash": N1.replace(DATE, "####-##-##"),
    "N1 date all eight digits as N": N1.replace(DATE, "NNNN-NN-NN"),
    "N1 date as the letters of YYYY-MM-DD": N1.replace(DATE, "YYYY-MM-DD"),
    "N1 date with one digit masked by a path char": N1.replace(DATE, DATE[:-1] + "x"),
    "N1 date as a bracketed token": N1.replace(DATE, "<date>"),
    "N1 date as a single star": N1.replace(DATE, "*"),
    "N1 without its leading prefix": N1[len(_F1[0]):],
    "N1 cut after its date at a text's end": f"found at {PARENT1}",
    "N1 cut after its date and slash at a text's end": f"found at {PARENT1}/",
    "N1 truncated four letters into its component at a line's end": f"{PARENT1}/{COMPONENT1[:4]}\n",
    "N1 from three letters into its word, ending before a space": f"path {WORD1[3:]}-{DATE} here",
    "N2 without its leading prefix": N2[len(_F2[0]):],
    "N2 truncated three letters into its second word at a line's end": f"{WORD2A}-{WORD2B[:3]}\n",
    "N2 from the fourth letter of its first word, before a double quote": f'at {WORD2A[3:]}-{WORD2B}"end',
    "the dated parent directory name alone": f"drwxr-xr-x 2 root root 4096 Jan 1 00:00 {PARENT_BARE}\n",
    # A cut that holds only J2 (starts inside the date), plain and with an escaped slash.
    "N1 J2 only: date then component": f"see {DATE}/{COMPONENT1} now",
    "N1 J2 only: date then an escaped slash and component": f"see {DATE}{BACKSLASH}/{COMPONENT1} now",
    # The whole date replaced by one token, inside cut forms (not only the full name).
    "N1 parent cut after a token date, bracketed": f"found at {PARENT1.replace(DATE, '<date>')}",
    "N1 cut after a token date and slash, star": f"dir {PARENT1.replace(DATE, '*')}/",
    "N1 token date, truncated into component": f"{PARENT1.replace(DATE, '[date]')}/{COMPONENT1[:4]}\n",
    "N1 three into word, token date": f"path {WORD1[3:]}-{'{date}'} here",
    "N1 parent listing, token date as ten x": f"drwx 2 root {WORD1}-{'x' * 10}\n",
    "N1 full name, token date before component": f"see {PREFIX1}{WORD1}-<date>/{COMPONENT1} ok",
    # Cuts bordered by '/' (the name under another parent) or an ASCII ellipsis.
    "N1 under another parent, git --stat abbreviation": f" .../{WORD1}-{DATE}/{COMPONENT1}/main.py | 3 +++",
    "N2 under another parent, git --stat abbreviation": f" .../{WORD2A}-{WORD2B}/notes.md | 2 +-",
    "N1 find-style ./ at a line start": f"./{WORD1}-{DATE}\n",
    "N1 ../ before the name without its prefix": f"../{WORD1}-{DATE}/{COMPONENT1}",
    "N2 x/ before the name without its prefix": f"x/{WORD2A}-{WORD2B}",
    "N1 cut ending at an ASCII ellipsis": f"{PARENT1}/{COMPONENT1[:4]}{TRUNC}",
    # A whole-date token followed by the truncation marker.
    "N1 bracketed token date before the truncation marker": f"{HEAD1}<date>{TRUNC} end",
    "N1 square-bracket token date before the truncation marker": f"{HEAD1}[date]{TRUNC} end",
    "N1 star-run token date before the truncation marker": f"{HEAD1}**{TRUNC} end",
    "N1 ten-x token date before the truncation marker": f"{HEAD1}{'x' * 10}{TRUNC} end",
    # Dots masking the date's digits, which an ASCII '...' run also reads as: every digit, the year,
    # the year's first three digits.
    "N1 cut after its date at a text's end, every digit a dot": f"found at {HEAD1}{DOTTED}",
    "N1 cut after its date at a text's end, the year as four dots": f"found at {HEAD1}....{DATE[4:]}",
    "N1 cut after its date at a text's end, the year's first three digits as dots": f"found at {HEAD1}...{DATE[3:]}",
    "N1 from three letters into its word, the year as four dots, before a space": f"path {WORD1[3:]}-....{DATE[4:]} here",
    "N1 cut after a four-dot year at a line's end": f"{HEAD1}....\nnext",
    # The truncation marker right after the word/date dash: without the prefix, and with four dots
    # (the head cases below cover it with the prefix, at date offset 0).
    "N1 word and dash, then the truncation marker, without the prefix": f"{WORD1}-{TRUNC} end",
    "N1 word and dash, then a four-dot truncation marker": f"{HEAD1}{TRUNC4} end",
    # The length counts normalised characters: a sharp s folds to the parent word's double s, so this
    # cut is eight characters (seven as written); an escaped slash is one character.
    "N1 eight-character cut whose double s is a sharp s": f"run {WORD1[-4:-2]}{SHARP_S}-{DATE[:3]} now",
    "N1 eight-character J2 cut whose slash is backslash-slash": f"see {DATE[-2:]}{BACKSLASH}/{COMPONENT1[:5]} now",
}
# The documented middle-truncation marker cutting N1 at every date offset: a head that ends there,
# and a tail that starts there. Next to the date's digits the marker is read both as a border and as
# masked digits.
FLAGGED.update({f"N1 head ending at date offset {k} before the truncation marker": f"{HEAD1}{DATE[:k]}{TRUNC} end"
                for k in range(len(DATE) + 1)})
FLAGGED.update({f"N1 tail starting at date offset {k} after the truncation marker": f"start{TRUNC}{DATE[k:]}/{COMPONENT1}"
                for k in range(len(DATE))})

# ----- The forms that must NOT be flagged -------------------------------------------------------

NOT_FLAGGED = {
    "the parent's word alone": WORD1,
    "the parent's word in prose": f"{WORD1} assessment complete",
    "the component's word alone": COMPONENT1,
    "the component's word in prose": f"{COMPONENT1} test passed",
    "N2's second word alone": WORD2B,
    "N2's second word in prose": f"{WORD2B}-based estimate",
    "N2's two words joined by an underscore": f"test_{WORD2A}_{WORD2B}_links.py",
    "a review-gate file under the prefix": f"{_F2[0]}{WORD2A}-gate.md",
    "a sibling path under the dated parent": f"{PARENT1}/plan.md",
    "the date alone": DATE,
    "accessed- then the date": f"accessed-{DATE}",
    "the mask token EXCL-A": "[EXCL-A]",
    "the mask token EXCL-B": "[EXCL-B]",
    "the mask token EXCL-B-HALF": "[EXCL-B-HALF]",
    "plain unrelated text": "the quick brown fox jumps over the lazy dog",
    # A left end that borders a path character, and cuts under eight characters.
    "N1 cut whose left end borders a path character": f"x{WORD1[3:]}-{DATE}",
    "a five-character cut across the N2 junction": f"a {WORD2A[-2:]}-{WORD2B[:2]} b",
    # A '/' before, but the segment starts mid-word, so it is not the name.
    "a slash before a mid-segment look-alike of N2": f"x/{WORD2A[1:]}-{WORD2B}",
    "a single dot before the dated name (a filename, not a path separator)": f"foo.{WORD1}-{DATE}",
    # Short N1 forms: a one-character token is rewritten to the ten-character date, but the cut counts
    # the token as written, so these stay under eight characters.
    "N1 short form: a glob in a find command": f"find . -name '*{WORD1[-1:]}-*'",
    "N1 short form: an html break in a table cell": f"| {WORD1[-2:]}-<br> |",
    "N1 short form: a tar flag before the component's first letter": f"tar -x/{COMPONENT1[:1]} ok",
    # An escaped slash counts as the one slash it stands for: these J2 cuts are seven and six
    # normalised characters (eight as written).
    "a seven-character J2 cut whose slash is backslash-slash": f"see {DATE[-2:]}{BACKSLASH}/{COMPONENT1[:4]} now",
    "a six-character J2 cut whose slash is %2F": f"see {DATE[-2:]}%2F{COMPONENT1[:3]} now",
    "a six-character J2 cut whose slash is %2f": f"see {DATE[-2:]}%2f{COMPONENT1[:3]} now",
}
NOT_FLAGGED.update({f"N1 short form: a one-character token after the word's last {j} letters": f"run {WORD1[-j:]}-* now"
                    for j in range(1, 6)})


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_result_is_flagged_on_post_tool_use(case: str, opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(FLAGGED[case], opted_repo), project_dir=plain_kit), case, "PostToolUse")


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_error_is_flagged_on_post_tool_use_failure(case: str, opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _failure_event(FLAGGED[case], opted_repo), project_dir=plain_kit,
                  event="PostToolUseFailure"), case, "PostToolUseFailure")


@pytest.mark.parametrize("case", list(NOT_FLAGGED))
def test_a_lookalike_result_is_not_flagged(case: str, opted_repo: Path, plain_kit: Path) -> None:
    _silent(_run(lambda: _post_event(NOT_FLAGGED[case], opted_repo), project_dir=plain_kit), case)
    _silent(_run(lambda: _failure_event(NOT_FLAGGED[case], opted_repo), project_dir=plain_kit,
                 event="PostToolUseFailure"), case)


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_form_nested_in_a_response_is_flagged(case: str, opted_repo: Path, plain_kit: Path) -> None:
    # The form as a value of an object in an array in an object.
    _flagged(_run(lambda: _post_event({"outer": [{"inner": {"value": FLAGGED[case]}}]}, opted_repo),
                  project_dir=plain_kit), case, "PostToolUse")


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_form_as_a_nested_object_key_is_flagged(case: str, opted_repo: Path, plain_kit: Path) -> None:
    # The form as a key inside a nested object.
    _flagged(_run(lambda: _post_event({"outer": [{FLAGGED[case]: "v"}]}, opted_repo), project_dir=plain_kit),
             case, "PostToolUse")


def test_a_name_as_a_key_of_the_response_object_itself_is_flagged(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event({N2: "v"}, opted_repo), project_dir=plain_kit),
             "a key of tool_response itself", "PostToolUse")


def test_a_name_in_a_failure_tool_response_is_flagged(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _failure_event("the command failed", opted_repo, tool_response={"stdout": N1}),
                  project_dir=plain_kit, event="PostToolUseFailure"),
             "name in a failure's tool_response", "PostToolUseFailure")


@pytest.mark.parametrize("event", EVENTS)
def test_a_name_only_in_tool_input_is_not_scanned(event: str, opted_repo: Path, plain_kit: Path) -> None:
    # The CODE RED git commands carry the names as exclusion pathspecs; scanning inputs would flag
    # every such command. tool_input is never scanned, on either event.
    _silent(_run(lambda: _tool_input_only_stdin(event, opted_repo), project_dir=plain_kit, event=event),
            f"name only in tool_input: {event}")


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_off_is_silent_even_for_a_named_result(event: str, plain_repo: Path, plain_kit: Path) -> None:
    _silent(_run(lambda: _event_stdin(N1, plain_repo, event), project_dir=plain_kit, event=event),
            f"opt-in off: {event}")


def test_a_named_result_is_flagged_in_a_linked_worktree(opted_worktree: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(N1, opted_worktree), project_dir=plain_kit), "linked worktree, opted in",
             "PostToolUse")


def test_a_named_result_is_flagged_in_a_relative_gitdir_worktree(opted_worktree_relative: Path,
                                                                 plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(N1, opted_worktree_relative), project_dir=plain_kit),
             "relative-gitdir worktree", "PostToolUse")


def test_the_marker_is_found_from_a_subdirectory(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(N2, opted_repo / "sub"), project_dir=plain_kit),
             "cwd in a subdirectory of the opted-in repo", "PostToolUse")


def test_the_project_dir_is_the_fallback_when_cwd_is_absent(opted_kit: Path) -> None:
    _flagged(_run(lambda: json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                      "tool_response": {"stdout": N1}}), project_dir=opted_kit),
             "cwd absent: marker via CLAUDE_PROJECT_DIR", "PostToolUse")


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_via_project_dir_when_cwd_is_outside_any_repository(event: str, opted_kit: Path,
                                                                    no_repo_dir: Path) -> None:
    # A CODE RED session whose cwd has moved into a scratch folder is still guarded.
    _flagged(_run(lambda: _event_stdin(N1, no_repo_dir, event), project_dir=opted_kit, event=event),
             f"cwd outside a repo, project dir opted in: {event}", event)


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_via_project_dir_when_cwd_is_another_unmarked_repository(event: str, plain_repo: Path,
                                                                         opted_kit: Path) -> None:
    # Either repository suffices: a cwd inside another, unmarked clone does not turn the guard off.
    _flagged(_run(lambda: _event_stdin(N1, plain_repo, event), project_dir=opted_kit, event=event),
             f"cwd in an unmarked repo, project dir opted in: {event}", event)


def test_cwd_outside_a_repo_and_project_dir_not_opted_in_is_silent(plain_kit: Path, no_repo_dir: Path) -> None:
    _silent(_run(lambda: _post_event(N1, no_repo_dir), project_dir=plain_kit),
            "cwd outside a repo, project dir not opted in")


@pytest.mark.parametrize("event", EVENTS)
def test_a_several_megabyte_benign_output_is_silent_and_in_time(event: str, opted_repo: Path,
                                                                plain_kit: Path) -> None:
    # ~5.5 MB, no name.
    _silent(_run(lambda: _event_stdin("The quarterly report is clean. " * 180_000, opted_repo, event),
                 project_dir=plain_kit, event=event), f"5MB benign: {event}")


def test_a_several_megabyte_output_with_a_name_is_flagged_and_in_time(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(("x" * (5 << 20)) + " " + N1, opted_repo), project_dir=plain_kit),
             "5MB with a name at the end", "PostToolUse")


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("stdin", ["", "not json at all", "[]", "123", "{"], ids=[
    "empty", "non-JSON text", "a list", "a scalar", "a truncated object"])
def test_unreadable_stdin_is_reported_unchecked_to_claude_when_opted_in(stdin: str, event: str,
                                                                        opted_kit: Path) -> None:
    # The registration's --event lets the notice reach Claude even though the input names no event.
    _unchecked(_run(lambda: stdin, project_dir=opted_kit, event=event), f"unreadable stdin opted in: {event}", event)


@pytest.mark.parametrize("event", EVENTS)
def test_a_json_parser_overflow_is_reported_unchecked_to_claude_when_opted_in(event: str, opted_kit: Path) -> None:
    # Deep nesting makes json.loads raise RecursionError, not ValueError; an opted-in session must
    # still get the could-not-check notice, never silence.
    _unchecked(_run(lambda: '{"tool_response": ' + "[" * 100_000 + "]" * 100_000 + "}", project_dir=opted_kit,
                    event=event), f"json parser overflow: {event}", event)


def test_an_unreadable_input_without_an_event_argument_gets_system_message_alone(opted_kit: Path) -> None:
    _unchecked(_run(lambda: "not json at all", project_dir=opted_kit, command=_bare_command("PostToolUse")),
               "unreadable input, no --event", None)


def test_unreadable_stdin_is_silent_when_opt_in_off(plain_kit: Path) -> None:
    _silent(_run(lambda: "not json at all", project_dir=plain_kit), "unreadable stdin, opt-in off")


@pytest.mark.parametrize("field", ["tool_response", "error"])
def test_an_unknown_event_scans_the_response_and_the_error(field: str, opted_repo: Path, plain_kit: Path) -> None:
    # Without --event and without a hook_event_name, the hook scans both and answers with
    # systemMessage alone (a guessed hookEventName would be rejected).
    _flagged(_run(lambda: _unknown_event_stdin(field, opted_repo), project_dir=plain_kit,
                  command=_bare_command("PostToolUse")), f"unknown event, name in {field}", None)


def test_an_unknown_event_never_scans_tool_input(opted_repo: Path, plain_kit: Path) -> None:
    _silent(_run(lambda: _unknown_event_stdin(None, opted_repo), project_dir=plain_kit,
                 command=_bare_command("PostToolUse")), "unknown event, name only in tool_input")


def test_neither_source_is_flagged(opted_repo: Path, plain_kit: Path) -> None:
    # R7 in miniature: the hook run on its own source and this test's source flags nothing.
    for label, path in (("hook source", HOOK), ("test source", Path(__file__))):
        _silent(_run(lambda: _post_event({"stdout": path.read_text(encoding="utf-8")}, opted_repo),
                     project_dir=plain_kit), f"{label} is not flagged")


def test_the_fixed_messages_are_distinct_and_say_what_they_mean() -> None:
    # The payload checks compare with these constants, so their content is pinned here.
    assert FLAGGED_MSG and UNCHECKED_MSG, "a fixed message is empty"
    assert FLAGGED_MSG != UNCHECKED_MSG, "the two fixed messages are the same"
    assert "contains a form of a directory name" in FLAGGED_MSG, "the flag message lost its key phrase"
    assert "could not check" in UNCHECKED_MSG, "the could-not-check message lost its key phrase"
    assert "The result is unchanged." in FLAGGED_MSG, "the flag message no longer says the result is unchanged"
    assert "The result is unchanged." in UNCHECKED_MSG, "the notice no longer says the result is unchanged"


def test_run_refuses_the_host_clone_as_project_dir() -> None:
    # The host clone may carry the marker; a case run through it would depend on the host's opt-in.
    with pytest.raises(AssertionError, match="project dir is the host clone"):
        _run(lambda: "{}", project_dir=ROOT)


# ----- Broken copies: a failing case prints no scanned text --------------------------------------

# The hook's lines the broken copies change, and what each copy plants there.
_FLAG_BRANCH = "            if flagged(text):\n                return _emit(FLAGGED, event)\n"
_ECHOING_FLAG_BRANCH = ("            if flagged(text):\n                sys.stdout.write(text)\n"
                        "                sys.stderr.write(text)\n                return _emit(FLAGGED, event)\n")
_OPT_IN_CHECK = "    if not _opted_in(cwd):  # not opted in: silent, whatever the input\n"
_OPT_IN_IGNORED = "    if False:  # this copy ignores the opt-in\n"
_UNCHECKED_BRANCH = ("        if data is None:  # opted in but the input was not a readable JSON object\n"
                     "            return _emit(UNCHECKED, event)\n")
_ECHOING_UNCHECKED_BRANCH = ("        if data is None:  # opted in but the input was not a readable JSON object\n"
                             "            sys.stderr.write(_C1)\n            return _emit(UNCHECKED, event)\n")
_MAIN = "def main() -> int:\n"
_SLEEPING_MAIN = "def main() -> int:\n    import time\n    time.sleep(3)\n"
_PIN = "test_a_broken_copy_prints_no_scanned_text"
_MESSAGES_TEST = "test_the_fixed_messages_are_distinct_and_say_what_they_mean"
_REGISTRATION_TEST = "test_the_hook_is_registered_on_both_events"

# Each broken copy: the hook edits it plants, the events whose guard registration it removes, the
# timeout it gives the PostToolUse registration, what it runs, and its pytest flags.
_COPIES: dict[str, dict] = {
    # Every case that runs the hook fails on the missing registration, before any input exists, and
    # -l prints the locals of every frame shown, so no test function may bind scanned text to a name.
    "the registrations removed": {
        "edits": (), "drop": EVENTS, "timeout": None, "flags": ["--tb=long", "-l"],
        "select": lambda test: [str(test), "-k", f"not {_PIN}"],
    },
    # A hook that ignores the opt-in and echoes what it matched (and a name on an unchecked input):
    # the flag, silent and unchecked checks fail, and their frames hide the streams.
    "an echoing hook that ignores the opt-in": {
        "edits": ((_FLAG_BRANCH, _ECHOING_FLAG_BRANCH), (_OPT_IN_CHECK, _OPT_IN_IGNORED),
                  (_UNCHECKED_BRANCH, _ECHOING_UNCHECKED_BRANCH)),
        "drop": (), "timeout": None, "flags": ["--tb=long", "-l"],
        "select": lambda test: [f"{test}::test_a_named_result_is_flagged_on_post_tool_use",
                                f"{test}::test_opt_in_off_is_silent_even_for_a_named_result",
                                f"{test}::test_unreadable_stdin_is_reported_unchecked_to_claude_when_opted_in"],
    },
    # A hook that sleeps past a one-second registered timeout: the standard library's frames, which
    # hold the input, must never reach the report. --full-trace turns pytest's frame hiding off and -l
    # prints every frame's locals, so `_run`'s own arguments and locals must hold no scanned text.
    "a hook that sleeps past its timeout": {
        "edits": ((_MAIN, _SLEEPING_MAIN),), "drop": (), "timeout": 1, "flags": ["--full-trace", "-l"],
        "select": lambda test: [f"{test}::test_a_named_result_is_flagged_on_post_tool_use[N1 alone]"],
    },
}


def _guard_entries(settings: dict, event: str) -> list[dict]:
    return [entry for entry in settings["hooks"].get(event, [])
            if any("excluded_dir_output_guard.py" in hook.get("command", "") for hook in entry["hooks"])]


def _nested_outcomes(junit: Path) -> dict[str, str]:
    """Each copied test's outcome from the copied run's JUnit XML, as one word: "passed", or its
    failure's kind -- "unpack" (the missing registration), "form" (a check whose report says a stream
    carries a form), "timeout" (_run's timeout), else "other" -- never the failure's text. The file
    holds the whole report, so it is deleted once read."""
    __tracebackhide__ = True
    try:
        root = ElementTree.parse(junit).getroot()
    finally:
        junit.unlink(missing_ok=True)
    outcomes = {}
    for case in root.iter("testcase"):
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        message = "" if problem is None else problem.get("message", "")
        if problem is None:
            kind = "other" if case.find("skipped") is not None else "passed"
        elif "ValueError: not enough values to unpack" in message:
            kind = "unpack"
        elif "carries a form True" in message:
            kind = "form"
        elif "did not finish within its registered" in message:
            kind = "timeout"
        else:
            kind = "other"
        outcomes[case.get("name")] = kind
    return outcomes


def _failed_as_intended(variant: str, outcomes: dict[str, str]) -> bool:
    """Whether the copied run failed the way its break should make it fail, so a copy whose hook
    cannot run at all (no python3 on PATH, say) does not pass the pin vacuously."""
    if variant == "the registrations removed":
        rest = {name: kind for name, kind in outcomes.items() if name not in (_MESSAGES_TEST, _REGISTRATION_TEST)}
        return (outcomes.get(_MESSAGES_TEST) == "passed" and outcomes.get(_REGISTRATION_TEST) == "other"
                and bool(rest) and set(rest.values()) == {"unpack"})
    if variant == "an echoing hook that ignores the opt-in":
        # Every flag case, both opt-in-off cases and the ten unreadable-input cases fail with the
        # streams carrying a form, which their reports state and do not print.
        return len(outcomes) == len(FLAGGED) + 2 + 10 and set(outcomes.values()) == {"form"}
    return outcomes == {"test_a_named_result_is_flagged_on_post_tool_use[N1 alone]": "timeout"}


@pytest.mark.parametrize("variant", list(_COPIES))
def test_a_broken_copy_prints_no_scanned_text(variant: str, tmp_path: Path) -> None:
    # Copy the hook, the settings and this file under a scratch root, break the copy as the variant
    # says, run its cases there, and check the report with the hook's own matcher. The report is never
    # printed or kept, and the copied run must fail the intended way.
    copy = _COPIES[variant]
    root = tmp_path / "copy"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / "backend" / "tests" / "unit").mkdir(parents=True)
    hook_source = HOOK.read_text(encoding="utf-8")
    for old, new in copy["edits"]:
        assert hook_source.count(old) == 1, f"{variant}: the hook's source changed; update this pin"
        hook_source = hook_source.replace(old, new)
    (root / ".claude" / "hooks" / HOOK.name).write_text(hook_source, encoding="utf-8")
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    for event in copy["drop"]:
        settings["hooks"][event] = [entry for entry in settings["hooks"][event]
                                    if entry not in _guard_entries(settings, event)]
    if copy["timeout"] is not None:
        [entry] = _guard_entries(settings, "PostToolUse")
        entry["hooks"][0]["timeout"] = copy["timeout"]
    (root / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    test_copy = root / "backend" / "tests" / "unit" / Path(__file__).name
    shutil.copy(Path(__file__), test_copy)
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *copy["select"](test_copy), "-p", "no:cacheprovider",
         "-p", "no:randomly", "-q", *copy["flags"], f"--basetemp={tmp_path / 'nested'}",
         f"--junitxml={tmp_path / 'nested.xml'}"],
        cwd=root, capture_output=True, text=True, timeout=300,
        env={key: value for key, value in os.environ.items() if not key.startswith("PYTEST_")})
    leaked = _hook.flagged(proc.stdout + proc.stderr)
    del proc
    intended = _failed_as_intended(variant, _nested_outcomes(tmp_path / "nested.xml"))
    assert intended, f"{variant}: the copied run did not fail the intended way"
    assert not leaked, f"{variant}: the report printed scanned text"


def test_the_hook_is_registered_on_both_events() -> None:
    for event in EVENTS:
        expected = [{"matcher": "*", "hooks": [{"type": "command", "command": COMMANDS[event], "timeout": 10}]}]
        assert _registered(event) == expected, event
    assert HOOK.is_file()
    assert "disableAllHooks" not in json.loads(SETTINGS.read_text(encoding="utf-8"))
