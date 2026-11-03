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

The two names are never written whole here: the module holds only their fragments, case ids and
builders, and `_Parts` joins the names when a case runs, so this source holds no name and no form the
hook flags (proven by test_neither_source_is_flagged), and no module global holds one either (an error
while a module loads makes pytest print module globals under `-l`; the hook builds its names lazily
too, each joined straight onto its object, so no argument or local of the hook's frames holds one --
test_no_frame_holds_a_joined_name_while_the_names_are_built reads every frame of a traced build
at each event --, and this file scans in-process through `_shape` and the pin). No scanned text
reaches a failure report:
- the parametrize id is the case id, never the scanned value;
- `_Parts` and `_Run` (a finished run: exit status and streams) have text-free reprs, so no frame that
  holds one prints a name or a stream, even with frame hiding off (`--full-trace`);
- no test function binds scanned text to a local, which `-l` would print: each case hands `_run` a
  builder (a lambda), and `_run` resolves the registration and checks the project dir before it
  builds the input, binds the input to no name, and turns a timeout or a command that cannot start
  into a text-free error, so the standard library's frames, which hold the input, never show;
- the helpers whose arguments hold scanned text or a run's streams hide their frames from pytest's
  traceback: `_run`, `_cpu_run`, `_text`, the input builders (`_post_event`, `_failure_event`,
  `_event_stdin`, `_tool_input_only_stdin`, `_unknown_event_stdin`, `_path_listing`,
  `_token_listing`, `_costliest_listing`), the checks (`_flagged`, `_unchecked`, `_silent`,
  `_expect`) and the stream readers (`_json`, `_shape`);
- a failed check reports only a run's shape (exit status, JSON keys, stream lengths, whether a stream
  carries a form), never stream text.
test_a_broken_copy_prints_no_scanned_text pins this on copies with the registrations removed (every
case, every shown frame's locals printed in full), with a hook that ignores the opt-in and echoes the
match (frame hiding on, then off), with a hook that sleeps past its registered timeout (frame hiding
off), with an error raised after the last statement of a name's construction (pytest's default flags,
then every local printed, then on the two-word name's alone) and at the end of the hook's `_names()`
(every local printed, then frame hiding off), and with an error appended to the end of the test
module's and of the hook's source, so it runs after every module-level statement.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import resource
import signal
import subprocess
import sys
import types
from collections.abc import Callable
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
HOOK = ROOT / ".claude" / "hooks" / "excluded_dir_output_guard.py"
LESSON = ROOT / "lessons" / "ops-flag-excluded-directory-names-in-tool-output.md"
EVENTS = ("PostToolUse", "PostToolUseFailure")
# -I -S: no PYTHON* variables, user site or site-packages reach the hook; --event names the event.
COMMANDS = {event: f'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/excluded_dir_output_guard.py" --event {event} || exit 1'
            for event in EVENTS}
MARKER = "code-red-excluded-dir-guard"

# The hook module: its two fixed messages (they contain no directory name, and are pinned below by
# their content too), its matcher and its file-only common-directory resolver. Importing runs no
# __main__ block and joins no name.
_spec = importlib.util.spec_from_file_location("excluded_dir_output_guard", HOOK)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)
FLAGGED_MSG = _hook.FLAGGED
UNCHECKED_MSG = _hook.UNCHECKED

# Fragments of the two names, joined only inside _Parts (as the hook keeps them). N1 is the dated
# name <prefix><word>-<date>/<component>; N2 is the two-word name <prefix><word>-<word>.
_F1 = ("tasks/", "readi", "ness", "-", "2026", "-09-", "21", "/", "accep", "tance")
_F2 = ("tasks/", "rev", "iew", "-", "evi", "dence")
_DATE_LEN = sum(len(fragment) for fragment in _F1[4:7])

BACKSLASH = chr(92)
SHARP_S = "\N{LATIN SMALL LETTER SHARP S}"  # case-folds to the two letters "ss"
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"         # a Unicode ellipsis, one character
TRUNC = "... [42 characters truncated] ..."  # the middle-truncation marker of an error string
TRUNC4 = "...." + TRUNC[3:-3] + "...."       # the same marker drawn with four dots


class _Parts:
    """The two names and the parts the cases are built from, joined from the fragments when a case
    runs, never at module scope. Its repr is text-free, so a frame that holds it prints no name."""

    __slots__ = ("n1", "n2", "prefix1", "word1", "date", "component1", "parent1", "parent_bare", "head1",
                 "word2a", "word2b", "dotted")

    def __init__(self) -> None:
        self.prefix1 = _F1[0]
        self.word1 = _F1[1] + _F1[2]                        # the dated parent's word
        self.date = _F1[4] + _F1[5] + _F1[6]                # the parent's date
        self.component1 = _F1[8] + _F1[9]                   # the last path component
        self.n1 = "".join(_F1)
        self.n2 = "".join(_F2)
        self.parent1 = self.prefix1 + self.word1 + "-" + self.date  # the dated parent, with its prefix
        self.parent_bare = self.word1 + "-" + self.date             # the dated parent's own name
        self.head1 = self.prefix1 + self.word1 + "-"                # N1 up to its date
        self.word2a = _F2[1] + _F2[2]                       # N2's first word
        self.word2b = _F2[4] + _F2[5]                       # N2's second word
        self.dotted = "".join("." if ch.isdigit() else ch for ch in self.date)  # every date digit a dot

    def __repr__(self) -> str:
        return "<the names' parts>"


def _text(table: dict[str, Callable[[_Parts], str]], case: str) -> str:
    """The scanned text of `case` in `table`, built now from freshly joined parts."""
    __tracebackhide__ = True
    return table[case](_Parts())


class _Run:
    """A finished run of the hook: its exit status and both streams. Its repr is the run's shape,
    never stream text, so a frame that holds it prints no stream, even with frame hiding off."""

    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, proc: subprocess.CompletedProcess[str]) -> None:
        self.returncode, self.stdout, self.stderr = proc.returncode, proc.stdout, proc.stderr

    def __repr__(self) -> str:
        return f"<run: {_shape(self)}>"


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
         command: str | None = None) -> _Run:
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
        return _Run(subprocess.run(["sh", "-c", command or hook["command"]], input=build(), capture_output=True,
                                   text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
                                   cwd=str(project_dir), timeout=hook["timeout"]))
    except subprocess.TimeoutExpired:
        raise AssertionError(f"the hook did not finish within its registered {hook['timeout']} s timeout") from None
    except OSError:
        raise AssertionError("the registered command could not be started") from None


def _cpu_run(build: Callable[[], str], *, project_dir: Path, hang_stop: int) -> tuple[_Run, float]:
    """Run the registered PostToolUse command as `_run` does, in its own process group, and return the
    run and the CPU seconds (user plus system) the shell and the hook used, from the children's resource
    usage around it. `hang_stop` is wall time and only stops a runaway: past it the whole group is
    killed and the case fails with a text-free AssertionError raised `from None`. The input is bound to
    no name, and the streams go straight into a `_Run`."""
    __tracebackhide__ = True  # this frame builds the scanned input
    hook = _registered_hook("PostToolUse")
    assert _hook._common_dir(str(project_dir)) != _hook._common_dir(str(ROOT)), "project dir is the host clone"
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    proc = subprocess.Popen(["sh", "-c", hook["command"]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, cwd=str(project_dir), start_new_session=True,
                            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)})
    try:
        run = _Run(subprocess.CompletedProcess(proc.args, -1, *proc.communicate(input=build(), timeout=hang_stop)))
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise AssertionError(f"the hook was still running at its {hang_stop} s hang stop") from None
    run.returncode = proc.returncode
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return run, after.ru_utime - before.ru_utime + after.ru_stime - before.ru_stime


def _post_event(tool_response: object, cwd: Path) -> str:
    __tracebackhide__ = True
    return json.dumps({
        "session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
        "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
        "tool_response": tool_response, "tool_use_id": "toolu_1",
    })


