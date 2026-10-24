"""E128: the check-then-write units that a process lock serializes within one instance also take, before their
check, a database lock that every instance shares, and hold it to the commit that carries their write. The API runs
up to two instances, and a process lock reaches one, so across them two alert enables at the cap could both pass it,
two adds could both write a row, a referral credit could be lost and two joins could take one place.

- The watch-row writes (an add, a remove, an earnings alert's enable and disable) take the account's users row lock
  (``watchlist_service.lock_watch_rows``) before their first read of the watchlist, and before ``watch_row_lock``:
  a unit that waits on one account's row then holds no process lock that other accounts' writes would wait on.
- The saved-row writes (a save, a notes update, a delete) take the same lock (``saved_summary_service.lock_saved_rows``)
  before their first read of the library, and before ``saved_row_lock``, for the same reason; two saves of one summary
  across instances could otherwise store it twice.
- The waitlist join takes the waitlist's place lock (``waitlist_service._lock_waitlist_places``, a transaction-level
  advisory lock) before its first read of the signups, under ``_join_lock``, which a waiter takes before its first
  query and so waits on holding no connection.
- The join's credit is one UPDATE that adds to the stored score, so a credit committed after the join read its
  referrer is kept.
- The reads beside them take no lock: no row lock of any strength, and no advisory lock.

SQLite omits ``FOR UPDATE`` and has no advisory locks, so the lock cases read the statements each unit's session
runs, compiled for PostgreSQL. The join's run on an engine whose dialect calls itself PostgreSQL, with a stand-in
for ``pg_advisory_xact_lock``. ``test_check_then_write_units_serialize.py`` holds the process locks; no CI step races
two instances on PostgreSQL.
"""
import re
from typing import NamedTuple

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app import database
from app.models import Base, Company, Filing, SavedSummary, Summary, User, WaitlistSignup, Watchlist
from app.services import earnings_alert_service, saved_summary_service, waitlist_service, watchlist_service
from app.utils.datetimes import utcnow

# Exercise existing collection behavior with an explicitly published synthetic operator notice.
pytestmark = pytest.mark.usefixtures("collection_ready")

# Apart from the company ids, so a lock taken by a company's id in place of the account's fails.
USER_ID = 1000
# "WAITLIST" in ASCII, pinned here rather than read from the module under test, so a changed key fails.
PLACE_LOCK_KEY = int.from_bytes(b"WAITLIST", "big")
# Each of PostgreSQL's row-locking clauses, so a read that locks a row at another strength, or another row, fails too.
ROW_LOCK = re.compile(r"\bFOR (?:UPDATE|NO KEY UPDATE|SHARE|KEY SHARE)\b")


class Recorded(NamedTuple):
    """One statement the session ran, compiled for PostgreSQL, or a ``-- flush``, ``-- commit`` or ``-- rollback``
    marker; a flush's params name the models it writes, by kind."""
    sql: str
    params: dict
    process_lock_held: bool = False


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


def _recorded(session, statements: list[Recorded], process_lock=None):
    """``session``, recording each ORM statement it runs, with its parameters, each flush with the models it writes,
    and each end of a transaction, each with whether ``process_lock`` (``watch_row_lock`` unless named) was held as it
    ran."""
    held = process_lock or watchlist_service.watch_row_lock

    def record(state) -> None:
        compiled = state.statement.compile(dialect=postgresql.dialect())
        statements.append(Recorded(str(compiled), {**compiled.params, **(state.parameters or {})}, held.locked()))

    def flushing(flushed, _context, _instances) -> None:
        statements.append(Recorded("-- flush", {
            kind: {type(instance).__name__ for instance in getattr(flushed, kind)}
            for kind in ("new", "dirty", "deleted")
        }, held.locked()))

    event.listen(session, "do_orm_execute", record)
    event.listen(session, "before_flush", flushing)
    event.listen(session, "after_commit", lambda _session: statements.append(Recorded("-- commit", {}, held.locked())))
    event.listen(session, "after_rollback",
                 lambda _session: statements.append(Recorded("-- rollback", {}, held.locked())))
    return session


