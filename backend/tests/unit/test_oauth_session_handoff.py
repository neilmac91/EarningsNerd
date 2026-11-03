"""An OAuth sign-in's session handoff (E29 (5)), end to end against the app's SQLite database.

A Google or Apple callback's answer is a navigation, which cannot hold the session cookies' Web Lock
(frontend/lib/api/client.ts), so a refresh another tab sent with the previous account's cookies could answer after it
and set those back over the new session's: the reader landed as the previous account. For a start that asks for the
handoff, the callbacks set no session cookie. They commit the sign-in with a one-time session handoff and redirect to the frontend's landing page,
/auth/complete, with its code in the URL fragment, which no request log records, and set a cookie that binds the code
to the browser they answer. The landing page posts the code to ``POST /api/auth/oauth/complete`` holding the lock,
and that answer sets the session cookies. Only a start that asks for it hands off (``handoff=1`` on a GET start,
``"handoff": true`` on a POST start: a frontend with the landing page asks); any other takes main's path, the session
cookies on the redirect home, so an API rollback is safe at any time and a frontend rollback for every start made
after it (docs/DEPLOYMENT.md). Pinned here:

- the compatibility gate: each start that asks hands off, each that does not (no parameter or key, ``handoff=true``,
  ``handoff=0``, a state row from before the column) takes main's path, and a JSON string is refused 422;

- the callback's redirect: the landing page with the code in its fragment alone (no query string), the binding
  cookie and no session cookie; the handoff row holds only the SHA-256 hashes of the code and the binder, for two
  minutes, and the binding cookie is scoped as the session cookies are;
- the exchange signs in once, the session cookies on its own answer, in order, and leaves the binding cookie alone;
- it refuses, with one sentence, a second use, an expired code, a code from another browser (login CSRF: no binding
  cookie, or another sign-in's), and an unknown code, each setting no cookie and writing nothing; and a code or binder
  of the wrong shape without a query of the handoffs;
- no exchange's answer touches the binding cookie the browser holds, a refusal or a success: two sign-ins at once in
  one browser, the second's callback replacing the first's binding cookie, end with the second signed in whichever
  landing page posts first, and so do two whose second callback lands while the first's exchange is in flight;
- it reads the code from a JSON body alone, never a query string;
- a mint that fails at the exchange leaves the code unused and sets no cookie;
- the exchange is rate limited per IP in a bucket of its own;
- an account-wide sign-out (logout-all, a password change, a password reset) ends a handoff not yet exchanged, and an
  inactive account's handoff is refused, each writing nothing;
- a browser signed in as one account that completes another account's handoff ends on that other account; and
- neither the code nor the binder reaches a log record.
"""
import hashlib
import logging
import re
import secrets
import uuid
from datetime import timedelta, timezone
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal, engine
from app.models import OAuthState, RefreshToken, SessionHandoff, User
from app.routers import auth as auth_module
from app.services import refresh_token_service
from app.services.password_utils import get_password_hash
from app.utils.datetimes import utcnow
from tests.support.account_agreement import ACCOUNT_AGREEMENT
from tests.support.oauth_handoff import (
    COMPLETE_PATH, HANDOFF_BODY, HANDOFF_COOKIE, HANDOFF_QUERY, complete_sign_in, handoff_code,
)
from tests.support.summary_stream_harness import reset_rate_limiters

pytestmark = pytest.mark.usefixtures("collection_ready")

