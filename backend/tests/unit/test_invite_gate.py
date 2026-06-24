"""
Integration tests for the invite-only registration gate (POST /api/auth/register).

Exercises the real endpoint against the app's SQLite DB (created by the TestClient lifespan), so the
invite_codes table and users.is_beta column come from Base.metadata.create_all — no Postgres needed.
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
    """Clear the auth limiters before each test (register is 5/min/IP)."""
    from app.routers import auth as auth_module

    for lim in (auth_module.REGISTER_LIMITER, auth_module.LOGIN_LIMITER):
        lim._hits.clear()
    yield


@pytest.fixture
def invite_only(monkeypatch):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")
    yield


def _unique_email() -> str:
    return f"invitetest_{uuid.uuid4().hex[:12]}@example.com"


def _mint_invite(**kwargs):
    """Mint an invite directly against the app DB; return the raw token."""
    from app.database import SessionLocal
    from app.services import invite_service

    db = SessionLocal()
    try:
        invite, raw, _link = invite_service.mint_invite(db, created_by=None, **kwargs)
        return invite.id, raw
    finally:
        db.close()


@pytest.mark.requires_db
def test_public_mode_ignores_invite(client):
    """Default (public) registration is unchanged — no invite required."""
    resp = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    client.cookies.clear()


@pytest.mark.requires_db
def test_invite_only_rejects_missing_and_bad_invites(client, invite_only):
    """Invite-only mode blocks public signup and rejects an unknown token (403)."""
    no_code = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD},
    )
    assert no_code.status_code == 403, no_code.text

    bad_code = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD, "invite_code": "garbage"},
    )
    assert bad_code.status_code == 403, bad_code.text


@pytest.mark.requires_db
def test_valid_invite_registers_sets_is_beta_and_is_single_use(client, invite_only):
    from app.database import SessionLocal
    from app.models import User, InviteCode

    invite_id, raw = _mint_invite(email=None)
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "invite_code": raw},
    )
    assert resp.status_code == 200, resp.text
    client.cookies.clear()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None and user.is_beta is True
        invite = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
        assert invite.used_at is not None and invite.user_id == user.id
    finally:
        db.close()

    # Single-use: the same token can't be redeemed again.
    reuse = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD, "invite_code": raw},
    )
    assert reuse.status_code == 403, reuse.text


@pytest.mark.requires_db
def test_email_bound_invite_requires_matching_email(client, invite_only):
    bound = _unique_email()
    _invite_id, raw = _mint_invite(email=bound)

    wrong = client.post(
        "/api/auth/register",
        json={"email": _unique_email(), "password": VALID_PASSWORD, "invite_code": raw},
    )
    assert wrong.status_code == 403, wrong.text

    ok = client.post(
        "/api/auth/register",
        json={"email": bound, "password": VALID_PASSWORD, "invite_code": raw},
    )
    assert ok.status_code == 200, ok.text
    client.cookies.clear()
