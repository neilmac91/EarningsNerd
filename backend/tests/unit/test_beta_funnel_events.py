"""
Tests for the closed-beta activation-funnel telemetry emitted from POST /api/auth/register
(roadmap Week 6). Asserts that signup_completed / invite_redeemed fire with the canonical
str(user.id) distinct_id (so server + client events stitch onto one person) and carry the right
properties — without sending PII. Reuses the real endpoint against the app's SQLite DB, mirroring
test_invite_gate.py.
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
    from app.routers import auth as auth_module

    for lim in (auth_module.REGISTER_LIMITER, auth_module.LOGIN_LIMITER):
        lim._hits.clear()
    yield


@pytest.fixture
def invite_only(monkeypatch):
    from app.routers import auth as auth_module

    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")
    yield


@pytest.fixture
def captured_events(monkeypatch):
    """Spy on capture_event. auth.py imports capture_event at module level, so patch the name bound
    in app.routers.auth (patching app.services.posthog_client would not affect the already-bound
    reference)."""
    events: list[tuple[str, str, dict]] = []

    def _spy(distinct_id, event, properties=None):
        events.append((distinct_id, event, properties or {}))

    monkeypatch.setattr("app.routers.auth.capture_event", _spy)
    return events


def _unique_email() -> str:
    return f"funnel_{uuid.uuid4().hex[:12]}@example.com"


def _mint_invite(**kwargs):
    from app.database import SessionLocal
    from app.services import invite_service

    db = SessionLocal()
    try:
        invite, raw, _link = invite_service.mint_invite(db, created_by=None, **kwargs)
        return invite.id, raw
    finally:
        db.close()


def _user_id(email: str) -> int:
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        return user.id
    finally:
        db.close()


def _find(events, name):
    return [e for e in events if e[1] == name]


@pytest.mark.requires_db
def test_public_signup_emits_signup_completed_not_beta(client, captured_events):
    """Public mode: signup_completed fires (is_beta False, invited False); no invite_redeemed."""
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    client.cookies.clear()

    signups = _find(captured_events, "signup_completed")
    assert len(signups) == 1
    distinct_id, _event, props = signups[0]
    assert distinct_id == str(_user_id(email))
    assert props == {"is_beta": False, "invited": False}
    assert _find(captured_events, "invite_redeemed") == []
    # No PII leaked into any event property.
    assert all(email not in str(p) for _d, _e, p in captured_events)


@pytest.mark.requires_db
def test_invited_signup_emits_invite_redeemed_and_signup_completed(
    client, invite_only, captured_events
):
    """Invite-only + valid invite: both invite_redeemed and signup_completed fire, keyed on the
    same user id, with is_beta/invited True."""
    invite_id, raw = _mint_invite(email=None)
    email = _unique_email()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": VALID_PASSWORD, "invite_code": raw},
    )
    assert resp.status_code == 200, resp.text
    client.cookies.clear()

    uid = str(_user_id(email))

    redeemed = _find(captured_events, "invite_redeemed")
    assert len(redeemed) == 1
    assert redeemed[0][0] == uid
    assert redeemed[0][2] == {"email_bound": False}  # minted with email=None

    signups = _find(captured_events, "signup_completed")
    assert len(signups) == 1
    assert signups[0][0] == uid
    assert signups[0][2] == {"is_beta": True, "invited": True}