PROVIDERS = ("google", "apple")
REFUSED = {"detail": "This login has expired or was already used. Log in again."}
# Set-Cookie headers as the test settings render them, values and expiry stamps redacted.
SESSION_ISSUED = [
    "earningsnerd_access_token=<v>; HttpOnly; Max-Age=1800; Path=/; SameSite=lax",
    "en_session=1; HttpOnly; Max-Age=2592000; Path=/; SameSite=lax",
    "earningsnerd_refresh_token=<v>; HttpOnly; Max-Age=2592000; Path=/api/auth; SameSite=lax",
]
STATE_CLEARED = {
    "google": 'oauth_state=""; expires=<t>; Max-Age=0; Path=/; SameSite=lax',
    "apple": 'apple_oauth_state=""; expires=<t>; HttpOnly; Max-Age=0; Path=/; SameSite=none; Secure',
}
HANDOFF_SET = "en_oauth_handoff=<v>; HttpOnly; Max-Age=120; Path=/api/auth/oauth; SameSite=lax"
_EXPIRES = re.compile(r"expires=[^;]+")
PASSWORD = "Sup3rSecretPassw0rd"  # >=12 chars, upper+lower+digit; test fixture, not a credential  # gitleaks:allow
NEW_PASSWORD = "An0therSecretPassw0rd"  # test fixture, not a credential  # gitleaks:allow


@pytest.fixture(scope="module")
def client():
    # HTTPS base: the Apple binding cookie is Secure and the client returns it only over HTTPS.
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client, monkeypatch):
    reset_rate_limiters()
    auth_module.OAUTH_START_LIMITER._hits.clear()  # the starts' and the exchange's buckets, 20/min/IP each
    client.cookies.clear()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-google-client")
    monkeypatch.setattr(settings, "APPLE_CLIENT_ID", "io.earningsnerd.test")
    yield
    client.cookies.clear()


@pytest.fixture
def server_errors():
    """A client that gets the app's 500 for an unhandled exception instead of re-raising it (no lifespan of its own:
    the module client ran the app's startup)."""
    errors_client = TestClient(app, base_url="https://testserver", raise_server_exceptions=False)
    yield errors_client
    errors_client.close()


@pytest.fixture
def other_device():
    """A second browser, the account owner's on another device (no lifespan of its own, as ``server_errors``)."""
    device = TestClient(app, base_url="https://testserver")
    yield device
    device.close()


@pytest.fixture
def postgres_shaped_reset_expiry():
    """Load the reset link's expiry tz-aware, as PostgreSQL returns it (SQLite drops the zone), as
    ``test_auth_token_flows.py`` does for its reset cases."""
    def _aware(target, *_args):
        value = target.__dict__.get("password_reset_expires")
        if value is not None and value.tzinfo is None:
            set_committed_value(target, "password_reset_expires", value.replace(tzinfo=timezone.utc))

    event.listen(User, "load", _aware)
    event.listen(User, "refresh", _aware)
    yield
    event.remove(User, "load", _aware)
    event.remove(User, "refresh", _aware)


@pytest.fixture
def handoff_statements():
    """Every statement the app's engine runs on the handoffs' table, as it runs."""
    seen: list[str] = []

    def _record(_conn, _cursor, statement, *_args):
        if "earningsnerd_session_handoffs" in statement:
            seen.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    yield seen
    event.remove(engine, "before_cursor_execute", _record)


class _FakeTokenResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"id_token": "stub"}


class _FakeAsyncClient:
    """Google's code exchange, answered at once."""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def post(self, *args, **kwargs) -> _FakeTokenResponse:
        return _FakeTokenResponse()


def _email() -> str:
    return f"handoff_{uuid.uuid4().hex[:12]}@example.com"


def _start(client: TestClient, provider: str, *, start: str = "post", ask: Optional[dict] = None) -> str:
    """An OAuth start as the frontend makes it, and its state. ``start="post"`` is the sign-up page's POST, with signup
    assent and ``ask`` in its body (the handoff's ask by default); ``start="get"`` is the login page's link, with ``ask``
    as its query (none by default)."""
    if start == "post":
        resp = client.post(f"/api/auth/{provider}/start", json={**ACCOUNT_AGREEMENT, **(HANDOFF_BODY if ask is None else ask)})
        assert resp.status_code == 200, resp.text
        url = resp.json()["url"]
    else:
        resp = client.get(f"/api/auth/{provider}", params=ask or {}, follow_redirects=False)
        assert resp.status_code == 302, resp.text
        url = resp.headers["location"]
    return parse_qs(urlparse(url).query)["state"][0]


