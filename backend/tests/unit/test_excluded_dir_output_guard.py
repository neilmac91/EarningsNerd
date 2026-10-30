"""Gate for `.claude/hooks/excluded_dir_output_guard.py`, the PostToolUse / PostToolUseFailure hook
that flags a tool result naming either of the two directories a CODE RED program keeps out of its
agents' contexts (CODE RED closure 220; CLAUDE.md rule 12, AGENTS.md section 4).

Each case runs the hook the way `.claude/settings.json` registers it: the registered command,
through the shell (`/bin/sh -c`, as Claude Code runs it), on the event Claude Code sends, within the
registered timeout. CLAUDE_PROJECT_DIR points at the repository root so the command finds the hook;
opt-in is driven by the event's `cwd` (a temporary git repository with or without the marker). The
cwd-absent cases (the fallback to CLAUDE_PROJECT_DIR, and unreadable stdin) use a "kit" directory
that both holds the hook (a symlink) and carries or omits the marker.

The hook is a detector: on a match it writes, on exit 0, a JSON object whose additionalContext and
systemMessage carry one fixed factual message and never the matched text; anything else exits 0 with
no output; opted in but unreadable input yields a different fixed "could not check" message.

The two names are never written whole here: every case string is built from the fragments below at
run time, so this source holds no name and no form the hook flags (proven by
test_neither_source_is_flagged). Assertions name a case id, never a scanned text; the hook never
echoes a match, so a captured stdout cannot carry one either.
"""
from __future__ import annotations

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

# Fragments of the two names, joined only at run time (as the hook keeps them). N1 is the dated name
# <prefix><word>-<date>/<component>; N2 is the two-word name <prefix><word>-<word>.
_F1 = ("tasks/", "readi", "ness", "-", "2026", "-09-", "21", "/", "accep", "tance")
_F2 = ("tasks/", "rev", "iew", "-", "evi", "dence")
N1 = "".join(_F1)
N2 = "".join(_F2)
WORD1 = _F1[1] + _F1[2]                 # the dated parent's word
DATE = _F1[4] + _F1[5] + _F1[6]         # the parent's date
COMPONENT1 = _F1[8] + _F1[9]            # the last path component
PARENT1 = _F1[0] + WORD1 + "-" + DATE   # the dated parent directory, with its prefix
PARENT_BARE = WORD1 + "-" + DATE        # the dated parent directory's own name (as a listing prints it)
WORD2A = _F2[1] + _F2[2]                # N2's first word
WORD2B = _F2[4] + _F2[5]                # N2's second word

BACKSLASH = chr(92)

# Distinctive substrings of the hook's two fixed messages; neither repeats a directory name.
FLAG_MARK = "a form of a directory name that CODE RED"
UNCHECKED_MARK = "could not check this tool result"


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


def _flagged(proc: subprocess.CompletedProcess[str], case: str) -> None:
    assert proc.returncode == 0, case
    assert FLAG_MARK in proc.stdout, case
    assert UNCHECKED_MARK not in proc.stdout, case


def _silent(proc: subprocess.CompletedProcess[str], case: str) -> None:
    assert (proc.returncode, proc.stdout) == (0, ""), case


def _unchecked(proc: subprocess.CompletedProcess[str], case: str) -> None:
    assert proc.returncode == 0, case
    assert UNCHECKED_MARK in proc.stdout, case
    assert FLAG_MARK not in proc.stdout, case


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
    """A linked worktree: its `.git` is a file naming a gitdir whose `commondir` names the common
    directory, where the marker sits."""
    common = tmp_path / "wtrepo" / ".git"
    git_dir = common / "worktrees" / "wt"
    git_dir.mkdir(parents=True)
    (git_dir / "commondir").write_text("../..\n", encoding="utf-8")
    (common / MARKER).write_text("", encoding="utf-8")
    checkout = tmp_path / "wt"
    checkout.mkdir()
    (checkout / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    return checkout


def _kit(tmp_path: Path, name: str, opted: bool) -> Path:
    """A project directory that holds the hook (a symlink) and is opted in or not, so a cwd-absent
    event resolves the marker through CLAUDE_PROJECT_DIR while the command still finds the hook."""
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
    "N1 date with one digit masked": N1.replace(DATE, DATE[:-1] + "#"),
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
}

_NESTED = {"outer": [{"inner": {"value": N1}}]}  # an object in an array in an object
_AS_KEY = {N2: "a value under a flagged key"}

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
}


