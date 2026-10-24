"""QW1 (PR#573) — DB-first serving of the company filings list.

Once we hold any persisted filings for a company, the endpoint serves them immediately and refreshes
from SEC in the BACKGROUND — the request never blocks on a SEC round-trip. Only a first-ever view
(empty DB) does a synchronous, bounded live fetch. These tests run against a real in-memory SQLite
DB (so the actual queries execute) with SEC faked at the compat boundary.
"""
import asyncio
import contextlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from unittest.mock import AsyncMock

import main
from app.config import settings
from app.database import Base, get_db
from app.integrations import sec_api
import app.models  # noqa: F401 — register models on Base.metadata
from app.models import Company, Filing
from app.routers import filings as filings_mod
from app.services import filing_history_service, filing_list_service
from app.services.edgar import client as edgar_client_mod
from app.services.edgar.exceptions import EdgarError
from app.services.latest_filing_service import company_list_forms
from app.services.request_work import request_work_scope
from app.utils.sec_urls import build_sec_archive_url
from tests.support.filings_budgets import unspend_filings_budgets

# The client fixture stubs the history walk; the FPI backfill tests below put the real one back.
_REAL_FETCH_HISTORY_ROWS = filing_history_service._fetch_history_rows


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_engine, monkeypatch):
    TestingSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    # The background refresh opens its OWN SessionLocal — point it at the same in-memory engine.
    monkeypatch.setattr(filing_list_service, "SessionLocal", TestingSession)

    # An unstamped company enqueues the on-visit deep-history backfill (filings.py:151-159), whose
    # only network I/O is this EFTS walk. Stub it like the pool-lifetime test below: no windows
    # fetched, so nothing is persisted and the company stays unstamped.
    async def _no_history_fetch(*, cik, ticker, efts_client=None):
        return [], 0, 0

    monkeypatch.setattr(filing_history_service, "_fetch_history_rows", _no_history_fetch)
    unspend_filings_budgets(monkeypatch)
    filing_list_service._filings_synced_at.clear()
    filing_list_service._refreshing_keys.clear()
    filing_list_service._history_backfilling_ids.clear()

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(main.app), TestingSession
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        filing_list_service._filings_synced_at.clear()
        filing_list_service._refreshing_keys.clear()
        filing_list_service._history_backfilling_ids.clear()


def _on_event_loop() -> bool:
    """Whether the calling thread is running an event loop: a request unit handed to the thread
    pool runs in a worker thread, which has none."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _seed_company(session, ticker="TESTCO", cik="0000895421"):
    company = Company(cik=cik, ticker=ticker, name="Test Co", exchange="NYSE")
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def _seed_filing(session, company, accession, filing_type="10-K", year=2025):
    accession_clean = accession.replace("-", "")
    cik_clean = company.cik.lstrip("0") or "0"
    sec_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/"
    filing = Filing(
        company_id=company.id,
        accession_number=accession,
        filing_type=filing_type,
        filing_date=datetime(year, 2, 19, tzinfo=timezone.utc),
        period_end_date=datetime(year - 1, 12, 31, tzinfo=timezone.utc),
        document_url=sec_url + "primary.htm",
        sec_url=sec_url,
    )
    session.add(filing)
    session.commit()
    session.refresh(filing)
    return filing


def test_db_first_serves_persisted_rows_without_blocking_on_sec(client, monkeypatch):
    tc, TestingSession = client
    with TestingSession() as s:
        company = _seed_company(s)
        _seed_filing(s, company, "0000895421-25-000010", "10-K", 2025)
        _seed_filing(s, company, "0000895421-25-000044", "10-Q", 2025)

    # The background refresh will call this; the RESPONSE must already be served from the DB.
    sec_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", sec_mock)

    resp = tc.get("/api/filings/company/TESTCO")

    assert resp.status_code == 200
    data = resp.json()
    # Served the two persisted rows, newest-first, with the FilingResponse contract intact.
    assert {f["filing_type"] for f in data} == {"10-K", "10-Q"}
    first = data[0]
    assert first["accession_number"]
    assert first["sec_url"].startswith("https://www.sec.gov/Archives/edgar/data/")
    assert first["company"]["ticker"] == "TESTCO"
    # DB-first fired a background refresh (bounded) rather than blocking the request on it.
    assert sec_mock.await_count == 1


def test_db_first_background_refresh_persists_new_rows_and_stamps_the_list_fresh(client, monkeypatch):
    """The refresh runs after the response on its OWN session (the patched SessionLocal): the newly
    listed filing lands in the DB, the (ticker, types) is stamped fresh for the B2 fast path, and the
    in-flight key is cleared."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", False)
    with TestingSession() as s:
        company = _seed_company(s)
        company.history_backfilled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)  # refresh only
        s.commit()
        _seed_filing(s, company, "0000895421-25-000010", "10-K", 2025)

    new_url = "https://www.sec.gov/Archives/edgar/data/895421/000089542126000010/"
    sec_mock = AsyncMock(return_value=[{
        "accession_number": "0000895421-26-000010", "filing_type": "10-K",
        "filing_date": "2026-02-19", "report_date": "2025-12-31",
        "document_url": new_url + "primary.htm", "sec_url": new_url,
    }])
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", sec_mock)

    resp = tc.get("/api/filings/company/TESTCO")

    # The response was served from the persisted row; the refresh then added the new one.
    assert resp.status_code == 200
    assert [f["accession_number"] for f in resp.json()] == ["0000895421-25-000010"]
    with TestingSession() as s:
        assert s.query(Filing).filter(Filing.accession_number == "0000895421-26-000010").count() == 1
    assert sec_mock.await_count == 1
    types = tuple(sec_mock.await_args.args[1])
    assert ("TESTCO", types) in filing_list_service._filings_synced_at
    assert filing_list_service._refreshing_keys == set()


