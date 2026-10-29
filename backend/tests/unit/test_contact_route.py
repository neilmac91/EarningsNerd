"""Route tests for POST /api/contact/ (E13c).

Per-test in-memory SQLite (the response is built from the refreshed ORM row), ``get_db`` overridden,
``send_email`` monkeypatched to a recorder. Client IPs are simulated through ``X-Forwarded-For``
with ``TRUSTED_PROXY_HOPS=1`` (the right-most hop is the trusted one).
"""
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.database import Base, get_db
from app.models import ContactSubmission, Subscription, User
from app.routers import contact as contact_router
from app.services import rate_limiter
from app.services import turnstile
from app.services.contact_submission_service import ContactPersistenceError
from app.services.resend_service import ResendError

# Exercise existing collection behavior with an explicitly published synthetic operator notice.
pytestmark = pytest.mark.usefixtures("collection_ready")

IP_A = "203.0.113.7"
IP_B = "198.51.100.9"
ADMIN_EMAIL = "admin@example.com"
PAYLOAD = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "subject": "Question",
    "message": "Does the summary include segment data?",
}


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


class _EmailRecorder(list):
    """Recorded ``(to, subject)`` pairs (``bodies`` keeps each ``html`` in send order); set
    ``raise_with`` to make every send fail."""

    raise_with: Exception | None = None

    def __init__(self) -> None:
        super().__init__()
        self.bodies: list[str] = []
        self.reply_addresses: list[str | None] = []


@pytest.fixture
def sent_emails(monkeypatch):
    recorder = _EmailRecorder()

    async def _fake_send_email(to, subject, html, *args, **kwargs):
        recorder.append((list(to), subject))
        recorder.bodies.append(html)
        recorder.reply_addresses.append(kwargs.get("reply_to"))
        if recorder.raise_with is not None:
            raise recorder.raise_with
        return {"id": "msg_test"}

    monkeypatch.setattr(contact_router, "send_email", _fake_send_email)
    return recorder


@pytest.fixture
def client(session_factory, monkeypatch, sent_emails):
    contact_router.CONTACT_LIMITER._hits.clear()
    monkeypatch.setattr(rate_limiter.settings, "TRUSTED_PROXY_HOPS", 1)
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")
    monkeypatch.setattr(contact_router.settings, "RESEND_FROM_EMAIL", "Sender <sender@example.com>")
    monkeypatch.setattr(contact_router.settings, "CONTACT_NOTIFICATION_EMAIL", ADMIN_EMAIL)
    monkeypatch.setattr(contact_router.settings, "RESEND_REPLY_TO_EMAIL", "help@example.com")

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    contact_router.CONTACT_LIMITER._hits.clear()


def _post(client, ip: str, **overrides):
    return client.post("/api/contact/", json={**PAYLOAD, **overrides}, headers={"X-Forwarded-For": ip})


def test_submission_persists_hashed_ip_and_sends_admin_and_user_emails(client, session_factory, sent_emails):
    resp = _post(client, IP_A)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "new" and body["email"] == PAYLOAD["email"]
    assert "ip_address" not in body  # the hash is never echoed to the client

    with session_factory() as s:
        rows = s.query(ContactSubmission).all()
        assert len(rows) == 1
        assert rows[0].ip_address == contact_router.hash_ip_address(IP_A)
        assert IP_A not in rows[0].ip_address

    recipients = [to for to, _subject in sent_emails]
    assert recipients == [[ADMIN_EMAIL], [PAYLOAD["email"]]]
    assert sent_emails.reply_addresses == [PAYLOAD["email"], "help@example.com"]


def test_user_confirmation_never_echoes_the_message_while_the_admin_copy_carries_it(client, sent_emails):
    message = "Does the summary include segment data? Asking for the Q3 10-Q."
    resp = _post(client, IP_A, message=message)
    assert resp.status_code == 201, resp.text

    recipients = [to for to, _subject in sent_emails]
    assert recipients == [[ADMIN_EMAIL], [PAYLOAD["email"]]]
    admin_html, user_html = sent_emails.bodies
    assert message in admin_html
    assert message not in user_html
    assert "Your message" not in user_html
    assert PAYLOAD["name"] in user_html  # the greeting is still personal


