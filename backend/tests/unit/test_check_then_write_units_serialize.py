"""Gate for lessons/ops-release-cached-filing-reads-before-yield.md's serialization clause: a
check-then-write unit moved into the thread pool holds a lock from its check to its commit, or writes
atomically in the database.

On the event loop each of these units ran whole before the next could start. In worker threads two
requests can both pass a check before either writes, so each unit below takes a lock from its check to
its commit (two account writes, at the end, write atomically instead):
- the waitlist join (``waitlist_service._join_lock``): two joins on one referral link both read the
  referrer's priority and one credit is lost, and two joins both count the list before either
  inserts and take one place;
- the watch-row writes (``watchlist_service.watch_row_lock``): two enables of an earnings alert both
  pass the plan cap, two adds of one company (or an add and an enable) both pass the duplicate check
  and write two rows, two removes both find the row, and a disable updates a row a remove deleted;
- the saved-row writes (``saved_summary_service.saved_row_lock``): two saves of one summary both pass
  the duplicate check and store it twice, two deletes both find the row, and a notes update writes a
  row a delete removed.

Each case runs two units in threads on sessions configured as ``SessionLocal`` is, and meets them
inside the critical section, after each has made its check: each waits there until the other has
made its check too, or until the other is parked on the lock, which only a lock can do. Without the
lock both have checked before either writes, so the race happens however slow the host.
The watch-row and saved-row locks are also taken after the session's first query and must run no
new checkout inside them, so no holder waits for a pool slot that a waiter holds: each watch-row and
saved-row case fails a checkout made by the thread that holds the lock.

These locks reach one process. Each unit also takes a database lock that the API's instances share,
the watch-row and saved-row writes before the process lock and the join inside it;
``test_check_then_write_units_lock_across_instances.py`` holds those (E128).

Two account writes take no lock: each writes atomically in the database, the clause's other way, which
reaches every instance and the alert scanner as well. A first read of an account's alert preferences
inserts their row under a SAVEPOINT and reads the stored row when its insert clashes on the unique
``user_id``, and the bell's mark writes its stamp only over an older one. Their cases meet the two units
after their checks (two first reads; a first read and a first update, which inserts once the read has
committed), or park the mark stamped first at its UPDATE until the later one has committed, and hold the
outcome.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.database import Base
from app.models import (
    Company, Filing, NotificationPreferences, SavedSummary, Summary, User, WaitlistSignup, Watchlist,
)
from app.services import (
    earnings_alert_service, notification_service, saved_summary_service, user_notification_feed_service,
    waitlist_service, watchlist_service,
)
from app.utils.datetimes import utcnow

# Exercise existing collection behavior with an explicitly published synthetic operator notice.
pytestmark = pytest.mark.usefixtures("collection_ready")


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'check-then-write.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)  # as app.database.SessionLocal


class _Meeting:
    """Stands in for a unit's lock and lets two units meet inside it.

    ``meet`` waits until the other unit has arrived too, or is parked on the lock, which it can be
    only while this one holds it. So a run without the lock always meets inside the unit, however
    slow the host, and a run with it never waits for a timeout. Also records which thread holds the
    lock, so a checkout made inside it can be failed."""

    def __init__(self, lock) -> None:
        self._lock = lock if hasattr(lock, "acquire") else None  # a stand-in with no lock: nothing to park on
        self._state = threading.Condition()
        self._arrived = 0
        self._parked = 0
        self.holder: int | None = None

    def __enter__(self) -> "_Meeting":
        if self._lock is not None and not self._lock.acquire(blocking=False):
            with self._state:
                self._parked += 1
                self._state.notify_all()
            self._lock.acquire()
            with self._state:
                self._parked -= 1
        self.holder = threading.get_ident()
        return self

    def __exit__(self, *exc_info) -> None:
        self.holder = None
        if self._lock is not None:
            self._lock.release()

    @property
    def arrivals(self) -> int:
        with self._state:
            return self._arrived

    def meet(self) -> None:
        with self._state:
            self._arrived += 1
            self._state.notify_all()
            assert self._state.wait_for(lambda: self._arrived >= 2 or self._parked > 0, timeout=10)

    def wait_for(self, done: threading.Event) -> None:
        """Wait until ``done`` is set or the other unit is parked on the lock."""
        with self._state:
            assert self._state.wait_for(lambda: done.is_set() or self._parked > 0, timeout=10)

    def wake(self) -> None:
        with self._state:
            self._state.notify_all()


def _meet_after(monkeypatch, meeting: _Meeting, module, name: str) -> None:
    """Make ``module.name``, a unit's check, meet the other unit once it has run: both units then
    hold their check's answer before either writes."""
    real = getattr(module, name)

    def check_then_meet(*args, **kwargs):
        answer = real(*args, **kwargs)
        meeting.meet()
        return answer

    monkeypatch.setattr(module, name, check_then_meet)


