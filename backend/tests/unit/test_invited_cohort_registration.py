"""Invited-cohort registration (EN-BETA PB-01): an admission exception, default off, while collection is held.

Through the real readiness service, admin, register, OAuth start and callback routes, account services and sender
(only the providers' token checks and the mail transport are stood in for), with collection held throughout unless a
case says otherwise. The cases pin what docs/LEGAL_READINESS.md ("Invited-cohort registration") promises:

- the exception is in effect only under invite_only, with its switch on and a cohort an invitation can carry, and it
  admits only an invitation bound to its recipient's address whose stored cohort is exactly the configured one;
- every creation path decides for itself, when it acts: the admin's mint and re-send before anything is written or
  revoked, the sender at the send, password registration at the route and again at the account service, whose guarded
  redemption decides on the invitation's row, and a social sign-up at its start and again at its callback;
- a disabled, unset or misset cohort, an invitation outside it (another cohort, unbound, bound elsewhere) and an
  expired, revoked or used one admit nothing and write nothing; an exception closed or changed mid-request admits
  nothing either, a social sign-in's included;
- generic registration, the waitlist, the contact form, promotion, checkout and the public readiness answer stay
  closed, and no answer names the cohort; with collection open the general path is unchanged.

Every value here is synthetic.
"""
from __future__ import annotations

import base64
import uuid
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.config import settings
from app.database import SessionLocal, engine
from app.models import AccountAgreement, InviteCode, OAuthState, User
from app.routers import admin as admin_module
from app.routers import auth as auth_module
from app.routers.auth import create_access_token
from app.services import (
    auth_account_service,
    email_service,
    invite_delivery_service,
    invite_service,
    legal_readiness_service,
    oauth_account_service,
)
from app.services.account_agreement_service import accept_current_agreement
from app.services.legal_readiness_service import COLLECTION_UNAVAILABLE_MESSAGE, CollectionUnavailable
from app.utils.datetimes import utcnow
from main import app
from tests.support.account_agreement import ACCOUNT_AGREEMENT

pytestmark = pytest.mark.requires_db

COHORT = "cohort-synthetic-7f3a9c"
OTHER_COHORT = "cohort-synthetic-0b4e1d"
# Built, not written out, so the secret scan reads no credential in this file (as test_invite_mail_controls.py does).
TESTER_PASSWORD = "-".join(("Cohort", "Tester", "2026", "Ok"))
# A Svix signing secret is base64 after "whsec_"; built from a synthetic phrase, as test_invite_mail_controls.py's is.
WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"pb-01 synthetic cohort webhook key").decode()
REFUSED_INVITE = {"detail": "A valid invite is required to register."}
CLOSED = {"detail": COLLECTION_UNAVAILABLE_MESSAGE}
OPAQUE = {"message": "Check your email for a link to finish setting up your account."}
PROVIDERS = ("google", "apple")


@pytest.fixture(scope="module")
def client():
    # HTTPS base: the Apple binding cookie is Secure (as in test_oauth_invite_gate.py).
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client, monkeypatch):
    client.cookies.clear()
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "io.earningsnerd.test")
    auth_module.REGISTER_LIMITER._hits.clear()
    auth_module.OAUTH_START_LIMITER._hits.clear()
    yield
    client.cookies.clear()
    auth_module.REGISTER_LIMITER._hits.clear()
    auth_module.OAUTH_START_LIMITER._hits.clear()


@pytest.fixture
def cohort_open(monkeypatch):
    """The exception open; collection held, as the conftest leaves it."""
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", True)
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT", COHORT)
    assert not legal_readiness_service.is_collection_available()
    assert legal_readiness_service.is_invited_cohort_available()


@pytest.fixture
def admin():
    address = f"cohort-admin-{uuid.uuid4().hex}@example.com"
    with SessionLocal() as db:
        db.add(User(email=address, is_admin=True, email_verified=True))
        db.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': address})}"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _address() -> str:
    return f"cohort-tester-{uuid.uuid4().hex[:12]}@example.com"


def _mint(email: str | None, cohort: str | None = COHORT, *, state: str = "pending") -> tuple[int, str]:
    """An invitation minted directly (as one made while collection was open could be), in the state asked for."""
    with SessionLocal() as db:
        invite, raw, _link = invite_service.mint_invite(db, created_by=None, email=email, cohort=cohort)
        if state == "expired":
            invite.expires_at = utcnow() - timedelta(minutes=5)
        elif state == "revoked":
            invite.is_revoked = True
        elif state == "used":
            invite.used_at = utcnow()
        db.commit()
        return invite.id, raw


