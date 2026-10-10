"""Gate for ``tasks/code-red-20261004/runtime/tools/records-gate.sh`` (lessons/ops-a-piped-gate-does-not-gate.md).

Two commit chains failed to gate a CODE RED records commit: one piped the records gate (``pytest … | tail -1``, so ``tail``'s
status decided; chief defect 10) and one relied on ``set -e``, which the chief's tool shell suppresses, so a failed
``ruff format --check`` did not stop the commit (chief defect 11; DECISIONS-21). The wrapper is the supported way to verify a
records commit: every step runs unpiped with its exit status captured explicitly, and the wrapper exits 0 only when every step
passed. This test pins that form and proves it by mutation in a temporary repository shaped like this one: a failing pytest step
and a failing non-pytest step (an unformatted file) each fail the wrapper; a clean repository passes it. Each proof runs the
wrapper in a subprocess with the running interpreter; nothing in the real tree is touched.
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


def _is_unpiped_with_status_captured(line: str) -> bool:
    """The rule the wrapper's step runner must satisfy: no pipe (``||`` captures the status and is not one), and ``|| status=$?``."""
    return "|" not in line.replace("||", "") and re.search(r"\|\| status=\$\?", line) is not None


def _lines_containing(text: str, needle: str) -> list[str]:
    """Non-comment lines of the wrapper containing ``needle`` (the header comment quotes the rule it describes)."""
    return [line.strip() for line in text.splitlines() if needle in line and not line.lstrip().startswith("#")]


def test_wrapper_form_every_step_unpiped_with_its_status_captured() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert WRAPPER.stat().st_mode & stat.S_IXUSR, "records-gate.sh must be executable"
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text, "the wrapper must run in strict mode with pipefail"
    runner_lines = _lines_containing(text, "|| status=$?")
    assert len(runner_lines) == 1, f"exactly one status capture expected (the step runner), found {runner_lines}"
    assert _is_unpiped_with_status_captured(runner_lines[0]), runner_lines[0]
    for needle in ("-m pytest", "-m ruff check", "-m ruff format --check"):
        step_lines = _lines_containing(text, needle)
        assert len(step_lines) == 1, f"exactly one {needle!r} step expected, found {step_lines}"
        assert step_lines[0].startswith("run_step "), f"{needle!r} must run through the step runner: {step_lines[0]!r}"
        assert "|" not in step_lines[0], f"a step is never piped: {step_lines[0]!r}"
    assert re.search(r'^exit "\$failed"\s*$', text, re.MULTILINE), "the wrapper must exit non-zero when any step failed"


def _run_wrapper(tmp_path: Path, probe_body: str) -> subprocess.CompletedProcess[str]:
    repo = tmp_path / "repo"
    tests = repo / "backend" / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_probe.py").write_text(probe_body, encoding="utf-8")
    env = {
        **os.environ,
        "RECORDS_GATE_PYTHON": sys.executable,
        "RECORDS_GATE_TEST": "tests/unit/test_probe.py",
        "RECORDS_GATE_LINT_PATHS": "tests/unit/test_probe.py",
        # Keep the inner pytest session hermetic and independent of this repository's pytest.ini and plugins' autoload.
        "PYTEST_ADDOPTS": "-p no:randomly -p no:xdist",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    return subprocess.run(  # noqa: S603 - the wrapper under test, with controlled arguments
        [str(WRAPPER), str(repo)], capture_output=True, text=True, env=env, timeout=180, check=False
    )


def test_wrapper_fails_when_the_pytest_step_fails(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, FAILING_PROBE)
    assert result.returncode != 0, (
        f"a failing gate must fail the wrapper; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "records-gate: FAIL  records gate (exit 1)" in result.stderr, result.stderr
    assert "records-gate: ok    ruff format" in result.stdout, result.stdout
    assert result.stderr.rstrip().endswith("records-gate: FAILED"), result.stderr


def test_wrapper_fails_when_a_non_pytest_step_fails(tmp_path: Path) -> None:
    """Chief defect 11's shape: the tests pass but a formatting check fails; the wrapper must still fail."""
    result = _run_wrapper(tmp_path, UNFORMATTED_PROBE)
    assert result.returncode != 0, (
        f"a failing non-pytest step must fail the wrapper; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "records-gate: ok    records gate" in result.stdout, result.stdout
    assert "records-gate: FAIL  ruff format (exit 1)" in result.stderr, result.stderr
    assert result.stderr.rstrip().endswith("records-gate: FAILED"), result.stderr


def test_wrapper_passes_when_every_step_passes(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, CLEAN_PROBE)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    ok_lines = [line for line in result.stdout.splitlines() if line.startswith("records-gate: ok    ")]
    assert [line.split(":")[1].strip() for line in ok_lines] == [
        "ok    records gate",
        "ok    ruff check",
        "ok    ruff format",
    ], result.stdout
    assert result.stdout.rstrip().endswith("records-gate: PASSED"), result.stdout
    assert result.stderr == "", result.stderr


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
