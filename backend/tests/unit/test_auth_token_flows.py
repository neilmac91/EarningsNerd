"""
Characterization of the auth flows no other test drives end to end.

Written against the router before its ORM work moved into app/services/ (the router-ORM ratchet,
tests/unit/test_router_orm_ceilings_allowlist.py), and every test here passed on that pre-move
router as well as after the move, so it proved the refactor preserved behaviour. The password
login's one commit and the refusals of a login or change whose account changed while it hashed
(E121), the logout rows that name the user whose refresh token a logout revoked (E137), and the
register row a Google or Apple sign-in writes when it creates the account (D-054) pin deliberate
changes made since, and fail on the code before them; the rows of signed-in logouts that revoke
nothing, which E137 kept, the audit rows of the other sign-ins and of a password sign-up, and a
first sign-in whose session mint fails are pinned beside them:

  - email verification: verify, single use, unknown and expired links, resend (opaque; a resend
    supersedes the earlier link; a verified account gets no mail)
  - password reset: forgot-password is opaque and mails only password accounts; reset sets the
    password, confirms the email and evicts every session; unknown and expired links
  - the reverse trial granted on verification: the grant and its event, a failed grant that still
    verifies, and a user who is already Pro
  - the exact Set-Cookie headers, in order, of every session-issuing or session-clearing endpoint
    (cookie values and expiry stamps redacted)
  - the OAuth callbacks when the refresh-token write loses a race (IntegrityError at the flush):
    the conflict redirect, no session cookie, nothing persisted; likewise when a first sign-in's
    new-account insert loses a concurrent create for the same email, with the router's warning
  - logout and logout-all commit their own revocations (with no audit row committing after them),
    and unlinking a provider commits the delete itself before its oauth_unlinked audit row; a logout
    that sends only the refresh cookie logs its row under that token's user, a deliberate change
    (E137)
  - a password login: a success resets the failed-login count, and that reset, last_login_at and the
    session's refresh token commit together, under the account's lock (E121), so a failed mint
    changes nothing; a password change whose mint fails changes nothing (one commit); a login or a
    change whose password changed while it hashed is refused, and a login whose account was
    deactivated meanwhile too; a registration that loses a concurrent create stays opaque
  - an OAuth callback commits its own sign-in (a new account, the link, last_login_at, the refresh
    token) with no audit row committing after it; the connections list; Apple's name fill-in on an
    existing link and its first sign-in without an email
  - the audit rows of a sign-up and an OAuth sign-in: /register writes register once, under the
    keyed hash of the address; an OAuth sign-in that creates the account, in public mode or by
    invite under invite_only (the deployed mode), writes register and then oauth_login, once each,
    under the same hash; a returning one oauth_login alone; a link to an existing verified account
    oauth_login and oauth_linked; a refused sign-in, a conflict, a lost create race and a new account
    whose commit loses its link write none and set no session cookie; and a first sign-in whose
    session mint fails answers 500 and leaves no account, link or audit row
  - the failure paths that roll back (a failed reverse trial, the OAuth races) do so before they log

Real endpoints against the app's SQLite database, like the rest of the auth suite. Mail is captured
by patching app.services.email_service (the router and account_mail_service look the senders up on it
at call time; with durable tasks off, as here, the reset and resend mails go out in a background task
the test client runs before it returns). SQLite hands
back ``DateTime(timezone=True)`` columns naive while PostgreSQL hands them back aware; the
``_postgres_shaped_expiries`` fixture gives the two token-expiry columns the production shape, so
the expiry comparisons run as they do on PostgreSQL. The session-mint failures and the races are
injected at the session's flush (SQLAlchemy events), so they hit the same write before and after
the move, whichever module issues it.
"""
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Optional
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
from app.models import AuditLog, LoginAttempt, OAuthAccount, RefreshToken, Subscription, User
from app.routers import auth as auth_module
from app.services import invite_service, login_lockout, refresh_token_service
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
    auth_module.OAUTH_START_LIMITER._hits.clear()  # 20/min/IP; this file starts many OAuth flows
    client.cookies.clear()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", False)
    yield
    client.cookies.clear()


@pytest.fixture
def server_errors(client):
    """A client that gets the app's 500 for an unhandled exception instead of re-raising it.

    No ``with``: the module client already ran the app's startup, and a second lifespan's shutdown
    would tear down state that client still uses.
    """
    errors_client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    yield errors_client
    errors_client.close()


@pytest.fixture
def fail_the_refresh_token_insert():
    """Arm with ``armed["on"] = True``: the next flush that inserts a RefreshToken raises instead, as
    a failed session mint would, after the endpoint's earlier writes."""
    armed = {"on": False, "fired": False}

    def _before_flush(session, _flush_context, _instances):
        if armed["on"] and any(isinstance(obj, RefreshToken) for obj in session.new):
            armed.update(on=False, fired=True)
            raise RuntimeError("refresh-token store down")

    event.listen(Session, "before_flush", _before_flush)
    yield armed
    event.remove(Session, "before_flush", _before_flush)


