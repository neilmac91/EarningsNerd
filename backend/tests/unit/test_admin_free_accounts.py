"""Direct admin provisioning is retired: only recipients can accept account requirements.

Intentional auth-contract change: valid admin requests now receive an invitation instruction,
without account/token/mail writes. Authorization, validation and existing-account invariants stay.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from main import app
from app.config import settings
from app.database import SessionLocal, engine
from app.models import AccountAgreement, AuditLog, RefreshToken, Subscription, User
from app.services import auth_account_service, password_utils
from app.routers.auth import create_access_token, get_current_user
from tests.support.summary_stream_harness import reset_rate_limiters

REFUSAL = "Use an invitation so the recipient can accept the account requirements."


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


def email():
    return f"free-account-{uuid.uuid4().hex}@example.com"


def counts():
    with SessionLocal() as db:
        return {
            model.__tablename__: db.query(model).count()
            for model in (User, AccountAgreement, RefreshToken, Subscription, AuditLog)
        }


@pytest.mark.parametrize("authenticated", [False, True])
def test_non_admin_is_rejected_before_lookup_hash_or_mail(client, monkeypatch, mail, authenticated):
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(is_admin=False)
    lookup = Mock(side_effect=AssertionError("lookup before authorization"))
    hashing = Mock(side_effect=AssertionError("hash before authorization"))
    creation = Mock(side_effect=AssertionError("write before authorization"))
    monkeypatch.setattr(auth_account_service, "find_user_by_email", lookup)
    monkeypatch.setattr(auth_account_service, "create_password_account", creation)
    monkeypatch.setattr(password_utils, "get_password_hash", hashing)
    response = client.post("/api/admin/users/free", json={"email": email()})
    assert response.status_code == (403 if authenticated else 401)
    lookup.assert_not_called()
    hashing.assert_not_called()
    creation.assert_not_called()
    mail.assert_not_called()


@pytest.mark.requires_db
def test_valid_admin_is_refused_without_account_agreement_token_mail_or_audit(client, as_admin, mail):
    address = email()
    before = counts()
    response = client.post("/api/admin/users/free", json={"email": f" {address.upper()} ", "full_name": " Free Test "})
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": REFUSAL}
    assert not response.cookies
    assert counts() == before
    mail.assert_not_called()
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
    monkeypatch.setattr(password_utils, "get_password_hash", hashing)
    response = client.post("/api/admin/users/free", json={"email": f" {address.upper()} ", "full_name": "Replacement"})
    assert response.status_code == 409
    assert response.json() == {"detail": REFUSAL}
    mail.assert_not_called()
    hashing.assert_not_called()
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == address).one()
        assert {column.name: getattr(user, column.name) for column in User.__table__.columns} == before


def test_admin_refusal_precedes_lookup_hash_creation_and_reset(client, as_admin, mail, monkeypatch):
    lookup = Mock(side_effect=AssertionError("must not look up recipient"))
    hashing = Mock(side_effect=AssertionError("must not hash an initial password"))
    create = Mock(side_effect=AssertionError("must not stage recipient account"))
    issue = Mock(side_effect=AssertionError("must not issue a setup token"))
    monkeypatch.setattr(auth_account_service, "find_user_by_email", lookup)
    monkeypatch.setattr(password_utils, "get_password_hash", hashing)
    monkeypatch.setattr(auth_account_service, "create_password_account", create)
    monkeypatch.setattr(auth_account_service, "issue_password_reset_token", issue)
    response = client.post("/api/admin/users/free", json={"email": email()})
    assert response.status_code == 409
    lookup.assert_not_called()
    hashing.assert_not_called()
    create.assert_not_called()
    issue.assert_not_called()
    mail.assert_not_called()


@pytest.mark.requires_db
def test_real_admin_session_refuses_without_synchronous_sql_on_event_loop(client, mail):
    """Authorization still reads the actor off-loop; the refused action writes no recipient."""
    actor_email = email()
    with SessionLocal() as db:
        db.add(User(email=actor_email, is_admin=True, email_verified=True))
        db.commit()
    client.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": actor_email}))
    mail.side_effect = AssertionError("refused provisioning must not send mail")
    before = counts()
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
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": REFUSAL}
    assert counts() == before
    mail.assert_not_called()
    assert on_loop_sql == [], f"Synchronous SQL ran on the request event loop: {on_loop_sql}"


@pytest.mark.parametrize("overrides", [
    {"email": "not-an-email"}, {"email": "x" * 255 + "@example.com"}, {"full_name": "x" * 101},
    {"full_name": "bad\nname"}, {"is_beta": False}, {"is_admin": True}, {"email_verified": True},
    {"adult_eligible": True}, {"terms_accepted": True}, {"terms_version": "2026-10-23"},
])
def test_invalid_or_privilege_fields_are_rejected(client, as_admin, mail, overrides):
    response = client.post("/api/admin/users/free", json={"email": email(), **overrides})
    assert response.status_code == 422
    mail.assert_not_called()