def _invite(invite_id: int) -> InviteCode:
    with SessionLocal() as db:
        return db.query(InviteCode).filter(InviteCode.id == invite_id).one()


def _invite_count() -> int:
    with SessionLocal() as db:
        return db.query(InviteCode).count()


def _user(email: str) -> User | None:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).first()


def _register(client, email: str, invite: str | None):
    body = {**ACCOUNT_AGREEMENT, "email": email, "password": TESTER_PASSWORD}
    if invite is not None:
        body["invite_code"] = invite
    return client.post("/api/auth/register", json=body)


def _refused_invite(case: str) -> tuple[str, str, int]:
    """(registering address, raw token, invite id) for an invitation the exception refuses, by case."""
    email = _address()
    if case == "unknown":
        return email, "not-a-minted-token", 0
    minted = {
        "other_cohort": dict(email=email, cohort=OTHER_COHORT),
        "no_cohort": dict(email=email, cohort=None),
        "cohort_case_differs": dict(email=email, cohort=COHORT.upper()),
        "unbound": dict(email=None, cohort=COHORT),
        "bound_elsewhere": dict(email=_address(), cohort=COHORT),
        "expired": dict(email=email, cohort=COHORT, state="expired"),
        "revoked": dict(email=email, cohort=COHORT, state="revoked"),
        "used": dict(email=email, cohort=COHORT, state="used"),
    }[case]
    invite_id, raw = _mint(**minted)
    return email, raw, invite_id


REFUSED_CASES = (
    "other_cohort", "no_cohort", "cohort_case_differs", "unbound", "bound_elsewhere", "expired", "revoked", "used",
    "unknown",
)
# A start knows no address yet, so an invitation bound to another one is the callback's to refuse (a case below).
START_REFUSED_CASES = ("no_invite", *(case for case in REFUSED_CASES if case != "bound_elsewhere"))


class _FakeTokenResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"id_token": "stub"}


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient in the Google code exchange."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, *args, **kwargs) -> _FakeTokenResponse:
        return _FakeTokenResponse()


def _start(client, provider: str, invite: str | None):
    body = {**ACCOUNT_AGREEMENT}
    if invite is not None:
        body["invite"] = invite
    return client.post(f"/api/auth/{provider}/start", json=body)


def _state(resp) -> str:
    assert resp.status_code == 200, resp.text
    return parse_qs(urlparse(resp.json()["url"]).query)["state"][0]


def _claims(provider: str, email: str) -> dict:
    if provider == "google":
        return {"sub": f"google_{uuid.uuid4().hex}", "email": email, "email_verified": True}
    return {"sub": f"apple_{uuid.uuid4().hex}", "email": email, "email_verified": "true"}


def _callback(client, monkeypatch, provider: str, claims: dict, state: str):
    if provider == "google":
        monkeypatch.setattr(auth_module, "httpx", SimpleNamespace(AsyncClient=_FakeAsyncClient))
        monkeypatch.setattr(auth_module, "_verify_google_id_token", AsyncMock(return_value=claims))
        return client.get("/api/auth/google/callback", params={"code": "code", "state": state}, follow_redirects=False)
    monkeypatch.setattr(auth_module, "_verify_apple_id_token", AsyncMock(return_value=claims))
    return client.post("/api/auth/apple/callback", data={"state": state, "id_token": "stub"}, follow_redirects=False)


def _error_of(resp) -> str | None:
    assert resp.status_code == 302, resp.text
    return parse_qs(urlparse(resp.headers["location"]).query).get("error", [None])[0]


def _state_count() -> int:
    with SessionLocal() as db:
        return db.query(OAuthState).count()


# ── readiness ─────────────────────────────────────────────────────────────────

