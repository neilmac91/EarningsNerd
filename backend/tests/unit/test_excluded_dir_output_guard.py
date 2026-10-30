"""Gate for `.claude/hooks/excluded_dir_output_guard.py`, the PostToolUse / PostToolUseFailure hook
that flags a tool result naming either of the two directories a CODE RED program keeps out of its
agents' contexts (CODE RED closure 220; CLAUDE.md rule 12, AGENTS.md section 4).

Each case runs the hook the way `.claude/settings.json` registers it: the registered command,
through the shell (`/bin/sh -c`, as Claude Code runs it), on the event Claude Code sends, within the
registered timeout. CLAUDE_PROJECT_DIR points at the repository root so the command finds the hook;
opt-in is driven by the event's `cwd` (a temporary git repository with or without the marker), and,
for the cwd-absent and cwd-outside-a-repository cases, by a "kit" directory that holds the hook (a
symlink) and carries or omits the marker.

The hook is a detector: on a match it writes, on exit 0, a JSON object whose systemMessage (and,
when the event is known, hookSpecificOutput.additionalContext) carry one fixed factual message and
never the matched text; anything else exits 0 with no output; an opted-in but unreadable input
yields a different fixed "could not check" message as systemMessage alone. Every helper parses the
JSON and compares it to the exact expected payload, so a regression in the delivery channel, the
event name, or the no-echo rule turns the gate red.

The two names are never written whole here: every case string is built from the fragments below at
run time, so this source holds no name and no form the hook flags (proven by
test_neither_source_is_flagged). The parametrize id is the case id, never the scanned value, so a
failing case prints no name or cut form; the hook never echoes a match, so a captured stdout cannot
carry one either. The fixed messages are imported from the hook, not retyped (they hold no name).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SETTINGS = ROOT / ".claude" / "settings.json"
HOOK = ROOT / ".claude" / "hooks" / "excluded_dir_output_guard.py"
# -I -S: no PYTHON* variables, user site or site-packages reach the hook.
COMMAND = 'python3 -I -S "$CLAUDE_PROJECT_DIR/.claude/hooks/excluded_dir_output_guard.py" || exit 1'
EVENTS = ("PostToolUse", "PostToolUseFailure")
MARKER = "code-red-excluded-dir-guard"

# The hook's two fixed messages, imported (they contain no directory name) so the gate pins them
# exactly without retyping. Importing runs no __main__ block and reads no stdin.
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
PREFIX2 = _F2[0]
WORD2A = _F2[1] + _F2[2]                # N2's first word
WORD2B = _F2[4] + _F2[5]                # N2's second word

BACKSLASH = chr(92)


def _registered(event: str) -> list[dict]:
    """The entries of `event` in .claude/settings.json that run the guard."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return [entry for entry in settings["hooks"].get(event, [])
            if any("excluded_dir_output_guard.py" in hook.get("command", "") for hook in entry["hooks"])]


def _run(stdin: str, project_dir: Path = ROOT, event: str = "PostToolUse") -> subprocess.CompletedProcess[str]:
    """Run the registered command (same text for both events) as Claude Code does (`/bin/sh -c`),
    with CLAUDE_PROJECT_DIR set so the command locates the hook, within the registered timeout."""
    [entry] = _registered(event)
    [hook] = entry["hooks"]
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)}
    return subprocess.run(["sh", "-c", hook["command"]], input=stdin, capture_output=True, text=True,
                          env=env, timeout=hook["timeout"])


def _post_event(tool_response: object, cwd: Path) -> str:
    return json.dumps({
        "session_id": "s", "transcript_path": "/dev/null", "cwd": str(cwd), "permission_mode": "default",
        "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"},
        "tool_response": tool_response, "tool_use_id": "toolu_1",
    })


def _failure_event(error: object, cwd: Path, tool_response: object = None) -> str:
    payload = {
        "session_id": "s", "cwd": str(cwd), "hook_event_name": "PostToolUseFailure", "tool_name": "Bash",
        "tool_input": {"command": "ls"}, "error": error, "is_interrupt": False, "duration_ms": 1,
    }
    if tool_response is not None:
        payload["tool_response"] = tool_response
    return json.dumps(payload)


