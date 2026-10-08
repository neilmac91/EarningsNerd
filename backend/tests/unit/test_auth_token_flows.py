"""
Characterization of the auth flows no other test drives end to end.

Written against the router before its ORM work moved into app/services/ (the router-ORM ratchet,
tests/unit/test_router_orm_ceilings_allowlist.py) and kept unchanged through that move, so it
proves the refactor preserved behaviour:

  - email verification: verify, single use, unknown and expired links, resend (opaque; a resend
    supersedes the earlier link; a verified account gets no mail)
  - password reset: forgot-password is opaque and mails only password accounts; reset sets the
    password, confirms the email and evicts every session; unknown and expired links
  - the reverse trial granted on verification: the grant and its event, a failed grant that still
    verifies, and a user who is already Pro
  - the exact Set-Cookie headers, in order, of every session-issuing or session-clearing endpoint
    (cookie values and expiry stamps redacted)
  - the OAuth callbacks when the refresh-token write loses a race (IntegrityError at the flush):
    the conflict redirect, no session cookie, nothing persisted

Real endpoints against the app's SQLite database, like the rest of the auth suite. Mail is captured
by patching app.services.email_service (the router imports the senders at call time). SQLite hands
back ``DateTime(timezone=True)`` columns naive while PostgreSQL hands them back aware; the
``_postgres_shaped_expiries`` fixture gives the two token-expiry columns the production shape, so
the expiry comparisons run as they do on PostgreSQL.
"""
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal
from app.models import OAuthAccount, RefreshToken, Subscription, User
from app.routers import auth as auth_module
from app.services.posthog_client import EVENT_TRIAL_STARTED
from tests.support.summary_stream_harness import reset_rate_limiters

PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit; test fixture, not a credential  # gitleaks:allow
NEW_PASSWORD = PASSWORD + "9z"  # gitleaks:allow

VERIFIED_BODY = {"message": "Email verified. You can now use all features."}
RESEND_OPAQUE = {"message": "If that email has an unverified account, a new verification link is on its way."}
FORGOT_OPAQUE = {"message": "If an account exists for that email, a password reset link is on its way."}
RESET_BODY = {"message": "Password updated. You can now log in with your new password."}

# Set-Cookie headers as the test settings render them, values and expiry stamps redacted.
SESSION_ISSUED = [
    "earningsnerd_access_token=<v>; HttpOnly; Max-Age=1800; Path=/; SameSite=lax",
    "en_session=1; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax",
    "earningsnerd_refresh_token=<v>; HttpOnly; Max-Age=2592000; Path=/api/auth; SameSite=lax",
]
ACCESS_CLEARED = [
    'earningsnerd_access_token=""; expires=<t>; Max-Age=0; Path=/; SameSite=lax',
    'en_session=""; expires=<t>; Max-Age=0; Path=/; SameSite=lax',
]
REFRESH_CLEARED = ['earningsnerd_refresh_token=""; expires=<t>; Max-Age=0; Path=/api/auth; SameSite=lax']
GOOGLE_STATE_CLEARED = 'oauth_state=""; expires=<t>; Max-Age=0; Path=/; SameSite=lax'
APPLE_STATE_CLEARED = 'apple_oauth_state=""; expires=<t>; HttpOnly; Max-Age=0; Path=/; SameSite=none; Secure'

_TOKEN_EXPIRIES = ("email_verification_expires", "password_reset_expires")
_EXPIRES = re.compile(r"expires=[^;]+")


@pytest.fixture(scope="module")
def client():
    # HTTPS base: the Apple binding cookie is Secure and the client returns it only over HTTPS.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client, monkeypatch):
    reset_rate_limiters()
    client.cookies.clear()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", False)
    yield
    client.cookies.clear()


@pytest.fixture(autouse=True)
def _postgres_shaped_expiries():
    """Load the token-expiry columns tz-aware, as PostgreSQL returns them (SQLite drops the zone)."""
    def _aware(target, *_args):
        for name in _TOKEN_EXPIRIES:
            value = target.__dict__.get(name)
            if value is not None and value.tzinfo is None:
                set_committed_value(target, name, value.replace(tzinfo=timezone.utc))

    event.listen(User, "load", _aware)
    event.listen(User, "refresh", _aware)
    yield
    event.remove(User, "load", _aware)
    event.remove(User, "refresh", _aware)


