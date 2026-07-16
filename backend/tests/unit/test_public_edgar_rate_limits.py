"""Per-IP rate limits on the unauthenticated always-live-EDGAR endpoints.

/api/companies/{ticker}/insiders and /api/search/full-text hit SEC EDGAR live on every
request (no DB cache), so without a per-IP limit an anonymous burst can drain the
process-wide 10 req/s SEC budget for everyone. These tests pin that both endpoints 429
past their limit — with the upstream call faked so no test touches the network.
"""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import main
from app.routers import insiders as insiders_mod
from app.routers import search as search_mod
from app.schemas.insiders import InsiderActivityResponse, InsiderActivitySummary
from app.services.rate_limiter import RateLimiter


@pytest.fixture
def client():
    return TestClient(main.app)


def test_insiders_endpoint_429s_past_per_ip_limit(client, monkeypatch):
    monkeypatch.setattr(insiders_mod, "_insiders_rate_limiter", RateLimiter(limit=3, window_seconds=60))
    fake = InsiderActivityResponse(
        ticker="AAPL",
        window_days=90,
        summary=InsiderActivitySummary(
            window_days=90,
            buy_count=0,
            sell_count=0,
            buy_shares=0.0,
            sell_shares=0.0,
            net_shares=0.0,
            discretionary_net_shares=0.0,
            plan_10b5_1_sell_shares=0.0,
        ),
        transactions=[],
        total_transactions=0,
    )
    monkeypatch.setattr(
        insiders_mod.insider_service, "get_insider_activity", AsyncMock(return_value=fake)
    )

    for _ in range(3):
        assert client.get("/api/companies/AAPL/insiders").status_code == 200
    blocked = client.get("/api/companies/AAPL/insiders")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_full_text_search_429s_past_per_ip_limit(client, monkeypatch):
    monkeypatch.setattr(search_mod, "_fts_rate_limiter", RateLimiter(limit=3, window_seconds=60))

    class FakeResult:
        query = "material weakness"
        total = 0
        hits = []

    monkeypatch.setattr(
        search_mod.sec_full_text_search_client, "search", AsyncMock(return_value=FakeResult())
    )

    for _ in range(3):
        assert client.get("/api/search/full-text", params={"q": "material weakness"}).status_code == 200
    blocked = client.get("/api/search/full-text", params={"q": "material weakness"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
