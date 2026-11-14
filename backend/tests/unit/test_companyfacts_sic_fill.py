"""A company whose SIC is unknown has it filled from SEC before its companyfacts are normalized (``facts/sic_fill``).

No code that creates a ``Company`` writes ``sic``, and the sync reads a financial filer's revenue (SIC 6000-6799) from
its reported total but every other filer's from the generic tags, whose first is a bank's ASC 606 fee line. A bank
added after the last hand-run SIC backfill was synced as a non-financial filer, and its fee line stayed its revenue:
a resync skips stored identities. The batch sync, the request path's sync and the backfill's cross-check now look the
SIC up (the SEC boundary is faked here) between their database units, store it with the facts, remember "SEC lists
none" as an empty string, and store nothing when the lookup fails.
"""

import logging
import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.models import Base, Company, Filing, FinancialFact
from app.services import facts_service
from app.services.edgar import company_sic
from app.services.edgar.circuit_breaker import CircuitOpenError

FEE = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _year(tag: str, value: float) -> dict:
    return {tag: {"units": {"USD": [{
        "val": value, "start": "2024-01-01", "end": "2024-12-31", "accn": "0000000000-25-000001",
        "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-15",
    }]}}}


# A bank's year: its total is 450 (net interest income 300 plus noninterest income 150); its ASC 606 fee line is 50.
BANK = {"facts": {"us-gaap": {
    **_year(FEE, 50.0), **_year("Revenues", 450.0),
    **_year("InterestIncomeExpenseNet", 300.0), **_year("NoninterestIncome", 150.0),
}}}


async def _bank(_cik):
    return BANK


@pytest.fixture
def engine(tmp_path):
    """A pool the test can read: ``checkedout()`` counts the connections held when the SEC lookup runs."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sic-fill.db'}", connect_args={"check_same_thread": False},
        poolclass=QueuePool, pool_size=4, max_overflow=0, pool_timeout=10.0,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(engine):
    return sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def inflight():
    saved = dict(facts_service._inflight_syncs)
    facts_service._inflight_syncs.clear()
    yield
    facts_service._inflight_syncs.clear()
    facts_service._inflight_syncs.update(saved)


class FakeSec:
    """The SIC lookup's SEC boundary (``edgar.company_sic``): answers ``result``, or raises it, and records the pool's
    checked-out connections at each call."""

    def __init__(self, engine, result):
        self.engine, self.result, self.calls = engine, result, []

    def answer(self, cik):
        self.calls.append((cik, self.engine.pool.checkedout()))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    async def lookup(self, cik):
        return self.answer(cik)


@pytest.fixture
def sec(monkeypatch, engine):
    def install(result):
        fake = FakeSec(engine, result)
        monkeypatch.setattr(company_sic, "fetch_company_sic", fake.lookup)
        monkeypatch.setattr(company_sic, "fetch_company_sic_sync", fake.answer)
        return fake
    return install


def _company(sessions, sic=None) -> int:
    with sessions() as db:
        company = Company(cik=f"{uuid.uuid4().int % 10**10:010d}", ticker=f"B{uuid.uuid4().hex[:6]}".upper(),
                          name="A Bank", sic=sic)
        db.add(company)
        db.commit()
        return company.id


def _stored(sessions, company_id):
    """The company's stored SIC, its current revenue values and its sync stamp."""
    with sessions() as db:
        company = db.get(Company, company_id)
        revenue = sorted(float(r.value) for r in db.query(FinancialFact).filter_by(
            company_id=company_id, concept="revenue", is_latest=True))
        return company.sic, revenue, company.facts_synced_at


async def _sync_batch(sessions, company_id, *, force=False, fetcher=_bank):
    with sessions() as db:
        ticker = db.get(Company, company_id).ticker
        return await facts_service.sync_companyfacts_batch(db, tickers=[ticker], force=force, fetcher=fetcher)


async def _sync_by_id(sessions, company_id, *, force=False, fetcher=_bank):
    return await facts_service.ingest_companyfacts_by_id(
        company_id, session_factory=sessions, force=force, fetcher=fetcher)


