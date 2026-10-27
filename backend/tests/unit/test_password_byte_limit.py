"""Gate: no policy-valid password reaches bcrypt over its 72-byte limit (CLAUDE.md rule 12).

The policy (``validate_password_strength``) caps a password at 128 CHARACTERS, up to 512 UTF-8
bytes; bcrypt reads only the first 72 BYTES. bcrypt 4 dropped the rest silently, but bcrypt 5
(pinned in requirements.txt) raises ``ValueError`` instead, and nothing above the hash catches it:
register, reset-password and change-password answered 500 for a long passphrase or for about 37
non-ASCII characters, and login refused such a password even against the hash bcrypt 4 had made.

``password_utils`` now hands bcrypt the first 72 bytes of the UTF-8 encoding in both
``get_password_hash`` and ``verify_password``, exactly what bcrypt 4 hashed, so every stored hash
keeps verifying and there is no new hash format. Bytes past 72 do not contribute to the hash.

The behaviour tests reach bcrypt only through those two functions, so a structural check holds the
other paths: in every tracked backend Python file outside ``tests/``, bcrypt and passlib are
imported only by ``app/services/password_utils.py``, and every use of ``bcrypt`` there is
``bcrypt.gensalt`` or a ``bcrypt.hashpw``/``bcrypt.checkpw`` call whose first argument is
``_bcrypt_input(...)``. ``BCRYPT_REACH_FORMS`` scores that walk on each way it can be broken and
each look-alike that must pass. Out of its reach, each planted as a gap: a module named at run time
(``import_module(name)``, ``getattr(module, "bcrypt")``, ``sys.modules``), and passlib inside
``password_utils``, whose verify fallback hands passlib's bcrypt handler the whole password (dead
under bcrypt 5, whose length check fails passlib's self-test; removing it is a separate cleanup).

A password that is not valid text (a lone surrogate) is refused before either (E97): it encodes to no UTF-8, so the
breach check and bcrypt raised on it, and FastAPI's own 422, which quoted every refused value (the whole body for a
missing field), could not render it and answered 500 with a traceback that quoted the password. The section on it
holds each password route at a 422 of type, loc and msg only (``auth_validation.public_validation_errors``, which
``main.py`` answers ``RequestValidationError`` with), login and the current-password check at their usual refusal,
and the 500's two channels (the log line, the Sentry event's exception chain) free of a refused password. An
unencodable reset or verification token is refused as unknown, where its hash raised the same 500.

Real endpoints against the app's SQLite database, like the rest of the auth suite. SQLite hands
``DateTime(timezone=True)`` columns back naive while PostgreSQL hands them back aware; the
``_postgres_shaped_expiries`` fixture gives the reset-token expiry the production shape.
"""
import ast
import asyncio
import hashlib
import json
import logging
import subprocess
import uuid
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bcrypt
import pytest
import sentry_sdk
from tests.support.account_agreement import ACCOUNT_AGREEMENT

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.routers.auth import create_access_token
from app.services import auth_account_service, auth_validation, password_utils, pwned_passwords
from app.services.password_utils import get_password_hash, validate_password_strength, verify_password
from tests.support.summary_stream_harness import reset_rate_limiters

pytestmark = pytest.mark.usefixtures("collection_ready")

ASCII_87 = "correct horse battery staple " * 3  # 87 chars, 87 bytes  # gitleaks:allow
CYRILLIC_42 = "пароль" * 7  # 42 chars, 84 bytes  # gitleaks:allow
ASCII_72 = "a1b2c3d4" * 9  # 72 chars, exactly 72 bytes  # gitleaks:allow
STRADDLE = "x" * 71 + "é" + "tail"  # "é" is bytes 72-73, so the limit cuts it in half  # gitleaks:allow
THREE_BYTE_STRADDLE = "x" * 70 + "€tail"  # "€" is bytes 71-73; the limit keeps two  # gitleaks:allow
FOUR_BYTE_STRADDLE = "x" * 70 + "\U0001F510" + "tail"  # the lock is bytes 71-74; the limit keeps two
FOUR_BYTE_MAX = "\U0001F510" * password_utils.PASSWORD_MAX_LENGTH  # 128 chars, 512 bytes
SHORT = "OldStr0ngPassw0rd!"  # under 72 bytes; test fixture, not a credential  # gitleaks:allow

LONG_PASSWORDS = pytest.mark.parametrize("password", [ASCII_87, CYRILLIC_42], ids=["ascii87", "cyrillic84b"])


