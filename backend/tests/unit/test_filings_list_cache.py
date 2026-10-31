"""Offline tests for the B2 filings-list freshness cache (app.services.filing_list_service).

Pure logic — no DB/network: they prove the (ticker, types) freshness + eviction behavior that lets
a recently-synced ticker skip the SEC round-trip, for the company whose listing wrote the stamp."""
from datetime import timedelta

import pytest

from app.services import filing_list_service as f
from app.utils.datetimes import utcnow

COMPANY_ID = 7


@pytest.fixture(autouse=True)
def _clear_cache():
    f._filings_synced_at.clear()
    yield
    f._filings_synced_at.clear()


def test_cold_key_is_not_fresh():
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID) is False


def test_marked_key_is_fresh():
    f._mark_filings_synced("AAPL", ["10-K", "10-Q"], COMPANY_ID)
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID) is True


def test_freshness_is_types_sensitive():
    f._mark_filings_synced("AAPL", ["10-K", "10-Q"], COMPANY_ID)
    # A different type set is a different cache key — must not be served as fresh.
    assert f.filings_cache_fresh("AAPL", ["10-K"], COMPANY_ID) is False
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q", "20-F"], COMPANY_ID) is False


def test_a_stamp_is_fresh_only_for_the_company_whose_listing_wrote_it():
    # A ticker can pass to another company within the TTL (SEC reassigns it to a new CIK); the new
    # company's listing has not been fetched, so the old company's stamp must not answer it.
    f._mark_filings_synced("AAPL", ["10-K", "10-Q"], COMPANY_ID)
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID + 1) is False
    f._mark_filings_synced("AAPL", ["10-K", "10-Q"], COMPANY_ID + 1)  # its own listing re-stamps the key
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID + 1) is True
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID) is False
    assert len(f._filings_synced_at) == 1


def test_stale_key_past_ttl_is_not_fresh():
    key = ("AAPL", ("10-K", "10-Q"))
    f._filings_synced_at[key] = (COMPANY_ID, utcnow() - (f.FILINGS_LIST_TTL + timedelta(minutes=1)))
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID) is False


def test_key_just_within_ttl_is_fresh():
    key = ("AAPL", ("10-K", "10-Q"))
    f._filings_synced_at[key] = (COMPANY_ID, utcnow() - (f.FILINGS_LIST_TTL - timedelta(minutes=1)))
    assert f.filings_cache_fresh("AAPL", ["10-K", "10-Q"], COMPANY_ID) is True


def test_eviction_bounds_memory(monkeypatch):
    monkeypatch.setattr(f, "MAX_FILINGS_SYNC_ENTRIES", 3)
    for i in range(3):
        f._mark_filings_synced(f"T{i}", ["10-K"], COMPANY_ID)
    assert len(f._filings_synced_at) == 3
    # The oldest (T0) is evicted when a 4th distinct key is added.
    f._mark_filings_synced("T3", ["10-K"], COMPANY_ID)
    assert len(f._filings_synced_at) == 3
    assert ("T0", ("10-K",)) not in f._filings_synced_at
    assert ("T3", ("10-K",)) in f._filings_synced_at