def _event_stdin(form: object, cwd: Path, event: str) -> str:
    return _post_event(form, cwd) if event == "PostToolUse" else _failure_event(form, cwd)


def _json(stdout: str) -> object:
    try:
        return json.loads(stdout)
    except ValueError:
        return None


def _flagged(proc: subprocess.CompletedProcess[str], case: str, event: str) -> None:
    assert proc.returncode == 0, case
    assert _json(proc.stdout) == {
        "systemMessage": FLAGGED_MSG,
        "hookSpecificOutput": {"hookEventName": event, "additionalContext": FLAGGED_MSG},
    }, case


def _unchecked(proc: subprocess.CompletedProcess[str], case: str) -> None:
    # An unreadable input has no event name, so the hook emits systemMessage alone (accepted on
    # either event), with no hookSpecificOutput.
    assert proc.returncode == 0, case
    assert _json(proc.stdout) == {"systemMessage": UNCHECKED_MSG}, case


def _silent(proc: subprocess.CompletedProcess[str], case: str) -> None:
    assert (proc.returncode, proc.stdout) == (0, ""), case


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
    """A main checkout with no marker: the hook must stay silent."""
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


def _kit(tmp_path: Path, name: str, opted: bool) -> Path:
    """A project directory that holds the hook (a symlink) and is opted in or not, so a cwd-absent
    or cwd-outside-a-repository event resolves the marker through CLAUDE_PROJECT_DIR while the command
    still finds the hook."""
    kit = tmp_path / name
    (kit / ".claude" / "hooks").mkdir(parents=True)
    (kit / ".git").mkdir()
    (kit / ".claude" / "hooks" / "excluded_dir_output_guard.py").symlink_to(HOOK)
    if opted:
        (kit / ".git" / MARKER).write_text("", encoding="utf-8")
    return kit


@pytest.fixture
def opted_kit(tmp_path: Path) -> Path:
    return _kit(tmp_path, "kit_on", opted=True)


@pytest.fixture
def plain_kit(tmp_path: Path) -> Path:
    return _kit(tmp_path, "kit_off", opted=False)


@pytest.fixture
def no_repo_dir(tmp_path: Path) -> Path:
    """A directory with no .git at or above it within the temp tree (a scratch folder)."""
    scratch = tmp_path / "scratch" / "deep"
    scratch.mkdir(parents=True)
    return scratch


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
    # Finding 14: a cut that holds only J2 (starts inside the date), plain and with an escaped slash.
    "N1 J2 only: date then component": f"see {DATE}/{COMPONENT1} now",
    "N1 J2 only: date then an escaped slash and component": f"see {DATE}{BACKSLASH}/{COMPONENT1} now",
    # Finding 1: the whole date replaced by one token, inside cut forms (not only the full name).
    "N1 parent cut after a token date, bracketed": f"found at {PARENT1.replace(DATE, '<date>')}",
    "N1 cut after a token date and slash, star": f"dir {PARENT1.replace(DATE, '*')}/",
    "N1 token date, truncated into component": f"{PARENT1.replace(DATE, '[date]')}/{COMPONENT1[:4]}\n",
    "N1 three into word, token date": f"path {WORD1[3:]}-{'{date}'} here",
    "N1 parent listing, token date as ten x": f"drwx 2 root {WORD1}-{'x' * 10}\n",
    "N1 full name, token date before component": f"see {PREFIX1}{WORD1}-<date>/{COMPONENT1} ok",
    # Finding 4: cuts bordered by '/' (the name under another parent) or an ASCII ellipsis.
    "N1 under another parent, git --stat abbreviation": f" .../{WORD1}-{DATE}/{COMPONENT1}/main.py | 3 +++",
    "N2 under another parent, git --stat abbreviation": f" .../{WORD2A}-{WORD2B}/notes.md | 2 +-",
    "N1 find-style ./ at a line start": f"./{WORD1}-{DATE}\n",
    "N1 ../ before the name without its prefix": f"../{WORD1}-{DATE}/{COMPONENT1}",
    "N2 x/ before the name without its prefix": f"x/{WORD2A}-{WORD2B}",
    "N1 cut ending at an ASCII ellipsis": f"{PARENT1}/{COMPONENT1[:4]}... [12 characters truncated] ...",
}

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
    # Finding 15: a left end that borders a path character, and a cut under eight characters.
    "N1 cut whose left end borders a path character": f"x{WORD1[3:]}-{DATE}",
    "a five-character cut across the N2 junction": f"a {WORD2A[-2:]}-{WORD2B[:2]} b",
    # Finding 4 counterpart: a '/' before, but the segment starts mid-word, so it is not the name.
    "a slash before a mid-segment look-alike of N2": f"x/{WORD2A[1:]}-{WORD2B}",
    "a single dot before the dated name (a filename, not a path separator)": f"foo.{WORD1}-{DATE}",
}