@pytest.mark.asyncio
async def test_background_refresh_collapses_a_concurrent_burst(client, monkeypatch):
    """Check-and-add on the in-flight key has no await between them, so a burst of refreshes for
    one (ticker, types) makes one SEC call; the key clears when that call's refresh finishes."""
    _tc, TestingSession = client
    with TestingSession() as s:
        company_id = _seed_company(s).id
    release = asyncio.Event()
    calls = []

    async def get_filings(cik, types):
        calls.append(cik)
        await release.wait()
        return []

    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", get_filings)
    burst = [
        asyncio.create_task(
            filing_list_service.refresh_company_filings("0000895421", "TESTCO", ["10-K"], company_id)
        )
        for _ in range(3)
    ]
    await asyncio.sleep(0)  # every refresh reaches its guard; the first one holds the key
    assert filing_list_service._refreshing_keys == {("TESTCO", ("10-K",))}

    release.set()
    await asyncio.gather(*burst)

    assert calls == ["0000895421"]
    assert filing_list_service._refreshing_keys == set()
    assert ("TESTCO", ("10-K",)) in filing_list_service._filings_synced_at


@pytest.mark.asyncio
async def test_history_backfill_collapses_a_concurrent_burst(monkeypatch):
    """Same guard for the on-visit history backfill, keyed by company id: one walk, run on the
    module's own session factory, and the id clears when it finishes."""
    release = asyncio.Event()
    calls = []

    async def backfill(company_id, *, session_factory):
        calls.append((company_id, session_factory))
        await release.wait()

    monkeypatch.setattr(filing_history_service, "backfill_company_by_id", backfill)
    monkeypatch.setattr(filing_list_service, "_history_backfilling_ids", set())
    burst = [
        asyncio.create_task(filing_list_service.run_history_backfill_on_visit(7)) for _ in range(3)
    ]
    await asyncio.sleep(0)
    assert filing_list_service._history_backfilling_ids == {7}

    release.set()
    await asyncio.gather(*burst)

    assert calls == [(7, filing_list_service.SessionLocal)]
    assert filing_list_service._history_backfilling_ids == set()


def _begins_recorded(session_factory, begins):
    """A session factory whose sessions record, as each begins a transaction, whether it began on the
    event loop."""
    def factory():
        session = session_factory()
        event.listen(session, "after_begin", lambda *_: begins.append(_on_event_loop()))
        return session
    return factory


@pytest.mark.asyncio
async def test_background_refresh_works_its_session_off_the_event_loop(client, monkeypatch):
    """With DURABLE_TASKS_ENABLED off the refresh runs in the API process after the response. Its
    upsert is one unit in the thread pool, so its checkout never freezes the loop while the pool is
    full (E123)."""
    _tc, TestingSession = client
    with TestingSession() as s:
        company_id = _seed_company(s).id
    url = "https://www.sec.gov/Archives/edgar/data/895421/000089542126000011/"
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", AsyncMock(return_value=[{
        "accession_number": "0000895421-26-000011", "filing_type": "10-K",
        "filing_date": "2026-02-19", "report_date": "2025-12-31",
        "document_url": url + "primary.htm", "sec_url": url,
    }]))
    begins = []
    monkeypatch.setattr(filing_list_service, "SessionLocal", _begins_recorded(TestingSession, begins))

    await filing_list_service.refresh_company_filings("0000895421", "TESTCO", ["10-K"], company_id)

    assert begins and not any(begins), f"a refresh session began on the event loop: {begins}"
    with TestingSession() as s:
        assert s.query(Filing).filter(Filing.accession_number == "0000895421-26-000011").count() == 1
    assert ("TESTCO", ("10-K",)) in filing_list_service._filings_synced_at


