"""tests/support/postgres_gates.py fails a gate's PostgreSQL case that uses a session unlike production's (E132).

Each child run loads the plugin as its conftest and runs one probe module named after a gate home, in a subprocess. The
probe's ``postgres_engine`` is an in-memory SQLite engine whose dialect calls itself PostgreSQL: the check compares a
session's engine with it and names the dialect of any other, so the run needs no database. The forms planted: an
autoflushing session, one opened in a thread, a session on another database through a helper handed the wrong engine,
one on a second engine that calls itself PostgreSQL, as one built from the gate's URL without the case's schema would,
and one that only begins. Then the forms a wider-scoped fixture gives: its own work at setup, before the case's
fixtures, and a session it began in an earlier case's setup that the case then queries, or only flushes. A session
bound to a connection of the case's engine, or to a proxy ``execution_options()`` made of it, passes.
"""
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)

PLUGIN_SOURCE = (Path(__file__).resolve().parents[1] / "support" / "postgres_gates.py").read_text(encoding="utf-8")
HOME = "test_usage_counter_transactions"
VARIABLE = "USAGE_CONCURRENCY_TEST_DATABASE_URL"
CHILD_ARGS = ("-p", "no:cacheprovider", "-p", "no:randomly")
# Under xdist a module's cases stay in one worker, in their order, as a fixture of module scope needs here.
PARALLEL = ("-n", "2", "--dist", "loadfile")

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

DERIVED_BINDS = ENGINES + """
def test_a_race(postgres_engine):
    _use(_session(postgres_engine.execution_options(isolation_level="SERIALIZABLE")))
    with postgres_engine.connect() as connection:
        _use(_session(connection))
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

A_SECOND_POSTGRES_ENGINE = ENGINES + """
def test_a_race(postgres_engine):
    second = create_engine("sqlite://")
    second.dialect.name = "postgresql"  # the gate's URL without the case's schema, say
    _use(_session(postgres_engine))
    _use(_session(second))
    second.dispose()
"""

IN_A_THREAD = ENGINES + """
def test_a_race(postgres_engine):
    worker = threading.Thread(target=_use, args=(Session(postgres_engine),))
    worker.start()
    worker.join()
"""

A_SESSION_THAT_ONLY_BEGINS = ENGINES + """
def test_a_race(postgres_engine, sqlite_engine):
    _use(_session(postgres_engine))
    with _session(sqlite_engine) as db:
        db.connection()  # begins, and runs nothing through the session
"""

WORK_IN_A_WIDER_FIXTURE = ENGINES + """
@pytest.fixture(scope="module")
def seeded():
    engine = create_engine("sqlite://")
    engine.dialect.name = "postgresql"
    _use(Session(engine))  # all its work at setup, before the case's own fixtures
    yield "seeded"
    engine.dispose()


def test_a_race(postgres_engine, seeded):
    _use(_session(postgres_engine))
"""

BEGUN_BEFORE = ENGINES + """
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Row(Base):
    __tablename__ = "rows"
    id: Mapped[int] = mapped_column(primary_key=True)


@pytest.fixture(scope="module")
def shared():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.execute(text("select 1"))  # begun here, in the earlier case's setup
    yield session
    session.close()
    engine.dispose()


def test_a_sqlite_case(sqlite_engine, shared):
    _use(_session(sqlite_engine))
"""

BEGUN_BEFORE_THEN_QUERIED = BEGUN_BEFORE + """
def test_a_race(postgres_engine, shared):
    _use(_session(postgres_engine))
    shared.execute(text("select 1"))  # in the transaction begun before this case
"""

BEGUN_BEFORE_THEN_FLUSHED = BEGUN_BEFORE + """
def test_a_race(postgres_engine, shared):
    _use(_session(postgres_engine))
    shared.add(Row())
    shared.flush()  # in the transaction begun before this case, with no statement through execute()
"""

A_SQLITE_CASE = ENGINES + """
def test_a_sqlite_case(sqlite_engine):
    _use(Session(sqlite_engine))
"""


def _run(pytester, source, *args):
    pytester.makeconftest(PLUGIN_SOURCE)
    pytester.makepyfile(**{HOME: source})
    return pytester.runpytest_subprocess(*CHILD_ARGS, *args)


@pytest.mark.parametrize("source", [PRODUCTION_SESSIONS, DERIVED_BINDS], ids=["engine", "derived-binds"])
def test_a_case_whose_sessions_are_production_s_passes(pytester, monkeypatch, source):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, source)
    assert result.ret == pytest.ExitCode.OK, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=1)


@pytest.mark.parametrize("parallel", [(), PARALLEL], ids=["serial", "xdist"])
@pytest.mark.parametrize("source,why,passed", [
    (AUTOFLUSHING, "Session with autoflush=True, on the case's engine", 1),
    (ANOTHER_DATABASE, "Session with autoflush=False, on another sqlite engine", 1),
    (A_SECOND_POSTGRES_ENGINE, "Session with autoflush=False, on another postgresql engine", 1),
    (IN_A_THREAD, "Session with autoflush=True, on the case's engine", 1),
    (A_SESSION_THAT_ONLY_BEGINS, "Session with autoflush=False, on another sqlite engine", 1),
    (WORK_IN_A_WIDER_FIXTURE, "Session with autoflush=True, on another postgresql engine", 1),
    (BEGUN_BEFORE_THEN_QUERIED, "Session with autoflush=True, on another sqlite engine", 2),
    (BEGUN_BEFORE_THEN_FLUSHED, "Session with autoflush=True, on another sqlite engine", 2),
], ids=["autoflush", "another-database", "second-postgres-engine", "thread", "only-begins", "wider-fixture-work",
        "begun-before-then-queried", "begun-before-then-flushed"])
def test_a_case_with_a_session_unlike_production_s_fails(pytester, monkeypatch, source, why, passed, parallel):
    monkeypatch.setenv(VARIABLE, "postgresql://set-by-the-step")
    result = _run(pytester, source, *parallel)
    assert result.ret == pytest.ExitCode.TESTS_FAILED, result.stdout.str()[-2000:]
    result.assert_outcomes(passed=passed, errors=1)
    result.stdout.fnmatch_lines([f"*postgres gate: {VARIABLE} is set, yet this PostgreSQL case used a session unlike*"])
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
