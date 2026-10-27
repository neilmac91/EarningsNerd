"""Regression gate: only a refresh token that was rotated away is a theft signal.

Every refresh rotates the presented token: it is revoked and ``replaced_by_id`` points at its
successor. Presenting a rotated-away token again means two parties hold copies of it, so
``refresh_token_service.rotate_refresh_token`` revokes that token's chain (since E96; below). Logout,
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
gated by ``test_refresh_replay.py`` and ``test_auth_token_flows.py``.

Since E96 the theft path revokes the replayed token's chain alone: the live tokens its rotations lead to, followed
only through links to the same user's newer tokens (``refresh_token_service._live_descendants``). A replay on one
device ends that device's chain and leaves the account's other devices signed in, and a copy rotated away before a
reset no longer ends the login made after it. A link the walk must not follow (to another user, to an older token,
to itself or to no row) refuses the replay and revokes nothing past it. The refresh route also takes a per-IP limit
before any database work, above a burst of tabs, keyed by the trusted client address, and refuses a refresh token
no minting could produce (a lone surrogate) as an unknown one instead of answering 500.
"""
import json
import logging
import uuid
from datetime import timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from tests.support.account_agreement import ACCOUNT_AGREEMENT

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal
from app.models import RefreshToken, User
from app.routers import auth as auth_module
from app.services import refresh_token_service
from tests.support.summary_stream_harness import reset_rate_limiters

pytestmark = pytest.mark.usefixtures("collection_ready")

PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit; test fixture, not a credential  # gitleaks:allow
NEW_PASSWORD = PASSWORD + "9z"  # gitleaks:allow
REFUSED = {"detail": "Your session has ended. Log in again."}


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
    resp = client.post("/api/auth/register", json={**ACCOUNT_AGREEMENT, "email": email, "password": PASSWORD})
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
    theft path, which since E96 ends only that copy's chain: a later test pins that the new login
    survives it (arch-only-a-rotated-refresh-token-signals-theft.md)."""
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
def test_a_copy_rotated_away_before_a_reset_no_longer_ends_the_login_made_after_it(
    laptop, phone, mail, postgres_shaped_reset_expiry
):
    """The residual the lesson recorded, closed by E96. A thief copies the phone's token and never uses it; the
    phone's own silent refresh then rotates it away. After a reset and a new login, replaying the copy is still
    detected as theft and refused, but the sweep now ends the copy's own chain, which the reset already ended, so
    the new login survives. Before E96 the sweep was user-wide and these last two assertions read 0 and 401 (the
    accepted replay-scope change, Neil 2026-10-25)."""
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
    assert _live_tokens(user_id) == 1
    assert laptop.post("/api/auth/refresh").status_code == 200


# ── a replay ends its own chain (E96) ─────────────────────────────────────────────────────────────────────────

@pytest.mark.requires_db
def test_a_replay_on_one_device_ends_that_devices_chain_and_leaves_the_other_signed_in(laptop, phone, mail):
    """Two chains of one account: the phone's and the laptop's. A copy of the laptop's token, replayed after the
    laptop rotated it away, is refused and ends the laptop's chain, its live tip included; the phone's session is
    another chain and still refreshes. Before E96 the sweep revoked every token of the account."""
    email, user_id = _register(laptop)
    _login(phone, email)
    stolen = _login(laptop, email)
    assert laptop.post("/api/auth/refresh").status_code == 200  # the laptop rotates its copy away
    tip = laptop.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert _live_tokens(user_id) == 2

    laptop.cookies.clear()
    replay = laptop.post("/api/auth/refresh", json={"refresh_token": stolen})
    assert replay.status_code == 401 and replay.json() == REFUSED, replay.text
    assert _live_tokens(user_id) == 1  # the phone's

    laptop.cookies.set(settings.REFRESH_COOKIE_NAME, tip)
    assert laptop.post("/api/auth/refresh").status_code == 401  # the laptop's tip went with its chain
    assert phone.post("/api/auth/refresh").status_code == 200


def _chain_user() -> User:
    with SessionLocal() as db:
        user = User(email=f"chain_{uuid.uuid4().hex[:12]}@example.com", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def _minted(user: User) -> tuple[int, str]:
    with SessionLocal() as db:
        token, raw = refresh_token_service.create_refresh_token(db, db.get(User, user.id))
        db.commit()
        return token.id, raw


def _link(token_id: int, replaced_by_id: int) -> None:
    """Write a link no rotation writes: the forms the walk must refuse to follow."""
    with SessionLocal() as db:
        token = db.get(RefreshToken, token_id)
        token.revoked_at, token.replaced_by_id = token.created_at.replace(tzinfo=None), replaced_by_id
        db.commit()


def _live(token_id: int) -> bool:
    with SessionLocal() as db:
        return db.get(RefreshToken, token_id).revoked_at is None


@pytest.mark.requires_db
@pytest.mark.parametrize("form", ["to-another-user", "to-an-older-token", "to-itself", "to-no-row"])
def test_a_replay_over_a_link_no_rotation_writes_revokes_nothing_past_it(form, caplog):
    # Each form is decided by one guard alone (lessons/test-pin-each-guard-where-it-alone-decides.md): the other
    # user's token is newer than the replayed one, so only the same-user guard refuses that link, and the older token
    # is the owner's, so only the increasing-id guard refuses that one.
    owner, other = _chain_user(), _chain_user()
    older_id, _ = _minted(owner)
    replayed_id, raw = _minted(owner)
    others_id, _ = _minted(other)
    target = {"to-another-user": others_id, "to-an-older-token": older_id, "to-itself": replayed_id,
              "to-no-row": replayed_id + 10_000}[form]
    _link(replayed_id, target)

    with caplog.at_level(logging.WARNING, logger="app.services.refresh_token_service"):
        with SessionLocal() as db, pytest.raises(refresh_token_service.RefreshTokenReuseError):
            refresh_token_service.rotate_and_commit(db, raw)
        with SessionLocal() as db:
            assert refresh_token_service.revoke_and_commit(db, raw) is None  # a logout's walk is the same walk
    assert _live(older_id) and _live(others_id)
    unfollowed = [r.getMessage() for r in caplog.records if "did not follow" in r.getMessage()]
    assert unfollowed and all(str(replayed_id) in line and raw not in line for line in unfollowed), unfollowed


@pytest.mark.requires_db
def test_a_refresh_token_no_minting_could_produce_is_refused_as_unknown(laptop):
    """Tokens are URL-safe ASCII; one holding a lone surrogate answered 500 where it was hashed (E97's review)."""
    body = json.dumps({"refresh_token": "tok\ud800"})  # json.dumps escapes it, as a client sends it
    resp = laptop.post("/api/auth/refresh", content=body, headers={"content-type": "application/json"})
    assert resp.status_code == 401 and resp.json() == REFUSED, resp.text


# ── the refresh route's per-IP limit (E96) ───────────────────────────────────────────────────────────────────

def _refresh_from(client: TestClient, forwarded_for: Optional[str] = None):
    headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}
    return client.post("/api/auth/refresh", headers=headers)