@pytest.fixture
def root_rollbacks(caplog):
    """Each rollback of a Session's own transaction, recorded as the number of log records
    ``caplog`` held at that moment, so a test can pin "rolled back, then logged". A failed flush
    also rolls back its sub-transaction; that one is not recorded."""
    marks: list[int] = []

    def _after_soft_rollback(_session, previous_transaction):
        if previous_transaction.parent is None:
            marks.append(len(caplog.records))

    event.listen(Session, "after_soft_rollback", _after_soft_rollback)
    yield marks
    event.remove(Session, "after_soft_rollback", _after_soft_rollback)


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
def test_a_failed_reverse_trial_still_verifies(client, mail, events, monkeypatch, caplog, root_rollbacks):
    monkeypatch.setattr(settings, "REVERSE_TRIAL_ENABLED", True)

    def _boom(db, user, days):
        user.is_pro = True  # a half-applied grant: it must not persist
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
    (warning,) = [
        r for r in caplog.records
        if r.name == "app.routers.auth" and r.levelno == logging.WARNING
        and r.getMessage() == f"Failed to start reverse trial for user {user_id} on verify"
    ]
    # The warning carries the original failure, not a wrapper, as its exception.
    assert warning.exc_info[0] is RuntimeError and str(warning.exc_info[1]) == "billing store down"
    # The half-applied grant is rolled back before the warning is logged, and nothing else rolls back.
    assert len(root_rollbacks) == 1 and root_rollbacks[0] <= caplog.records.index(warning)


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
    assert unknown.json() == {"detail": "Your session has ended. Log in again."}
    assert unknown.headers["www-authenticate"] == "Bearer"
    # The handler clears both cookies on the injected Response, but FastAPI renders an HTTPException
    # as a fresh response, so a refused refresh carries no Set-Cookie at all.
    assert _cookies(unknown) == []

    replay = client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
    assert replay.status_code == 401
    assert replay.json() == {"detail": "Your session has ended. Log in again."}
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


# ── password login and change: what commits, and when ─────────────────────────

WRONG_PASSWORD = "not-the-password"  # gitleaks:allow


def _lockout_rows(email: str) -> int:
    with SessionLocal() as db:
        return db.query(LoginAttempt).filter(LoginAttempt.email_hash == login_lockout._email_hash(email)).count()


def _failed_count(email: str) -> Optional[int]:
    with SessionLocal() as db:
        return db.query(LoginAttempt.failed_count).filter(
            LoginAttempt.email_hash == login_lockout._email_hash(email)
        ).scalar()


def _refresh_tokens(user_id: int) -> int:
    with SessionLocal() as db:
        return db.query(RefreshToken).filter(RefreshToken.user_id == user_id).count()


def _failed_login_audits(email: str) -> int:
    with SessionLocal() as db:
        return db.query(AuditLog).filter(AuditLog.action == "login_failed", AuditLog.user_email == email).count()


@pytest.mark.requires_db
@pytest.mark.parametrize("account", ["unknown_email", "no_password"])
def test_a_login_with_no_password_to_check_still_runs_bcrypt(client, mail, monkeypatch, account):
    """bcrypt runs whether or not the email has an account with a password, against a fixed dummy hash
    when it has none (an unknown email, or an account that signs in only through Google or Apple), so
    the answer's timing does not tell which emails are registered; the answer is the generic 401."""
    if account == "unknown_email":
        email = _email()
    else:
        email, _ = _register(client, mail)
        _update_user(email, hashed_password=None)
    hashes_checked: list[str] = []
    real_verify = auth_module.verify_password

    def recording_verify(password: str, hashed: str) -> bool:
        hashes_checked.append(hashed)
        return real_verify(password, hashed)

    monkeypatch.setattr(auth_module, "verify_password", recording_verify)
    resp = _login(client, email, PASSWORD)
    assert resp.status_code == 401 and resp.json() == {"detail": "Incorrect email or password"}
    assert hashes_checked == [auth_module._DUMMY_PASSWORD_HASH]


@pytest.mark.requires_db
def test_a_successful_login_resets_the_failed_login_count(client, mail):
    """THRESHOLD-1 failures, a success, THRESHOLD-1 more failures: without the reset the second run
    would reach the threshold and lock the account (429)."""
    email, _ = _register(client, mail)

    def _attempt(password: str) -> int:
        auth_module.LOGIN_LIMITER._hits.clear()  # isolate the per-account lockout from the per-IP limiter
        resp = _login(client, email, password)
        client.cookies.clear()
        return resp.status_code

    misses = login_lockout.LOCKOUT_THRESHOLD - 1
    for _ in range(2):
        assert [_attempt(WRONG_PASSWORD) for _ in range(misses)] == [401] * misses
        assert _lockout_rows(email) == 1
        assert _attempt(PASSWORD) == 200
        assert _lockout_rows(email) == 0


