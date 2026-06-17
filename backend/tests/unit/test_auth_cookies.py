"""Regression tests for the session-cookie scoping that caused the post-login redirect loop.

Root cause: in production COOKIE_DOMAIN was unset, so the auth cookie was host-only on
api.earningsnerd.io and the Next.js middleware on earningsnerd.io never saw it. These tests
pin (a) the access cookie is parent-domain scoped, (b) a durable, refresh-lifetime
session-presence cookie is issued for the edge middleware, and (c) the cookie-name contract
shared with frontend/middleware.ts.
"""
import pytest
from starlette.responses import Response

from app.config import settings
from app.routers.auth import (
    _set_auth_cookie,
    _clear_auth_cookie,
    SESSION_PRESENCE_COOKIE,
)


def _set_cookie_headers(response: Response) -> list[str]:
    return [v.decode() for (k, v) in response.raw_headers if k.decode().lower() == "set-cookie"]


@pytest.fixture
def domain_scoped(monkeypatch):
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".earningsnerd.io")


def test_access_cookie_is_parent_domain_scoped(domain_scoped):
    resp = Response()
    _set_auth_cookie(resp, "jwt.token.value")
    access = next(c for c in _set_cookie_headers(resp) if c.startswith(settings.COOKIE_NAME + "="))
    assert "Domain=.earningsnerd.io" in access  # the fix: NOT host-only on api.
    assert "HttpOnly" in access and "Path=/" in access


def test_session_presence_cookie_is_durable(domain_scoped):
    resp = Response()
    _set_auth_cookie(resp, "jwt.token.value")
    presence = next(
        c for c in _set_cookie_headers(resp) if c.startswith(SESSION_PRESENCE_COOKIE + "=")
    )
    assert "Domain=.earningsnerd.io" in presence
    # Lifetime mirrors the refresh token, far beyond the 30-min access token, so the middleware
    # gate survives access-token rotation.
    expected_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    assert f"Max-Age={expected_max_age}" in presence


def test_presence_cookie_name_matches_frontend_contract():
    # frontend/middleware.ts hardcodes this literal; the two must never drift.
    assert SESSION_PRESENCE_COOKIE == "en_session"


def test_clear_auth_cookie_clears_both(domain_scoped):
    resp = Response()
    _clear_auth_cookie(resp)
    names = [c.split("=", 1)[0] for c in _set_cookie_headers(resp)]
    assert settings.COOKIE_NAME in names
    assert SESSION_PRESENCE_COOKIE in names