@pytest.mark.parametrize("response", FLAGGED.values(), ids=FLAGGED.keys())
def test_a_named_result_is_flagged_on_post_tool_use(response: str, opted_repo: Path) -> None:
    case = next(name for name, value in FLAGGED.items() if value == response)
    _flagged(_run(_post_event(response, opted_repo)), case)


@pytest.mark.parametrize("response", FLAGGED.values(), ids=FLAGGED.keys())
def test_a_named_error_is_flagged_on_post_tool_use_failure(response: str, opted_repo: Path) -> None:
    case = next(name for name, value in FLAGGED.items() if value == response)
    _flagged(_run(_failure_event(response, opted_repo), event="PostToolUseFailure"), case)


@pytest.mark.parametrize("response", NOT_FLAGGED.values(), ids=NOT_FLAGGED.keys())
def test_a_lookalike_result_is_not_flagged(response: str, opted_repo: Path) -> None:
    case = next(name for name, value in NOT_FLAGGED.items() if value == response)
    _silent(_run(_post_event(response, opted_repo)), case)
    _silent(_run(_failure_event(response, opted_repo), event="PostToolUseFailure"), case)


def test_a_name_nested_in_a_response_is_flagged(opted_repo: Path) -> None:
    _flagged(_run(_post_event(_NESTED, opted_repo)), "object in an array in an object")


def test_a_name_as_an_object_key_is_flagged(opted_repo: Path) -> None:
    _flagged(_run(_post_event(_AS_KEY, opted_repo)), "name as an object key")


def test_a_name_in_a_failure_tool_response_is_flagged(opted_repo: Path) -> None:
    event = _failure_event("the command failed", opted_repo, tool_response={"stdout": N1})
    _flagged(_run(event, event="PostToolUseFailure"), "name in a failure's tool_response")


def test_a_name_only_in_tool_input_is_not_scanned(opted_repo: Path) -> None:
    # The CODE RED git commands carry the names as exclusion pathspecs; scanning inputs would flag
    # every such command. tool_input is never scanned.
    event = json.dumps({
        "session_id": "s", "cwd": str(opted_repo), "hook_event_name": "PostToolUse", "tool_name": "Bash",
        "tool_input": {"command": f"git status -- . ':!{N1}/' ':!{N2}/'"},
        "tool_response": {"stdout": "nothing to commit", "stderr": ""}, "tool_use_id": "t",
    })
    _silent(_run(event), "name only in tool_input")


@pytest.mark.parametrize("event", EVENTS)
def test_opt_in_off_is_silent_even_for_a_named_result(event: str, plain_repo: Path) -> None:
    stdin = _post_event(N1, plain_repo) if event == "PostToolUse" else _failure_event(N1, plain_repo)
    _silent(_run(stdin, event=event), f"opt-in off: {event}")


def test_a_named_result_is_flagged_in_a_linked_worktree(opted_worktree: Path) -> None:
    _flagged(_run(_post_event(N1, opted_worktree)), "linked worktree, opted in")


def test_the_marker_is_found_from_a_subdirectory(opted_repo: Path) -> None:
    sub = opted_repo / "sub"
    _flagged(_run(_post_event(N2, sub)), "cwd in a subdirectory of the opted-in repo")


def test_the_project_dir_env_is_the_fallback_when_cwd_is_absent(opted_kit: Path) -> None:
    stdin = json.dumps({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                        "tool_response": {"stdout": N1}})
    _flagged(_run(stdin, project_dir=opted_kit), "cwd absent: marker found via CLAUDE_PROJECT_DIR")


@pytest.mark.parametrize("event", EVENTS)
def test_a_several_megabyte_benign_output_is_silent_and_in_time(event: str, opted_repo: Path) -> None:
    big = "The quarterly report is clean. " * 180_000  # ~5.5 MB, no name
    stdin = _post_event(big, opted_repo) if event == "PostToolUse" else _failure_event(big, opted_repo)
    _silent(_run(stdin, event=event), f"5MB benign: {event}")


def test_a_several_megabyte_output_with_a_name_is_flagged_and_in_time(opted_repo: Path) -> None:
    big = ("x" * (5 << 20)) + " " + N1
    _flagged(_run(_post_event(big, opted_repo)), "5MB with a name at the end")


@pytest.mark.parametrize("stdin", ["", "not json at all", "[]", "123", "{"], ids=[
    "empty", "non-JSON text", "a list", "a scalar", "a truncated object"])
def test_unreadable_stdin_is_reported_unchecked_when_opted_in(stdin: str, opted_kit: Path) -> None:
    _unchecked(_run(stdin, project_dir=opted_kit), f"unreadable stdin opted in: {stdin!r}")


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
