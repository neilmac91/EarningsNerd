"""Regression gate: only a refresh token that was rotated away is a theft signal.

Every refresh rotates the presented token: it is revoked and ``replaced_by_id`` points at its
successor. Presenting a rotated-away token again means two parties hold copies of it, so
``refresh_token_service.rotate_refresh_token`` revokes every live token of the user. Logout,
logout-all, a password change and a password reset also revoke tokens, but they do not rotate them
(``replaced_by_id`` stays NULL). A device signed out that way keeps its cookie and presents it on
its next silent refresh. Treating that as theft revoked the session the user had just been given:
the acting device's re-issued one after a password change, or the new login after logout-all or a
reset. After a reset it also let whoever held an evicted token sign the owner out again on every
request.

Each case runs over HTTP with two clients, so the two devices keep separate cookie jars. The
signed-out device's refresh is refused with a 401, writes nothing and logs no reuse warning, and
the other device's new session still refreshes. The last test pins the other half: replaying a
rotated-away token still revokes the user's live chain.
"""
import uuid
from datetime import timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal
from app.models import RefreshToken, User
from tests.support.summary_stream_harness import reset_rate_limiters

PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit; test fixture, not a credential  # gitleaks:allow
NEW_PASSWORD = PASSWORD + "9z"  # gitleaks:allow
REFUSED = {"detail": "Invalid or expired refresh token"}
REUSE_WARNING = "Refresh token reuse detected"


@pytest.fixture(scope="module")
def laptop():
    """The device the user acts on. Its ``with`` runs the app's startup (the tables)."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def phone(laptop):
    """A second device with its own cookie jar. No ``with``: a second lifespan's shutdown would tear
    down state the laptop client still uses."""
    client = TestClient(app)
    yield client
    client.close()


@pytest.fixture(autouse=True)
def _fresh(laptop, phone, monkeypatch):
    reset_rate_limiters()
    laptop.cookies.clear()
    phone.cookies.clear()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    yield
    laptop.cookies.clear()
    phone.cookies.clear()


@pytest.fixture
def mail(monkeypatch):
    sent = SimpleNamespace(verification=AsyncMock(), reset=AsyncMock())
    monkeypatch.setattr("app.services.email_service.send_verification_email", sent.verification)
    monkeypatch.setattr("app.services.email_service.send_password_reset_email", sent.reset)
    return sent


@pytest.fixture
def postgres_shaped_reset_expiry():
    """SQLite drops the zone from ``password_reset_expires``; load it aware, as PostgreSQL does."""
    def _aware(target, *_args):
        value = target.__dict__.get("password_reset_expires")
        if value is not None and value.tzinfo is None:
            set_committed_value(target, "password_reset_expires", value.replace(tzinfo=timezone.utc))

    event.listen(User, "load", _aware)
    event.listen(User, "refresh", _aware)
    yield
    event.remove(User, "load", _aware)
    event.remove(User, "refresh", _aware)


def _register(client: TestClient) -> tuple[str, int]:
    """Register a fresh password account; return (email, user id). Register issues no session."""
    email = f"revocationkinds_{uuid.uuid4().hex[:12]}@example.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    with SessionLocal() as db:
        return email, db.query(User.id).filter(User.email == email).scalar()


def _login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    """Log ``client`` in; return the refresh token now in its jar."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert token
    return token


def _live_tokens(user_id: int) -> int:
    with SessionLocal() as db:
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        ).count()


def _assert_stale_refused_and_new_session_refreshes(
    stale: TestClient,
    new: TestClient,
    user_id: int,
    caplog: pytest.LogCaptureFixture,
    body: Optional[dict] = None,
) -> None:
    """The signed-out device's refresh is a plain 401, twice (it retries on every app open), that
    revokes nothing and logs no reuse warning; the other device's new session then still refreshes."""
    live = _live_tokens(user_id)
    assert live == 1, "the other device's new session must be the user's one live token"
    for _ in range(2):
        resp = stale.post("/api/auth/refresh", json=body)
        assert resp.status_code == 401 and resp.json() == REFUSED, resp.text
    assert new.post("/api/auth/refresh").status_code == 200
    assert _live_tokens(user_id) == live  # the rotation replaced the one live token, nothing else
    assert REUSE_WARNING not in caplog.text


@pytest.mark.requires_db
def test_a_password_change_keeps_the_acting_devices_reissued_session(laptop, phone, mail, caplog):
    email, user_id = _register(laptop)
    _login(phone, email)
    _login(laptop, email)

    changed = laptop.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert changed.status_code == 200, changed.text

    _assert_stale_refused_and_new_session_refreshes(phone, laptop, user_id, caplog)


@pytest.mark.requires_db
def test_logout_all_then_a_new_login_keeps_the_new_session(laptop, phone, mail, caplog):
    email, user_id = _register(laptop)
    _login(phone, email)
    _login(laptop, email)

    everywhere = laptop.post("/api/auth/logout-all")
    assert everywhere.status_code == 200 and everywhere.json()["sessions_revoked"] == 2
    _login(laptop, email)

    _assert_stale_refused_and_new_session_refreshes(phone, laptop, user_id, caplog)


@pytest.mark.requires_db
def test_a_password_reset_then_a_new_login_keeps_the_new_session(
    laptop, phone, mail, caplog, postgres_shaped_reset_expiry
):
    """The reset evicts every session. The evicted holder (a forgotten device, or the attacker the
    reset was for) presenting its token again must not sign the owner out of the new login."""
    email, user_id = _register(laptop)
    _login(phone, email)

    assert laptop.post("/api/auth/forgot-password", json={"email": email}).status_code == 200
    token = parse_qs(urlparse(mail.reset.call_args.kwargs["reset_link"]).query)["token"][0]
    reset = laptop.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert reset.status_code == 200, reset.text
    _login(laptop, email, NEW_PASSWORD)

    _assert_stale_refused_and_new_session_refreshes(phone, laptop, user_id, caplog)


@pytest.mark.requires_db
def test_a_logout_on_one_device_leaves_the_other_session_alone(laptop, phone, mail, caplog):
    email, user_id = _register(laptop)
    signed_out = _login(phone, email)
    _login(laptop, email)

    assert phone.post("/api/auth/logout").status_code == 200
    # Logout cleared the phone's cookie; a refresh another tab sent before the logout landed still
    # carries the token (here in the body).
    phone.cookies.clear()
    _assert_stale_refused_and_new_session_refreshes(
        phone, laptop, user_id, caplog, body={"refresh_token": signed_out}
    )


@pytest.mark.requires_db
def test_replaying_a_rotated_away_token_still_revokes_the_live_chain(laptop, phone, mail, caplog):
    email, user_id = _register(laptop)
    stolen = _login(phone, email)
    assert phone.post("/api/auth/refresh").status_code == 200  # the holder rotates it away
    _login(laptop, email)
    assert _live_tokens(user_id) == 2

    thief = TestClient(app)  # its own empty jar; no ``with``, as for ``phone``
    try:
        replay = thief.post("/api/auth/refresh", json={"refresh_token": stolen})
    finally:
        thief.close()
    assert replay.status_code == 401 and replay.json() == REFUSED, replay.text
    assert REUSE_WARNING in caplog.text

    assert _live_tokens(user_id) == 0
    assert phone.post("/api/auth/refresh").status_code == 401
    assert laptop.post("/api/auth/refresh").status_code == 401