def _callback(
    client: TestClient, monkeypatch, provider: str, email: str, *, start: str = "post", ask: Optional[dict] = None,
    state: Optional[str] = None,
):
    """A provider sign-in end to end: the start (``_start``; a POST start that asks for the handoff by default, a new
    account then), or the ``state`` of one already made, then the callback, not followed."""
    state = state or _start(client, provider, start=start, ask=ask)
    sub = f"{provider}_{uuid.uuid4().hex}"
    if provider == "google":
        monkeypatch.setattr(auth_module, "httpx", SimpleNamespace(AsyncClient=_FakeAsyncClient))
        monkeypatch.setattr(
            auth_module, "_verify_google_id_token",
            AsyncMock(return_value={"sub": sub, "email": email, "email_verified": True}),
        )
        return client.get(
            "/api/auth/google/callback", params={"code": "provider-code", "state": state}, follow_redirects=False,
        )
    monkeypatch.setattr(
        auth_module, "_verify_apple_id_token",
        AsyncMock(return_value={"sub": sub, "email": email, "email_verified": "true"}),
    )
    return client.post("/api/auth/apple/callback", data={"state": state, "id_token": "stub"}, follow_redirects=False)


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


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _account(email: str) -> tuple[int, list[SessionHandoff], int]:
    """The account's id, its handoff rows and how many refresh tokens it holds."""
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        handoffs = db.query(SessionHandoff).filter_by(user_id=user.id).all()
        for row in handoffs:
            db.expunge(row)
        return user.id, handoffs, db.query(RefreshToken).filter_by(user_id=user.id).count()


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_callback_hands_the_landing_page_a_code_in_its_fragment_and_sets_no_session_cookie(
    client, monkeypatch, provider,
):
    """The redirect is the landing page with the code in its fragment and nowhere else, its cookies the state's clear
    and the binding cookie alone; the row stores the two values' hashes, never the values, for two minutes."""
    email = _email()
    resp = _callback(client, monkeypatch, provider, email)
    code = handoff_code(resp)
    assert _cookies(resp) == [STATE_CLEARED[provider], HANDOFF_SET]
    binder = resp.cookies[HANDOFF_COOKIE]
    assert binder != code and len(code) == len(binder) == 43
    _, (row,), tokens = _account(email)
    assert (row.code_hash, row.binder_hash) == (_sha256(code), _sha256(binder))
    stored = [str(getattr(row, column.name)) for column in SessionHandoff.__table__.columns]
    assert not [value for value in stored if code in value or binder in value]
    assert row.used_at is None and row.expires_at - row.created_at == timedelta(seconds=120)
    assert tokens == 0


