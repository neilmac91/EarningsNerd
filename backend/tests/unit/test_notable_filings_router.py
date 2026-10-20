"""GET /api/notable_filings — response shape, flag gating, limit bounds.

Each case reads a private in-memory database through the route's ``get_db``, so the companies and
summaries it seeds meet no other test's rows.
"""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import get_db
from app.models import Company, Filing, NotableFiling, Summary
from app.services import notable_filings_service as svc
from app.services.notable_filings_service import NotableFilingsService
from app.utils.datetimes import utcnow
from app.utils.sec_urls import build_sec_archive_url
from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh_service(monkeypatch):
    """Give the router a per-test service instance so the L1 cache can't cross tests."""
    import app.routers.notable_filings as router_module

    monkeypatch.setattr(router_module, "notable_filings_service", NotableFilingsService())


@pytest.fixture
def db():
    """The route's database for one case: a private in-memory SQLite behind ``get_db``."""
    from app.models import Base

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine)

    def override_get_db():
        session = sessions()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    seed = sessions()
    try:
        yield seed
    finally:
        seed.close()
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def _seed(db, ticker, *, days_ago=1, score=55):
    """A 10-K candidate from a company that holds a summary the filing page shows."""
    cik = f"{db.query(Company).count() + 1001:010d}"
    company = Company(cik=cik, ticker=ticker, name=f"{ticker} Inc")
    db.add(company)
    db.flush()
    accession = f"{cik}-26-000001"
    url = build_sec_archive_url(cik, accession)
    filing = Filing(company_id=company.id, accession_number=accession, filing_type="10-K",
                    filing_date=utcnow(), sec_url=url, document_url=f"{url}doc.htm")
    db.add(filing)
    db.flush()
    db.add(Summary(filing_id=filing.id, business_overview="Revenue rose 6% as services grew."))
    db.add(NotableFiling(
        accession_number=f"{ticker}-router-test",
        ticker=ticker,
        cik=cik,
        company_name=f"{ticker} Inc",
        form="10-K",
        reason="annual_report",
        filed_date=svc.today_eastern() - timedelta(days=days_ago),
        score=score,
        sec_url=f"https://www.sec.gov/Archives/edgar/data/1/{ticker}/",
    ))
    db.commit()


def test_flag_off_returns_empty(client, db):
    _seed(db, "AAA")
    _seed(db, "BBB")
    _seed(db, "CCC")
    resp = client.get("/api/notable_filings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filings"] == []
    assert body["status"] == "empty"
    assert body["timestamp"]


def test_seeded_and_enabled_returns_ranked_payload(client, db, monkeypatch):
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    _seed(db, "AAA", days_ago=1)
    _seed(db, "BBB", days_ago=2)
    _seed(db, "CCC", days_ago=3)
    resp = client.get("/api/notable_filings?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert [f["ticker"] for f in body["filings"]] == ["AAA", "BBB"]
    first = body["filings"][0]
    assert set(first) == {
        "ticker", "company_name", "form", "reason", "reason_label", "filed_date", "sec_url",
    }
    assert (first["form"], first["reason_label"]) == ("10-K", "Annual report")


def test_a_limit_above_six_is_served_six(client, db, monkeypatch):
    """The frontend's dormant fetcher asks for eight; the route answers it with D-046's six rather
    than a 422 its fetcher would read as an absent section."""
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    for days_ago in range(1, 9):
        _seed(db, f"TK{days_ago}", days_ago=days_ago)
    resp = client.get("/api/notable_filings?limit=8")
    assert resp.status_code == 200
    assert [f["ticker"] for f in resp.json()["filings"]] == [f"TK{n}" for n in range(1, 7)]


def test_limit_bounds(client):
    assert client.get("/api/notable_filings?limit=0").status_code == 422
    assert client.get("/api/notable_filings?limit=13").status_code == 422
