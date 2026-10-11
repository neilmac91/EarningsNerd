"""Admin provisioning creates only new Free accounts; setup uses the existing inbox proof."""
import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal, engine
from app.models import AuditLog, Subscription, User
from app.services import admin_account_service
from app.routers.auth import create_access_token, get_current_user
from app.services.password_utils import verify_password
from tests.support.summary_stream_harness import reset_rate_limiters

PASSWORD = "FreeAccountSetup-test-2026"  # test fixture, not a credential  # gitleaks:allow


@pytest.fixture(scope="module")
def client():
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_state(client, monkeypatch):
    app.dependency_overrides.clear()
    client.cookies.clear()
    reset_rate_limiters()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", False)
    yield
    app.dependency_overrides.clear()
    client.cookies.clear()


@pytest.fixture
def as_admin():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1, email="admin@example.com", is_admin=True,
    )


@pytest.fixture
def mail(monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr("app.services.email_service.send_password_reset_email", sender)
    return sender


@pytest.fixture
def postgres_expiry():
    """SQLite drops timezone information; token comparisons need PostgreSQL's aware shape."""
    def aware(target, *_args):
        value = target.__dict__.get("password_reset_expires")
        if value is not None and value.tzinfo is None:
            set_committed_value(target, "password_reset_expires", value.replace(tzinfo=timezone.utc))

    event.listen(User, "load", aware)
    event.listen(User, "refresh", aware)
    yield
    event.remove(User, "load", aware)
    event.remove(User, "refresh", aware)


def email():
    return f"free-account-{uuid.uuid4().hex}@example.com"


def token(mail):
    return parse_qs(urlparse(mail.call_args.kwargs["reset_link"]).query)["token"][0]


@pytest.mark.parametrize("authenticated", [False, True])
def test_only_admin_can_create_before_lookup_hash_or_mail(client, monkeypatch, mail, authenticated):
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=False)
    lookup = Mock(side_effect=AssertionError("lookup before authorization"))
    hashing = Mock(side_effect=AssertionError("hash before authorization"))
    creation = Mock(side_effect=AssertionError("write before authorization"))
    monkeypatch.setattr(admin_account_service.auth_account_service, "find_user_by_email", lookup)
    monkeypatch.setattr(admin_account_service.auth_account_service, "create_password_account", creation)
    monkeypatch.setattr(admin_account_service, "get_password_hash", hashing)
    response = client.post("/api/admin/users/free", json={"email": email()})
    assert response.status_code == (403 if authenticated else 401)
    lookup.assert_not_called()
    hashing.assert_not_called()
    creation.assert_not_called()
    mail.assert_not_called()


@pytest.mark.requires_db
def test_created_account_is_free_and_setup_token_stays_private(client, as_admin, mail, caplog):
    address = email()
    with caplog.at_level(logging.INFO):
        response = client.post("/api/admin/users/free", json={"email": f" {address.upper()} ", "full_name": " Free Test "})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body == {
        "id": body["id"], "email": address, "full_name": "Free Test", "is_pro": False,
        "is_beta": False, "is_admin": False, "email_verified": False, "emailed": True,
    }
    raw_token = token(mail)
    assert raw_token not in response.text and raw_token not in caplog.text
    assert mail.call_args.kwargs["to_email"] == address
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == address).one()
        assert user.is_active and not user.is_beta and not user.is_pro and not user.is_admin
        assert not user.email_verified
        assert user.stripe_customer_id is None and user.stripe_subscription_id is None
        assert db.query(Subscription).filter(Subscription.user_id == user.id).count() == 0
        assert user.password_reset_token == hashlib.sha256(raw_token.encode()).hexdigest()
        assert user.hashed_password and user.hashed_password not in response.text
        expiry = user.password_reset_expires.replace(tzinfo=timezone.utc)
        assert timedelta(minutes=55) < expiry - datetime.now(timezone.utc) <= timedelta(hours=1)
        audit = db.query(AuditLog).filter(AuditLog.action == "free_account_created", AuditLog.entity_id == str(user.id)).one()
        assert audit.details == {"emailed": True}
    # Admin provisioning must not open the public invite gate.
    refused = client.post("/api/auth/register", json={"email": email(), "password": PASSWORD})
    assert refused.status_code == 403
    assert settings.REGISTRATION_MODE == "invite_only" and settings.REVERSE_TRIAL_ENABLED is False


