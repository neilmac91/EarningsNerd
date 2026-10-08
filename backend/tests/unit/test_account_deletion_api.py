"""DELETE /api/users/me: account deletion (GDPR Art. 17), characterized over HTTP.

Pins what the handler does and in which order: the ``user_deleted`` audit row commits before the
account row is deleted; the session cookies are cleared with the logout helpers (access +
session-presence, then refresh) only after the delete commits; and a failed delete rolls the
session back, keeps the account and sets no cookie. The failure is injected inside the request's
own session (a ``before_flush`` listener), not by patching a function, so the test holds wherever
the delete code lives.
"""
import re
import uuid
from contextlib import contextmanager

import pytest
from fastapi import Depends, Response
from fastapi.testclient import TestClient
from sqlalchemy import event

from main import app
from app.database import SessionLocal, get_db
from app.models import AuditLog, User
from app.routers.auth import _clear_auth_cookie, _clear_refresh_cookie, get_current_user

DELETED_MESSAGE = "Your account and all associated data have been permanently deleted."
FAILED_DETAIL = "Failed to delete account. Please contact support."


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _seeded_user():
    """A real user row, authenticated through the request's own ``get_db`` session so the
    handler's ``db.delete(current_user)`` acts on an in-session instance."""
    email = f"del-{uuid.uuid4().hex}@example.com"
    db = SessionLocal()
    user = User(email=email, hashed_password=None, email_verified=True, is_active=True)
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


def _cleared_session_cookies() -> list[str]:
    """The Set-Cookie headers the logout helpers emit, in call order."""
    expected = Response()
    _clear_auth_cookie(expected)
    _clear_refresh_cookie(expected)
    return expected.headers.getlist("set-cookie")


_EXPIRES = re.compile(r"expires=[^;]+;")


def _clock_free(headers: list[str]) -> list[str]:
    """``delete_cookie`` stamps ``expires`` with the current second, so two calls a moment apart
    can differ there; every other byte of every header still has to match."""
    assert all(len(_EXPIRES.findall(header)) == 1 for header in headers), headers
    return [_EXPIRES.sub("expires=<now>;", header) for header in headers]


def _audit_rows(email: str) -> list[tuple[str, str, str]]:
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.user_email == email).order_by(AuditLog.id).all()
        return [(row.action, row.entity_id, row.status) for row in rows]
    finally:
        db.close()


def _user_exists(uid: int) -> bool:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == uid).first() is not None
    finally:
        db.close()


@pytest.mark.requires_db
def test_delete_account_audits_deletes_and_clears_session_cookies(client):
    with _seeded_user() as (uid, email):
        resp = client.delete("/api/users/me")

        assert resp.status_code == 200
        body = resp.json()
        assert list(body) == ["status", "message", "deleted_at", "third_party_deletions"]
        assert body["status"] == "success"
        assert body["message"] == DELETED_MESSAGE
        assert set(body["third_party_deletions"]) == {"stripe", "posthog", "sentry"}
        cleared = _cleared_session_cookies()
        assert len(cleared) >= 2
        # Byte-identical (bar the clock) and in order: access + presence, then refresh.
        assert _clock_free(resp.headers.get_list("set-cookie")) == _clock_free(cleared)
        assert not _user_exists(uid)
        assert _audit_rows(email) == [("user_deleted", str(uid), "success")]


@pytest.mark.requires_db
def test_failed_delete_rolls_back_keeps_account_and_sets_no_cookie(client):
    with _seeded_user() as (uid, email):
        session_events: list[str] = []

        def _refuse_user_delete(session, flush_context, instances):
            if any(isinstance(obj, User) for obj in session.deleted):
                raise RuntimeError("injected account-delete failure")

        def _failing_db():
            db = SessionLocal()
            event.listen(db, "before_flush", _refuse_user_delete)
            event.listen(db, "after_rollback", lambda session: session_events.append("rollback"))
            try:
                yield db
            finally:
                session_events.append("close")
                db.close()

        app.dependency_overrides[get_db] = _failing_db
        resp = client.delete("/api/users/me")

        assert resp.status_code == 500
        assert resp.json() == {"detail": FAILED_DETAIL}
        assert resp.headers.get_list("set-cookie") == []
        # The handler rolls back before the request's session is closed.
        assert "rollback" in session_events
        assert session_events.index("rollback") < session_events.index("close")
        assert _user_exists(uid)
        # Pre-existing behaviour, pinned as-is: the audit row committed before the delete failed.
        assert _audit_rows(email) == [("user_deleted", str(uid), "success")]