def _failure_event(error: object, cwd: Path, tool_response: object = None) -> str:
    __tracebackhide__ = True
    return json.dumps({
        "session_id": "s", "cwd": str(cwd), "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
        "tool_input": {"command": "ls"}, "error": error, "is_interrupt": False, "duration_ms": 1,
        **({} if tool_response is None else {"tool_response": tool_response}),
    })


def _event_stdin(form: object, cwd: Path, event: str) -> str:
    __tracebackhide__ = True
    return _post_event(form, cwd) if event == "PostToolUse" else _failure_event(form, cwd)


def _tool_input_only_stdin(event: str, cwd: Path) -> str:
    """Both names only in tool_input, as a CODE RED git command's exclusion pathspecs carry them. No
    local holds a name: the input is built in the one expression that serialises it."""
    __tracebackhide__ = True
    rest = ({"tool_response": {"stdout": "nothing to commit", "stderr": ""}} if event == "PostToolUse"
            else {"error": "exit status 1", "tool_response": {"stdout": "", "stderr": "nothing to commit"}})
    return json.dumps({
        "session_id": "s", "cwd": str(cwd), "hook_event_name": event, "tool_name": "Bash",
        "tool_input": {"command": f"git status -- . ':!{_Parts().n1}/' ':!{_Parts().n2}/'"}, "tool_use_id": "t",
        **rest,
    })


def _unknown_event_stdin(field: str | None, cwd: Path) -> str:
    """A readable object with no hook_event_name, N1 under `field` (None: only in tool_input). No local
    holds the name: the input is built in the one expression that serialises it."""
    __tracebackhide__ = True
    base = {"session_id": "s", "cwd": str(cwd), "tool_name": "Bash"}
    if field is None:
        return json.dumps({**base, "tool_input": {"command": f"ls {_Parts().n1}"}})
    return json.dumps({**base, "tool_input": {"command": "ls"},
                       field: {"stdout": _Parts().n1} if field == "tool_response" else _Parts().n1})


def _path_listing() -> str:
    """A find-style listing of several megabytes, dense with junction hits that are no cut: per line,
    two date/component hits (a '/' before the component's first letter) and one word/date hit (the
    dated word's last letter before a dash), with dashes throughout and one ASCII '...'."""
    __tracebackhide__ = True
    parts = _Parts()
    first, last = parts.component1[0], parts.word1[-1]
    lines = [f"./{first}pp/{first}sset{last}-v2/images/icon_{i:06d}.png\n" for i in range(140_000)]
    lines.insert(70_000, "...\n")
    return "".join(lines)


def _token_listing(with_form: bool) -> str:
    """About two megabytes in which every line holds an ellipsis token: four dots before the
    component's first three letters (the per-digit walk at a token's date/component junction), then
    lines alternating an ellipsis after the dated word's last letter before a sibling file (the
    elision-border check) and four dots before a sibling file, none of them a cut; and, `with_form`,
    last one form only the per-digit walk after an ellipsis token finds (five dots, a closing bracket,
    the slash and the component). The component lines come first, so no token on the lines after them
    has a date/component junction within its window. Without the form, a window search that ran past
    its limit would cross the rest of the text at every one of those tokens; with it, such a search
    would stop at the last line's junction and end the scan there, so the silent listing pins the
    limit and the other proves the hook reads to the end."""
    __tracebackhide__ = True
    parts = _Parts()
    component_lines = f"q-..../{parts.component1[:3]}\n" * 60_000
    sibling_lines = f"q{parts.word1[-1]}-{ELLIPSIS}/plan.md\nq-..../plan\n" * 60_000
    return component_lines + sibling_lines + (f"-.....]/{parts.component1}\n" if with_form else "")


# The costliest-class case's blocks, one run each. The first run: block A1, the first class (units of
# four characters, 1.0 MB, the size the run's CPU per MB is taken over), then block B's lines of 101
# characters (about 0.4 MB). The second run: block A2, the second class alone (units of ten
# characters, 0.5 MB).
COSTLIEST_A1_UNITS = 250_000
COSTLIEST_A1_MB = 1.0
COSTLIEST_B_LINES = 4_000
COSTLIEST_A2_UNITS = 50_000
COSTLIEST_A2_MB = 0.5


def _costliest_listing(second: bool) -> str:
    """A listing with no cut for one run of the costliest-class case. The first: the dated word's last
    letter, a dash, an x and a closing parenthesis, repeated (block A1) -- at every token the walk
    nine characters back finds its junction and the walk at the token's own dash passes its junction
    check, and both stop at their pre-checks (read per digit, no cut there reaches eight characters);
    then lines of a letter, a dash, an x and a closing parenthesis (block B), whose tokens fail every
    junction check, with no junction anywhere after them, so a junction check that searched on from
    its index would cross the rest of the text at every token. The second, `second`: a letter, the
    word's last letter, a dash, a letter and the word's last three letters, a dash, a star and a
    closing parenthesis, repeated (block A2) -- at every token both walks pass their pre-checks and
    walk, the one six characters back to find no clean start, the one at the token's own dash to find
    no cut of eight characters."""
    __tracebackhide__ = True
    parts = _Parts()
    last = parts.word1[-1]
    if second:
        return f"q{last}-a{parts.word1[-3:]}-*)" * COSTLIEST_A2_UNITS
    return f"{last}-x)" * COSTLIEST_A1_UNITS + ("q-x)" * 25 + "\n") * COSTLIEST_B_LINES


def _stated_size_mb() -> float:
    """The size the hook's Limits paragraph and the lesson state for the costliest class: a result
    that holds more than that many MB of it may reach the registered timeout."""
    pattern = re.compile(r"more than about (\d+(?:\.\d+)?) MB of it may reach that timeout")
    hook_sizes = pattern.findall(" ".join((_hook.__doc__ or "").split()))
    lesson_sizes = pattern.findall(" ".join(LESSON.read_text(encoding="utf-8").split()))
    assert len(hook_sizes) == 1 and hook_sizes == lesson_sizes, "the hook and the lesson must state one size, the same"
    return float(hook_sizes[0])


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


def _shape(run: _Run) -> str:
    """What a failing case may print about a run: its exit status, its stdout's JSON keys, and each
    stream's length and whether it carries a form -- never the streams' text, which a regressed hook
    could fill with the very form it matched."""
    __tracebackhide__ = True  # `run` holds both streams
    payload = _json(run.stdout)
    keys = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
    return (f"exit {run.returncode}; stdout {len(run.stdout)} chars, JSON keys {keys}, carries a form "
            f"{_hook.flagged(run.stdout)}; stderr {len(run.stderr)} chars, carries a form "
            f"{_hook.flagged(run.stderr)}")


def _expect(run: _Run, expected: dict | None, case: str) -> None:
    """Exit 0, an empty stderr, and a stdout that is exactly `expected` as JSON (None: no output at
    all). Only a boolean reaches the assert, and its message is `_shape`'s, so the report shows no
    stream text."""
    __tracebackhide__ = True  # `run` holds both streams
    stdout_ok = run.stdout == "" if expected is None else _json(run.stdout) == expected
    ok = run.returncode == 0 and run.stderr == "" and stdout_ok
    assert ok, f"{case}: {_shape(run)}"


def _flagged(run: _Run, case: str, event: str | None) -> None:
    """The flag, on exactly the channels the hook documents: systemMessage, and additionalContext with
    the event's name when the event is known; empty stderr."""
    __tracebackhide__ = True
    _expect(run, _payload(FLAGGED_MSG, event), case)


def _unchecked(run: _Run, case: str, event: str | None) -> None:
    """The could-not-check notice: to Claude (additionalContext) as well as the user when the event is
    known, which `--event` makes true even for an unreadable input; systemMessage alone otherwise."""
    __tracebackhide__ = True
    _expect(run, _payload(UNCHECKED_MSG, event), case)


def _silent(run: _Run, case: str) -> None:
    __tracebackhide__ = True
    _expect(run, None, case)


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


# ----- The forms that must be flagged: case ids and builders, the text built when a case runs ----

