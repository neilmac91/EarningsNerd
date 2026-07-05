"""Anchor: the security-header middleware in ``main.py`` (``add_security_headers``).

Promoted into the Wave 0 anchor set (PR #546 review). The deleted orphan
``test_endpoint_security.py`` was the *only* test asserting these headers, so a regression in
the middleware would otherwise ship silently. This is a route-level test against the current app.
"""
import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_always_on_security_headers(client):
    """The four unconditional headers are stamped on every response."""
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert r.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"


def test_csp_header_on_api_paths(client):
    """Content-Security-Policy is stamped on ``/api/`` responses (the 404 still passes the
    middleware, so no route/auth setup is needed to observe the header)."""
    r = client.get("/api/__no_such_route__")
    assert r.headers["Content-Security-Policy"] == "default-src 'none'"
    # and the unconditional headers ride along on API responses too
    assert r.headers["X-Content-Type-Options"] == "nosniff"
