"""Phase 4: change-password (set/change, OAuth-only path) + profile name edit."""
import uuid
from contextlib import contextmanager

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from main import app
from app.config import settings
from app.database import get_db, SessionLocal
from app.models import User
from app.models.refresh_token import RefreshToken
from app.routers.auth import create_access_token, get_current_user, get_password_hash, verify_password
from app.services import refresh_token_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


OLD_PASSWORD = "OldStr0ngPassw0rd!"  # gitleaks:allow - test fixture, not a credential
SHOWN_ACCOUNT_REFUSED = (
    "This browser is logged in to a different account from the one this page shows, so the password was not changed."
)


def _create_account(*, has_password: bool) -> tuple[int, str]:
    """A verified, active account (OLD_PASSWORD, or social-only with no password); return (id, email)."""
    db = SessionLocal()
    user = User(
        email=f"p4-{uuid.uuid4().hex}@example.com",
        hashed_password=get_password_hash(OLD_PASSWORD) if has_password else None,
        full_name="Original Name",
        email_verified=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    uid, email = user.id, user.email
    db.close()
    return uid, email


def _delete_account(uid: int) -> None:
    db = SessionLocal()
    db.query(User).filter(User.id == uid).delete()
    db.commit()
    db.close()


@contextmanager
def _auth_as(*, has_password: bool):
    """Create a user and authenticate as them. The override fetches the user via the request's own
    get_db session, so endpoint mutations + commit persist (a plain detached stand-in would not)."""
    uid, _ = _create_account(has_password=has_password)

    def _fetch_current_user(db=Depends(get_db)):
        return db.query(User).filter(User.id == uid).first()

    app.dependency_overrides[get_current_user] = _fetch_current_user
    try:
        yield uid
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        _delete_account(uid)


def _reload_hash(uid):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == uid).first().hashed_password
    finally:
        db.close()


def _reload_name(uid):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == uid).first().full_name
    finally:
        db.close()


# --------------------------------------------------------------------------- change password

@pytest.mark.requires_db
def test_change_password_with_correct_current(client):
    with _auth_as(has_password=True) as uid:
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "OldStr0ngPassw0rd!", "new_password": "BrandNewPassw0rd!", "account_id": uid},
        )
        assert resp.status_code == 200
        new_hash = _reload_hash(uid)
        assert new_hash.startswith("$argon2id$")  # a changed password is Argon2id (E97)
        assert verify_password("BrandNewPassw0rd!", new_hash)
        assert not verify_password("OldStr0ngPassw0rd!", new_hash)


@pytest.mark.requires_db
def test_change_password_wrong_current_is_rejected(client):
    with _auth_as(has_password=True) as uid:
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "WrongPassw0rd!!", "new_password": "BrandNewPassw0rd!", "account_id": uid},
        )
        assert resp.status_code == 400
        # Password unchanged.
        assert verify_password("OldStr0ngPassw0rd!", _reload_hash(uid))


@pytest.mark.requires_db
def test_oauth_only_user_can_set_password_without_current(client):
    with _auth_as(has_password=False) as uid:
        assert _reload_hash(uid) is None
        resp = client.post(
            "/api/auth/change-password",
            json={"new_password": "FirstPassw0rd123!", "account_id": uid},
        )
        assert resp.status_code == 200
        assert _reload_hash(uid).startswith("$argon2id$")
        assert verify_password("FirstPassw0rd123!", _reload_hash(uid))


def _live_token_ids(uid):
    db = SessionLocal()
    try:
        return sorted(
            t.id for t in db.query(RefreshToken).filter(RefreshToken.user_id == uid, RefreshToken.revoked_at.is_(None))
        )
    finally:
        db.close()


def _mint_session(uid):
    """A live refresh token for ``uid``: a session the refused change must leave alone."""
    db = SessionLocal()
    try:
        refresh_token_service.mint_refresh_token(db, db.query(User).filter(User.id == uid).first())
    finally:
        db.close()