@pytest.mark.asyncio
async def test_background_refresh_of_a_company_gone_marks_nothing_fresh(client, monkeypatch):
    """A company deleted before the refresh's unit runs leaves its list unmarked, so the next visit
    refreshes again rather than serving the fast path."""
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", AsyncMock(return_value=[]))

    await filing_list_service.refresh_company_filings("0000895421", "TESTCO", ["10-K"], 999_999)

    assert ("TESTCO", ("10-K",)) not in filing_list_service._filings_synced_at
    assert filing_list_service._refreshing_keys == set()


@pytest.mark.asyncio
@pytest.mark.parametrize("owned", [False, True], ids=["unowned", "in-a-request-work-scope"])
async def test_history_backfill_works_its_sessions_off_the_event_loop(client, owned):
    """The on-visit backfill's two short units, its read before the EFTS walk and its persistence
    after it, each run in the thread pool (E123): AnyIO's, or inside a request-work scope, as the
    durable worker's task process runs it, the owned executor."""
    _tc, TestingSession = client
    with TestingSession() as s:
        company_id = _seed_company(s).id
    begins = []

    async with request_work_scope() if owned else contextlib.nullcontext():
        await filing_history_service.backfill_company_by_id(
            company_id, session_factory=_begins_recorded(TestingSession, begins)
        )

    # Both units began a transaction (each reads the company), and neither on the loop.
    assert len(begins) >= 2 and not any(begins), f"a backfill session began on the event loop: {begins}"


def test_cold_empty_db_does_synchronous_bounded_fetch_and_persists(client, monkeypatch):
    tc, TestingSession = client
    with TestingSession() as s:
        _seed_company(s)  # company known, but NO filings yet (the mega-filer cold case)

    sec_filings = [
        {
            "accession_number": "0000895421-26-000010",
            "filing_type": "10-K",
            "filing_date": "2026-02-19",
            "report_date": "2025-12-31",
            "document_url": "https://www.sec.gov/Archives/edgar/data/895421/000089542126000010/primary.htm",
            "sec_url": "https://www.sec.gov/Archives/edgar/data/895421/000089542126000010/",
        }
    ]
    monkeypatch.setattr(
        filings_mod.sec_edgar_service, "get_filings", AsyncMock(return_value=sec_filings)
    )

    resp = tc.get("/api/filings/company/TESTCO")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["filing_type"] == "10-K"
    assert data[0]["accession_number"] == "0000895421-26-000010"
    # The synchronous fetch persisted the row.
    with TestingSession() as s:
        assert s.query(Filing).filter(Filing.accession_number == "0000895421-26-000010").count() == 1


