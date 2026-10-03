"""
Account creation on the social sign-in callbacks is gated like POST /api/auth/register.

Behaviour (real endpoints against the app's SQLite DB; provider HTTP + id-token verification are
mocked, mirroring test_apple_signin.py):
  - under REGISTRATION_MODE=invite_only a Google or Apple callback for an unknown provider subject
    creates no User and redirects with error=invite_required; a sign-in started with a valid invite
    (GET /api/auth/google|apple?invite=...) creates the account, tags it is_beta and consumes the
    invite; linking to an existing verified account still works
  - a provider claim with email_verified=false never seeds an account (error=email_unverified)
  - the Apple callback requires the browser-binding cookie set at GET /api/auth/apple
  - a lost invite-redemption race rolls the account back on both the social and the email path,
    and the email path's response stays byte-identical to the success response

Structural gate (CLAUDE.md rule 12): every ``User(`` construction in app/routers/auth.py sits in a
function that calls the gate helper, or is register() (whose gate is the REGISTRATION_MODE check
at the top of the handler). A fourth creation path cannot appear silently.
"""
import ast
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from main import app
from app.database import SessionLocal
from app.models import InviteCode, OAuthAccount, OAuthState, User
from app.routers import auth as auth_module
from app.services import invite_service

AUTH_ROUTER = Path(__file__).resolve().parents[2] / "app" / "routers" / "auth.py"
GATE_HELPER = "_oauth_new_account_gate"
VALID_PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit; test fixture, not a credential  # gitleaks:allow
PROVIDERS = ("google", "apple")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh_flow(client, monkeypatch):
    """Every test starts with no cookies, both providers configured (the GET starters need a client
    id) and a clear register limiter (5/min/IP)."""
    client.cookies.clear()
    monkeypatch.setattr(auth_module.settings, "GOOGLE_CLIENT_ID", "test-google-client")
    monkeypatch.setattr(auth_module.settings, "APPLE_CLIENT_ID", "io.earningsnerd.test")
    auth_module.REGISTER_LIMITER._hits.clear()
    auth_module.OAUTH_START_LIMITER._hits.clear()
    yield
    client.cookies.clear()


@pytest.fixture
def invite_only(monkeypatch):
    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "invite_only")


@pytest.fixture
def public_mode(monkeypatch):
    monkeypatch.setattr(auth_module.settings, "REGISTRATION_MODE", "public")


# ── provider mocks + flow helpers ─────────────────────────────────────────────

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


def _state_from(resp) -> str:
    assert resp.status_code == 302, resp.text
    return parse_qs(urlparse(resp.headers["location"]).query)["state"][0]


def _start(client: TestClient, provider: str, invite: str | None = None) -> str:
    """GET /api/auth/<provider> (optionally carrying an invite) and return the state it issued. The
    state cookie lands on ``client`` as it would on a browser."""
    resp = client.get(
        f"/api/auth/{provider}",
        params={"invite": invite} if invite else None,
        follow_redirects=False,
    )
    state = _state_from(resp)
    if provider == "apple":
        assert auth_module._APPLE_STATE_COOKIE in resp.cookies, "Apple must issue the binding cookie"
    return state


def _claims(provider: str, email: str, *, verified: bool = True) -> dict:
    if provider == "google":
        return {"sub": f"google_{uuid.uuid4().hex}", "email": email, "email_verified": verified}
    return {"sub": f"apple_{uuid.uuid4().hex}", "email": email, "email_verified": str(verified).lower()}


def _callback(client: TestClient, monkeypatch, provider: str, claims: dict, *, state: str | None = None):
    """Drive the provider callback with a verified-claims mock. Without ``state`` a plain (no-invite)
    Google sign-in is simulated by setting the state cookie directly; Apple always needs _start()."""
    if provider == "google":
        if state is None:
            state = f"state_{uuid.uuid4().hex}"
            client.cookies.set(auth_module._OAUTH_STATE_COOKIE, state)
        monkeypatch.setattr(auth_module, "httpx", SimpleNamespace(AsyncClient=_FakeAsyncClient))
        monkeypatch.setattr(auth_module, "_verify_google_id_token", AsyncMock(return_value=claims))
        return client.get(
            "/api/auth/google/callback", params={"code": "code", "state": state}, follow_redirects=False
        )
    assert state is not None
    monkeypatch.setattr(auth_module, "_verify_apple_id_token", AsyncMock(return_value=claims))
    return client.post(
        "/api/auth/apple/callback", data={"state": state, "id_token": "stub"}, follow_redirects=False
    )


# ── DB helpers ────────────────────────────────────────────────────────────────

def _email() -> str:
    return f"oauthgate_{uuid.uuid4().hex[:12]}@example.com"