FLAGGED: dict[str, Callable[[_Parts], str]] = {
    "N1 alone": lambda p: p.n1,
    "N1 then /x.md in a sentence": lambda p: f"The file {p.n1}/x.md was written.",
    "N2 alone": lambda p: p.n2,
    "N2 then a slash at a line's end": lambda p: f"listing:\n{p.n2}/\nnext",
    "N1 with its slashes written as backslash-slash": lambda p: p.n1.replace("/", BACKSLASH + "/"),
    "N2 with its slash written as %2F": lambda p: p.n2.replace("/", "%2F"),
    "N2 with its slash written as %2f": lambda p: p.n2.replace("/", "%2f"),
    "N1 upper-cased": lambda p: p.n1.upper(),
    "N1 date all eight digits as hash": lambda p: p.n1.replace(p.date, "####-##-##"),
    "N1 date all eight digits as N": lambda p: p.n1.replace(p.date, "NNNN-NN-NN"),
    "N1 date as the letters of YYYY-MM-DD": lambda p: p.n1.replace(p.date, "YYYY-MM-DD"),
    "N1 date with one digit masked by a path char": lambda p: p.n1.replace(p.date, p.date[:-1] + "x"),
    "N1 date as a bracketed token": lambda p: p.n1.replace(p.date, "<date>"),
    "N1 date as a single star": lambda p: p.n1.replace(p.date, "*"),
    "N1 without its leading prefix": lambda p: p.n1[len(p.prefix1):],
    "N1 cut after its date at a text's end": lambda p: f"found at {p.parent1}",
    "N1 cut after its date and slash at a text's end": lambda p: f"found at {p.parent1}/",
    "N1 truncated four letters into its component at a line's end": lambda p: f"{p.parent1}/{p.component1[:4]}\n",
    "N1 from three letters into its word, ending before a space": lambda p: f"path {p.word1[3:]}-{p.date} here",
    "N2 without its leading prefix": lambda p: p.n2[len(_F2[0]):],
    "N2 truncated three letters into its second word at a line's end": lambda p: f"{p.word2a}-{p.word2b[:3]}\n",
    "N2 from the fourth letter of its first word, before a double quote": lambda p: f'at {p.word2a[3:]}-{p.word2b}"end',
    "the dated parent directory name alone": lambda p: f"drwxr-xr-x 2 root root 4096 Jan 1 00:00 {p.parent_bare}\n",
    # A cut that holds only J2 (starts inside the date), plain and with an escaped slash.
    "N1 J2 only: date then component": lambda p: f"see {p.date}/{p.component1} now",
    "N1 J2 only: date then an escaped slash and component": lambda p: f"see {p.date}{BACKSLASH}/{p.component1} now",
    # The whole date replaced by one token, inside cut forms (not only the full name).
    "N1 parent cut after a token date, bracketed": lambda p: f"found at {p.parent1.replace(p.date, '<date>')}",
    "N1 cut after a token date and slash, star": lambda p: f"dir {p.parent1.replace(p.date, '*')}/",
    "N1 token date, truncated into component": lambda p: f"{p.parent1.replace(p.date, '[date]')}/{p.component1[:4]}\n",
    "N1 three into word, token date": lambda p: f"path {p.word1[3:]}-{'{date}'} here",
    "N1 parent listing, token date as ten x": lambda p: f"drwx 2 root {p.word1}-{'x' * 10}\n",
    "N1 full name, token date before component": lambda p: f"see {p.head1}<date>/{p.component1} ok",
    # Cuts bordered by '/' (the name under another parent) or an ASCII ellipsis.
    "N1 under another parent, git --stat abbreviation": lambda p: f" .../{p.parent_bare}/{p.component1}/main.py | 3 +++",
    "N2 under another parent, git --stat abbreviation": lambda p: f" .../{p.word2a}-{p.word2b}/notes.md | 2 +-",
    "N1 find-style ./ at a line start": lambda p: f"./{p.parent_bare}\n",
    "N1 ../ before the name without its prefix": lambda p: f"../{p.parent_bare}/{p.component1}",
    "N2 x/ before the name without its prefix": lambda p: f"x/{p.word2a}-{p.word2b}",
    "N1 cut ending at an ASCII ellipsis": lambda p: f"{p.parent1}/{p.component1[:4]}{TRUNC}",
    # A whole-date token followed by the truncation marker.
    "N1 bracketed token date before the truncation marker": lambda p: f"{p.head1}<date>{TRUNC} end",
    "N1 square-bracket token date before the truncation marker": lambda p: f"{p.head1}[date]{TRUNC} end",
    "N1 star-run token date before the truncation marker": lambda p: f"{p.head1}**{TRUNC} end",
    "N1 ten-x token date before the truncation marker": lambda p: f"{p.head1}{'x' * 10}{TRUNC} end",
    # Dots masking the date's digits, which an ASCII '...' run also reads as: every digit, the year,
    # the year's first three digits.
    "N1 cut after its date at a text's end, every digit a dot": lambda p: f"found at {p.head1}{p.dotted}",
    "N1 cut after its date at a text's end, the year as four dots": lambda p: f"found at {p.head1}....{p.date[4:]}",
    "N1 cut after its date at a text's end, the year's first three digits as dots": lambda p: f"found at {p.head1}...{p.date[3:]}",
    "N1 from three letters into its word, the year as four dots, before a space": lambda p: f"path {p.word1[3:]}-....{p.date[4:]} here",
    "N1 cut after a four-dot year at a line's end": lambda p: f"{p.head1}....\nnext",
    # The truncation marker right after the word/date dash: without the prefix, and with four dots
    # (the head cases below cover it with the prefix, at date offset 0).
    "N1 word and dash, then the truncation marker, without the prefix": lambda p: f"{p.word1}-{TRUNC} end",
    "N1 word and dash, then a four-dot truncation marker": lambda p: f"{p.head1}{TRUNC4} end",
    # A dotted year, then the truncation marker at a month or day digit: the year's dots are masked
    # digits and the marker's dots a border, in one cut.
    "N1 four-dot year, then the truncation marker at month offset 0": lambda p: f"{p.head1}....{p.date[4:5]}{TRUNC} end",
    "N1 four-dot year, then the truncation marker at month offset 1": lambda p: f"{p.head1}....{p.date[4:6]}{TRUNC} end",
    "N1 four-dot year, then the truncation marker at day offset 0": lambda p: f"{p.head1}....{p.date[4:8]}{TRUNC} end",
    "N1 four-dot year, then the truncation marker at day offset 1": lambda p: f"{p.head1}....{p.date[4:9]}{TRUNC} end",
    "N1 four-dot year, then a four-dot truncation marker at day offset 0": lambda p: f"{p.head1}....{p.date[4:8]}{TRUNC4} end",
    "N1 word, dash and four-dot year, then the truncation marker at month offset 1": lambda p: f"{p.word1}-....{p.date[4:6]}{TRUNC} end",
    # A Unicode ellipsis at the date's digits, then a path character: the ellipsis ends the cut.
    "N1 cut two digits into its date, then an ellipsis, a slash and the component": lambda p: f"{p.head1}{p.date[:2]}{ELLIPSIS}/{p.component1}",
    "N1 cut after its date's first digit, an ellipsis, its last digit, a slash and the component": lambda p: f"{p.head1}{p.date[:1]}{ELLIPSIS}{p.date[-1:]}/{p.component1}",
    "N1 cut after its year and dash, then an ellipsis, a slash and the component": lambda p: f"{p.head1}{p.date[:5]}{ELLIPSIS}/{p.component1}",
    "N1 word, dash, the date's first digit, an ellipsis, its last digit, a slash and the component": lambda p: f"{p.word1}-{p.date[:1]}{ELLIPSIS}{p.date[-1:]}/{p.component1}",
    "N1 cut two digits into its date as a JSON key": lambda p: f'{{"{p.head1}{p.date[:2]}":1}}',
    # A sibling path under the dated parent whose year, or every date digit, is dotted: a '...' run
    # after the date's first digit also reads as a truncation marker inside the date, so the parent is
    # flagged (over-flagging this rare shape is the safe side, by design).
    "the dated parent with its year as four dots, then a sibling file": lambda p: f"{p.head1}....{p.date[4:]}/plan.md",
    "the dated parent with every date digit a dot, then a sibling file": lambda p: f"{p.head1}{p.dotted}/plan.md",
    # The whole date elided by one ellipsis, Unicode or three ASCII dots: a whole-date token whose end
    # is also a clean border, so the name, with or without its prefix, and the parent before a sibling
    # file are flagged.
    "N1 with its date elided by a Unicode ellipsis, before a space": lambda p: f"see {p.head1}{ELLIPSIS}/{p.component1} now",
    "N1 with its date elided by a Unicode ellipsis, at a line's end": lambda p: f"{p.head1}{ELLIPSIS}/{p.component1}\n",
    "N1 with its date elided by three dots, before a space": lambda p: f"see {p.head1}.../{p.component1} now",
    "N1 with its date elided by three dots, at a line's end": lambda p: f"{p.head1}.../{p.component1}\n",
    "N1 without its prefix, its date elided by a Unicode ellipsis, before a space": lambda p: f"see {p.word1}-{ELLIPSIS}/{p.component1} now",
    "N1 without its prefix, its date elided by a Unicode ellipsis, at a line's end": lambda p: f"{p.word1}-{ELLIPSIS}/{p.component1}\n",
    "N1 without its prefix, its date elided by three dots, before a space": lambda p: f"see {p.word1}-.../{p.component1} now",
    "N1 without its prefix, its date elided by three dots, at a line's end": lambda p: f"{p.word1}-.../{p.component1}\n",
    "the dated parent with its date elided by a Unicode ellipsis, then a sibling file": lambda p: f"{p.head1}{ELLIPSIS}/plan.md",
    "the dated parent with its date elided by three dots, then a sibling file": lambda p: f"{p.head1}.../plan.md",
    # A cut across an elided date into the component counts the ellipsis as written, as for any token:
    # from the dash after a space, and from the word's last two letters.
    "a space, the dash, a Unicode ellipsis, a slash and the component": lambda p: f"see -{ELLIPSIS}/{p.component1} now",
    "a space, the dash, three dots, a slash and the component": lambda p: f"see -.../{p.component1} now",
    "the word's last two letters, an elided date and four component letters at a line's end":
        lambda p: f"{p.word1[-2:]}-{ELLIPSIS}/{p.component1[:4]}\n",
    # An ellipsis followed by another is no whole-date token: per digit, two masked digits make this an
    # eight-character cut.
    "the word's last five letters, the dash and two Unicode ellipses": lambda p: f"{p.word1[-5:]}-{ELLIPSIS}{ELLIPSIS}",
    # A mask token after an elided word or the truncation marker still stands for the whole date.
    "a Unicode ellipsis, the dash, a star, a slash and the component": lambda p: f"{ELLIPSIS}-*/{p.component1}",
    "a Unicode ellipsis, the dash, a bracketed token, a slash and the component": lambda p: f"{ELLIPSIS}-<date>/{p.component1}",
    "the truncation marker, the dash, a star, a slash and the component": lambda p: f"{TRUNC}-*/{p.component1}",
    # A dot-run token is also the date's last digits dotted at the component's slash after it: with the
    # name's own start not clean, a cut through that junction starts inside the run, after three dots.
    "a letter, the word, the dash, four dots, a slash and six component letters": lambda p: f"x{p.word1}-..../{p.component1[:6]}",
    "a letter, the word, the dash, five dots, a slash and the component": lambda p: f"x{p.word1}-...../{p.component1}",
    # A punctuation mark between an ellipsis token and the component's slash is the date's last digit,
    # per digit: a cut through that junction then starts inside the token, or at the first of two marks.
    "a dash, five dots, a closing bracket, a slash and the component at a line's end": lambda p: f"-.....]/{p.component1}\n",
    "a dash, a Unicode ellipsis, a closing parenthesis, a slash and the component": lambda p: f"-{ELLIPSIS})/{p.component1}",
    "a dash, a Unicode ellipsis, two marks, a slash and five component letters at a line's end":
        lambda p: f"-{ELLIPSIS}])/{p.component1[:5]}\n",
    # A letter-masked year, or year and month, keeps its per-digit reading when a whole-date token
    # claims its own dash (the letter left of that dash lets the token match there): an ellipsis, a
    # star, a bracketed token, the truncation marker, or a mask run for the day.
    "N1 with a letter-masked year, its dash, an ellipsis, a slash and the component":
        lambda p: f"{p.head1}YYYY-{ELLIPSIS}/{p.component1}",
    "N1 with a letter-masked year, its dash, three dots, a slash and the component":
        lambda p: f"{p.head1}YYYY-.../{p.component1}",
    "N1 with a letter-masked year and month, their dash, an ellipsis, a slash and the component":
        lambda p: f"{p.head1}YYYY-MM-{ELLIPSIS}/{p.component1}",
    "N1 with a letter-masked year, its dash, a star, a slash and the component":
        lambda p: f"{p.head1}YYYY-*/{p.component1}",
    "N1 with a letter-masked year, its dash, an angle-bracket token, a slash and the component":
        lambda p: f"{p.head1}YYYY-<mm-dd>/{p.component1}",
    "N1 with a letter-masked year, its dash, a square-bracket token, a slash and the component":
        lambda p: f"{p.head1}YYYY-[mm-dd]/{p.component1}",
    "the word, a letter-masked year, its dash and an ellipsis, before a space":
        lambda p: f"see {p.word1}-YYYY-{ELLIPSIS} now",
    "the word's last four letters, a letter-masked year and month, their dash and an ellipsis":
        lambda p: f"{p.word1[-4:]}-YYYY-MM-{ELLIPSIS}\n",
    "the head, a letter-masked year, its dash and the truncation marker": lambda p: f"{p.head1}YYYY-{TRUNC} end",
    "the head, a letter-masked year and month, their dash and the truncation marker":
        lambda p: f"{p.head1}YYYY-MM-{TRUNC} end",
    "N1 with a letter-masked year and month and xx for the day": lambda p: f"{p.head1}YYYY-MM-xx/{p.component1}",
    "the dated parent with a letter-masked year and month and two stars for the day, at a text's end":
        lambda p: f"{p.head1}YYYY-MM-**",
    "N1 with its real year, a letter-masked month and xx for the day":
        lambda p: f"{p.head1}{p.date[:5]}MM-xx/{p.component1}",
    # A masked-digit character right after a whole-date token is one more digit of the date: per digit,
    # these cuts are eight characters.
    "the word's last three letters, the dash, three dots and a closing parenthesis": lambda p: f"{p.word1[-3:]}-...)",
    "the word's last five letters, the dash, a star and a closing parenthesis": lambda p: f"{p.word1[-5:]}-*)",
    "the word's last four letters, the dash, two stars and a closing parenthesis": lambda p: f"{p.word1[-4:]}-**)",
    "the word's last three letters, the dash, three stars and a closing parenthesis": lambda p: f"{p.word1[-3:]}-***)",
    "the word's last three letters, the dash, a three-character angle token and a closing parenthesis":
        lambda p: f"{p.word1[-3:]}-<d>)",
    "the word's last five letters, the dash, an x and a closing square bracket, in prose":
        lambda p: f"see {p.word1[-5:]}-x] now",
    # A token's own characters are the date's last digits before the component's slash, per digit,
    # when the token has two or more characters or a mark follows it; and the slash after a token of
    # two or more characters is where a word/date cut through the token's masked digits ends.
    "after the truncation marker: a letter-masked month, xx for the day, the slash and the component":
        lambda p: f"start{TRUNC}MM-xx/{p.component1}",
    "after the truncation marker: a letter-masked year and month, two stars for the day, the component":
        lambda p: f"start{TRUNC}YYYY-MM-**/{p.component1}",
    "a Unicode ellipsis, a letter-masked month, two question marks for the day and the component":
        lambda p: f"{ELLIPSIS}MM-??/{p.component1}",
    "a Unicode ellipsis, a letter-masked month, nn for the day, the slash and the component":
        lambda p: f"{ELLIPSIS}MM-nn/{p.component1}",
    "a letter-masked year and month, xx for the day, the slash and the component, in prose":
        lambda p: f"see YYYY-MM-xx/{p.component1} now",
    "the real year, a letter-masked month, xx for the day, the slash and the component, in prose":
        lambda p: f"see {p.date[:5]}MM-xx/{p.component1} now",
    "a letter-masked month, two stars for the day, the slash and the component":
        lambda p: f"MM-**/{p.component1}",
    "a letter, the dash, a star, a closing parenthesis, the slash and the component":
        lambda p: f"q-*)/{p.component1}",
    "the word, the dash and two stars, then a sibling file": lambda p: f"{p.word1}-**/plan.md",
    "the dated parent with two stars for its date, then a sibling file": lambda p: f"{p.head1}**/plan.md",
    # The pre-checks next to a token, one case per branch and per masked-year form. An own-dash cut
    # may find its room for eight characters in the date's next dash, five characters after the
    # token's, with only the word's last letter or two before the junction; and the year, or year and
    # month, that a walk six or nine characters back reads per digit may be masked with marks that
    # are not letters.
    "the word's last letter, the dash, a star, a mark, the year's last two digits, then month and day":
        lambda p: f"{p.word1[-1]}-*){p.date[2:]}",
    "the word's last two letters, the dash, a star, three dots, then the month and day with their dashes":
        lambda p: f"{p.word1[-2:]}-*...{p.date[4:]}",
    "the word's last letter, the dash, an angle token, a mark, then the month and day with their dashes":
        lambda p: f"{p.word1[-1]}-<d>){p.date[4:]}",
    "the word's last letter, the dash, an x, a mark, two letters, a dash and two letters, in prose":
        lambda p: f"see {p.word1[-1]}-x)ab-cd now",
    "a line of the word's last two letters, the dash, a star, a mark, two letters, a dash and two letters":
        lambda p: f"{p.word1[-2:]}-*]ab-cd\n",
    "N1 with a year of a letter, a dot and two letters, its dash, a star, the slash and the component":
        lambda p: f"{p.head1}Y.YY-*/{p.component1}",
    "the word, the dash, a year whose last digit is a letter, its dash and a Unicode ellipsis, in prose":
        lambda p: f"see {p.word1}-{p.date[:3]}Y-{ELLIPSIS} now",
    "the word, the dash, a year of four underscores, its dash and a Unicode ellipsis, in prose":
        lambda p: f"see {p.word1}-____-{ELLIPSIS} now",
    "N1 with a year and month of underscores, their dash, a star, the slash and the component":
        lambda p: f"{p.head1}____-__-*/{p.component1}",
    "the word, the dash, the real year, a month of a digit and an underscore, their dash, an ellipsis":
        lambda p: f"see {p.word1}-{p.date[:6]}_-{ELLIPSIS} now",
    # By design (the header's sibling sentence): a short bracketed token's last character is a masked
    # digit after its first that is a clean border.
    "the dated parent with a three-character angle token for its date, then a sibling file":
        lambda p: f"{p.head1}<d>/plan.md",
    # The length counts normalised characters: a sharp s folds to the parent word's double s, so this
    # cut is eight characters (seven as written); an escaped slash is one character.
    "N1 eight-character cut whose double s is a sharp s": lambda p: f"run {p.word1[-4:-2]}{SHARP_S}-{p.date[:3]} now",
    "N1 eight-character J2 cut whose slash is backslash-slash": lambda p: f"see {p.date[-2:]}{BACKSLASH}/{p.component1[:5]} now",
}
# The documented middle-truncation marker cutting N1 at every date offset: a head that ends there,
# and a tail that starts there. Its dots read both as masked digits and as a border.
FLAGGED.update({f"N1 head ending at date offset {k} before the truncation marker":
                (lambda p, k=k: f"{p.head1}{p.date[:k]}{TRUNC} end") for k in range(_DATE_LEN + 1)})
