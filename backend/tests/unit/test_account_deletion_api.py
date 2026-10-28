"""DELETE /api/users/me: account deletion (GDPR Art. 17), characterized over HTTP.

Pins what is observable over HTTP: the ``user_deleted`` audit row commits with the account's
deletion, in one transaction, and records the provider outcomes the response reports; a failed audit
insert, deletion or commit leaves neither behind, so the account stays and no failed deletion is
audited as a success (F19); on success the Set-Cookie headers equal the
logout helpers' output in call order (access + session-presence, then refresh); and a failed delete
rolls the session back before it closes, keeps the account and sends no Set-Cookie at all. Whether
the cookies are cleared before or after the delete is not observable here: when the handler raises
HTTPException, FastAPI builds the 500 without the headers set on the injected ``response``. The
failure is injected inside the request's own session (flush listeners), not by
patching a function, so the test holds wherever the delete code lives. A delete that finds the
account already gone, as the second of two deletions at once does, answers that 500 too, names the
account in its log line and stages no audit row; there the first deletion is played inside the
Stripe step. A failure after Stripe cancelled keeps the account: the cancellation is not undone, and
the failure's log line carries the outcomes the audit row would have held.

The Stripe step is pinned on the wire for the same reason. A fake ``requests`` session inside the
real ``stripe.RequestsClient`` plays Stripe's subscription list and cancel endpoints, so the list
query, the page walk and the cancel calls asserted here are the ones the SDK actually sends. The fake
account also holds another customer's live subscription, which a list without the customer filter
reaches, as it would on Stripe.
"""
import json
import logging
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
from app.routers import users
from app.routers.auth import _clear_auth_cookie, _clear_refresh_cookie, get_current_user

DELETED_MESSAGE = "Your account has been deleted. Some billing, audit and provider records may remain; see the privacy policy for details."
FAILED_DETAIL = "We could not delete your account. Contact support."
STRIPE_CUSTOMER = "cus_deleted_account"
# Every subscription status Stripe documents. The two ended ones can never bill again.
LIVE_STATUSES = ["active", "trialing", "past_due", "unpaid", "incomplete", "paused"]
ENDED_STATUSES = ["canceled", "incomplete_expired"]
# The SDK types the status as an open string: one Stripe adds later is live until it is known ended.
FUTURE_STATUS = "a_status_stripe_adds_later"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _seeded_user(stripe_customer_id=None):
    """A real user row, authenticated through the request's own ``get_db`` session, as the auth lookup
    loads it, so the route's release before its third-party calls returns that lookup's connection."""
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


def _last_audit_id() -> int:
    db = SessionLocal()
    try:
        return db.query(AuditLog.id).order_by(AuditLog.id.desc()).limit(1).scalar() or 0
    finally:
        db.close()


def _deletion_audits_since(mark: int) -> list[tuple]:
    """Every ``user_deleted`` row written after ``mark``, whatever email it holds (a row staged for an account
    already gone could hold none, which an email filter would not see)."""
    db = SessionLocal()
    try:
        rows = db.query(AuditLog).filter(AuditLog.id > mark, AuditLog.action == "user_deleted").order_by(AuditLog.id)
        return [(row.user_email, row.entity_id, row.status) for row in rows]
    finally:
        db.close()


def _audit_details(email: str) -> list[dict]:
    db = SessionLocal()
    try:
        return [row.details for row in db.query(AuditLog).filter(AuditLog.user_email == email).order_by(AuditLog.id)]
    finally:
        db.close()


def _failing_db(failed_write: str, session_events: list[str]):
    """A ``get_db`` whose session refuses one write of the deletion's transaction: the audit row's insert, the
    account's delete, or the commit once both are flushed. It records the session's rollback and close."""
    def refuse_before_flush(session, flush_context, instances):
        if failed_write == "audit" and any(isinstance(obj, AuditLog) for obj in session.new):
            raise RuntimeError("injected audit-insert failure")
        if failed_write == "account" and any(isinstance(obj, User) for obj in session.deleted):
            raise RuntimeError("injected account-delete failure")

    def refuse_after_flush(session, flush_context):
        # The flush has written the audit row and the account's delete; the commit never comes.
        if failed_write == "commit" and any(isinstance(obj, User) for obj in session.deleted):
            raise RuntimeError("injected commit failure")

    def get_failing_db():
        db = SessionLocal()
        event.listen(db, "before_flush", refuse_before_flush)
        event.listen(db, "after_flush", refuse_after_flush)
        event.listen(db, "after_rollback", lambda session: session_events.append("rollback"))
        try:
            yield db
        finally:
            session_events.append("close")
            db.close()

    return get_failing_db


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

    def __init__(self, statuses, refuse_later_pages=False, honour_customer_filter=True):
        self.subscriptions = [
            {"id": f"sub_{position}_{status}", "object": "subscription", "customer": STRIPE_CUSTOMER, "status": status}
            for position, status in enumerate(statuses)
        ] + [{"id": "sub_another_customer", "object": "subscription", "customer": "cus_another", "status": "active"}]
        self.refuse_later_pages = refuse_later_pages
        self.honour_customer_filter = honour_customer_filter
        self.list_queries: list[dict[str, str]] = []
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
        self.list_queries.append(query)
        limit = int(query.get("limit", 10))
        if not 1 <= limit <= 100:
            return self._refuse(400, "Invalid integer: limit")
        if self.refuse_later_pages and "starting_after" in query:
            return self._refuse(400, "injected failure on a later page")
        rows = self.subscriptions
        if "starting_after" in query:
            rows = rows[[row["id"] for row in rows].index(query["starting_after"]) + 1:]
        if "customer" in query and self.honour_customer_filter:
            rows = [row for row in rows if row["customer"] == query["customer"]]
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


