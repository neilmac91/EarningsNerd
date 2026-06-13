"""
Auth critical-path tests: register -> login -> authenticated request round-trip.

These exercise real JWT issuance, bcrypt hashing, and the HttpOnly cookie flow
against the app's default SQLite database (created by the TestClient lifespan),
so they run in CI without a Postgres service container.

Previously the auth suite only checked that endpoints existed (422/401); this
covers the actual success and failure paths.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from main import app

VALID_PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _unique_email() -> str:
    return f"authtest_{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture(scope="module")
def registered_user(client):
    """Register one user for the module (register is rate-limited to 5/min/IP)."""
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": "Auth Test"},
    )
    assert resp.status_code == 200, resp.text
    return {"email": email, "password": VALID_PASSWORD}


@pytest.mark.requires_db
def test_register_issues_token_and_sets_cookie(client):
    """Registration returns a bearer token and sets the HttpOnly auth cookie."""
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    # Cookie is set and HttpOnly.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "earningsnerd_access_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    # Clean up cookie jar so it doesn't leak into other tests.
    client.cookies.clear()


@pytest.mark.requires_db
def test_login_then_me_round_trip(client, registered_user):
    """Login sets a cookie that authenticates a follow-up /me request."""
    login = client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    # Cookie-based auth (TestClient persists the cookie).
    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == registered_user["email"]
    client.cookies.clear()

    # Bearer-token auth works too.
    me_bearer = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_bearer.status_code == 200
    assert me_bearer.json()["email"] == registered_user["email"]


@pytest.mark.requires_db
def test_login_wrong_password_rejected(client, registered_user):
    """A wrong password returns 401, not a token."""
    resp = client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": "Wr0ngPassword123"},
    )
    assert resp.status_code == 401


@pytest.mark.requires_db
def test_duplicate_registration_rejected(client, registered_user):
    """Registering an existing email returns 400."""
    resp = client.post(
        "/api/auth/register",
        json={"email": registered_user["email"], "password": VALID_PASSWORD},
    )
    assert resp.status_code == 400


def test_me_requires_auth(client):
    """/me without credentials is rejected."""
    client.cookies.clear()
    resp = client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


def test_weak_password_rejected(client):
    """Passwords failing the policy are rejected at validation (422)."""
    resp = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": "short"},
    )
    assert resp.status_code == 422
