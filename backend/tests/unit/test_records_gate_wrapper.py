"""Gate for ``tasks/code-red-20261004/runtime/tools/records-gate.sh`` (lessons/ops-a-piped-gate-does-not-gate.md).

A commit chain once ran the runtime-records gate as ``pytest … | tail -1 && git commit``; the pipe returned ``tail``'s status,
so a red gate did not stop the commit (chief defect 10, DECISIONS-21). The wrapper is the supported way to run that gate before a
records commit. This test pins the wrapper's form (strict mode; the pytest invocation unpiped; the exit status propagated) and
proves the behaviour by mutation: pointed at a failing test the wrapper exits non-zero and reports the failure; pointed at a
passing test it exits zero. The wrapper runs pytest in a subprocess inside a temporary repository shaped like this one, so the
proof costs two short pytest sessions and touches nothing in the real tree.
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


def test_wrapper_is_strict_and_runs_pytest_unpiped() -> None:
    text = WRAPPER.read_text(encoding="utf-8")
    assert WRAPPER.stat().st_mode & stat.S_IXUSR, "records-gate.sh must be executable"
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text, "the wrapper must run in strict mode with pipefail"
    pytest_lines = [line for line in text.splitlines() if "-m pytest" in line]
    assert len(pytest_lines) == 1, f"exactly one pytest invocation expected, found {pytest_lines}"
    # `||` captures the status; a lone `|` would hand the status to the right-hand command (the incident shape).
    assert "|" not in pytest_lines[0].replace("||", ""), f"the pytest invocation must not be piped: {pytest_lines[0]!r}"
    assert re.search(r"\|\| status=\$\?", pytest_lines[0]), "the invocation must capture pytest's exit status"
    assert re.search(r'^exit "\$status"\s*$', text, re.MULTILINE), "the wrapper must exit with pytest's status"


def _run_wrapper(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    repo = tmp_path / "repo"
    tests = repo / "backend" / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "test_probe.py").write_text(body, encoding="utf-8")
    env = {
        **os.environ,
        "RECORDS_GATE_PYTHON": sys.executable,
        "RECORDS_GATE_TEST": "tests/unit/test_probe.py",
        # Keep the inner session hermetic and independent of this repository's pytest.ini and plugins' autoload.
        "PYTEST_ADDOPTS": "-p no:randomly -p no:xdist",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    return subprocess.run(  # noqa: S603 - the wrapper under test, with controlled arguments
        [str(WRAPPER), str(repo)], capture_output=True, text=True, env=env, timeout=120, check=False
    )


def test_wrapper_fails_when_the_gate_fails(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, "def test_probe():\n    assert False, 'planted failure'\n")
    assert result.returncode != 0, (
        f"a failing gate must fail the wrapper; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "1 failed" in result.stdout.strip().splitlines()[-1], result.stdout
    assert "records-gate: FAILED" in result.stderr, result.stderr


def test_wrapper_passes_when_the_gate_passes(tmp_path: Path) -> None:
    result = _run_wrapper(tmp_path, "def test_probe():\n    assert True\n")
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "1 passed" in result.stdout.strip().splitlines()[-1], result.stdout
    assert result.stderr == "", result.stderr


@pytest.mark.parametrize("line", ["pytest tests/unit/test_code_red_runtime_records.py -q | tail -1"])
def test_the_incident_shape_is_what_the_wrapper_forbids(line: str) -> None:
    """Documents the shape of chief defect 10 so the static check above reads as the rule it enforces."""
    assert "|" in line and "pytest" in line