FLAGGED.update({f"N1 tail starting at date offset {k} after the truncation marker":
                (lambda p, k=k: f"start{TRUNC}{p.date[k:]}/{p.component1}") for k in range(_DATE_LEN)})

# ----- The forms that must NOT be flagged -------------------------------------------------------

NOT_FLAGGED: dict[str, Callable[[_Parts], str]] = {
    "the parent's word alone": lambda p: p.word1,
    "the parent's word in prose": lambda p: f"{p.word1} assessment complete",
    "the component's word alone": lambda p: p.component1,
    "the component's word in prose": lambda p: f"{p.component1} test passed",
    "N2's second word alone": lambda p: p.word2b,
    "N2's second word in prose": lambda p: f"{p.word2b}-based estimate",
    "N2's two words joined by an underscore": lambda p: f"test_{p.word2a}_{p.word2b}_links.py",
    "a review-gate file under the prefix": lambda p: f"{_F2[0]}{p.word2a}-gate.md",
    "a sibling path under the dated parent": lambda p: f"{p.parent1}/plan.md",
    "the date alone": lambda p: p.date,
    "accessed- then the date": lambda p: f"accessed-{p.date}",
    "the mask token EXCL-A": lambda p: "[EXCL-A]",
    "the mask token EXCL-B": lambda p: "[EXCL-B]",
    "the mask token EXCL-B-HALF": lambda p: "[EXCL-B-HALF]",
    "plain unrelated text": lambda p: "the quick brown fox jumps over the lazy dog",
    # A left end that borders a path character, and cuts under eight characters.
    "N1 cut whose left end borders a path character": lambda p: f"x{p.word1[3:]}-{p.date}",
    "a five-character cut across the N2 junction": lambda p: f"a {p.word2a[-2:]}-{p.word2b[:2]} b",
    # A '/' before, but the segment starts mid-word, so it is not the name.
    "a slash before a mid-segment look-alike of N2": lambda p: f"x/{p.word2a[1:]}-{p.word2b}",
    "a single dot before the dated name (a filename, not a path separator)": lambda p: f"foo.{p.parent_bare}",
    # Short N1 forms: a one-character token is rewritten to the ten-character date, but the cut counts
    # the token as written, so these stay under eight characters.
    "N1 short form: a glob in a find command": lambda p: f"find . -name '*{p.word1[-1:]}-*'",
    "N1 short form: an html break in a table cell": lambda p: f"| {p.word1[-2:]}-<br> |",
    "N1 short form: a tar flag before the component's first letter": lambda p: f"tar -x/{p.component1[:1]} ok",
    # An escaped slash counts as the one slash it stands for: these J2 cuts are seven and six
    # normalised characters (eight as written).
    "a seven-character J2 cut whose slash is backslash-slash": lambda p: f"see {p.date[-2:]}{BACKSLASH}/{p.component1[:4]} now",
    "a six-character J2 cut whose slash is %2F": lambda p: f"see {p.date[-2:]}%2F{p.component1[:3]} now",
    "a six-character J2 cut whose slash is %2f": lambda p: f"see {p.date[-2:]}%2f{p.component1[:3]} now",
    # Two dots in date position are a parent-directory step, never an elided date, even before the
    # whole component; and the parent before a sibling file with this bracketed token for its date
    # stays silent because the masked digits after its first are letters, no clean border (a short
    # bracketed token, with a mark after its first character, flags by design: the header's sibling
    # sentence).
    "two dots in date position, then a look-alike of the component": lambda p: f"see {p.head1}../{p.component1[:4]}x now",
    "two dots in date position, then the component": lambda p: f"see {p.head1}../{p.component1} now",
    "the dated parent with a bracketed token date, then a sibling file": lambda p: f"{p.head1}<date>/plan.md",
    # Eleven or more dots are no whole-date token: per digit, this cut is seven characters.
    "the word's last two letters, the dash and eleven dots, before a space": lambda p: f"see {p.word1[-2:]}-{'.' * 11} now",
    # The hook's documented reading (its header and _ELLIPSIS_TOKEN): a dot run followed by a Unicode
    # ellipsis is no whole-date token; per digit, this cut stays under eight characters.
    "the word's last four letters, the dash, five dots and a Unicode ellipsis":
        lambda p: f"{p.word1[-4:]}-.....{ELLIPSIS}",
}
NOT_FLAGGED.update({f"N1 short form: a one-character token after the word's last {j} letters":
                    (lambda p, j=j: f"run {p.word1[-j:]}-* now") for j in range(1, 6)})


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_result_is_flagged_on_post_tool_use(case: str, opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(_text(FLAGGED, case), opted_repo), project_dir=plain_kit), case,
             "PostToolUse")


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_error_is_flagged_on_post_tool_use_failure(case: str, opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _failure_event(_text(FLAGGED, case), opted_repo), project_dir=plain_kit,
                  event="PostToolUseFailure"), case, "PostToolUseFailure")


