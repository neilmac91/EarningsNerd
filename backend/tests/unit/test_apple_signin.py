"""
Apple Sign In tests.

Covers the security-critical pieces of the form_post flow:
  - id_token verification: JWKS `kid` selection and *mandatory* nonce binding
  - the callback's redirect branches (denied / invalid / state mismatch)
  - the account-resolution policy (link only when both sides verified; otherwise
    redirect with apple_account_conflict instead of a duplicate INSERT)

The crypto is mocked — we don't mint real Apple-signed tokens — so these assert
our verification *logic*, not python-jose's signature math. They run against the
app's default SQLite database (created by the TestClient lifespan), like the
rest of the auth suite.
"""

import hashlib
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import JWTError

from main import app
from app.database import SessionLocal
from app.models import OAuthAccount, OAuthState, User
from app.routers import auth as auth_module
from app.services import oauth_verify  # id-token verification moved here (roadmap S3)

RAW_NONCE = "raw-nonce-value-123"
HASHED_NONCE = hashlib.sha256(RAW_NONCE.encode()).hexdigest()
FAKE_JWKS = {"keys": [{"kid": "applekey1", "kty": "RSA", "n": "x", "e": "AQAB"}]}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _seed_state(nonce: str = RAW_NONCE, ttl_minutes: int = 5) -> str:
    """Insert a fresh OAuthState row and return its state token."""
    state = f"state_{uuid.uuid4().hex}"
    db = SessionLocal()
    try:
        db.add(OAuthState(
            state=state,
            nonce=nonce,
            # Naive UTC to match the OAuthState model + the auth.py comparison.
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        ))
        db.commit()
    finally:
        db.close()
    return state


# ── _verify_apple_id_token: JWKS key selection + mandatory nonce ──────────────

@pytest.mark.asyncio
async def test_verify_returns_claims_on_valid_token_and_nonce():
    claims = {"sub": "001", "email": "a@b.com", "nonce": HASHED_NONCE}
    with patch.object(oauth_verify, "_get_apple_jwks", AsyncMock(return_value=FAKE_JWKS)), \
         patch.object(oauth_verify.jwt, "get_unverified_header", return_value={"kid": "applekey1"}), \
         patch.object(oauth_verify.jwt, "decode", return_value=claims) as decode:
        out = await oauth_verify._verify_apple_id_token("dummy", RAW_NONCE)
    assert out["sub"] == "001"
    # The matching JWK (not the whole JWKS dict) is handed to jwt.decode.
    assert decode.call_args.args[1] == FAKE_JWKS["keys"][0]


@pytest.mark.asyncio
async def test_verify_rejects_nonce_mismatch():
    claims = {"sub": "001", "nonce": "a-different-nonce"}
    with patch.object(oauth_verify, "_get_apple_jwks", AsyncMock(return_value=FAKE_JWKS)), \
         patch.object(oauth_verify.jwt, "get_unverified_header", return_value={"kid": "applekey1"}), \
         patch.object(oauth_verify.jwt, "decode", return_value=claims):
        with pytest.raises(ValueError, match="nonce"):
            await oauth_verify._verify_apple_id_token("dummy", RAW_NONCE)


@pytest.mark.asyncio
async def test_verify_rejects_missing_nonce():
    """A token with no nonce claim must be rejected — nonce binding is mandatory."""
    claims = {"sub": "001"}  # no nonce echoed back
    with patch.object(oauth_verify, "_get_apple_jwks", AsyncMock(return_value=FAKE_JWKS)), \
         patch.object(oauth_verify.jwt, "get_unverified_header", return_value={"kid": "applekey1"}), \
         patch.object(oauth_verify.jwt, "decode", return_value=claims):
        with pytest.raises(ValueError, match="nonce"):
            await oauth_verify._verify_apple_id_token("dummy", RAW_NONCE)


@pytest.mark.asyncio
async def test_verify_rejects_when_kid_not_in_jwks():
    with patch.object(oauth_verify, "_get_apple_jwks", AsyncMock(return_value=FAKE_JWKS)), \
         patch.object(oauth_verify.jwt, "get_unverified_header", return_value={"kid": "unknown-kid"}):
        with pytest.raises(ValueError, match="Matching key not found"):
            await oauth_verify._verify_apple_id_token("dummy", RAW_NONCE)