@pytest.mark.requires_db
def test_a_login_whose_session_mint_fails_changes_nothing(
    client, mail, server_errors, fail_the_refresh_token_insert
):
    """The lockout reset, last_login_at and the session's refresh token commit together, under the
    account's lock (E121): a failed mint answers 500 with no session and no login audit row, and
    keeps the failed-login count and the empty login stamp it found."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    assert _login(client, email, WRONG_PASSWORD).status_code == 401
    assert _failed_count(email) == 1 and _user(email).last_login_at is None

    fail_the_refresh_token_insert["on"] = True
    resp = server_errors.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert fail_the_refresh_token_insert["fired"], "the mint failure was never injected"
    assert resp.status_code == 500 and _cookies(resp) == []
    assert _failed_count(email) == 1  # neither cleared nor counted again
    assert _user(email).last_login_at is None
    assert _refresh_tokens(user_id) == 0
    assert _audit_actions(user_id, "login_success") == []


@pytest.mark.requires_db
@pytest.mark.parametrize("meanwhile", ["password_changed", "deactivated"])
def test_a_login_whose_account_changed_while_it_hashed_is_refused(client, mail, monkeypatch, meanwhile):
    """A password reset or change, or a deactivation, that commits while a login is in bcrypt leaves
    the account the login read stale: the login is refused like a wrong password and mints no session
    (E121)."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    real_verify = auth_module.verify_password
    matches: list[bool] = []

    def verify_then_reset(password: str, hashed: str) -> bool:
        matched = real_verify(password, hashed)
        matches.append(matched)
        with SessionLocal() as db:  # the change commits while the login hashes
            user = db.get(User, user_id)
            if meanwhile == "password_changed":
                user.hashed_password = auth_module.get_password_hash(NEW_PASSWORD)
            else:
                user.is_active = False
            db.commit()
        return matched

    monkeypatch.setattr(auth_module, "verify_password", verify_then_reset)
    resp = _login(client, email, PASSWORD)
    assert matches == [True]  # refused by the re-check, not as a wrong password
    assert resp.status_code == 401 and resp.json() == {"detail": "Incorrect email or password"}
    assert _cookies(resp) == []
    assert _refresh_tokens(user_id) == 0
    assert _failed_count(email) == 1 and _user(email).last_login_at is None
    assert _audit_actions(user_id, "login_success") == [] and _failed_login_audits(email) == 1


@pytest.mark.requires_db
def test_a_password_change_whose_session_mint_fails_changes_nothing(
    client, mail, server_errors, fail_the_refresh_token_insert
):
    """The new hash, the revocation of every session and this device's new refresh token commit
    together: when the mint fails, the old password and the existing session still work."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    login = _login(client, email)
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    existing_refresh = client.cookies.get("earningsnerd_refresh_token")
    client.cookies.clear()
    stored_hash = _user(email).hashed_password

    fail_the_refresh_token_insert["on"] = True
    resp = server_errors.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert fail_the_refresh_token_insert["fired"], "the mint failure was never injected"
    assert resp.status_code == 500 and _cookies(resp) == []
    assert _user(email).hashed_password == stored_hash
    assert _live_refresh_tokens(user_id) == 1

    assert client.post("/api/auth/refresh", json={"refresh_token": existing_refresh}).status_code == 200
    client.cookies.clear()
    assert _login(client, email).status_code == 200
    client.cookies.clear()
    assert _login(client, email, NEW_PASSWORD).status_code == 401


@pytest.mark.requires_db
def test_a_password_change_whose_password_changed_while_it_hashed_is_refused(client, mail, monkeypatch):
    """A password reset or another change that commits while a change is in bcrypt leaves the current
    password the change checked stale: the change is refused as a wrong current password and writes
    nothing, so the password that committed meanwhile stands and no session is revoked or minted (E121)."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    login = _login(client, email)
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    client.cookies.clear()
    recovered_hash = auth_module.get_password_hash(PASSWORD + "8y")
    real_verify = auth_module.verify_password
    matches: list[bool] = []

    def verify_then_reset(password: str, hashed: str) -> bool:
        matched = real_verify(password, hashed)
        matches.append(matched)
        with SessionLocal() as db:  # the reset commits while the change hashes
            db.get(User, user_id).hashed_password = recovered_hash
            db.commit()
        return matched

    monkeypatch.setattr(auth_module, "verify_password", verify_then_reset)
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert matches == [True]  # refused by the re-check, not as a wrong current password
    assert resp.status_code == 400 and resp.json() == {"detail": "Current password is incorrect."}
    assert _cookies(resp) == []
    assert _user(email).hashed_password == recovered_hash
    assert (_refresh_tokens(user_id), _live_refresh_tokens(user_id)) == (1, 1)  # the login's, untouched


# ── logout: each endpoint commits its own revocation ──────────────────────────

