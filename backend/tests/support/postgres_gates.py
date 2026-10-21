"""A PostgreSQL gate's run fails when its database variable is set and any of its cases skip, and a PostgreSQL case
fails when it opens a session unlike production's.

Each required PostgreSQL step in CI's migrations-postgres job sets one variable and runs one test
home; the home's cases skip when the variable is unset, which is how the fast lane runs them. A home
whose engine fixture stops reading its variable skips its PostgreSQL cases at setup, and the step
passed with them unrun: pytest exits 0 when collected tests skip, as it does for a module's skip mark
(``pytestmark``) (E132). So when the variable is set, every case of that home that does not run fails
the run: a skip at setup, in a test or by a mark, an expected failure (xfail), or a module that skips
as it imports. Such a module collects nothing, so its step already failed (exit 5); it now fails with
the same report. ``test_migration_lock_safety.py`` pins ``POSTGRES_GATES`` to the workflow's steps,
and ``test_postgres_gates_fail_when_their_cases_skip.py`` runs the plugin in child pytest sessions.

The steps run serially. Under pytest-xdist, as a developer's default ``pytest`` runs, the controller
sees every worker's test reports and its skipped collection reports and ignores a worker's exit
status, so only the controller (or a serial run) keeps count and fails the run. The count belongs to
the run's config, so a pytester child in the same process keeps its own.

The same steps check every session a PostgreSQL case opens (a case that takes ``postgres_engine``),
as each one begins a transaction: it must not autoflush, and it must run on the case's own engine,
the one ``postgres_engine`` handed it, in the case's disposable schema. That holds however the case
built the session, through an alias, a helper's argument or a module the home imports, which
``test_migration_lock_safety.py``'s reading of the source cannot follow;
``test_postgres_gates_open_production_sessions.py`` runs this check in child pytest sessions.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

# Each PostgreSQL gate's test home, and the variable its CI step sets.
POSTGRES_GATES = {
    "test_subscription_event_transactions.py": "STRIPE_CONCURRENCY_TEST_DATABASE_URL",
    "test_usage_counter_transactions.py": "USAGE_CONCURRENCY_TEST_DATABASE_URL",
    "test_login_lockout_transactions.py": "LOGIN_CONCURRENCY_TEST_DATABASE_URL",
    "test_notification_delivery_transactions.py": "DELIVERY_CONCURRENCY_TEST_DATABASE_URL",
    "test_refresh_rotation_transactions.py": "REFRESH_CONCURRENCY_TEST_DATABASE_URL",
}
# Each gate home's PostgreSQL engine fixture: a case that takes it, directly or through another fixture, is one of
# the home's PostgreSQL cases.
POSTGRES_ENGINE_FIXTURE = "postgres_engine"


def _armed_home(nodeid: str) -> str | None:
    """The gate home a report belongs to, when that home's variable is set in this run."""
    home = Path(nodeid.split("::", 1)[0]).name
    variable = POSTGRES_GATES.get(home)
    return home if variable and os.environ.get(variable) else None


def _root_engine(engine):
    """The engine another was derived from: ``Engine.execution_options()`` returns a proxy of its engine."""
    while (proxied := getattr(engine, "_proxied", None)) is not None:
        engine = proxied
    return engine


@pytest.fixture(autouse=True)
def _postgres_cases_open_production_sessions(request: pytest.FixtureRequest):
    """When a gate's variable is set, each of its PostgreSQL cases opens every ORM session as production does,
    autoflush off, on the case's own engine: the one ``postgres_engine`` handed it, which runs in the case's disposable
    schema. A session that autoflushes, or that runs on another engine, fails the case at its teardown. Another engine
    is the suite's SQLite file, where the test conftest binds production's ``SessionLocal`` and the app's engine, or a
    second PostgreSQL engine, such as one built from the gate's URL, which runs outside the case's schema. The listener
    only records, in whatever thread the session begins: an exception raised inside the event would leave a
    transaction, and its locks, on a pooled connection."""
    home = _armed_home(request.node.nodeid)
    if home is None:
        yield
        return
    begun: list[tuple[str, bool, object]] = []

    def record(session: Session, transaction, connection) -> None:
        begun.append((type(session).__name__, session.autoflush, connection.engine))

    event.listen(Session, "after_begin", record)
    try:
        yield
    finally:
        event.remove(Session, "after_begin", record)
    # The case's fixture values stay on the item until its teardown ends. Engines are compared by identity, through
    # any proxy: a pool taken as a session begins is no witness, since the engine's dispose() gives it a new one
    # before this runs.
    case_engine = (request.node.funcargs or {}).get(POSTGRES_ENGINE_FIXTURE)
    if case_engine is None:
        # A SQLite case, which takes no postgres_engine, or a PostgreSQL case whose fixtures did not set up: it has
        # already errored, or skipped, and a skip fails the run.
        return
    unlike = [
        f"{name} with autoflush={autoflush}, on "
        + ("the case's engine" if _root_engine(engine) is case_engine else f"another {engine.dialect.name} engine")
        for name, autoflush, engine in begun
        if autoflush or _root_engine(engine) is not case_engine
    ]
    if unlike:
        pytest.fail(
            f"postgres gate: {POSTGRES_GATES[home]} is set, yet this PostgreSQL case opened {len(unlike)} session(s) "
            f"unlike production's ({'; '.join(sorted(set(unlike)))}). Open each through a sessionmaker that spreads "
            "SessionLocal.kw and binds the case's own engine (tests/support/postgres_gates.py).",
            pytrace=False,
        )


class _UnrunCases:
    """One run's count: each armed gate home's cases that did not run."""

    def __init__(self) -> None:
        self.unrun: dict[str, list[str]] = {}

    def _record(self, report) -> None:
        if not report.skipped:
            return
        home = _armed_home(report.nodeid)
        if home is not None:
            kind = "xfailed" if hasattr(report, "wasxfail") else "skipped"
            self.unrun.setdefault(home, []).append(f"{kind}: {report.nodeid or home}")

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        self._record(report)  # a module that skips as it imports

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self._record(report)  # a test's skip, at setup, in its body or by a mark, or an xfail

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.unrun and session.exitstatus in (pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(self, terminalreporter) -> None:
        for home, cases in sorted(self.unrun.items()):
            terminalreporter.section(
                f"postgres gate: {POSTGRES_GATES[home]} is set, yet {len(cases)} of {home}'s cases did not run "
                "-- session FAILED",
                sep="=", red=True, bold=True,
            )
            for case in cases:
                terminalreporter.line(case)
            terminalreporter.line(
                "A required PostgreSQL step must run its cases, not skip them: read the variable in the engine "
                "fixture and skip only when it is unset (tests/support/postgres_gates.py)."
            )


def pytest_configure(config: pytest.Config) -> None:
    if not hasattr(config, "workerinput"):  # an xdist worker: its controller counts
        config.pluginmanager.register(_UnrunCases(), "postgres_gates_unrun_cases")