@pytest.mark.requires_db
def test_the_binding_cookie_is_scoped_as_the_session_cookies_are(client, monkeypatch):
    """Under the deployment's cookie settings the binding cookie takes the session cookies' Domain, Secure and SameSite;
    the exchange's answer sets those three cookies alone and leaves the binding cookie to lapse."""
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".earningsnerd.io")
    monkeypatch.setattr(settings, "COOKIE_SECURE", True)
    resp = _callback(client, monkeypatch, "google", _email())
    code = handoff_code(resp)
    (issued,) = [h for h in resp.headers.get_list("set-cookie") if h.startswith(f"{HANDOFF_COOKIE}=")]
    binder = issued.split(";", 1)[0].split("=", 1)[1]
    assert issued == (
        f"{HANDOFF_COOKIE}={binder}; Domain=.earningsnerd.io; HttpOnly; Max-Age=120; Path=/api/auth/oauth; "
        "SameSite=lax; Secure"
    )
    # The jar keeps no cookie for another domain, so the landing page's post carries the binder by hand.
    exchange = client.post(COMPLETE_PATH, json={"code": code}, headers={"cookie": f"{HANDOFF_COOKIE}={binder}"})
    assert exchange.status_code == 200, exchange.text
    access, presence, refresh = exchange.headers.get_list("set-cookie")
    for header in (access, presence, refresh):
        assert "Domain=.earningsnerd.io" in header and "Secure" in header and "SameSite=lax" in header, header
        assert not header.startswith(f"{HANDOFF_COOKIE}="), header


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_the_exchange_signs_in_once_with_the_session_cookies_on_its_own_answer(client, monkeypatch, provider):
    """The landing page's post sets the new account's session, in order, and leaves the binding cookie alone; the same
    code again, with that binder still in the jar, is refused and changes nothing."""
    email = _email()
    resp = _callback(client, monkeypatch, provider, email)
    binder = resp.cookies[HANDOFF_COOKIE]
    exchange = complete_sign_in(client, resp)
    assert exchange.status_code == 200 and exchange.json() == {"status": "signed_in"}
    assert _cookies(exchange) == SESSION_ISSUED
    access = jwt.decode(exchange.cookies[settings.COOKIE_NAME], options={"verify_signature": False})
    assert access["sub"] == email
    user_id, (row,), tokens = _account(email)
    assert row.used_at is not None and tokens == 1
    with SessionLocal() as db:
        (live,) = db.query(RefreshToken).filter_by(user_id=user_id, revoked_at=None).all()
        assert live.token_hash == refresh_token_service._hash_token(exchange.cookies[settings.REFRESH_COOKIE_NAME])
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == email

    assert client.cookies.get(HANDOFF_COOKIE) == binder
    again = complete_sign_in(client, resp)
    assert again.status_code == 400 and again.json() == REFUSED
    assert _cookies(again) == []
    assert _account(email)[2] == 1


@pytest.mark.requires_db
@pytest.mark.parametrize("refusal", ["expired", "no-binding-cookie", "another-sign-ins-binder", "unknown-code"])
def test_the_exchange_refuses_a_code_it_cannot_redeem_alike_and_writes_nothing(client, monkeypatch, refusal):
    """One answer for each: no cookie set (the binding cookie stays as the browser holds it), the code still unused and
    no refresh token.
    A code posted from a browser with no binding cookie, or another sign-in's, is login CSRF refused: an attacker's
    own sign-in, completed in their browser, cannot be planted on a victim's."""
    email = _email()
    resp = _callback(client, monkeypatch, "google", email)
    code = handoff_code(resp)
    if refusal == "expired":
        with SessionLocal() as db:
            db.query(SessionHandoff).filter_by(code_hash=_sha256(code)).update(
                {SessionHandoff.expires_at: utcnow() - timedelta(seconds=1)}, synchronize_session=False,
            )
            db.commit()
    elif refusal == "no-binding-cookie":
        client.cookies.clear()
    elif refusal == "another-sign-ins-binder":
        client.cookies.clear()
        client.cookies.set(HANDOFF_COOKIE, secrets.token_urlsafe(32))
    else:
        code = secrets.token_urlsafe(32)
    refused = client.post(COMPLETE_PATH, json={"code": code})
    assert refused.status_code == 400 and refused.json() == REFUSED
    assert _cookies(refused) == []
    _, (row,), tokens = _account(email)
    assert row.used_at is None and tokens == 0


@pytest.mark.requires_db
@pytest.mark.parametrize("first", ["earlier", "later"], ids=["earlier-tab-posts-first", "later-tab-posts-first"])
def test_two_sign_ins_at_once_in_one_browser_end_with_the_later_one_signed_in(client, monkeypatch, first):
    """The later callback's binding cookie replaces the earlier one's (one name, Domain and Path), so the earlier tab's
    code is refused as another browser's. Its refusal sets no cookie: the later tab's exchange still carries its own
    binding cookie and signs in, whichever landing page posts first (open question 6 on #1963). A refusal that cleared
    the browser's binding cookie failed both tabs when the earlier one posted first."""
    earlier_email, later_email = _email(), _email()
    earlier = _callback(client, monkeypatch, "google", earlier_email)
    later = _callback(client, monkeypatch, "apple", later_email)
    assert client.cookies.get(HANDOFF_COOKIE) == later.cookies[HANDOFF_COOKIE]

    if first == "earlier":
        refused = complete_sign_in(client, earlier)
        assert refused.status_code == 400 and refused.json() == REFUSED and _cookies(refused) == []
        assert client.cookies.get(HANDOFF_COOKIE) == later.cookies[HANDOFF_COOKIE]
        signed_in = complete_sign_in(client, later)
    else:
        signed_in = complete_sign_in(client, later)
        refused = complete_sign_in(client, earlier)
        assert refused.status_code == 400 and refused.json() == REFUSED and _cookies(refused) == []
    assert signed_in.status_code == 200 and _cookies(signed_in) == SESSION_ISSUED
    assert client.get("/api/auth/me").json()["email"] == later_email
    (_, (earlier_row,), earlier_tokens), (_, (later_row,), later_tokens) = _account(earlier_email), _account(later_email)
    assert earlier_row.used_at is None and earlier_tokens == 0
    assert later_row.used_at is not None and later_tokens == 1