@pytest.fixture
def mail(monkeypatch):
    sent = SimpleNamespace(verification=AsyncMock(), reset=AsyncMock())
    monkeypatch.setattr("app.services.email_service.send_verification_email", sent.verification)
    monkeypatch.setattr("app.services.email_service.send_password_reset_email", sent.reset)
    return sent


@pytest.fixture
def events(monkeypatch):
    seen: list[tuple[str, str, dict]] = []

    def _spy(distinct_id, event_name, properties=None):
        seen.append((distinct_id, event_name, properties or {}))

    monkeypatch.setattr(auth_module, "capture_event", _spy)
    return seen


# ── helpers ───────────────────────────────────────────────────────────────────

def _email() -> str:
    return f"tokenflow_{uuid.uuid4().hex[:12]}@example.com"


def _token(sender: AsyncMock, link_kwarg: str) -> str:
    link = sender.call_args.kwargs[link_kwarg]
    return parse_qs(urlparse(link).query)["token"][0]


def _register(client: TestClient, mail) -> tuple[str, str]:
    """Register a fresh password account; return (email, raw verification token)."""
    email = _email()
    resp = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    assert mail.verification.call_args.kwargs["to_email"] == email
    return email, _token(mail.verification, "verification_link")


def _user(email: str) -> User:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        db.expunge(user)
        return user


def _update_user(email: str, **fields) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        for name, value in fields.items():
            setattr(user, name, value)
        db.commit()


def _cookies(resp) -> list[str]:
    """The response's Set-Cookie headers in order, with random values and expiry stamps redacted."""
    shapes = []
    for header in resp.headers.get_list("set-cookie"):
        name, rest = header.split("=", 1)
        value, _, attrs = rest.partition(";")
        if value not in ('""', "1"):
            value = "<v>"
        shapes.append(_EXPIRES.sub("expires=<t>", f"{name}={value};{attrs}"))
    return shapes


def _login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ── email verification ────────────────────────────────────────────────────────

