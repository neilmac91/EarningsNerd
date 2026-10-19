"""Gate for lessons/ops-release-cached-filing-reads-before-yield.md's serialization clause: a
check-then-write unit moved into the thread pool still runs one at a time within the process.

On the event loop each of these units ran whole before the next could start. In worker threads two
requests can both pass a check before either writes, so each unit takes a lock from its check to its
commit:
- the waitlist join (``waitlist_service._join_lock``): two joins on one referral link both read the
  referrer's priority and one credit is lost, and two plain joins both count the list before either
  inserts and take one position;
- the watch-row writes (``watchlist_service.watch_row_lock``): two enables of an earnings alert both
  pass the plan cap, and two adds of one company both pass the duplicate check.

Each case runs two units in threads and meets them at a barrier inside the critical section. Without
the lock both arrive and the race happens; with it the first waits out the barrier's timeout alone
and the second runs after its commit.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.database import Base
from app.models import Company, User, WaitlistSignup, Watchlist
from app.services import earnings_alert_service, waitlist_service, watchlist_service


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'check-then-write.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=4,
        max_overflow=0,
        pool_timeout=5.0,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine)
    engine.dispose()


def _meet_inside(monkeypatch, module, name: str) -> None:
    """Make ``module.name`` wait at a two-party barrier before it runs: both units meet there unless
    a lock keeps the second out, in which case the first waits out the timeout and goes on alone."""
    real = getattr(module, name)
    barrier = threading.Barrier(2, timeout=0.5)

    def meeting(*args, **kwargs):
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, meeting)


def _run_both(first, second) -> list:
    """Run two units in threads; each returns its result, or the exception it raised."""

    def outcome(unit):
        try:
            return unit()
        except Exception as exc:  # noqa: BLE001 - the outcome under test may be a refusal
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        return [future.result(timeout=10) for future in (pool.submit(outcome, first), pool.submit(outcome, second))]


@pytest.mark.parametrize("referral_code", ["refcode0", None])
def test_two_joins_each_take_a_place_and_credit_their_referrer(sessions, monkeypatch, referral_code):
    """Referred, each join must credit the referrer; plain, each must count the other's signup (the
    referrer's update serializes referred joins' counts on its own, so only plain joins share one)."""
    with sessions() as db:
        db.add(WaitlistSignup(email="referrer@example.com", referral_code="refcode0", position=1, priority_score=0))
        db.commit()
    _meet_inside(monkeypatch, waitlist_service, "count_signups")

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


def test_two_alert_enables_at_the_cap_take_its_last_slot_once(sessions, monkeypatch):
    with sessions() as db:
        user = User(email="capped@example.com", is_active=True)
        db.add(user)
        companies = [Company(cik=f"{i + 1:010d}", ticker=f"CAP{i}", name=f"Capped {i}") for i in range(4)]
        db.add_all(companies)
        db.flush()
        # A Free account (cap 3) with two alerts on, enabling its third and fourth at once.
        db.add_all(Watchlist(user_id=user.id, company_id=company.id, earnings_alert=True) for company in companies[:2])
        db.commit()
    _meet_inside(monkeypatch, earnings_alert_service, "count_enabled")

    def enable(ticker: str):
        def unit():
            with sessions() as db:
                reader = db.query(User).filter_by(email="capped@example.com").one()
                return earnings_alert_service.set_earnings_alert(db, reader, ticker, enabled=True)
        return unit

    outcomes = _run_both(enable("CAP2"), enable("CAP3"))
    assert sorted(type(outcome).__name__ for outcome in outcomes) == ["EarningsAlertLimitError", "bool"]
    with sessions() as db:
        assert earnings_alert_service.count_enabled(db, 1) == 3


def test_two_adds_of_one_company_keep_one_watch_row(sessions, monkeypatch):
    with sessions() as db:
        user = User(email="watcher@example.com", is_active=True)
        db.add_all([user, Company(cik="0000000001", ticker="CACHED", name="Cached fixture")])
        db.commit()
    _meet_inside(monkeypatch, watchlist_service, "_watched")

    def add():
        with sessions() as db:
            watchlist_item, _company = watchlist_service.add_company(db, 1, "CACHED")
            return watchlist_item.id

    outcomes = _run_both(add, add)
    assert sorted(type(outcome).__name__ for outcome in outcomes) == ["AlreadyOnWatchlist", "int"]
    with sessions() as db:
        assert db.query(Watchlist).filter_by(user_id=1, company_id=1).count() == 1