@pytest.mark.parametrize("case", list(NOT_FLAGGED))
def test_a_lookalike_result_is_not_flagged(case: str, opted_repo: Path, plain_kit: Path) -> None:
    _silent(_run(lambda: _post_event(_text(NOT_FLAGGED, case), opted_repo), project_dir=plain_kit), case)
    _silent(_run(lambda: _failure_event(_text(NOT_FLAGGED, case), opted_repo), project_dir=plain_kit,
                 event="PostToolUseFailure"), case)


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_form_nested_in_a_response_is_flagged(case: str, opted_repo: Path, plain_kit: Path) -> None:
    # The form as a value of an object in an array in an object.
    _flagged(_run(lambda: _post_event({"outer": [{"inner": {"value": _text(FLAGGED, case)}}]}, opted_repo),
                  project_dir=plain_kit), case, "PostToolUse")


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_form_as_a_nested_object_key_is_flagged(case: str, opted_repo: Path, plain_kit: Path) -> None:
    # The form as a key inside a nested object.
    _flagged(_run(lambda: _post_event({"outer": [{_text(FLAGGED, case): "v"}]}, opted_repo), project_dir=plain_kit),
             case, "PostToolUse")


def test_a_name_as_a_key_of_the_response_object_itself_is_flagged(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event({_Parts().n2: "v"}, opted_repo), project_dir=plain_kit),
             "a key of tool_response itself", "PostToolUse")