def _audit_actions(user_id: int, action: str) -> list[tuple[str, dict]]:
    with SessionLocal() as db:
        return [
            (row.entity_type, row.details)
            for row in db.query(AuditLog).filter(AuditLog.user_id == str(user_id), AuditLog.action == action)
        ]


def _logout_rows(user_id: int) -> list[tuple[str, str, bool]]:
    """Each logout row under ``user_id``: its entity, its email, and whether it records an address."""
    with SessionLocal() as db:
        return [
            (row.entity_type, row.user_email, row.ip_address is not None)
            for row in db.query(AuditLog).filter(AuditLog.user_id == str(user_id), AuditLog.action == "logout")
        ]


def _live_refresh_tokens(user_id: int) -> int:
    with SessionLocal() as db:
        return db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        ).count()


@pytest.fixture
def no_audit_rows(monkeypatch):
    """Make every audit write a no-op, so its commit can no longer carry an endpoint's pending writes."""
    monkeypatch.setattr("app.services.audit_service.create_audit_log", lambda *args, **kwargs: None)


@pytest.mark.requires_db
def test_logout_with_only_the_refresh_cookie_revokes_it(client, mail, no_audit_rows):
    """No live access token, and no audit row whose commit could carry the revocation: logout's own
    commit must persist it."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    assert _login(client, email).status_code == 200
    refresh = client.cookies.get("earningsnerd_refresh_token")
    client.cookies.delete("earningsnerd_access_token")
    client.cookies.delete("en_session")

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200 and resp.json() == {"status": "success"}
    assert _cookies(resp) == ACCESS_CLEARED + REFRESH_CLEARED
    assert _live_refresh_tokens(user_id) == 0

    client.cookies.clear()
    assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401


@pytest.mark.requires_db
def test_logout_with_only_the_refresh_cookie_logs_it_under_that_tokens_user(client, mail):
    """The session token lasts 30 minutes, so a logout after them names no current user; its row names
    the user whose refresh token it revoked (E137). Once that token is revoked, the same cookie ends no
    session and writes no second row."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    assert _login(client, email).status_code == 200
    refresh = client.cookies.get("earningsnerd_refresh_token")
    client.cookies.clear()

    for _ in range(2):
        client.cookies.set("earningsnerd_refresh_token", refresh)
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200 and resp.json() == {"status": "success"}

    assert _logout_rows(user_id) == [("user", email, True)]
    assert _live_refresh_tokens(user_id) == 0


@pytest.mark.requires_db
@pytest.mark.parametrize("refresh_cookie", ["not_sent", "revoked_elsewhere"])
def test_a_signed_in_logout_that_revokes_nothing_logs_it_under_the_signed_in_user(client, mail, refresh_cookie):
    """A signed-in logout whose refresh cookie revokes nothing still ends the session token's use here,
    so its row names the signed-in user. One sends no refresh cookie, and its token stays live; the
    other sends the cookie of a token that logout-all on another device has already revoked, as a
    browser still holding it would."""
    email, _ = _register(client, mail)
    user_id = _user(email).id
    assert _login(client, email).status_code == 200
    if refresh_cookie == "not_sent":
        client.cookies.delete("earningsnerd_refresh_token")
    else:
        with SessionLocal() as db:
            assert refresh_token_service.revoke_all_and_commit(db, user_id) == 1

    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200 and resp.json() == {"status": "success"}
    assert _logout_rows(user_id) == [("user", email, True)]
    assert _live_refresh_tokens(user_id) == (1 if refresh_cookie == "not_sent" else 0)


@pytest.mark.requires_db
def test_a_logout_whose_refresh_cookie_is_another_accounts_logs_it_under_that_account(client, mail):
    """One account's bearer token beside another's refresh cookie (an API client; the site never sends a
    bearer token): the session the logout ends is the refresh token's, so its row names that token's user
    and none names the bearer's (Codex r4332649556 on #1451)."""
    bearer_email, _ = _register(client, mail)
    cookie_email, _ = _register(client, mail)
    client.cookies.clear()
    bearer = _login(client, bearer_email).json()["access_token"]
    client.cookies.clear()
    assert _login(client, cookie_email).status_code == 200
    refresh = client.cookies.get("earningsnerd_refresh_token")
    client.cookies.clear()
    client.cookies.set("earningsnerd_refresh_token", refresh)

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {bearer}"})
    assert resp.status_code == 200 and resp.json() == {"status": "success"}
    assert _logout_rows(_user(cookie_email).id) == [("user", cookie_email, True)]
    assert _logout_rows(_user(bearer_email).id) == []
    assert _live_refresh_tokens(_user(cookie_email).id) == 0


