"""DELETE /api/users/me: account deletion (GDPR Art. 17), characterized over HTTP.

Pins what is observable over HTTP: the ``user_deleted`` audit row commits before the account row
is deleted (a failed delete still leaves it behind); on success the Set-Cookie headers equal the
logout helpers' output in call order (access + session-presence, then refresh); and a failed delete
rolls the session back before it closes, keeps the account and sends no Set-Cookie at all. Whether
the cookies are cleared before or after the delete is not observable here: when the handler raises
HTTPException, FastAPI builds the 500 without the headers set on the injected ``response``. The
failure is injected inside the request's own session (a ``before_flush`` listener), not by
patching a function, so the test holds wherever the delete code lives.

The Stripe step is pinned on the wire for the same reason. A fake ``requests`` session inside the
real ``stripe.RequestsClient`` plays Stripe's subscription list and cancel endpoints, so the status
filter, the page walk and the cancel calls asserted here are the ones the SDK actually sends.
"""
import json
import re
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

import pytest
import stripe
from fastapi import Depends, Response
from fastapi.testclient import TestClient
from sqlalchemy import event

from main import app
from app.database import SessionLocal, get_db
from app.models import AuditLog, User
from app.routers.auth import _clear_auth_cookie, _clear_refresh_cookie, get_current_user

DELETED_MESSAGE = "Your account and all associated data have been permanently deleted."
FAILED_DETAIL = "Failed to delete account. Please contact support."
STRIPE_CUSTOMER = "cus_deleted_account"
# Every subscription status Stripe documents. The two ended ones can never bill again.
LIVE_STATUSES = ["active", "trialing", "past_due", "unpaid", "incomplete", "paused"]
ENDED_STATUSES = ["canceled", "incomplete_expired"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _seeded_user(stripe_customer_id=None):
    """A real user row, authenticated through the request's own ``get_db`` session so the
    handler's ``db.delete(current_user)`` acts on an in-session instance."""
    email = f"del-{uuid.uuid4().hex}@example.com"
    db = SessionLocal()
    user = User(email=email, hashed_password=None, email_verified=True, is_active=True,
                stripe_customer_id=stripe_customer_id)
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


class _FakeStripe:
    """Stripe's subscription list and cancel endpoints for one customer, as the ``requests``
    session the SDK talks through. Rows are newest first, as Stripe lists them; pages are
    cursor-based and hold at most 100 rows; a ``status`` filter behaves as Stripe documents it."""

    def __init__(self, statuses):
        self.subscriptions = [
            {"id": f"sub_{position}_{status}", "object": "subscription", "customer": STRIPE_CUSTOMER, "status": status}
            for position, status in enumerate(statuses)
        ]
        self.cancelled: list[str] = []
        self.other_requests: list[tuple[str, str]] = []

    def request(self, method, url, **_transport_options):
        target = urlsplit(url)
        if (method, target.path) == ("get", "/v1/subscriptions"):
            return self._list(dict(parse_qsl(target.query)))
        if method == "delete" and target.path.startswith("/v1/subscriptions/"):
            return self._cancel(target.path.rsplit("/", 1)[1])
        self.other_requests.append((method, target.path))
        return self._refuse(404, f"{method} {target.path} is not faked")

    def _list(self, query):
        limit = int(query.get("limit", 10))
        if not 1 <= limit <= 100:
            return self._refuse(400, "Invalid integer: limit")
        rows = self.subscriptions
        if "starting_after" in query:
            rows = rows[[row["id"] for row in rows].index(query["starting_after"]) + 1:]
        rows = [row for row in rows if row["customer"] == query.get("customer")]
        status = query.get("status")
        if status is None:
            rows = [row for row in rows if row["status"] != "canceled"]
        elif status != "all":
            rows = [row for row in rows if row["status"] == status]
        return self._respond(200, {
            "object": "list", "url": "/v1/subscriptions", "has_more": len(rows) > limit, "data": rows[:limit],
        })

    def _cancel(self, subscription_id):
        self.cancelled.append(subscription_id)
        row = next(row for row in self.subscriptions if row["id"] == subscription_id)
        row["status"] = "canceled"
        return self._respond(200, row)

    def _refuse(self, status_code, message):
        return self._respond(status_code, {"error": {"type": "invalid_request_error", "message": message}})

    @staticmethod
    def _respond(status_code, payload):
        return SimpleNamespace(content=json.dumps(payload).encode(), status_code=status_code, headers={})


def _delete_account_of_customer(client, monkeypatch, statuses) -> _FakeStripe:
    """Delete an account whose Stripe customer holds one subscription per given status."""
    stripe_api = _FakeStripe(statuses)
    monkeypatch.setattr(stripe, "default_http_client", stripe.RequestsClient(session=stripe_api))
    with _seeded_user(stripe_customer_id=STRIPE_CUSTOMER) as (uid, _email):
        resp = client.delete("/api/users/me")
        assert resp.status_code == 200
        # The handler swallows a Stripe failure and reports it here; any other value is that failure.
        assert resp.json()["third_party_deletions"]["stripe"] == "subscriptions_cancelled"
        assert not _user_exists(uid)
    return stripe_api


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


@pytest.mark.requires_db
@pytest.mark.parametrize("status", LIVE_STATUSES)
def test_delete_account_cancels_a_subscription_in_any_live_status(client, monkeypatch, status):
    stripe_api = _delete_account_of_customer(client, monkeypatch, [status])

    assert stripe_api.cancelled == [f"sub_0_{status}"]
    # Subscriptions only: the customer record is retained for tax compliance.
    assert stripe_api.other_requests == []


@pytest.mark.requires_db
def test_delete_account_leaves_ended_subscriptions_alone(client, monkeypatch):
    statuses = [ENDED_STATUSES[0], "trialing", ENDED_STATUSES[1]]
    stripe_api = _delete_account_of_customer(client, monkeypatch, statuses)

    assert stripe_api.cancelled == ["sub_1_trialing"]


@pytest.mark.requires_db
def test_delete_account_walks_every_page_of_subscriptions(client, monkeypatch):
    # A full page of ended history sits in front of each live subscription, whatever the page size.
    history = ["canceled"] * 100
    statuses = history + ["trialing"] + history + ["past_due"]
    stripe_api = _delete_account_of_customer(client, monkeypatch, statuses)

    assert stripe_api.cancelled == ["sub_100_trialing", "sub_201_past_due"]
