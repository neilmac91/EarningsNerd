"""Offline tests for the B2 filings-list freshness cache (app.routers.filings).

Pure logic — no DB/network: they prove the (ticker, types) freshness + eviction behavior that lets
a recently-synced ticker skip the SEC round-trip."""
from datetime import datetime, timedelta

import pytest

from app.routers import filings as f


@pytest.fixture(autouse=True)
def _clear_cache():
    f._filings_synced_at.clear()
    yield
    f._filings_synced_at.clear()


def test_cold_key_is_not_fresh():
    assert f._filings_cache_fresh("AAPL", ["10-K", "10-Q"]) is False


def test_marked_key_is_fresh():
    f._mark_filings_synced("AAPL", ["10-K", "10-Q"])
    assert f._filings_cache_fresh("AAPL", ["10-K", "10-Q"]) is True


def test_freshness_is_types_sensitive():
    f._mark_filings_synced("AAPL", ["10-K", "10-Q"])
    # A different type set is a different cache key — must not be served as fresh.
    assert f._filings_cache_fresh("AAPL", ["10-K"]) is False
    assert f._filings_cache_fresh("AAPL", ["10-K", "10-Q", "20-F"]) is False


def test_stale_key_past_ttl_is_not_fresh():
    key = ("AAPL", ("10-K", "10-Q"))
    f._filings_synced_at[key] = datetime.utcnow() - (f.FILINGS_LIST_TTL + timedelta(minutes=1))
    assert f._filings_cache_fresh("AAPL", ["10-K", "10-Q"]) is False


def test_key_just_within_ttl_is_fresh():
    key = ("AAPL", ("10-K", "10-Q"))
    f._filings_synced_at[key] = datetime.utcnow() - (f.FILINGS_LIST_TTL - timedelta(minutes=1))
    assert f._filings_cache_fresh("AAPL", ["10-K", "10-Q"]) is True


def test_eviction_bounds_memory(monkeypatch):
    monkeypatch.setattr(f, "MAX_FILINGS_SYNC_ENTRIES", 3)
    for i in range(3):
        f._mark_filings_synced(f"T{i}", ["10-K"])
    assert len(f._filings_synced_at) == 3
    # The oldest (T0) is evicted when a 4th distinct key is added.
    f._mark_filings_synced("T3", ["10-K"])
    assert len(f._filings_synced_at) == 3
    assert ("T0", ("10-K",)) not in f._filings_synced_at
    assert ("T3", ("10-K",)) in f._filings_synced_at