@pytest.mark.requires_db
def test_logout_all_commits_its_revocation_without_the_audit_row(client, mail, no_audit_rows):
    email, _ = _register(client, mail)
    user_id = _user(email).id
    assert _login(client, email).status_code == 200
    other_device = client.cookies.get("earningsnerd_refresh_token")
    client.cookies.clear()
    assert _login(client, email).status_code == 200

    resp = client.post("/api/auth/logout-all")
    assert resp.status_code == 200 and resp.json() == {"status": "success", "sessions_revoked": 2}
    assert _live_refresh_tokens(user_id) == 0

    client.cookies.clear()
    assert client.post("/api/auth/refresh", json={"refresh_token": other_device}).status_code == 401


# ── connections: unlinking a linked provider ──────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.parametrize("audited", [True, False], ids=["audited", "audit-write-skipped"])
def test_unlinking_a_linked_provider_deletes_the_link_then_audits_it(client, mail, request, audited):
    """The delete commits on its own, before the oauth_unlinked audit row; with the audit write made
    a no-op the link must still be gone."""
    email, _ = _register(client, mail)  # a password account, so the link is not its last method
    user_id = _user(email).id
    with SessionLocal() as db:
        db.add(OAuthAccount(
            user_id=user_id, provider="google", provider_account_id=f"google_{uuid.uuid4().hex}",
            provider_email=email,
        ))
        db.commit()
    assert _login(client, email).status_code == 200
    if not audited:
        request.getfixturevalue("no_audit_rows")

    resp = client.delete("/api/auth/connections/google")
    assert resp.status_code == 200 and resp.json() == {"status": "success", "unlinked": "google"}
    with SessionLocal() as db:
        assert db.query(OAuthAccount).filter_by(user_id=user_id).count() == 0
    assert _audit_actions(user_id, "oauth_unlinked") == ([("user", {"provider": "google"})] if audited else [])


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


def _seed_verified(email: str, full_name: Optional[str] = None) -> int:
    with SessionLocal() as db:
        user = User(email=email, hashed_password="x", email_verified=True, full_name=full_name)
        db.add(user)
        db.commit()
        return user.id


def _seed_link(user_id: int, provider: str, sub: str, email: str) -> None:
    with SessionLocal() as db:
        db.add(OAuthAccount(user_id=user_id, provider=provider, provider_account_id=sub, provider_email=email))
        db.commit()