def test_a_name_in_a_failure_tool_response_is_flagged(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _failure_event("the command failed", opted_repo, tool_response={"stdout": _Parts().n1}),
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
    _silent(_run(lambda: _event_stdin(_Parts().n1, plain_repo, event), project_dir=plain_kit, event=event),
            f"opt-in off: {event}")


def test_a_named_result_is_flagged_in_a_linked_worktree(opted_worktree: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(_Parts().n1, opted_worktree), project_dir=plain_kit),
             "linked worktree, opted in", "PostToolUse")


def test_a_named_result_is_flagged_in_a_relative_gitdir_worktree(opted_worktree_relative: Path,
                                                                 plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(_Parts().n1, opted_worktree_relative), project_dir=plain_kit),
             "relative-gitdir worktree", "PostToolUse")


def test_the_marker_is_found_from_a_subdirectory(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(_Parts().n2, opted_repo / "sub"), project_dir=plain_kit),
             "cwd in a subdirectory of the opted-in repo", "PostToolUse")


def test_the_project_dir_is_the_fallback_when_cwd_is_absent(opted_kit: Path) -> None:
    _flagged(_run(lambda: json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                                      "tool_response": {"stdout": _Parts().n1}}), project_dir=opted_kit),
             "cwd absent: marker via CLAUDE_PROJECT_DIR", "PostToolUse")


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_via_project_dir_when_cwd_is_outside_any_repository(event: str, opted_kit: Path,
                                                                    no_repo_dir: Path) -> None:
    # A CODE RED session whose cwd has moved into a scratch folder is still guarded.
    _flagged(_run(lambda: _event_stdin(_Parts().n1, no_repo_dir, event), project_dir=opted_kit, event=event),
             f"cwd outside a repo, project dir opted in: {event}", event)


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_via_project_dir_when_cwd_is_another_unmarked_repository(event: str, plain_repo: Path,
                                                                         opted_kit: Path) -> None:
    # Either repository suffices: a cwd inside another, unmarked clone does not turn the guard off.
    _flagged(_run(lambda: _event_stdin(_Parts().n1, plain_repo, event), project_dir=opted_kit, event=event),
             f"cwd in an unmarked repo, project dir opted in: {event}", event)


def test_cwd_outside_a_repo_and_project_dir_not_opted_in_is_silent(plain_kit: Path, no_repo_dir: Path) -> None:
    _silent(_run(lambda: _post_event(_Parts().n1, no_repo_dir), project_dir=plain_kit),
            "cwd outside a repo, project dir not opted in")


@pytest.mark.parametrize("event", EVENTS)
def test_a_several_megabyte_benign_output_is_silent_and_in_time(event: str, opted_repo: Path,
                                                                plain_kit: Path) -> None:
    # ~5.5 MB, no name.
    _silent(_run(lambda: _event_stdin("The quarterly report is clean. " * 180_000, opted_repo, event),
                 project_dir=plain_kit, event=event), f"5MB benign: {event}")


@pytest.mark.parametrize("event", EVENTS)
def test_a_several_megabyte_hit_dense_output_is_silent_and_in_time(event: str, opted_repo: Path,
                                                                   plain_kit: Path) -> None:
    # ~5.5 MB with about 420,000 junction hits, none of them a cut, dashes throughout and one ASCII
    # '...': the per-hit walk must stay within the registered timeout. No whole-date token follows any
    # of its dashes, so this case runs no token path; the token-dense and costliest-class cases below
    # time those, on CPU time.
    _silent(_run(lambda: _event_stdin(_path_listing(), opted_repo, event), project_dir=plain_kit, event=event),
            f"5MB hit-dense listing: {event}")


# The token-dense and costliest-class cases' wall-clock hang stop, far above their runs' loaded wall
# time: it only ends a runaway run and is not the assertion.
TOKEN_HANG_STOP = 60


@pytest.mark.parametrize("with_form", [False, True], ids=["silent", "ending with a form"])
def test_a_token_dense_output_is_checked_within_its_registered_timeout(with_form: bool, opted_repo: Path,
                                                                        plain_kit: Path) -> None:
    # ~2 MB whose every line holds an ellipsis token (_token_listing): the token rewrite, the
    # elision-border check and the date/component window after each token run there, while the walks
    # six or nine characters back and at a token's own dash never get past their junction checks (the
    # costliest-class case below times those). Silent, the window searches must keep to their limits;
    # ending with a form, the hook must read to the last line. The bound is the registration's own
    # timeout, read from settings.json: a run needing more CPU than that is cancelled in use and fails
    # open, on any machine. The assertion bounds CPU time, which a loaded runner hardly inflates, not
    # wall time (test_wall_clock_bounds.py).
    run, cpu_seconds = _cpu_run(lambda: _post_event(_token_listing(with_form), opted_repo), project_dir=plain_kit,
                                hang_stop=TOKEN_HANG_STOP)
    if with_form:
        _flagged(run, "2MB token-dense listing ending with a form", "PostToolUse")
    else:
        _silent(run, "2MB token-dense listing")
    timeout = _registered_hook("PostToolUse")["timeout"]
    assert cpu_seconds < timeout, f"the hook used {cpu_seconds:.1f} s of CPU, over its registered {timeout} s timeout"


@pytest.mark.parametrize("second", [False, True], ids=["the first class, then lines with no junction",
                                                       "the second class alone"])
