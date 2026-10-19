"""Gate for lessons/ops-release-cached-filing-reads-before-yield.md's serialization clause: a
check-then-write unit moved into the thread pool still runs one at a time within the process.

On the event loop each of these units ran whole before the next could start. In worker threads two
requests can both pass a check before either writes, so each unit takes a lock from its check to its
commit:
- the waitlist join (``waitlist_service._join_lock``): two joins on one referral link both read the
  referrer's priority and one credit is lost, and two joins both count the list before either
  inserts and take one place;
- the watch-row writes (``watchlist_service.watch_row_lock``): two enables of an earnings alert both
  pass the plan cap, two adds of one company (or an add and an enable) both pass the duplicate check
  and write two rows, two removes both find the row, and a disable updates a row a remove deleted.

Each case runs two units in threads on sessions configured as ``SessionLocal`` is, and meets them
inside the critical section, after each has made its check: each waits there until the other has
made its check too, or until the other is parked on the lock, which only a lock can do. Without the
lock both have checked before either writes, so the race happens however slow the host.
The watch-row lock is also taken after the session's first query and must run no new checkout
inside it, so no holder waits for a pool slot that a waiter holds: each watch-row case fails a
checkout made by the thread that holds the lock.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.database import Base
from app.models import Company, User, WaitlistSignup, Watchlist
from app.services import earnings_alert_service, waitlist_service, watchlist_service


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
