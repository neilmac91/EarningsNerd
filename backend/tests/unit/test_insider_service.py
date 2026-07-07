"""Unit tests for the insider-activity orchestration layer.

The EdgarTools fetch is replaced with an injected async ``fetcher``, so these
run without edgartools installed and assert the windowing, caching, recent-sort,
and response-shape contract that the router and schema depend on.
"""

from datetime import date, timedelta

import pytest

from app.services import insider_service


def _days_ago(n: int) -> str:
    """ISO date n days before today (so transactions fall inside the real window)."""
    return (date.today() - timedelta(days=n)).isoformat()


# A stand-in for edgar's CompanyNotFoundError. We avoid importing the real one
# because the app.services.edgar package pulls in edgartools at import time
# (absent in this test env). The service only *propagates* the fetcher's
# exception — it never inspects the type — so any exception exercises the
# contract the router relies on (router maps CompanyNotFoundError -> 404).
class CompanyNotFoundError(Exception):
    pass


def _bundle(transactions, ticker="AAPL", name="Apple Inc.", cik="0000320193"):
    return {
        "ticker": ticker,
        "company_name": name,
        "cik": cik,
        "transactions": transactions,
    }


def _txn(code, ad, shares, price, day, is_plan=False):
    return {
        "insider_name": "Jane Doe",
        "transaction_code": code,
        "acquired_disposed": ad,
        "shares": shares,
        "price": price,
        "value": shares * price,
        "transaction_date": day,
        "is_10b5_1": is_plan,
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    insider_service.clear_cache()
    yield
    insider_service.clear_cache()


@pytest.mark.asyncio
async def test_get_insider_activity_shape_and_summary():
    buy_day, sell_day = _days_ago(20), _days_ago(10)
    txns = [
        _txn("P", "A", 100, 10, buy_day),
        _txn("S", "D", 40, 20, sell_day),
    ]

    async def fetcher(ticker, limit):
        assert ticker == "AAPL"
        return _bundle(txns)

    res = await insider_service.get_insider_activity(
        "aapl", window_days=90, fetcher=fetcher
    )

    assert res["ticker"] == "AAPL"
    assert res["company_name"] == "Apple Inc."
    assert res["cik"] == "0000320193"
    assert res["window_days"] == 90
    assert res["total_transactions"] == 2
    assert res["summary"]["buy_shares"] == 100
    assert res["summary"]["sell_shares"] == 40
    assert len(res["transactions"]) == 2
    # Recent-first ordering (the more recent sell comes first).
    assert res["transactions"][0]["transaction_date"] == sell_day


@pytest.mark.asyncio
async def test_recent_limit_truncates_but_summary_uses_all():
    # 20 buys on distinct, in-window days (1..20 days ago).
    txns = [_txn("P", "A", 1, 1, _days_ago(d)) for d in range(1, 21)]

    async def fetcher(ticker, limit):
        return _bundle(txns)

    res = await insider_service.get_insider_activity(
        "AAPL", window_days=90, recent_limit=5, fetcher=fetcher
    )
    assert len(res["transactions"]) == 5
    assert res["total_transactions"] == 20
    # Summary counts all 20 buys, not just the returned 5.
    assert res["summary"]["buy_count"] == 20
    # Most recent first (1 day ago).
    assert res["transactions"][0]["transaction_date"] == _days_ago(1)


@pytest.mark.asyncio
async def test_cache_fetches_once_across_windows():
    calls = {"n": 0}
    txns = [_txn("P", "A", 10, 5, "2024-05-15")]

    async def fetcher(ticker, limit):
        calls["n"] += 1
        return _bundle(txns)

    await insider_service.get_insider_activity("AAPL", window_days=90, fetcher=fetcher)
    # Different window must reuse the cached bundle (same ticker + limit_filings).
    await insider_service.get_insider_activity("AAPL", window_days=30, fetcher=fetcher)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_company_not_found_propagates():
    async def fetcher(ticker, limit):
        raise CompanyNotFoundError(ticker)

    with pytest.raises(CompanyNotFoundError):
        await insider_service.get_insider_activity("NOPE", fetcher=fetcher)


@pytest.mark.asyncio
async def test_empty_transactions_yield_zero_summary():
    async def fetcher(ticker, limit):
        return _bundle([])

    res = await insider_service.get_insider_activity("AAPL", fetcher=fetcher)
    assert res["total_transactions"] == 0
    assert res["summary"]["buy_count"] == 0
    assert res["transactions"] == []


@pytest.mark.asyncio
async def test_total_and_list_are_windowed():
    # A trade far outside the window must not appear in the list or the count, so they agree
    # with the (windowed) summary instead of reporting stale activity.
    txns = [
        _txn("P", "A", 100, 10, _days_ago(5)),    # inside the 30d window
        _txn("S", "D", 50, 10, _days_ago(400)),   # ~13 months ago — outside
    ]

    async def fetcher(ticker, limit):
        return _bundle(txns)

    res = await insider_service.get_insider_activity("AAPL", window_days=30, fetcher=fetcher)
    assert res["total_transactions"] == 1
    assert len(res["transactions"]) == 1
    assert res["transactions"][0]["transaction_date"] == _days_ago(5)
    assert res["summary"]["buy_count"] == 1
    assert res["summary"]["sell_count"] == 0


class _FakeInsiderCompany:
    """Records the Form 4 get_filings kwargs; returns no filings (so obj() is never called)."""

    last_kwargs = None

    def __init__(self, ticker):
        self.cik = "0000320193"
        self.name = "Apple Inc."
        self.ticker = "AAPL"

    def get_filings(self, form=None, amendments=None, trigger_full_load=None):
        _FakeInsiderCompany.last_kwargs = {
            "form": form,
            "amendments": amendments,
            "trigger_full_load": trigger_full_load,
        }
        return []


def test_collect_insider_data_sync_uses_recent_window(monkeypatch):
    # Regression gate: the real Form 4 fetch must pass trigger_full_load=False so it reads only the
    # recent submissions window, not the company's entire lifetime history (the mega-filer cost the
    # filing-load fix removed from listings).
    import edgar

    monkeypatch.setattr(edgar, "Company", _FakeInsiderCompany)
    _FakeInsiderCompany.last_kwargs = None

    result = insider_service._collect_insider_data_sync("AAPL", limit_filings=5)

    assert _FakeInsiderCompany.last_kwargs["form"] == "4"
    assert _FakeInsiderCompany.last_kwargs["trigger_full_load"] is False
    assert result["transactions"] == []