@pytest.mark.requires_db
@pytest.mark.parametrize("has_password", [True, False], ids=["password_account", "oauth_only_account"])
def test_change_password_naming_another_account_changes_nothing(client, monkeypatch, has_password):
    """E29 (6): a tab left showing account A by another tab's sign-in posts with the cookies of the account the browser
    holds. Naming A, the request is refused with 409 for the browser's account before anything else runs: no attempt
    counts against the account's limit, no current password is checked, no breach check runs, no hash is made, and no
    session is revoked or issued; for an account without a password, which the route asks for no current password, as
    for one with. The reader of a stale tab types the password of the account it shows, which is wrong for this one:
    a refusal that came after the password check would answer 400, not 409."""
    from app.routers import auth

    reached: list[str] = []

    def recorded(name, original):
        def call(*args, **kwargs):
            reached.append(name)
            return original(*args, **kwargs)
        return call

    async def pwned(password):
        reached.append("is_password_pwned")
        return False

    monkeypatch.setattr(auth, "enforce_rate_limit", recorded("enforce_rate_limit", auth.enforce_rate_limit))
    monkeypatch.setattr(auth, "verify_password", recorded("verify_password", auth.verify_password))
    monkeypatch.setattr(auth, "get_password_hash", recorded("get_password_hash", auth.get_password_hash))
    monkeypatch.setattr(auth, "is_password_pwned", pwned)
    shown, _ = _create_account(has_password=True)  # the account the stale tab shows: a real one, not a made-up id
    try:
        with _auth_as(has_password=has_password) as uid:
            _mint_session(uid)
            _mint_session(shown)
            before = {account: (_reload_hash(account), _live_token_ids(account)) for account in (uid, shown)}
            assert [len(sessions) for _, sessions in before.values()] == [1, 1]

            resp = client.post(
                "/api/auth/change-password",
                json={
                    "current_password": "TheShownAccountsPassw0rd!" if has_password else None,
                    "new_password": "BrandNewPassw0rd!",
                    "account_id": shown,
                },
            )

            assert resp.status_code == 409, resp.text
            assert resp.json()["detail"] == SHOWN_ACCOUNT_REFUSED
            assert reached == []
            assert {account: (_reload_hash(account), _live_token_ids(account)) for account in (uid, shown)} == before
            assert "earningsnerd_refresh_token" not in resp.cookies
    finally:
        _delete_account(shown)


@pytest.mark.requires_db
@pytest.mark.parametrize("has_password", [True, False], ids=["password_account", "oauth_only_account"])
def test_change_password_naming_its_own_account_changes_it(client, has_password):
    """The tab that shows the browser's account names it and the change goes through as without the field."""
    with _auth_as(has_password=has_password) as uid:
        resp = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "OldStr0ngPassw0rd!" if has_password else None,
                "new_password": "BrandNewPassw0rd!",
                "account_id": uid,
            },
        )
        assert resp.status_code == 200, resp.text
        assert verify_password("BrandNewPassw0rd!", _reload_hash(uid))


_OMITTED = object()


@pytest.mark.requires_db
@pytest.mark.parametrize("has_password", [True, False], ids=["password_account", "oauth_only_account"])
# Missing and null name no account; the rest are values a lax int would coerce to one (7, 1 and 7).
@pytest.mark.parametrize(
    "account_id", [_OMITTED, None, "7", True, 7.0], ids=["missing", "null", "string", "boolean", "whole_float"]
)
def test_change_password_requires_the_shown_account(client, has_password, account_id):
    """The request must name the account its tab shows, strictly (StrictInt, as the logout of every session names it;
    required since the founder's rule 6 approval): a request without it, with null, or with a value a lax int would
    coerce is refused with 422 for that field before the route runs, so no password is set or changed and no session
    is revoked or issued. A page loaded before the field was required omits it and must reload."""
    with _auth_as(has_password=has_password) as uid:
        _mint_session(uid)
        before_hash, before_sessions = _reload_hash(uid), _live_token_ids(uid)
        assert len(before_sessions) == 1
        body = {"current_password": OLD_PASSWORD if has_password else None, "new_password": "BrandNewPassw0rd!"}
        if account_id is not _OMITTED:
            body["account_id"] = account_id

        resp = client.post("/api/auth/change-password", json=body)

        assert resp.status_code == 422, resp.text
        assert [error["loc"] for error in resp.json()["detail"]] == [["body", "account_id"]]
        assert _reload_hash(uid) == before_hash
        assert _live_token_ids(uid) == before_sessions
        assert "earningsnerd_refresh_token" not in resp.cookies


