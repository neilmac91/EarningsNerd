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


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Clear the module-level auth limiters before each test so register/login pressure from
    one test (or another file in the same process) can't trip another test's request."""
    from app.routers import auth as auth_module

    for lim in (
        auth_module.LOGIN_LIMITER,
        auth_module.REGISTER_LIMITER,
        auth_module.ACCOUNT_LOGIN_FAIL_LIMITER,
        auth_module.RESET_REQUEST_LIMITER,
        auth_module.RESEND_VERIFY_LIMITER,
    ):
        lim._hits.clear()
    yield


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
def test_login_unknown_email_returns_same_401(client):
    """An unknown email returns the same generic 401 as a wrong password (no enumeration)."""
    client.cookies.clear()
    resp = client.post(
        "/api/auth/login",
        json={"email": _unique_email(), "password": VALID_PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"


@pytest.mark.requires_db
def test_login_inactive_account_returns_401_not_403(client):
    """A deactivated account is indistinguishable from a bad credential (generic 401, not 403)."""
    email = _unique_email()
    reg = client.post("/api/auth/register", json={"email": email, "password": VALID_PASSWORD})
    assert reg.status_code == 200, reg.text
    client.cookies.clear()

    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.is_active = False
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"
    client.cookies.clear()


@pytest.mark.requires_db
def test_repeated_failures_lock_the_account(client):
    """After enough failed attempts a single account is throttled (429), bounding brute-force.

    The per-IP limiter is cleared between attempts so this exercises the *per-account* throttle
    specifically rather than the per-IP one (both share the same default limit)."""
    from app.routers import auth as auth_module

    email = _unique_email()
    for _ in range(auth_module.ACCOUNT_LOGIN_FAIL_LIMITER.limit):
        auth_module.LOGIN_LIMITER._hits.clear()  # isolate the account throttle from the IP one
        resp = client.post("/api/auth/login", json={"email": email, "password": VALID_PASSWORD})
        assert resp.status_code == 401

    auth_module.LOGIN_LIMITER._hits.clear()
    resp = client.post("/api/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert resp.status_code == 429
    client.cookies.clear()


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


# --- Refresh token flow -----------------------------------------------------------------

@pytest.mark.requires_db
def test_register_sets_refresh_cookie(client):
    """Registration sets an HttpOnly, auth-path-scoped refresh cookie alongside the access cookie."""
    client.cookies.clear()
    resp = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    set_cookie = resp.headers.get("set-cookie", "")
    assert "earningsnerd_refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/auth" in set_cookie
    client.cookies.clear()


def _login(client, registered_user) -> str:
    """Log in and return the issued refresh-token cookie value."""
    resp = client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    refresh_cookie = client.cookies.get("earningsnerd_refresh_token")
    assert refresh_cookie
    return refresh_cookie


@pytest.mark.requires_db
def test_refresh_rotates_and_issues_new_access_token(client, registered_user):
    """A valid refresh cookie yields a new access token and rotates the refresh token."""
    client.cookies.clear()
    old_refresh = _login(client, registered_user)

    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]
    # Rotation: the cookie jar now holds a different refresh token.
    new_refresh = client.cookies.get("earningsnerd_refresh_token")
    assert new_refresh and new_refresh != old_refresh

    # The rotated (new) token still works for a subsequent refresh.
    assert client.post("/api/auth/refresh").status_code == 200
    client.cookies.clear()


@pytest.mark.requires_db
def test_refresh_reuse_of_rotated_token_is_rejected(client, registered_user):
    """Replaying a token that was already rotated away is rejected (reuse detection)."""
    client.cookies.clear()
    stolen = _login(client, registered_user)

    # Legitimate rotation consumes `stolen` and issues a replacement.
    assert client.post("/api/auth/refresh").status_code == 200

    # Replaying the consumed token (via body, since the cookie has rotated) is rejected.
    client.cookies.clear()
    resp = client.post("/api/auth/refresh", json={"refresh_token": stolen})
    assert resp.status_code == 401
    client.cookies.clear()


@pytest.mark.requires_db
def test_refresh_without_token_rejected(client):
    """Refresh with no cookie and no body token is a 401."""
    client.cookies.clear()
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.requires_db
def test_logout_revokes_refresh_token(client, registered_user):
    """After logout the previously-issued refresh token can no longer be used."""
    client.cookies.clear()
    refresh_before_logout = _login(client, registered_user)

    assert client.post("/api/auth/logout").status_code == 200

    # The token issued before logout is now revoked.
    client.cookies.clear()
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh_before_logout})
    assert resp.status_code == 401
    client.cookies.clear()
