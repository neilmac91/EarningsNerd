import os
import sys

import pytest
from fastapi.testclient import TestClient


def _load_app(tmp_path):
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_waitlist.db"
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["FRONTEND_URL"] = "https://earningsnerd.io"

    for module_name in list(sys.modules):
        if module_name == "main" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    import app.config
    import app.database
    import app.models
    import app.routers.watchlist
    import main

    app.database.Base.metadata.create_all(bind=app.database.engine)
    return main.app


def test_referral_code_uniqueness():
    from app.services.waitlist_service import generate_referral_code, REFERRAL_CODE_LENGTH

    codes = {generate_referral_code() for _ in range(250)}
    assert len(codes) == 250
    assert all(len(code) == REFERRAL_CODE_LENGTH for code in codes)


def test_position_calculation():
    from app.services.waitlist_service import calculate_waitlist_position, REFERRAL_BONUS

    assert calculate_waitlist_position(100, 0) == 100
    assert calculate_waitlist_position(100, 1) == 100 - REFERRAL_BONUS
    assert calculate_waitlist_position(3, 1) == 1


def test_waitlist_signup_flow(tmp_path, monkeypatch):
    app = _load_app(tmp_path)
    client = TestClient(app)

    import app.routers.watchlist as waitlist_router
    from app.services.rate_limiter import RateLimiter

    async def _noop_email(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.email_service.send_waitlist_welcome_email", _noop_email
    )
    monkeypatch.setattr(
        "app.services.email_service.send_referral_success_email", _noop_email
    )
    waitlist_router.WAITLIST_JOIN_LIMITER = RateLimiter(limit=100, window_seconds=60)

    payload = {"email": "person@example.com", "name": "Test User", "source": "homepage"}
    response = client.post("/api/waitlist/join", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["position"] >= 1
    assert data["referral_code"]

    status_response = client.get(f"/api/waitlist/status/{payload['email']}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["referral_code"] == data["referral_code"]

    duplicate_response = client.post("/api/waitlist/join", json=payload)
    assert duplicate_response.status_code == 200
    duplicate_payload = duplicate_response.json()
    assert duplicate_payload["success"] is False
    assert duplicate_payload["error"] == "already_registered"


def test_invalid_referral_code(tmp_path, monkeypatch):
    app = _load_app(tmp_path)
    client = TestClient(app)

    import app.routers.watchlist as waitlist_router
    from app.services.rate_limiter import RateLimiter

    async def _noop_email(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.email_service.send_waitlist_welcome_email", _noop_email
    )
    waitlist_router.WAITLIST_JOIN_LIMITER = RateLimiter(limit=100, window_seconds=60)

    payload = {
        "email": "invalid@example.com",
        "referral_code": "badcode",
        "source": "homepage",
    }
    response = client.post("/api/waitlist/join", json=payload)
    assert response.status_code == 400


def test_referral_increases_priority_score(tmp_path, monkeypatch):
    app = _load_app(tmp_path)
    client = TestClient(app)

    import app.routers.watchlist as waitlist_router
    from app.services.rate_limiter import RateLimiter
    from app.services.waitlist_service import REFERRAL_BONUS

    async def _noop_email(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.email_service.send_waitlist_welcome_email", _noop_email
    )
    monkeypatch.setattr(
        "app.services.email_service.send_referral_success_email", _noop_email
    )
    waitlist_router.WAITLIST_JOIN_LIMITER = RateLimiter(limit=100, window_seconds=60)

    referrer = client.post(
        "/api/waitlist/join",
        json={"email": "referrer@example.com", "name": "Referrer"},
    ).json()

    client.post(
        "/api/waitlist/join",
        json={"email": "friend@example.com", "referral_code": referrer["referral_code"]},
    )

    status_response = client.get("/api/waitlist/status/referrer@example.com")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["positions_gained"] == REFERRAL_BONUS