@pytest.mark.requires_db
def test_verify_email_verifies_the_account_once(client, mail):
    email, token = _register(client, mail)
    before = _user(email)
    assert before.email_verified is False and before.email_verification_token is not None
    remaining = before.email_verification_expires - datetime.now(timezone.utc)
    assert timedelta(hours=23) < remaining <= timedelta(hours=24)

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200, resp.text
    assert resp.json() == VERIFIED_BODY
    after = _user(email)
    assert after.email_verified is True
    assert after.email_verification_token is None and after.email_verification_expires is None

    again = client.post("/api/auth/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json() == {"detail": "Invalid or expired verification link."}


@pytest.mark.requires_db
def test_verify_email_rejects_an_unknown_token(client):
    resp = client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid or expired verification link."}


@pytest.mark.requires_db
def test_verify_email_rejects_an_expired_link_and_changes_nothing(client, mail):
    email, token = _register(client, mail)
    _update_user(email, email_verification_expires=datetime.now(timezone.utc) - timedelta(minutes=1))
    pending = _user(email).email_verification_token

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Verification link has expired. Request a new one."}
    user = _user(email)
    assert user.email_verified is False and user.email_verification_token == pending


@pytest.mark.requires_db
def test_resend_verification_is_opaque_and_supersedes_the_earlier_link(client, mail):
    unknown = client.post("/api/auth/resend-verification", json={"email": _email()})
    assert unknown.status_code == 200 and unknown.json() == RESEND_OPAQUE
    assert mail.verification.call_count == 0

    email, first = _register(client, mail)
    resent = client.post("/api/auth/resend-verification", json={"email": email.upper()})
    assert resent.status_code == 200 and resent.json() == RESEND_OPAQUE
    assert mail.verification.call_count == 2
    second = _token(mail.verification, "verification_link")
    assert second != first

    stale = client.post("/api/auth/verify-email", json={"token": first})
    assert stale.status_code == 400 and stale.json() == {"detail": "Invalid or expired verification link."}
    assert client.post("/api/auth/verify-email", json={"token": second}).json() == VERIFIED_BODY

    verified = client.post("/api/auth/resend-verification", json={"email": email})
    assert verified.status_code == 200 and verified.json() == RESEND_OPAQUE
    assert mail.verification.call_count == 2  # a verified account gets no mail


# ── password reset ────────────────────────────────────────────────────────────

@pytest.mark.requires_db
def test_forgot_password_is_opaque_and_mails_only_password_accounts(client, mail):
    unknown = client.post("/api/auth/forgot-password", json={"email": _email()})
    assert unknown.status_code == 200 and unknown.json() == FORGOT_OPAQUE

    social = _email()
    with SessionLocal() as db:
        db.add(User(email=social, hashed_password=None, email_verified=True))
        db.commit()
    social_only = client.post("/api/auth/forgot-password", json={"email": social})
    assert social_only.status_code == 200 and social_only.json() == FORGOT_OPAQUE
    assert mail.reset.call_count == 0
    assert _user(social).password_reset_token is None

    email, _ = _register(client, mail)
    resp = client.post("/api/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200 and resp.json() == FORGOT_OPAQUE
    assert mail.reset.call_count == 1
    assert mail.reset.call_args.kwargs["to_email"] == email
    token = _token(mail.reset, "reset_link")
    user = _user(email)
    assert user.password_reset_token is not None and user.password_reset_token != token  # hash only
    remaining = user.password_reset_expires - datetime.now(timezone.utc)
    assert timedelta(minutes=59) < remaining <= timedelta(hours=1)


@pytest.mark.requires_db
def test_reset_password_sets_the_password_confirms_the_email_and_evicts_sessions(client, mail):
    email, _ = _register(client, mail)
    assert _login(client, email).status_code == 200
    stale_refresh = client.cookies.get("earningsnerd_refresh_token")
    assert stale_refresh
    client.cookies.clear()

    client.post("/api/auth/forgot-password", json={"email": email})
    token = _token(mail.reset, "reset_link")
    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert resp.status_code == 200, resp.text
    assert resp.json() == RESET_BODY
    assert resp.headers.get_list("set-cookie") == []  # reset never signs the user in

    user = _user(email)
    assert user.email_verified is True
    assert user.password_reset_token is None and user.password_reset_expires is None
    assert client.post("/api/auth/refresh", json={"refresh_token": stale_refresh}).status_code == 401
    client.cookies.clear()
    assert _login(client, email).status_code == 401
    assert _login(client, email, NEW_PASSWORD).status_code == 200
    client.cookies.clear()

    again = client.post("/api/auth/reset-password", json={"token": token, "new_password": PASSWORD})
    assert again.status_code == 400 and again.json() == {"detail": "Invalid or expired reset link."}


@pytest.mark.requires_db
def test_reset_password_rejects_unknown_and_expired_links(client, mail):
    unknown = client.post("/api/auth/reset-password", json={"token": "nope", "new_password": NEW_PASSWORD})
    assert unknown.status_code == 400 and unknown.json() == {"detail": "Invalid or expired reset link."}

    email, _ = _register(client, mail)
    client.post("/api/auth/forgot-password", json={"email": email})
    token = _token(mail.reset, "reset_link")
    _update_user(email, password_reset_expires=datetime.now(timezone.utc) - timedelta(minutes=1))
    expired = client.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert expired.status_code == 400
    assert expired.json() == {"detail": "Reset link has expired. Request a new one."}
    assert _user(email).email_verified is False
    assert _login(client, email).status_code == 200  # the old password still works


# ── reverse trial on verification ─────────────────────────────────────────────

def _subscriptions(user_id: int) -> list[tuple[str, str]]:
    with SessionLocal() as db:
        return [(s.plan, s.status) for s in db.query(Subscription).filter(Subscription.user_id == user_id)]


@pytest.mark.requires_db
def test_verification_grants_the_reverse_trial_when_enabled(client, mail, events, monkeypatch):
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", True)
    email, token = _register(client, mail)
    user_id = _user(email).id
    events.clear()  # drop the signup events

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200 and resp.json() == VERIFIED_BODY
    assert _subscriptions(user_id) == [("pro", "trialing")]
    assert _user(email).is_pro is True
    assert events == [
        (str(user_id), EVENT_TRIAL_STARTED, {"source": "reverse_trial", "days": settings.REVERSE_TRIAL_DAYS})
    ]


@pytest.mark.requires_db
def test_a_failed_reverse_trial_still_verifies(client, mail, events, monkeypatch, caplog):
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", True)

    def _boom(db, user, days):
        user.is_pro = True  # a half-applied grant, which the rollback must discard
        raise RuntimeError("billing store down")

    monkeypatch.setattr("app.services.subscription_sync.start_reverse_trial", _boom)
    email, token = _register(client, mail)
    user_id = _user(email).id
    events.clear()

    with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
        resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200 and resp.json() == VERIFIED_BODY
    user = _user(email)
    assert user.email_verified is True and user.is_pro is False
    assert _subscriptions(user_id) == []
    assert events == []
    assert any(
        r.name == "app.routers.auth" and r.levelno == logging.WARNING and r.exc_info
        and r.getMessage() == f"Failed to start reverse trial for user {user_id} on verify"
        for r in caplog.records
    )


@pytest.mark.requires_db
def test_reverse_trial_skips_a_user_who_is_already_pro(client, mail, events, monkeypatch):
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", True)
    granted = []
    monkeypatch.setattr(
        "app.services.subscription_sync.start_reverse_trial", lambda *args: granted.append(args)
    )
    email, token = _register(client, mail)
    _update_user(email, is_pro=True)
    events.clear()

    resp = client.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 200 and resp.json() == VERIFIED_BODY
    assert granted == [] and events == []


# ── Set-Cookie headers, in order ──────────────────────────────────────────────

@pytest.mark.requires_db
def test_session_cookie_headers_and_their_order(client, mail):
    email, _ = _register(client, mail)

    login = _login(client, email)
    assert login.status_code == 200 and _cookies(login) == SESSION_ISSUED
    first_refresh = client.cookies.get("earningsnerd_refresh_token")

    rotated = client.post("/api/auth/refresh")
    assert rotated.status_code == 200 and _cookies(rotated) == SESSION_ISSUED

    changed = client.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert changed.status_code == 200 and _cookies(changed) == SESSION_ISSUED

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200 and logout.json() == {"status": "success"}
    assert _cookies(logout) == ACCESS_CLEARED + REFRESH_CLEARED

    client.cookies.clear()
    assert _login(client, email, NEW_PASSWORD).status_code == 200
    everywhere = client.post("/api/auth/logout-all")
    assert everywhere.status_code == 200 and everywhere.json() == {"status": "success", "sessions_revoked": 1}
    assert _cookies(everywhere) == ACCESS_CLEARED + REFRESH_CLEARED

    client.cookies.clear()
    unknown = client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert unknown.status_code == 401
    assert unknown.json() == {"detail": "Invalid or expired refresh token"}
    assert unknown.headers["www-authenticate"] == "Bearer"
    # The handler clears both cookies on the injected Response, but FastAPI renders an HTTPException
    # as a fresh response, so a refused refresh carries no Set-Cookie at all.
    assert _cookies(unknown) == []

    replay = client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
    assert replay.status_code == 401
    assert replay.json() == {"detail": "Invalid or expired refresh token"}
    assert _cookies(replay) == []


@pytest.mark.requires_db
def test_refresh_replay_revokes_the_live_chain(client, mail):
    """Replaying a rotated token is a theft signal: the revocation of the user's live tokens is
    committed even though the request is refused."""
    email, _ = _register(client, mail)
    _login(client, email)
    replayed = client.cookies.get("earningsnerd_refresh_token")
    assert client.post("/api/auth/refresh").status_code == 200
    live = client.cookies.get("earningsnerd_refresh_token")

    client.cookies.clear()
    assert client.post("/api/auth/refresh", json={"refresh_token": replayed}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": live}).status_code == 401
    with SessionLocal() as db:
        user_id = db.query(User.id).filter(User.email == email).scalar()
        assert db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        ).count() == 0


# ── OAuth callbacks: success cookies and the lost refresh-token race ──────────

class _FakeTokenResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"id_token": "stub"}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, *args, **kwargs) -> _FakeTokenResponse:
        return _FakeTokenResponse()