@pytest.fixture
def watch_rows(monkeypatch, engine):
    """The watch-row lock wrapped in a meeting, in both modules that take it, failing any checkout
    its holder makes while it holds it."""
    meeting = _Meeting(watchlist_service.watch_row_lock)
    monkeypatch.setattr(watchlist_service, "watch_row_lock", meeting)
    monkeypatch.setattr(earnings_alert_service, "watch_row_lock", meeting)
    inside: list[bool] = []
    event.listen(engine, "checkout", lambda *_: inside.append(meeting.holder == threading.get_ident()))
    yield meeting
    assert inside and not any(inside), "a checkout ran inside the watch-row lock"


@pytest.fixture
def saved_rows(monkeypatch, engine):
    """The saved-row lock wrapped in a meeting, failing any checkout its holder makes while it holds it."""
    meeting = _Meeting(saved_summary_service.saved_row_lock)
    monkeypatch.setattr(saved_summary_service, "saved_row_lock", meeting)
    inside: list[bool] = []
    event.listen(engine, "checkout", lambda *_: inside.append(meeting.holder == threading.get_ident()))
    yield meeting
    assert inside and not any(inside), "a checkout ran inside the saved-row lock"


def _run_both(first, second) -> list:
    """Run two units in threads; each returns its result, or the exception it raised."""

    def outcome(unit):
        try:
            return unit()
        except Exception as exc:  # noqa: BLE001 - the outcome under test may be a refusal
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        return [future.result(timeout=20) for future in (pool.submit(outcome, first), pool.submit(outcome, second))]


def _kinds(outcomes: list) -> list[str]:
    return sorted(type(outcome).__name__ for outcome in outcomes)


@pytest.mark.parametrize("referral_code", ["refcode0", None])
def test_two_joins_each_take_a_place_and_credit_their_referrer(sessions, monkeypatch, referral_code):
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()
    meeting = _Meeting(waitlist_service._join_lock)
    monkeypatch.setattr(waitlist_service, "_join_lock", meeting)
    _meet_after(monkeypatch, meeting, waitlist_service, "count_signups")

    def join(email: str):
        def unit():
            with sessions() as db:
                joined = waitlist_service.create_signup(
                    db, email=email, name=None, referral_code=referral_code, source=None)
                return joined.signup.position
        return unit

    positions = _run_both(join("first@example.com"), join("second@example.com"))
    with sessions() as db:
        referrer = db.query(WaitlistSignup).filter_by(email="referrer@example.com").one()
        assert (referrer.priority_score, sorted(positions)) == (2 if referral_code else 0, [2, 3])


def _watcher(sessions, *, alerts_on: int = 0, watched: bool = False) -> None:
    """A Free account (cap 3) and four companies; ``alerts_on`` of them have its alert on, and
    ``watched`` puts CAP3 on its watchlist with the alert on."""
    with sessions() as db:
        user = User(email="watcher@example.com", is_active=True)
        db.add(user)
        companies = [Company(cik=f"{i + 1:010d}", ticker=f"CAP{i}", name=f"Capped {i}") for i in range(4)]
        db.add_all(companies)
        db.flush()
        db.add_all(Watchlist(user_id=user.id, company_id=company.id, earnings_alert=True)
                   for company in companies[:alerts_on])
        if watched:
            db.add(Watchlist(user_id=user.id, company_id=companies[3].id, earnings_alert=True))
        db.commit()


def _as_watcher(sessions, unit):
    """Run ``unit(db, user)`` on a session whose first query, the user's lookup, has already checked
    a connection out, as the route's auth dependency has."""

    def run():
        with sessions() as db:
            user = db.query(User).filter_by(email="watcher@example.com").one()
            return unit(db, user)
    return run


def _rows(sessions, company_id: int) -> list[bool]:
    with sessions() as db:
        return [alert for (alert,) in db.query(Watchlist.earnings_alert).filter_by(user_id=1, company_id=company_id)]


