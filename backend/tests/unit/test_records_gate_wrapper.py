"""Gate for ``tasks/code-red-20261004/runtime/tools/records-gate.sh`` (lessons/ops-a-piped-gate-does-not-gate.md).

Two commit chains failed to gate a CODE RED records commit: one piped the records gate (``pytest … | tail -1``, so ``tail``'s
status decided; chief defect 10) and one relied on ``set -e``, which the chief's tool shell suppresses, so a failed
``ruff format --check`` did not stop the commit (chief defect 11; DECISIONS-21). A third gap (chief defect 12) was procedural:
pushes that changed ``backend/tests/`` were not preceded by the repository's full backend gate. The wrapper is the supported way
to verify a records commit: every step runs unpiped with its exit status captured explicitly, the ``backend`` scope adds the full
backend gate (``ruff check .``, ``bandit -r app -ll``, ``python -m pytest``) and is chosen automatically when the working tree
or the commits since main change anything under ``backend/`` (failing closed when no base exists to compare with), and the
wrapper exits 0 only when every step passed. This test pins that form and proves
it by mutation in temporary repositories shaped like this one: a failing pytest step, a failing non-pytest step (an unformatted
file) and a failing full-gate step (a planted Bandit finding) each fail the wrapper; clean trees pass it in both scopes. Each
proof runs the wrapper in a subprocess with the running interpreter; nothing in the real tree is touched.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WRAPPER = REPO_ROOT / "tasks" / "code-red-20261004" / "runtime" / "tools" / "records-gate.sh"

CLEAN_PROBE = "def test_probe() -> None:\n    assert True\n"
FAILING_PROBE = 'def test_probe() -> None:\n    raise AssertionError("planted failure")\n'
UNFORMATTED_PROBE = "def test_probe( ) -> None:\n    assert True\n"
BANDIT_FINDING = (
    "def run(code: str) -> None:\n    exec(code)  # planted: Bandit B102 (medium severity), reported under -ll\n"
)

RECORDS_STEPS = ["records gate", "ruff check", "ruff format"]
BACKEND_STEPS = [*RECORDS_STEPS, "ruff check (backend)", "bandit", "pytest (backend)"]
STEP_MARKERS = (
    '-m pytest "$test_path" -q -p no:cacheprovider',
    "-m ruff check $lint_paths",
    "-m ruff format --check $lint_paths",
    "-m ruff check .",
    "-m bandit -r app -ll",
    "-m pytest -q -p no:cacheprovider",
)


def _is_unpiped_with_status_captured(line: str) -> bool:
    """The rule the wrapper's step runner must satisfy: no pipe (``||`` captures the status and is not one), and ``|| status=$?``."""
    return "|" not in line.replace("||", "") and re.search(r"\|\| status=\$\?", line) is not None


def _lines_containing(text: str, needle: str) -> list[str]:
    """Non-comment lines of the wrapper containing ``needle`` (the header comment quotes the rule it describes)."""
    return [line.strip() for line in text.splitlines() if needle in line and not line.lstrip().startswith("#")]


def _ok_steps(stdout: str) -> list[str]:
    return [
        line.split(":")[1].strip().removeprefix("ok").strip()
        for line in stdout.splitlines()
        if line.startswith("records-gate: ok    ")
    ]


def test_wrapper_form_every_step_unpiped_with_its_status_captured() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert WRAPPER.stat().st_mode & stat.S_IXUSR, "records-gate.sh must be executable"
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text, "the wrapper must run in strict mode with pipefail"
    runner_lines = _lines_containing(text, "|| status=$?")
    assert len(runner_lines) == 1, f"exactly one status capture expected (the step runner), found {runner_lines}"
    assert _is_unpiped_with_status_captured(runner_lines[0]), runner_lines[0]
    for marker in STEP_MARKERS:
        step_lines = _lines_containing(text, marker)
        assert len(step_lines) == 1, f"exactly one {marker!r} step expected, found {step_lines}"
        assert step_lines[0].startswith("run_step "), f"{marker!r} must run through the step runner: {step_lines[0]!r}"
        assert "|" not in step_lines[0], f"a step is never piped: {step_lines[0]!r}"
    assert re.search(r'^exit "\$failed"\s*$', text, re.MULTILINE), "the wrapper must exit non-zero when any step failed"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603, S607 - git on a throwaway repository under tmp_path
        ["git", "-C", str(repo), "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", *args],
        check=True,
        capture_output=True,
    )