@pytest.mark.requires_db
def test_a_success_leaves_a_later_sign_ins_binding_cookie_for_its_own_exchange(client, monkeypatch):
    """One browser: sign-in 1's landing page posts its code, and sign-in 2's callback sets its binding cookie while
    that exchange is in flight (the post carries sign-in 1's binder, the cookie of the moment it was sent). Sign-in 1's
    answer, a 200, sets the session cookies alone and leaves sign-in 2's binder in place, so sign-in 2's exchange signs
    in. An answer that cleared the binding cookie on a success deleted sign-in 2's, and its exchange was refused."""
    first_email, second_email = _email(), _email()
    first = _callback(client, monkeypatch, "google", first_email)
    first_binder = first.cookies[HANDOFF_COOKIE]
    second = _callback(client, monkeypatch, "apple", second_email)
    second_binder = second.cookies[HANDOFF_COOKIE]
    assert client.cookies.get(HANDOFF_COOKIE) == second_binder

    # Sent before sign-in 2's callback replaced the cookie, so it carries sign-in 1's binder; it answers after.
    exchanged = client.post(
        COMPLETE_PATH, json={"code": handoff_code(first)}, headers={"cookie": f"{HANDOFF_COOKIE}={first_binder}"},
    )
    assert exchanged.status_code == 200 and _cookies(exchanged) == SESSION_ISSUED
    assert client.cookies.get(HANDOFF_COOKIE) == second_binder

    signed_in = complete_sign_in(client, second)
    assert signed_in.status_code == 200 and _cookies(signed_in) == SESSION_ISSUED
    assert client.get("/api/auth/me").json()["email"] == second_email
    (_, (first_row,), first_tokens), (_, (second_row,), second_tokens) = _account(first_email), _account(second_email)
    assert first_row.used_at is not None and first_tokens == 1
    assert second_row.used_at is not None and second_tokens == 1


@pytest.mark.requires_db
@pytest.mark.parametrize(
    "code, cookie",
    [
        ("é" * 43, None),  # a code no mint wrote: not ASCII
        ("a" * 129, None),  # longer than any mint writes, inside the body's bound
        ("", None),
        (None, b"en_oauth_handoff=\xe9\xe9\xe9"),  # a binder that is not ASCII
        (None, b"en_oauth_handoff=" + b"b" * 129),
    ],
    ids=["code-not-ascii", "code-too-long", "code-empty", "binder-not-ascii", "binder-too-long"],
)
def test_a_code_or_binder_of_the_wrong_shape_is_refused_with_no_query(
    client, monkeypatch, handoff_statements, code, cookie,
):
    resp = _callback(client, monkeypatch, "google", _email())
    real_code = handoff_code(resp)
    if cookie is not None:
        client.cookies.clear()
    handoff_statements.clear()  # the callback's own
    headers = {"cookie": cookie} if cookie is not None else None
    refused = client.post(COMPLETE_PATH, json={"code": real_code if code is None else code}, headers=headers)
    assert refused.status_code == 400 and refused.json() == REFUSED
    assert handoff_statements == []


