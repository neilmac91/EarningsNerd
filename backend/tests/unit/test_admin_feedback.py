"""
Tests for the admin feedback endpoints (list / patch status).

Mirrors the admin-invites harness: TestClient against the app's SQLite DB, overriding only
`get_current_user` (the real `get_db` is kept so feedback rows actually persist).
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


def _seed_feedback(user_id=None, user_email=None, type="general", status="new", message="Test feedback message"):
    """Insert a feedback row (and optionally a user to join against) and return its id."""
    from app.database import SessionLocal
    from app.models import User
    from app.models.feedback import Feedback

    db = SessionLocal()
    try:
        if user_id is not None and user_email is not None:
            existing = db.query(User).filter(User.id == user_id).first()
            if existing is None:
                db.add(User(id=user_id, email=user_email, hashed_password="x"))
                db.commit()
        fb = Feedback(
            user_id=user_id,
            type=type,
            message=message,
            page_url="/dashboard",
            status=status,
        )
        db.add(fb)
        db.commit()
        db.refresh(fb)
        return fb.id
    finally:
        db.close()


@pytest.mark.requires_db
def test_list_returns_rows_with_user_email(client, as_admin):
    fb_id = _seed_feedback(user_id=501, user_email="reporter@example.com", type="bug")
    resp = client.get("/api/admin/feedback")
    assert resp.status_code == 200, resp.text
    rows = resp.json()["feedback"]
    row = next(r for r in rows if r["id"] == fb_id)
    assert row["user_id"] == 501
    assert row["user_email"] == "reporter@example.com"
    assert row["type"] == "bug"
    assert row["status"] == "new"
    assert row["message"] == "Test feedback message"
    assert row["page_url"] == "/dashboard"
    assert "created_at" in row


@pytest.mark.requires_db
def test_list_handles_null_user_email(client, as_admin):
    # user_id null (anonymized / deleted submitter) — the left join keeps the row, email is null.
    fb_id = _seed_feedback(user_id=None, user_email=None, type="general")
    resp = client.get("/api/admin/feedback")
    assert resp.status_code == 200, resp.text
    row = next(r for r in resp.json()["feedback"] if r["id"] == fb_id)
    assert row["user_id"] is None
    assert row["user_email"] is None


@pytest.mark.requires_db
def test_list_filters_by_status(client, as_admin):
    new_id = _seed_feedback(status="new", message="new one for filter")
    resolved_id = _seed_feedback(status="resolved", message="resolved one for filter")
    resp = client.get("/api/admin/feedback?status=resolved")
    assert resp.status_code == 200, resp.text
    ids = {r["id"] for r in resp.json()["feedback"]}
    assert resolved_id in ids
    assert new_id not in ids


@pytest.mark.requires_db
def test_list_filters_by_type(client, as_admin):
    bug_id = _seed_feedback(type="bug", message="a bug for type filter")
    feature_id = _seed_feedback(type="feature", message="a feature for type filter")
    resp = client.get("/api/admin/feedback?type=feature")
    assert resp.status_code == 200, resp.text
    ids = {r["id"] for r in resp.json()["feedback"]}
    assert feature_id in ids
    assert bug_id not in ids


@pytest.mark.requires_db
def test_patch_transitions_status_and_persists(client, as_admin):
    from app.database import SessionLocal
    from app.models.feedback import Feedback

    fb_id = _seed_feedback(user_id=502, user_email="patchme@example.com", status="new")
    resp = client.patch(f"/api/admin/feedback/{fb_id}", json={"status": "triaged"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == fb_id
    assert body["status"] == "triaged"
    # Same shape as a list item, with user_email re-resolved.
    assert body["user_email"] == "patchme@example.com"
    assert body["user_id"] == 502

    db = SessionLocal()
    try:
        row = db.query(Feedback).filter(Feedback.id == fb_id).first()
        assert row.status == "triaged"
    finally:
        db.close()


@pytest.mark.requires_db
def test_patch_invalid_status_returns_422(client, as_admin):
    fb_id = _seed_feedback(status="new")
    resp = client.patch(f"/api/admin/feedback/{fb_id}", json={"status": "bogus"})
    assert resp.status_code == 422, resp.text


@pytest.mark.requires_db
def test_patch_missing_id_returns_404(client, as_admin):
    resp = client.patch("/api/admin/feedback/99999999", json={"status": "resolved"})
    assert resp.status_code == 404, resp.text


@pytest.mark.requires_db
def test_patch_writes_audit_log(client, as_admin):
    from app.database import SessionLocal
    from app.models.audit_log import AuditLog

    fb_id = _seed_feedback(status="new")
    resp = client.patch(f"/api/admin/feedback/{fb_id}", json={"status": "resolved"})
    assert resp.status_code == 200, resp.text

    db = SessionLocal()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.action == "feedback_status_changed",
            AuditLog.entity_id == str(fb_id),
        ).first()
        assert audit is not None
        assert audit.entity_type == "feedback"
        assert audit.details.get("status") == "resolved"
    finally:
        db.close()


def test_non_admin_is_forbidden(client, as_non_admin):
    assert client.get("/api/admin/feedback").status_code == 403
    assert client.patch("/api/admin/feedback/1", json={"status": "triaged"}).status_code == 403
