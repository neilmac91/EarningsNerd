"""QW1 (PR#573) — DB-first serving of the company filings list.

Once we hold any persisted filings for a company, the endpoint serves them immediately and refreshes
from SEC in the BACKGROUND — the request never blocks on a SEC round-trip. Only a first-ever view
(empty DB) does a synchronous, bounded live fetch. These tests run against a real in-memory SQLite
DB (so the actual queries execute) with SEC faked at the compat boundary.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool
from unittest.mock import AsyncMock

import main
from app.database import Base, get_db
import app.models  # noqa: F401 — register models on Base.metadata
from app.models import Company, Filing
from app.routers import filings as filings_mod
from app.services import filing_history_service


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
    monkeypatch.setattr(filings_mod, "SessionLocal", TestingSession)
    filings_mod._filings_synced_at.clear()
    filings_mod._refreshing_keys.clear()
    filings_mod._history_backfilling_ids.clear()

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(main.app), TestingSession
    finally:
        main.app.dependency_overrides.pop(get_db, None)
        filings_mod._filings_synced_at.clear()
        filings_mod._refreshing_keys.clear()
        filings_mod._history_backfilling_ids.clear()


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
    """Warm background, cold-list and company-miss SEC waits all release the one-slot pool."""
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

    def override_get_db():
        with TestingSession() as db:
            yield db

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

    monkeypatch.setattr(filings_mod, "SessionLocal", TestingSession)
    monkeypatch.setattr(filing_history_service, "_fetch_history_rows", fake_history_fetch)
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", fake_get_filings)
    monkeypatch.setattr(filings_mod.sec_edgar_service, "search_company", fake_search_company)
    monkeypatch.setattr(
        filings_mod.sec_edgar_service, "primary_ticker_for_cik", fake_primary_ticker
    )
    filings_mod._filings_synced_at.clear()
    filings_mod._refreshing_keys.clear()
    filings_mod._history_backfilling_ids.clear()

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
        filings_mod._filings_synced_at.clear()
        filings_mod._refreshing_keys.clear()
        filings_mod._history_backfilling_ids.clear()
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


@pytest.mark.parametrize("synced_forms, expected_fetches", [
    (["10-K", "10-Q", "10-K/A", "10-Q/A"], 0),
    (["10-K", "10-Q"], 1),  # An original-only fetch never proves amendment freshness.
])
def test_db_first_skips_refresh_when_freshly_synced(client, monkeypatch, synced_forms, expected_fetches):
    tc, TestingSession = client
    with TestingSession() as s:
        company = _seed_company(s)
        _seed_filing(s, company, "0000895421-25-000010", "10-K", 2025)

    # Only a stamp covering every requested form can suppress the background refresh.
    filings_mod._mark_filings_synced("TESTCO", synced_forms)
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
    # Freshly-synced → DB-first serves without any SEC round-trip.
    filings_mod._mark_filings_synced("TESTCO", ["10-K", "10-Q", "10-K/A", "10-Q/A"])
    monkeypatch.setattr(filings_mod.sec_edgar_service, "get_filings", AsyncMock(return_value=[]))

    # Default: capped at CACHED_FILINGS_LIMIT (behaviour unchanged).
    default_resp = tc.get("/api/filings/company/TESTCO")
    assert default_resp.status_code == 200
    assert len(default_resp.json()) == filings_mod.CACHED_FILINGS_LIMIT

    # Explicit limit raises the ceiling to surface the full backfilled history.
    full_resp = tc.get("/api/filings/company/TESTCO?limit=100")
    assert full_resp.status_code == 200
    assert len(full_resp.json()) == 25
    # Newest-first ordering preserved.
    dates = [f["filing_date"] for f in full_resp.json()]
    assert dates == sorted(dates, reverse=True)