# A couple of representative forms for the whole-FLAGGED nested/key sweep plus two singled-out shapes.
_NESTED_KEY_SENTINEL = {"outer": [{N1: "value under a flagged key in a nested object"}]}


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_result_is_flagged_on_post_tool_use(case: str, opted_repo: Path) -> None:
    _flagged(_run(_post_event(FLAGGED[case], opted_repo)), case, "PostToolUse")


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_error_is_flagged_on_post_tool_use_failure(case: str, opted_repo: Path) -> None:
    _flagged(_run(_failure_event(FLAGGED[case], opted_repo), event="PostToolUseFailure"),
             case, "PostToolUseFailure")


@pytest.mark.parametrize("case", list(NOT_FLAGGED))
def test_a_lookalike_result_is_not_flagged(case: str, opted_repo: Path) -> None:
    _silent(_run(_post_event(NOT_FLAGGED[case], opted_repo)), case)
    _silent(_run(_failure_event(NOT_FLAGGED[case], opted_repo), event="PostToolUseFailure"), case)


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_form_nested_in_a_response_is_flagged(case: str, opted_repo: Path) -> None:
    response = {"outer": [{"inner": {"value": FLAGGED[case]}}]}  # an object in an array in an object
    _flagged(_run(_post_event(response, opted_repo)), case, "PostToolUse")


@pytest.mark.parametrize("case", list(FLAGGED))
def test_a_named_form_as_a_nested_object_key_is_flagged(case: str, opted_repo: Path) -> None:
    response = {"outer": [{FLAGGED[case]: "v"}]}  # the form as a key inside a nested object
    _flagged(_run(_post_event(response, opted_repo)), case, "PostToolUse")


def test_a_name_as_a_top_level_object_key_is_flagged(opted_repo: Path) -> None:
    _flagged(_run(_post_event(_NESTED_KEY_SENTINEL, opted_repo)), "nested object key", "PostToolUse")


def test_a_name_in_a_failure_tool_response_is_flagged(opted_repo: Path) -> None:
    event = _failure_event("the command failed", opted_repo, tool_response={"stdout": N1})
    _flagged(_run(event, event="PostToolUseFailure"), "name in a failure's tool_response", "PostToolUseFailure")


@pytest.mark.parametrize("event", EVENTS)
def test_a_name_only_in_tool_input_is_not_scanned(event: str, opted_repo: Path) -> None:
    # The CODE RED git commands carry the names as exclusion pathspecs; scanning inputs would flag
    # every such command. tool_input is never scanned, on either event.
    command = f"git status -- . ':!{N1}/' ':!{N2}/'"
    payload = {
        "session_id": "s", "cwd": str(opted_repo), "hook_event_name": event, "tool_name": "Bash",
        "tool_input": {"command": command}, "tool_use_id": "t",
    }
    if event == "PostToolUse":
        payload["tool_response"] = {"stdout": "nothing to commit", "stderr": ""}
    else:
        payload["error"] = "exit status 1"
        payload["tool_response"] = {"stdout": "", "stderr": "nothing to commit"}
    _silent(_run(json.dumps(payload), event=event), f"name only in tool_input: {event}")


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_off_is_silent_even_for_a_named_result(event: str, plain_repo: Path) -> None:
    _silent(_run(_event_stdin(N1, plain_repo, event), event=event), f"opt-in off: {event}")


def test_a_named_result_is_flagged_in_a_linked_worktree(opted_worktree: Path) -> None:
    _flagged(_run(_post_event(N1, opted_worktree)), "linked worktree, opted in", "PostToolUse")


