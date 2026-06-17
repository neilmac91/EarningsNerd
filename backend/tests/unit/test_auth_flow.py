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
def test_register_returns_opaque_message_and_no_session(client):
    """Verify-first signup: register returns a generic message and issues NO session (no
    access/refresh cookie, no token in the body) — it doesn't auto-log-in."""
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "message" in body
    assert "access_token" not in body
    set_cookie = resp.headers.get("set-cookie", "")
    assert "earningsnerd_access_token=" not in set_cookie
    assert "earningsnerd_refresh_token=" not in set_cookie
    client.cookies.clear()


@pytest.mark.requires_db
def test_register_creates_account_usable_for_login(client):
    """Even without a session, register creates the account so the chosen password works at login."""
    client.cookies.clear()
    email = _unique_email()
    reg = client.post("/api/auth/register", json={"email": email, "password": VALID_PASSWORD})
    assert reg.status_code == 200, reg.text
    assert "earningsnerd_refresh_token=" not in reg.headers.get("set-cookie", "")

    login = client.post("/api/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
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
def test_register_is_opaque_for_new_and_existing_email(client, registered_user):
    """Anti-enumeration: registering a brand-new email and an already-registered one return
    identical responses (same status, same body, no session cookie) — so probing /register
    cannot reveal which emails have accounts."""
    new_resp = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD},
    )
    client.cookies.clear()
    existing_resp = client.post(
        "/api/auth/register",
        json={"email": registered_user["email"], "password": VALID_PASSWORD},
    )
    client.cookies.clear()
    assert new_resp.status_code == existing_resp.status_code == 200
    assert new_resp.json() == existing_resp.json()
    assert "earningsnerd_access_token=" not in existing_resp.headers.get("set-cookie", "")


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
def test_login_sets_refresh_cookie(client, registered_user):
    """Login sets an HttpOnly, auth-path-scoped refresh cookie (register no longer issues one)."""
    client.cookies.clear()
    resp = client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
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


# --- Account-security endpoints ---------------------------------------------------------

@pytest.mark.requires_db
def test_logout_all_revokes_every_session(client, registered_user):
    """logout-all revokes the user's whole refresh-token chain (sign out everywhere)."""
    client.cookies.clear()
    refresh = _login(client, registered_user)
    assert client.post("/api/auth/logout-all").status_code == 200
    client.cookies.clear()
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401
    client.cookies.clear()


@pytest.mark.requires_db
def test_connections_lists_password_account(client, registered_user):
    """A password account reports has_password=True and no linked OAuth providers."""
    client.cookies.clear()
    _login(client, registered_user)
    resp = client.get("/api/auth/connections")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_password"] is True
    assert body["providers"] == []
    client.cookies.clear()


@pytest.mark.requires_db
def test_unlink_unknown_provider_rejected(client, registered_user):
    client.cookies.clear()
    _login(client, registered_user)
    assert client.delete("/api/auth/connections/myspace").status_code == 400
    client.cookies.clear()


@pytest.mark.requires_db
def test_unlink_provider_not_linked_returns_404(client, registered_user):
    client.cookies.clear()
    _login(client, registered_user)
    assert client.delete("/api/auth/connections/google").status_code == 404
    client.cookies.clear()


@pytest.mark.requires_db
def test_cannot_unlink_only_sign_in_method(client):
    """A social-only account (no password, single provider) can't unlink its last credential."""
    from app.database import SessionLocal
    from app.models import User, OAuthAccount
    from app.routers.auth import create_access_token

    email = _unique_email()
    db = SessionLocal()
    try:
        user = User(email=email, hashed_password=None, email_verified=True, full_name="Social Only")
        db.add(user)
        db.flush()
        db.add(OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=f"sub-{uuid.uuid4().hex}",
            provider_email=email,
        ))
        db.commit()
    finally:
        db.close()

    token = create_access_token(data={"sub": email})
    client.cookies.clear()
    resp = client.delete(
        "/api/auth/connections/google", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 400
    assert "only sign-in method" in resp.json()["detail"]
    client.cookies.clear()