def test_sec_network_phases_do_not_retain_queuepool_connections(tmp_path, monkeypatch):
    """Warm background, cold-list and company-miss SEC waits all release the one-slot pool, and
    each route returns with it released, before the dependency finalizer runs. Every transaction
    the request session begins, the lookup, the company persist, the cached read and the live
    persist, begins in the thread pool: a checkout on the event loop would freeze it for the pool
    timeout once the pool is full (lessons/ops-release-cached-filing-reads-before-yield.md)."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'filings-lifetime.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.05,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    held_at_finalizer = []
    # Only the request session's own transactions: the history backfill runs after the response and
    # opens its own sessions (filing_list_service.SessionLocal).
    request_begins_on_loop = []

    def override_get_db():
        with TestingSession() as db:
            event.listen(db, "after_begin", lambda *_: request_begins_on_loop.append(_on_event_loop()))
            yield db
            # The function-scoped finalizer runs once the route has returned (in the thread pool).
            # The route must already have released its connection; each unit does that before it
            # returns, after building its response.
            held_at_finalizer.append(engine.pool.checkedout())

    phases = []

    def assert_released(phase):
        assert engine.pool.checkedout() == 0, f"{phase} retained a database connection"
        phases.append(phase)

    async def fake_history_fetch(*, cik, ticker, efts_client=None):
        assert_released(f"history:{ticker}")
        return [], 1, 1

    def filing_payload(cik):
        accession = f"{cik}-{26:02d}-000001"
        archive_cik = cik.lstrip("0") or "0"
        accession_clean = accession.replace("-", "")
        sec_url = f"https://www.sec.gov/Archives/edgar/data/{archive_cik}/{accession_clean}/"
        return [{
            "accession_number": accession,
            "filing_type": "10-K",
            "filing_date": "2026-02-19",
            "report_date": "2025-12-31",
            "document_url": sec_url + "primary.htm",
            "sec_url": sec_url,
        }]

    async def fake_get_filings(cik, _types):
        assert_released(f"filings:{cik}")
        return [] if cik == "0000000001" else filing_payload(cik)

    async def fake_search_company(ticker):
        assert_released(f"search:{ticker}")
        return [{
            "cik": "0000000003", "ticker": ticker.upper(),
            "name": "Missing Company", "exchange": "NYSE",
        }]

    async def fake_primary_ticker(cik):
        assert_released(f"primary:{cik}")
        return "MISSING"

    monkeypatch.setattr(filing_list_service, "SessionLocal", TestingSession)
    monkeypatch.setattr(filing_history_service, "_fetch_history_rows", fake_history_fetch)
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", fake_get_filings)
    monkeypatch.setattr(filings_mod.sec_edgar_service, "search_company", fake_search_company)
    monkeypatch.setattr(
        filings_mod.sec_edgar_service, "primary_ticker_for_cik", fake_primary_ticker
    )
    filing_list_service._filings_synced_at.clear()
    filing_list_service._refreshing_keys.clear()
    filing_list_service._history_backfilling_ids.clear()

    with TestingSession() as db:
        warm = _seed_company(db, ticker="WARM", cik="0000000001")
        _seed_filing(db, warm, "0000000001-25-000001")
        cold = _seed_company(db, ticker="COLD", cik="0000000002")
        cold.history_backfilled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.commit()

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        tc = TestClient(main.app)
        assert tc.get("/api/filings/company/WARM").status_code == 200
        assert tc.get("/api/filings/company/COLD").status_code == 200
        assert tc.get("/api/filings/company/MISSING").status_code == 200
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        filing_list_service._filings_synced_at.clear()
        filing_list_service._refreshing_keys.clear()
        filing_list_service._history_backfilling_ids.clear()
        engine.dispose()

    assert phases == [
        "history:WARM",
        "filings:0000000001",
        "filings:0000000002",
        "search:MISSING",
        "primary:0000000003",
        "filings:0000000003",
        "history:MISSING",
    ]
    assert held_at_finalizer == [0, 0, 0]  # WARM (cached), COLD (live), MISSING (miss + live)
    # The lookups, the company persist, the cached reads and the live persists: none began on the loop.
    assert request_begins_on_loop and not any(request_begins_on_loop)


@pytest.mark.parametrize("failure, status", [("timeout", 503), ("edgar", 503), ("persist", 500)])
def test_cold_fetch_fallbacks_keep_the_request_session_off_the_event_loop(tmp_path, monkeypatch, failure, status):
    """The cold live fetch's fallbacks (an SEC timeout, an SEC error, a persist that raises) read
    the cached rows in the thread pool as well: no request-session transaction begins on the event
    loop, and the route returns with its connection released."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'filings-fallbacks.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.05,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    held_at_finalizer = []
    request_begins_on_loop = []

    def override_get_db():
        with TestingSession() as db:
            event.listen(db, "after_begin", lambda *_: request_begins_on_loop.append(_on_event_loop()))
            try:
                yield db
            finally:  # the route's HTTPException is thrown in at the yield
                held_at_finalizer.append(engine.pool.checkedout())

    async def get_filings(cik, _types):
        if failure == "timeout":
            raise asyncio.TimeoutError
        if failure == "edgar":
            raise EdgarError("edgar down")
        accession = f"{cik}-26-000001"
        sec_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession.replace('-', '')}/"
        return [{"accession_number": accession, "filing_type": "10-K", "filing_date": "not-a-date",
                 "document_url": sec_url + "primary.htm", "sec_url": sec_url}]

    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", get_filings)
    filing_list_service._filings_synced_at.clear()

    with TestingSession() as db:
        cold = _seed_company(db, ticker="COLD", cik="0000000002")
        cold.history_backfilled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.commit()

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        assert TestClient(main.app).get("/api/filings/company/COLD").status_code == status
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        filing_list_service._filings_synced_at.clear()
        engine.dispose()

    assert held_at_finalizer == [0]
    assert not any(request_begins_on_loop)
    # The lookup, the cached read, the persist that raised (for that case) and the fallback read.
    assert len(request_begins_on_loop) >= 3


@pytest.mark.parametrize("synced_forms, expected_fetches", [
    (["10-K", "10-Q", "10-K/A", "10-Q/A"], 0),
    (["10-K", "10-Q"], 1),  # An original-only fetch never proves amendment freshness.
])
def test_db_first_skips_refresh_when_freshly_synced(client, monkeypatch, synced_forms, expected_fetches):
    tc, TestingSession = client
    with TestingSession() as s:
        company = _seed_company(s)
        _seed_filing(s, company, "0000895421-25-000010", "10-K", 2025)
        company_id = company.id

    # Only a stamp covering every requested form can suppress the background refresh.
    filing_list_service._mark_filings_synced("TESTCO", synced_forms, company_id)
    sec_mock = AsyncMock(return_value=[])
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", sec_mock)

    resp = tc.get("/api/filings/company/TESTCO")

    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert sec_mock.await_count == expected_fetches
    if expected_fetches:
        assert sec_mock.await_args.args[1] == ["10-K", "10-Q", "10-K/A", "10-Q/A"]


