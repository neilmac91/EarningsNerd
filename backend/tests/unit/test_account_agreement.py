"""Adult-account assent is required at creation, never invented for existing users.

Exercise real HTTP validation, OAuth state consumption and account transactions against the
suite's private database. Provider verification and outbound side effects are mocked, not the
agreement/readiness decisions. SQLite proves rollback and sequential replay here; overlapping
PostgreSQL state consumers require the separate transaction suite.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.config import settings
from app.database import SessionLocal, engine
from app.models import (
    AccountAgreement,
    AuditLog,
    InviteCode,
    OAuthAccount,
    OAuthState,
    RefreshToken,
    Subscription,
    User,
)
from app.routers import auth as auth_module
from app.services import account_mail_service, auth_account_service, invite_service, oauth_account_service
from app.services.account_agreement_service import AcceptedAccountAgreement, AgreementRequired
from app.services.legal_readiness_service import CollectionUnavailable
from main import app

pytestmark = pytest.mark.requires_db

PASSWORD = "AdultAgreement-test-2026"  # synthetic fixture, not a credential  # gitleaks:allow
VERSION = "2026-10-24"
PROVIDERS = ("google", "apple")
ASSENT = {
    "adult_eligible": True,
    "terms_accepted": True,
    "terms_version": VERSION,
    "eligibility_version": VERSION,
}


@pytest.fixture(scope="module")
def client():
    # Apple's cross-site binding cookie is Secure, so exercise the HTTPS browser behavior.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def setup(client, monkeypatch):
    client.cookies.clear()
    saved_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    for key, value in {
        "REGISTRATION_MODE": "public",
        "GOOGLE_CLIENT_ID": "agreement-test-google",
        "APPLE_CLIENT_ID": "io.earningsnerd.agreement-test",
        "REVERSE_TRIAL_ENABLED": False,
        "LEGAL_COLLECTION_ENABLED": True,
        "LEGAL_OPERATOR_PUBLISHED": True,
        "LEGAL_OPERATOR_NAME": "Synthetic Test Operator",
        "LEGAL_OPERATOR_POSTAL_ADDRESS": "1 Synthetic Test Street",
        "LEGAL_OPERATOR_COUNTRY": "CH",
        "LEGAL_OPERATOR_EMAIL": "privacy@example.com",
    }.items():
        monkeypatch.setattr(settings, key, value)
    auth_module.REGISTER_LIMITER._hits.clear()
    auth_module.OAUTH_START_LIMITER._hits.clear()
    auth_module.LOGIN_LIMITER._hits.clear()
    yield
    client.cookies.clear()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved_overrides)


@pytest.fixture
def effects(monkeypatch):
    spies = SimpleNamespace(
        turnstile=AsyncMock(),
        pwned=AsyncMock(return_value=False),
        hashing=Mock(return_value="synthetic-account-hash"),
        verification=AsyncMock(),
        existing=AsyncMock(),
        linked=AsyncMock(),
        capture=Mock(),
    )
    for name, replacement in {
        "enforce_turnstile": spies.turnstile,
        "is_password_pwned": spies.pwned,
        "get_password_hash": spies.hashing,
        "_send_account_exists_email_safe": spies.existing,
        "_send_oauth_linked_email_safe": spies.linked,
        "capture_event": spies.capture,
    }.items():
        monkeypatch.setattr(auth_module, name, replacement)
    monkeypatch.setattr(account_mail_service, "send_verification_link", spies.verification)
    return spies


def _email():
    return f"agreement-{uuid4().hex}@example.com"


def _registration(address, **overrides):
    return {"email": address, "password": PASSWORD, **ASSENT, **overrides}


def _counts():
    with SessionLocal() as db:
        return {
            model.__tablename__: db.query(model).count()
            for model in (User, AccountAgreement, OAuthAccount, RefreshToken, Subscription, AuditLog)
        }


def _assert_no_session(response):
    assert settings.COOKIE_NAME not in response.cookies
    assert settings.REFRESH_COOKIE_NAME not in response.cookies


def _assert_no_signup_effects(effects):
    effects.verification.assert_not_called()
    effects.existing.assert_not_called()
    effects.linked.assert_not_called()
    effects.capture.assert_not_called()


def _assert_refused(response, code):
    assert response.status_code == 302, response.text
    assert parse_qs(urlparse(response.headers["location"]).query) == {"error": [code]}
    _assert_no_session(response)


def _claims(provider, address):
    return {
        "sub": f"{provider}_{uuid4().hex}",
        "email": address,
        "email_verified": True if provider == "google" else "true",
    }


class _TokenResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"id_token": "synthetic-token"}


class _ProviderClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        return _TokenResponse()


def _start(client, provider, *, assent=True, invite=None):
    body = dict(ASSENT) if assent else {}
    if invite:
        body["invite"] = invite
    response = client.post(f"/api/auth/{provider}/start", json=body)
    assert response.status_code == 200, response.text
    url = response.json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    # Assent and policy versions are not authority-bearing query parameters at the provider.
    assert all(field not in parse_qs(urlparse(url).query) for field in ASSENT)
    return state


def _bind(client, provider, state):
    client.cookies.clear()
    if provider == "google":
        client.cookies.set(auth_module._OAUTH_STATE_COOKIE, state)
    else:
        client.cookies.set(auth_module._APPLE_STATE_COOKIE, auth_module._apple_state_cookie_value(state))


def _callback(client, monkeypatch, provider, claims, state):
    if provider == "google":
        monkeypatch.setattr(auth_module, "httpx", SimpleNamespace(AsyncClient=_ProviderClient))
        monkeypatch.setattr(auth_module, "_verify_google_id_token", AsyncMock(return_value=claims))
        return client.get(
            "/api/auth/google/callback", params={"code": "synthetic-code", "state": state},
            follow_redirects=False,
        )
    monkeypatch.setattr(auth_module, "_verify_apple_id_token", AsyncMock(return_value=claims))
    return client.post(
        "/api/auth/apple/callback", data={"state": state, "id_token": "synthetic-token"},
        follow_redirects=False,
    )


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("start_method", ("get", "post"))
def test_oauth_state_start_and_consume_sql_run_off_event_loop(client, monkeypatch, provider, start_method):
    """Observe actual DB statements, including plain Google login's newly required state write.

    A callback with signed but incomplete claims stops after real state consumption, isolating
    this unit from account resolution. Provider boundaries are mocked; no database unit is.
    """
    observations = []

    def observe(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "oauth_states" not in statement.lower():
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            on_event_loop = False
        else:
            on_event_loop = True
        observations.append((statement.lower(), on_event_loop))

    event.listen(engine, "before_cursor_execute", observe)
    try:
        if start_method == "get":
            response = client.get(f"/api/auth/{provider}", follow_redirects=False)
            assert response.status_code == 302
            state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
        else:
            state = _start(client, provider)
        response = _callback(client, monkeypatch, provider, {}, state)
        assert response.status_code == 302
        assert f"error={provider}_missing_claims" in response.headers["location"]
    finally:
        event.remove(engine, "before_cursor_execute", observe)

    assert any("insert into oauth_states" in sql for sql, _ in observations)
    assert any("delete from oauth_states" in sql and "returning" in sql for sql, _ in observations)
    assert observations and not any(on_loop for _, on_loop in observations), observations


def _seed_user(address, *, provider=None, subject=None):
    with SessionLocal() as db:
        user = User(email=address, hashed_password="legacy-hash", email_verified=True)
        db.add(user)
        db.flush()
        user_id = user.id
        if provider:
            db.add(OAuthAccount(
                user_id=user_id, provider=provider, provider_account_id=subject,
                provider_email=address,
            ))
        db.commit()
        return user_id


INVALID_ASSENT = [
    pytest.param(field, None, True, id=f"missing-{field}") for field in ASSENT
] + [
    pytest.param(field, value, False, id=f"{field}-{value!r}")
    for field in ("adult_eligible", "terms_accepted")
    for value in (False, "true", "false", 1, 0, None)
] + [
    pytest.param(field, "2020-01-01", False, id=f"stale-{field}")
    for field in ("terms_version", "eligibility_version")
]


@pytest.mark.parametrize("field,value,remove", INVALID_ASSENT)
def test_password_invalid_assent_is_rejected_before_any_account_or_provider_effect(
    client, effects, field, value, remove,
):
    body = _registration(_email())
    if remove:
        del body[field]
    else:
        body[field] = value
    before = _counts()
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 422, response.text
    _assert_no_session(response)
    assert _counts() == before
    effects.turnstile.assert_not_called()
    effects.pwned.assert_not_called()
    effects.hashing.assert_not_called()
    _assert_no_signup_effects(effects)


def test_closed_registration_rejects_before_turnstile_breach_check_or_hashing(
    client, monkeypatch, effects,
):
    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)
    before = _counts()
    response = client.post("/api/auth/register", json=_registration(_email()))
    assert response.status_code == 503, response.text
    _assert_no_session(response)
    assert _counts() == before
    effects.turnstile.assert_not_called()
    effects.pwned.assert_not_called()
    effects.hashing.assert_not_called()
    _assert_no_signup_effects(effects)


def test_password_creation_records_current_assent_with_server_time_and_source(client, effects):
    address = _email()
    started = datetime.now(timezone.utc)
    response = client.post("/api/auth/register", json=_registration(
        address, accepted_at="1999-01-01T00:00:00Z", source="google",
    ))
    assert response.status_code == 200, response.text
    _assert_no_session(response)  # verify-first registration still issues no session
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=address).one()
        agreement = db.query(AccountAgreement).filter_by(user_id=user.id).one()
        assert agreement.adult_eligible is True and agreement.terms_accepted is True
        assert (agreement.terms_version, agreement.eligibility_version) == (VERSION, VERSION)
        assert agreement.source == "password"
        accepted = agreement.accepted_at.replace(tzinfo=timezone.utc)
        assert started <= accepted <= datetime.now(timezone.utc)
        assert not user.email_verified
        assert db.query(RefreshToken).filter_by(user_id=user.id).count() == 0
        assert db.query(Subscription).filter_by(user_id=user.id).count() == 0
    effects.verification.assert_awaited_once()


def test_registration_does_not_backfill_assent_on_an_existing_account(client, effects):
    address = _email()
    user_id = _seed_user(address)
    response = client.post("/api/auth/register", json=_registration(address))
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.query(AccountAgreement).filter_by(user_id=user_id).count() == 0
        assert db.get(User, user_id).hashed_password == "legacy-hash"
    effects.existing.assert_awaited_once()
    effects.verification.assert_not_called()
    effects.capture.assert_not_called()


def test_closed_collection_preserves_legacy_password_login_without_new_assent(
    client, monkeypatch, effects,
):
    address = _email()
    user_id = _seed_user(address)
    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)
    monkeypatch.setattr(auth_module, "verify_password", Mock(return_value=True))
    response = client.post("/api/auth/login", json={"email": address, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert settings.COOKIE_NAME in response.cookies
    with SessionLocal() as db:
        assert db.query(AccountAgreement).filter_by(user_id=user_id).count() == 0
        assert db.query(RefreshToken).filter_by(user_id=user_id).count() == 1
    effects.verification.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("field,value,remove", INVALID_ASSENT)
def test_oauth_partial_or_invalid_assent_cannot_be_stored(client, provider, field, value, remove):
    body = dict(ASSENT)
    if remove:
        del body[field]
    else:
        body[field] = value
    with SessionLocal() as db:
        before = db.query(OAuthState).count()
    response = client.post(f"/api/auth/{provider}/start", json=body)
    assert response.status_code == 422, response.text
    assert not response.cookies
    with SessionLocal() as db:
        assert db.query(OAuthState).count() == before


@pytest.mark.parametrize("provider", PROVIDERS)
def test_login_only_oauth_start_cannot_create_an_account(client, monkeypatch, effects, provider):
    state = _start(client, provider, assent=False)
    before = _counts()
    response = _callback(client, monkeypatch, provider, _claims(provider, _email()), state)
    _assert_refused(response, "account_agreement_required")
    assert _counts() == before
    _assert_no_signup_effects(effects)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_query_parameters_cannot_supply_oauth_assent(client, monkeypatch, effects, provider):
    response = client.get(f"/api/auth/{provider}", params=ASSENT, follow_redirects=False)
    assert response.status_code == 302
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    before = _counts()
    callback = _callback(client, monkeypatch, provider, _claims(provider, _email()), state)
    _assert_refused(callback, "account_agreement_required")
    assert _counts() == before


@pytest.mark.parametrize("provider", PROVIDERS)
def test_oauth_stored_assent_creates_one_agreement_and_state_cannot_be_replayed(
    client, monkeypatch, effects, provider,
):
    address = _email()
    claims = _claims(provider, address)
    state = _start(client, provider)
    with SessionLocal() as db:
        stored = db.query(OAuthState).filter_by(state=state).one()
        accepted_at = stored.agreement_accepted_at
        assert stored.agreement_terms_version == VERSION
        assert stored.agreement_eligibility_version == VERSION
        assert accepted_at is not None
    response = _callback(client, monkeypatch, provider, claims, state)
    assert response.status_code == 302
    assert response.headers["location"] == settings.FRONTEND_URL
    assert settings.COOKIE_NAME in response.cookies
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=address).one()
        agreement = db.query(AccountAgreement).filter_by(user_id=user.id).one()
        assert agreement.source == provider
        assert agreement.terms_accepted is True and agreement.adult_eligible is True
        assert (agreement.terms_version, agreement.eligibility_version) == (VERSION, VERSION)
        assert agreement.accepted_at.replace(tzinfo=timezone.utc) == accepted_at.replace(tzinfo=timezone.utc)
        assert db.query(OAuthState).filter_by(state=state).count() == 0
    before_replay = _counts()
    _bind(client, provider, state)  # replay even with the original correct browser cookie
    replay = _callback(client, monkeypatch, provider, claims, state)
    _assert_refused(replay, "oauth_state_mismatch")
    assert _counts() == before_replay


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("invalid", ["expired", "stale_terms", "stale_eligibility"])
def test_oauth_expired_or_stale_stored_assent_creates_nothing(
    client, monkeypatch, effects, provider, invalid,
):
    state = _start(client, provider)
    with SessionLocal() as db:
        stored = db.query(OAuthState).filter_by(state=state).one()
        if invalid == "expired":
            stored.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        elif invalid == "stale_terms":
            stored.agreement_terms_version = "2020-01-01"
        else:
            stored.agreement_eligibility_version = "2020-01-01"
        db.commit()
    before = _counts()
    response = _callback(client, monkeypatch, provider, _claims(provider, _email()), state)
    _assert_refused(response, "oauth_state_mismatch" if invalid == "expired" else "account_agreement_required")
    assert _counts() == before
    _assert_no_signup_effects(effects)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("already_linked", [False, True])
def test_closed_collection_preserves_legacy_oauth_login_and_verified_linking_without_assent(
    client, monkeypatch, effects, provider, already_linked,
):
    address = _email()
    claims = _claims(provider, address)
    user_id = _seed_user(
        address, provider=provider if already_linked else None, subject=claims["sub"],
    )
    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)
    state = _start(client, provider, assent=False)
    response = _callback(client, monkeypatch, provider, claims, state)
    assert response.status_code == 302
    assert response.headers["location"] == settings.FRONTEND_URL
    assert settings.COOKIE_NAME in response.cookies
    with SessionLocal() as db:
        assert db.query(AccountAgreement).filter_by(user_id=user_id).count() == 0
        assert db.query(OAuthAccount).filter_by(user_id=user_id, provider=provider).count() == 1
        assert db.query(RefreshToken).filter_by(user_id=user_id).count() == 1
    effects.verification.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_readiness_is_rechecked_after_oauth_start(client, monkeypatch, effects, provider):
    state = _start(client, provider)
    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)
    before = _counts()
    response = _callback(client, monkeypatch, provider, _claims(provider, _email()), state)
    _assert_refused(response, "registration_unavailable")
    assert _counts() == before
    _assert_no_signup_effects(effects)


@pytest.mark.parametrize("provider", ("password", *PROVIDERS))
def test_lost_invite_redemption_rolls_back_account_and_agreement(
    client, monkeypatch, effects, provider,
):
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    with SessionLocal() as db:
        invite, raw, _ = invite_service.mint_invite(db, created_by=None)
        invite_id = invite.id
    state = _start(client, provider, invite=raw) if provider != "password" else None
    redeem = Mock(return_value=False)
    monkeypatch.setattr(invite_service, "redeem_invite", redeem)
    before = _counts()
    address = _email()
    if provider == "password":
        response = client.post("/api/auth/register", json=_registration(address, invite_code=raw))
        assert response.status_code == 200
        assert response.json() == auth_module._REGISTER_OPAQUE
        _assert_no_session(response)
    else:
        response = _callback(client, monkeypatch, provider, _claims(provider, address), state)
        _assert_refused(response, "invite_required")
    redeem.assert_called_once()
    assert redeem.call_args.kwargs["commit"] is False
    assert _counts() == before
    with SessionLocal() as db:
        assert db.get(InviteCode, invite_id).used_at is None
    _assert_no_signup_effects(effects)


@pytest.mark.parametrize("provider", ("password", *PROVIDERS))
@pytest.mark.parametrize("invalid", ["missing", "stale_terms", "stale_eligibility"])
def test_account_creation_services_refuse_missing_or_stale_agreement_even_without_router(
    provider, invalid,
):
    agreement = None if invalid == "missing" else AcceptedAccountAgreement(
        terms_version="2020-01-01" if invalid == "stale_terms" else VERSION,
        eligibility_version="2020-01-01" if invalid == "stale_eligibility" else VERSION,
        accepted_at=datetime.now(timezone.utc),
    )
    before = _counts()
    with SessionLocal() as db:
        if provider == "password":
            with pytest.raises(AgreementRequired):
                auth_account_service.create_password_account(
                    db, email=_email(), hashed_password="synthetic-hash", full_name=None,
                    invite=None, agreement=agreement,
                )
        else:
            result = oauth_account_service.oauth_create_account(
                db, provider=provider, email=_email(), full_name=None, email_verified=True,
                invite_code_hash=None, agreement=agreement,
            )
            assert result == (None, "account_agreement_required")
        # A future caller must not accidentally commit a partially staged rejected account.
        db.commit()
    assert _counts() == before


@pytest.mark.parametrize("provider", ("password", *PROVIDERS))
def test_account_creation_services_recheck_readiness_even_with_valid_agreement(monkeypatch, provider):
    agreement = AcceptedAccountAgreement(VERSION, VERSION, datetime.now(timezone.utc))
    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)
    before = _counts()
    with SessionLocal() as db:
        if provider == "password":
            with pytest.raises(CollectionUnavailable):
                auth_account_service.create_password_account(
                    db, email=_email(), hashed_password="synthetic-hash", full_name=None,
                    invite=None, agreement=agreement,
                )
        else:
            result = oauth_account_service.oauth_create_account(
                db, provider=provider, email=_email(), full_name=None, email_verified=True,
                invite_code_hash=None, agreement=agreement,
            )
            assert result == (None, "registration_unavailable")
        db.commit()
    assert _counts() == before
