"""tests/support/postgres_gates.py fails a gate's PostgreSQL case that opens a session unlike production's (E132).

Each child run loads the plugin as its conftest and runs one probe module named after a gate home, in a subprocess. The
probe's ``postgres_engine`` is an in-memory SQLite engine whose dialect calls itself PostgreSQL, which is all the check
reads of it, so the run needs no database. The forms planted: an autoflushing session, a session on another database
through a helper handed the wrong engine, and one opened in a thread.
"""
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)

PLUGIN_SOURCE = (Path(__file__).resolve().parents[1] / "support" / "postgres_gates.py").read_text(encoding="utf-8")
HOME = "test_usage_counter_transactions"
VARIABLE = "USAGE_CONCURRENCY_TEST_DATABASE_URL"
CHILD_ARGS = ("-p", "no:cacheprovider", "-p", "no:randomly")

ENGINES = """
import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def postgres_engine():
    engine = create_engine("sqlite://")
    engine.dialect.name = "postgresql"  # all the check reads of the engine it is handed
    yield engine
    engine.dispose()


@pytest.fixture
def sqlite_engine():
    engine = create_engine("sqlite://")
    yield engine
    engine.dispose()


def _session(bind):
    return sessionmaker(autoflush=False, bind=bind)()


def _use(session):
    with session as db:
        db.execute(text("select 1"))
"""

PRODUCTION_SESSIONS = ENGINES + """
def test_a_race(postgres_engine):
    _use(_session(postgres_engine))
"""

AUTOFLUSHING = ENGINES + """
def test_a_race(postgres_engine):
    _use(Session(postgres_engine))
"""

ANOTHER_DATABASE = ENGINES + """
def test_a_race(postgres_engine, sqlite_engine):
    _use(_session(postgres_engine))
    _use(_session(sqlite_engine))  # a helper handed the app's engine, say
"""

IN_A_THREAD = ENGINES + """
def test_a_race(postgres_engine):
    worker = threading.Thread(target=_use, args=(Session(postgres_engine),))
    worker.start()
    worker.join()
"""

A_SQLITE_CASE = ENGINES + """
def test_a_sqlite_case(sqlite_engine):
    _use(Session(sqlite_engine))
"""


def _run(pytester, source, *args):
    pytester.makeconftest(PLUGIN_SOURCE)
    pytester.makepyfile(**{HOME: source})
    return pytester.runpytest_subprocess(*CHILD_ARGS, *args)


def test_a_case_whose_sessions_are_production_s_passes(pytester, monkeypatch):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, PRODUCTION_SESSIONS)
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("parallel", [(), ("-n", "2")], ids=["serial", "xdist"])
@pytest.mark.parametrize("source,why", [
    (AUTOFLUSHING, "Session with autoflush=True, on postgresql"),
    (ANOTHER_DATABASE, "Session with autoflush=False, on sqlite"),
    (IN_A_THREAD, "Session with autoflush=True, on postgresql"),
], ids=["autoflush", "another-database", "thread"])
def test_a_case_with_a_session_unlike_production_s_fails(pytester, monkeypatch, source, why, parallel):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, source, *parallel)
    assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1, errors=1)
    result.stdout.fnmatch_lines([f"*postgres gate: {VARIABLE} is set, yet this PostgreSQL case opened 1 session(s)*"])
    result.stdout.fnmatch_lines([f"*({why})*"])


def test_the_fast_lane_does_not_check(pytester, monkeypatch):
    monkeypatch.delenv(VARIABLE, raising=False)
    result = _run(pytester, AUTOFLUSHING)
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1)


def test_a_case_without_the_postgres_engine_is_not_checked(pytester, monkeypatch):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, A_SQLITE_CASE)
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1)