def _assert_holds_the_lock_from_its_check_to_its_write(
    statements: list[Recorded], *, lock, lock_value, checks: str, writes: tuple[str, str],
) -> int:
    """The first statement that reads ``checks`` follows the lock ``lock`` names, taken on ``lock_value`` and waiting
    for its holder, and the first end of a transaction after the lock is the commit that carries the unit's write: a
    flush of a ``writes`` (kind, model) pair comes between them. So nothing releases the lock between the check and
    the write. Returns the lock's index."""
    shown = "\n".join(f"{s.sql} {s.params if s.sql == '-- flush' else ''}" for s in statements)
    locks = [i for i, s in enumerate(statements) if lock(s.sql) and lock_value in s.params.values()]
    assert locks, shown
    reads = [i for i, s in enumerate(statements) if checks in s.sql]
    ends = [i for i, s in enumerate(statements) if i > locks[0] and s.sql in ("-- commit", "-- rollback")]
    assert reads and ends and locks[0] < reads[0] < ends[0], shown
    assert statements[ends[0]].sql == "-- commit", shown
    kind, model = writes
    assert any(s.sql == "-- flush" and model in s.params[kind] for s in statements[locks[0]:ends[0]]), shown
    return locks[0]


def _users_row_lock(sql: str) -> bool:
    """The account's users row, locked FOR NO KEY UPDATE and waiting for its holder (no SKIP LOCKED, no NOWAIT)."""
    return "FROM users" in sql and sql.rstrip().endswith("FOR NO KEY UPDATE")


def _place_lock(sql: str) -> bool:
    """The waitlist's place lock: the transaction-level advisory lock that waits for its holder, not the
    session-level one, which a pooled connection would keep past the unit, and not a try that gives up."""
    return "pg_advisory_xact_lock(" in sql and "pg_try_" not in sql


def _takes_a_lock(statements: list[Recorded]) -> bool:
    """Any row lock, of any strength and on any table, or any advisory lock."""
    return any(ROW_LOCK.search(s.sql) or "advisory" in s.sql for s in statements)


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


def _watch_row_statements(sessions, unit) -> list[Recorded]:
    """The statements ``unit(db, user)`` runs, on a session whose first query, the user's lookup, ran before it, as
    the route's auth dependency's does."""
    statements: list[Recorded] = []
    with sessions() as db:
        user = db.get(User, USER_ID)
        _recorded(db, statements)
        unit(db, user)
    return statements


@pytest.mark.parametrize("unit, writes", [
    pytest.param(lambda db, user: watchlist_service.add_company(db, user.id, "CAP2"), ("new", "Watchlist"), id="add"),
    pytest.param(lambda db, user: watchlist_service.remove_company(db, user.id, "CAP3"), ("deleted", "Watchlist"),
                 id="remove"),
    pytest.param(lambda db, user: earnings_alert_service.set_earnings_alert(db, user, "CAP2", enabled=True),
                 ("new", "Watchlist"), id="alert enable"),
    pytest.param(lambda db, user: earnings_alert_service.set_earnings_alert(db, user, "CAP3", enabled=False),
                 ("dirty", "Watchlist"), id="alert disable"),
])
def test_each_watch_row_write_locks_the_account_before_it_checks(sessions, unit, writes):
    """Each write as it succeeds: CAP0 and CAP3 have the alert on, one slot short of the cap, and CAP2 is not
    watched. The account's lock comes before the process lock, so a unit that waits on it holds that lock for
    no other account."""
    _watcher(sessions, alerts_on=1, watched=True)
    statements = _watch_row_statements(sessions, unit)
    lock = _assert_holds_the_lock_from_its_check_to_its_write(
        statements, lock=_users_row_lock, lock_value=USER_ID, checks="FROM watchlist", writes=writes)
    assert not statements[lock].process_lock_held, "the account's lock was taken inside watch_row_lock"


def test_the_alert_enable_counts_the_cap_under_the_lock(sessions):
    """The cap count itself, not only the row read before it, comes after the lock."""
    _watcher(sessions, alerts_on=2)
    statements = _watch_row_statements(
        sessions, lambda db, user: earnings_alert_service.set_earnings_alert(db, user, "CAP2", enabled=True))
    _assert_holds_the_lock_from_its_check_to_its_write(
        statements, lock=_users_row_lock, lock_value=USER_ID, checks="count(distinct(watchlist.company_id))",
        writes=("new", "Watchlist"))