def test_a_named_result_is_flagged_in_a_relative_gitdir_worktree(opted_worktree_relative: Path) -> None:
    _flagged(_run(_post_event(N1, opted_worktree_relative)), "relative-gitdir worktree", "PostToolUse")


def test_the_marker_is_found_from_a_subdirectory(opted_repo: Path) -> None:
    sub = opted_repo / "sub"
    _flagged(_run(_post_event(N2, sub)), "cwd in a subdirectory of the opted-in repo", "PostToolUse")


def test_the_project_dir_env_is_the_fallback_when_cwd_is_absent(opted_kit: Path) -> None:
    stdin = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                        "tool_response": {"stdout": N1}})
    _flagged(_run(stdin, project_dir=opted_kit), "cwd absent: marker via CLAUDE_PROJECT_DIR", "PostToolUse")


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_via_project_dir_when_cwd_is_outside_any_repository(event: str, opted_kit: Path,
                                                                    no_repo_dir: Path) -> None:
    # A CODE RED session whose cwd has moved into a scratch folder is still guarded: the project
    # clone carries the marker. (Finding 16 / 2.)
    _flagged(_run(_event_stdin(N1, no_repo_dir, event), project_dir=opted_kit, event=event),
             f"cwd outside a repo, project dir opted in: {event}", event)


def test_cwd_outside_a_repo_and_project_dir_not_opted_in_is_silent(plain_kit: Path, no_repo_dir: Path) -> None:
    _silent(_run(_post_event(N1, no_repo_dir), project_dir=plain_kit), "cwd outside a repo, project dir not opted in")


@pytest.mark.parametrize("event", EVENTS)
def test_a_several_megabyte_benign_output_is_silent_and_in_time(event: str, opted_repo: Path) -> None:
    big = "The quarterly report is clean. " * 180_000  # ~5.5 MB, no name
    _silent(_run(_event_stdin(big, opted_repo, event), event=event), f"5MB benign: {event}")


def test_a_several_megabyte_output_with_a_name_is_flagged_and_in_time(opted_repo: Path) -> None:
    big = ("x" * (5 << 20)) + " " + N1
    _flagged(_run(_post_event(big, opted_repo)), "5MB with a name at the end", "PostToolUse")


@pytest.mark.parametrize("stdin", ["", "not json at all", "[]", "123", "{"], ids=[
    "empty", "non-JSON text", "a list", "a scalar", "a truncated object"])
def test_unreadable_stdin_is_reported_unchecked_when_opted_in(stdin: str, opted_kit: Path) -> None:
    _unchecked(_run(stdin, project_dir=opted_kit), f"unreadable stdin opted in: {stdin!r}")


def test_a_json_parser_overflow_is_reported_unchecked_when_opted_in(opted_kit: Path) -> None:
    # Deep nesting makes json.loads raise RecursionError, not ValueError; an opted-in session must
    # still get the could-not-check message, never silence. (Findings 5, 7, 13.)
    stdin = '{"tool_response": ' + "[" * 100_000 + "]" * 100_000 + "}"
    _unchecked(_run(stdin, project_dir=opted_kit), "json parser overflow opted in")


def test_unreadable_stdin_is_silent_when_opt_in_off(plain_kit: Path) -> None:
    _silent(_run("not json at all", project_dir=plain_kit), "unreadable stdin, opt-in off")


def test_neither_source_is_flagged(opted_repo: Path) -> None:
    # R7 in miniature: the hook run on its own source and this test's source flags nothing.
    for label, path in (("hook source", HOOK), ("test source", Path(__file__))):
        text = path.read_text(encoding="utf-8")
        _silent(_run(_post_event({"stdout": text}, opted_repo)), f"{label} is not flagged")


def test_the_hook_is_registered_on_both_events() -> None:
    expected = [{"matcher": "*", "hooks": [{"type": "command", "command": COMMAND, "timeout": 10}]}]
    for event in EVENTS:
        assert _registered(event) == expected, event
    assert HOOK.is_file()
    assert "disableAllHooks" not in json.loads(SETTINGS.read_text(encoding="utf-8"))
