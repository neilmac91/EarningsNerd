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


@pytest.mark.requires_db
def test_mint_persists_and_returns_cohort(client, as_admin):
    from app.database import SessionLocal
    from app.models import InviteCode

    resp = client.post("/api/admin/invites", json={"cohort": "wave-1"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cohort"] == "wave-1"

    db = SessionLocal()
    try:
        row = db.query(InviteCode).filter(InviteCode.id == body["id"]).first()
        assert row is not None
        assert row.cohort == "wave-1"
    finally:
        db.close()


@pytest.mark.requires_db
def test_list_returns_cohort(client, as_admin):
    mint = client.post("/api/admin/invites", json={"cohort": "wave-2"})
    invite_id = mint.json()["id"]
    listed = client.get("/api/admin/invites")
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json()["invites"] if r["id"] == invite_id)
    assert row["cohort"] == "wave-2"


@pytest.mark.requires_db
def test_resend_mints_new_invite_and_revokes_old(client, as_admin):
    from app.database import SessionLocal
    from app.models import InviteCode

    mint = client.post(
        "/api/admin/invites", json={"email": "resend@example.com", "cohort": "wave-3"}
    )
    assert mint.status_code == 200, mint.text
    old_id = mint.json()["id"]

    resend = client.post(f"/api/admin/invites/{old_id}/resend", json={})
    assert resend.status_code == 200, resend.text
    body = resend.json()

    # A brand-new invite was minted with the same email + cohort.
    assert body["id"] != old_id
    assert body["revoked_invite_id"] == old_id
    assert body["email"] == "resend@example.com"
    assert body["cohort"] == "wave-3"
    assert "/register?invite=" in body["invite_link"]

    db = SessionLocal()
    try:
        old = db.query(InviteCode).filter(InviteCode.id == old_id).first()
        new = db.query(InviteCode).filter(InviteCode.id == body["id"]).first()
        assert old.is_revoked is True
        assert new is not None
        assert new.is_revoked is False
        assert new.email == "resend@example.com"
        assert new.cohort == "wave-3"
    finally:
        db.close()


@pytest.mark.requires_db
def test_resend_on_used_invite_returns_409(client, as_admin):
    from app.database import SessionLocal
    from app.models import InviteCode
    from app.services.invite_service import _now

    mint = client.post("/api/admin/invites", json={})
    invite_id = mint.json()["id"]

    # Mark the invite as redeemed.
    db = SessionLocal()
    try:
        row = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
        row.used_at = _now()
        db.commit()
    finally:
        db.close()

    resend = client.post(f"/api/admin/invites/{invite_id}/resend", json={})
    assert resend.status_code == 409, resend.text
    assert resend.json()["detail"] == "Invite already redeemed"


@pytest.mark.requires_db
def test_resend_not_found_returns_404(client, as_admin):
    resp = client.post("/api/admin/invites/99999999/resend", json={})
    assert resp.status_code == 404


@pytest.mark.requires_db
def test_audit_log_written_for_mint_resend_revoke(client, as_admin):
    from app.database import SessionLocal
    from app.models.audit_log import AuditLog

    mint = client.post("/api/admin/invites", json={"cohort": "audit-cohort"})
    minted_id = mint.json()["id"]

    resend = client.post(f"/api/admin/invites/{minted_id}/resend", json={})
    new_id = resend.json()["id"]

    client.post(f"/api/admin/invites/{new_id}/revoke")

    db = SessionLocal()
    try:
        minted = db.query(AuditLog).filter(
            AuditLog.action == "invite_minted", AuditLog.entity_id == str(minted_id)
        ).first()
        resent = db.query(AuditLog).filter(
            AuditLog.action == "invite_resent", AuditLog.entity_id == str(new_id)
        ).first()
        revoked = db.query(AuditLog).filter(
            AuditLog.action == "invite_revoked", AuditLog.entity_id == str(new_id)
        ).first()
        assert minted is not None
        assert minted.entity_type == "invite"
        assert resent is not None
        assert resent.details.get("revoked_invite_id") == minted_id
        assert revoked is not None
    finally:
        db.close()


@pytest.mark.requires_db
def test_revoke_on_used_invite_returns_409(client, as_admin):
    from app.database import SessionLocal
    from app.models import InviteCode
    from app.services.invite_service import _now

    mint = client.post("/api/admin/invites", json={})
    invite_id = mint.json()["id"]

    db = SessionLocal()
    try:
        row = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
        row.used_at = _now()
        db.commit()
    finally:
        db.close()

    rev = client.post(f"/api/admin/invites/{invite_id}/revoke")
    assert rev.status_code == 409, rev.text
    assert rev.json()["detail"] == "Invite already redeemed"


@pytest.mark.requires_db
def test_used_status_outranks_revoked_in_list(client, as_admin):
    from app.database import SessionLocal
    from app.models import InviteCode
    from app.services.invite_service import _now

    mint = client.post("/api/admin/invites", json={})
    invite_id = mint.json()["id"]

    # Force the (legacy/edge) state where a row carries BOTH flags; redemption must win.
    db = SessionLocal()
    try:
        row = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
        row.used_at = _now()
        row.is_revoked = True
        db.commit()
    finally:
        db.close()

    listed = client.get("/api/admin/invites")
    row = next(r for r in listed.json()["invites"] if r["id"] == invite_id)
    assert row["status"] == "used"


@pytest.mark.requires_db
def test_mint_rejects_overlong_cohort_with_422(client, as_admin):
    resp = client.post("/api/admin/invites", json={"cohort": "x" * 65})
    assert resp.status_code == 422, resp.text


def test_non_admin_is_forbidden(client, as_non_admin):
    assert client.post("/api/admin/invites", json={}).status_code == 403
    assert client.get("/api/admin/invites").status_code == 403
    assert client.post("/api/admin/invites/1/resend", json={}).status_code == 403
    assert client.post("/api/admin/invites/1/revoke").status_code == 403
