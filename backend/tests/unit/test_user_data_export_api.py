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
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.database import SessionLocal, get_db
from app.models import (
    AuditLog, BillingPayment, Company, Filing, SavedSummary, Summary, User, UserSearch, UserUsage, Watchlist,
)
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
        account = db.get(User, uid)
        if account is not None:
            db.delete(account)
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
        assert payload["export_timestamp"].endswith("Z")
        assert _audit_rows(email) == [("data_exported", str(uid), "success")]


@pytest.mark.requires_db
@pytest.mark.parametrize("database_offset", [None, 2])
def test_export_timestamps_preserve_instants_as_utc_z_and_keep_nulls(client, database_offset):
    stamp = datetime(2026, 7, 6, 10, 52, 35, 123456, tzinfo=timezone.utc)
    with _seeded_user() as (uid, _email):
        with SessionLocal() as db:
            company = Company(cik=uuid.uuid4().hex, ticker="EXPORT", name="Export fixture")
            db.add(company)
            db.flush()
            company_id = company.id
            filing = Filing(company_id=company_id, accession_number=uuid.uuid4().hex, filing_type="10-K",
                            filing_date=stamp, document_url="https://example.test/filing", sec_url="https://example.test/filing")
            db.add(filing)
            db.flush()
            summary = Summary(filing_id=filing.id)
            db.add(summary)
            db.flush()
            db.query(User).filter(User.id == uid).update({"created_at": stamp, "updated_at": None})
            db.add_all([
                UserSearch(user_id=uid, query="Export fixture", company_id=company_id, created_at=stamp),
                SavedSummary(user_id=uid, summary_id=summary.id, created_at=stamp),
                Watchlist(user_id=uid, company_id=company_id, created_at=stamp),
                UserUsage(user_id=uid, month="2026-07", summary_count=1, created_at=stamp, updated_at=None),
            ])
            db.commit()

        def _database_representation(session, instance):
            if database_offset is not None and isinstance(instance, (User, UserSearch, SavedSummary, Watchlist, UserUsage)):
                zone = timezone(timedelta(hours=database_offset))
                for name in ("created_at", "updated_at"):
                    value = getattr(instance, name, None)
                    if value is not None:
                        set_committed_value(instance, name, value.replace(tzinfo=timezone.utc).astimezone(zone))

        def _export_db():
            with SessionLocal() as db:
                # Simulate the representation an aware PostgreSQL column can return, without
                # changing stored instants. The other case uses SQLite's actual naive reads.
                event.listen(db, "loaded_as_persistent", _database_representation)
                yield db

        app.dependency_overrides[get_db] = _export_db
        try:
            resp = client.get("/api/users/export")
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["profile"]["created_at"] == "2026-07-06T10:52:35.123456Z"
            assert payload["profile"]["updated_at"] is None
            for section in ("searches", "saved_summaries", "watchlist", "usage"):
                assert len(payload[section]) == 1
                assert payload[section][0]["created_at"] == "2026-07-06T10:52:35.123456Z"
            assert payload["usage"][0]["updated_at"] is None
        finally:
            with SessionLocal() as db:
                db.delete(db.get(User, uid))
                db.delete(db.get(Company, company_id))
                db.commit()


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