def test_a_burst_of_tabs_passes_and_a_loop_is_limited(laptop):
    # The documented cap (E96's pull request records the burst it was set from): 60 a minute per trusted address,
    # per API process.
    assert (auth_module.REFRESH_LIMITER.limit, auth_module.REFRESH_LIMITER.window_seconds) == (60, 60)
    limit = auth_module.REFRESH_LIMITER.limit
    burst = [_refresh_from(laptop).status_code for _ in range(20)]  # twenty tabs waking at once
    assert set(burst) == {401}, burst  # refused as signed out (no cookie), never limited
    for _ in range(limit - 20):
        assert _refresh_from(laptop).status_code == 401
    limited = _refresh_from(laptop)
    assert limited.status_code == 429, limited.text
    assert int(limited.headers["retry-after"]) > 0
    assert limited.json() == {"detail": "Too many session refreshes. Try again in a minute."}


def test_a_forged_forwarded_for_shares_the_real_clients_bucket(laptop, monkeypatch):
    # Cloud Run's front end appends the address it saw as the last entry; with one trusted hop (the deployed value)
    # that entry is the key, so a client rewriting the entries before it stays in its own bucket.
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    limit = auth_module.REFRESH_LIMITER.limit
    for n in range(limit):
        assert _refresh_from(laptop, f"198.51.100.{n % 250}, 203.0.113.7").status_code == 401
    assert _refresh_from(laptop, "192.0.2.1, 203.0.113.7").status_code == 429
    assert _refresh_from(laptop, "203.0.113.8").status_code == 401  # another real client has a bucket of its own
