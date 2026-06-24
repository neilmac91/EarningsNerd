"""
Tests for the admin invite endpoints (mint / list / revoke).

Uses TestClient against the app's SQLite DB and overrides only `get_current_user` (the real `get_db`
is kept so invites actually persist), mirroring the auth dependency-override pattern.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers.auth import get_current_user


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def as_admin():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, email="admin@example.com", is_admin=True
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def as_non_admin():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=2, email="user@example.com", is_admin=False
    )
    yield
    app.dependency_overrides.clear()


@pytest.mark.requires_db
def test_mint_returns_link_and_stores_only_the_hash(client, as_admin):
    from app.database import SessionLocal
    from app.models import InviteCode

    resp = client.post("/api/admin/invites", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "/register?invite=" in body["invite_link"]
    raw = body["invite_link"].split("invite=")[1]

    db = SessionLocal()
    try:
        assert db.query(InviteCode).filter(InviteCode.id == body["id"]).first() is not None
        # The raw token is never persisted — only its SHA-256 hash.
        assert db.query(InviteCode).filter(InviteCode.code_hash == raw).first() is None
    finally:
        db.close()


@pytest.mark.requires_db
def test_revoke_sets_status_revoked(client, as_admin):
    mint = client.post("/api/admin/invites", json={})
    invite_id = mint.json()["id"]
    rev = client.post(f"/api/admin/invites/{invite_id}/revoke")
    assert rev.status_code == 200, rev.text
    assert rev.json()["status"] == "revoked"


@pytest.mark.requires_db
def test_list_includes_minted_invite(client, as_admin):
    mint = client.post("/api/admin/invites", json={})
    invite_id = mint.json()["id"]
    listed = client.get("/api/admin/invites")
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == invite_id for row in listed.json()["invites"])


def test_non_admin_is_forbidden(client, as_non_admin):
    assert client.post("/api/admin/invites", json={}).status_code == 403
    assert client.get("/api/admin/invites").status_code == 403
