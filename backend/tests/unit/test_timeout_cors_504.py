"""QW3 (PR#573) — the request-timeout middleware's 504 must carry CORS headers.

request_timeout_middleware sits OUTSIDE CORSMiddleware, so a 504 it synthesizes never passes back
through CORSMiddleware. Without Access-Control-Allow-Origin the browser blocks the cross-origin 504
and the client shows an opaque "Unable to connect to the server" instead of the real timeout — the
exact masking behind the reported bug. This pins the fix (the 500/503 handlers are already guarded).
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def slow_route():
    # A non-streaming route that outlives the (patched-tiny) timeout. Path matches no prefix/suffix
    # in the timeout tables, so it uses the "default" bucket.
    if "/__cors_timeout_probe" not in {getattr(r, "path", None) for r in main.app.routes}:
        @main.app.get("/__cors_timeout_probe")
        async def _probe():  # pragma: no cover - never completes under the patched timeout
            await asyncio.sleep(0.5)
            return {"ok": True}
    yield


def test_timeout_504_includes_cors_headers(slow_route, monkeypatch):
    monkeypatch.setitem(main.REQUEST_TIMEOUT_SECONDS, "default", 0.01)
    client = TestClient(main.app)

    resp = client.get("/__cors_timeout_probe", headers={"origin": "http://localhost:3000"})

    assert resp.status_code == 504
    # The masking is exactly the absence of this header — it must be present and echo the origin.
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp.headers.get("access-control-allow-credentials") == "true"
    body = resp.json()
    assert "timed out" in body["detail"].lower()


def test_timeout_504_omits_cors_for_disallowed_origin(slow_route, monkeypatch):
    monkeypatch.setitem(main.REQUEST_TIMEOUT_SECONDS, "default", 0.01)
    client = TestClient(main.app)

    resp = client.get("/__cors_timeout_probe", headers={"origin": "https://evil.example.com"})

    assert resp.status_code == 504
    # A non-allowlisted origin gets no allow-origin header (no reflection).
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}