def _run_wrapper(
    tmp_path: Path,
    probe_body: str,
    *,
    scope: str | None = "records",
    app_body: str | None = None,
    git: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the wrapper on a temporary repository.

    ``git`` lays the repository out for the auto-scope proofs: ``"untracked-change"`` (initialised, nothing committed, so the
    backend files are untracked, with ``status.showUntrackedFiles=no`` set to prove the read does not depend on it), ``"committed-change"`` (a ``main`` with the test only, then a branch whose commit
    adds ``backend/app``; the working tree is clean), ``"no-base"`` (one branch named ``work`` holding everything; no ``main``),
    ``"on-local-main"`` (``main`` itself holds everything, no ``origin/main``; the working tree is clean).
    """
    repo = tmp_path / "repo"
    tests = repo / "backend" / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_probe.py").write_text(probe_body, encoding="utf-8")
    # The repository's own lint selection (backend/ruff.toml), so the backend lint step is deterministic here too.
    (repo / "backend" / "ruff.toml").write_text('[lint]\nselect = ["E4", "E7", "E9", "F"]\n', encoding="utf-8")
    if app_body is not None:
        app = repo / "backend" / "app"
        app.mkdir()
        (app / "__init__.py").write_text("", encoding="utf-8")
        (app / "planted.py").write_text(app_body, encoding="utf-8")
    if git == "untracked-change":
        _git(repo, "init", "-q")
        # A configuration that hides untracked files from a plain `git status`; the wrapper must see them regardless.
        _git(repo, "config", "status.showUntrackedFiles", "no")
    elif git == "committed-change":
        _git(repo, "init", "-q")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(repo, "add", "backend/tests", "backend/ruff.toml")
        _git(repo, "commit", "-q", "-m", "base")
        _git(repo, "checkout", "-q", "-b", "feature")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "a backend change")
    elif git == "no-base":
        _git(repo, "init", "-q")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/work")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "everything")
    elif git == "on-local-main":
        _git(repo, "init", "-q")
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "a backend change committed on main")
    else:
        assert git is None, git
    env = {
        **os.environ,
        "RECORDS_GATE_PYTHON": sys.executable,
        "RECORDS_GATE_TEST": "tests/unit/test_probe.py",
        "RECORDS_GATE_LINT_PATHS": "tests/unit/test_probe.py",
        # Keep the inner pytest sessions hermetic and independent of this repository's pytest.ini and plugins' autoload.
        "PYTEST_ADDOPTS": "-p no:randomly -p no:xdist",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    env.pop("RECORDS_GATE_SCOPE", None)
    if scope is not None:
        env["RECORDS_GATE_SCOPE"] = scope
    return subprocess.run(  # noqa: S603 - the wrapper under test, with controlled arguments
        [str(WRAPPER), str(repo)], capture_output=True, text=True, env=env, timeout=300, check=False
    )


def test_wrapper_fails_when_the_pytest_step_fails(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, FAILING_PROBE)
    assert result.returncode != 0, (
        f"a failing gate must fail the wrapper; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "records-gate: FAIL  records gate (exit 1)" in result.stderr, result.stderr
    assert _ok_steps(result.stdout) == ["ruff check", "ruff format"], result.stdout
    assert result.stderr.rstrip().endswith("records-gate: FAILED"), result.stderr


def test_wrapper_fails_when_a_non_pytest_step_fails(tmp_path: Path) -> None:
    """Chief defect 11's shape: the tests pass but a formatting check fails; the wrapper must still fail."""
    result = _run_wrapper(tmp_path, UNFORMATTED_PROBE)
    assert result.returncode != 0, (
        f"a failing non-pytest step must fail the wrapper; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert _ok_steps(result.stdout) == ["records gate", "ruff check"], result.stdout
    assert "records-gate: FAIL  ruff format (exit 1)" in result.stderr, result.stderr
    assert result.stderr.rstrip().endswith("records-gate: FAILED"), result.stderr


def test_wrapper_passes_when_every_records_step_passes(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, CLEAN_PROBE)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("records-gate: scope records\n"), result.stdout
    assert _ok_steps(result.stdout) == RECORDS_STEPS, result.stdout
    assert result.stdout.rstrip().endswith("records-gate: PASSED"), result.stdout
    assert result.stderr == "", result.stderr


def test_backend_scope_fails_when_a_full_gate_step_fails(tmp_path: Path) -> None:
    """Chief defect 12's shape: the records steps pass but the full backend gate would not; the wrapper must fail."""
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope="backend", app_body=BANDIT_FINDING)
    assert result.returncode != 0, (
        f"a failing full-gate step must fail the wrapper; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert _ok_steps(result.stdout) == [*RECORDS_STEPS, "ruff check (backend)", "pytest (backend)"], result.stdout
    assert "records-gate: FAIL  bandit (exit 1)" in result.stderr, result.stderr
    assert result.stderr.rstrip().endswith("records-gate: FAILED"), result.stderr


def test_backend_scope_passes_when_every_step_passes(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope="backend", app_body="")
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("records-gate: scope backend\n"), result.stdout
    assert _ok_steps(result.stdout) == BACKEND_STEPS, result.stdout
    assert result.stdout.rstrip().endswith("records-gate: PASSED"), result.stdout
    assert result.stderr == "", result.stderr


def test_auto_scope_is_backend_when_the_working_tree_changes_backend(tmp_path: Path) -> None:
    """In a git repository whose working tree has an (untracked) change under backend/, auto picks the full gate."""
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope=None, app_body="", git="untracked-change")
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("records-gate: scope backend\n"), result.stdout
    assert _ok_steps(result.stdout) == BACKEND_STEPS, result.stdout


def test_auto_scope_is_backend_when_a_commit_since_main_changes_backend(tmp_path: Path) -> None:
    """After the commit the working tree is clean; the commits since main still change backend/, so auto picks the full gate."""
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope=None, app_body="", git="committed-change")
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("records-gate: scope backend\n"), result.stdout
    assert _ok_steps(result.stdout) == BACKEND_STEPS, result.stdout