@pytest.mark.requires_db
def test_the_exchange_reads_its_code_from_a_json_body_alone(client, monkeypatch, handoff_statements):
    """Never from a query string, which request logs record, nor from a form, a body with another field, a number or
    a string past the bound; each is refused before any read of the handoffs, and its 422 quotes no input."""
    resp = _callback(client, monkeypatch, "google", _email())
    code = handoff_code(resp)
    handoff_statements.clear()
    for refused in (
        client.post(f"{COMPLETE_PATH}?code={code}"),
        client.post(COMPLETE_PATH, data={"code": code}),
        client.post(COMPLETE_PATH, json={"code": code, "binder": resp.cookies[HANDOFF_COOKIE]}),
        client.post(COMPLETE_PATH, json={"code": 7}),
        client.post(COMPLETE_PATH, json={"code": code + "x" * 200}),
    ):
        assert refused.status_code == 422, refused.text
        assert code not in refused.text and resp.cookies[HANDOFF_COOKIE] not in refused.text
    assert client.get(COMPLETE_PATH).status_code == 405
    assert handoff_statements == []
    assert complete_sign_in(client, resp).status_code == 200  # none of them spent the code


@pytest.mark.requires_db
def test_a_mint_that_fails_at_the_exchange_leaves_the_code_unused_and_sets_no_cookie(monkeypatch, server_errors):
    """The redemption commits with the session's refresh token: a mint that fails rolls both back, so the answer is the
    500 with no cookie, and the same browser's next post of the code signs in."""
    email = _email()
    resp = _callback(server_errors, monkeypatch, "apple", email)
    armed = {"on": True}

    def _before_flush(session, _flush_context, _instances):
        if armed["on"] and any(isinstance(obj, RefreshToken) for obj in session.new):
            armed["on"] = False
            raise RuntimeError("refresh-token store down")

    event.listen(Session, "before_flush", _before_flush)
    try:
        failed = complete_sign_in(server_errors, resp)
    finally:
        event.remove(Session, "before_flush", _before_flush)
    assert armed["on"] is False, "the mint failure was never injected"
    assert failed.status_code == 500 and _cookies(failed) == []
    _, (row,), tokens = _account(email)
    assert row.used_at is None and tokens == 0
    retried = complete_sign_in(server_errors, resp)
    assert retried.status_code == 200 and _cookies(retried) == SESSION_ISSUED


@pytest.mark.requires_db
def test_the_exchange_is_rate_limited_per_ip_in_a_bucket_of_its_own(client, monkeypatch):
    """The starts' limiter, 20 a minute per IP, under its own key: the exchange's posts spend none of the starts'."""
    for _ in range(20):
        assert client.post(COMPLETE_PATH, json={"code": secrets.token_urlsafe(32)}).status_code == 400
    limited = client.post(COMPLETE_PATH, json={"code": secrets.token_urlsafe(32)})
    assert limited.status_code == 429 and limited.json() == {"detail": "Too many login attempts. Try again shortly."}
    assert client.post("/api/auth/google/start", json=ACCOUNT_AGREEMENT).status_code == 200


def _verified_account(email: str, password: Optional[str] = None) -> int:
    """A verified account a Google or Apple sign-in with its address links to (so a GET start, which carries no signup
    assent, signs in too), with a password when given; its id."""
    with SessionLocal() as db:
        user = User(
            email=email, is_active=True, email_verified=True,
            hashed_password=get_password_hash(password) if password else None,
        )
        db.add(user)
        db.commit()
        return user.id


def _assert_main_path(client: TestClient, resp, provider: str, email: str) -> None:
    """Main's path: the redirect home carrying the state's clear and the session cookies, no handoff row and no binding
    cookie, the account signed in on this answer alone."""
    assert resp.status_code == 302 and resp.headers["location"] == settings.FRONTEND_URL, resp.headers.get("location")
    assert _cookies(resp) == [STATE_CLEARED[provider], *SESSION_ISSUED]
    _, handoffs, tokens = _account(email)
    assert handoffs == [] and tokens == 1
    assert client.get("/api/auth/me").json()["email"] == email


