"""The per-IP rate limit on the unauthenticated always-live-EDGAR endpoint.

/api/search/full-text hits SEC EDGAR live on every request (no DB cache), so without a per-IP limit an anonymous
burst can drain the process-wide SEC budget for everyone. This pins that it answers 429 past its limit, with the
upstream call faked so no test touches the network. The insider endpoint was the other such route; it now reads
the database for a signed-in beta account (ADR 0009) and its tests are tests/unit/test_insiders_route.py.
"""
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import main
from app.routers import search as search_mod
from app.services.rate_limiter import RateLimiter


@pytest.fixture
def client():
    return TestClient(main.app)


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
