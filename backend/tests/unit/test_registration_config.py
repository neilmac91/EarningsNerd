"""GET /api/auth/registration: the public read of the signup gate.

The marketing landing page derives its account CTAs (Create a free account vs Request an invite)
and the "Free for beta members" pricing line from this endpoint, so it must (a) mirror
settings.REGISTRATION_MODE exactly, (b) report whether the beta promo is configured, and (c) stay
unauthenticated and cacheable.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_public_mode_without_promo(client, monkeypatch):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "public")
    monkeypatch.setattr(auth_module.settings, "STRIPE_BETA_PROMO_CODE_ID", "")

    resp = client.get("/api/auth/registration")

    assert resp.status_code == 200
    assert resp.json() == {"mode": "public", "beta_promo_enabled": False}
    assert resp.headers["cache-control"] == "public, max-age=300"


def test_invite_only_mode_with_promo(client, monkeypatch):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(auth_module.settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_test123")

    resp = client.get("/api/auth/registration")

    assert resp.status_code == 200
    assert resp.json() == {"mode": "invite_only", "beta_promo_enabled": True}


def test_needs_no_credentials(client):
    # No Authorization header, no cookie: the landing page is rendered for anonymous visitors.
    resp = client.get("/api/auth/registration", headers={"Authorization": ""})
    assert resp.status_code == 200
    assert set(resp.json()) == {"mode", "beta_promo_enabled"}
