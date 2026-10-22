"""E128: the check-then-write units that a process lock serializes within one instance also take, before their
check, a database lock that every instance shares. The API runs up to two instances, and a process lock reaches
one, so across them two alert enables at the cap could both pass it, two adds could both write a row, a referral
credit could be lost and two joins could take one place.

- The watch-row writes (an add, a remove, an earnings alert's enable and disable) take the account's users row lock
  (``watchlist_service.lock_watch_rows``) before their first read of the watchlist, under ``watch_row_lock``.
- The waitlist join takes the waitlist's place lock (``waitlist_service._lock_waitlist_places``, a transaction-level
  advisory lock) before its first read of the signups, under ``_join_lock``.
- The join's credit is one UPDATE that adds to the stored score, so a credit committed after the join read its
  referrer is kept.

SQLite omits ``FOR UPDATE`` and has no advisory locks, so the lock cases read the statements each unit's session
runs, compiled for PostgreSQL. The join's run on an engine whose dialect calls itself PostgreSQL, with a stand-in
for ``pg_advisory_xact_lock``. ``test_check_then_write_units_serialize.py`` holds the process locks; no CI step races
two instances on PostgreSQL.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, User, WaitlistSignup, Watchlist
from app.services import earnings_alert_service, waitlist_service, watchlist_service

# Apart from the company ids, so a lock taken by a company's id in place of the account's fails.
USER_ID = 1000


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'lock-across-instances.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(engine):
    return sessionmaker(**{**database.SessionLocal.kw, "bind": engine})


@pytest.fixture
def postgres_named(engine):
    """``engine``, with a dialect that calls itself PostgreSQL, the name ``_lock_waitlist_places`` reads, and a
    stand-in for ``pg_advisory_xact_lock`` that SQLite runs and that returns nothing."""
    event.listen(engine, "connect",
                 lambda connection, _record: connection.create_function("pg_advisory_xact_lock", 1, lambda key: None))
    engine.dispose()  # the connection create_all pooled has no stand-in
    engine.dialect.name = "postgresql"
    return engine


def _recorded(session, statements: list[tuple[str, dict]]):
    """``session``, recording each ORM statement it runs, compiled for PostgreSQL, with its parameters, and each
    end of a transaction."""
    def record(state) -> None:
        compiled = state.statement.compile(dialect=postgresql.dialect())
        statements.append((str(compiled), {**compiled.params, **(state.parameters or {})}))

    event.listen(session, "do_orm_execute", record)
    event.listen(session, "after_commit", lambda _session: statements.append(("-- commit", {})))
    event.listen(session, "after_rollback", lambda _session: statements.append(("-- rollback", {})))
    return session


def _assert_locks_before_it_checks(statements: list[tuple[str, dict]], *, lock, lock_value, checks: str) -> None:
    """The first statement that reads ``checks`` follows the lock ``lock`` names, taken on ``lock_value`` and
    waiting for its holder, and no end of a transaction between them releases it."""
    shown = "\n".join(sql for sql, _ in statements)
    locks = [i for i, (sql, params) in enumerate(statements) if lock(sql) and lock_value in params.values()]
    reads = [i for i, (sql, _) in enumerate(statements) if checks in sql]
    assert locks and reads and locks[0] < reads[0], shown
    assert not any(sql.startswith("-- ") for sql, _ in statements[locks[0]:reads[0]]), shown


def _users_row_lock(sql: str) -> bool:
    """The account's users row, locked FOR NO KEY UPDATE and waiting for its holder (no SKIP LOCKED, no NOWAIT)."""
    return "FROM users" in sql and sql.rstrip().endswith("FOR NO KEY UPDATE")


def _place_lock(sql: str) -> bool:
    """The waitlist's place lock: the transaction-level advisory lock that waits for its holder, not the
    session-level one, which a pooled connection would keep past the unit, and not a try that gives up."""
    return "pg_advisory_xact_lock(" in sql and "pg_try_" not in sql


def _watcher(sessions, *, alerts_on: int = 0, watched: bool = False) -> None:
    """A Free account (cap 3) and four companies; ``alerts_on`` of them have its alert on, and ``watched`` puts
    CAP3 on its watchlist with the alert on."""
    with sessions() as db:
        db.add(User(id=USER_ID, email="watcher@example.com", is_active=True))
        companies = [Company(cik=f"{i + 1:010d}", ticker=f"CAP{i}", name=f"Capped {i}") for i in range(4)]
        db.add_all(companies)
        db.flush()
        db.add_all(Watchlist(user_id=USER_ID, company_id=company.id, earnings_alert=True)
                   for company in companies[:alerts_on])
        if watched:
            db.add(Watchlist(user_id=USER_ID, company_id=companies[3].id, earnings_alert=True))
        db.commit()


