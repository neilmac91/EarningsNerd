"""Upcoming-earnings calendar: filtered to watched tickers, graceful when FMP is unconfigured."""
import uuid
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.calendar_service import upcoming_for_user


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


class _FakeFMP:
    def __init__(self, events):
        self._events = events

    async def fetch_upcoming_earnings(self, days_ahead=14):
        return self._events


def _event(d, time="amc", eps=1.0, rev=1e9):
    return SimpleNamespace(earnings_date=d, time=time, eps_estimated=eps, revenue_estimated=rev)


@contextmanager
def _user_watching(tickers):
    from app.database import SessionLocal
    from app.models import Company, User, Watchlist

    db = SessionLocal()
    suffix = uuid.uuid4().hex[:8]
    user = User(email=f"cal-{suffix}@example.com", hashed_password="x", email_verified=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    company_ids = []
    for i, t in enumerate(tickers):
        c = Company(cik=f"cik{suffix}{i}", ticker=t, name=f"{t} Inc")
        db.add(c)
        db.commit()
        db.refresh(c)
        db.add(Watchlist(user_id=user.id, company_id=c.id))
        company_ids.append(c.id)
    db.commit()
    uid = user.id
    db.close()
    try:
        yield uid
    finally:
        db = SessionLocal()
        from app.models import Company, User, Watchlist
        db.query(Watchlist).filter(Watchlist.user_id == uid).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_only_watched_tickers_returned_sorted():
    from app.database import SessionLocal

    fmp = _FakeFMP({
        "AAPL": _event(date(2026, 7, 10)),
        "MSFT": _event(date(2026, 7, 2)),   # watched, sooner
        "ZZZZ": _event(date(2026, 7, 5)),   # not watched
    })
    with _user_watching(["AAPL", "MSFT"]) as uid:
        db = SessionLocal()
        events = await upcoming_for_user(db, uid, fmp=fmp, days_ahead=30)
        db.close()

    tickers = [e["ticker"] for e in events]
    assert tickers == ["MSFT", "AAPL"]  # filtered to watched, soonest first
    assert all(e["ticker"] != "ZZZZ" for e in events)
    assert events[0]["earnings_date"] == "2026-07-02"


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_empty_when_fmp_unconfigured():
    from app.database import SessionLocal

    with _user_watching(["AAPL"]) as uid:
        db = SessionLocal()
        events = await upcoming_for_user(db, uid, fmp=_FakeFMP({}), days_ahead=30)
        db.close()
    assert events == []


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_empty_when_no_watchlist():
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    user = User(email=f"cal-empty-{uuid.uuid4().hex}@example.com", hashed_password="x", email_verified=True)
    db.add(user)
    db.commit()
    uid = user.id
    try:
        events = await upcoming_for_user(db, uid, fmp=_FakeFMP({"AAPL": _event(date(2026, 7, 10))}))
        assert events == []
    finally:
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()
