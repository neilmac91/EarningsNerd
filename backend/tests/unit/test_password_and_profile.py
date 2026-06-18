"""Phase 4: change-password (set/change, OAuth-only path) + profile name edit."""
import uuid
from contextlib import contextmanager

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from main import app
from app.database import get_db, SessionLocal
from app.models import User
from app.routers.auth import get_current_user, get_password_hash, verify_password


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _auth_as(*, has_password: bool):
    """Create a user and authenticate as them. The override fetches the user via the request's own
    get_db session, so endpoint mutations + commit persist (a plain detached stand-in would not)."""
    db = SessionLocal()
    user = User(
        email=f"p4-{uuid.uuid4().hex}@example.com",
        hashed_password=get_password_hash("OldStr0ngPassw0rd!") if has_password else None,
        full_name="Original Name",
        email_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()

    def _fetch_current_user(db=Depends(get_db)):
        return db.query(User).filter(User.id == uid).first()

    app.dependency_overrides[get_current_user] = _fetch_current_user
    try:
        yield uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        db = SessionLocal()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


def _reload_hash(uid):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == uid).first().hashed_password
    finally:
        db.close()


def _reload_name(uid):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == uid).first().full_name
    finally:
        db.close()


# --------------------------------------------------------------------------- change password

@pytest.mark.requires_db
def test_change_password_with_correct_current(client):
    with _auth_as(has_password=True) as uid:
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "OldStr0ngPassw0rd!", "new_password": "BrandNewPassw0rd!"},
        )
        assert resp.status_code == 200
        new_hash = _reload_hash(uid)
        assert verify_password("BrandNewPassw0rd!", new_hash)
        assert not verify_password("OldStr0ngPassw0rd!", new_hash)


@pytest.mark.requires_db
def test_change_password_wrong_current_is_rejected(client):
    with _auth_as(has_password=True) as uid:
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "WrongPassw0rd!!", "new_password": "BrandNewPassw0rd!"},
        )
        assert resp.status_code == 400
        # Password unchanged.
        assert verify_password("OldStr0ngPassw0rd!", _reload_hash(uid))


@pytest.mark.requires_db
def test_oauth_only_user_can_set_password_without_current(client):
    with _auth_as(has_password=False) as uid:
        assert _reload_hash(uid) is None
        resp = client.post(
            "/api/auth/change-password",
            json={"new_password": "FirstPassw0rd123!"},
        )
        assert resp.status_code == 200
        assert verify_password("FirstPassw0rd123!", _reload_hash(uid))


@pytest.mark.requires_db
def test_weak_new_password_is_rejected(client):
    with _auth_as(has_password=True):
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "OldStr0ngPassw0rd!", "new_password": "short"},
        )
        assert resp.status_code == 422  # fails the strength validator


# --------------------------------------------------------------------------- profile name

@pytest.mark.requires_db
def test_update_profile_name(client):
    with _auth_as(has_password=True) as uid:
        resp = client.patch("/api/users/me", json={"full_name": "  New Name  "})
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "New Name"  # trimmed
        assert _reload_name(uid) == "New Name"


@pytest.mark.requires_db
def test_clear_profile_name(client):
    with _auth_as(has_password=True) as uid:
        resp = client.patch("/api/users/me", json={"full_name": ""})
        assert resp.status_code == 200
        assert resp.json()["full_name"] is None
        assert _reload_name(uid) is None