def _seed_verified(email: str) -> int:
    with SessionLocal() as db:
        user = User(email=email, hashed_password="x", email_verified=True)
        db.add(user)
        db.commit()
        return user.id


def _oauth_callback(client: TestClient, monkeypatch, provider: str, sub: str, email: str):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "io.earningsnerd.test")
    start = client.get(f"/api/auth/{provider}", follow_redirects=False)
    assert start.status_code == 302, start.text
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    if provider == "google":
        monkeypatch.setattr(auth_module, "httpx", SimpleNamespace(AsyncClient=_FakeAsyncClient))
        monkeypatch.setattr(
            auth_module, "_verify_google_id_token",
            AsyncMock(return_value={"sub": sub, "email": email, "email_verified": True}),
        )
        return client.get(
            "/api/auth/google/callback", params={"code": "code", "state": state}, follow_redirects=False
        )
    monkeypatch.setattr(
        auth_module, "_verify_apple_id_token",
        AsyncMock(return_value={"sub": sub, "email": email, "email_verified": "true"}),
    )
    return client.post(
        "/api/auth/apple/callback", data={"state": state, "id_token": "stub"}, follow_redirects=False
    )


_STATE_CLEARED = {"google": GOOGLE_STATE_CLEARED, "apple": APPLE_STATE_CLEARED}


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_link_issues_the_session_cookies_in_order(client, monkeypatch, provider):
    email = _email()
    user_id = _seed_verified(email)
    resp = _oauth_callback(client, monkeypatch, provider, f"{provider}_{uuid.uuid4().hex}", email)
    assert resp.status_code == 302 and resp.headers["location"] == settings.FRONTEND_URL
    assert _cookies(resp) == [_STATE_CLEARED[provider], *SESSION_ISSUED]
    user = _user(email)
    assert user.last_login_at is not None
    with SessionLocal() as db:
        assert db.query(OAuthAccount).filter_by(user_id=user_id, provider=provider).count() == 1
        assert db.query(RefreshToken).filter_by(user_id=user_id).count() == 1