def _assert_handed_off(client: TestClient, resp, provider: str, email: str) -> None:
    """This PR's path: the landing page with the code and the binding cookie, no session cookie until the exchange."""
    handoff_code(resp)
    assert _cookies(resp) == [STATE_CLEARED[provider], HANDOFF_SET]
    assert _account(email)[2] == 0
    exchange = complete_sign_in(client, resp)
    assert exchange.status_code == 200 and _cookies(exchange) == SESSION_ISSUED
    assert client.get("/api/auth/me").json()["email"] == email


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    "start, ask, hands_off",
    [
        ("get", HANDOFF_QUERY, True),
        ("post", HANDOFF_BODY, True),
        ("get", {}, False),
        ("post", {}, False),
        ("get", {"handoff": "true"}, False),
        ("get", {"handoff": "0"}, False),
        ("post", {"handoff": False}, False),
    ],
    ids=["get-1", "post-true", "get-none", "post-none", "get-true-string", "get-0", "post-false"],
)
def test_only_a_start_that_asks_for_the_handoff_gets_it(client, monkeypatch, provider, start, ask, hands_off):
    """The compatibility gate (E29 (5)): the login page's link asks with ``handoff=1`` and the sign-up page's buttons
    with ``"handoff": true``; any other start (an older frontend, a bookmark, the runbook's direct URL) takes main's
    path, so a new API serves an old frontend, and an old API, which ignores the ask, serves a start a new one makes
    (a start that asked before a frontend rollback still lands on /auth/complete: docs/DEPLOYMENT.md)."""
    email = _email()
    _verified_account(email)
    resp = _callback(client, monkeypatch, provider, email, start=start, ask=ask)
    if hands_off:
        _assert_handed_off(client, resp, provider, email)
    else:
        _assert_main_path(client, resp, provider, email)


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("ask", ["true", 1, "1"], ids=["string-true", "number-1", "string-1"])
def test_a_post_start_refuses_a_handoff_ask_that_is_not_json_true(client, provider, ask):
    """StrictBool: a string or a number is no JSON true; the start answers 422 and writes no state."""
    with SessionLocal() as db:
        before = db.query(OAuthState).count()
    resp = client.post(f"/api/auth/{provider}/start", json={**ACCOUNT_AGREEMENT, "handoff": ask})
    assert resp.status_code == 422, resp.text
    with SessionLocal() as db:
        assert db.query(OAuthState).count() == before


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_state_row_from_before_the_column_takes_main_path(client, monkeypatch, provider):
    """A start an API without the column wrote leaves ``session_handoff`` NULL; its callback, served by the new API
    after the deploy, takes main's path, as the frontend that made that start expects."""
    email = _email()
    _verified_account(email)
    state = _start(client, provider)
    with SessionLocal() as db:
        assert db.query(OAuthState).filter_by(state=state).update({OAuthState.session_handoff: None}) == 1
        db.commit()
    resp = _callback(client, monkeypatch, provider, email, state=state)
    _assert_main_path(client, resp, provider, email)


def _reset_token(client: TestClient, monkeypatch, email: str) -> str:
    """The token of the reset link forgot-password mails the account, its mail captured."""
    sent = AsyncMock()
    monkeypatch.setattr("app.services.email_service.send_password_reset_email", sent)
    assert client.post("/api/auth/forgot-password", json={"email": email}).status_code == 200
    return parse_qs(urlparse(sent.call_args.kwargs["reset_link"]).query)["token"][0]


