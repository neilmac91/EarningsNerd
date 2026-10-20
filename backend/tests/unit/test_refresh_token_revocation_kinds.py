"""Regression gate: only a refresh token that was rotated away is a theft signal.

Every refresh rotates the presented token: it is revoked and ``replaced_by_id`` points at its
successor. Presenting a rotated-away token again means two parties hold copies of it, so
``refresh_token_service.rotate_refresh_token`` revokes every live token of the user. Logout,
logout-all, a password change and a password reset also revoke tokens, but they do not rotate them
(``replaced_by_id`` stays NULL). A device signed out that way keeps its cookie and presents it on
its next silent refresh. Treating that as theft revoked the session the user had just been given:
the acting device's re-issued one after a password change, or the new login after logout-all or a
reset. After a reset it also let whoever still held a token the reset revoked sign the owner out
again on every request.

Each case runs over HTTP with two clients, so the two devices keep separate cookie jars. The
signed-out device's refresh is refused with a 401 that revokes nothing, and the other device's new
session still refreshes. A logout that presents a token rotated away follows the rotation links to its
chain's live tip and revokes that alone; it is no theft signal either. Replaying a rotated-away token still takes the theft path; that half is
gated by ``test_refresh_replay.py`` and ``test_auth_token_flows.py``. The last test pins that it
still does after a reset, which is the residual the lesson records: the sweep is user-wide, so it
also ends the new login.
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


def _reset_password(client: TestClient, mail: SimpleNamespace, email: str) -> None:
    """Reset ``email``'s password to NEW_PASSWORD through the mailed link; the reset revokes every
    refresh token of the user."""
    assert client.post("/api/auth/forgot-password", json={"email": email}).status_code == 200
    token = parse_qs(urlparse(mail.reset.call_args.kwargs["reset_link"]).query)["token"][0]
    reset = client.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert reset.status_code == 200, reset.text


def _live_tokens(user_id: int) -> int:
    with SessionLocal() as db:
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        ).count()


def _assert_stale_refused_and_new_session_refreshes(
    stale: TestClient,
    new: TestClient,
    user_id: int,
    body: Optional[dict] = None,
) -> None:
    """The signed-out device's refresh is a plain 401, twice (it retries on every app open), that
    revokes nothing; the other device's new session then still refreshes."""
    live = _live_tokens(user_id)
    assert live == 1, "the other device's new session must be the user's one live token"
    for _ in range(2):
        resp = stale.post("/api/auth/refresh", json=body)
        assert resp.status_code == 401 and resp.json() == REFUSED, resp.text
    assert new.post("/api/auth/refresh").status_code == 200
    assert _live_tokens(user_id) == live  # the rotation replaced the one live token, nothing else


@pytest.mark.requires_db
def test_a_password_change_keeps_the_acting_devices_reissued_session(laptop, phone, mail):
    email, user_id = _register(laptop)
    _login(phone, email)
    _login(laptop, email)

    changed = laptop.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert changed.status_code == 200, changed.text

    _assert_stale_refused_and_new_session_refreshes(phone, laptop, user_id)


@pytest.mark.requires_db
def test_logout_all_then_a_new_login_keeps_the_new_session(laptop, phone, mail):
    email, user_id = _register(laptop)
    _login(phone, email)
    _login(laptop, email)

    everywhere = laptop.post("/api/auth/logout-all")
    assert everywhere.status_code == 200 and everywhere.json()["sessions_revoked"] == 2
    _login(laptop, email)

    _assert_stale_refused_and_new_session_refreshes(phone, laptop, user_id)


@pytest.mark.requires_db
def test_a_password_reset_then_a_new_login_keeps_the_new_session(
    laptop, phone, mail, postgres_shaped_reset_expiry
):
    """The reset evicts every session. A holder of a token the reset itself revoked (a forgotten
    device, or a stolen copy nobody refreshed before the reset) presenting it again must not sign
    the owner out of the new login. A stolen copy that was rotated away before the reset, by the
    attacker using it or by the owner's own device refreshing after the theft, still takes the
    user-wide theft sweep: the last test pins that residual, which the lesson
    arch-only-a-rotated-refresh-token-signals-theft.md records."""
    email, user_id = _register(laptop)
    _login(phone, email)

    _reset_password(laptop, mail, email)
    _login(laptop, email, NEW_PASSWORD)

    _assert_stale_refused_and_new_session_refreshes(phone, laptop, user_id)


@pytest.mark.requires_db
def test_a_logout_on_one_device_leaves_the_other_session_alone(laptop, phone, mail):
    email, user_id = _register(laptop)
    signed_out = _login(phone, email)
    _login(laptop, email)

    assert phone.post("/api/auth/logout").status_code == 200
    # Logout cleared the phone's cookie; a refresh another tab sent before the logout landed still
    # carries the token (here in the body).
    phone.cookies.clear()
    _assert_stale_refused_and_new_session_refreshes(
        phone, laptop, user_id, body={"refresh_token": signed_out}
    )


@pytest.mark.requires_db
def test_a_logout_whose_cookie_rotations_moved_past_signs_out_only_its_chains_live_tip(laptop, phone, mail):
    """Another tab refreshed twice while this logout's request was on its way, so its cookie is two
    rotations behind. The logout follows the rotation links to the chain's live tip and revokes it. It
    is no theft signal: the phone's session is untouched."""
    email, user_id = _register(laptop)
    _login(phone, email)
    behind = _login(laptop, email)
    for _ in range(2):
        assert laptop.post("/api/auth/refresh").status_code == 200

    laptop.cookies.clear()
    laptop.cookies.set(settings.REFRESH_COOKIE_NAME, behind)
    assert laptop.post("/api/auth/logout").status_code == 200

    assert _live_tokens(user_id) == 1  # the phone's session alone
    assert phone.post("/api/auth/refresh").status_code == 200


@pytest.mark.requires_db
def test_a_copy_rotated_away_before_a_reset_still_takes_the_user_wide_sweep(
    laptop, phone, mail, postgres_shaped_reset_expiry
):
    """The residual the lesson records. A thief copies the phone's token and never uses it; the
    phone's own silent refresh then rotates it away. After a reset and a new login, replaying the
    copy is still detected as theft, and the sweep is user-wide, so it ends the new login too.
    Scoping the sweep to the replayed token's own chain (deferred) would flip the last two
    assertions."""
    email, user_id = _register(laptop)
    stolen = _login(phone, email)
    assert phone.post("/api/auth/refresh").status_code == 200  # the owner rotates the copy away

    _reset_password(laptop, mail, email)
    _login(laptop, email, NEW_PASSWORD)
    assert _live_tokens(user_id) == 1

    # The thief replays the copy from a jar of its own (the cookie is read before the body).
    phone.cookies.clear()
    replay = phone.post("/api/auth/refresh", json={"refresh_token": stolen})
    assert replay.status_code == 401 and replay.json() == REFUSED, replay.text
    assert _live_tokens(user_id) == 0
    assert laptop.post("/api/auth/refresh").status_code == 401