def test_the_costliest_token_classes_stay_within_the_size_the_docs_state(second: bool, opted_repo: Path,
                                                                          plain_kit: Path) -> None:
    # The walks next to a token six or nine characters back and at its own dash, at every token of a
    # costliest class (_costliest_listing): the first run times their junction checks and pre-checks
    # on the first class, then lines whose tokens fail every junction check with no junction after
    # them; the second run times their cut walks on the second class alone. Two bounds per run, both
    # from the registration's own timeout read from settings.json: the run's CPU (the hook uses at most
    # about a fifth of it), and the run's CPU per MB of its class times the size the hook and the
    # lesson state for the costliest class (the hook keeps 1.5x headroom with every CPU busy). The
    # assertions bound CPU time, which a loaded runner hardly inflates, not wall time
    # (test_wall_clock_bounds.py).
    run, cpu_seconds = _cpu_run(lambda: _post_event(_costliest_listing(second), opted_repo), project_dir=plain_kit,
                                hang_stop=TOKEN_HANG_STOP)
    _silent(run, "costliest-class listing")
    timeout = _registered_hook("PostToolUse")["timeout"]
    assert cpu_seconds < timeout, f"the hook used {cpu_seconds:.1f} s of CPU, over its registered {timeout} s timeout"
    per_mb, stated = cpu_seconds / (COSTLIEST_A2_MB if second else COSTLIEST_A1_MB), _stated_size_mb()
    assert per_mb * stated < timeout, (f"at {per_mb:.2f} s of CPU per MB, the {stated} MB the docs state for the "
                                       f"costliest class would take over the registered {timeout} s timeout")