def _delete_account_of_customer(client, monkeypatch, statuses, stripe_result="subscriptions_cancelled",
                                **fake_options) -> _FakeStripe:
    """Delete an account whose Stripe customer holds one subscription per given status."""
    stripe_api = _FakeStripe(statuses, **fake_options)
    monkeypatch.setattr(stripe, "default_http_client", stripe.RequestsClient(session=stripe_api))
    with _seeded_user(stripe_customer_id=STRIPE_CUSTOMER) as (uid, email):
        resp = client.delete("/api/users/me")
        assert resp.status_code == 200
        # The handler swallows a Stripe failure and reports it here (``error: …``).
        assert re.fullmatch(stripe_result, resp.json()["third_party_deletions"]["stripe"])
        assert not _user_exists(uid)
        # The audit row records the outcomes the response reports, Stripe's included.
        assert [details["third_party_deletions"] for details in _audit_details(email)] == [
            resp.json()["third_party_deletions"]]
    # Every list query is this customer's, over every status, in pages of 100.
    assert stripe_api.list_queries
    assert all({key: query[key] for key in ("customer", "status", "limit") if key in query}
               == {"customer": STRIPE_CUSTOMER, "status": "all", "limit": "100"} for query in stripe_api.list_queries)
    return stripe_api


@pytest.mark.requires_db
def test_delete_account_audits_deletes_and_clears_session_cookies(client):
    with _seeded_user() as (uid, email):
        mark = _last_audit_id()
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
        assert _deletion_audits_since(mark) == [(email, str(uid), "success")]
        [details] = _audit_details(email)
        assert details["third_party_deletions"] == body["third_party_deletions"]
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z", details["timestamp"]), details


@pytest.mark.requires_db
@pytest.mark.parametrize("failed_write", ["audit", "account", "commit"])
def test_failed_delete_rolls_back_keeps_account_and_sets_no_cookie(client, failed_write):
    # "audit" is the mandatory audit: before F19 its insert failure was swallowed and the account deleted anyway.
    with _seeded_user() as (uid, email):
        session_events: list[str] = []
        app.dependency_overrides[get_db] = _failing_db(failed_write, session_events)
        mark = _last_audit_id()
        resp = client.delete("/api/users/me")

        assert resp.status_code == 500
        assert resp.json() == {"detail": FAILED_DETAIL}
        assert resp.headers.get_list("set-cookie") == []
        # The handler rolls back before the request's session is closed. For "commit" SQLAlchemy rolls the failed
        # flush back itself, so only "audit" and "account" prove the route's own rollback.
        assert "rollback" in session_events
        assert session_events.index("rollback") < session_events.index("close")
        assert _user_exists(uid)
        assert _audit_rows(email) == []  # before F19 the success row had committed ahead of the delete
        assert _deletion_audits_since(mark) == []


@pytest.mark.requires_db
@pytest.mark.parametrize("status", LIVE_STATUSES + [FUTURE_STATUS])
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


@pytest.mark.requires_db
def test_a_stripe_failure_is_reported_and_the_deletion_still_proceeds(client, monkeypatch):
    # Pre-existing behaviour, pinned as-is (the founder's decision to make): the account is deleted, the
    # failure is reported, and the walk stops where it failed, here on the second page.
    statuses = ["trialing"] + ["canceled"] * 100 + ["past_due"]
    stripe_api = _delete_account_of_customer(client, monkeypatch, statuses, r"error: .+", refuse_later_pages=True)

    assert stripe_api.cancelled == ["sub_0_trialing"]


@pytest.mark.requires_db
def test_a_listed_subscription_of_another_customer_is_never_cancelled(client, monkeypatch):
    # The list is external data: if a response ever ignored the customer filter, another customer's live
    # subscription would be listed beside this one, and deleting this account must not cancel it.
    stripe_api = _delete_account_of_customer(client, monkeypatch, ["trialing"], honour_customer_filter=False)

    assert stripe_api.cancelled == ["sub_0_trialing"]