@pytest.fixture(scope="module")
def client():
    # A 500 comes back as a response (as in production) instead of re-raising into the test.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _fresh(client, monkeypatch):
    reset_rate_limiters()
    client.cookies.clear()
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "public")
    monkeypatch.setattr(password_utils, "BCRYPT_ROUNDS", 4)  # cost is irrelevant to the byte limit
    monkeypatch.setattr("app.services.email_service.send_verification_email", AsyncMock())
    yield
    client.cookies.clear()


@pytest.fixture(autouse=True)
def _postgres_shaped_expiries():
    """Load the reset-token expiry tz-aware, as PostgreSQL returns it (SQLite drops the zone)."""
    def _aware(target, *_args):
        value = target.__dict__.get("password_reset_expires")
        if value is not None and value.tzinfo is None:
            set_committed_value(target, "password_reset_expires", value.replace(tzinfo=timezone.utc))

    event.listen(User, "load", _aware)
    event.listen(User, "refresh", _aware)
    yield
    event.remove(User, "load", _aware)
    event.remove(User, "refresh", _aware)


def _email() -> str:
    return f"pwbytes_{uuid.uuid4().hex[:12]}@example.com"


def _create_user(email: str, hashed_password: str) -> None:
    with SessionLocal() as db:
        db.add(User(email=email, hashed_password=hashed_password, email_verified=True, is_active=True))
        db.commit()


def _login(client: TestClient, email: str, password: str):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    client.cookies.clear()
    return resp


def _bcrypt4_hash(password: str) -> str:
    """What bcrypt 4 stored for ``password``: the hash of its first 72 bytes."""
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4)).decode("utf-8")


# ── the hash and verify functions ────────────────────────────────────────────

@pytest.mark.parametrize(
    "password",
    [ASCII_87, CYRILLIC_42, ASCII_72, STRADDLE, FOUR_BYTE_MAX],
    ids=["ascii87", "cyrillic84b", "ascii72-boundary", "straddles-byte-72", "max-4-byte-chars"],
)
def test_every_policy_valid_password_hashes_and_verifies(password):
    assert validate_password_strength(password) == password
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
    # The stored hash is bcrypt 4's hash of the same password: its first 72 bytes, no new format.
    assert bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode("utf-8"))


def test_bytes_past_72_do_not_contribute_and_every_byte_before_does():
    hashed = get_password_hash(ASCII_87)
    assert verify_password(ASCII_87[:72] + " a different tail", hashed)  # bcrypt's documented limit
    assert not verify_password(ASCII_87[:71] + "#" + ASCII_87[72:], hashed)  # byte 72 still counts
    straddle_hash = get_password_hash(STRADDLE)
    # "ж" starts with a different lead byte than "é", so the half character at byte 72 still counts.
    assert not verify_password("x" * 71 + "ж" + "tail", straddle_hash)


@LONG_PASSWORDS
def test_a_hash_bcrypt4_made_from_a_long_password_still_verifies(password):
    assert verify_password(password, _bcrypt4_hash(password))


# ── the endpoints ────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@LONG_PASSWORDS
def test_register_accepts_a_long_password_and_login_takes_it(client, password):
    email = _email()
    resp = client.post("/api/auth/register", json={**ACCOUNT_AGREEMENT, "email": email, "password": password})
    assert resp.status_code == 200, resp.text
    assert _login(client, email, password).status_code == 200


@pytest.mark.requires_db
@LONG_PASSWORDS
def test_reset_password_accepts_a_long_password_and_login_takes_it(client, password):
    email = _email()
    _create_user(email, get_password_hash(SHORT))
    with SessionLocal() as db:
        token = auth_account_service.issue_password_reset_token(
            db, db.query(User).filter(User.email == email).one()
        )
    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": password})
    assert resp.status_code == 200, resp.text
    assert _login(client, email, password).status_code == 200
    assert _login(client, email, SHORT).status_code == 401


@pytest.mark.requires_db
@LONG_PASSWORDS
def test_change_password_accepts_a_long_password_and_login_takes_it(client, password):
    email = _email()
    _create_user(email, get_password_hash(SHORT))
    signed_in = _login(client, email, SHORT)
    assert signed_in.status_code == 200
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {signed_in.json()['access_token']}"},
        json={"current_password": SHORT, "new_password": password},
    )
    assert resp.status_code == 200, resp.text
    client.cookies.clear()
    assert _login(client, email, password).status_code == 200
    assert _login(client, email, SHORT).status_code == 401