PATHS = {"batch": _sync_batch, "by_id": _sync_by_id}


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.asyncio
async def test_an_unknown_sic_is_filled_and_a_bank_reads_its_total(sessions, sec, path):
    fake = sec(("6021", "National Commercial Banks"))
    company_id = _company(sessions)

    await PATHS[path](sessions, company_id)

    sic, revenue, synced_at = _stored(sessions, company_id)
    assert sic == "6021"
    assert revenue == [450.0]  # the bank's total, never its 50 fee line
    assert synced_at is not None
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_the_request_paths_lookup_holds_no_connection(sessions, sec):
    """The lookup runs between the sync's units: after the freshness read has released its connection and before the
    persist checks one out (and takes its row lock)."""
    fake = sec(("6021", "National Commercial Banks"))
    company_id = _company(sessions)

    await _sync_by_id(sessions, company_id)

    assert [held for _cik, held in fake.calls] == [0]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.asyncio
async def test_a_stored_sic_is_not_looked_up(sessions, sec, path):
    fake = sec(AssertionError("a stored SIC needs no SEC lookup"))
    company_id = _company(sessions, sic="6021")

    await PATHS[path](sessions, company_id)

    assert fake.calls == []
    assert _stored(sessions, company_id)[:2] == ("6021", [450.0])


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.asyncio
async def test_no_sic_at_sec_is_remembered_and_never_asked_again(sessions, sec, path, caplog):
    """SEC answers without a SIC: the sync stores the facts as a non-financial filer's, names the company once, and
    stores an empty SIC, so the second sync (forced past the TTL) makes no lookup: one lookup in all."""
    fake = sec(None)
    company_id = _company(sessions)

    with caplog.at_level(logging.WARNING, logger="app.services.facts_service"):
        await PATHS[path](sessions, company_id)
        await PATHS[path](sessions, company_id, force=True)

    sic, revenue, synced_at = _stored(sessions, company_id)
    assert (sic, revenue) == ("", [50.0])
    assert synced_at is not None
    assert len(fake.calls) == 1
    cik = fake.calls[0][0]
    assert [r.levelname for r in caplog.records if cik in r.getMessage() and "no SIC" in r.getMessage()] == ["WARNING"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("failure", [CircuitOpenError("edgar"), TimeoutError("SEC timed out")])
@pytest.mark.asyncio
async def test_a_failed_lookup_stores_nothing_and_the_next_sync_retries(sessions, sec, path, failure, caplog):
    """An unknown SIC SEC could not be asked for is a failed fetch: no facts, no stamp and no SIC, with a WARNING that
    names the company, so the next touch retries; storing would have read a bank's fee line as its revenue for good."""
    fake = sec(failure)
    company_id = _company(sessions)

    with caplog.at_level(logging.WARNING, logger="app.services.facts_service"):
        result = await PATHS[path](sessions, company_id)

    if path == "by_id":
        assert (result["synced"], result["error"]) == (False, "fetch_failed")
    else:
        assert result["failed"] == 1
    assert _stored(sessions, company_id) == (None, [], None)
    cik = fake.calls[0][0]
    assert any(r.levelname == "WARNING" and cik in r.getMessage() and "SEC lookup failed" in r.getMessage()
               for r in caplog.records)

    fake.result = ("6021", "National Commercial Banks")
    await PATHS[path](sessions, company_id)
    assert _stored(sessions, company_id)[:2] == ("6021", [450.0])


def _bank_filing(sessions, company_id, mark):
    with sessions() as db:
        db.add(Filing(
            company_id=company_id, accession_number=f"ACC-{uuid.uuid4().hex[:10]}", filing_type="10-K",
            filing_date=datetime(2025, 2, 15), document_url="https://sec.example/x.htm",
            sec_url="https://sec.example/", xbrl_data={"mark": mark},
        ))
        db.commit()
        return db.get(Company, company_id).ticker


def _bank_extract(xbrl):
    """The filing's own revenue: the bank's total, as the per-filing extractor reads it."""
    return {"revenue": {"current": {"period": "2024-12-31", "value": 450.0}}}


@pytest.mark.parametrize("flags_only", [False, True])
def test_the_backfill_cross_check_fills_the_sic_and_keeps_a_banks_total(sessions, sec, flags_only):
    """The scheduled backfill can reach a new bank before any sync. Its cross-check replaces a filing's figure that
    disagrees with companyfacts, so read as a non-financial filer the bank's 450 total became its 50 fee line. The
    audit's flags-only pass reads the SIC too but writes nothing outside its flag columns."""
    fake = sec(("6021", "National Commercial Banks"))
    company_id = _company(sessions)
    ticker = _bank_filing(sessions, company_id, "bank")

    with sessions() as db:
        facts_service.backfill_facts(db, extract=_bank_extract, companyfacts_fetcher=lambda _cik: BANK,
                                     tickers=[ticker])
    if flags_only:
        with sessions() as db:
            db.query(Company).filter_by(id=company_id).update({"sic": None})
            db.commit()
            audit = facts_service.backfill_facts(db, extract=_bank_extract, companyfacts_fetcher=lambda _cik: BANK,
                                                 tickers=[ticker], refresh_flags=True, flags_only=True)
        # Read as a non-financial filer, the audit would hold the stored 450 against the 50 fee line.
        assert (audit["value_mismatch"], audit["companyfacts_unavailable"]) == (0, 0)

    sic, revenue, _ = _stored(sessions, company_id)
    assert revenue == [450.0]
    assert sic == (None if flags_only else "6021")
    assert len(fake.calls) == (2 if flags_only else 1)


def test_a_failed_cross_check_lookup_counts_the_company_unavailable(sessions, sec, caplog):
    """As for a failed companyfacts fetch: no authority, the miss counted, the filing's own figure kept."""
    sec(CircuitOpenError("edgar"))
    company_id = _company(sessions)
    ticker = _bank_filing(sessions, company_id, "bank")

    with sessions() as db, caplog.at_level(logging.WARNING, logger="app.services.facts_service"):
        stats = facts_service.backfill_facts(db, extract=_bank_extract, companyfacts_fetcher=lambda _cik: BANK,
                                             tickers=[ticker], refresh_flags=True)

    assert stats["companyfacts_unavailable"] == 1
    assert _stored(sessions, company_id)[:2] == (None, [450.0])
    assert any("SIC is unknown and the SEC lookup failed" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_on_the_caller_owned_paths_the_lookup_holds_what_the_fetch_holds(engine, sessions, sec):
    """``sync_companyfacts_batch`` and ``backfill_facts`` own one session for the whole walk, and the companyfacts fetch
    has always run inside whatever read transaction it holds: the batch's cohort query for its first company, the
    backfill's re-read of each filing. The lookup runs right after that fetch and holds the same, never more (no unit
    of its own, not the persist's row lock); only the request path's lookup holds nothing
    (``test_the_request_paths_lookup_holds_no_connection``)."""
    fake = sec(("6021", "National Commercial Banks"))
    fetched: list[int] = []

    async def bank(_cik):
        fetched.append(engine.pool.checkedout())
        return BANK

    def bank_sync(_cik):
        fetched.append(engine.pool.checkedout())
        return BANK

    first, second = _company(sessions), _company(sessions)
    with sessions() as db:
        tickers = [db.get(Company, first).ticker, db.get(Company, second).ticker]
    with sessions() as db:
        await facts_service.sync_companyfacts_batch(db, tickers=tickers, fetcher=bank)
    ticker = _bank_filing(sessions, _company(sessions), "bank")
    with sessions() as db:
        facts_service.backfill_facts(db, extract=_bank_extract, companyfacts_fetcher=bank_sync, tickers=[ticker])

    assert [held for _cik, held in fake.calls] == fetched == [1, 0, 1]