@pytest.fixture
def lose_the_link_race():
    """Arm with (sub, user_id): the next flush that inserts an OAuthAccount for ``sub`` first has a
    competing request commit the same provider identity, so that flush raises IntegrityError (the
    concurrent first-sign-in race the callbacks turn into an account-conflict redirect)."""
    armed: dict = {}

    def _before_flush(session, _flush_context, _instances):
        sub = armed.get("sub")
        if sub is None or not any(
            isinstance(obj, OAuthAccount) and obj.provider_account_id == sub for obj in session.new
        ):
            return
        armed["sub"] = None
        with SessionLocal() as other:
            other.add(OAuthAccount(
                user_id=armed["user_id"], provider=armed["provider"], provider_account_id=sub,
            ))
            other.commit()

    event.listen(Session, "before_flush", _before_flush)
    yield armed
    event.remove(Session, "before_flush", _before_flush)


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_link_that_loses_the_race_redirects_with_a_conflict(
    client, monkeypatch, caplog, lose_the_link_race, provider
):
    email = _email()
    user_id = _seed_verified(email)
    sub = f"{provider}_{uuid.uuid4().hex}"
    lose_the_link_race.update(sub=sub, user_id=user_id, provider=provider)

    with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
        resp = _oauth_callback(client, monkeypatch, provider, sub, email)
    assert lose_the_link_race["sub"] is None, "the race was never injected"
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_URL}/login?error={provider}_account_conflict"
    assert _cookies(resp) == ([] if provider == "google" else [APPLE_STATE_CLEARED])
    assert _user(email).last_login_at is None  # the whole sign-in rolled back
    with SessionLocal() as db:
        assert db.query(RefreshToken).filter_by(user_id=user_id).count() == 0
        assert db.query(OAuthAccount).filter_by(provider_account_id=sub).count() == 1  # the winner's
    label = "Google" if provider == "google" else "Apple"
    assert any(
        r.name == "app.routers.auth" and r.getMessage() == f"{label} OAuth IntegrityError for sub={sub}"
        for r in caplog.records
    )
