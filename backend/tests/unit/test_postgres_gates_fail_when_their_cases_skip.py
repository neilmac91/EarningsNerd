"""tests/support/postgres_gates.py fails a run in which a PostgreSQL gate's variable is set and its cases skip (E132).

Each child run loads the plugin as its conftest and runs one probe module named after a gate home, in a subprocess so
the plugin's counts start empty, serially and under pytest-xdist (where only the controller sees every report).
"""
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)

PLUGIN_SOURCE = (Path(__file__).resolve().parents[1] / "support" / "postgres_gates.py").read_text(encoding="utf-8")
HOME = "test_usage_counter_transactions"
VARIABLE = "USAGE_CONCURRENCY_TEST_DATABASE_URL"
CHILD_ARGS = ("-p", "no:cacheprovider", "-p", "no:randomly")
PARALLEL = pytest.mark.parametrize("parallel", [(), ("-n", "2")], ids=["serial", "xdist"])

# The step's variable renamed in the fixture alone: its race skips, its SQLite case still runs.
FIXTURE_READS_ANOTHER_VARIABLE = """
import os
import pytest

@pytest.fixture
def postgres_engine():
    if not os.environ.get("A_RENAMED_DATABASE_URL"):
        pytest.skip("A_RENAMED_DATABASE_URL is not configured")
    return object()

def test_a_race(postgres_engine):
    pass

def test_a_sqlite_case():
    pass
"""

MODULE_SKIP = """
import pytest

pytest.skip("parked", allow_module_level=True)

def test_a_race():
    pass
"""

CASES_RUN = """
import os
import pytest

@pytest.fixture
def postgres_engine():
    if not os.environ.get("USAGE_CONCURRENCY_TEST_DATABASE_URL"):
        pytest.skip("USAGE_CONCURRENCY_TEST_DATABASE_URL is not configured")
    return object()

def test_a_race(postgres_engine):
    pass
"""


def _run(pytester, source, *args, home=HOME):
    pytester.makeconftest(PLUGIN_SOURCE)
    pytester.makepyfile(**{home: source})
    return pytester.runpytest_subprocess(*CHILD_ARGS, *args)


@PARALLEL
@pytest.mark.parametrize("source", [FIXTURE_READS_ANOTHER_VARIABLE, MODULE_SKIP], ids=["fixture", "module"])
def test_a_gate_whose_cases_skip_while_its_variable_is_set_fails(pytester, monkeypatch, source, parallel):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, source, *parallel)
    assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()[-2000:]
    result.stdout.fnmatch_lines([f"*postgres gate: {VARIABLE} is set, yet 1 of {HOME}.py's cases skipped*"])


@PARALLEL
def test_a_gate_whose_cases_run_passes(pytester, monkeypatch, parallel):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, CASES_RUN, *parallel)
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1)


def test_the_fast_lane_still_skips_a_gate_whose_variable_is_unset(pytester, monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)
    result = _run(pytester, FIXTURE_READS_ANOTHER_VARIABLE)
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1, skipped=1)


def test_a_home_that_is_no_gate_may_skip_while_a_gate_variable_is_set(pytester, monkeypatch):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, FIXTURE_READS_ANOTHER_VARIABLE, home="test_something_else")
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1, skipped=1)