def test_two_alert_enables_at_the_cap_take_its_last_slot_once(sessions, monkeypatch, watch_rows):
    _watcher(sessions, alerts_on=2)
    _meet_after(monkeypatch, watch_rows, earnings_alert_service, "count_enabled")

    def enable(ticker: str):
        return _as_watcher(sessions, lambda db, user: earnings_alert_service.set_earnings_alert(
            db, user, ticker, enabled=True))

    assert _kinds(_run_both(enable("CAP2"), enable("CAP3"))) == ["EarningsAlertLimitError", "bool"]
    with sessions() as db:
        assert earnings_alert_service.count_enabled(db, 1) == 3


def test_two_adds_of_one_company_keep_one_watch_row(sessions, monkeypatch, watch_rows):
    _watcher(sessions)
    _meet_after(monkeypatch, watch_rows, watchlist_service, "_watched")
    add = _as_watcher(sessions, lambda db, user: watchlist_service.add_company(db, user.id, "CAP3"))

    assert _kinds(_run_both(add, add)) == ["AddedWatch", "AlreadyOnWatchlist"]
    assert _rows(sessions, 4) == [False]


def test_an_add_and_an_alert_enable_of_one_company_keep_one_watch_row(sessions, monkeypatch, watch_rows):
    _watcher(sessions)
    _meet_after(monkeypatch, watch_rows, watchlist_service, "_watched")
    _meet_after(monkeypatch, watch_rows, earnings_alert_service, "count_enabled")
    add = _as_watcher(sessions, lambda db, user: watchlist_service.add_company(db, user.id, "CAP3"))
    enable = _as_watcher(sessions, lambda db, user: earnings_alert_service.set_earnings_alert(
        db, user, "CAP3", enabled=True))

    outcomes = _run_both(add, enable)
    # One row, its alert on: the enable either added it or switched on the add's.
    assert _rows(sessions, 4) == [True]
    assert _kinds(outcomes) in (["AddedWatch", "bool"], ["AlreadyOnWatchlist", "bool"])


def test_two_removes_of_one_company_delete_it_once(sessions, monkeypatch, watch_rows):
    _watcher(sessions, watched=True)
    _meet_after(monkeypatch, watch_rows, watchlist_service, "_watched")
    remove = _as_watcher(sessions, lambda db, user: watchlist_service.remove_company(db, user.id, "CAP3"))

    assert _kinds(_run_both(remove, remove)) == ["NoneType", "NotOnWatchlist"]
    assert _rows(sessions, 4) == []


def test_an_alert_disable_and_a_remove_of_one_company_both_finish(sessions, monkeypatch, watch_rows):
    """The disable reads the row, and only once the remove has deleted it (or is parked on the
    lock) does it update: without the lock the update matches no row."""
    _watcher(sessions, watched=True)
    removed = threading.Event()
    real_remove = watchlist_service.remove_company

    def remove_company(*args, **kwargs):
        try:
            return real_remove(*args, **kwargs)
        finally:
            removed.set()
            watch_rows.wake()

    monkeypatch.setattr(watchlist_service, "remove_company", remove_company)
    _meet_after(monkeypatch, watch_rows, watchlist_service, "_watched")
    real_read = earnings_alert_service._watch_row_for_ticker

    def read_then_wait(*args, **kwargs):
        row = real_read(*args, **kwargs)
        watch_rows.meet()
        watch_rows.wait_for(removed)
        return row

    monkeypatch.setattr(earnings_alert_service, "_watch_row_for_ticker", read_then_wait)
    remove = _as_watcher(sessions, lambda db, user: watchlist_service.remove_company(db, user.id, "CAP3"))
    disable = _as_watcher(sessions, lambda db, user: earnings_alert_service.set_earnings_alert(
        db, user, "CAP3", enabled=False))

    # Either order is fine; neither may fail on a row the other changed under it.
    assert _kinds(_run_both(remove, disable)) == ["NoneType", "bool"]
    assert _rows(sessions, 4) == []