def test_auto_scope_fails_closed_without_a_base_to_compare_with(tmp_path: Path) -> None:
    """A clean tree in a repository with neither origin/main nor main: auto cannot tell and refuses to guess."""
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope=None, app_body="", git="no-base")
    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "cannot determine the scope" in result.stderr, result.stderr
    assert "records-gate: ok" not in result.stdout, result.stdout


def test_auto_scope_fails_closed_when_head_sits_on_the_local_main(tmp_path: Path) -> None:
    """No origin/main and HEAD is the local main: comparing HEAD with itself would hide the committed backend change."""
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope=None, app_body="", git="on-local-main")
    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "HEAD is on the local main itself" in result.stderr, result.stderr
    assert "records-gate: ok" not in result.stdout, result.stdout


def test_auto_scope_is_records_outside_a_repository(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope=None)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert result.stdout.startswith("records-gate: scope records\n"), result.stdout
    assert _ok_steps(result.stdout) == RECORDS_STEPS, result.stdout


def test_unknown_scope_is_refused(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, CLEAN_PROBE, scope="everything")
    assert result.returncode == 2, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "unknown scope 'everything'" in result.stderr, result.stderr


@pytest.mark.parametrize(
    ("line", "accepted"),
    [
        # chief defect 10: the pipe hands the status to tail
        ("python -m pytest tests/unit/test_code_red_runtime_records.py -q | tail -1", False),
        # piped and then captured: still rejected, the capture sees tail's status
        ("python -m pytest tests/unit/test_code_red_runtime_records.py -q | tail -1 || status=$?", False),
        # unpiped but the status is not captured: nothing records the failure for the exit line
        ('python -m pytest tests/unit/test_code_red_runtime_records.py -q >"$log" 2>&1', False),
        # the wrapper's step runner
        ('(cd "$repo/backend" && "$@") >"$log" 2>&1 || status=$?', True),
    ],
)
def test_the_predicate_rejects_the_incident_shape(line: str, accepted: bool) -> None:
    """The static rule above, exercised on the shape of chief defect 10 and on the wrapper's step runner."""
    assert _is_unpiped_with_status_captured(line) is accepted