@pytest.mark.parametrize("is_pro,status,plan_line", [
    (True, None, "Pro (an account uses this address; the form does not verify it)"),
    (False, None, "Free (an account uses this address; the form does not verify it)"),
    # The subscription row decides before the is_pro mirror (entitlements.get_plan, rule 4).
    (True, "canceled", "Free (an account uses this address; the form does not verify it)"),
])
def test_team_notice_names_the_plan_of_the_account_that_uses_the_address(
    client, session_factory, sent_emails, is_pro, status, plan_line,
):
    """D-050's priority support, kept by hand: the notice to the team names the plan of the account that uses the
    address the form was given, in whatever case either was written, so a Pro member's message can be answered
    first. The confirmation to the person who wrote in names no plan."""
    with session_factory() as s:
        user = User(email="Ada@Example.com", hashed_password="x", is_pro=is_pro)
        s.add(user)
        if status is not None:
            s.add(Subscription(user=user, plan="pro", status=status))
        s.commit()
    resp = _post(client, IP_A, email="aDA@example.COM")
    assert resp.status_code == 201, resp.text

    admin_html, user_html = sent_emails.bodies
    assert f'<div class="value">{plan_line}</div>' in admin_html
    assert "Plan:" not in user_html and "account uses this address" not in user_html
    # The subject carries the plan too, so an inbox lists a member's message first; the caveat stays in the body.
    (_admin, admin_subject), (_user, user_subject) = sent_emails
    assert admin_subject == f"New Contact Form Submission from {PAYLOAD['name']} ({plan_line.split(' ')[0]})"
    assert "Pro" not in user_subject and "Free" not in user_subject


def test_team_notice_says_when_no_account_uses_the_address(client, sent_emails):
    resp = _post(client, IP_A)
    assert resp.status_code == 201, resp.text
    admin_html, _user_html = sent_emails.bodies
    assert '<div class="value">No account uses this address</div>' in admin_html
    assert sent_emails[0][1] == f"New Contact Form Submission from {PAYLOAD['name']}"  # no plan, no tag


def test_a_failed_plan_read_still_saves_the_submission_and_sends_both_mails(
    client, session_factory, sent_emails, monkeypatch,
):
    def _unreadable(db, email):
        raise RuntimeError("the users table is unreachable")

    monkeypatch.setattr(contact_router, "sender_plan", _unreadable)
    resp = _post(client, IP_A)
    assert resp.status_code == 201, resp.text
    with session_factory() as s:
        assert s.query(ContactSubmission).count() == 1
    assert [to for to, _subject in sent_emails] == [[ADMIN_EMAIL], [PAYLOAD["email"]]]
    assert '<div class="value">Not read (the lookup failed)</div>' in sent_emails.bodies[0]
    assert sent_emails[0][1] == f"New Contact Form Submission from {PAYLOAD['name']}"


def test_limit_plus_one_from_one_ip_is_429_with_retry_after_and_other_ip_still_succeeds(client, session_factory):
    limit = contact_router.CONTACT_LIMITER.limit
    assert limit == 3
    for _ in range(limit):
        assert _post(client, IP_A).status_code == 201

    blocked = _post(client, IP_A)
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == contact_router.CONTACT_RATE_LIMIT_DETAIL
    assert 0 < int(blocked.headers["Retry-After"]) <= contact_router.CONTACT_LIMITER.window_seconds

    assert _post(client, IP_B).status_code == 201

    with session_factory() as s:
        assert s.query(ContactSubmission).count() == limit + 1  # the blocked post saved nothing


def test_email_failure_still_returns_201_with_the_row_saved(client, session_factory, sent_emails):
    sent_emails.raise_with = ResendError("resend is down")
    resp = _post(client, IP_A)
    assert resp.status_code == 201, resp.text
    with session_factory() as s:
        assert s.query(ContactSubmission).count() == 1
    assert len(sent_emails) == 2  # both sends were attempted; neither failure surfaced


def test_persistence_failure_is_500_and_notifies_no_one(client, session_factory, monkeypatch, sent_emails):
    """The service's persistence failure maps to the 500, and no email goes out for a row that was never
    saved."""
    def _fail(db, **fields):
        raise ContactPersistenceError from RuntimeError("database is down")

    monkeypatch.setattr(contact_router, "persist_contact_submission", _fail)
    resp = _post(client, IP_A)
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Failed to save contact form submission"
    assert sent_emails == []
    with session_factory() as s:
        assert s.query(ContactSubmission).count() == 0


def test_turnstile_configured_without_token_is_403_and_saves_nothing(client, session_factory, monkeypatch, sent_emails):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "turnstile-secret")
    resp = _post(client, IP_A)
    assert resp.status_code == 403
    with session_factory() as s:
        assert s.query(ContactSubmission).count() == 0
    assert sent_emails == []


def test_limiter_runs_before_turnstile(client, monkeypatch):
    """Exhausted clients get 429 (cheap, local) before the Turnstile check would 403 them."""
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "turnstile-secret")
    for _ in range(contact_router.CONTACT_LIMITER.limit):
        assert _post(client, IP_A).status_code == 403
    assert _post(client, IP_A).status_code == 429
