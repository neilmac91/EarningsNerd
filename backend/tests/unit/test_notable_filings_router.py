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
    monkeypatch.setattr(
        router_module, "homepage_notable_filings_service", NotableFilingsService(homepage_only=True)
    )
    yield
    _clear()


def _clear():
    from app.database import SessionLocal
    from app.models import NotableFiling

    db = SessionLocal()
    db.query(NotableFiling).delete(synchronize_session=False)
    db.commit()
    db.close()


def _seed(ticker, *, days_ago=1, score=80, form="8-K", accession=None):
    from app.database import SessionLocal
    from app.models import NotableFiling

    today = svc.today_eastern()
    db = SessionLocal()
    db.add(NotableFiling(
        accession_number=accession or f"{ticker}-router-test",
        ticker=ticker,
        company_name=f"{ticker} Inc",
        form=form,
        reason={"10-K": "annual_report", "10-Q": "quarterly_report"}.get(form, "earnings_results"),
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
    assert first["reason_label"] == "Results or financial condition"


def test_limit_bounds(client):
    assert client.get("/api/notable_filings?limit=0").status_code == 422
    assert client.get("/api/notable_filings?limit=13").status_code == 422


@pytest.mark.requires_db
@pytest.mark.parametrize("homepage_first", [False, True])
def test_homepage_curation_filters_the_full_window_and_keeps_default_feed(
    client, monkeypatch, homepage_first
):
    """The homepage policy owns eligibility, before dedupe/minimum/limit, in either cache order."""
    from datetime import date

    import app.routers.notable_filings as router_module
    from app.services import index_membership_service

    monkeypatch.setattr(settings, "NOTABLE_FILINGS_ENABLED", True)
    monkeypatch.setattr(svc, "today_eastern", lambda: date(2026, 7, 6))
    monkeypatch.setattr(index_membership_service, "member_tickers", lambda: frozenset({"AAPL", "MSFT", "BRK.B"}))
    for i in range(13):
        _seed(f"TAIL{i}", score=100 + i)
    _seed("AAPL", score=200)  # Wins this issuer in the ordinary feed; cannot hide its 10-K.
    _seed("AAPL", form="10-K", score=55, accession="aapl-annual")
    _seed("MSFT", form="10-Q", score=45)
    _seed("MSFT", form="10-K", score=1000, days_ago=8, accession="msft-stale")
    _seed("BRK-B", form="10-K", score=50, days_ago=7)  # Inclusive freshness boundary.
    _seed("BRK.B", form="10-Q", score=40, days_ago=7)  # Same normalized issuer, not a fourth.
    _seed("OUTSIDE", form="10-K", score=999)

    ordinary_url = "/api/notable_filings?limit=12"
    curated_url = "/api/notable_filings?homepage_only=true&limit=2"
    urls = [curated_url, ordinary_url] if homepage_first else [ordinary_url, curated_url]
    responses = {url: client.get(url) for url in urls}
    assert all(response.status_code == 200 for response in responses.values())
    ordinary = responses[ordinary_url].json()
    assert len(ordinary["filings"]) == 12
    assert ordinary["filings"][0]["ticker"] == "OUTSIDE"
    assert any(row["form"] == "8-K" for row in ordinary["filings"])
    curated = responses[curated_url].json()
    assert curated["status"] == "ok"
    assert [(row["ticker"], row["form"]) for row in curated["filings"]] == [
        ("AAPL", "10-K"), ("MSFT", "10-Q"),
    ]
    # Cached ranking is complete; the next limit reveals the third issuer, not the alias twice.
    full = client.get("/api/notable_filings?homepage_only=true&limit=8").json()
    assert [(row["ticker"], row["form"]) for row in full["filings"]] == [
        ("AAPL", "10-K"), ("MSFT", "10-Q"), ("BRK-B", "10-K"),
    ]
    assert full["timestamp"] == curated["timestamp"]
    assert client.get(ordinary_url).json() == ordinary  # Curated cache cannot replace the default.

    # A new instance represents a reloaded committed universe; only two issuers, or an unavailable
    # universe, must omit the curated surface even though the ordinary feed still has ample rows.
    for members in (frozenset({"AAPL", "MSFT"}), frozenset()):
        monkeypatch.setattr(index_membership_service, "member_tickers", lambda: members)
        monkeypatch.setattr(
            router_module, "homepage_notable_filings_service", NotableFilingsService(homepage_only=True)
        )
        empty = client.get(curated_url).json()
        assert empty["status"] == "empty"
        assert empty["filings"] == []
        assert client.get(ordinary_url).json() == ordinary
