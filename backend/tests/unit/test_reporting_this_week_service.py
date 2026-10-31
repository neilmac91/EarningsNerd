"""Reporting-this-week: the current market week's events from earnings_events, ranked by
anticipation_score (the curated intersect is retired — the score carries the mega-cap floor).
Never raises."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import EarningsEvent
from app.routers import reporting_this_week as reporting_this_week_router
from app.services.reporting_this_week_service import (
    ReportingCompany,
    ReportingThisWeekService,
    current_market_week,
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def _seed(ticker, event_date, score, *, name=None, time="amc", status="estimated"):
    from app.database import SessionLocal
    from app.models import EarningsEvent

    db = SessionLocal()
    db.add(EarningsEvent(
        ticker=ticker.upper(),
        company_name=name or f"{ticker} Inc",
        fiscal_period_end=date(2026, 3, 31),
        event_date=event_date,
        event_time=time,
        status=status,
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
def test_ranked_by_anticipation_score():
    _clear_week()
    monday, _ = current_market_week()
    _seed("AAPL", monday + timedelta(days=1), score=1500)
    _seed("ZZZZ", monday, score=5)      # not curated — no longer excluded, just ranked last
    _seed("JPM", monday, score=1100)
    _seed("GOOGL", monday + timedelta(days=2), score=1300)
    try:
        db = _new_db()
        # today=monday keeps every seeded (estimated) row visible under the past-day filter,
        # whatever real weekday the suite runs on.
        result = ReportingThisWeekService().get_reporting_this_week(db, today=monday)
        db.close()
        assert result["status"] == "ok"
        tickers = [c["ticker"] for c in result["companies"]]
        assert tickers == ["AAPL", "GOOGL", "JPM", "ZZZZ"]  # score desc; ZZZZ present but last
    finally:
        _clear_week()


@pytest.mark.requires_db
def test_empty_status_when_no_events():
    _clear_week()
    monday, _ = current_market_week()
    db = _new_db()
    result = ReportingThisWeekService().get_reporting_this_week(db, today=monday)
    db.close()
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.requires_db
def test_below_minimum_count_treated_as_empty():
    _clear_week()
    monday, _ = current_market_week()
    _seed("AAPL", monday, score=1000)
    _seed("JPM", monday, score=900)  # only 2 — below MIN_COMPANIES (4)
    try:
        db = _new_db()
        result = ReportingThisWeekService().get_reporting_this_week(db, today=monday)
        db.close()
        assert result["companies"] == []
        assert result["status"] == "empty"
    finally:
        _clear_week()


@pytest.mark.requires_db
def test_respects_limit():
    _clear_week()
    monday, _ = current_market_week()
    for i in range(10):
        _seed(f"T{i:02d}", monday, score=1000 - i)
    try:
        db = _new_db()
        result = ReportingThisWeekService().get_reporting_this_week(db, limit=5, today=monday)
        db.close()
        assert len(result["companies"]) == 5
    finally:
        _clear_week()


@pytest.mark.requires_db
def test_past_days_serve_facts_only():
    """Mid-week, days already behind us show only reported rows; estimates ahead still show."""
    _clear_week()
    monday, _ = current_market_week()
    wednesday = monday + timedelta(days=2)
    _seed("PASTE", monday, score=1000)                                    # past estimate → hidden
    _seed("RPTDW", monday + timedelta(days=1), score=950, status="reported")  # past fact → kept
    _seed("FUT1", monday + timedelta(days=3), score=900)
    _seed("FUT2", monday + timedelta(days=3), score=800)
    _seed("FUT3", monday + timedelta(days=4), score=700)
    _seed("FUT4", monday + timedelta(days=4), score=600)
    try:
        db = _new_db()
        result = ReportingThisWeekService().get_reporting_this_week(db, today=wednesday)
        db.close()
        tickers = [c["ticker"] for c in result["companies"]]
        assert "PASTE" not in tickers
        assert "RPTDW" in tickers
        assert result["status"] == "ok"
    finally:
        _clear_week()


@pytest.mark.requires_db
def test_never_raises_on_query_error():
    # A broken session must degrade to empty, never raise.
    class _BrokenDB:
        def query(self, *a, **k):
            raise RuntimeError("boom")

    result = ReportingThisWeekService().get_reporting_this_week(_BrokenDB())
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.requires_db
def test_cache_hit_avoids_refetch():
    _clear_week()
    monday, _ = current_market_week()
    for t, s in (("AAPL", 1000), ("JPM", 900), ("MSFT", 800), ("GOOGL", 700)):
        _seed(t, monday, score=s)
    try:
        svc = ReportingThisWeekService()
        calls = {"n": 0}
        original = svc._fetch

        def counting(db, mon, fri, today):
            calls["n"] += 1
            return original(db, mon, fri, today)

        svc._fetch = counting
        db = _new_db()
        first = svc.get_reporting_this_week(db, today=monday)
        second = svc.get_reporting_this_week(db, today=monday)
        db.close()
        assert first == second
        assert calls["n"] == 1  # second served from cache

        db = _new_db()
        svc.get_reporting_this_week(db, force_refresh=True, today=monday)
        db.close()
        assert calls["n"] == 2  # force_refresh bypasses cache

        # A new ET day is a cache MISS even inside the TTL — the past-day filter must roll at
        # midnight, not when the 6h TTL happens to lapse.
        db = _new_db()
        svc.get_reporting_this_week(db, today=monday + timedelta(days=1))
        db.close()
        assert calls["n"] == 3
    finally:
        _clear_week()


@pytest.mark.requires_db
def test_failed_fetch_is_not_cached():
    """A failed read serves empty to that request only. Caching it would keep the homepage strip
    blank for the 6h TTL after the database recovers."""
    _clear_week()
    monday, _ = current_market_week()
    tuesday = monday + timedelta(days=1)
    for t, s in (("AAPL", 1000), ("JPM", 900), ("MSFT", 800), ("GOOGL", 700)):
        _seed(t, tuesday, score=s)  # still ahead on Tuesday, so visible on both days

    class _BrokenDB:
        def query(self, *a, **k):
            raise RuntimeError("QueuePool limit reached")

    try:
        svc = ReportingThisWeekService()
        # A cold instance: the first-ever read fails, then a healthy one returns the week.
        failed = svc.get_reporting_this_week(_BrokenDB(), today=monday)
        assert failed["companies"] == []
        assert failed["status"] == "empty"
        db = _new_db()
        assert svc.get_reporting_this_week(db, today=monday)["status"] == "ok"

        # A warm instance: ET midnight changes the key while Monday's success is still inside
        # the TTL, and the new day's first read fails. The retry on that key must not hit it.
        failed = svc.get_reporting_this_week(_BrokenDB(), today=tuesday)
        assert failed["status"] == "empty"
        recovered = svc.get_reporting_this_week(db, today=tuesday)
        db.close()
        assert recovered["status"] == "ok"
        assert [c["ticker"] for c in recovered["companies"]] == ["AAPL", "JPM", "MSFT", "GOOGL"]
    finally:
        _clear_week()


@pytest.mark.requires_db
def test_successful_empty_week_is_cached():
    """Only a failure skips the cache: a week that really has no events is cached like any other."""
    _clear_week()
    monday, _ = current_market_week()
    svc = ReportingThisWeekService()
    calls = {"n": 0}
    original = svc._fetch

    def counting(db, mon, fri, today):
        calls["n"] += 1
        return original(db, mon, fri, today)

    svc._fetch = counting
    db = _new_db()
    first = svc.get_reporting_this_week(db, today=monday)
    second = svc.get_reporting_this_week(db, today=monday)
    db.close()
    assert first["status"] == second["status"] == "empty"
    assert calls["n"] == 1


_WEEK_TICKERS = ["AAPL", "JPM", "MSFT", "GOOGL"]


def _cold_burst(n, reads_return):
    """`n` concurrent requests on a cold cache, each in a thread of its own as the route's unit runs.
    The first read is held until every request has checked the cache; each read returns the next
    item of `reads_return` (None = a failed read). Returns the responses and the number of reads."""
    monday, _ = current_market_week()
    checks = threading.Semaphore(0)
    release_reads = threading.Event()
    reads: list[int] = []

    def fetch(db, mon, fri, today):
        result = reads_return[min(len(reads), len(reads_return) - 1)]
        reads.append(1)
        release_reads.wait(timeout=2)
        return result

    svc = ReportingThisWeekService()
    svc._fetch = fetch
    check = svc._cached

    def counted(key, now):
        try:
            return check(key, now)
        finally:
            checks.release()

    svc._cached = counted
    with ThreadPoolExecutor(max_workers=n) as pool:
        requests = [pool.submit(svc.get_reporting_this_week, None, today=monday) for _ in range(n)]
        try:
            # Each request's first check and the first reader's recheck under the lock: all have missed
            # before any read returns, since the others wait on the lock that reader holds.
            missed = 0
            while missed < n + 1 and checks.acquire(timeout=2):
                missed += 1
            # A request that raised before its check would look like a missing check, so its error rides along.
            assert missed == n + 1, (
                f"{missed} of {n + 1} cache checks before the first read returned; "
                f"errors: {[request.exception() for request in requests if request.done()]}")
        finally:
            # A failed precondition still lets the held read return, so the pool's shutdown does not wait
            # out each reader's timeout in turn.
            release_reads.set()
        return [request.result(timeout=3) for request in requests], len(reads)


def _week():
    monday, _ = current_market_week()
    return [ReportingCompany(t, f"{t} Inc", monday, "amc") for t in _WEEK_TICKERS]


def test_concurrent_misses_share_one_read():
    """A burst on a cold or expired cache (a fresh instance, ET midnight) waits for one read and is
    served from it. A read per request would check out a pooled connection each."""
    responses, reads = _cold_burst(8, [_week()])
    assert reads == 1
    assert all([c["ticker"] for c in r["companies"]] == _WEEK_TICKERS for r in responses)


def test_failed_read_lets_the_next_waiter_retry():
    """A failed read is still neither cached nor shared: it serves its own request, the next waiter
    reads again, and the rest are served from that success."""
    responses, reads = _cold_burst(3, [None, _week()])
    assert reads == 2
    # The failed read answers whichever request took the lock first.
    assert sorted(r["status"] for r in responses) == ["empty", "ok", "ok"]


@pytest.mark.asyncio
async def test_waiting_fetch_lets_another_request_release_its_connection(monkeypatch, tmp_path):
    """The route is public, so no auth dependency checks the session out off the event loop first.
    A cache miss that waits on the pool must not block the loop that the holder of the last
    connection needs in order to finish and release it."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rtw-pool.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.25,
    )
    EarningsEvent.__table__.create(engine)
    monday, _ = current_market_week()
    loop = asyncio.get_running_loop()
    holder_entered = asyncio.Event()
    release_holder = asyncio.Event()

    class ObservedSession(Session):
        def query(self, *args, **kwargs):
            # The strip's read is about to wait on the only connection. Its owner can finish as
            # soon as the event loop is free to run this callback.
            loop.call_soon_threadsafe(release_holder.set)
            return super().query(*args, **kwargs)

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=ObservedSession))
    for t, s in (("AAPL", 1000), ("JPM", 900), ("MSFT", 800), ("GOOGL", 700)):
        # _seed only adds and commits, so seeding never fires the query() release above.
        _seed(t, monday, score=s, status="reported")  # reported: visible whatever today is
    monkeypatch.setattr(
        reporting_this_week_router, "reporting_this_week_service", ReportingThisWeekService()
    )
    app = FastAPI()
    app.include_router(reporting_this_week_router.router, prefix="/api")

    @app.get("/hold")
    async def hold(db: Session = Depends(database.get_db)):
        db.connection()  # takes the pool's only connection until the request cleans up
        holder_entered.set()
        await asyncio.wait_for(release_holder.wait(), timeout=2)
        return {"ok": True}

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            holder = asyncio.create_task(client.get("/hold"))
            await asyncio.wait_for(holder_entered.wait(), timeout=2)
            strip = await asyncio.wait_for(client.get("/api/reporting_this_week"), timeout=3)
            assert (await asyncio.wait_for(holder, timeout=3)).status_code == 200
        assert strip.status_code == 200
        assert strip.json()["status"] == "ok"
        assert [c["ticker"] for c in strip.json()["companies"]] == ["AAPL", "JPM", "MSFT", "GOOGL"]
        assert engine.pool.checkedout() == 0
    finally:
        release_holder.set()
        engine.dispose()