def test_the_watch_row_reads_take_no_lock(sessions):
    """The list, the insights and the alert reads beside the writes take no lock."""
    _watcher(sessions, alerts_on=1, watched=True)
    for read in (
        lambda db, user: watchlist_service.list_items(db, user.id),
        lambda db, user: watchlist_service.load_insight_rows(db, user.id),
        lambda db, user: earnings_alert_service.enabled_tickers(db, user.id),
        lambda db, user: earnings_alert_service.count_enabled(db, user.id),
    ):
        statements = _watch_row_statements(sessions, read)
        assert statements and not _takes_a_lock(statements), statements


def _reader(sessions, *, saved: bool) -> None:
    """The account and a filing's summary (summary 1); ``saved`` puts it in the account's library (row 1)."""
    with sessions() as db:
        db.add(User(id=USER_ID, email="reader@example.com", is_active=True))
        company = Company(cik="0000000001", ticker="LIB", name="Library Co")
        db.add(company)
        db.flush()
        filing = Filing(company_id=company.id, accession_number="library-0", filing_type="10-Q",
                        filing_date=utcnow(), sec_url="https://sec.example/", document_url="https://sec.example/doc")
        db.add(filing)
        db.flush()
        summary = Summary(filing_id=filing.id, business_overview="Overview")
        db.add(summary)
        db.flush()
        if saved:
            db.add(SavedSummary(user_id=USER_ID, summary_id=summary.id, notes="Kept"))
        db.commit()


def _saved_row_statements(sessions, unit) -> list[Recorded]:
    """As ``_watch_row_statements``, each entry recording whether ``saved_row_lock`` was held as it ran, and each pool
    checkout the unit makes as a ``-- checkout`` entry: the session's recorder sees its ORM statements, flushes and
    ends of transactions, not a checkout made through the session's connection."""
    statements: list[Recorded] = []
    held = saved_summary_service.saved_row_lock
    engine = sessions.kw["bind"]

    def checkout(*_args) -> None:
        statements.append(Recorded("-- checkout", {}, held.locked()))

    with sessions() as db:
        user = db.get(User, USER_ID)
        _recorded(db, statements, process_lock=held)
        event.listen(engine, "checkout", checkout)
        try:
            unit(db, user)
        finally:
            event.remove(engine, "checkout", checkout)
    return statements


@pytest.mark.parametrize("saved, unit, writes", [
    pytest.param(False, lambda db, user: saved_summary_service.save_summary(db, user_id=user.id, summary_id=1, notes=None),
                 ("new", "SavedSummary"), id="save"),
    pytest.param(True, lambda db, user: saved_summary_service.save_summary(db, user_id=user.id, summary_id=1,
                                                                           notes="Renoted"),
                 ("dirty", "SavedSummary"), id="save over a saved row"),
    pytest.param(True, lambda db, user: saved_summary_service.update_saved_summary_notes(
        db, user_id=user.id, saved_summary_id=1, notes="Edited"), ("dirty", "SavedSummary"), id="notes update"),
    pytest.param(True, lambda db, user: saved_summary_service.delete_saved_summary(db, user_id=user.id,
                                                                                   saved_summary_id=1),
                 ("deleted", "SavedSummary"), id="delete"),
])
def test_each_saved_row_write_locks_the_account_before_it_checks(sessions, saved, unit, writes):
    """Each write as it succeeds. The account's lock comes before the process lock, so a unit that waits on it holds
    that lock for no other account. The write's commit runs inside saved_row_lock, which within one process is the
    only serialization under SQLite, nothing runs there after it, and no connection is checked out inside it: a
    checkout there could wait for a pool slot that a waiter holds."""
    _reader(sessions, saved=saved)
    statements = _saved_row_statements(sessions, unit)
    shown = "\n".join(f"{s.sql[:90]} held={s.process_lock_held}" for s in statements)
    lock = _assert_holds_the_lock_from_its_check_to_its_write(
        statements, lock=_users_row_lock, lock_value=USER_ID, checks="FROM saved_summaries", writes=writes)
    assert not statements[lock].process_lock_held, "the account's lock was taken inside saved_row_lock"
    commit = next(i for i, s in enumerate(statements) if i > lock and s.sql in ("-- commit", "-- rollback"))
    assert statements[commit].process_lock_held, f"the write's commit ran outside saved_row_lock\n{shown}"
    assert not any(s.process_lock_held for s in statements[commit + 1:]), (
        f"something ran inside saved_row_lock after the write's commit\n{shown}")
    assert not any(s.sql == "-- checkout" and s.process_lock_held for s in statements), (
        f"a connection was checked out inside saved_row_lock\n{shown}")