def _seed_history(session, company, n, start_year=2000):
    """Seed n distinct 10-K/10-Q filings across years (unique accessions/urls)."""
    for i in range(n):
        ftype = "10-K" if i % 4 == 0 else "10-Q"
        _seed_filing(session, company, f"0000895421-{i:02d}-000{i:03d}", ftype, start_year + i)


def test_filings_limit_param_default_unchanged(client, monkeypatch):
    """P1-6: the endpoint still caps at CACHED_FILINGS_LIMIT by default; an explicit ?limit= raises
    the ceiling so deep-backfilled history surfaces."""
    tc, TestingSession = client
    with TestingSession() as s:
        company = _seed_company(s)
        # Stamp so the on-visit history backfill guard skips (no live EFTS call in the test).
        company.history_backfilled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        s.add(company)
        s.commit()
        _seed_history(s, company, 25)
        company_id = company.id
    # Freshly-synced → DB-first serves without any SEC round-trip.
    filing_list_service._mark_filings_synced("TESTCO", ["10-K", "10-Q", "10-K/A", "10-Q/A"], company_id)
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", AsyncMock(return_value=[]))

    # Default: capped at CACHED_FILINGS_LIMIT (behaviour unchanged).
    default_resp = tc.get("/api/filings/company/TESTCO")
    assert default_resp.status_code == 200
    assert len(default_resp.json()) == filing_list_service.CACHED_FILINGS_LIMIT

    # Explicit limit raises the ceiling to surface the full backfilled history.
    full_resp = tc.get("/api/filings/company/TESTCO?limit=100")
    assert full_resp.status_code == 200
    assert len(full_resp.json()) == 25
    # Newest-first ordering preserved.
    dates = [f["filing_date"] for f in full_resp.json()]
    assert dates == sorted(dates, reverse=True)


# ---- 6-K budget: a daily 6-K filer still lists its 20-F ----
# Foreign issuers such as BP, Shell and HSBC furnish a 6-K most business days (buyback notices). A
# single row cap across every form let those 6-Ks push the 20-F annual report out of the list, on the
# live SEC path (the recent-window materialize cap) and on the DB-first path (the cached row cap).

FPI_CIK = "0000313807"


class _WindowFiling:
    """An edgartools EntityFiling as the recent submissions window lists it (cheap fields only)."""

    def __init__(self, form, filing_date, accession):
        self.form = form
        self.filing_date = filing_date
        self.report_date = "2025-12-31" if form in ("10-K", "20-F") else None
        self.accession_number = accession
        self.primary_document = "doc.htm"
        self.company = "Test Co"


def _fake_edgar_company(window):
    """An EdgarCompany whose recent window is ``window`` (newest first), filtered like edgartools."""

    class _FakeEdgarCompany:
        cik = int(FPI_CIK)

        def __init__(self, ident):
            pass

        def get_filings(self, form=None, amendments=None, trigger_full_load=None, sort_by=None):
            assert trigger_full_load is False  # the list path never loads the full history
            return [f for f in window if f.form.replace("/A", "") in form]

    return _FakeEdgarCompany


def _daily(form, n, newest, prefix):
    """``n`` filings of ``form``, one a day back from ``newest``, newest first."""
    return [
        _WindowFiling(form, newest - timedelta(days=i), f"{FPI_CIK}-26-{prefix}{i:05d}")
        for i in range(n)
    ]


def _seed_dated(session, company, accession, filing_type, filed):
    cik_clean = company.cik.lstrip("0") or "0"
    sec_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession.replace('-', '')}/"
    session.add(Filing(
        company_id=company.id,
        accession_number=accession,
        filing_type=filing_type,
        filing_date=datetime(filed.year, filed.month, filed.day, tzinfo=timezone.utc),
        document_url=sec_url + "doc.htm",
        sec_url=sec_url,
    ))


def _seed_stamped_company(session, ticker):
    company = _seed_company(session, ticker=ticker, cik=FPI_CIK)
    company.history_backfilled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)  # no on-visit walk
    session.commit()
    return company


