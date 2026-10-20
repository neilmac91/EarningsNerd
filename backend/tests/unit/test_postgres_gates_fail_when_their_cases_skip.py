"""tests/support/postgres_gates.py fails a run in which a PostgreSQL gate's variable is set and its cases do not run
(E132).

Each child run loads the plugin as its conftest and runs one probe module named after a gate home, in a subprocess,
serially and under pytest-xdist (where only the controller sees every report). The forms planted: a fixture that reads
another variable, a module that skips as it imports, a module's skip mark, a skip in a test's body, and an xfail.
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

# A module that skips as it imports collects nothing (alone in a run, exit 5).
MODULE_SKIP = """
import pytest

pytest.skip("parked", allow_module_level=True)

def test_a_race():
    pass
"""

# A module's skip mark collects its tests and skips each one (exit 0 on its own).
MARKED_SKIP = """
import pytest

pytestmark = pytest.mark.skip(reason="parked")

def test_a_race():
    pass
"""

BODY_SKIP = """
import pytest

def test_a_race():
    pytest.skip("not today")
"""

EXPECTED_FAILURE = """
import pytest

@pytest.mark.xfail(reason="known")
def test_a_race():
    assert False
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
@pytest.mark.parametrize("source,kind", [
    (FIXTURE_READS_ANOTHER_VARIABLE, "skipped"), (MODULE_SKIP, "skipped"), (MARKED_SKIP, "skipped"),
    (BODY_SKIP, "skipped"), (EXPECTED_FAILURE, "xfailed"),
], ids=["fixture", "module", "mark", "body", "xfail"])
def test_a_gate_whose_cases_do_not_run_while_its_variable_is_set_fails(pytester, monkeypatch, source, kind, parallel):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, source, *parallel)
    assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()[-2000:]
    result.stdout.fnmatch_lines([
        f"*postgres gate: {VARIABLE} is set, yet 1 of {HOME}.py's cases did not run*", f"{kind}: *",
    ])


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


def test_each_run_in_one_process_keeps_its_own_count(pytester, monkeypatch):
    """Two in-process runs one after the other, as a pytester child runs inside a serial parent: the first's case
    that did not run must not fail the second, nor the parent."""
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    pytester.makepyfile(**{HOME: FIXTURE_READS_ANOTHER_VARIABLE})
    first = pytester.runpytest("-p", "tests.support.postgres_gates", *CHILD_ARGS)
    assert first.ret == pytest.ExitCode.TESTS_FAILED, first.stdout.str()[-2000:]
    pytester.makepyfile(**{HOME: CASES_RUN})
    second = pytester.runpytest("-p", "tests.support.postgres_gates", *CHILD_ARGS)
    assert second.ret == pytest.ExitCode.OK, second.stdout.str()[-2000:]
