"""Reporting-this-week: curated tickers intersected with FMP's earnings calendar,
scoped to the current America/New_York market week. Never raises."""
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.reporting_this_week_service import (
    ReportingThisWeekService,
    current_market_week,
)


class _FakeFMP:
    def __init__(self, events=None, raise_error=False):
        self._events = events or {}
        self._raise_error = raise_error

    async def fetch_earnings_calendar(self, from_date=None, to_date=None):
        if self._raise_error:
            raise RuntimeError("boom")
        return self._events


def _event(d, time="amc"):
    return SimpleNamespace(earnings_date=d, time=time)


def test_current_market_week_monday_to_friday():
    # 2026-07-01 is a Wednesday.
    monday, friday = current_market_week(today=date(2026, 7, 1))
    assert monday == date(2026, 6, 29)
    assert friday == date(2026, 7, 3)


def test_current_market_week_stable_across_weekend():
    # Saturday and Sunday both resolve to the week that just ended.
    sat_monday, sat_friday = current_market_week(today=date(2026, 7, 4))
    sun_monday, sun_friday = current_market_week(today=date(2026, 7, 5))
    assert sat_monday == sun_monday == date(2026, 6, 29)
    assert sat_friday == sun_friday == date(2026, 7, 3)


@pytest.mark.asyncio
async def test_only_curated_tickers_included_sorted_by_date():
    fmp = _FakeFMP({
        "AAPL": _event(date(2026, 6, 30)),
        "ZZZZ": _event(date(2026, 6, 29)),  # not curated, must be excluded
        "JPM": _event(date(2026, 6, 29)),
        "GOOGL": _event(date(2026, 7, 1)),
        "MSFT": _event(date(2026, 7, 2)),
    })
    svc = ReportingThisWeekService(fmp=fmp)
    result = await svc.get_reporting_this_week()

    assert result["status"] == "ok"
    tickers = [c["ticker"] for c in result["companies"]]
    assert tickers == ["JPM", "AAPL", "GOOGL", "MSFT"]  # soonest first; ZZZZ excluded
    assert all(c["ticker"] != "ZZZZ" for c in result["companies"])


@pytest.mark.asyncio
async def test_empty_status_when_no_curated_matches():
    svc = ReportingThisWeekService(fmp=_FakeFMP({}))
    result = await svc.get_reporting_this_week()
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.asyncio
async def test_below_minimum_count_treated_as_empty():
    # Only 2 curated matches — below MIN_COMPANIES (4), should collapse to empty
    # so the homepage section doesn't render an awkwardly sparse row.
    fmp = _FakeFMP({
        "AAPL": _event(date(2026, 6, 30)),
        "JPM": _event(date(2026, 6, 29)),
    })
    svc = ReportingThisWeekService(fmp=fmp)
    result = await svc.get_reporting_this_week()
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.asyncio
async def test_never_raises_on_fmp_error():
    svc = ReportingThisWeekService(fmp=_FakeFMP(raise_error=True))
    result = await svc.get_reporting_this_week()
    assert result["companies"] == []
    assert result["status"] == "empty"


@pytest.mark.asyncio
async def test_respects_limit():
    from app.services.reporting_this_week_service import CURATED_TICKERS

    events = {t: _event(date(2026, 6, 29)) for t in list(CURATED_TICKERS.keys())[:10]}
    svc = ReportingThisWeekService(fmp=_FakeFMP(events))
    result = await svc.get_reporting_this_week(limit=5)
    assert len(result["companies"]) == 5


@pytest.mark.asyncio
async def test_cache_hit_returns_same_payload_without_refetch():
    call_count = {"n": 0}

    class _CountingFMP(_FakeFMP):
        async def fetch_earnings_calendar(self, from_date=None, to_date=None):
            call_count["n"] += 1
            return await super().fetch_earnings_calendar(from_date, to_date)

    fmp = _CountingFMP({
        "AAPL": _event(date(2026, 6, 29)),
        "JPM": _event(date(2026, 6, 29)),
        "MSFT": _event(date(2026, 6, 29)),
        "GOOGL": _event(date(2026, 6, 29)),
    })
    svc = ReportingThisWeekService(fmp=fmp)
    first = await svc.get_reporting_this_week()
    second = await svc.get_reporting_this_week()
    assert first == second
    assert call_count["n"] == 1  # second call served from in-memory cache


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache():
    call_count = {"n": 0}

    class _CountingFMP(_FakeFMP):
        async def fetch_earnings_calendar(self, from_date=None, to_date=None):
            call_count["n"] += 1
            return await super().fetch_earnings_calendar(from_date, to_date)

    fmp = _CountingFMP({
        "AAPL": _event(date(2026, 6, 29)),
        "JPM": _event(date(2026, 6, 29)),
        "MSFT": _event(date(2026, 6, 29)),
        "GOOGL": _event(date(2026, 6, 29)),
    })
    svc = ReportingThisWeekService(fmp=fmp)
    await svc.get_reporting_this_week()
    await svc.get_reporting_this_week(force_refresh=True)
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_cache_respects_different_limits():
    # Caching the already-sliced payload would let an early small-limit request poison
    # the cache for a later, larger-limit request within the same window — regression
    # test for that bug.
    fmp = _FakeFMP({
        "AAPL": _event(date(2026, 6, 29)),
        "JPM": _event(date(2026, 6, 29)),
        "MSFT": _event(date(2026, 6, 29)),
        "GOOGL": _event(date(2026, 6, 29)),
    })
    svc = ReportingThisWeekService(fmp=fmp)

    first = await svc.get_reporting_this_week(limit=2)
    assert len(first["companies"]) == 2

    second = await svc.get_reporting_this_week(limit=4)
    assert len(second["companies"]) == 4
