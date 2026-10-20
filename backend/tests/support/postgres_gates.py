"""A PostgreSQL gate's run fails when its database variable is set and any of its cases skip.

Each required PostgreSQL step in CI's migrations-postgres job sets one variable and runs one test
home; the home's cases skip when the variable is unset, which is how the fast lane runs them. A home
whose engine fixture stops reading its variable skips its PostgreSQL cases at setup, and the step
passed with them unrun (exit 0, its SQLite cases passing or nothing at all) (E132). So when the
variable is set, every skip in that home fails the run: a test's (a fixture's skip, or a mark) or
the module's. A skipped module already failed its step, as no test was collected (exit 5); it now
fails with the same report. ``test_migration_lock_safety.py`` pins
``POSTGRES_GATES`` to the steps, and ``test_postgres_gates_fail_when_their_cases_skip.py`` runs the
plugin in a child pytest.

Under pytest-xdist the controller sees every worker's test reports and its skipped collection
reports, and it ignores a worker's exit status, so only the controller (or a serial run) keeps
count and fails the run.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Each PostgreSQL gate's test home, and the variable its CI step sets.
POSTGRES_GATES = {
    "test_subscription_event_transactions.py": "STRIPE_CONCURRENCY_TEST_DATABASE_URL",
    "test_usage_counter_transactions.py": "USAGE_CONCURRENCY_TEST_DATABASE_URL",
    "test_login_lockout_transactions.py": "LOGIN_CONCURRENCY_TEST_DATABASE_URL",
    "test_notification_delivery_transactions.py": "DELIVERY_CONCURRENCY_TEST_DATABASE_URL",
    "test_refresh_rotation_transactions.py": "REFRESH_CONCURRENCY_TEST_DATABASE_URL",
}

_counting = True
_skipped: dict[str, list[str]] = {}  # home -> the skipped nodeids, while its variable is set


def _armed_home(nodeid: str) -> str | None:
    """The gate home a report belongs to, when that home's variable is set in this run."""
    home = Path(nodeid.split("::", 1)[0]).name
    variable = POSTGRES_GATES.get(home)
    return home if variable and os.environ.get(variable) else None


def _record(report) -> None:
    if not (_counting and report.skipped):
        return
    home = _armed_home(report.nodeid)
    if home is not None:
        _skipped.setdefault(home, []).append(report.nodeid or home)


def pytest_configure(config: pytest.Config) -> None:
    global _counting
    _counting = not hasattr(config, "workerinput")  # an xdist worker: its controller counts


def pytest_collectreport(report: pytest.CollectReport) -> None:
    _record(report)  # a skipped module


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    _record(report)  # a skipped test, at setup (a fixture's skip) or as marked


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session) -> None:
    if _skipped and session.exitstatus in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter) -> None:
    for home, nodeids in sorted(_skipped.items()):
        terminalreporter.section(
            f"postgres gate: {POSTGRES_GATES[home]} is set, yet {len(nodeids)} of {home}'s cases skipped "
            "-- session FAILED",
            sep="=", red=True, bold=True,
        )
        for nodeid in nodeids:
            terminalreporter.line(f"skipped: {nodeid}")
        terminalreporter.line(
            "A required PostgreSQL step must run its cases, not skip them: read the variable in the engine fixture "
            "and skip only when it is unset (tests/support/postgres_gates.py)."
        )
