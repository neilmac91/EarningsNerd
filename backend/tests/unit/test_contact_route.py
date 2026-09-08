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
from app.models import ContactSubmission
from app.routers import contact as contact_router
from app.services import rate_limiter
from app.services import turnstile
from app.services.resend_service import ResendError

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
    """Recorded ``(to, subject)`` pairs; set ``raise_with`` to make every send fail."""

    raise_with: Exception | None = None


@pytest.fixture
def sent_emails(monkeypatch):
    recorder = _EmailRecorder()

    async def _fake_send_email(to, subject, html, *args, **kwargs):
        recorder.append((list(to), subject))
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
    monkeypatch.setattr(contact_router.settings, "RESEND_FROM_EMAIL", f"Ops <{ADMIN_EMAIL}>")

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