def _oauth_callback(
    client: TestClient,
    monkeypatch,
    provider: str,
    sub: str,
    email: Optional[str],
    *,
    apple_user: Optional[str] = None,
    invite: Optional[str] = None,
):
    """Run a provider flow end to end; ``apple_user`` is the JSON ``user`` field Apple posts on a
    first authorization, and ``invite`` a closed-beta token the flow starts with, sent in the body of
    the POST start as the sign-up page sends it."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "io.earningsnerd.test")
    if invite is None:
        start = client.get(f"/api/auth/{provider}", follow_redirects=False)
        assert start.status_code == 302, start.text
        consent_url = start.headers["location"]
    else:
        start = client.post(f"/api/auth/{provider}/start", json={"invite": invite})
        assert start.status_code == 200, start.text
        consent_url = start.json()["url"]
    state = parse_qs(urlparse(consent_url).query)["state"][0]
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
    form = {"state": state, "id_token": "stub"}
    if apple_user is not None:
        form["user"] = apple_user
    return client.post("/api/auth/apple/callback", data=form, follow_redirects=False)


_STATE_CLEARED = {"google": GOOGLE_STATE_CLEARED, "apple": APPLE_STATE_CLEARED}


@pytest.mark.requires_db
@pytest.mark.parametrize("audited", [True, False], ids=["audited", "audit-write-skipped"])
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_link_issues_the_session_cookies_in_order(client, monkeypatch, request, provider, audited):
    """Linking a verified account signs it in. The callback commits the sign-in itself (the link,
    last_login_at and the refresh token) before its audit rows: with the audit writes made no-ops
    all of it must still persist."""
    email = _email()
    user_id = _seed_verified(email)
    if not audited:
        request.getfixturevalue("no_audit_rows")
    resp = _oauth_callback(client, monkeypatch, provider, f"{provider}_{uuid.uuid4().hex}", email)
    assert resp.status_code == 302 and resp.headers["location"] == settings.FRONTEND_URL
    assert _cookies(resp) == [_STATE_CLEARED[provider], *SESSION_ISSUED]
    user = _user(email)
    assert user.last_login_at is not None
    with SessionLocal() as db:
        assert db.query(OAuthAccount).filter_by(user_id=user_id, provider=provider).count() == 1
        assert db.query(RefreshToken).filter_by(user_id=user_id).count() == 1
    audit_rows = [("user", {"provider": provider})] if audited else []
    assert _audit_actions(user_id, "oauth_login") == audit_rows
    assert _audit_actions(user_id, "oauth_linked") == audit_rows

    # The session it issued lists the new link among the account's sign-in methods.
    connections = client.get("/api/auth/connections")
    assert connections.status_code == 200, connections.text
    body = connections.json()
    (linked,) = body["providers"]
    assert datetime.fromisoformat(linked.pop("linked_at"))
    assert body == {"has_password": True, "providers": [{"provider": provider, "provider_email": email}]}


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_first_sign_in_commits_the_new_account_itself(client, monkeypatch, no_audit_rows, provider):
    """A first social sign-in's new account, its link, last_login_at and the refresh token are
    committed by the sign-in, not by the audit row written after it (made a no-op here)."""
    email = _email()
    sub = f"{provider}_{uuid.uuid4().hex}"
    resp = _oauth_callback(client, monkeypatch, provider, sub, email)
    assert resp.status_code == 302 and resp.headers["location"] == settings.FRONTEND_URL
    assert _cookies(resp) == [_STATE_CLEARED[provider], *SESSION_ISSUED]
    user = _user(email)
    assert user.hashed_password is None and user.email_verified is True
    assert user.last_login_at is not None
    with SessionLocal() as db:
        assert db.query(OAuthAccount).filter_by(provider=provider, provider_account_id=sub).one().user_id == user.id
    assert _refresh_tokens(user.id) == 1


_APPLE_FIRST_AUTH_USER = json.dumps({"name": {"firstName": "Ada", "lastName": "Lovelace"}})


@pytest.mark.requires_db
@pytest.mark.parametrize(
    "stored_name, expected", [(None, "Ada Lovelace"), ("Grace Hopper", "Grace Hopper")], ids=["empty", "kept"]
)
def test_apple_sign_in_on_an_existing_link_fills_in_only_a_missing_name(client, monkeypatch, stored_name, expected):
    email = _email()
    user_id = _seed_verified(email, full_name=stored_name)
    sub = f"apple_{uuid.uuid4().hex}"
    _seed_link(user_id, "apple", sub, email)

    resp = _oauth_callback(client, monkeypatch, "apple", sub, email, apple_user=_APPLE_FIRST_AUTH_USER)
    assert resp.status_code == 302 and resp.headers["location"] == settings.FRONTEND_URL
    assert _cookies(resp) == [APPLE_STATE_CLEARED, *SESSION_ISSUED]
    assert _user(email).full_name == expected


@pytest.mark.requires_db
@pytest.mark.parametrize("linked", [False, True], ids=["first-sign-in", "existing-link"])
def test_apple_sign_in_without_an_email_needs_an_existing_link(client, monkeypatch, linked):
    """No email claim: a first sign-in is refused with apple_missing_claims and persists nothing; an
    existing link (looked up first) still signs in."""
    sub = f"apple_{uuid.uuid4().hex}"
    if linked:
        email = _email()
        _seed_link(_seed_verified(email), "apple", sub, email)

    resp = _oauth_callback(client, monkeypatch, "apple", sub, None)
    assert resp.status_code == 302
    if linked:
        assert resp.headers["location"] == settings.FRONTEND_URL
        assert _cookies(resp) == [APPLE_STATE_CLEARED, *SESSION_ISSUED]
        return
    assert resp.headers["location"] == f"{settings.FRONTEND_URL}/login?error=apple_missing_claims"
    assert _cookies(resp) == [APPLE_STATE_CLEARED]
    with SessionLocal() as db:
        assert db.query(OAuthAccount).filter_by(provider_account_id=sub).count() == 0


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
    client, monkeypatch, caplog, root_rollbacks, lose_the_link_race, provider
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
    (warning,) = [
        r for r in caplog.records
        if r.name == "app.routers.auth" and r.getMessage() == f"{label} OAuth IntegrityError for sub={sub}"
    ]
    assert warning.levelno == logging.WARNING
    # Rolled back (once) before the warning is logged.
    assert len(root_rollbacks) == 1 and root_rollbacks[0] <= caplog.records.index(warning)


@pytest.fixture
def lose_the_create_race():
    """Arm with an email: the next flush that inserts a User with that email first has a competing
    request commit an account for it, so that flush raises IntegrityError (UNIQUE users.email), the
    concurrent first sign-in a new-account callback turns into an account-conflict redirect."""
    armed: dict = {}

    def _before_flush(session, _flush_context, _instances):
        email = armed.get("email")
        if email is None or not any(isinstance(obj, User) and obj.email == email for obj in session.new):
            return
        armed["email"] = None
        armed["winner_id"] = _seed_verified(email)

    event.listen(Session, "before_flush", _before_flush)
    yield armed
    event.remove(Session, "before_flush", _before_flush)


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_first_sign_in_that_loses_the_create_race_redirects_with_a_conflict(
    client, monkeypatch, caplog, root_rollbacks, lose_the_create_race, provider
):
    email = _email()
    sub = f"{provider}_{uuid.uuid4().hex}"
    lose_the_create_race["email"] = email

    with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
        resp = _oauth_callback(client, monkeypatch, provider, sub, email)
    assert lose_the_create_race["email"] is None, "the race was never injected"
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_URL}/login?error={provider}_account_conflict"
    assert _cookies(resp) == ([] if provider == "google" else [APPLE_STATE_CLEARED])
    with SessionLocal() as db:
        assert [u.id for u in db.query(User).filter(User.email == email)] == [lose_the_create_race["winner_id"]]
        assert db.query(OAuthAccount).filter_by(provider_account_id=sub).count() == 0
        assert db.query(RefreshToken).filter_by(user_id=lose_the_create_race["winner_id"]).count() == 0
    warnings = [r for r in caplog.records if r.getMessage().endswith("OAuth IntegrityError creating account")]
    assert [(r.name, r.levelno, r.getMessage()) for r in warnings] == [
        ("app.routers.auth", logging.WARNING, f"{provider} OAuth IntegrityError creating account")
    ]
    # Rolled back (once) before the warning is logged.
    assert len(root_rollbacks) == 1 and root_rollbacks[0] <= caplog.records.index(warnings[0])


# ── sign-ups and OAuth sign-ins: the audit rows they write (D-054) ────────────

def _audit_trail(email: str) -> list[tuple[str, Optional[str], Optional[dict], Optional[str]]]:
    """Every audit row written for ``email``, oldest first: its action, the account id it names, its
    details and the address it records."""
    with SessionLocal() as db:
        return [
            (row.action, row.user_id, row.details, row.ip_address)
            for row in db.query(AuditLog).filter(AuditLog.user_email == email).order_by(AuditLog.id)
        ]


def _test_client_address() -> str:
    """The address an audit row records for the test client: the SHA-256 of its host, ``testclient``,
    keyed with SECRET_KEY. Computed here, not by the router's helper, so a raw or unkeyed address
    fails."""
    return hashlib.sha256(f"testclient:{settings.SECRET_KEY}".encode("utf-8")).hexdigest()


@pytest.mark.requires_db
def test_a_password_sign_up_writes_the_register_row(client, mail):
    """/register writes the register row once, under the keyed hash of the address: the row a Google or
    Apple sign-up writes below. The frontend's legalTruth.spec.tsx counts the action as written while
    any module calls log_register, as the callbacks now do, so this pins /register's own row."""
    email, _ = _register(client, mail)
    assert _audit_trail(email) == [("register", str(_user(email).id), None, _test_client_address())]