def _reader(sessions, *, saved: bool = False) -> None:
    """An account and a filing's summary (summary 1); ``saved`` puts it in the account's library (row 1)
    with the notes "Kept"."""
    with sessions() as db:
        user = User(email="reader@example.com", is_active=True)
        company = Company(cik="0000000001", ticker="LIB", name="Library Co")
        db.add_all([user, company])
        db.flush()
        filing = Filing(company_id=company.id, accession_number="library-0", filing_type="10-Q",
                        filing_date=utcnow(), sec_url="https://sec.example/", document_url="https://sec.example/doc")
        db.add(filing)
        db.flush()
        summary = Summary(filing_id=filing.id, business_overview="Overview")
        db.add(summary)
        db.flush()
        if saved:
            db.add(SavedSummary(user_id=user.id, summary_id=summary.id, notes="Kept"))
        db.commit()


def _as_reader(sessions, unit):
    """Run ``unit(db, user)`` on a session whose first query, the user's lookup, has already checked
    a connection out, as the route's auth dependency has."""

    def run():
        with sessions() as db:
            user = db.query(User).filter_by(email="reader@example.com").one()
            return unit(db, user)
    return run


def _library(sessions) -> list:
    """The notes of each row in the account's library."""
    with sessions() as db:
        return [notes for (notes,) in db.query(SavedSummary.notes).filter_by(user_id=1)]


def test_two_saves_of_one_summary_keep_one_library_row(sessions, monkeypatch, saved_rows):
    _reader(sessions)
    _meet_after(monkeypatch, saved_rows, saved_summary_service, "_saved")
    save = _as_reader(sessions, lambda db, user: saved_summary_service.save_summary(
        db, user_id=user.id, summary_id=1, notes=None))

    outcomes = _run_both(save, save)
    # The second save found the first's row and answers it.
    assert _kinds(outcomes) == ["dict", "dict"] and outcomes[0]["id"] == outcomes[1]["id"], outcomes
    assert _library(sessions) == [None]


def test_two_deletes_of_one_library_row_delete_it_once(sessions, monkeypatch, saved_rows):
    _reader(sessions, saved=True)
    _meet_after(monkeypatch, saved_rows, saved_summary_service, "_owned")
    delete = _as_reader(sessions, lambda db, user: saved_summary_service.delete_saved_summary(
        db, user_id=user.id, saved_summary_id=1))

    assert sorted(_run_both(delete, delete), key=repr) == [False, True]
    assert _library(sessions) == []


def test_a_notes_update_and_a_delete_of_one_library_row_both_finish(sessions, monkeypatch, saved_rows):
    """The update reads the row, and only once the delete has removed it (or is parked on the lock)
    does it write: without the lock its UPDATE matches no row."""
    _reader(sessions, saved=True)
    deleted = threading.Event()
    real_delete = saved_summary_service.delete_saved_summary

    def delete_saved_summary(*args, **kwargs):
        try:
            return real_delete(*args, **kwargs)
        finally:
            deleted.set()
            saved_rows.wake()

    monkeypatch.setattr(saved_summary_service, "delete_saved_summary", delete_saved_summary)
    _meet_after(monkeypatch, saved_rows, saved_summary_service, "_owned")
    real_read = saved_summary_service._owned_library_row

    def read_then_wait(*args, **kwargs):
        row = real_read(*args, **kwargs)
        saved_rows.meet()
        saved_rows.wait_for(deleted)
        return row

    monkeypatch.setattr(saved_summary_service, "_owned_library_row", read_then_wait)
    delete = _as_reader(sessions, lambda db, user: saved_summary_service.delete_saved_summary(
        db, user_id=user.id, saved_summary_id=1))
    update = _as_reader(sessions, lambda db, user: saved_summary_service.update_saved_summary_notes(
        db, user_id=user.id, saved_summary_id=1, notes="Edited"))

    # Either order is fine: the update edits the row before the delete removes it, or finds it gone.
    deleted_once, updated = _run_both(delete, update)
    edited = isinstance(updated, dict) and updated["notes"] == "Edited"
    assert deleted_once is True and (updated is None or edited), (deleted_once, updated)
    assert _library(sessions) == []


def _account(sessions, *, seen_at: datetime | None = None) -> None:
    """An account (user 1) with no alert preferences, and the bell stamp ``seen_at``."""
    with sessions() as db:
        db.add(User(email="account@example.com", is_active=True, notifications_seen_at=seen_at))
        db.commit()


def _as_account(sessions, unit):
    """Run ``unit(db, user)`` on a session whose first query, the user's lookup, has already checked a
    connection out, as the route's auth dependency has."""

    def run():
        with sessions() as db:
            user = db.query(User).filter_by(email="account@example.com").one()
            return unit(db, user)
    return run