def test_the_exception_is_held_by_default_and_names_each_condition(monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    assert legal_readiness_service.invited_cohort_readiness() == {
        "available": False,
        "reasons": ["registration_not_invite_only", "invited_cohort_disabled", "invited_cohort_unset"],
    }
    assert legal_readiness_service.invited_cohort() is None


@pytest.mark.parametrize("setting, value, reason", [
    ("REGISTRATION_MODE", "public", "registration_not_invite_only"),
    ("LEGAL_INVITED_COHORT_ENABLED", False, "invited_cohort_disabled"),
    ("LEGAL_INVITED_COHORT", "", "invited_cohort_unset"),
    ("LEGAL_INVITED_COHORT", f"{COHORT}\n", "invited_cohort_unset"),   # a secret store's trailing newline
    ("LEGAL_INVITED_COHORT", f" {COHORT}", "invited_cohort_unset"),
    ("LEGAL_INVITED_COHORT", "cohort\x07synthetic", "invited_cohort_unset"),
    ("LEGAL_INVITED_COHORT", "c" * 65, "invited_cohort_unset"),        # wider than InviteCode.cohort
])
def test_each_condition_holds_the_exception_alone(cohort_open, monkeypatch, setting, value, reason):
    monkeypatch.setattr(settings, setting, value)
    assert legal_readiness_service.invited_cohort_readiness() == {"available": False, "reasons": [reason]}
    assert legal_readiness_service.invited_cohort() is None
    assert legal_readiness_service.admits_invite(COHORT, _address()) is False


def test_an_open_exception_admits_only_an_invitation_bound_and_in_its_cohort_exactly(cohort_open, monkeypatch):
    # The widest cohort an invitation can carry is accepted (the column's 64 characters).
    assert legal_readiness_service.invited_cohort_readiness() == {"available": True, "reasons": []}
    assert legal_readiness_service.admits_invite(COHORT, "a@example.com") is True
    for cohort, email in ((COHORT, None), (COHORT, ""), (OTHER_COHORT, "a@example.com"), (None, "a@example.com"),
                          (COHORT.upper(), "a@example.com"), (f"{COHORT} ", "a@example.com")):
        assert legal_readiness_service.admits_invite(cohort, email) is False, (cohort, email)
    wide = "c" * 64
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT", wide)
    assert legal_readiness_service.admits_invite(wide, "a@example.com") is True


def test_collection_admits_any_invitation_as_before(cohort_open, collection_ready):
    for cohort, email in ((None, None), (OTHER_COHORT, None), (OTHER_COHORT, "a@example.com")):
        assert legal_readiness_service.admits_invite(cohort, email) is True
    assert legal_readiness_service.require_account_admission(invited=False) is None
    assert legal_readiness_service.require_account_admission(invited=True) is None


def test_the_account_boundary_admits_an_invited_account_alone_under_the_exception(cohort_open, monkeypatch):
    assert legal_readiness_service.require_account_admission(invited=True) == COHORT
    with pytest.raises(CollectionUnavailable):
        legal_readiness_service.require_account_admission(invited=False)
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
    with pytest.raises(CollectionUnavailable):
        legal_readiness_service.require_account_admission(invited=True)


def test_invitation_email_waits_for_a_redeemable_link_not_for_collection(cohort_open, monkeypatch):
    assert "collection_unavailable" not in legal_readiness_service.invitation_email_readiness()["reasons"]
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
    assert "collection_unavailable" in legal_readiness_service.invitation_email_readiness()["reasons"]


# ── what stays closed ─────────────────────────────────────────────────────────

def test_generic_registration_meets_the_closure_it_always_met(client, cohort_open, monkeypatch):
    email = _address()
    opened = _register(client, email, None)
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
    held = _register(client, _address(), None)
    assert (opened.status_code, opened.json()) == (held.status_code, held.json()) == (503, CLOSED)
    assert _user(email) is None


def test_the_exception_opens_no_other_collection_and_names_no_cohort(client, cohort_open):
    waitlist = client.post("/api/waitlist/join", json={"email": _address(), "name": "Synthetic Tester"})
    contact = client.post("/api/contact/", json={
        "name": "Synthetic Tester", "email": _address(), "message": "A synthetic message, long enough.",
    })
    readiness = client.get("/api/legal/readiness")
    registration = client.get("/api/auth/registration")

    assert (waitlist.status_code, waitlist.json()) == (503, CLOSED)
    assert (contact.status_code, contact.json()) == (503, CLOSED)
    assert readiness.json()["collection_available"] is False
    assert readiness.json()["checkout_available"] is False and readiness.json()["marketing_available"] is False
    assert readiness.json()["operator"] is None
    assert registration.json()["invited_cohort_available"] is True
    assert legal_readiness_service.is_marketing_available() is False
    assert legal_readiness_service.is_checkout_available() is False
    for answer in (waitlist, contact, readiness, registration):
        assert COHORT not in answer.text


# ── password registration ─────────────────────────────────────────────────────

def test_an_invitation_in_the_cohort_opens_an_account_while_collection_is_held(client, cohort_open):
    email = _address()
    invite_id, raw = _mint(email)

    resp = _register(client, email, raw)

    assert (resp.status_code, resp.json()) == (200, OPAQUE)
    user = _user(email)
    assert user is not None and user.is_beta is True and user.email_verified is False
    invite = _invite(invite_id)
    assert invite.used_at is not None and invite.user_id == user.id
    with SessionLocal() as db:
        agreement = db.query(AccountAgreement).filter(AccountAgreement.user_id == user.id).one()
    assert (agreement.adult_eligible, agreement.terms_accepted, agreement.source) == (True, True, "password")


@pytest.mark.parametrize("case", REFUSED_CASES)
def test_an_invitation_the_exception_does_not_admit_is_refused_and_writes_nothing(client, cohort_open, case):
    email, raw, invite_id = _refused_invite(case)
    before = _invite(invite_id) if invite_id else None

    resp = _register(client, email, raw)

    assert (resp.status_code, resp.json()) == (403, REFUSED_INVITE)
    assert _user(email) is None
    if before is not None:
        after = _invite(invite_id)
        assert (after.used_at, after.user_id, after.is_revoked) == (before.used_at, before.user_id, before.is_revoked)


@pytest.mark.parametrize("setting, value", [
    ("LEGAL_INVITED_COHORT_ENABLED", False), ("LEGAL_INVITED_COHORT", ""), ("REGISTRATION_MODE", "public"),
])
def test_with_the_exception_held_a_cohort_invitation_meets_the_closure(client, cohort_open, monkeypatch, setting, value):
    email = _address()
    invite_id, raw = _mint(email)
    monkeypatch.setattr(settings, setting, value)

    resp = _register(client, email, raw)

    assert (resp.status_code, resp.json()) == (503, CLOSED)
    assert _user(email) is None and _invite(invite_id).used_at is None


def test_an_exception_closed_after_the_routes_check_admits_no_account(client, cohort_open, monkeypatch):
    # The account service decides again: the switch goes off during the breached-password check, after the route's
    # check and the invite's read.
    email = _address()
    invite_id, raw = _mint(email)

    async def close_then_pass(_password):
        monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
        return False

    monkeypatch.setattr(auth_module, "is_password_pwned", close_then_pass)
    resp = _register(client, email, raw)

    assert (resp.status_code, resp.json()) == (503, CLOSED)
    assert _user(email) is None and _invite(invite_id).used_at is None


def test_a_cohort_changed_after_the_routes_check_is_refused_by_the_redemption_itself(client, cohort_open, monkeypatch):
    # The exception stays open with another cohort, so only the redemption's guard, on the invitation's row, can refuse
    # it: the route's check passed on the cohort it read, and the account service admits an invited account.
    email = _address()
    invite_id, raw = _mint(email)

    async def change_then_pass(_password):
        monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT", OTHER_COHORT)
        return False

    monkeypatch.setattr(auth_module, "is_password_pwned", change_then_pass)
    resp = _register(client, email, raw)

    assert (resp.status_code, resp.json()) == (200, OPAQUE)  # a refused redemption stays opaque, as a lost race does
    assert _user(email) is None and _invite(invite_id).used_at is None


def test_collection_open_keeps_the_general_path_for_any_invitation(client, cohort_open, collection_ready):
    email = _address()
    invite_id, raw = _mint(None, None)  # unbound, no cohort: admitted by collection as before the exception

    resp = _register(client, email, raw)

    assert (resp.status_code, resp.json()) == (200, OPAQUE)
    assert _user(email) is not None and _invite(invite_id).used_at is not None


# ── the account service, called directly ─────────────────────────────────────

def _detached(invite_id: int) -> InviteCode:
    """The invitation as register's first unit leaves it: read, then released with the session."""
    with SessionLocal() as db:
        invite = db.query(InviteCode).filter(InviteCode.id == invite_id).one()
        db.expunge(invite)
        return invite


def _create(email: str, invite: InviteCode | None):
    with SessionLocal() as db:
        return auth_account_service.create_password_account(
            db, email=email, hashed_password="synthetic-hash", full_name=None, invite=invite,
            agreement=accept_current_agreement(),
        )


def test_the_account_service_refuses_an_uninvited_account_under_the_exception(cohort_open):
    email = _address()
    with pytest.raises(CollectionUnavailable):
        _create(email, None)
    assert _user(email) is None


@pytest.mark.parametrize("bound_to_another, cohort", [(True, COHORT), (False, OTHER_COHORT), (False, None)])
def test_the_account_service_decides_on_the_row_whatever_its_caller_read(cohort_open, bound_to_another, cohort):
    # A caller that skips the route's checks hands over an invitation outside the exception: the guarded redemption
    # refuses it on the row, and the account rolls back with it.
    email = _address()
    invite_id, _raw = _mint(_address() if bound_to_another else email, cohort)

    assert _create(email, _detached(invite_id)) is None
    assert _user(email) is None and _invite(invite_id).used_at is None


def test_the_account_service_refuses_once_the_exception_closes(cohort_open, monkeypatch):
    email = _address()
    invite_id, _raw = _mint(email)
    invite = _detached(invite_id)
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)

    with pytest.raises(CollectionUnavailable):
        _create(email, invite)
    assert _user(email) is None and _invite(invite_id).used_at is None


