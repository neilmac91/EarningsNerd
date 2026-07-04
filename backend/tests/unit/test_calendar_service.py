"""Upcoming-earnings calendar: DB-backed (earnings_events), filtered to watched tickers, in-window."""
import uuid
from contextlib import contextmanager
from datetime import date, timedelta

import pytest

from app.services.calendar_service import upcoming_for_user


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@contextmanager
def _user_watching(tickers):
    """Create a user watching `tickers` (companies created too). Yields (uid, cleanup-tracked)."""
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


def _seed_event(ticker, event_date, *, eps=1.0, time="amc"):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    ev = EarningsEvent(
        ticker=ticker.upper(),
        company_name=f"{ticker} Inc",
        fiscal_period_end=date(2026, 3, 31),
        event_date=event_date,
        event_time=time,
        status="estimated",
        confidence="medium",
        eps_estimate=eps,
        source="alpha_vantage",
    )
    db.add(ev)
    db.commit()
    db.close()


def _clear_events(*tickers):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    db.query(EarningsEvent).filter(EarningsEvent.ticker.in_([t.upper() for t in tickers])).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_only_watched_tickers_returned_sorted():
    from app.database import SessionLocal

    today = date.today()
    _clear_events("AAPL", "MSFT", "ZZZZ")
    _seed_event("AAPL", today + timedelta(days=10))
    _seed_event("MSFT", today + timedelta(days=2))   # watched, sooner
    _seed_event("ZZZZ", today + timedelta(days=5))   # not watched
    try:
        with _user_watching(["AAPL", "MSFT"]) as uid:
            db = SessionLocal()
            events = await upcoming_for_user(db, uid, days_ahead=30)
            db.close()

        tickers = [e["ticker"] for e in events]
        assert tickers == ["MSFT", "AAPL"]  # filtered to watched, soonest first
        assert all(e["ticker"] != "ZZZZ" for e in events)
        assert events[0]["earnings_date"] == (today + timedelta(days=2)).isoformat()
        # Contract preserved: revenue_estimated key still present (always None now).
        assert events[0]["revenue_estimated"] is None
        assert events[0]["eps_estimated"] == 1.0
    finally:
        _clear_events("AAPL", "MSFT", "ZZZZ")


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_out_of_window_excluded():
    from app.database import SessionLocal

    today = date.today()
    _clear_events("AAPL")
    _seed_event("AAPL", today + timedelta(days=40))  # beyond a 30-day horizon
    try:
        with _user_watching(["AAPL"]) as uid:
            db = SessionLocal()
            events = await upcoming_for_user(db, uid, days_ahead=30)
            db.close()
        assert events == []
    finally:
        _clear_events("AAPL")


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_empty_when_no_events():
    from app.database import SessionLocal

    _clear_events("AAPL")
    with _user_watching(["AAPL"]) as uid:
        db = SessionLocal()
        events = await upcoming_for_user(db, uid, days_ahead=30)
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
        events = await upcoming_for_user(db, uid)
        assert events == []
    finally:
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_upcoming_not_filtered_by_index_membership(monkeypatch):
    """Decision: the index filter is a DISCOVERY-surface concern only. A company a user has
    explicitly watchlisted still shows in their dashboard 'upcoming' even when it's outside the
    S&P 500 / Nasdaq 100 and the filter is on."""
    from app.database import SessionLocal
    from app.config import settings
    from app.services import index_membership_service as idx

    monkeypatch.setattr(idx, "_MEMBER_TICKERS", frozenset({"BIGCAPX"}))  # TAILWCH is NOT a member
    monkeypatch.setattr(settings, "CALENDAR_INDEX_FILTER_ENABLED", True)

    _clear_events("TAILWCH")
    with _user_watching(["TAILWCH"]) as uid:
        _seed_event("TAILWCH", date.today() + timedelta(days=5))
        db = SessionLocal()
        try:
            events = await upcoming_for_user(db, uid, days_ahead=30)
        finally:
            db.close()
        assert any(e["ticker"] == "TAILWCH" for e in events), "watched non-member must still appear"
    _clear_events("TAILWCH")