@pytest.mark.requires_db
def test_duplicate_email_preserves_every_existing_field_and_sends_no_mail(client, as_admin, mail, monkeypatch):
    address = email()
    with SessionLocal() as db:
        user = User(email=address, full_name="Preserve", hashed_password="existing-hash", is_beta=True,
                    is_pro=True, is_admin=True, email_verified=True, password_reset_token="existing-token",
                    password_reset_expires=datetime.now(timezone.utc) + timedelta(hours=2))
        db.add(user)
        db.commit()
        db.refresh(user)
        before = {column.name: getattr(user, column.name) for column in User.__table__.columns}
    hashing = Mock(side_effect=AssertionError("must reject before hashing"))
    monkeypatch.setattr(admin_account_service, "get_password_hash", hashing)
    response = client.post("/api/admin/users/free", json={"email": f" {address.upper()} ", "full_name": "Replacement"})
    assert response.status_code == 409
    mail.assert_not_called()
    hashing.assert_not_called()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == address).one()
        assert {column.name: getattr(user, column.name) for column in User.__table__.columns} == before


def test_concurrent_creation_conflict_never_issues_reset(client, as_admin, mail, monkeypatch):
    monkeypatch.setattr(admin_account_service.auth_account_service, "create_password_account", lambda *a, **kw: None)
    issue = Mock(side_effect=AssertionError("must not reset winning account"))
    monkeypatch.setattr(admin_account_service.auth_account_service, "issue_password_reset_token", issue)
    response = client.post("/api/admin/users/free", json={"email": email()})
    assert response.status_code == 409
    issue.assert_not_called()
    mail.assert_not_called()


@pytest.mark.requires_db
@pytest.mark.parametrize("mail_fails", [False, True])
def test_real_admin_session_never_loads_expired_accounts_on_event_loop(client, mail, mail_fails):
    """Token and audit commits expire both Users; all subsequent reads must use plain snapshots."""
    actor_email = email()
    with SessionLocal() as db:
        db.add(User(email=actor_email, is_admin=True, email_verified=True))
        db.commit()
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": actor_email}))
    if mail_fails:
        mail.side_effect = RuntimeError("mail unavailable")
    on_loop_sql = []

    def observe_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        on_loop_sql.append(statement.split()[0])

    event.listen(engine, "before_cursor_execute", observe_sql)
    try:
        response = client.post("/api/admin/users/free", json={"email": email()})
    finally:
        event.remove(engine, "before_cursor_execute", observe_sql)
    assert response.status_code == 201, response.text
    assert response.json()["emailed"] is not mail_fails
    assert on_loop_sql == [], f"Synchronous SQL ran on the request event loop: {on_loop_sql}"


@pytest.mark.requires_db
def test_setup_reset_verifies_email_then_login_works_and_token_cannot_replay(client, as_admin, mail, postgres_expiry):
    address = email()
    assert client.post("/api/admin/users/free", json={"email": address}).status_code == 201
    raw_token = token(mail)
    app.dependency_overrides.clear()
    reset = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": PASSWORD})
    assert reset.status_code == 200, reset.text
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == address).one()
        assert user.email_verified and not user.is_beta and not user.is_pro
        assert user.password_reset_token is None and user.password_reset_expires is None
        assert verify_password(PASSWORD, user.hashed_password)
        assert db.query(Subscription).filter(Subscription.user_id == user.id).count() == 0
    assert client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": PASSWORD}).status_code == 400
    login = client.post("/api/auth/login", json={"email": address, "password": PASSWORD})
    assert login.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == address and me.json()["is_beta"] is False


@pytest.mark.requires_db
def test_mail_failure_is_redacted_and_existing_forgot_password_recovers(client, as_admin, mail, caplog):
    address = email()
    failed_links = []

    async def fail_delivery(**kwargs):
        failed_links.append(kwargs["reset_link"])
        raise RuntimeError(f"provider leaked request body: {kwargs['reset_link']}")

    mail.side_effect = fail_delivery
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/admin/users/free", json={"email": address})
    assert response.status_code == 201 and response.json()["emailed"] is False
    failed_token = parse_qs(urlparse(failed_links[0]).query)["token"][0]
    assert failed_token not in response.text and failed_token not in caplog.text
    assert "provider leaked" not in caplog.text
    mail.side_effect = None
    mail.reset_mock()
    app.dependency_overrides.clear()
    assert client.post("/api/auth/forgot-password", json={"email": address}).status_code == 200
    mail.assert_awaited_once()
    assert token(mail) != failed_token


@pytest.mark.parametrize("overrides", [
    {"email": "not-an-email"}, {"email": "x" * 255 + "@example.com"}, {"full_name": "x" * 101},
    {"full_name": "bad\nname"}, {"is_beta": False}, {"is_admin": True}, {"email_verified": True},
])
def test_invalid_or_privilege_fields_are_rejected(client, as_admin, mail, overrides):
    response = client.post("/api/admin/users/free", json={"email": email(), **overrides})
    assert response.status_code == 422
    mail.assert_not_called()
