"""E137: the two responses built outside ``add_security_headers`` carry its headers too.

``request_timeout_middleware`` sits outside ``add_security_headers``, so the 504 it builds never passes
back through it. Starlette answers the global ``Exception`` handler from ServerErrorMiddleware, outside
every user middleware, so the 500 does not either. /security says the API's responses under /api carry
a Content-Security-Policy of default-src 'none', so both set the headers themselves
(``main._security_headers``). The responses that do pass back through the middleware (a 404, the
CircuitOpenError and TaskUnavailable 503s) are test_security_headers.py's.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient

import main

TIMEOUT_PROBE = "/api/__e137_timeout_probe"
ERROR_PROBE = "/api/__e137_error_probe"

SECURITY_HEADERS = (
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
    "content-security-policy",
    "strict-transport-security",
)


@pytest.fixture
def probes(monkeypatch):
    """Two /api routes: one outlives the patched timeout, one raises an error nothing handles."""
    async def slow():  # pragma: no cover - never completes under the patched timeout
        await asyncio.sleep(0.5)
        return {"ok": True}

    async def broken():
        raise RuntimeError("probe failure")

    before = list(main.app.router.routes)
    main.app.add_api_route(TIMEOUT_PROBE, slow, methods=["GET"])
    main.app.add_api_route(ERROR_PROBE, broken, methods=["GET"])
    monkeypatch.setitem(main.REQUEST_TIMEOUT_SECONDS, "default", 0.01)
    try:
        yield TestClient(main.app, raise_server_exceptions=False)
    finally:
        main.app.router.routes[:] = before


def _security(response) -> dict[str, str]:
    return {name: response.headers[name] for name in SECURITY_HEADERS if name in response.headers}


def test_the_timeouts_504_carries_the_security_headers(probes):
    resp = probes.get(TIMEOUT_PROBE)

    assert resp.status_code == 504
    assert _security(resp) == {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "geolocation=(), microphone=(), camera=()",
        "content-security-policy": "default-src 'none'",
    }


def test_the_unhandled_errors_500_carries_the_security_headers(probes):
    resp = probes.get(ERROR_PROBE)

    assert resp.status_code == 500
    assert resp.json()["type"] == "internal_server_error"
    assert _security(resp) == {
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "strict-origin-when-cross-origin",
        "permissions-policy": "geolocation=(), microphone=(), camera=()",
        "content-security-policy": "default-src 'none'",
    }


def test_the_hand_built_responses_carry_what_the_middleware_stamps(probes):
    """The same set as an /api response that passes back through add_security_headers (a 404)."""
    stamped = _security(probes.get("/api/__e137_no_such_route__"))

    assert _security(probes.get(TIMEOUT_PROBE)) == stamped
    assert _security(probes.get(ERROR_PROBE)) == stamped


def test_in_production_the_504_and_the_500_carry_hsts(probes, monkeypatch):
    monkeypatch.setattr(main.settings, "ENVIRONMENT", "production")

    for path, status in ((TIMEOUT_PROBE, 504), (ERROR_PROBE, 500)):
        resp = probes.get(path)
        assert resp.status_code == status
        assert resp.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert resp.headers["content-security-policy"] == "default-src 'none'"


def test_the_500_keeps_its_cors_headers_beside_them(probes):
    """The security headers join the CORS headers the handler already re-applies; neither replaces the other."""
    resp = probes.get(ERROR_PROBE, headers={"origin": "http://localhost:3000"})

    assert resp.status_code == 500
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert resp.headers["content-security-policy"] == "default-src 'none'"