def test_two_first_reads_of_one_accounts_preferences_keep_one_row(sessions, monkeypatch):
    """Both reads find no row before either inserts. The second insert's clash on the unique ``user_id``
    rolls back only that insert, under its SAVEPOINT, and it answers the row the first stored: without
    the SAVEPOINT its commit raises IntegrityError, a 500."""
    _account(sessions)
    meeting = _Meeting(None)
    _meet_after(monkeypatch, meeting, notification_service, "_preferences")
    read = _as_account(sessions, lambda db, user: notification_service.get_or_create_preferences(db, user.id).id)

    assert _run_both(read, read) == [1, 1]
    # Both checks ran through the named check and met there: a check made some other way would race freely.
    assert meeting.arrivals >= 2
    with sessions() as db:
        assert db.query(NotificationPreferences.user_id).all() == [(1,)]


def test_a_first_read_and_a_first_update_of_one_accounts_preferences_both_finish(sessions, monkeypatch):
    """Both find no row before either inserts, and the update inserts once the read has committed. Its
    clash rolls back only its insert, under its SAVEPOINT, and it updates the stored row: without the
    SAVEPOINT on the update's path (``commit=False``) its failed flush leaves the session unusable, a
    500."""
    _account(sessions)
    meeting = _Meeting(None)
    read_committed = threading.Event()
    role = threading.local()
    real = notification_service._preferences

    def check_then_order(db, user_id):
        answer = real(db, user_id)
        if not getattr(role, "checked", False):
            role.checked = True
            meeting.meet()
            if role.name == "update":
                assert read_committed.wait(timeout=10)
        return answer

    monkeypatch.setattr(notification_service, "_preferences", check_then_order)

    def read(db, user):
        role.name = "read"
        try:
            return notification_service.get_or_create_preferences(db, user.id).notify_10q
        finally:
            read_committed.set()

    def update(db, user):
        role.name = "update"
        prefs = notification_service.get_or_create_preferences(db, user.id, commit=False)
        notification_service.apply_preference_update(db, prefs, {"notify_10q": False}, user)
        return prefs.notify_10q

    # The read answers the defaults it stored, and the update its change, on that one row.
    assert _run_both(_as_account(sessions, read), _as_account(sessions, update)) == [True, False]
    assert meeting.arrivals >= 2
    with sessions() as db:
        assert db.query(NotificationPreferences.user_id, NotificationPreferences.notify_10q).all() == [(1, False)]


def test_a_mark_stamped_first_that_commits_last_keeps_the_later_stamp(sessions, engine, monkeypatch):
    """Two marks of one account's bell over an older stamp. The one stamped first makes its check and
    reaches its UPDATE before the other starts, and runs that UPDATE only once the other has committed.
    That UPDATE writes the stamp only over an older one, so the later stamp stands: a plain write, or a
    check in Python before an unconditional write, puts the earlier one back, and an alert logged between
    the two stamps reads unread again; a write only over an unset stamp never moves an old one."""
    older = datetime(2026, 10, 24, 11, 0, tzinfo=timezone.utc)
    first, later = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc), datetime(2026, 10, 24, 12, 1, tzinfo=timezone.utc)
    _account(sessions, seen_at=older)
    first_parked, later_committed = threading.Event(), threading.Event()
    clock = threading.local()
    monkeypatch.setattr(user_notification_feed_service, "utcnow", lambda: clock.stamp)

    def park_the_first_update(conn, cursor, statement, *_args):
        if getattr(clock, "parks", False) and statement.lstrip().upper().startswith("UPDATE USERS"):
            first_parked.set()
            assert later_committed.wait(timeout=10)

    event.listen(engine, "before_cursor_execute", park_the_first_update)

    def mark(stamp: datetime, parks: bool):
        def unit(db, user):
            clock.stamp, clock.parks = stamp, parks
            try:
                if not parks:
                    # Any check the first mark makes before its UPDATE has read the older stamp by now.
                    assert first_parked.wait(timeout=10)
                return user_notification_feed_service.mark_seen(db, user).notifications_seen_at
            finally:
                if not parks:
                    later_committed.set()
        return _as_account(sessions, unit)

    # SQLite hands the stamps back naive.
    assert _run_both(mark(first, True), mark(later, False)) == [later.replace(tzinfo=None)] * 2
    with sessions() as db:
        assert db.query(User.notifications_seen_at).scalar() == later.replace(tzinfo=None)