def test_the_account_service_admits_the_invitation_the_exception_names(cohort_open):
    email = _address()
    invite_id, _raw = _mint(email)

    user = _create(email, _detached(invite_id))

    assert user is not None and user.is_beta is True
    assert _invite(invite_id).used_at is not None


# ── Google and Apple ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("provider", PROVIDERS)
def test_an_invited_social_sign_up_in_the_cohort_opens_an_account(client, cohort_open, monkeypatch, provider):
    email = _address()
    invite_id, raw = _mint(email)
    state = _state(_start(client, provider, raw))
    with SessionLocal() as db:
        (row,) = db.query(OAuthState).filter(OAuthState.state == state).all()
    assert row.invite_code_hash == invite_service.hash_invite_token(raw)

    resp = _callback(client, monkeypatch, provider, _claims(provider, email), state)

    assert _error_of(resp) is None and resp.headers["location"] == settings.FRONTEND_URL
    user = _user(email)
    assert user is not None and user.is_beta is True
    assert _invite(invite_id).used_at is not None and _invite(invite_id).user_id == user.id


@pytest.mark.parametrize("case", START_REFUSED_CASES)
@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_sign_up_start_the_exception_does_not_admit_is_refused_before_any_state(client, cohort_open, provider, case):
    raw = None if case == "no_invite" else _refused_invite(case)[1]
    before = _state_count()

    resp = _start(client, provider, raw)

    assert (resp.status_code, resp.json()) == (503, CLOSED)
    assert _state_count() == before
    assert not resp.cookies


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_login_start_is_unchanged_by_the_exception(client, cohort_open, provider):
    resp = client.post(f"/api/auth/{provider}/start", json={})
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_social_sign_up_whose_verified_address_is_not_the_bound_one_is_refused(client, cohort_open, monkeypatch,
                                                                                 provider):
    bound, other = _address(), _address()
    invite_id, raw = _mint(bound)
    state = _state(_start(client, provider, raw))

    resp = _callback(client, monkeypatch, provider, _claims(provider, other), state)

    assert _error_of(resp) == "invite_required"
    assert _user(other) is None and _user(bound) is None and _invite(invite_id).used_at is None


