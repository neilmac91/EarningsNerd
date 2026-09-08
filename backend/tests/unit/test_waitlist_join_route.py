"""Route tests for POST /api/waitlist/join (E13c).

Per-test in-memory SQLite, ``get_db`` overridden, both email senders monkeypatched on the router
module (they are imported by name there). Every test uses uuid emails so no two rows can collide
even if the engine were ever shared.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db
from app.models import WaitlistSignup
from app.routers import watchlist as watchlist_router
from app.services import turnstile


def _email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def emails(monkeypatch):
    """Recorders for the welcome + referral senders; ``welcome_error`` makes the welcome send raise."""
    rec = {"welcome": [], "referral": [], "welcome_error": None}

    async def _welcome(**kwargs):
        rec["welcome"].append(kwargs)
        if rec["welcome_error"] is not None:
            raise rec["welcome_error"]

    async def _referral(**kwargs):
        rec["referral"].append(kwargs)

    monkeypatch.setattr(watchlist_router, "send_waitlist_welcome_email", _welcome)
    monkeypatch.setattr(watchlist_router, "send_referral_success_email", _referral)
    return rec


@pytest.fixture
def client(session_factory, monkeypatch, emails):
    watchlist_router.WAITLIST_JOIN_LIMITER._hits.clear()
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        watchlist_router.WAITLIST_JOIN_LIMITER._hits.clear()
        with session_factory() as s:
            s.query(WaitlistSignup).delete()
            s.commit()


def _join(client, **payload):
    return client.post("/api/waitlist/join", json=payload)


def _seed_referrer(session_factory, code: str = "ref00001") -> str:
    email = _email()
    with session_factory() as s:
        s.add(WaitlistSignup(email=email, name="Ref", referral_code=code, position=1, priority_score=0))
        s.commit()
    return email


def test_honeypot_is_rejected_with_400(client, session_factory):
    resp = _join(client, email=_email(), honeypot="bot-filled")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid submission."
    with session_factory() as s:
        assert s.query(WaitlistSignup).count() == 0


def test_unknown_referral_code_is_400_invalid_referral(client, session_factory):
    resp = _join(client, email=_email(), referral_code="nosuch01")
    assert resp.status_code == 400
    assert resp.json() == {
        "success": False,
        "error": "invalid_referral",
        "message": "Referral code not recognized.",
    }
    with session_factory() as s:
        assert s.query(WaitlistSignup).count() == 0


def test_duplicate_email_returns_already_registered(client, emails):
    email = _email()
    first = _join(client, email=email)
    assert first.status_code == 200 and first.json()["success"] is True

    dup = _join(client, email=email.upper())  # the validator lower-cases, so this is the same row
    assert dup.status_code == 200
    body = dup.json()
    assert body["success"] is False and body["error"] == "already_registered"
    assert body["referral_code"] == first.json()["referral_code"]
    assert len(emails["welcome"]) == 1  # no second welcome email


def test_valid_referral_bumps_referrer_priority_and_sends_referral_email(client, session_factory, emails):
    referrer_email = _seed_referrer(session_factory, code="ref00001")
    resp = _join(client, email=_email(), referral_code="REF00001")  # normalised to lower-case
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True

    with session_factory() as s:
        referrer = s.query(WaitlistSignup).filter_by(email=referrer_email).one()
        assert referrer.priority_score == 1
        joined = s.query(WaitlistSignup).filter_by(referred_by="ref00001").one()
        assert joined.referral_code == resp.json()["referral_code"]

    assert [r["to_email"] for r in emails["referral"]] == [referrer_email]
    assert emails["referral"][0]["new_position"] == watchlist_router.calculate_waitlist_position(1, 1)


def test_welcome_email_sent_flag_tracks_the_send(client, session_factory, emails):
    ok_email = _email()
    ok = _join(client, email=ok_email)
    assert ok.status_code == 200 and ok.json()["email_sent"] is True

    emails["welcome_error"] = RuntimeError("resend down")
    failed_email = _email()
    failed = _join(client, email=failed_email)
    assert failed.status_code == 200, failed.text
    assert failed.json()["success"] is True and failed.json()["email_sent"] is False

    with session_factory() as s:
        rows = {r.email: r.welcome_email_sent for r in s.query(WaitlistSignup).all()}
    assert rows[ok_email] is True
    assert rows[failed_email] is False  # row persists, flag stays False
    assert len(emails["welcome"]) == 2