def _user(email: str) -> User | None:
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def _links(email: str) -> int:
    db = SessionLocal()
    try:
        return db.query(OAuthAccount).filter_by(provider_email=email).count()
    finally:
        db.close()


def _state_rows(state: str) -> list[OAuthState]:
    db = SessionLocal()
    try:
        return db.query(OAuthState).filter_by(state=state).all()
    finally:
        db.close()


def _seed_user(email: str, *, verified: bool) -> None:
    db = SessionLocal()
    try:
        db.add(User(email=email, hashed_password="x", email_verified=verified))
        db.commit()
    finally:
        db.close()


def _mint_invite() -> tuple[int, str]:
    db = SessionLocal()
    try:
        invite, raw, _link = invite_service.mint_invite(db, created_by=None)
        return invite.id, raw
    finally:
        db.close()


def _invite(invite_id: int) -> InviteCode:
    db = SessionLocal()
    try:
        return db.query(InviteCode).filter(InviteCode.id == invite_id).one()
    finally:
        db.close()


def _assert_refused(resp, error_code: str, email: str) -> None:
    assert resp.status_code == 302, resp.text
    assert urlparse(resp.headers["location"]).query == f"error={error_code}", resp.headers["location"]
    assert f"{auth_module.settings.COOKIE_NAME}=" not in resp.headers.get("set-cookie", "")
    assert _user(email) is None
    assert _links(email) == 0


def _assert_signed_in(resp, email: str) -> None:
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == auth_module.settings.FRONTEND_URL
    assert f"{auth_module.settings.COOKIE_NAME}=" in resp.headers.get("set-cookie", "")
    assert _links(email) == 1


# ── invite gate ───────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_unknown_subject_is_refused_in_invite_only_mode(client, monkeypatch, invite_only, provider):
    email = _email()
    state = _start(client, provider) if provider == "apple" else None
    resp = _callback(client, monkeypatch, provider, _claims(provider, email), state=state)
    _assert_refused(resp, "invite_required", email)


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_linking_an_existing_verified_account_still_works_in_invite_only_mode(
    client, monkeypatch, invite_only, provider
):
    email = _email()
    _seed_user(email, verified=True)
    state = _start(client, provider) if provider == "apple" else None
    resp = _callback(client, monkeypatch, provider, _claims(provider, email), state=state)
    _assert_signed_in(resp, email)
    assert _user(email).is_beta is False  # linking consumes no invite


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_invited_social_sign_up_creates_a_beta_account_and_consumes_the_invite(
    client, monkeypatch, invite_only, provider
):
    invite_id, raw = _mint_invite()
    email = _email()
    state = _start(client, provider, invite=raw)
    (row,) = _state_rows(state)
    assert row.invite_code_hash == invite_service.hash_invite_token(raw)  # never the raw token

    resp = _callback(client, monkeypatch, provider, _claims(provider, email), state=state)
    _assert_signed_in(resp, email)
    user = _user(email)
    assert user is not None and user.is_beta is True and user.email_verified is True
    invite = _invite(invite_id)
    assert invite.used_at is not None and invite.user_id == user.id
    assert _state_rows(state) == []  # single use


@pytest.mark.requires_db
def test_lost_invite_redemption_rolls_the_social_account_back(client, monkeypatch, invite_only):
    invite_id, raw = _mint_invite()
    email = _email()
    state = _start(client, "google", invite=raw)
    monkeypatch.setattr(invite_service, "redeem_invite", lambda *args, **kwargs: False)
    resp = _callback(client, monkeypatch, "google", _claims("google", email), state=state)
    _assert_refused(resp, "invite_required", email)
    assert _invite(invite_id).used_at is None


@pytest.mark.requires_db
def test_register_rolls_the_account_back_when_the_invite_redemption_is_lost(client, monkeypatch, invite_only):
    # Reference: a registration whose redemption succeeds.
    _ok_id, ok_raw = _mint_invite()
    ok_email = _email()
    ok = client.post(
        "/api/auth/register", json={"email": ok_email, "password": VALID_PASSWORD, "invite_code": ok_raw}
    )
    assert ok.status_code == 200 and _user(ok_email) is not None

    invite_id, raw = _mint_invite()
    email = _email()
    monkeypatch.setattr(invite_service, "redeem_invite", lambda *args, **kwargs: False)
    lost = client.post(
        "/api/auth/register", json={"email": email, "password": VALID_PASSWORD, "invite_code": raw}
    )
    assert lost.status_code == 200
    assert lost.content == ok.content  # opaque: indistinguishable from success
    assert _user(email) is None
    assert _invite(invite_id).used_at is None


# ── provider-claim and state hygiene ──────────────────────────────────────────