@pytest.mark.parametrize("closure, setting, value", [
    ("registration_unavailable", "LEGAL_INVITED_COHORT_ENABLED", False),
    ("registration_unavailable", "REGISTRATION_MODE", "public"),
    ("invite_required", "LEGAL_INVITED_COHORT", OTHER_COHORT),
])
@pytest.mark.parametrize("provider", PROVIDERS)
def test_an_exception_closed_during_a_social_sign_up_admits_no_account(client, cohort_open, monkeypatch, provider,
                                                                       closure, setting, value):
    email = _address()
    invite_id, raw = _mint(email)
    state = _state(_start(client, provider, raw))
    monkeypatch.setattr(settings, setting, value)

    resp = _callback(client, monkeypatch, provider, _claims(provider, email), state)

    assert _error_of(resp) == closure
    assert f"{settings.COOKIE_NAME}=" not in resp.headers.get("set-cookie", "")
    assert _user(email) is None and _invite(invite_id).used_at is None


@contextmanager
def _user_inserts():
    """Every INSERT INTO users the app's engine sends while the block runs."""
    inserts: list[str] = []

    def spy(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("INSERT INTO USERS"):
            inserts.append(statement)

    event.listen(engine, "before_cursor_execute", spy)
    try:
        yield inserts
    finally:
        event.remove(engine, "before_cursor_execute", spy)


@pytest.mark.parametrize("cohort, error", [(COHORT, None), (OTHER_COHORT, "invite_required")],
                         ids=["admitted-inserts-once", "outside-inserts-nothing"])
def test_the_callback_gate_refuses_an_invitation_outside_the_cohort_before_any_insert(client, cohort_open, monkeypatch,
                                                                                     cohort, error):
    # The gate decides before the account's insert; the redemption's guard (below) would refuse it too, after one. The
    # admitted case shows the spy sees the insert a sign-up makes.
    email = _address()
    invite_id, raw = _mint(email)
    state = _state(_start(client, "google", raw))
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT", cohort)

    with _user_inserts() as inserts:
        resp = _callback(client, monkeypatch, "google", _claims("google", email), state)

    assert _error_of(resp) == error
    assert len(inserts) == (1 if error is None else 0)
    assert (_user(email) is not None) is (error is None)
    assert (_invite(invite_id).used_at is not None) is (error is None)


def test_the_social_redemption_decides_on_the_row_too(cohort_open, monkeypatch):
    # The callback's gate refuses such an invitation first; with the gate answering as if it had admitted it, the
    # redemption's guard alone refuses it, and the new account rolls back.
    email = _address()
    invite_id, raw = _mint(email, OTHER_COHORT)
    with SessionLocal() as db:
        invite = db.query(InviteCode).filter(InviteCode.id == invite_id).one()
        db.expunge(invite)
    monkeypatch.setattr(oauth_account_service, "oauth_new_account_gate", lambda *args, **kwargs: (None, invite, COHORT))

    with SessionLocal() as db:
        user, error = oauth_account_service.oauth_create_account(
            db, provider="google", email=email, full_name=None, email_verified=True,
            invite_code_hash=invite_service.hash_invite_token(raw), agreement=accept_current_agreement(),
        )
        db.rollback()

    assert (user, error) == (None, "invite_required")
    assert _user(email) is None and _invite(invite_id).used_at is None


# ── the admin's invitations ───────────────────────────────────────────────────

def test_admin_readiness_names_the_exception_by_its_conditions_never_its_cohort(client, admin, cohort_open,
                                                                               monkeypatch):
    opened = client.get("/api/admin/invites/readiness", headers=admin)
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
    held = client.get("/api/admin/invites/readiness", headers=admin)

    assert opened.status_code == 200, opened.text
    assert opened.json()["collection"]["available"] is False
    assert opened.json()["invited_cohort"] == {"available": True, "reasons": []}
    assert "collection_unavailable" not in opened.json()["invitation_email"]["reasons"]
    assert held.json()["invited_cohort"] == {"available": False, "reasons": ["invited_cohort_disabled"]}
    assert "collection_unavailable" in held.json()["invitation_email"]["reasons"]
    assert COHORT not in opened.text and COHORT not in held.text


@pytest.mark.parametrize("body, admitted", [
    ({"cohort": COHORT}, True),
    ({"cohort": f"  {COHORT}  "}, True),     # a mint strips the cohort, and the stored value is what is checked
    ({"cohort": None}, False),
    ({"cohort": OTHER_COHORT}, False),
    ({"cohort": COHORT.upper()}, False),
    ({"cohort": COHORT, "email": None}, False),  # unbound
])
def test_a_mint_under_the_exception_makes_only_a_link_it_admits(client, admin, cohort_open, body, admitted):
    before = _invite_count()
    resp = client.post("/api/admin/invites", json={"email": _address(), **body}, headers=admin)

    if admitted:
        assert resp.status_code == 200, resp.text
        assert resp.json()["cohort"] == COHORT and resp.json()["email"]
        assert _invite_count() == before + 1
    else:
        assert (resp.status_code, resp.json()) == (422, {"detail": admin_module.INVITED_COHORT_ONLY_DETAIL})
        assert _invite_count() == before
        assert COHORT not in resp.text


def test_a_mint_meets_the_closure_while_neither_collection_nor_the_exception_is_open(client, admin, cohort_open,
                                                                                    monkeypatch):
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
    before = _invite_count()
    resp = client.post("/api/admin/invites", json={"email": _address(), "cohort": COHORT}, headers=admin)
    assert (resp.status_code, resp.json()) == (503, CLOSED)
    assert _invite_count() == before


@pytest.mark.parametrize("email_bound, cohort", [(False, COHORT), (True, OTHER_COHORT), (True, None)])
def test_a_resend_outside_the_exception_is_refused_before_anything_is_revoked(client, admin, cohort_open,
                                                                              email_bound, cohort):
    invite_id, _raw = _mint(_address() if email_bound else None, cohort)
    before = _invite_count()

    resp = client.post(f"/api/admin/invites/{invite_id}/resend", json={"send_email": False}, headers=admin)

    assert (resp.status_code, resp.json()) == (422, {"detail": admin_module.INVITED_COHORT_ONLY_DETAIL})
    assert _invite(invite_id).is_revoked is False and _invite_count() == before


def test_a_resend_in_the_cohort_replaces_its_link(client, admin, cohort_open, monkeypatch):
    invite_id, _raw = _mint(_address())

    resp = client.post(f"/api/admin/invites/{invite_id}/resend", json={"send_email": False}, headers=admin)

    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked_invite_id"] == invite_id and resp.json()["cohort"] == COHORT
    assert _invite(invite_id).is_revoked is True
    monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)
    closed = client.post(f"/api/admin/invites/{resp.json()['id']}/resend", json={"send_email": False}, headers=admin)
    assert (closed.status_code, closed.json()) == (503, CLOSED)
    assert _invite(resp.json()["id"]).is_revoked is False


