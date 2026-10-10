"""GET /api/users/export: the GDPR Art. 20 download, characterized over HTTP.

Pins the wire shape (top-level and profile key order, the attachment filename) and that the
``data_exported`` audit row is written only after the payload is built: a build that fails part-way
returns the 500 and leaves no audit row. The failure is injected inside the request's own session
(a ``do_orm_execute`` listener on the last query of the build), not by patching a function, so the
test holds wherever the export code lives.
"""
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import event

from main import app
from app.database import SessionLocal, get_db
from app.models import AuditLog, BillingPayment, User
from app.routers.auth import get_current_user

EXPORT_KEYS = [
    "profile", "searches", "saved_summaries", "watchlist", "usage", "billing_payments",
    "export_timestamp",
]
PROFILE_KEYS = [
    "user_id", "email", "full_name", "is_active", "is_pro", "stripe_customer_id",
    "stripe_subscription_id", "created_at", "updated_at",
]
FAILED_DETAIL = "Failed to export user data"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _seeded_user():
    """A real user row, authenticated through the request's own ``get_db`` session."""
    email = f"export-{uuid.uuid4().hex}@example.com"
    db = SessionLocal()
    user = User(email=email, hashed_password=None, full_name="Export Owner",
                email_verified=True, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    uid = user.id
    db.close()

    def _fetch_current_user(db=Depends(get_db)):
        return db.query(User).filter(User.id == uid).first()

    app.dependency_overrides[get_current_user] = _fetch_current_user
    try:
        yield uid, email
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        db = SessionLocal()
        db.query(AuditLog).filter(AuditLog.user_email == email).delete()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


def _audit_rows(email: str) -> list[tuple[str, str, str]]:
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.user_email == email).order_by(AuditLog.id).all()
        return [(row.action, row.entity_id, row.status) for row in rows]
    finally:
        db.close()


@pytest.mark.requires_db
def test_export_key_order_filename_and_audit_row(client):
    with _seeded_user() as (uid, email):
        resp = client.get("/api/users/export")

        assert resp.status_code == 200
        assert re.fullmatch(
            rf'attachment; filename="earningsnerd_data_export_{uid}_\d{{8}}_\d{{6}}\.json"',
            resp.headers["content-disposition"],
        )
        payload = resp.json()
        assert list(payload) == EXPORT_KEYS
        assert list(payload["profile"]) == PROFILE_KEYS
        assert payload["profile"]["user_id"] == uid
        assert payload["profile"]["email"] == email
        assert payload["profile"]["full_name"] == "Export Owner"
        for key in ("searches", "saved_summaries", "watchlist", "usage", "billing_payments"):
            assert payload[key] == []
        assert datetime.fromisoformat(payload["export_timestamp"]).utcoffset() == timedelta(0)
        assert _audit_rows(email) == [("data_exported", str(uid), "success")]


@pytest.mark.requires_db
def test_failed_export_build_returns_500_and_writes_no_audit_row(client):
    with _seeded_user() as (uid, email):
        refused: list[str] = []

        def _refuse_payments_query(orm_execute_state):
            mapper = orm_execute_state.bind_mapper
            if orm_execute_state.is_select and mapper is not None and mapper.class_ is BillingPayment:
                refused.append("billing_payments")
                raise RuntimeError("injected export-build failure")

        def _failing_db():
            db = SessionLocal()
            event.listen(db, "do_orm_execute", _refuse_payments_query)
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _failing_db
        resp = client.get("/api/users/export")

        assert refused == ["billing_payments"]
        assert resp.status_code == 500
        assert resp.json() == {"detail": FAILED_DETAIL}
        assert "content-disposition" not in resp.headers
        assert _audit_rows(email) == []