@pytest.mark.asyncio
async def test_verify_wraps_jwt_error():
    with patch.object(oauth_verify, "_get_apple_jwks", AsyncMock(return_value=FAKE_JWKS)), \
         patch.object(oauth_verify.jwt, "get_unverified_header", return_value={"kid": "applekey1"}), \
         patch.object(oauth_verify.jwt, "decode", side_effect=JWTError("bad signature")):
        with pytest.raises(ValueError, match="invalid"):
            await oauth_verify._verify_apple_id_token("dummy", RAW_NONCE)


# ── callback redirect branches (no DB / crypto needed) ────────────────────────

def test_apple_login_unconfigured_returns_503(client):
    """With APPLE_CLIENT_ID unset (test default), initiating Apple login is a 503."""
    resp = client.get("/api/auth/apple", follow_redirects=False)
    assert resp.status_code == 503


def test_callback_user_denied_redirects(client):
    resp = client.post(
        "/api/auth/apple/callback",
        data={"error": "user_cancelled_authorize"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=apple_denied" in resp.headers["location"]


def test_callback_missing_fields_redirects(client):
    resp = client.post(
        "/api/auth/apple/callback",
        data={"state": "x"},  # no id_token
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=apple_invalid" in resp.headers["location"]


@pytest.mark.requires_db
def test_callback_unknown_state_redirects(client):
    resp = client.post(
        "/api/auth/apple/callback",
        data={"state": "does-not-exist", "id_token": "dummy"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=oauth_state_mismatch" in resp.headers["location"]


# ── account resolution policy ─────────────────────────────────────────────────

@pytest.mark.requires_db
def test_callback_conflict_when_existing_account_unverified(client):
    """Same email already held by an unverified local account → conflict, no duplicate INSERT."""
    email = f"conflict_{uuid.uuid4().hex[:10]}@example.com"
    db = SessionLocal()
    try:
        db.add(User(email=email, hashed_password="x", email_verified=False))
        db.commit()
    finally:
        db.close()

    state = _seed_state()
    claims = {
        "sub": f"apple_{uuid.uuid4().hex}",
        "email": email,
        "email_verified": "true",
        "nonce": HASHED_NONCE,
    }
    with patch.object(auth_module, "_verify_apple_id_token", AsyncMock(return_value=claims)):
        resp = client.post(
            "/api/auth/apple/callback",
            data={"state": state, "id_token": "dummy"},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    assert "error=apple_account_conflict" in resp.headers["location"]

    db = SessionLocal()
    try:
        # Exactly one user with that email (no duplicate), and no link was created.
        assert db.query(User).filter(User.email == email).count() == 1
        assert db.query(OAuthAccount).filter_by(provider_email=email).count() == 0
        # The single-use state row was consumed.
        assert db.query(OAuthState).filter_by(state=state).count() == 0
    finally:
        db.close()


@pytest.mark.requires_db
def test_callback_links_verified_account_and_stores_name(client):
    """Verified local account + Apple-verified email → link, issue session, store first-auth name."""
    email = f"verified_{uuid.uuid4().hex[:10]}@example.com"
    db = SessionLocal()
    try:
        db.add(User(email=email, hashed_password="x", email_verified=True))
        db.commit()
    finally:
        db.close()

    state = _seed_state()
    apple_sub = f"apple_{uuid.uuid4().hex}"
    claims = {"sub": apple_sub, "email": email, "email_verified": "true", "nonce": HASHED_NONCE}
    with patch.object(auth_module, "_verify_apple_id_token", AsyncMock(return_value=claims)):
        resp = client.post(
            "/api/auth/apple/callback",
            data={
                "state": state,
                "id_token": "dummy",
                "user": '{"name": {"firstName": "Jane", "lastName": "Doe"}}',
            },
            follow_redirects=False,
        )

    assert resp.status_code == 302
    # Session cookies are issued on success.
    assert "earningsnerd_access_token=" in resp.headers.get("set-cookie", "")

    db = SessionLocal()
    try:
        link = db.query(OAuthAccount).filter_by(
            provider="apple", provider_account_id=apple_sub
        ).first()
        assert link is not None
        assert link.user.email == email
        assert link.user.full_name == "Jane Doe"  # first-auth name captured
    finally:
        db.close()
    client.cookies.clear()