@pytest.mark.requires_db
@pytest.mark.parametrize("path", ["first-sign-in", "invited-first-sign-in", "returning", "linked"])
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_an_oauth_sign_in_writes_the_register_row_only_when_it_creates_the_account(
    client, monkeypatch, provider, path
):
    """/security says registrations are written to the audit log. A Google or Apple sign-in that
    creates the account writes the register row a password sign-up writes, once, then its
    oauth_login row, both under the hashed address, so the log tells the sign-up from a later
    login: in public mode, and under invite_only with the invite the sign-up started with, the
    only kind the deployed service accepts (docs/CONFIGURATION.md). A returning sign-in writes
    oauth_login alone, and a link to an existing verified account oauth_login and oauth_linked.
    The response is the same on every path."""
    email = _email()
    sub = f"{provider}_{uuid.uuid4().hex}"
    invite = None
    if path == "invited-first-sign-in":
        monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
        with SessionLocal() as db:
            _row, invite, _link = invite_service.mint_invite(db, created_by=None)
    elif path != "first-sign-in":
        user_id = _seed_verified(email)
        if path == "returning":
            _seed_link(user_id, provider, sub, email)

    resp = _oauth_callback(client, monkeypatch, provider, sub, email, invite=invite)
    assert resp.status_code == 302 and resp.headers["location"] == settings.FRONTEND_URL
    assert _cookies(resp) == [_STATE_CLEARED[provider], *SESSION_ISSUED]
    account, address = str(_user(email).id), _test_client_address()
    login = ("oauth_login", account, {"provider": provider}, address)
    assert _audit_trail(email) == {
        "first-sign-in": [("register", account, None, address), login],
        "invited-first-sign-in": [("register", account, None, address), login],
        "returning": [login],
        "linked": [login, ("oauth_linked", account, {"provider": provider}, address)],
    }[path]


@pytest.fixture
def lose_the_new_accounts_link_race():
    """Arm with (email, sub, provider, owner_id): when a first sign-in for ``email`` flushes its new
    account, a competing request first commits the same provider identity for ``owner_id`` (the
    identity's email changed between the two), so the sign-in's commit, where its link is flushed
    with the refresh token, raises IntegrityError and rolls the new account back."""
    armed: dict = {}

    def _before_flush(session, _flush_context, _instances):
        email = armed.get("email")
        if email is None or not any(isinstance(obj, User) and obj.email == email for obj in session.new):
            return
        armed["email"] = None
        with SessionLocal() as other:
            other.add(OAuthAccount(
                user_id=armed["owner_id"], provider=armed["provider"], provider_account_id=armed["sub"],
            ))
            other.commit()

    event.listen(Session, "before_flush", _before_flush)
    yield armed
    event.remove(Session, "before_flush", _before_flush)