@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_unverified_provider_email_creates_no_account_even_in_public_mode(
    client, monkeypatch, public_mode, provider
):
    email = _email()
    state = _start(client, provider) if provider == "apple" else None
    resp = _callback(client, monkeypatch, provider, _claims(provider, email, verified=False), state=state)
    _assert_refused(resp, "email_unverified", email)


@pytest.mark.requires_db
def test_google_collision_with_an_unverified_password_account_redirects_instead_of_failing(
    client, monkeypatch, public_mode
):
    email = _email()
    _seed_user(email, verified=False)
    resp = _callback(client, monkeypatch, "google", _claims("google", email))
    assert resp.status_code == 302
    assert "error=google_account_conflict" in resp.headers["location"]
    assert _links(email) == 0
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.email == email).count() == 1
    finally:
        db.close()


@pytest.mark.requires_db
def test_apple_callback_requires_the_browser_binding_cookie(client, monkeypatch, public_mode):
    email = _email()
    state = _start(client, "apple")

    client.cookies.clear()  # a browser that did not start this flow
    resp = _callback(client, monkeypatch, "apple", _claims("apple", email), state=state)
    _assert_refused(resp, "oauth_state_mismatch", email)

    client.cookies.set(auth_module._APPLE_STATE_COOKIE, auth_module._apple_state_cookie_value("other"))
    resp = _callback(client, monkeypatch, "apple", _claims("apple", email), state=state)
    _assert_refused(resp, "oauth_state_mismatch", email)
    assert len(_state_rows(state)) == 1  # a post without the cookie does not burn the row

    client.cookies.set(auth_module._APPLE_STATE_COOKIE, auth_module._apple_state_cookie_value(state))
    resp = _callback(client, monkeypatch, "apple", _claims("apple", email), state=state)
    _assert_signed_in(resp, email)
    assert _state_rows(state) == []


# ── structural gate ───────────────────────────────────────────────────────────

class _UserConstructionFinder(ast.NodeVisitor):
    """Innermost enclosing function of every ``User(...)`` call, plus the functions calling the gate."""

    def __init__(self) -> None:
        self.constructions: list[tuple[str, int]] = []
        self.gate_callers: set[str] = set()
        self._stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            where = self._stack[-1] if self._stack else "<module>"
            if node.func.id == "User":
                self.constructions.append((where, node.lineno))
            elif node.func.id == GATE_HELPER:
                self.gate_callers.add(where)
        self.generic_visit(node)


def test_every_user_construction_in_the_auth_router_is_gated():
    tree = ast.parse(AUTH_ROUTER.read_text(encoding="utf-8"))
    finder = _UserConstructionFinder()
    finder.visit(tree)

    functions = {where for where, _ in finder.constructions}
    assert "register" in functions, "scanner found no User( in register() — the walk is broken"
    assert len(functions) >= 2, "the OAuth creation path constructs no User — the walk is broken"

    ungated = sorted(
        (where, line) for where, line in finder.constructions
        if where != "register" and where not in finder.gate_callers
    )
    assert not ungated, (
        f"User(...) constructed outside the gate in app/routers/auth.py: {ungated}. Every account "
        f"creation path must call {GATE_HELPER}() (REGISTRATION_MODE + email_verified) in the same "
        "function, or be register() itself."
    )

    gate = next(
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == GATE_HELPER
    )
    body = ast.unparse(gate)
    assert "settings.REGISTRATION_MODE" in body and "validate_invite_hash" in body, (
        f"{GATE_HELPER} no longer reads REGISTRATION_MODE / validates the invite"
    )


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_oauth_start_persists_nothing_for_an_unknown_invite(client, monkeypatch, invite_only, provider):
    """An unauthenticated caller cannot grow the state table by inventing invite values: an unknown
    token stores no invite hash (Google: no row at all; Apple: its nonce row carries no invite)."""
    with SessionLocal() as db:
        before = db.query(OAuthState).count()
    state = _start(client, provider, invite="not-a-real-invite-token")
    rows = _state_rows(state)
    if provider == "google":
        assert rows == []
    else:
        assert [row.invite_code_hash for row in rows] == [None]
    with SessionLocal() as db:
        assert db.query(OAuthState).filter(OAuthState.invite_code_hash.isnot(None)).count() == 0
        assert db.query(OAuthState).count() - before == (0 if provider == "google" else 1)


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_oauth_start_is_rate_limited_per_ip(client, monkeypatch, public_mode, provider):
    limit = auth_module.OAUTH_START_LIMITER.limit
    for _ in range(limit):
        assert client.get(f"/api/auth/{provider}", follow_redirects=False).status_code == 302
    blocked = client.get(f"/api/auth/{provider}", follow_redirects=False)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