def test_a_several_megabyte_output_with_a_name_is_flagged_and_in_time(opted_repo: Path, plain_kit: Path) -> None:
    _flagged(_run(lambda: _post_event(("x" * (5 << 20)) + " " + _Parts().n1, opted_repo), project_dir=plain_kit),
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


def test_no_case_id_is_longer_than_pytest_names_by_value() -> None:
    # pytest names a case whose id is over 100 characters by its argument name and index instead (its
    # default parametrize_long_str_id_strategy), so a longer case id would run under a number.
    longest = max(len(case) for case in (*FLAGGED, *NOT_FLAGGED, *_COPIES))
    assert longest <= 100, f"the longest case id is {longest} characters; pytest names ids over 100 by index"


def test_no_frame_holds_a_joined_name_while_the_names_are_built() -> None:
    # A fresh copy of the hook builds its names under sys.settrace, and the matcher reads the repr of
    # every argument and local of every frame the build creates -- the hook's own, and any library
    # frame it calls into -- at each call, line and return event, so a helper's arguments and a local
    # bound and deleted again are read too, not only what a frame holds at its end (the broken copies
    # below check pytest's reports). The report names frames, locals and events.
    spec = importlib.util.spec_from_file_location("excluded_dir_output_guard_traced", HOOK)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    held: set[str] = set()

    def trace(frame: types.FrameType, event: str, arg: object) -> Callable[..., object]:
        values = {**frame.f_locals, "<its return value>": arg} if event == "return" else frame.f_locals
        held.update(f"{frame.f_code.co_name}: {name} at a {event} event" for name, value in values.items()
                    if _hook.flagged(repr(value)))
        return trace

    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        fresh._names()
    finally:
        sys.settrace(previous)
    assert not held, f"frames held a joined name while the names were built: {sorted(held)}"


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

# The lines the broken copies change, and what each copy plants there.
_FLAG_BRANCH = "            if flagged(text):\n                return _emit(FLAGGED, event)\n"
_ECHOING_FLAG_BRANCH = ("            if flagged(text):\n                sys.stdout.write(text)\n"
                        "                sys.stderr.write(text)\n                return _emit(FLAGGED, event)\n")
_OPT_IN_CHECK = "    if not _opted_in(cwd):  # not opted in: silent, whatever the input\n"
_OPT_IN_IGNORED = "    if False:  # this copy ignores the opt-in\n"
_UNCHECKED_BRANCH = ("        if data is None:  # opted in but the input was not a readable JSON object\n"
                     "            return _emit(UNCHECKED, event)\n")
_ECHOING_UNCHECKED_BRANCH = ("        if data is None:  # opted in but the input was not a readable JSON object\n"
                             "            sys.stderr.write(_names()[0].canon)\n            return _emit(UNCHECKED, event)\n")
_MAIN = "def main() -> int:\n"
_SLEEPING_MAIN = "def main() -> int:\n    import time\n    time.sleep(3)\n"
# A raise after the last statement of a name's construction (_apply checks with ast that this line
# still ends _Name.__init__), so every local the constructor binds is set: on the first construction,
# the dated name's, and on the two-word name's alone. And one at the end of _names() once both names
# exist.
_INIT_END = '        self.seg_starts = frozenset({0} | {i + 1 for i, ch in enumerate(self.canon) if ch == "/"})\n'
_INIT_END_RAISING = _INIT_END + "        raise RuntimeError(\"a planted error at the end of a name's construction\")\n"
_TWO_WORD_INIT_END_RAISING = (_INIT_END + "        if date is None:\n"
                              "            raise RuntimeError(\"a planted error at the end of the two-word name's construction\")\n")
_NAMES_RETURN = "    return _Name(_F1, (4, 7)), _Name(_F2, None)\n"
_NAMES_RAISING = ("    names = _Name(_F1, (4, 7)), _Name(_F2, None)\n"
                  "    raise RuntimeError(\"a planted error at the end of the names' construction\")\n")
# A raise appended to the end of a module's source: on import it runs after every module-level
# statement (an import skips the hook's main block), so no module-level code can come after it.
_MODULE_RAISE = '\n\nraise RuntimeError("a planted module-level error")\n'
_ECHOING = ((_FLAG_BRANCH, _ECHOING_FLAG_BRANCH), (_OPT_IN_CHECK, _OPT_IN_IGNORED),
            (_UNCHECKED_BRANCH, _ECHOING_UNCHECKED_BRANCH))
_PIN = "test_a_broken_copy_prints_no_scanned_text"
_MESSAGES_TEST = "test_the_fixed_messages_are_distinct_and_say_what_they_mean"
_REGISTRATION_TEST = "test_the_hook_is_registered_on_both_events"
# The tests that never run the hook through its registration, so they pass in the copy with the
# registrations removed.
_UNREGISTERED_TESTS = (_MESSAGES_TEST, "test_no_case_id_is_longer_than_pytest_names_by_value",
                       "test_no_frame_holds_a_joined_name_while_the_names_are_built")
_FIRST_CASE = "test_a_named_result_is_flagged_on_post_tool_use[N1 alone]"
_FULL_TRACE_ECHO_CASES = (_FIRST_CASE, "test_opt_in_off_is_silent_even_for_a_named_result[PostToolUse]",
                          "test_unreadable_stdin_is_reported_unchecked_to_claude_when_opted_in[empty-PostToolUse]")


def _variant(flags: list[str], select: Callable[[Path], list[str]], *, edits: tuple = (), drop: tuple = (),
             timeout: int | None = None, hook_tail: str = "", test_tail: str = "") -> dict:
    """One broken copy: its pytest flags and what it runs, the hook edits it plants, the events whose
    guard registration it removes, the timeout it gives the PostToolUse registration, and what it
    appends to the end of the copied hook's and test's source."""
    return {"flags": flags, "select": select, "edits": edits, "drop": drop, "timeout": timeout,
            "hook_tail": hook_tail, "test_tail": test_tail}


def _first_case(test: Path) -> list[str]:
    return [f"{test}::{_FIRST_CASE}"]


# The broken copies. -l runs at -vv, so pytest prints every local whole, not cut to 240 characters.
_COPIES: dict[str, dict] = {
    # Every case that runs the hook fails on the missing registration, before any input exists, and
    # -l prints the locals of every frame shown, so no test function may bind scanned text to a name.
    "the registrations removed": _variant(
        ["-vv", "--tb=long", "-l"], lambda test: [str(test), "-k", f"not {_PIN}"], drop=EVENTS),
    # A hook that ignores the opt-in and echoes what it matched (and a name on an unchecked input):
    # the flag, silent and unchecked checks fail, and their frames hide the runs.
    "an echoing hook that ignores the opt-in": _variant(
        ["-vv", "--tb=long", "-l"],
        lambda test: [f"{test}::test_a_named_result_is_flagged_on_post_tool_use",
                      f"{test}::test_opt_in_off_is_silent_even_for_a_named_result",
                      f"{test}::test_unreadable_stdin_is_reported_unchecked_to_claude_when_opted_in"],
        edits=_ECHOING),
    # The same hook with frame hiding off: every check's frame shows its arguments and locals, so the
    # run it holds must print as its shape.
    "an echoing hook that ignores the opt-in, every frame shown": _variant(
        ["-vv", "--full-trace", "-l"], lambda test: [f"{test}::{case}" for case in _FULL_TRACE_ECHO_CASES],
        edits=_ECHOING),
    # A hook that sleeps past a one-second registered timeout: the standard library's frames, which
    # hold the input, must never reach the report. --full-trace turns pytest's frame hiding off and -l
    # prints every frame's locals, so `_run`'s own arguments and locals must hold no scanned text.
    "a hook that sleeps past its timeout": _variant(
        ["-vv", "--full-trace", "-l"], _first_case, edits=((_MAIN, _SLEEPING_MAIN),), timeout=1),
    # A raise after the last statement of a name's construction, the dated name's (built first). The
    # hook run reports that it could not check, and the case's failure message builds the run's shape,
    # which scans in-process and so raises there too: pytest's default report prints the innermost
    # frame's arguments (CI's flags), and -l every shown frame's locals, all bound by then, so neither
    # may hold a joined name.
    "a raise at the end of a name's construction, at the default flags": _variant(
        [], _first_case, edits=((_INIT_END, _INIT_END_RAISING),)),
    "a raise at the end of a name's construction, every local printed": _variant(
        ["-vv", "--tb=long", "-l"], _first_case, edits=((_INIT_END, _INIT_END_RAISING),)),
    # The same raise on the two-word name's construction alone, whose branch the first never takes.
    "a raise at the end of the two-word name's construction, every local printed": _variant(
        ["-vv", "--tb=long", "-l"], _first_case, edits=((_INIT_END, _TWO_WORD_INIT_END_RAISING),)),
    # A raise at the end of _names(), once both names exist: its locals, and with frame hiding off
    # every frame's arguments and locals, must hold no joined name.
    "a raise at the end of the names' construction, every local printed": _variant(
        ["-vv", "--tb=long", "-l"], _first_case, edits=((_NAMES_RETURN, _NAMES_RAISING),)),
    "a raise at the end of the names' construction, every frame shown": _variant(
        ["-vv", "--full-trace", "-l"], _first_case, edits=((_NAMES_RETURN, _NAMES_RAISING),)),
    # An error appended to the end of the test module's source: collection fails after every
    # module-level statement, and -l prints the module frame's locals, all of the module's globals.
    "a module-level error at the end of the test": _variant(
        ["-vv", "--tb=long", "-l"], lambda test: [str(test)], test_tail=_MODULE_RAISE),
    # An error appended to the end of the hook's source, raised while the test module imports it: -l
    # prints all of the hook's globals and the test module's so far.
    "a module-level error at the end of the hook": _variant(
        ["-vv", "--tb=long", "-l"], lambda test: [str(test)], hook_tail=_MODULE_RAISE),
}


def _guard_entries(settings: dict, event: str) -> list[dict]:
    return [entry for entry in settings["hooks"].get(event, [])
            if any("excluded_dir_output_guard.py" in hook.get("command", "") for hook in entry["hooks"])]


def _apply(source: str, edits: tuple, variant: str) -> str:
    for old, new in edits:
        assert source.count(old) == 1, f"{variant}: the source this pin edits changed; update the pin"
        if old == _INIT_END:
            assert _ends_name_init(source, old), f"{variant}: _Name.__init__ no longer ends at the plant; update the pin"
        source = source.replace(old, new)
    return source


def _ends_name_init(source: str, line: str) -> bool:
    """Whether `line` is the last statement of the hook's _Name.__init__, so a raise planted after it
    runs with every local the constructor binds."""
    tree = ast.parse(source)
    [name_class] = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "_Name"]
    [init] = [node for node in name_class.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"]
    return ast.get_source_segment(source, init.body[-1]) == line.strip()


def _nested_outcomes(junit: Path) -> dict[str, str]:
    """Each copied test's outcome from the copied run's JUnit XML, as one word: "passed", or its
    problem's kind -- "collection" (the module failed to load), "unpack" (the missing registration),
    "form" (a check whose report says a stream carries a form), "timeout" (_run's timeout), "planted"
    (an error a copy planted in the names' construction), else "other" -- never the problem's text.
    The file holds the whole report, so it is deleted once read."""
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
        elif problem.tag == "error" and message == "collection failure":
            kind = "collection"
        elif "ValueError: not enough values to unpack" in message:
            kind = "unpack"
        elif "carries a form True" in message:
            kind = "form"
        elif "did not finish within its registered" in message:
            kind = "timeout"
        elif "a planted error" in message:
            kind = "planted"
        else:
            kind = "other"
        outcomes[case.get("name")] = kind
    return outcomes


def _failed_as_intended(variant: str, outcomes: dict[str, str]) -> bool:
    """Whether the copied run failed the way its break should make it fail, so a copy whose hook
    cannot run at all (no python3 on PATH, say) does not pass the pin vacuously."""
    if variant == "the registrations removed":
        rest = {name: kind for name, kind in outcomes.items() if name not in (*_UNREGISTERED_TESTS, _REGISTRATION_TEST)}
        return (all(outcomes.get(name) == "passed" for name in _UNREGISTERED_TESTS)
                and outcomes.get(_REGISTRATION_TEST) == "other" and bool(rest) and set(rest.values()) == {"unpack"})
    if variant == "an echoing hook that ignores the opt-in":
        # Every flag case, both opt-in-off cases and the ten unreadable-input cases fail with the
        # streams carrying a form, which their reports state and do not print.
        return len(outcomes) == len(FLAGGED) + 2 + 10 and set(outcomes.values()) == {"form"}
    if variant == "an echoing hook that ignores the opt-in, every frame shown":
        return outcomes == {case: "form" for case in _FULL_TRACE_ECHO_CASES}
    if variant == "a hook that sleeps past its timeout":
        return outcomes == {_FIRST_CASE: "timeout"}
    if variant.startswith("a raise "):
        return outcomes == {_FIRST_CASE: "planted"}
    return list(outcomes.values()) == ["collection"]  # the two module-level errors


@pytest.mark.parametrize("variant", list(_COPIES))
def test_a_broken_copy_prints_no_scanned_text(variant: str, tmp_path: Path) -> None:
    # Copy the hook, the settings and this file under a scratch root, break the copy as the variant
    # says, run its cases there, and check the report with the hook's own matcher. The report is never
    # printed or kept, and the copied run must fail the intended way.
    copy = _COPIES[variant]
    root = tmp_path / "copy"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / "backend" / "tests" / "unit").mkdir(parents=True)
    (root / ".claude" / "hooks" / HOOK.name).write_text(
        _apply(HOOK.read_text(encoding="utf-8"), copy["edits"], variant) + copy["hook_tail"], encoding="utf-8")
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    for event in copy["drop"]:
        settings["hooks"][event] = [entry for entry in settings["hooks"][event]
                                    if entry not in _guard_entries(settings, event)]
    if copy["timeout"] is not None:
        [entry] = _guard_entries(settings, "PostToolUse")
        entry["hooks"][0]["timeout"] = copy["timeout"]
    (root / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    test_copy = root / "backend" / "tests" / "unit" / Path(__file__).name
    test_copy.write_text(Path(__file__).read_text(encoding="utf-8") + copy["test_tail"], encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *copy["select"](test_copy), "-p", "no:cacheprovider",
         "-p", "no:randomly", *copy["flags"], f"--basetemp={tmp_path / 'nested'}",
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