FAILURE_CAUSES = {
    "audit": "injected audit-insert failure",
    "account": "injected account-delete failure",
    "commit": "injected commit failure",
}


@pytest.mark.requires_db
@pytest.mark.parametrize("failed_write", list(FAILURE_CAUSES))
def test_a_deletion_that_fails_after_stripe_cancelled_keeps_the_account_and_logs_the_outcomes(
    client, monkeypatch, caplog, failed_write,
):
    # Stripe's cancellation is not part of the database transaction and is not undone. The account stays, no
    # audit row commits, and the failure's log line carries the outcomes the audit row would have recorded
    # (F19; F18's operator evidence).
    stripe_api = _FakeStripe(["trialing"])
    monkeypatch.setattr(stripe, "default_http_client", stripe.RequestsClient(session=stripe_api))
    with _seeded_user(stripe_customer_id=STRIPE_CUSTOMER) as (uid, email):
        app.dependency_overrides[get_db] = _failing_db(failed_write, [])
        mark = _last_audit_id()
        with caplog.at_level(logging.ERROR, logger="app.routers.users"):
            resp = client.delete("/api/users/me")

        assert resp.status_code == 500
        assert resp.json() == {"detail": FAILED_DETAIL}
        assert resp.headers.get_list("set-cookie") == []
        assert stripe_api.cancelled == ["sub_0_trialing"]
        assert _user_exists(uid)
        assert _audit_rows(email) == [] and _deletion_audits_since(mark) == []
        assert (f"Error deleting user account {uid}: {FAILURE_CAUSES[failed_write]}. Third-party deletion "
                f"results: {{'stripe': 'subscriptions_cancelled', ") in caplog.text


@pytest.mark.requires_db
def test_a_retry_after_a_deletion_failed_past_stripe_deletes_the_account_and_cancels_nothing_twice(client, monkeypatch):
    # The retry after a partial cleanup (F18's runbook): the first request cancelled the subscription and then failed
    # in the database, keeping the account and committing no audit row. The retry walks the same subscriptions, finds
    # the cancelled one ended and cancels nothing again, then deletes the account with one audit row of its own. Its
    # Stripe outcome reads "subscriptions_cancelled" because its walk finished, not because it cancelled anything.
    stripe_api = _FakeStripe(["trialing"])
    monkeypatch.setattr(stripe, "default_http_client", stripe.RequestsClient(session=stripe_api))
    with _seeded_user(stripe_customer_id=STRIPE_CUSTOMER) as (uid, email):
        mark = _last_audit_id()
        app.dependency_overrides[get_db] = _failing_db("account", [])
        first = client.delete("/api/users/me")
        assert first.status_code == 500 and _user_exists(uid)
        assert _deletion_audits_since(mark) == []
        app.dependency_overrides.pop(get_db)

        retry = client.delete("/api/users/me")

        assert retry.status_code == 200, retry.text
        assert retry.json()["third_party_deletions"]["stripe"] == "subscriptions_cancelled"
        assert stripe_api.cancelled == ["sub_0_trialing"]  # once, by the first request
        assert not _user_exists(uid)
        assert _deletion_audits_since(mark) == [(email, str(uid), "success")]


@pytest.mark.requires_db
def test_a_delete_that_finds_the_account_gone_answers_the_routes_500(client, monkeypatch, caplog):
    # A second deletion of the account at once: the first deletes the row while this one makes its Stripe call,
    # so under the account's lock this one finds no row. It answers 500, as at the base (the deletion-failure
    # policy is F18's), but now the route's own 500 and log line, where the base's error log read the deleted
    # row and raised, so main.py's global handler answered. Its audit row is staged only once the lock finds the
    # account, so this deletion commits none (before F19 its success row committed ahead of the delete).
    def first_deletion_commits(stripe_customer_id, _user_id):
        with SessionLocal() as other:
            other.query(User).filter(User.stripe_customer_id == stripe_customer_id).delete()
            other.commit()

    monkeypatch.setattr(users, "_cancel_billable_subscriptions", first_deletion_commits)
    with _seeded_user(stripe_customer_id=STRIPE_CUSTOMER) as (uid, email):
        mark = _last_audit_id()
        with caplog.at_level(logging.ERROR, logger="app.routers.users"):
            resp = client.delete("/api/users/me")

        assert resp.status_code == 500
        assert resp.json() == {"detail": FAILED_DETAIL}
        assert resp.headers.get_list("set-cookie") == []
        assert not _user_exists(uid)
        assert _audit_rows(email) == [] and _deletion_audits_since(mark) == []
        assert f"Error deleting user account {uid}: Account {uid} was deleted after its lookup" in caplog.text