def test_live_list_keeps_the_20f_behind_sixty_newer_6ks(client, monkeypatch):
    """Cold view (empty DB): the route's own SEC fetch lists and persists the 20-F although 60 6-Ks
    are newer; the 6-Ks keep a budget of their own, so they stay bounded too."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    window = _daily("6-K", 60, date(2026, 8, 31), "1") + [
        _WindowFiling("20-F", date(2026, 3, 5), f"{FPI_CIK}-26-900001")
    ]
    monkeypatch.setattr(edgar_client_mod, "EdgarCompany", _fake_edgar_company(window))
    with TestingSession() as s:
        _seed_stamped_company(s, "BPX")

    resp = tc.get("/api/filings/company/BPX")

    assert resp.status_code == 200
    types = [f["filing_type"] for f in resp.json()]
    assert "20-F" in types
    assert types.count("6-K") == edgar_client_mod.RECENT_FILINGS_MATERIALIZE_CAP
    with TestingSession() as s:
        assert s.query(Filing).filter(Filing.filing_type == "20-F").count() == 1


def test_cached_list_keeps_the_20f_behind_sixty_newer_6ks(client, monkeypatch):
    """DB-first serving: the default list shows the stored 20-F next to the newest 6-Ks, newest
    first, and an explicit ?limit= caps the 6-Ks, a 6-K/A among them, apart from the reports."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    with TestingSession() as s:
        company = _seed_stamped_company(s, "BPX")
        for f in _daily("6-K", 60, date(2026, 8, 31), "1"):
            _seed_dated(s, company, f.accession_number, "6-K", f.filing_date)
        _seed_dated(s, company, f"{FPI_CIK}-26-900001", "20-F", date(2026, 3, 5))
        _seed_dated(s, company, f"{FPI_CIK}-26-800001", "6-K/A", date(2026, 9, 1))  # not a default form
        s.commit()
        company_id = company.id
    filing_list_service._mark_filings_synced("BPX", company_list_forms(), company_id)  # serve from the DB
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", AsyncMock(return_value=[]))

    default = tc.get("/api/filings/company/BPX").json()

    types = [f["filing_type"] for f in default]
    assert types == ["6-K"] * filing_list_service.CACHED_FILINGS_LIMIT + ["20-F"]
    dates = [f["filing_date"] for f in default]
    assert dates == sorted(dates, reverse=True)

    limited = [f["filing_type"] for f in tc.get("/api/filings/company/BPX?limit=5").json()]
    assert limited == ["6-K"] * 5 + ["20-F"]
    amended = tc.get("/api/filings/company/BPX?filing_types=20-F,6-K,6-K/A&limit=5").json()
    assert [f["filing_type"] for f in amended] == ["6-K/A"] + ["6-K"] * 4 + ["20-F"]


@pytest.mark.parametrize("query, kept_6ks, kept_20fs", [("", 50, 10), ("?limit=5", 5, 5)])
def test_cold_list_caps_each_group_at_the_requested_limit(client, monkeypatch, query, kept_6ks, kept_20fs):
    """Cold view (empty DB): the live fetch persists every row it lists, the newest 50 6-Ks and all
    ten 20-Fs. The default response is all of them; an explicit ?limit=5 serves the newest five of
    each group, in SEC order, as the DB-first list does."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    # Synthetic: a 20-F every week among daily 6-Ks, so the groups interleave and each holds more than 5.
    window = [
        _WindowFiling("20-F" if i % 7 == 3 else "6-K", date(2026, 8, 31) - timedelta(days=i),
                      f"{FPI_CIK}-26-{i:06d}")
        for i in range(70)
    ]
    monkeypatch.setattr(edgar_client_mod, "EdgarCompany", _fake_edgar_company(window))
    # The error fallbacks also cap each group in SQL, so a live path that raised after its commit
    # would still serve these rows from them; refusing the fallback proves the live path served it.
    def _no_fallback(*_args, **_kwargs):
        raise AssertionError("the cold list was served by an error fallback, not the live fetch")

    monkeypatch.setattr(filing_list_service, "cached_filings_after_rollback", _no_fallback)
    with TestingSession() as s:
        _seed_stamped_company(s, "BPX")

    cold = [f["accession_number"] for f in tc.get(f"/api/filings/company/BPX{query}").json()]

    six_ks = [f.accession_number for f in window if f.form == "6-K"]
    twenty_fs = [f.accession_number for f in window if f.form == "20-F"]
    newest = set(six_ks[:kept_6ks] + twenty_fs[:kept_20fs])
    assert cold == [f.accession_number for f in window if f.accession_number in newest]
    with TestingSession() as s:
        assert s.query(Filing).count() == 60


def test_domestic_lists_are_unchanged_by_the_6k_budget(client, monkeypatch):
    """With the foreign forms on (production), a 10-K/10-Q filer's live list is still the newest 50
    rows and its cached default the newest 20, each in filing-date order."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    window = [
        _WindowFiling("10-K" if i % 4 == 0 else "10-Q", date(2026, 8, 31) - timedelta(days=30 * i),
                      f"{FPI_CIK}-26-{i:06d}")
        for i in range(60)
    ]
    newest_first = [f.accession_number for f in window]
    monkeypatch.setattr(edgar_client_mod, "EdgarCompany", _fake_edgar_company(window))
    with TestingSession() as s:
        _seed_stamped_company(s, "DOMX")

    live = tc.get("/api/filings/company/DOMX").json()  # cold: the live SEC path persists the rows
    cached = tc.get("/api/filings/company/DOMX").json()  # stamped fresh: the DB-first path

    assert [f["accession_number"] for f in live] == newest_first[:50]
    assert [f["accession_number"] for f in cached] == newest_first[:filing_list_service.CACHED_FILINGS_LIMIT]


