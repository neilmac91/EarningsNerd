"""GET /api/auth/registration: the public read of the signup gate.

The marketing landing page derives its account CTAs (Create a free account vs Request an invite)
and the "Free for beta members" pricing line from this endpoint, so it must (a) mirror
settings.REGISTRATION_MODE exactly, (b) require a configured promo and available checkout, (c) stay
unauthenticated, and (d) say whether the invited-cohort exception is open without naming its cohort,
in an answer no cache keeps: the register page reads it afresh before it offers an invitee the form.
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
    assert resp.json() == {"mode": "public", "beta_promo_enabled": False, "invited_cohort_available": False}
    assert resp.headers["cache-control"] == "no-store"


def test_invite_only_mode_with_promo(client, monkeypatch):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(auth_module.settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_test123")
    # Exercise the dormant enabled-offer contract without bypassing the production hold.
    monkeypatch.setattr(auth_module, "is_checkout_available", lambda: True)

    resp = client.get("/api/auth/registration")

    assert resp.status_code == 200
    assert resp.json() == {"mode": "invite_only", "beta_promo_enabled": True, "invited_cohort_available": False}


def test_configured_promo_does_not_promise_free_pro_while_checkout_is_held(client, monkeypatch):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(auth_module.settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_test123")

    resp = client.get("/api/auth/registration")

    assert resp.status_code == 200
    assert resp.json() == {"mode": "invite_only", "beta_promo_enabled": False, "invited_cohort_available": False}
    assert resp.headers["cache-control"] == "no-store"


def test_needs_no_credentials(client):
    # No Authorization header, no cookie: the landing page is rendered for anonymous visitors.
    resp = client.get("/api/auth/registration", headers={"Authorization": ""})
    assert resp.status_code == 200
    assert set(resp.json()) == {"mode", "beta_promo_enabled", "invited_cohort_available"}


# A synthetic, unguessable-looking label: it must never reach a public answer.
SYNTHETIC_COHORT = "cohort-synthetic-7f3a9c"


@pytest.mark.parametrize("mode, enabled, cohort, available", [
    ("invite_only", True, SYNTHETIC_COHORT, True),
    ("invite_only", False, SYNTHETIC_COHORT, False),   # the operator's switch is off
    ("invite_only", True, "", False),                  # no cohort configured
    ("invite_only", True, f" {SYNTHETIC_COHORT}", False),  # a value no minted invite could carry
    ("public", True, SYNTHETIC_COHORT, False),         # the exception only narrows invite-only registration
])
def test_the_invited_cohort_flag_says_only_whether_the_exception_is_open(
    client, monkeypatch, mode, enabled, cohort, available,
):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", mode)
    monkeypatch.setattr(auth_module.settings, "LEGAL_INVITED_COHORT_ENABLED", enabled)
    monkeypatch.setattr(auth_module.settings, "LEGAL_INVITED_COHORT", cohort)

    resp = client.get("/api/auth/registration")

    assert resp.status_code == 200
    assert resp.json()["invited_cohort_available"] is available
    assert resp.headers["cache-control"] == "no-store"
    assert SYNTHETIC_COHORT not in resp.text


def test_an_open_exception_leaves_the_public_legal_readiness_answer_unchanged(client, monkeypatch):
    # Collection stays held (the conftest default): the exception opens neither collection, checkout, promotion nor
    # the operator notice, and the answer names no cohort.
    from app.routers import auth as auth_module

    closed = client.get("/api/legal/readiness").json()
    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(auth_module.settings, "LEGAL_INVITED_COHORT_ENABLED", True)
    monkeypatch.setattr(auth_module.settings, "LEGAL_INVITED_COHORT", SYNTHETIC_COHORT)

    opened = client.get("/api/legal/readiness")

    assert client.get("/api/auth/registration").json()["invited_cohort_available"] is True
    assert opened.json() == closed
    assert opened.json()["collection_available"] is False and opened.json()["operator"] is None
    assert SYNTHETIC_COHORT not in opened.text
