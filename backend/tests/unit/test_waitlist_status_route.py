"""Route tests for GET /api/waitlist/status/{email}.

The lookup is public, so it is bounded per client IP and answers with position and referral
progress only — never the referral code/link or the verification state. Per-test in-memory
SQLite, ``get_db`` overridden; client IPs are simulated through ``X-Forwarded-For`` with
``TRUSTED_PROXY_HOPS=1`` (the right-most hop is the trusted one).
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
from app.services import rate_limiter
from app.services.waitlist_service import REFERRAL_BONUS

IP_A = "203.0.113.7"
IP_B = "198.51.100.9"
REFERRER_CODE = "ref00001"


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
def client(session_factory, monkeypatch):
    watchlist_router.WAITLIST_STATUS_LIMITER._hits.clear()
    monkeypatch.setattr(rate_limiter.settings, "TRUSTED_PROXY_HOPS", 1)

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
        watchlist_router.WAITLIST_STATUS_LIMITER._hits.clear()


def _seed(session_factory, *, referrals: int = 0, priority_score: int = 0) -> str:
    """One verified signup at position 4 with ``referrals`` signups referred by it."""
    email = _email()
    with session_factory() as s:
        s.add(WaitlistSignup(email=email, name="Ref", referral_code=REFERRER_CODE, position=4,
                             priority_score=priority_score, email_verified=True))
        for i in range(referrals):
            s.add(WaitlistSignup(email=_email(), referral_code=f"joi{i:05d}", referred_by=REFERRER_CODE,
                                 position=10 + i, priority_score=0))
        s.commit()
    return email


def _status(client, email: str, ip: str = IP_A):
    return client.get(f"/api/waitlist/status/{email}", headers={"X-Forwarded-For": ip})


def test_status_returns_position_and_referral_progress_only(client, session_factory):
    email = _seed(session_factory, referrals=2, priority_score=2)
    resp = _status(client, email)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"position", "referrals_count", "positions_gained"}
    assert body["referrals_count"] == 2
    assert body["positions_gained"] == 2 * REFERRAL_BONUS
    assert body["position"] == watchlist_router.calculate_waitlist_position(4, 2)
    for dropped in ("referral_code", "referral_link", "email_verified", REFERRER_CODE):
        assert dropped not in resp.text


def test_unknown_email_is_404(client):
    resp = _status(client, _email())
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Email not found on the waitlist."


def test_status_is_rate_limited_per_client_ip(client, session_factory):
    email = _seed(session_factory)
    limiter = watchlist_router.WAITLIST_STATUS_LIMITER
    assert (limiter.limit, limiter.window_seconds) == (10, 60)

    for _ in range(limiter.limit):
        assert _status(client, email, IP_A).status_code == 200

    blocked = _status(client, email, IP_A)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "Too many status checks. Please try again later."
    assert 0 < int(blocked.headers["Retry-After"]) <= limiter.window_seconds

    # Misses are charged too: the limiter runs before the lookup.
    assert _status(client, _email(), IP_A).status_code == 429
    # Another client is unaffected.
    assert _status(client, email, IP_B).status_code == 200
