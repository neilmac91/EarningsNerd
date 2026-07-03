"""Reporting-this-week: the current market week's events from earnings_events, ranked by
anticipation_score (the curated intersect is retired — the score carries the mega-cap floor).
Never raises."""
from datetime import date, timedelta

import pytest

from app.services.reporting_this_week_service import (
    ReportingThisWeekService,
    current_market_week,
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _seed(ticker, event_date, score, *, name=None, time="amc"):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    db.add(EarningsEvent(
        ticker=ticker.upper(),
        company_name=name or f"{ticker} Inc",
        fiscal_period_end=date(2026, 3, 31),
        event_date=event_date,
        event_time=time,
        status="estimated",
        confidence="medium",
        anticipation_score=score,
        source="alpha_vantage",
    ))
    db.commit()
    db.close()


def _clear_week():
    """Wipe events in the current market week so tests don't cross-contaminate."""
    from app.database import SessionLocal
    from app.models import EarningsEvent

    monday, friday = current_market_week()
    db = SessionLocal()
    db.query(EarningsEvent).filter(
        EarningsEvent.event_date >= monday, EarningsEvent.event_date <= friday
    ).delete(synchronize_session=False)
    db.commit()
    db.close()


def _new_db():
    from app.database import SessionLocal
    return SessionLocal()


# ---- pure market-week math (unchanged) ------------------------------------

def test_current_market_week_monday_to_friday():
    monday, friday = current_market_week(today=date(2026, 7, 1))  # a Wednesday
    assert monday == date(2026, 6, 29)
    assert friday == date(2026, 7, 3)


def test_current_market_week_stable_across_weekend():
    sat_monday, sat_friday = current_market_week(today=date(2026, 7, 4))
    sun_monday, sun_friday = current_market_week(today=date(2026, 7, 5))
    assert sat_monday == sun_monday == date(2026, 6, 29)
    assert sat_friday == sun_friday == date(2026, 7, 3)


# ---- DB-backed ranking ----------------------------------------------------

@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_ranked_by_anticipation_score():
    _clear_week()
    monday, _ = current_market_week()
    _seed("AAPL", monday + timedelta(days=1), score=1500)
    _seed("ZZZZ", monday, score=5)      # not curated — no longer excluded, just ranked last
    _seed("JPM", monday, score=1100)
    _seed("GOOGL", monday + timedelta(days=2), score=1300)
    try:
        db = _new_db()
        result = await ReportingThisWeekService().get_reporting_this_week(db)
        db.close()
        assert result["status"] == "ok"
        tickers = [c["ticker"] for c in result["companies"]]
        assert tickers == ["AAPL", "GOOGL", "JPM", "ZZZZ"]  # score desc; ZZZZ present but last
    finally:
        _clear_week()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_empty_status_when_no_events():
    _clear_week()
    db = _new_db()
    result = await ReportingThisWeekService().get_reporting_this_week(db)
    db.close()
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_below_minimum_count_treated_as_empty():
    _clear_week()
    monday, _ = current_market_week()
    _seed("AAPL", monday, score=1000)
    _seed("JPM", monday, score=900)  # only 2 — below MIN_COMPANIES (4)
    try:
        db = _new_db()
        result = await ReportingThisWeekService().get_reporting_this_week(db)
        db.close()
        assert result["companies"] == []
        assert result["status"] == "empty"
    finally:
        _clear_week()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_respects_limit():
    _clear_week()
    monday, _ = current_market_week()
    for i in range(10):
        _seed(f"T{i:02d}", monday, score=1000 - i)
    try:
        db = _new_db()
        result = await ReportingThisWeekService().get_reporting_this_week(db, limit=5)
        db.close()
        assert len(result["companies"]) == 5
    finally:
        _clear_week()


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_never_raises_on_query_error():
    # A broken session must degrade to empty, never raise.
    class _BrokenDB:
        def query(self, *a, **k):
            raise RuntimeError("boom")

    result = await ReportingThisWeekService().get_reporting_this_week(_BrokenDB())
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_cache_hit_avoids_refetch():
    _clear_week()
    monday, _ = current_market_week()
    for t, s in (("AAPL", 1000), ("JPM", 900), ("MSFT", 800), ("GOOGL", 700)):
        _seed(t, monday, score=s)
    try:
        svc = ReportingThisWeekService()
        calls = {"n": 0}
        original = svc._fetch

        def counting(db, mon, fri):
            calls["n"] += 1
            return original(db, mon, fri)

        svc._fetch = counting
        db = _new_db()
        first = await svc.get_reporting_this_week(db)
        second = await svc.get_reporting_this_week(db)
        db.close()
        assert first == second
        assert calls["n"] == 1  # second served from cache

        db = _new_db()
        await svc.get_reporting_this_week(db, force_refresh=True)
        db.close()
        assert calls["n"] == 2  # force_refresh bypasses cache
    finally:
        _clear_week()
