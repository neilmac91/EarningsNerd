"""Follow-up (post-#577): the per-CIK EdgarCompany cache behind resolve_filing_by_accession.

A single summary run resolves the SAME filing twice — the XBRL extraction and the section extraction
fire as CONCURRENT tasks, each in the edgar thread pool. Sharing one cached entity means an
accession older than the recent window full-loads the company's history ONCE, not per extraction.
These tests pin the cache/lock behavior (no network: EdgarCompany is faked).
"""
import threading
import time
from datetime import timedelta

import pytest

from app.services.edgar import client as client_mod


class _CountingCompany:
    """Counts constructions; get_filings returns one filing regardless of args."""

    construct_count = 0
    build_delay = 0.0

    def __init__(self, cik):
        _CountingCompany.construct_count += 1
        if _CountingCompany.build_delay:
            time.sleep(_CountingCompany.build_delay)
        self.cik = cik
        self.sic = "6199"

    def get_filings(self, accession_number=None, trigger_full_load=None):
        return [object()]


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    _CountingCompany.construct_count = 0
    _CountingCompany.build_delay = 0.0
    client_mod._company_cache.clear()
    client_mod._company_locks.clear()
    monkeypatch.setattr(client_mod, "EdgarCompany", _CountingCompany)
    yield
    client_mod._company_cache.clear()
    client_mod._company_locks.clear()


def test_resolver_reuses_cached_company_for_same_cik():
    company1, filings1 = client_mod.resolve_filing_by_accession("0000320193", "acc-1")
    company2, filings2 = client_mod.resolve_filing_by_accession("0000320193", "acc-2")
    # One construction, reused — this is the whole point (an old filing full-loads once per run).
    assert _CountingCompany.construct_count == 1
    assert company1 is company2
    assert filings1 and filings2


def test_resolver_isolates_by_cik():
    client_mod.resolve_filing_by_accession("0000320193", "acc")
    client_mod.resolve_filing_by_accession("0000789019", "acc")
    assert _CountingCompany.construct_count == 2


def test_resolver_rebuilds_after_ttl():
    client_mod.resolve_filing_by_accession("0000320193", "acc")
    assert _CountingCompany.construct_count == 1
    # Age the cache entry past its TTL.
    company, ts = client_mod._company_cache["0000320193"]
    client_mod._company_cache["0000320193"] = (
        company,
        ts - client_mod._COMPANY_CACHE_TTL - timedelta(seconds=1),
    )
    client_mod.resolve_filing_by_accession("0000320193", "acc")
    assert _CountingCompany.construct_count == 2


def test_resolver_cache_is_bounded():
    for i in range(client_mod._COMPANY_CACHE_MAX + 3):
        client_mod.resolve_filing_by_accession(f"cik-{i}", "acc")
    assert len(client_mod._company_cache) <= client_mod._COMPANY_CACHE_MAX


def test_idle_company_lock_is_garbage_collected():
    # _company_locks is a WeakValueDictionary, so a CIK's lock is dropped once no thread references
    # it — no unbounded growth over the process lifetime. The company itself stays in the bounded cache.
    import gc

    client_mod.resolve_filing_by_accession("0000320193", "acc")
    gc.collect()
    assert "0000320193" not in client_mod._company_locks
    assert "0000320193" in client_mod._company_cache


def test_resolver_builds_once_under_concurrent_same_cik_access():
    # The per-CIK lock must serialize concurrent same-CIK resolution so edgartools' lazy full-load
    # can't race between the two concurrent extractions — and so only ONE construction happens.
    # A small build delay widens the window so a missing lock would let both threads construct.
    _CountingCompany.build_delay = 0.03
    results = []

    def worker():
        results.append(client_mod.resolve_filing_by_accession("0000320193", "acc"))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _CountingCompany.construct_count == 1  # lock prevented the double build
    # Both callers got the same cached company instance.
    assert results[0][0] is results[1][0]
