"""Characterization test T8: the auth refresh round-trip and reuse-theft revocation.

Pins two behaviors of the access/refresh token flow, exercised end-to-end against the app's
real router with real JWT issuance, real bcrypt hashing, and the real SQLite database created by
the TestClient lifespan (no network, no mocks):

1. Expired-access + refresh round-trip: an expired access token is rejected at a protected
   endpoint (401); the still-valid refresh token then mints a fresh access token; and the same
   protected endpoint accepts that new token.
2. Reuse-theft revokes the chain: replaying a refresh token that was already rotated away is
   rejected (401) *and* trips theft detection, which revokes the user's whole active chain — so
   the currently-valid rotated token is revoked too and can no longer refresh.

Modeled on tests/unit/test_auth_flow.py (same fixtures, helpers, and cookie handling).
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from main import app

VALID_PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit

REFRESH_COOKIE = "earningsnerd_refresh_token"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_rate_limiters(client):
    """Clear the module-level auth limiters and the DB-backed per-account lockout before each test,
    so register/login pressure from another test (or another file in the same process) can't trip
    this test's requests. Depends on ``client`` so the app lifespan has created the tables."""
    from app.routers import auth as auth_module

    for lim in (
        auth_module.LOGIN_LIMITER,
        auth_module.REGISTER_LIMITER,
        auth_module.RESET_REQUEST_LIMITER,
        auth_module.RESEND_VERIFY_LIMITER,
        auth_module.RESET_RESEND_IP_LIMITER,
    ):
        lim._hits.clear()
    from app.database import SessionLocal
    from app.models import LoginAttempt
    db = SessionLocal()
    try:
        db.query(LoginAttempt).delete()
        db.commit()
    finally:
        db.close()
    yield


def _unique_email() -> str:
    return f"refreshtest_{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture(scope="module")
def registered_user(client):
    """Register one user for the module (register is rate-limited to 5/min/IP)."""
    from app.routers import auth as auth_module

    auth_module.REGISTER_LIMITER._hits.clear()  # module fixtures run before the autouse reset
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "full_name": "Refresh Test"},
    )
    assert resp.status_code == 200, resp.text
    return {"email": email, "password": VALID_PASSWORD}


def _login(client, registered_user) -> str:
    """Log in and return the issued refresh-token cookie value (jar holds access + refresh)."""
    resp = client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    refresh_cookie = client.cookies.get(REFRESH_COOKIE)
    assert refresh_cookie
    return refresh_cookie


@pytest.mark.requires_db
def test_expired_access_then_refresh_round_trip(client, registered_user):
    """An expired access token is rejected; the refresh token mints a working replacement."""
    from app.routers.auth import create_access_token

    client.cookies.clear()
    # Log in — the jar now holds a valid refresh cookie (and a valid access cookie).
    _login(client, registered_user)

    # Mint an EXPIRED access token with the app's own JWT helper (exp one hour in the past —
    # well beyond the 10s decode leeway).
    expired = create_access_token(
        data={"sub": registered_user["email"]},
        expires_delta=timedelta(hours=-1),
    )

    # (1) The expired token is rejected at a protected endpoint. Passing it as a Bearer header
    #     forces it to be evaluated (Bearer strictly precedes the cookie in the app's token
    #     resolution), so the 401 is unambiguously from the expired token.
    rejected = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert rejected.status_code == 401, rejected.text

    # (2) Refresh with the still-valid refresh cookie (in the jar) → a brand-new access token.
    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    new_access = refreshed.json()["access_token"]
    assert new_access and new_access != expired

    # (3) Retrying the SAME protected endpoint with the new token now succeeds.
    ok = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["email"] == registered_user["email"]

    client.cookies.clear()


@pytest.mark.requires_db
def test_refresh_reuse_revokes_the_rotated_chain(client, registered_user):
    """Replaying a rotated-away refresh token is rejected AND revokes the whole active chain,
    so the currently-valid rotated token can no longer refresh either (theft mitigation)."""
    client.cookies.clear()
    # Log in and capture the first refresh token (this is the one that will be rotated away).
    old = _login(client, registered_user)

    # Legitimate rotation: consumes `old` and issues a replacement into the cookie jar.
    rotated_resp = client.post("/api/auth/refresh")
    assert rotated_resp.status_code == 200, rotated_resp.text
    rotated = client.cookies.get(REFRESH_COOKIE)
    assert rotated and rotated != old  # the currently-valid token after one rotation

    # Replay the already-rotated `old` token. The cookie is read before the body, so clear the
    # jar to force the endpoint onto the body token we supply.
    client.cookies.clear()
    reuse = client.post("/api/auth/refresh", json={"refresh_token": old})
    assert reuse.status_code == 401, reuse.text

    # Theft detection revoked the ENTIRE active chain — so the token that was valid a moment ago
    # (`rotated`) is now revoked too and can no longer be exchanged.
    client.cookies.clear()
    after_theft = client.post("/api/auth/refresh", json={"refresh_token": rotated})
    assert after_theft.status_code == 401, after_theft.text

    client.cookies.clear()