@pytest.mark.requires_db
@pytest.mark.parametrize("revocation", ["logout_all", "change_password", "reset"])
def test_an_account_wide_sign_out_ends_a_handoff_not_yet_exchanged(
    client, monkeypatch, other_device, postgres_shaped_reset_expiry, revocation,
):
    """A Google sign-in committed its handoff; before its landing page exchanges the code, the account's owner signs out
    everywhere, changes the password or resets it on another device. The revocation deletes the account's handoffs
    with its tokens (``revoke_all_for_user``), so the exchange is refused, sets no cookie and mints nothing: no session
    from before the sign-out reaches a browser after it."""
    email = _email()
    user_id = _verified_account(email, PASSWORD)
    resp = _callback(client, monkeypatch, "google", email)
    handoff_code(resp)
    assert len(_account(email)[1]) == 1
    if revocation == "reset":
        signed_out = other_device.post(
            "/api/auth/reset-password", json={"token": _reset_token(other_device, monkeypatch, email), "new_password": NEW_PASSWORD},
        )
    else:
        login = other_device.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        if revocation == "logout_all":
            signed_out = other_device.post("/api/auth/logout-all", json={"account_id": user_id})
        else:
            signed_out = other_device.post(
                "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            )
    assert signed_out.status_code == 200, signed_out.text
    _, handoffs, tokens_before = _account(email)
    assert handoffs == []

    refused = complete_sign_in(client, resp)
    assert refused.status_code == 400 and refused.json() == REFUSED
    assert _cookies(refused) == []
    assert _account(email)[2] == tokens_before
    with SessionLocal() as db:
        live = db.query(RefreshToken).filter_by(user_id=user_id, revoked_at=None).count()
    assert live == (1 if revocation == "change_password" else 0)  # the changer's new session alone
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_an_inactive_accounts_handoff_is_refused_and_writes_nothing(client, monkeypatch, provider):
    """An account deactivated between its callback and its landing page's exchange: the exchange reads the account
    under its lock, finds it inactive and refuses, as a password login does, leaving the handoff unused and minting
    nothing."""
    email = _email()
    resp = _callback(client, monkeypatch, provider, email)
    handoff_code(resp)
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        user.is_active = False
        db.commit()
    refused = complete_sign_in(client, resp)
    assert refused.status_code == 400 and refused.json() == REFUSED
    assert _cookies(refused) == []
    _, (row,), tokens = _account(email)
    assert row.used_at is None and tokens == 0


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_a_browser_signed_in_as_one_account_completes_anothers_handoff_and_ends_on_it(client, monkeypatch, provider):
    """One browser, signed in as account A by the password login, signs in as account B with Google or Apple
    (PB-05's ask on #1963): the exchange's answer replaces A's cookies with B's, so /me answers B and the access and
    refresh cookies the browser holds are B's."""
    a_email, b_email = _email(), _email()
    _verified_account(a_email, PASSWORD)
    login = client.post("/api/auth/login", json={"email": a_email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    assert client.get("/api/auth/me").json()["email"] == a_email

    resp = _callback(client, monkeypatch, provider, b_email)
    handoff_code(resp)
    exchange = complete_sign_in(client, resp)
    assert exchange.status_code == 200 and _cookies(exchange) == SESSION_ISSUED

    assert client.get("/api/auth/me").json()["email"] == b_email
    access = jwt.decode(client.cookies.get(settings.COOKIE_NAME), options={"verify_signature": False})
    assert access["sub"] == b_email
    b_id = _account(b_email)[0]
    with SessionLocal() as db:
        held = db.query(RefreshToken).filter_by(
            token_hash=refresh_token_service._hash_token(client.cookies.get(settings.REFRESH_COOKIE_NAME)),
        ).one()
        assert (held.user_id, held.revoked_at) == (b_id, None)


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_neither_the_code_nor_the_binder_reaches_a_log_record(client, monkeypatch, caplog, provider):
    with caplog.at_level(logging.DEBUG):
        resp = _callback(client, monkeypatch, provider, _email())
        code, binder = handoff_code(resp), resp.cookies[HANDOFF_COOKIE]
        assert complete_sign_in(client, resp).status_code == 200
        assert complete_sign_in(client, resp).status_code == 400  # the binder still in the jar
    assert caplog.records, "the run logged nothing, so the check read nothing"
    leaked = [
        record.name for record in caplog.records
        if code in record.getMessage() or binder in record.getMessage() or code in (record.exc_text or "")
    ]
    assert leaked == []