# Long passwords as bcrypt 4 stored them, a character split at byte 72 included: login and the
# current-password check apply no policy, so every such account keeps signing in.
STORED_LONG_PASSWORDS = pytest.mark.parametrize(
    "password",
    [ASCII_87, CYRILLIC_42, STRADDLE, THREE_BYTE_STRADDLE, FOUR_BYTE_STRADDLE],
    ids=["ascii87", "cyrillic84b", "straddles-byte-72", "3-byte-char-straddles", "4-byte-char-straddles"],
)


@pytest.mark.requires_db
@STORED_LONG_PASSWORDS
def test_login_takes_a_long_password_against_its_bcrypt4_hash(client, password):
    email = _email()
    _create_user(email, _bcrypt4_hash(password))
    assert _login(client, email, password).status_code == 200


@pytest.mark.requires_db
@STORED_LONG_PASSWORDS
def test_change_password_takes_a_long_current_password_against_its_bcrypt4_hash(client, password):
    email = _email()
    _create_user(email, _bcrypt4_hash(password))
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {create_access_token(data={'sub': email})}"},
        json={"current_password": password, "new_password": SHORT},
    )
    assert resp.status_code == 200, resp.text
    client.cookies.clear()
    assert _login(client, email, SHORT).status_code == 200


# ── breach screening sees what bcrypt keys on ───────────────────────────────

# A breached password of exactly 72 bytes, and one of 71 so a 2-byte character straddles byte 72.
BREACHED_72 = "breached passphrase " * 3 + "breached pas"  # gitleaks:allow
BREACHED_71 = BREACHED_72[:71]  # gitleaks:allow