# ── the invitation email ──────────────────────────────────────────────────────

@pytest.fixture
def mail_ready_for_the_cohort(cohort_open, monkeypatch):
    """Invitation email's own conditions, with the exception (not collection) making its links redeemable."""
    monkeypatch.setattr(settings, "LEGAL_INVITATION_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "synthetic-provider-key")
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", WEBHOOK_SECRET)
    assert legal_readiness_service.is_invitation_email_available()


@pytest.fixture
def transport(monkeypatch):
    send = AsyncMock(side_effect=lambda **kwargs: {"id": f"em_{uuid.uuid4().hex[:12]}"})
    monkeypatch.setattr(email_service, "send_email", send)
    return send


SENDER = dict(
    magic_link="https://example.com/register?invite=synthetic",
    unsubscribe_link="https://example.com/email/unsubscribe#token=synthetic",
    delivery_ref="0" * 32,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("cohort", [OTHER_COHORT, None, COHORT.upper()])
async def test_the_sender_refuses_an_invitation_outside_the_cohort(mail_ready_for_the_cohort, transport, cohort):
    with pytest.raises(email_service.PromotionalMailUnavailable):
        await email_service.send_invite_email(to_email=_address(), cohort=cohort, **SENDER)
    transport.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_sender_sends_an_invitation_in_the_cohort(mail_ready_for_the_cohort, transport):
    await email_service.send_invite_email(to_email=_address(), cohort=COHORT, **SENDER)
    transport.assert_awaited_once()
    assert COHORT not in str(transport.call_args)


PERMISSION = {"requested_via": "message", "requested_on": utcnow().date().isoformat()}


def test_an_emailed_invitation_in_the_cohort_goes_out(client, admin, mail_ready_for_the_cohort, transport):
    resp = client.post(
        "/api/admin/invites",
        json={"email": _address(), "cohort": COHORT, "send_email": True, "permission": PERMISSION},
        headers=admin,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["emailed"] is True and resp.json()["delivery_status"] == "accepted"
    transport.assert_awaited_once()


def test_the_sender_refuses_when_the_exception_closes_after_the_route_checked(client, admin, mail_ready_for_the_cohort,
                                                                             transport, monkeypatch):
    prepare = invite_delivery_service.prepare_invite_send

    def prepare_then_close(*args, **kwargs):
        prepared = prepare(*args, **kwargs)
        monkeypatch.setattr(settings, "LEGAL_INVITED_COHORT_ENABLED", False)  # after the link committed, before the send
        return prepared

    monkeypatch.setattr(invite_delivery_service, "prepare_invite_send", prepare_then_close)
    resp = client.post(
        "/api/admin/invites",
        json={"email": _address(), "cohort": COHORT, "send_email": True, "permission": PERMISSION},
        headers=admin,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["emailed"] is False and resp.json()["delivery_status"] == "failed"
    transport.assert_not_awaited()