# ---- History backfill: a foreign issuer's older annual reports reach its company page ----
# The live list reads SEC's recent window, the greater of about a year or about 1,000 filings, so it
# stores no 20-F older than that window; with ENABLE_FPI_FILINGS on, the EFTS history walk does.


def _efts_listing(filings):
    """The real EFTS client over a fake transport: a query-less listing answers with the ``filings``
    (``_WindowFiling``) of a requested form filed in the request's window, as EFTS lists them, an
    amendment under its root form too (the P1-6 live walk dropped seven /A hits), with live EFTS's
    form fields: ``root_forms`` lists the root form, and ``form`` and ``file_type`` keep the /A."""

    def respond(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        hits = [
            {"_id": f"{f.accession_number}:{f.primary_document}", "_source": {
                "root_forms": [f.form.removesuffix("/A")], "form": f.form,
                "file_type": f.form, "file_date": f.filing_date.isoformat(), "period_ending": f.report_date,
                "ciks": [FPI_CIK], "display_names": [f"Test Co (BPX) (CIK {FPI_CIK})"],
            }}
            for f in filings
            if {f.form, f.form.removesuffix("/A")} & set(params["forms"].split(","))
            and params["startdt"] <= f.filing_date.isoformat() <= params["enddt"]
        ]
        return httpx.Response(200, json={"hits": {"total": {"value": len(hits)}, "hits": hits}})

    return sec_api.SECFullTextSearchClient(transport=httpx.MockTransport(respond))


def _annual(form, fiscal_year, sequence):
    """A December-year-end annual report for ``fiscal_year``, filed the next March."""
    filing = _WindowFiling(form, date(fiscal_year + 1, 3, 5), f"{FPI_CIK}-{(fiscal_year + 1) % 100:02d}-9{sequence:05d}")
    filing.report_date = f"{fiscal_year}-12-31"
    return filing


def _stored_fields(session, accession):
    """The stored row's columns a list response is built from."""
    row = session.query(Filing).filter(Filing.accession_number == accession).one()
    return {
        column: getattr(row, column)
        for column in ("company_id", "accession_number", "filing_type", "filing_date", "period_end_date",
                       "sec_url", "document_url", "superseded_by_accession")
    }


def test_history_backfill_lists_a_6k_filers_older_annual_reports(client, monkeypatch):
    """A first visit to a daily 6-K filer lists what its recent window holds: daily 6-Ks and its
    newest 20-F (the fake window is cut short; SEC's spans at least a year). The visit's history
    backfill walks EFTS (faked at the transport), and the next visit lists every 20-F newest first,
    the one the live list stored once, each with its period end and canonical archive URLs, so the
    page's year groups and "Compare periods" have the older annual reports. The 20-F/A EFTS lists
    beside them is not stored, as the default company list neither serves nor stores one."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    monkeypatch.setattr(settings, "HISTORY_BACKFILL_SINCE_YEAR", 2017)
    annuals = [_annual("20-F", year, year - 2016) for year in range(2017, 2026)]
    amendment = _annual("20-F/A", 2022, 99)
    window = _daily("6-K", 60, date(2026, 8, 31), "1") + annuals[-1:]
    monkeypatch.setattr(edgar_client_mod, "EdgarCompany", _fake_edgar_company(window))
    monkeypatch.setattr(filing_history_service, "_fetch_history_rows", _REAL_FETCH_HISTORY_ROWS)
    monkeypatch.setattr(sec_api, "sec_full_text_search_client", _efts_listing(annuals + [amendment] + window))
    with TestingSession() as s:
        company_id = _seed_company(s, ticker="BPX", cik=FPI_CIK).id  # not backfilled: the visit queues it

    first = tc.get("/api/filings/company/BPX").json()  # cold: the live list, then the backfill
    listed = tc.get("/api/filings/company/BPX").json()

    assert [f["accession_number"] for f in first if f["filing_type"] != "6-K"] == [annuals[-1].accession_number]
    reports = [f for f in listed if f["filing_type"] != "6-K"]
    newest_first = sorted(annuals, key=lambda f: f.filing_date, reverse=True)
    assert [f["accession_number"] for f in reports] == [f.accession_number for f in newest_first]
    for listed_report, annual in zip(reports, newest_first):
        sec_url = build_sec_archive_url(FPI_CIK, annual.accession_number)
        assert listed_report["filing_type"] == "20-F"
        assert listed_report["report_date"].startswith(annual.report_date)
        assert listed_report["filing_date"].startswith(annual.filing_date.isoformat())
        assert (listed_report["sec_url"], listed_report["document_url"]) == (sec_url, sec_url + "doc.htm")
    assert [f["filing_type"] for f in listed].count("6-K") == filing_list_service.CACHED_FILINGS_LIMIT
    with TestingSession() as s:
        assert s.query(Filing).filter(Filing.accession_number == amendment.accession_number).count() == 0
        assert s.get(Company, company_id).history_backfilled_at is not None


REWALK_MIGRATION = Path(__file__).resolve().parents[2] / "migrations/20261023_rewalk_foreign_issuer_history.sql"


def test_a_foreign_issuer_the_old_walk_stamped_is_walked_again_after_the_migration(client, db_engine, monkeypatch):
    """Before this release the walk listed 10-K/10-Q only, so a foreign issuer opened then holds what
    the live list stored (its recent 6-Ks and newest 20-F) and a stamp that stops every later visit
    from walking it, whatever forms the walk now lists. The deploy's migration clears that stamp, so
    the next visit walks EFTS with the foreign forms and the company lists its older 20-Fs."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    monkeypatch.setattr(settings, "HISTORY_BACKFILL_SINCE_YEAR", 2017)
    annuals = [_annual("20-F", year, year - 2016) for year in range(2017, 2026)]
    window = _daily("6-K", 60, date(2026, 8, 31), "1") + annuals[-1:]
    monkeypatch.setattr(edgar_client_mod, "EdgarCompany", _fake_edgar_company(window))
    monkeypatch.setattr(filing_history_service, "_fetch_history_rows", _REAL_FETCH_HISTORY_ROWS)
    monkeypatch.setattr(sec_api, "sec_full_text_search_client", _efts_listing(annuals + window))
    with TestingSession() as s:
        company_id = _seed_company(s, ticker="BPX", cik=FPI_CIK).id

    def reports() -> list[str]:
        filing_list_service._filings_synced_at.clear()  # each visit reads the stored rows afresh
        return [f["accession_number"] for f in tc.get("/api/filings/company/BPX").json() if f["filing_type"] != "6-K"]

    foreign_forms = filing_history_service._FPI_BACKFILL_FORMS
    monkeypatch.setattr(filing_history_service, "_FPI_BACKFILL_FORMS", ())  # the walk before this release
    assert reports() == [annuals[-1].accession_number]  # the first visit walks 10-K/10-Q only and stamps
    monkeypatch.setattr(filing_history_service, "_FPI_BACKFILL_FORMS", foreign_forms)
    with TestingSession() as s:
        assert s.get(Company, company_id).history_backfilled_at is not None
    assert reports() == [annuals[-1].accession_number]  # stamped: no visit walks it again

    raw = db_engine.raw_connection()
    try:  # the migration as the deploy applies it, its PostgreSQL session settings aside
        raw.driver_connection.executescript("\n".join(
            line for line in REWALK_MIGRATION.read_text().splitlines()
            if not line.startswith(("SET lock_timeout", "SET statement_timeout", "RESET "))
        ))
    finally:
        raw.close()
    reports()  # the visit queues the walk again

    assert reports() == [f.accession_number for f in sorted(annuals, key=lambda f: f.filing_date, reverse=True)]
    with TestingSession() as s:
        assert s.get(Company, company_id).history_backfilled_at is not None


def test_history_backfill_stores_a_20f_as_the_live_list_does(client, monkeypatch):
    """The row the backfill stores for a 20-F is the row the live list stores for it: the same form,
    dates and archive and document URLs (both through app/utils/sec_urls.py)."""
    tc, TestingSession = client
    monkeypatch.setattr(settings, "ENABLE_FPI_FILINGS", True)
    monkeypatch.setattr(settings, "HISTORY_BACKFILL_SINCE_YEAR", 2024)
    annual = _annual("20-F", 2025, 1)
    monkeypatch.setattr(edgar_client_mod, "EdgarCompany", _fake_edgar_company([annual]))
    monkeypatch.setattr(filing_history_service, "_fetch_history_rows", _REAL_FETCH_HISTORY_ROWS)
    with TestingSession() as s:
        company_id = _seed_stamped_company(s, "BPX").id

    assert [f["filing_type"] for f in tc.get("/api/filings/company/BPX").json()] == ["20-F"]
    with TestingSession() as s:
        live = _stored_fields(s, annual.accession_number)
        s.query(Filing).delete()
        s.commit()

    stats = asyncio.run(filing_history_service.backfill_company_by_id(
        company_id, session_factory=TestingSession, efts_client=_efts_listing([annual]), force=True,
    ))

    assert stats["inserted"] == 1
    with TestingSession() as s:
        assert _stored_fields(s, annual.accession_number) == live
