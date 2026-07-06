"""GET /api/notable_filings — response shape, flag gating, limit bounds."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services import notable_filings_service as svc
from app.services.notable_filings_service import NotableFilingsService
from main import app


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh_service(monkeypatch):
    """Give the router a per-test service instance so the L1 cache can't cross tests."""
    import app.routers.notable_filings as router_module

    monkeypatch.setattr(router_module, "notable_filings_service", NotableFilingsService())
    yield
    _clear()


def _clear():
    from app.database import SessionLocal
    from app.models import NotableFiling

    db = SessionLocal()
    db.query(NotableFiling).delete(synchronize_session=False)
    db.commit()
    db.close()


def _seed(ticker, *, days_ago=1, score=80):
    from app.database import SessionLocal
    from app.models import NotableFiling

    today = svc.today_eastern()
    db = SessionLocal()
    db.add(NotableFiling(
        accession_number=f"{ticker}-router-test",
        ticker=ticker,
        company_name=f"{ticker} Inc",
        form="8-K",
        reason="earnings_results",
        filed_date=today - timedelta(days=days_ago),
        score=score,
        sec_url=f"https://www.sec.gov/Archives/edgar/data/1/{ticker}/",
    ))
    db.commit()
    db.close()


@pytest.mark.requires_db
def test_flag_off_returns_empty(client):
    _seed("AAA")
    _seed("BBB")
    _seed("CCC")
    resp = client.get("/api/notable_filings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["filings"] == []
    assert body["status"] == "empty"
    assert body["timestamp"]


@pytest.mark.requires_db
def test_seeded_and_enabled_returns_ranked_payload(client, monkeypatch):
    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    _seed("AAA", score=90)
    _seed("BBB", score=80)
    _seed("CCC", score=70)
    resp = client.get("/api/notable_filings?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert [f["ticker"] for f in body["filings"]] == ["AAA", "BBB"]
    first = body["filings"][0]
    assert set(first) == {
        "ticker", "company_name", "form", "reason", "reason_label", "filed_date", "sec_url",
    }
    assert first["reason_label"] == "Earnings results"


def test_limit_bounds(client):
    assert client.get("/api/notable_filings?limit=0").status_code == 422
    assert client.get("/api/notable_filings?limit=13").status_code == 422
