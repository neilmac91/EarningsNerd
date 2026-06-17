"""GET/PUT /api/users/me/notification-preferences — defaults + Pro-gating coercion.

Auth is bypassed with a dependency override returning a stand-in user (id + is_pro + subscription),
which is all the endpoints + entitlements need. A real users row is created so the prefs FK is valid.
"""
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers.auth import get_current_user


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _as_user(is_pro):
    from app.database import SessionLocal
    from app.models import NotificationPreferences, User

    db = SessionLocal()
    user = User(email=f"prefs-{uuid.uuid4().hex}@example.com", hashed_password="x",
                email_verified=True, is_active=True, is_pro=is_pro)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=uid, is_pro=is_pro, subscription=None, email="x@example.com", full_name="Tester"
    )
    try:
        yield uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        db = SessionLocal()
        db.query(NotificationPreferences).filter(NotificationPreferences.user_id == uid).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


@pytest.mark.requires_db
def test_get_creates_defaults(client):
    with _as_user(is_pro=False):
        resp = client.get("/api/users/me/notification-preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert body["notify_10k"] is True
        assert body["notify_10q"] is True
        assert body["notify_8k"] is False
        assert body["realtime"] is False
        assert body["digest"] == "daily"
        assert body["realtime_available"] is False
        assert body["eightk_available"] is False


@pytest.mark.requires_db
def test_put_coerces_pro_toggles_for_free_user(client):
    with _as_user(is_pro=False):
        resp = client.put(
            "/api/users/me/notification-preferences",
            json={"realtime": True, "notify_8k": True, "notify_10q": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["realtime"] is False     # coerced off (not Pro)
        assert body["notify_8k"] is False     # coerced off (not Pro)
        assert body["notify_10q"] is False    # non-gated change persists


@pytest.mark.requires_db
def test_put_allows_pro_toggles_for_pro_user(client):
    with _as_user(is_pro=True):
        resp = client.put(
            "/api/users/me/notification-preferences",
            json={"realtime": True, "notify_8k": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["realtime"] is True
        assert body["notify_8k"] is True
        assert body["realtime_available"] is True
        assert body["eightk_available"] is True


@pytest.mark.requires_db
def test_put_rejects_invalid_digest(client):
    with _as_user(is_pro=False):
        resp = client.put("/api/users/me/notification-preferences", json={"digest": "hourly"})
        assert resp.status_code == 400