@pytest.mark.requires_db
def test_change_password_from_another_accounts_browser_changes_neither_account(client):
    """E29 (6), through two real browsers and no auth override: P has a password and signs in with it; S is
    social-only and holds the session cookies the app's own code mints for it. Each browser's change naming the
    other's account (S's without a current password, as a social-only account sends) is refused with 409: neither
    hash changes, neither account's live sessions change, and neither answer sets a session cookie."""
    assert get_current_user not in app.dependency_overrides
    password_id, password_email = _create_account(has_password=True)
    social_id, social_email = _create_account(has_password=False)
    try:
        with TestClient(app) as password_browser, TestClient(app) as social_browser:
            login = password_browser.post("/api/auth/login", json={"email": password_email, "password": OLD_PASSWORD})
            assert login.status_code == 200, login.text
            db = SessionLocal()
            try:
                social_refresh = refresh_token_service.mint_refresh_token(
                    db, db.query(User).filter(User.id == social_id).one()
                )
            finally:
                db.close()
            social_browser.cookies.set(settings.COOKIE_NAME, create_access_token(data={"sub": social_email}))
            social_browser.cookies.set(settings.REFRESH_COOKIE_NAME, social_refresh)
            for browser, account_id in ((password_browser, password_id), (social_browser, social_id)):
                me = browser.get("/api/auth/me")
                assert me.status_code == 200 and me.json()["id"] == account_id, me.text
            before = {account: _live_token_ids(account) for account in (password_id, social_id)}
            assert [len(sessions) for sessions in before.values()] == [1, 1]

            from_password = password_browser.post(
                "/api/auth/change-password",
                json={"current_password": OLD_PASSWORD, "new_password": "BrandNewPassw0rd!", "account_id": social_id},
            )
            from_social = social_browser.post(
                "/api/auth/change-password", json={"new_password": "BrandNewPassw0rd!", "account_id": password_id},
            )

            # Both directions read together, so a failure shows each browser's answer.
            assert [
                (resp.status_code, resp.json().get("detail"),
                 settings.COOKIE_NAME in resp.cookies or settings.REFRESH_COOKIE_NAME in resp.cookies)
                for resp in (from_password, from_social)
            ] == [(409, SHOWN_ACCOUNT_REFUSED, False)] * 2
            assert verify_password(OLD_PASSWORD, _reload_hash(password_id))
            assert _reload_hash(social_id) is None
            assert {account: _live_token_ids(account) for account in (password_id, social_id)} == before
    finally:
        _delete_account(password_id)
        _delete_account(social_id)


@pytest.mark.requires_db
def test_weak_new_password_is_rejected(client):
    with _auth_as(has_password=True) as uid:
        resp = client.post(
            "/api/auth/change-password",
            json={"current_password": "OldStr0ngPassw0rd!", "new_password": "short", "account_id": uid},
        )
        assert resp.status_code == 422  # fails the strength validator
        assert [error["loc"] for error in resp.json()["detail"]] == [["body", "new_password"]]


# --------------------------------------------------------------------------- profile name

@pytest.mark.requires_db
def test_update_profile_name(client):
    with _auth_as(has_password=True) as uid:
        resp = client.patch("/api/users/me", json={"full_name": "  New Name  "})
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "New Name"  # trimmed
        assert _reload_name(uid) == "New Name"


@pytest.mark.requires_db
def test_clear_profile_name(client):
    with _auth_as(has_password=True) as uid:
        resp = client.patch("/api/users/me", json={"full_name": ""})
        assert resp.status_code == 200
        assert resp.json()["full_name"] is None
        assert _reload_name(uid) is None


@pytest.mark.requires_db
def test_update_profile_name_of_a_user_another_session_loaded(client):
    # The edit writes through the row the request's own session reads, so it is saved even when the
    # user the auth dependency hands over was loaded, and detached, by another session.
    with _auth_as(has_password=True) as uid:
        db = SessionLocal()
        detached = db.query(User).filter(User.id == uid).first()
        db.close()
        app.dependency_overrides[get_current_user] = lambda: detached
        resp = client.patch("/api/users/me", json={"full_name": "Elsewhere"})
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Elsewhere"
        assert _reload_name(uid) == "Elsewhere"


@pytest.mark.requires_db
def test_empty_profile_patch_keeps_name(client):
    # Only the fields the client sent are applied: leaving full_name out must not clear it.
    with _auth_as(has_password=True) as uid:
        resp = client.patch("/api/users/me", json={})
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Original Name"
        assert _reload_name(uid) == "Original Name"