def _watch_row_statements(sessions, unit) -> list[tuple[str, dict]]:
    """The statements ``unit(db, user)`` runs, on a session whose first query, the user's lookup, ran before it, as
    the route's auth dependency's does."""
    statements: list[tuple[str, dict]] = []
    with sessions() as db:
        user = db.get(User, USER_ID)
        _recorded(db, statements)
        unit(db, user)
    return statements


@pytest.mark.parametrize("unit", [
    pytest.param(lambda db, user: watchlist_service.add_company(db, user.id, "CAP2"), id="add"),
    pytest.param(lambda db, user: watchlist_service.remove_company(db, user.id, "CAP3"), id="remove"),
    pytest.param(lambda db, user: earnings_alert_service.set_earnings_alert(db, user, "CAP2", enabled=True),
                 id="alert enable"),
    pytest.param(lambda db, user: earnings_alert_service.set_earnings_alert(db, user, "CAP3", enabled=False),
                 id="alert disable"),
])
def test_each_watch_row_write_locks_the_account_before_it_checks(sessions, unit):
    """Each write as it succeeds: CAP0 and CAP3 have the alert on, one slot short of the cap, and CAP2 is not
    watched."""
    _watcher(sessions, alerts_on=1, watched=True)
    statements = _watch_row_statements(sessions, unit)
    _assert_locks_before_it_checks(statements, lock=_users_row_lock, lock_value=USER_ID, checks="FROM watchlist")


def test_the_alert_enable_counts_the_cap_under_the_lock(sessions):
    """The cap count itself, not only the row read before it, comes after the lock."""
    _watcher(sessions, alerts_on=2)
    statements = _watch_row_statements(
        sessions, lambda db, user: earnings_alert_service.set_earnings_alert(db, user, "CAP2", enabled=True))
    _assert_locks_before_it_checks(statements, lock=_users_row_lock, lock_value=USER_ID,
                                   checks="count(distinct(watchlist.company_id))")


@pytest.mark.parametrize("referral_code", ["refcode0", None])
def test_the_join_takes_the_place_lock_before_it_reads_the_list(sessions, postgres_named, referral_code):
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()
    statements: list[tuple[str, dict]] = []
    with _recorded(sessions(), statements) as db:
        waitlist_service.create_signup(db, email="joiner@example.com", name=None, referral_code=referral_code,
                                       source=None)
    _assert_locks_before_it_checks(statements, lock=_place_lock, lock_value=waitlist_service.WAITLIST_PLACE_LOCK_KEY,
                                   checks="FROM waitlist_signups")


def test_the_join_takes_no_advisory_lock_off_postgresql(sessions):
    """SQLite has no ``pg_advisory_xact_lock``: off PostgreSQL the join runs under ``_join_lock`` alone."""
    statements: list[tuple[str, dict]] = []
    with _recorded(sessions(), statements) as db:
        waitlist_service.create_signup(db, email="joiner@example.com", name=None, referral_code=None, source=None)
    assert not any("advisory" in sql for sql, _ in statements), statements


def test_a_credit_committed_after_the_join_read_its_referrer_is_kept(sessions):
    """Another join's credit commits once this join has read its referrer and before it writes its own. A write of
    the score this join read plus one would overwrite it."""
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()
    credited: list[bool] = []

    def credit_after_the_referrer_read(state):
        sql = str(state.statement)
        if credited or not state.is_select or "waitlist_signups.referral_code =" not in sql:
            return None
        read = state.invoke_statement().freeze()
        with sessions() as other:
            other.query(WaitlistSignup).filter_by(referral_code="refcode0").update(
                {WaitlistSignup.priority_score: WaitlistSignup.priority_score + 1}, synchronize_session=False)
            other.commit()
        credited.append(True)
        return read()

    with sessions() as db:
        event.listen(db, "do_orm_execute", credit_after_the_referrer_read)
        joined = waitlist_service.create_signup(db, email="joiner@example.com", name=None, referral_code="refcode0",
                                                source=None)
        assert credited and joined.referrer.priority_score == 2
    with sessions() as db:
        assert db.query(WaitlistSignup).filter_by(referral_code="refcode0").one().priority_score == 2