@pytest.mark.requires_db
@pytest.mark.parametrize(
    "failure", ["refused-by-the-invite-gate", "account-conflict", "lost-the-create-race", "lost-the-new-link"]
)
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_an_oauth_sign_in_that_creates_no_account_writes_no_register_row(
    client, monkeypatch, request, caplog, provider, failure
):
    """No account comes of these sign-ins, so none writes a register row, nor any other audit row, and
    none sets a session cookie: the invite gate refusing a new account, an existing account that
    cannot be linked, a lost create race, and a new account whose commit loses its link to a
    concurrent sign-in (rolled back with that commit)."""
    email = _email()
    sub = f"{provider}_{uuid.uuid4().hex}"
    error = f"{provider}_account_conflict"
    armed: Optional[dict] = None
    if failure == "refused-by-the-invite-gate":
        monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
        error = "invite_required"
    elif failure == "account-conflict":
        with SessionLocal() as db:
            db.add(User(email=email, hashed_password="x", email_verified=False))
            db.commit()
    elif failure == "lost-the-create-race":
        armed = request.getfixturevalue("lose_the_create_race")
        armed["email"] = email
    else:
        armed = request.getfixturevalue("lose_the_new_accounts_link_race")
        armed.update(email=email, sub=sub, provider=provider, owner_id=_seed_verified(_email()))

    with caplog.at_level(logging.WARNING, logger="app.routers.auth"):
        resp = _oauth_callback(client, monkeypatch, provider, sub, email)
    assert armed is None or armed["email"] is None, "the race was never injected"
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{settings.FRONTEND_URL}/login?error={error}"
    assert _cookies(resp) == ([] if provider == "google" else [APPLE_STATE_CLEARED])
    assert _audit_trail(email) == []
    if failure == "lost-the-new-link":
        # Lost at the sign-in's commit, after the resolve had created the account, which rolled back.
        label = "Google" if provider == "google" else "Apple"
        assert f"{label} OAuth IntegrityError for sub={sub}" in [r.getMessage() for r in caplog.records]
        with SessionLocal() as db:
            assert db.query(User).filter(User.email == email).count() == 0
            assert db.query(OAuthAccount).filter_by(provider_account_id=sub).one().user_id == armed["owner_id"]


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_an_oauth_first_sign_in_whose_session_mint_fails_leaves_no_account_and_no_register_row(
    monkeypatch, server_errors, fail_the_refresh_token_insert, provider
):
    """A first sign-in's new account and link commit with its refresh token, and its audit rows follow
    that commit: when the mint fails, the callback answers 500 with no session and leaves no account,
    no link and no audit row. A register row written before the mint would commit the account, the link
    and itself, all kept behind the 500, whether or not the database enforces the refresh token's
    foreign key (SQLite here does not; PostgreSQL does)."""
    email = _email()
    sub = f"{provider}_{uuid.uuid4().hex}"
    fail_the_refresh_token_insert["on"] = True
    resp = _oauth_callback(server_errors, monkeypatch, provider, sub, email)
    assert fail_the_refresh_token_insert["fired"], "the mint failure was never injected"
    assert resp.status_code == 500 and _cookies(resp) == []
    with SessionLocal() as db:
        assert db.query(User).filter(User.email == email).count() == 0
        assert db.query(OAuthAccount).filter_by(provider_account_id=sub).count() == 0
    assert _audit_trail(email) == []


# ── registration that loses a concurrent create ───────────────────────────────

@pytest.mark.requires_db
def test_a_registration_that_loses_the_create_race_stays_opaque(client, mail, monkeypatch, lose_the_create_race):
    """The insert loses a concurrent create for the same email (IntegrityError at the flush): the
    answer is byte-identical to any other registration (anti-enumeration), only the winner's account
    exists, and neither a verification nor an account-exists mail goes out."""
    account_exists = AsyncMock()
    monkeypatch.setattr("app.services.email_service.send_account_exists_email", account_exists)
    normal = client.post("/api/auth/register", json={"email": _email(), "password": PASSWORD})
    assert normal.status_code == 200, normal.text
    mail.verification.reset_mock()

    email = _email()
    lose_the_create_race["email"] = email
    raced = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert lose_the_create_race["email"] is None, "the race was never injected"
    assert raced.status_code == normal.status_code
    assert raced.content == normal.content
    assert raced.headers["content-type"] == normal.headers["content-type"]
    assert raced.headers.get_list("set-cookie") == normal.headers.get_list("set-cookie") == []
    with SessionLocal() as db:
        assert [u.id for u in db.query(User).filter(User.email == email)] == [lose_the_create_race["winner_id"]]
        assert db.query(AuditLog).filter(AuditLog.user_email == email).count() == 0
    assert mail.verification.call_count == 0 and account_exists.call_count == 0