class _RangeApi:
    """Stands in for httpx.AsyncClient against the HIBP range API; ``listed`` holds the breached
    passwords, and ``asked`` records each lookup's SHA-1 prefix."""

    def __init__(self, listed: set[str]):
        self.listed = {hashlib.sha1(p.encode("utf-8")).hexdigest().upper() for p in listed}
        self.asked: list[str] = []

    def __call__(self, *_args, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def get(self, url, headers=None):
        prefix = url.rsplit("/", 1)[1]
        self.asked.append(prefix)
        body = "\n".join(f"{h[5:]}:7" for h in self.listed if h.startswith(prefix))
        return SimpleNamespace(text=body, raise_for_status=lambda: None)


@pytest.fixture
def range_api(monkeypatch):
    monkeypatch.setattr(pwned_passwords.settings, "PWNED_PASSWORD_CHECK_ENABLED", True)

    def install(listed: set[str]) -> _RangeApi:
        api = _RangeApi(listed)
        monkeypatch.setattr(pwned_passwords.httpx, "AsyncClient", api)
        return api

    return install


@pytest.mark.parametrize(
    "password, breached, lookups",
    [
        (BREACHED_72 + " and a tail nobody listed", BREACHED_72, 2),
        # Byte 72 splits "é": the breached text that ends with the whole "é" shares bcrypt's key.
        (BREACHED_71 + "é tail", BREACHED_71 + "é", 2),
        (BREACHED_71 + "é tail", BREACHED_71, 3),
    ],
    ids=["breached-72-byte-prefix", "breached-text-ending-in-the-split-character",
         "breached-prefix-before-a-split-character"],
)
def test_a_breached_bcrypt_prefix_with_an_unlisted_tail_is_screened_as_breached(
    range_api, password, breached, lookups
):
    api = range_api({breached})
    assert asyncio.run(pwned_passwords.is_password_pwned(password)) is True
    assert len(api.asked) == lookups  # the whole password, then bcrypt_screen_texts in order, to the first hit


@pytest.mark.parametrize(
    "password",
    [ASCII_87, CYRILLIC_42, STRADDLE, THREE_BYTE_STRADDLE, FOUR_BYTE_STRADDLE, FOUR_BYTE_MAX],
    ids=["ascii87", "cyrillic84b", "straddles-byte-72", "3-byte-char-straddles-byte-72",
         "4-byte-char-straddles-byte-72", "max-4-byte-chars"],
)
def test_the_first_screened_text_logs_in_wherever_the_password_does(password):
    """The text screened first must share bcrypt's key: if it is breached, it opens the account."""
    screened = password_utils.bcrypt_screen_texts(password)
    assert screened and password.startswith(screened[0])
    assert verify_password(screened[0], get_password_hash(password))


@pytest.mark.parametrize(
    "password, lookups",
    [(STRADDLE, 3), ("x" * 71 + "é", 2)],  # gitleaks:allow
    ids=["split-character-mid-password", "split-character-ends-the-password"],
)
def test_screening_looks_up_each_distinct_text_once(range_api, password, lookups):
    api = range_api({"password123"})
    assert asyncio.run(pwned_passwords.is_password_pwned(password)) is False
    assert len(api.asked) == lookups


def test_a_long_password_with_an_unlisted_prefix_passes_screening(range_api):
    api = range_api({"password123"})
    assert asyncio.run(pwned_passwords.is_password_pwned(ASCII_87)) is False
    assert len(api.asked) == 2


def test_a_password_bcrypt_hashes_whole_is_looked_up_once(range_api):
    api = range_api({"password123"})
    assert asyncio.run(pwned_passwords.is_password_pwned(ASCII_72)) is False
    assert len(api.asked) == 1


@pytest.mark.parametrize("password", [ASCII_87, STRADDLE], ids=["ascii87", "straddles-byte-72"])
def test_an_unreachable_hibp_costs_one_lookup_and_fails_open(monkeypatch, password):
    monkeypatch.setattr(pwned_passwords.settings, "PWNED_PASSWORD_CHECK_ENABLED", True)
    asked: list[str] = []

    class _Down(_RangeApi):
        async def get(self, url, headers=None):
            asked.append(url)
            raise pwned_passwords.httpx.ConnectTimeout("HIBP unreachable")

    monkeypatch.setattr(pwned_passwords.httpx, "AsyncClient", _Down(set()))
    assert asyncio.run(pwned_passwords.is_password_pwned(password)) is False
    assert len(asked) == 1  # one timeout, then fail open; not one per screened text


@pytest.mark.requires_db
def test_register_refuses_a_breached_bcrypt_prefix_behind_an_unlisted_tail(client, range_api):
    range_api({BREACHED_72})
    resp = client.post(
        "/api/auth/register",
        json={**ACCOUNT_AGREEMENT, "email": _email(), "password": BREACHED_72 + " and a tail nobody listed"},
    )
    assert resp.status_code == 400, resp.text
    assert "known data breach" in resp.json()["detail"]


# ── a password that is not valid text is refused where it enters, and no refused password comes back (E97) ────

# A refused password's distinctive part: no answer, log line or Sentry item may carry it. A lone surrogate after it
# (json.loads decodes the JSON escape "\ud800" to one) encodes to no UTF-8, so before E97 a short one made the 422
# itself fail to render, a 500 whose traceback quoted the password, and a long one passed the length rule and raised
# the same 500 in the breach check or bcrypt.
MARK = "Qx7mark"  # gitleaks:allow
SURROGATE_PASSWORDS = pytest.mark.parametrize(
    "password", [MARK + "\ud800", MARK + "-long-enough\ud800-tail"], ids=["under-the-floor", "over-the-floor"]
)
NOT_VALID_TEXT = "Value error, Password contains a character that is not valid text."
MALFORMED_JSON = '{"email": "a@example.com", "password": "' + MARK + '-long-enough-pass"'  # no closing brace


def _post_json(client: TestClient, path: str, payload, **headers):
    # json.dumps escapes a lone surrogate as "\ud800" (ensure_ascii), the bytes a client sends; httpx's own `json=`
    # encodes UTF-8 and would raise on it.
    return client.post(path, content=json.dumps(payload), headers={"content-type": "application/json", **headers})


def _refused(resp, status: int):
    assert resp.status_code == status, resp.text
    assert MARK not in resp.text
    body = resp.json()
    if status == 422:
        assert all(set(error) == {"type", "loc", "msg"} for error in body["detail"]), body
    return body


def _stored_hash(email: str) -> str | None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        return user.hashed_password if user else None


@pytest.mark.requires_db
@SURROGATE_PASSWORDS
def test_register_refuses_a_password_that_is_not_valid_text(client, range_api, password):
    lookups = range_api(set())
    email = _email()
    body = _refused(
        _post_json(client, "/api/auth/register", {**ACCOUNT_AGREEMENT, "email": email, "password": password}), 422
    )
    assert body["detail"] == [{"type": "value_error", "loc": ["body", "password"], "msg": NOT_VALID_TEXT}]
    assert lookups.asked == []  # refused before the breach check, so before bcrypt too
    assert _stored_hash(email) is None


@pytest.mark.requires_db
@SURROGATE_PASSWORDS
def test_reset_password_refuses_a_password_that_is_not_valid_text(client, range_api, password):
    lookups = range_api(set())
    email = _email()
    _create_user(email, get_password_hash(SHORT))
    with SessionLocal() as db:
        token = auth_account_service.issue_password_reset_token(
            db, db.query(User).filter(User.email == email).one()
        )
    before = _stored_hash(email)
    body = _refused(_post_json(client, "/api/auth/reset-password", {"token": token, "new_password": password}), 422)
    assert body["detail"] == [{"type": "value_error", "loc": ["body", "new_password"], "msg": NOT_VALID_TEXT}]
    assert lookups.asked == []
    assert _stored_hash(email) == before
    assert _login(client, email, SHORT).status_code == 200


@pytest.mark.requires_db
@SURROGATE_PASSWORDS
def test_change_password_refuses_a_new_password_that_is_not_valid_text(client, range_api, password):
    lookups = range_api(set())
    email = _email()
    _create_user(email, get_password_hash(SHORT))
    before = _stored_hash(email)
    resp = _post_json(
        client,
        "/api/auth/change-password",
        {"current_password": SHORT, "new_password": password},
        Authorization=f"Bearer {create_access_token(data={'sub': email})}",
    )
    body = _refused(resp, 422)
    assert body["detail"] == [{"type": "value_error", "loc": ["body", "new_password"], "msg": NOT_VALID_TEXT}]
    assert lookups.asked == []
    assert _stored_hash(email) == before


@pytest.mark.requires_db
def test_login_and_the_current_password_check_refuse_a_password_that_is_not_valid_text(client):
    # Neither applies the policy (a stored hash from any earlier rule keeps signing in), so each refuses as for any
    # wrong password: no hash was ever made from a password bcrypt could not encode.
    email = _email()
    _create_user(email, get_password_hash(SHORT))
    surrogate = MARK + "-long-enough\ud800-tail"
    login = _refused(_post_json(client, "/api/auth/login", {"email": email, "password": surrogate}), 401)
    assert login == {"detail": "Incorrect email or password"}
    client.cookies.clear()
    change = _post_json(
        client,
        "/api/auth/change-password",
        {"current_password": surrogate, "new_password": SHORT + "-next"},
        Authorization=f"Bearer {create_access_token(data={'sub': email})}",
    )
    assert _refused(change, 400) == {"detail": "Current password is incorrect."}


@pytest.mark.requires_db
@pytest.mark.parametrize(
    "path, payload, detail",
    [
        ("/api/auth/reset-password", {"token": "tok\ud800", "new_password": SHORT + "-next"},
         "Invalid or expired reset link."),
        ("/api/auth/verify-email", {"token": "tok\ud800"}, "Invalid or expired verification link."),
    ],
    ids=["reset-password", "verify-email"],
)
def test_an_account_token_that_is_not_valid_text_is_refused_as_unknown(client, path, payload, detail):
    # No minted token holds a lone surrogate (they are URL-safe ASCII), so the lookup refuses it as it refuses any
    # unknown token, where its hash's encode raised a 500 before E97.
    resp = _post_json(client, path, payload)
    assert (resp.status_code, resp.json()) == (400, {"detail": detail}), resp.text


@pytest.mark.requires_db
def test_an_invite_that_is_not_valid_text_is_no_invite(client, monkeypatch):
    # Invite-only registration reads the invite before anything else; one holding a lone surrogate is refused as any
    # invalid invite is, where its hash's encode raised a 500 before E97.
    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    payload = {**ACCOUNT_AGREEMENT, "email": _email(), "password": SHORT + "-next", "invite_code": "inv\ud800"}
    surrogate, unknown = (
        _post_json(client, "/api/auth/register", payload),
        _post_json(client, "/api/auth/register", {**payload, "email": _email(), "invite_code": "inv"}),
    )
    assert surrogate.status_code != 500, surrogate.text
    assert (surrogate.status_code, surrogate.json()) == (unknown.status_code, unknown.json())


@pytest.mark.requires_db
@pytest.mark.parametrize(
    "path, raw, detail",
    [
        # A missing field's `input` is the whole body, the password beside it.
        (
            "/api/auth/register",
            json.dumps({**ACCOUNT_AGREEMENT, "password": MARK + "-long-enough-pass"}),
            [{"type": "missing", "loc": ["body", "email"], "msg": "Field required"}],
        ),
        (
            "/api/auth/register",
            json.dumps({**ACCOUNT_AGREEMENT, "email": "short@example.com", "password": MARK}),
            [{"type": "value_error", "loc": ["body", "password"],
              "msg": f"Value error, Password must be at least {settings.PASSWORD_MIN_LENGTH} characters."}],
        ),
        # A body of the wrong shape is the `input` of the one error it raises.
        (
            "/api/auth/login",
            json.dumps([{"email": "list@example.com", "password": MARK + "-long-enough-pass"}]),
            [{"type": "model_attributes_type", "loc": ["body"],
              "msg": "Input should be a valid dictionary or object to extract fields from"}],
        ),
        # Malformed JSON: its decoder's message went out as `ctx`.
        (
            "/api/auth/login",
            MALFORMED_JSON,
            [{"type": "json_invalid", "loc": ["body", len(MALFORMED_JSON)], "msg": "JSON decode error"}],
        ),
    ],
    ids=["missing-field", "under-the-floor", "wrong-shape", "malformed-json"],
)
def test_a_refused_request_s_422_keeps_type_loc_and_msg_only(client, path, raw, detail):
    resp = client.post(path, content=raw, headers={"content-type": "application/json"})
    assert _refused(resp, 422)["detail"] == detail


@pytest.fixture
def sentry_items():
    # The API's own Sentry options with a transport that keeps every item (test_never_echo_environment_values.py).
    from tests.unit.test_never_echo_environment_values import _capturing

    yield from _capturing("_sentry_options")


def _send_refused_passwords(client: TestClient) -> list:
    under_the_floor = {**ACCOUNT_AGREEMENT, "email": _email(), "password": MARK + "\ud800"}
    return [
        _post_json(client, "/api/auth/register", under_the_floor),  # answered 500 before E97
        _post_json(client, "/api/auth/register", {**ACCOUNT_AGREEMENT, "password": MARK + "-pass"}),  # quoted the body
    ]


# What a Sentry event carries of a request's body is the event scrubber's (its denylist withholds `password`,
# `new_password` and `current_password`; test_never_echo_environment_values.py holds it), not this section's: Sentry
# starts here after the app is built, so the integration attaches no body to these events. These two cases hold the
# channels the 500 used. Two cases, observed before E97: while a Sentry client was active, the API's log line of the 500 printed no exception
# chain and its Sentry event carried the RequestValidationError, whose text prints each error's `input`; with none
# active, the log line's traceback printed it. Each channel is read in the configuration that sent the password there.
@pytest.mark.requires_db
def test_a_refused_password_reaches_no_log_line(client, caplog):
    caplog.set_level(logging.DEBUG)
    answers = _send_refused_passwords(client)
    formatter = logging.Formatter()
    logged = [
        record.getMessage() + (formatter.formatException(record.exc_info) if record.exc_info else "")
        for record in caplog.records
    ]
    assert logged, "the capture saw no log line: it would pass with nothing to read"
    assert [line for line in logged if MARK in line] == []
    for answer in answers:
        _refused(answer, 422)


@pytest.mark.requires_db
def test_a_refused_password_reaches_no_sentry_item(client, sentry_items):
    answers = _send_refused_passwords(client)
    sentry_sdk.flush()
    assert sentry_items, "the capture kept no item: it would pass with nothing to read"
    assert [item for item in sentry_items if MARK in json.dumps(item, default=str)] == []
    for answer in answers:
        _refused(answer, 422)


# The pure function main.py answers RequestValidationError with, on the error shapes pydantic writes.
def test_public_validation_errors_drop_everything_but_type_loc_and_msg():
    errors = [
        {"type": "missing", "loc": ("body", "email"), "msg": "Field required", "input": {"password": MARK}},
        {"type": "value_error", "loc": ("body", "password"), "msg": "Value error, no.", "input": MARK,
         "ctx": {"error": ValueError(MARK)}, "url": "https://errors.pydantic.dev/x", "later_key": MARK},
        {"type": "json_invalid", "loc": ("body", 12), "msg": "JSON decode error", "input": {}, "ctx": {"error": MARK}},
    ]
    assert auth_validation.public_validation_errors(errors) == [
        {"type": "missing", "loc": ["body", "email"], "msg": "Field required"},
        {"type": "value_error", "loc": ["body", "password"], "msg": "Value error, no."},
        {"type": "json_invalid", "loc": ["body", 12], "msg": "JSON decode error"},
    ]


def test_public_validation_errors_never_raise_on_an_odd_error():
    # A raise here would chain the RequestValidationError, whose text prints every input, into the 500's log line.
    odd = [None, "text", {"type": "x", "loc": None, "msg": None, "input": MARK}, {"loc": "body", "input": MARK}]
    assert auth_validation.public_validation_errors(odd) == [
        {"type": "", "loc": [], "msg": ""},
        {"type": "", "loc": [], "msg": ""},
        {"type": "x", "loc": [], "msg": "None"},
        {"type": "", "loc": [], "msg": ""},
    ]


def test_public_validation_errors_return_only_text_utf8_can_carry():
    # A dict key from the body lands in `loc` (an extra field, a mapping's key), and a validator's message may quote
    # what it was handed; each lone surrogate becomes "?", so the answer always renders.
    errors = [{"type": "extra_forbidden", "loc": ("body", "k\ud800", 3), "msg": "m\udfff"}]
    public = auth_validation.public_validation_errors(errors)
    assert public == [{"type": "extra_forbidden", "loc": ["body", "k?", 3], "msg": "m?"}]
    json.dumps(public, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize(
    "text, valid",
    [("plain", True), ("пароль", True), ("\U0001F510", True), ("a\ud800", False), ("\udc00z", False),
     ("\ud83d\udd10", False)],  # a pair only json.loads joins; as two code points it is two lone surrogates
    ids=["ascii", "cyrillic", "astral", "lone-high", "lone-low", "unjoined-pair"],
)
def test_is_valid_unicode(text, valid):
    assert auth_validation.is_valid_unicode(text) is valid
    password = text + "x" * settings.PASSWORD_MIN_LENGTH  # over the floor, whatever it is, so only the text decides
    if valid:
        assert validate_password_strength(password) == password
    else:
        with pytest.raises(ValueError, match="not valid text"):
            validate_password_strength(password)


# ── every path to bcrypt goes through _bcrypt_input ─────────────────────────

BACKEND_DIR = Path(__file__).resolve().parents[2]
PASSWORD_UTILS = "app/services/password_utils.py"
# bcrypt itself, and passlib, whose bcrypt handler hands bcrypt whatever password it is given.
BCRYPT_LIBRARIES = {"bcrypt", "passlib"}


def _sanctioned_bcrypt_use(name: ast.Name, parent: dict[ast.AST, ast.AST]) -> str | None:
    """The bcrypt function a ``bcrypt`` name in ``password_utils`` reaches the sanctioned way, else
    None: ``bcrypt.gensalt``, or a ``bcrypt.hashpw``/``bcrypt.checkpw`` call whose first argument
    is ``_bcrypt_input(...)``."""
    attribute = parent.get(name)
    if not isinstance(attribute, ast.Attribute):
        return None
    if attribute.attr == "gensalt":
        return "gensalt"
    call = parent.get(attribute)
    first = call.args[0] if isinstance(call, ast.Call) and call.func is attribute and call.args else None
    if (
        attribute.attr in {"hashpw", "checkpw"}
        and isinstance(first, ast.Call)
        and isinstance(first.func, ast.Name)
        and first.func.id == "_bcrypt_input"
    ):
        return attribute.attr
    return None


def _bcrypt_reach(source: str, rel: str) -> tuple[list[int], set[str]]:
    """One walk of ``source``, the backend file at ``rel``: the lines that can reach bcrypt without
    ``_bcrypt_input``, and the bcrypt functions it calls the sanctioned way."""
    tree = ast.parse(source)
    home = rel == PASSWORD_UTILS
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    bypasses: list[int] = []
    sanctioned: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                library = alias.name.split(".")[0]
                # Only a plain ``import bcrypt`` keeps every use spelled ``bcrypt.<fn>`` for the check below.
                plain_bcrypt = alias.name == "bcrypt" and alias.asname is None
                if library in BCRYPT_LIBRARIES and not (home and (plain_bcrypt or library == "passlib")):
                    bypasses.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            library = (node.module or "").split(".")[0] if node.level == 0 else ""
            if library in BCRYPT_LIBRARIES:
                if not (home and library == "passlib"):
                    bypasses.append(node.lineno)
            elif any(alias.name in BCRYPT_LIBRARIES for alias in node.names):
                bypasses.append(node.lineno)  # password_utils' bcrypt picked up as a re-export
        elif isinstance(node, ast.Call):
            func = node.func
            called = getattr(func, "id", None) or getattr(func, "attr", "")  # f(...) or m.f(...)
            first = node.args[0] if node.args else None
            if (
                called in {"__import__", "import_module"}
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.split(".")[0] in BCRYPT_LIBRARIES
            ):
                bypasses.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in BCRYPT_LIBRARIES and not home:
            bypasses.append(node.lineno)  # ``password_utils.bcrypt``
        elif home and isinstance(node, ast.Name) and node.id == "bcrypt":
            use = _sanctioned_bcrypt_use(node, parent)
            if use is None:
                bypasses.append(node.lineno)
            else:
                sanctioned.add(use)
    return bypasses, sanctioned


OTHER = "app/services/api_keys.py"
# (case, file, source, "flag" | "clean" | "gap"); a gap is a bypass the walk cannot see, named above.
BCRYPT_REACH_FORMS = [
    ("import-elsewhere", OTHER, "import bcrypt", "flag"),
    ("import-alias-elsewhere", OTHER, "import bcrypt as b", "flag"),
    ("from-import-elsewhere", OTHER, "from bcrypt import checkpw", "flag"),
    ("passlib-elsewhere", OTHER, "from passlib.context import CryptContext", "flag"),
    ("passlib-module-elsewhere", OTHER, "import passlib.hash", "flag"),
    ("re-export-import", OTHER, "from app.services.password_utils import bcrypt", "flag"),
    ("re-export-attribute", OTHER, "password_utils.bcrypt.checkpw(secret.encode(), h)", "flag"),
    ("import-module-constant", OTHER, "importlib.import_module('bcrypt')", "flag"),
    ("dunder-import-constant", OTHER, "__import__('passlib.hash')", "flag"),
    ("raw-hash-at-home", PASSWORD_UTILS, "bcrypt.hashpw(password.encode('utf-8'), salt)", "flag"),
    ("raw-verify-at-home", PASSWORD_UTILS, "def f(s, h):\n    return bcrypt.checkpw(s.encode(), h)", "flag"),
    ("keyword-at-home", PASSWORD_UTILS, "bcrypt.hashpw(password=_bcrypt_input(p), salt=s)", "flag"),
    ("extended-after-cut", PASSWORD_UTILS, "bcrypt.hashpw(_bcrypt_input(p) + pepper, s)", "flag"),
    ("reference-at-home", PASSWORD_UTILS, "check = bcrypt.checkpw", "flag"),
    ("getattr-at-home", PASSWORD_UTILS, "getattr(bcrypt, 'hashpw')(raw, salt)", "flag"),
    ("from-import-at-home", PASSWORD_UTILS, "from bcrypt import hashpw", "flag"),
    ("alias-at-home", PASSWORD_UTILS, "import bcrypt as _b", "flag"),
    ("hash-at-home", PASSWORD_UTILS, "import bcrypt\nbcrypt.hashpw(_bcrypt_input(p), s)", "clean"),
    ("verify-at-home", PASSWORD_UTILS, "bcrypt.checkpw(_bcrypt_input(p), h.encode('utf-8'))", "clean"),
    ("gensalt-at-home", PASSWORD_UTILS, "bcrypt.gensalt(rounds=BCRYPT_ROUNDS)", "clean"),
    ("passlib-import-at-home", PASSWORD_UTILS, "from passlib.context import CryptContext", "clean"),
    ("helpers-elsewhere", OTHER, "from app.services.password_utils import get_password_hash", "clean"),
    ("library-names-as-strings", OTHER, "CryptContext(schemes=['bcrypt'])\nx = ('passlib', 'passlib')", "clean"),
    ("variable-import", OTHER, "importlib.import_module(name)", "gap"),
    ("getattr-elsewhere", OTHER, "getattr(password_utils, 'bcrypt')", "gap"),
    ("sys-modules", OTHER, "sys.modules['bcrypt']", "gap"),
    ("passlib-at-home", PASSWORD_UTILS, "CryptContext(schemes=['bcrypt']).verify(plain, h)", "gap"),
]


@pytest.mark.parametrize(
    "rel,source,expected", [form[1:] for form in BCRYPT_REACH_FORMS], ids=[form[0] for form in BCRYPT_REACH_FORMS]
)
def test_the_bcrypt_walk_scores_every_planted_form(rel, source, expected):
    bypasses, _ = _bcrypt_reach(source, rel)
    assert bool(bypasses) == (expected == "flag")


def test_every_path_to_bcrypt_goes_through_bcrypt_input():
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=BACKEND_DIR, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    scanned = [rel for rel in tracked if not rel.startswith("tests/")]
    assert len(scanned) > 100 and PASSWORD_UTILS in scanned  # a broken walk must not pass as clean
    offenders: list[str] = []
    for rel in scanned:
        bypasses, sanctioned = _bcrypt_reach((BACKEND_DIR / rel).read_text(encoding="utf-8"), rel)
        offenders.extend(f"{rel}:{line}" for line in bypasses)
        if rel == PASSWORD_UTILS:
            assert {"hashpw", "checkpw"} <= sanctioned, "password_utils no longer hashes and verifies"
    assert not offenders, (
        f"bcrypt reached without _bcrypt_input: {offenders}. Hash and verify passwords through "
        "app.services.password_utils (get_password_hash, verify_password); inside it, pass "
        "_bcrypt_input(...) as the first argument of every bcrypt.hashpw/bcrypt.checkpw call."
    )