def test_the_save_takes_no_lock_on_its_summary(sessions):
    """The save reads its summary without a row lock. Its bookmark's foreign-key check takes the summary's key-share
    lock at the INSERT, inside saved_row_lock, so a save of a summary an admin tool is deleting waits there (see
    saved_row_lock's comment). Taking that lock earlier, at the read before both locks, deadlocked a save over a saved
    row with the admin reset-all, which deletes the bookmarks before their summaries (40P01 in each order on
    PostgreSQL 16, E171's saved-summaries verification lens): a change to the save's lock order goes with the
    reset-all's."""
    _reader(sessions, saved=False)
    statements = _saved_row_statements(sessions, lambda db, user: saved_summary_service.save_summary(
        db, user_id=user.id, summary_id=1, notes=None))
    summary_reads = [s for s in statements if "FROM summaries" in s.sql]
    assert summary_reads and not any(ROW_LOCK.search(s.sql) for s in summary_reads), (
        "\n".join(s.sql for s in statements))


def test_the_saved_row_reads_take_no_lock(sessions):
    """The library list and the status read beside the writes take no lock."""
    _reader(sessions, saved=True)
    for read in (
        lambda db, user: saved_summary_service.list_saved_summaries(db, user.id),
        lambda db, user: saved_summary_service.saved_summary_status(db, user_id=user.id, summary_id=1),
    ):
        statements = _saved_row_statements(sessions, read)
        assert statements and not _takes_a_lock(statements), statements


def test_the_place_lock_key_is_waitlist_in_ascii():
    assert waitlist_service.WAITLIST_PLACE_LOCK_KEY == PLACE_LOCK_KEY


@pytest.mark.parametrize("referral_code", ["refcode0", None])
def test_the_join_takes_the_place_lock_before_it_reads_the_list(sessions, postgres_named, referral_code):
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()
    statements: list[Recorded] = []
    with _recorded(sessions(), statements) as db:
        waitlist_service.create_signup(db, email="joiner@example.com", name=None, referral_code=referral_code,
                                       source=None)
    _assert_holds_the_lock_from_its_check_to_its_write(
        statements, lock=_place_lock, lock_value=PLACE_LOCK_KEY, checks="FROM waitlist_signups",
        writes=("new", "WaitlistSignup"))


def test_the_waitlist_reads_take_no_lock(sessions, postgres_named):
    """The status read (the signup and its referral count) and the stats read take no lock, even where the
    dialect is PostgreSQL's."""
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()
    statements: list[Recorded] = []
    with _recorded(sessions(), statements) as db:
        signup = waitlist_service.find_signup_by_email(db, "referrer@example.com")
        waitlist_service.count_referrals(db, signup.referral_code)
        waitlist_service.count_signups(db)
    assert statements and not _takes_a_lock(statements), statements


def test_the_join_takes_no_advisory_lock_off_postgresql(sessions):
    """SQLite has no ``pg_advisory_xact_lock``: off PostgreSQL the join runs under ``_join_lock`` alone."""
    statements: list[Recorded] = []
    with _recorded(sessions(), statements) as db:
        waitlist_service.create_signup(db, email="joiner@example.com", name=None, referral_code=None, source=None)
    assert not any("advisory" in s.sql for s in statements), statements


def test_a_join_takes_the_place_after_the_highest_held(sessions):
    """A deleted signup leaves a gap the count would fill: with places 1 and 3 held, the next join takes 4, not 3."""
    with sessions() as db:
        db.add_all([WaitlistSignup(email=f"early{place}@example.com", referral_code=f"early00{place}",
                                   position=place, priority_score=0) for place in (1, 3)])
        db.commit()
    with sessions() as db:
        joined = waitlist_service.create_signup(db, email="joiner@example.com", name=None, referral_code=None,
                                                source=None)
        assert (joined.signup.position, joined.total_signups) == (4, 2)


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
