"""An OAuth sign-in's session handoff (E29 (5)), end to end against the app's SQLite database.

A Google or Apple callback's answer is a navigation, which cannot hold the session cookies' Web Lock
(frontend/lib/api/client.ts), so a refresh another tab sent with the previous account's cookies could answer after it
and set those back over the new session's: the reader landed as the previous account. The callbacks now set no
session cookie. They commit the sign-in with a one-time session handoff and redirect to the frontend's landing page,
/auth/complete, with its code in the URL fragment, which no request log records, and set a cookie that binds the code
to the browser they answer. The landing page posts the code to ``POST /api/auth/oauth/complete`` holding the lock,
and that answer sets the session cookies. Pinned here:

- the callback's redirect: the landing page with the code in its fragment alone (no query string), the binding
  cookie and no session cookie; the handoff row holds only the SHA-256 hashes of the code and the binder, for two
  minutes, and the binding cookie is scoped as the session cookies are, its clear matching it;
- the exchange signs in once, the session cookies on its own answer, in order, and clears the binding cookie;
- it refuses, with one sentence, a second use, an expired code, a code from another browser (login CSRF: no binding
  cookie, or another sign-in's), and an unknown code, each with no session cookie, the binding cookie cleared and
  nothing written; and a code or binder of the wrong shape without a query of the handoffs;
- it reads the code from a JSON body alone, never a query string;
- a mint that fails at the exchange leaves the code unused and sets no cookie;
- the exchange is rate limited per IP in a bucket of its own; and
- neither the code nor the binder reaches a log record.
"""
import hashlib
import logging
import re
import secrets
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from main import app
from app.config import settings
from app.database import SessionLocal, engine
from app.models import RefreshToken, SessionHandoff, User
from app.routers import auth as auth_module
from app.services import refresh_token_service
from app.utils.datetimes import utcnow
from tests.support.account_agreement import ACCOUNT_AGREEMENT
from tests.support.oauth_handoff import COMPLETE_PATH, HANDOFF_COOKIE, complete_sign_in, handoff_code
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
HANDOFF_CLEARED = 'en_oauth_handoff=""; expires=<t>; Max-Age=0; Path=/api/auth/oauth; SameSite=lax'
_EXPIRES = re.compile(r"expires=[^;]+")


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


def _callback(client: TestClient, monkeypatch, provider: str, email: str):
    """A provider sign-in end to end for a new account: the POST start, then the callback, not followed."""
    start = client.post(f"/api/auth/{provider}/start", json=ACCOUNT_AGREEMENT)
    assert start.status_code == 200, start.text
    state = parse_qs(urlparse(start.json()["url"]).query)["state"][0]
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
def test_the_binding_cookie_is_scoped_as_the_session_cookies_are_and_its_clear_matches_it(client, monkeypatch):
    """Under the deployment's cookie settings the binding cookie takes the session cookies' Domain, Secure and SameSite,
    and the exchange clears it with the same Domain and Path, the pair a browser deletes by."""
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
    access, presence, refresh, cleared = exchange.headers.get_list("set-cookie")
    for header in (access, presence, refresh):
        assert "Domain=.earningsnerd.io" in header and "Secure" in header and "SameSite=lax" in header, header
    assert cleared.startswith(f'{HANDOFF_COOKIE}=""; Domain=.earningsnerd.io; expires='), cleared
    assert "Max-Age=0; Path=/api/auth/oauth" in cleared, cleared


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_the_exchange_signs_in_once_with_the_session_cookies_on_its_own_answer(client, monkeypatch, provider):
    """The landing page's post sets the new account's session, in order, and clears the binding cookie; the same
    code again, even with its binder, is refused and changes nothing."""
    email = _email()
    resp = _callback(client, monkeypatch, provider, email)
    binder = resp.cookies[HANDOFF_COOKIE]
    exchange = complete_sign_in(client, resp)
    assert exchange.status_code == 200 and exchange.json() == {"status": "signed_in"}
    assert _cookies(exchange) == [*SESSION_ISSUED, HANDOFF_CLEARED]
    access = jwt.decode(exchange.cookies[settings.COOKIE_NAME], options={"verify_signature": False})
    assert access["sub"] == email
    user_id, (row,), tokens = _account(email)
    assert row.used_at is not None and tokens == 1
    with SessionLocal() as db:
        (live,) = db.query(RefreshToken).filter_by(user_id=user_id, revoked_at=None).all()
        assert live.token_hash == refresh_token_service._hash_token(exchange.cookies[settings.REFRESH_COOKIE_NAME])
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == email

    client.cookies.set(HANDOFF_COOKIE, binder)
    again = complete_sign_in(client, resp)
    assert again.status_code == 400 and again.json() == REFUSED
    assert _cookies(again) == [HANDOFF_CLEARED]
    assert _account(email)[2] == 1


@pytest.mark.requires_db
@pytest.mark.parametrize("refusal", ["expired", "no-binding-cookie", "another-sign-ins-binder", "unknown-code"])
def test_the_exchange_refuses_a_code_it_cannot_redeem_alike_and_writes_nothing(client, monkeypatch, refusal):
    """One answer for each: no session cookie, the binding cookie cleared, the code still unused and no refresh token.
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
    assert _cookies(refused) == [HANDOFF_CLEARED]
    _, (row,), tokens = _account(email)
    assert row.used_at is None and tokens == 0


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
    assert retried.status_code == 200 and _cookies(retried) == [*SESSION_ISSUED, HANDOFF_CLEARED]


@pytest.mark.requires_db
def test_the_exchange_is_rate_limited_per_ip_in_a_bucket_of_its_own(client, monkeypatch):
    """The starts' limiter, 20 a minute per IP, under its own key: the exchange's posts spend none of the starts'."""
    for _ in range(20):
        assert client.post(COMPLETE_PATH, json={"code": secrets.token_urlsafe(32)}).status_code == 400
    limited = client.post(COMPLETE_PATH, json={"code": secrets.token_urlsafe(32)})
    assert limited.status_code == 429 and limited.json() == {"detail": "Too many login attempts. Try again shortly."}
    assert client.post("/api/auth/google/start", json=ACCOUNT_AGREEMENT).status_code == 200


@pytest.mark.requires_db
@pytest.mark.parametrize("provider", PROVIDERS)
def test_neither_the_code_nor_the_binder_reaches_a_log_record(client, monkeypatch, caplog, provider):
    with caplog.at_level(logging.DEBUG):
        resp = _callback(client, monkeypatch, provider, _email())
        code, binder = handoff_code(resp), resp.cookies[HANDOFF_COOKIE]
        assert complete_sign_in(client, resp).status_code == 200
        client.cookies.set(HANDOFF_COOKIE, binder)
        assert complete_sign_in(client, resp).status_code == 400
    assert caplog.records, "the run logged nothing, so the check read nothing"
    leaked = [
        record.name for record in caplog.records
        if code in record.getMessage() or binder in record.getMessage() or code in (record.exc_text or "")
    ]
    assert leaked == []
