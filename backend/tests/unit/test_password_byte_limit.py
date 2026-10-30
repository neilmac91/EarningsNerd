"""Gate: a new password hash keys on every byte, and every stored bcrypt hash keeps verifying (CLAUDE.md rule 12).

The policy (``validate_password_strength``) caps a password at 128 CHARACTERS, up to 512 UTF-8 bytes; bcrypt
reads only the first 72 BYTES. bcrypt 4 dropped the rest silently, and bcrypt 5 (pinned in requirements.txt)
raises ``ValueError`` instead, which once made register, reset-password and change-password answer 500 for a
long passphrase. Since E97's Argon2id slice a new or changed password is hashed with Argon2id over the whole
password (``get_password_hash``), so a password's tail past byte 72 counts. ``verify_password`` dispatches on
the stored hash's marker: an Argon2id hash is checked over every byte, a bcrypt hash made before then still on
its first 72 (``_bcrypt_input``, exactly what bcrypt 4 hashed), and any other value fails closed before a
library sees it. No login rewrites a hash, so a bcrypt hash changes only when its owner sets a new password.

Breach screening (``pwned_passwords``) looks up the whole password once, since that is what a new hash keys on;
while new hashes were bcrypt it screened their 72-byte prefix too, and the section below holds that such a
prefix now opens nothing. Every hash and check runs on the one password thread (``in_password_thread``), which
bounds the 32 MiB an Argon2 call holds to one call at a time per instance.

Two structural checks hold the paths the behaviour tests cannot reach. In every tracked backend Python file
outside ``tests/``: bcrypt, passlib and argon2 are imported only by ``app/services/password_utils.py``; every
use of ``bcrypt`` there is a ``bcrypt.checkpw`` call whose first argument is ``_bcrypt_input(...)``, so no new
hash is bcrypt (``hashpw`` and ``gensalt`` are bypasses); and every reference to ``get_password_hash`` or
``verify_password`` outside that module is its import or the first argument of an ``in_password_thread(...)``
call. ``HASH_REACH_FORMS`` and ``THREAD_FORMS`` score each walk on each way it can be broken and each
look-alike that must pass. Out of their reach, each planted as a gap: a module named at run time
(``import_module(name)``, ``getattr(module, "bcrypt")``, ``sys.modules``), and passlib inside
``password_utils``, whose legacy-check fallback hands passlib's bcrypt handler the whole password (dead under
bcrypt 5, whose length check fails passlib's self-test; removing it is a separate cleanup).

A password that is not valid text (a lone surrogate) is refused before either (E97): it encodes to no UTF-8, so the
breach check and bcrypt raised on it, and FastAPI's own 422, which quoted every refused value (the whole body for a
missing field), could not render it and answered 500 with a traceback that quoted the password. The section on it
holds each password route at a 422 of type, loc and msg only (``auth_validation.public_validation_errors``, which
``main.py`` answers ``RequestValidationError`` with), login and the current-password check at their usual refusal
against either scheme's hash, and the 500's two channels (the log line, the Sentry event's exception chain) free of
a refused password. An unencodable reset or verification token is refused as unknown, where its hash raised the same
500.

Real endpoints against the app's SQLite database, like the rest of the auth suite. SQLite hands
``DateTime(timezone=True)`` columns back naive while PostgreSQL hands them back aware; the
``_postgres_shaped_expiries`` fixture gives the reset-token expiry the production shape.
"""
import ast
import asyncio
import contextvars
import hashlib
import json
import logging
import subprocess
import threading
import time
import uuid
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bcrypt
import pytest
from argon2 import PasswordHasher, Type, extract_parameters
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
    # Argon2id at its lowest costs: they are irrelevant to what a hash keys on (the costs test restores the pinned ones).
    monkeypatch.setattr(password_utils, "_ARGON2", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
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


_REAL_ARGON2 = password_utils._ARGON2  # the pinned costs, read before the fixture swaps in cheap ones


def _bcrypt4_hash(password: str) -> str:
    """What bcrypt 4 stored for ``password``: the hash of its first 72 bytes."""
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4)).decode("utf-8")


def _first_72_bytes(password: str) -> str:
    """The whole characters of ``password``'s first 72 bytes: what a bcrypt hash of it keys on, near enough."""
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


# ── the hash and verify functions ────────────────────────────────────────────

POLICY_VALID = pytest.mark.parametrize(
    "password",
    [ASCII_87, CYRILLIC_42, ASCII_72, STRADDLE, FOUR_BYTE_MAX],
    ids=["ascii87", "cyrillic84b", "ascii72-boundary", "straddles-byte-72", "max-4-byte-chars"],
)


@POLICY_VALID
def test_every_policy_valid_password_hashes_and_verifies(password):
    assert validate_password_strength(password) == password
    hashed = get_password_hash(password)
    assert hashed.startswith("$argon2id$")  # a new hash is Argon2id, never bcrypt
    assert verify_password(password, hashed)
    assert get_password_hash(password) != hashed  # each hash has its own salt


@POLICY_VALID
def test_every_byte_of_a_new_hash_counts(password):
    """Two passwords that share their first 72 bytes and differ later do not open each other's hash, with a
    multibyte character at the boundary or anywhere else (E97); under bcrypt they did."""
    hashed = get_password_hash(password)
    assert not verify_password(password[:-1] + ("b" if password[-1] != "b" else "c"), hashed)  # the last character
    assert not verify_password(password + "x", hashed)  # a byte past the whole password
    if len(password.encode("utf-8")) > 72:
        assert not verify_password(_first_72_bytes(password), hashed)
        assert not verify_password(_first_72_bytes(password) + " a different tail", hashed)


def test_a_legacy_bcrypt_hash_keys_on_its_first_72_bytes_as_it_always_did():
    hashed = _bcrypt4_hash(ASCII_87)
    assert verify_password(ASCII_87[:72] + " a different tail", hashed)  # bcrypt's documented limit
    assert not verify_password(ASCII_87[:71] + "#" + ASCII_87[72:], hashed)  # byte 72 still counts
    straddle_hash = _bcrypt4_hash(STRADDLE)
    # "ж" starts with a different lead byte than "é", so the half character at byte 72 still counts.
    assert not verify_password("x" * 71 + "ж" + "tail", straddle_hash)


@LONG_PASSWORDS
def test_a_hash_bcrypt4_made_from_a_long_password_still_verifies(password):
    assert verify_password(password, _bcrypt4_hash(password))


@pytest.mark.parametrize("marker", ["$2a$", "$2b$", "$2x$", "$2y$"])
def test_a_legacy_bcrypt_hash_verifies_under_each_marker_and_refuses_a_wrong_password(marker):
    hashed = marker + _bcrypt4_hash(SHORT)[len("$2b$"):]  # as other bcrypt libraries write the same hash
    assert verify_password(SHORT, hashed)
    assert not verify_password("#" + SHORT[1:], hashed)


def test_a_new_hash_refuses_a_wrong_password():
    assert not verify_password("#" + SHORT[1:], get_password_hash(SHORT))
    assert not verify_password("", get_password_hash(SHORT))


# Neither marker: refused before either library is called.
UNKNOWN_HASHES = {
    "empty": "", "none": None, "plaintext": SHORT, "md5-crypt": "$1$saltsalt$qGQ6i1pZJ3p5yH0qC5b8a/",
    "argon2i": lambda: get_password_hash(SHORT).replace("$argon2id$", "$argon2i$", 1),
    "argon2d": lambda: get_password_hash(SHORT).replace("$argon2id$", "$argon2d$", 1),
}
# A marker, then a body its library refuses.
MALFORMED_HASHES = {
    "argon2id-marker-only": "$argon2id$", "argon2id-bad-params": "$argon2id$v=19$m=x,t=1,p=1$c2FsdA$aGFzaA",
    "argon2id-truncated": lambda: get_password_hash(SHORT)[:-6], "bcrypt-garbage": "$2b$12$garbage",
    "bcrypt-unknown-variant": lambda: "$2c$" + _bcrypt4_hash(SHORT)[len("$2b$"):],
}


@pytest.mark.parametrize("stored", list(UNKNOWN_HASHES.values()), ids=list(UNKNOWN_HASHES))
def test_an_unknown_hash_fails_closed_before_any_library(monkeypatch, stored):
    stored = stored() if callable(stored) else stored

    def reached(*_args, **_kwargs):
        raise AssertionError("an unknown hash reached a hashing library")

    monkeypatch.setattr(password_utils.bcrypt, "checkpw", reached)
    monkeypatch.setattr(password_utils, "_ARGON2", SimpleNamespace(verify=reached))
    assert verify_password(SHORT, stored) is False


@pytest.mark.parametrize("stored", list(MALFORMED_HASHES.values()), ids=list(MALFORMED_HASHES))
def test_a_malformed_hash_fails_closed(stored):
    assert verify_password(SHORT, stored() if callable(stored) else stored) is False


def test_new_hashes_and_the_dummy_record_the_pinned_costs(monkeypatch):
    """An unknown email's check costs a new account's: the dummy is Argon2id at the same pinned costs. The costs
    are the measured ones (E97, the PR's benchmark): moving one needs a new measurement against bcrypt-12."""
    monkeypatch.setattr(password_utils, "_ARGON2", _REAL_ARGON2)
    pinned = (Type.ID, password_utils.ARGON2_TIME_COST, password_utils.ARGON2_MEMORY_COST_KIB,
              password_utils.ARGON2_PARALLELISM, 32, 16)
    assert pinned[1:4] == (10, 32 * 1024, 1)
    for hashed in (get_password_hash(SHORT), password_utils._DUMMY_PASSWORD_HASH):
        cost = extract_parameters(hashed)
        assert (cost.type, cost.time_cost, cost.memory_cost, cost.parallelism, cost.hash_len, cost.salt_len) == pinned


def test_password_work_runs_on_its_own_thread_one_call_at_a_time():
    """Every hash and check waits for the one password thread (E97): never the event loop or its default executor,
    never two at once, so one Argon2 call's 32 MiB is the most in flight per instance. The caller's context goes
    with the call, as ``asyncio.to_thread`` carries it."""
    request = contextvars.ContextVar("request", default=None)
    lock, in_flight, peaks, seen = threading.Lock(), [0], [], []

    def work(n: int) -> int:
        with lock:
            in_flight[0] += 1
            peaks.append(in_flight[0])
        seen.append((threading.get_ident(), threading.current_thread().name, request.get()))
        time.sleep(0.02)
        with lock:
            in_flight[0] -= 1
        return n

    async def burst() -> tuple[list[int], int]:
        request.set("req-1")
        done = await asyncio.gather(*(password_utils.in_password_thread(work, n) for n in range(6)))
        return done, threading.get_ident()

    done, loop_thread = asyncio.run(burst())
    assert done == list(range(6))
    assert max(peaks) == 1
    assert loop_thread not in {ident for ident, _, _ in seen}
    assert {name for _, name, _ in seen} == {"password_hash_0"}
    assert {value for _, _, value in seen} == {"req-1"}


# ── the endpoints ────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@LONG_PASSWORDS
def test_register_accepts_a_long_password_and_login_takes_it_whole(client, password):
    email = _email()
    resp = client.post("/api/auth/register", json={**ACCOUNT_AGREEMENT, "email": email, "password": password})
    assert resp.status_code == 200, resp.text
    assert _stored_hash(email).startswith("$argon2id$")
    assert _login(client, email, password).status_code == 200
    assert _login(client, email, _first_72_bytes(password)).status_code == 401  # the tail counts


@pytest.mark.requires_db
@LONG_PASSWORDS
def test_reset_password_accepts_a_long_password_and_login_takes_it_whole(client, password):
    email = _email()
    _create_user(email, _bcrypt4_hash(SHORT))
    with SessionLocal() as db:
        token = auth_account_service.issue_password_reset_token(
            db, db.query(User).filter(User.email == email).one()
        )
    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": password})
    assert resp.status_code == 200, resp.text
    assert _stored_hash(email).startswith("$argon2id$")  # a reset from a legacy hash stores the new format
    assert _login(client, email, password).status_code == 200
    assert _login(client, email, _first_72_bytes(password)).status_code == 401
    assert _login(client, email, SHORT).status_code == 401


@pytest.mark.requires_db
@LONG_PASSWORDS
def test_change_password_accepts_a_long_password_and_login_takes_it_whole(client, password):
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
    assert _stored_hash(email).startswith("$argon2id$")
    client.cookies.clear()
    assert _login(client, email, password).status_code == 200
    assert _login(client, email, _first_72_bytes(password)).status_code == 401
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
    assert _stored_hash(email).startswith("$argon2id$")  # the changed password is the new format
    client.cookies.clear()
    assert _login(client, email, SHORT).status_code == 200


@pytest.mark.requires_db
@pytest.mark.parametrize("scheme", ["argon2id", "bcrypt"])
def test_a_login_rewrites_no_hash(client, scheme):
    """Neither a refused nor a successful login writes the stored hash: no upgrade on a legacy login (E97), so no
    new write races a password change's check that the hash is still the one it verified."""
    email = _email()
    stored = get_password_hash(SHORT) if scheme == "argon2id" else _bcrypt4_hash(SHORT)
    _create_user(email, stored)
    assert _login(client, email, "#" + SHORT[1:]).status_code == 401
    assert _stored_hash(email) == stored
    assert _login(client, email, SHORT).status_code == 200
    assert _stored_hash(email) == stored


# ── breach screening sees what a new hash keys on: the whole password ────────

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
    "password",
    [ASCII_72, ASCII_87, CYRILLIC_42, STRADDLE, THREE_BYTE_STRADDLE, FOUR_BYTE_STRADDLE, FOUR_BYTE_MAX],
    ids=["ascii72", "ascii87", "cyrillic84b", "straddles-byte-72", "3-byte-char-straddles-byte-72",
         "4-byte-char-straddles-byte-72", "max-4-byte-chars"],
)
def test_screening_looks_up_the_whole_password_once(range_api, password):
    api = range_api({"password123"})
    assert asyncio.run(pwned_passwords.is_password_pwned(password)) is False
    assert api.asked == [hashlib.sha1(password.encode("utf-8")).hexdigest().upper()[:5]]


def test_a_breached_password_is_screened_as_breached(range_api):
    api = range_api({BREACHED_72})
    assert asyncio.run(pwned_passwords.is_password_pwned(BREACHED_72)) is True
    assert len(api.asked) == 1


@pytest.mark.parametrize(
    "password, breached",
    [
        (BREACHED_72 + " and a tail nobody listed", BREACHED_72),
        # Byte 72 splits "é": under bcrypt the breached text ending with the whole "é" shared the key.
        (BREACHED_71 + "é tail", BREACHED_71 + "é"),
        (BREACHED_71 + "é tail", BREACHED_71),
    ],
    ids=["breached-72-byte-prefix", "breached-text-ending-in-the-split-character",
         "breached-prefix-before-a-split-character"],
)
def test_a_breached_prefix_behind_an_unlisted_tail_passes_and_opens_nothing(range_api, password, breached):
    """While new hashes were bcrypt such a prefix opened the account, so screening checked it too. A new hash keys
    on every byte (E97): the prefix opens nothing, so the whole password, unlisted, passes in one lookup."""
    api = range_api({breached})
    assert asyncio.run(pwned_passwords.is_password_pwned(password)) is False
    assert len(api.asked) == 1
    assert not verify_password(breached, get_password_hash(password))


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
    assert len(asked) == 1  # one timeout, then fail open


@pytest.mark.requires_db
def test_register_takes_a_breached_prefix_behind_an_unlisted_tail_and_the_prefix_opens_nothing(client, range_api):
    range_api({BREACHED_72})
    email, password = _email(), BREACHED_72 + " and a tail nobody listed"
    resp = client.post("/api/auth/register", json={**ACCOUNT_AGREEMENT, "email": email, "password": password})
    assert resp.status_code == 200, resp.text
    assert _login(client, email, BREACHED_72).status_code == 401
    assert _login(client, email, password).status_code == 200


@pytest.mark.requires_db
def test_register_refuses_a_breached_password(client, range_api):
    range_api({BREACHED_72})
    resp = client.post("/api/auth/register", json={**ACCOUNT_AGREEMENT, "email": _email(), "password": BREACHED_72})
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
    assert lookups.asked == []  # refused before the breach check, so before the hash too
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
@pytest.mark.parametrize("scheme", ["argon2id", "bcrypt"])
def test_login_and_the_current_password_check_refuse_a_password_that_is_not_valid_text(client, scheme):
    # Neither applies the policy (a stored hash from any earlier rule keeps signing in), so each refuses as for any
    # wrong password, against either scheme's hash: no hash was ever made from a password UTF-8 cannot encode.
    email = _email()
    _create_user(email, get_password_hash(SHORT) if scheme == "argon2id" else _bcrypt4_hash(SHORT))
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


# ── every path to a password hash goes through password_utils, on the password thread ───────

BACKEND_DIR = Path(__file__).resolve().parents[2]
PASSWORD_UTILS = "app/services/password_utils.py"
# bcrypt itself, passlib, whose bcrypt handler hands bcrypt whatever password it is given, and argon2.
HASH_LIBRARIES = {"bcrypt", "passlib", "argon2"}
# Libraries password_utils may import by any form; bcrypt it imports only as a plain ``import bcrypt``.
HOME_LIBRARIES = {"passlib", "argon2"}
# password_utils' own hasher, legacy check and thread: reached from elsewhere, each skips the dispatch or the bound.
PRIVATE = {"_ARGON2", "_verify_bcrypt", "_bcrypt_input", "_PASSWORD_THREADS"}


def _sanctioned_bcrypt_use(name: ast.Name, parent: dict[ast.AST, ast.AST]) -> str | None:
    """The bcrypt function a ``bcrypt`` name in ``password_utils`` reaches the sanctioned way, else None: a
    ``bcrypt.checkpw`` call whose first argument is ``_bcrypt_input(...)``, a legacy hash's check. No new hash is
    bcrypt since E97, so ``bcrypt.hashpw`` and ``bcrypt.gensalt`` are bypasses."""
    attribute = parent.get(name)
    if not isinstance(attribute, ast.Attribute):
        return None
    call = parent.get(attribute)
    first = call.args[0] if isinstance(call, ast.Call) and call.func is attribute and call.args else None
    if (
        attribute.attr == "checkpw"
        and isinstance(first, ast.Call)
        and isinstance(first.func, ast.Name)
        and first.func.id == "_bcrypt_input"
    ):
        return "checkpw"
    return None


def _hash_reach(source: str, rel: str) -> tuple[list[int], set[str]]:
    """One walk of ``source``, the backend file at ``rel``: the lines that can reach a hashing library other than
    through ``password_utils``' own functions, and the bcrypt functions it calls the sanctioned way."""
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
                if library in HASH_LIBRARIES and not (home and (plain_bcrypt or library in HOME_LIBRARIES)):
                    bypasses.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            library = (node.module or "").split(".")[0] if node.level == 0 else ""
            if library in HASH_LIBRARIES:
                if not (home and library in HOME_LIBRARIES):
                    bypasses.append(node.lineno)
            elif any(alias.name in HASH_LIBRARIES or (alias.name in PRIVATE and not home) for alias in node.names):
                bypasses.append(node.lineno)  # password_utils' library or helper picked up as a re-export
        elif isinstance(node, ast.Call):
            func = node.func
            called = getattr(func, "id", None) or getattr(func, "attr", "")  # f(...) or m.f(...)
            first = node.args[0] if node.args else None
            if (
                called in {"__import__", "import_module"}
                and isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.split(".")[0] in HASH_LIBRARIES
            ):
                bypasses.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in HASH_LIBRARIES | PRIVATE and not home:
            bypasses.append(node.lineno)  # ``password_utils.bcrypt``, ``password_utils._ARGON2``
        elif home and isinstance(node, ast.Name) and node.id == "bcrypt":
            use = _sanctioned_bcrypt_use(node, parent)
            if use is None:
                bypasses.append(node.lineno)
            else:
                sanctioned.add(use)
    return bypasses, sanctioned


OTHER = "app/services/api_keys.py"
# (case, file, source, "flag" | "clean" | "gap"); a gap is a bypass the walk cannot see, named above.
HASH_REACH_FORMS = [
    ("import-elsewhere", OTHER, "import bcrypt", "flag"),
    ("import-alias-elsewhere", OTHER, "import bcrypt as b", "flag"),
    ("from-import-elsewhere", OTHER, "from bcrypt import checkpw", "flag"),
    ("passlib-elsewhere", OTHER, "from passlib.context import CryptContext", "flag"),
    ("passlib-module-elsewhere", OTHER, "import passlib.hash", "flag"),
    ("argon2-elsewhere", OTHER, "from argon2 import PasswordHasher", "flag"),
    ("argon2-module-elsewhere", OTHER, "import argon2.low_level", "flag"),
    ("re-export-import", OTHER, "from app.services.password_utils import bcrypt", "flag"),
    ("re-export-attribute", OTHER, "password_utils.bcrypt.checkpw(secret.encode(), h)", "flag"),
    ("private-hasher-elsewhere", OTHER, "password_utils._ARGON2.hash(secret)", "flag"),
    ("private-hasher-import", OTHER, "from app.services.password_utils import _ARGON2", "flag"),
    ("private-legacy-check-import", OTHER, "from app.services.password_utils import _verify_bcrypt", "flag"),
    ("private-thread-elsewhere", OTHER, "loop.run_in_executor(password_utils._PASSWORD_THREADS, f)", "flag"),
    ("import-module-constant", OTHER, "importlib.import_module('bcrypt')", "flag"),
    ("dunder-import-constant", OTHER, "__import__('passlib.hash')", "flag"),
    ("argon2-import-module-constant", OTHER, "importlib.import_module('argon2')", "flag"),
    ("new-bcrypt-hash-at-home", PASSWORD_UTILS, "import bcrypt\nbcrypt.hashpw(_bcrypt_input(p), s)", "flag"),
    ("bcrypt-salt-at-home", PASSWORD_UTILS, "bcrypt.gensalt(rounds=12)", "flag"),
    ("raw-hash-at-home", PASSWORD_UTILS, "bcrypt.hashpw(password.encode('utf-8'), salt)", "flag"),
    ("raw-verify-at-home", PASSWORD_UTILS, "def f(s, h):\n    return bcrypt.checkpw(s.encode(), h)", "flag"),
    ("keyword-at-home", PASSWORD_UTILS, "bcrypt.checkpw(password=_bcrypt_input(p), hashed_password=h)", "flag"),
    ("extended-after-cut", PASSWORD_UTILS, "bcrypt.checkpw(_bcrypt_input(p) + pepper, h)", "flag"),
    ("reference-at-home", PASSWORD_UTILS, "check = bcrypt.checkpw", "flag"),
    ("getattr-at-home", PASSWORD_UTILS, "getattr(bcrypt, 'checkpw')(raw, h)", "flag"),
    ("from-import-at-home", PASSWORD_UTILS, "from bcrypt import checkpw", "flag"),
    ("alias-at-home", PASSWORD_UTILS, "import bcrypt as _b", "flag"),
    ("verify-at-home", PASSWORD_UTILS, "bcrypt.checkpw(_bcrypt_input(p), h.encode('utf-8'))", "clean"),
    ("passlib-import-at-home", PASSWORD_UTILS, "from passlib.context import CryptContext", "clean"),
    ("argon2-import-at-home", PASSWORD_UTILS, "from argon2 import PasswordHasher, Type", "clean"),
    ("argon2-exceptions-at-home", PASSWORD_UTILS, "from argon2.exceptions import VerificationError", "clean"),
    ("helpers-elsewhere", OTHER, "from app.services.password_utils import get_password_hash", "clean"),
    ("library-names-as-strings", OTHER, "CryptContext(schemes=['bcrypt'])\nx = ('passlib', 'argon2')", "clean"),
    ("variable-import", OTHER, "importlib.import_module(name)", "gap"),
    ("getattr-elsewhere", OTHER, "getattr(password_utils, 'bcrypt')", "gap"),
    ("sys-modules", OTHER, "sys.modules['bcrypt']", "gap"),
    ("passlib-at-home", PASSWORD_UTILS, "CryptContext(schemes=['bcrypt']).verify(plain, h)", "gap"),
]


@pytest.mark.parametrize(
    "rel,source,expected", [form[1:] for form in HASH_REACH_FORMS], ids=[form[0] for form in HASH_REACH_FORMS]
)
def test_the_hash_walk_scores_every_planted_form(rel, source, expected):
    bypasses, _ = _hash_reach(source, rel)
    assert bool(bypasses) == (expected == "flag")


def _scanned() -> list[str]:
    tracked = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=BACKEND_DIR, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    scanned = [rel for rel in tracked if not rel.startswith("tests/")]
    assert len(scanned) > 100 and PASSWORD_UTILS in scanned  # a broken walk must not pass as clean
    return scanned


def test_every_path_to_a_password_hash_goes_through_password_utils():
    offenders: list[str] = []
    for rel in _scanned():
        bypasses, sanctioned = _hash_reach((BACKEND_DIR / rel).read_text(encoding="utf-8"), rel)
        offenders.extend(f"{rel}:{line}" for line in bypasses)
        if rel == PASSWORD_UTILS:
            assert sanctioned == {"checkpw"}, "password_utils no longer checks legacy bcrypt hashes"
    assert not offenders, (
        f"A hashing library reached outside password_utils' functions: {offenders}. Hash and verify passwords "
        "through app.services.password_utils (get_password_hash, verify_password); inside it, a new hash is "
        "Argon2id, and bcrypt is only a legacy hash's check: bcrypt.checkpw(_bcrypt_input(...), ...)."
    )


# get_password_hash and verify_password, which run a hash: only ever on the password thread.
PASSWORD_WORK = {"get_password_hash", "verify_password"}


def _off_the_password_thread(source: str, rel: str) -> tuple[list[int], int]:
    """One walk of ``source``, an app file other than ``password_utils``: the lines that run a password hash or
    check anywhere but the password thread, and how many times it hands one there. A reference to
    ``get_password_hash`` or ``verify_password`` passes only as the first argument of an ``in_password_thread(...)``
    call (or the name in an import that keeps it); any other (a call, ``asyncio.to_thread`` or
    ``run_in_threadpool``, a sync unit that calls it, an alias) is flagged."""
    tree = ast.parse(source)
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    flagged: list[int] = []
    handed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            flagged.extend(node.lineno for alias in node.names if alias.name in PASSWORD_WORK and alias.asname)
            continue
        name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
        if name not in PASSWORD_WORK:
            continue
        call = parent.get(node)
        to = (getattr(call.func, "id", None) or getattr(call.func, "attr", None)) if isinstance(call, ast.Call) else None
        if to == "in_password_thread" and call.args and call.args[0] is node:
            handed += 1
        else:
            flagged.append(node.lineno)
    return flagged, handed


THREAD_FORMS = [
    ("on-the-loop", OTHER, "ok = verify_password(p, h)", "flag"),
    ("default-executor", OTHER, "h = await asyncio.to_thread(get_password_hash, p)", "flag"),
    ("thread-pool", OTHER, "ok = await run_in_threadpool(verify_password, p, h)", "flag"),
    ("sync-unit", OTHER, "def unit():\n    return get_password_hash(p)", "flag"),
    ("reference", OTHER, "check = verify_password", "flag"),
    ("module-attribute", OTHER, "h = password_utils.get_password_hash(p)", "flag"),
    ("aliased-import", OTHER, "from app.services.password_utils import verify_password as check", "flag"),
    ("by-keyword", OTHER, "await in_password_thread(work=get_password_hash)", "flag"),
    ("not-the-work", OTHER, "await in_password_thread(log, verify_password)", "flag"),
    ("password-thread", OTHER, "h = await in_password_thread(get_password_hash, p)", "clean"),
    ("password-thread-attribute", OTHER,
     "ok = await password_utils.in_password_thread(password_utils.verify_password, p, h)", "clean"),
    ("import", OTHER, "from app.services.password_utils import get_password_hash, verify_password", "clean"),
    ("getattr", OTHER, "getattr(password_utils, 'verify_password')(p, h)", "gap"),
]


@pytest.mark.parametrize(
    "rel,source,expected", [form[1:] for form in THREAD_FORMS], ids=[form[0] for form in THREAD_FORMS]
)
def test_the_thread_walk_scores_every_planted_form(rel, source, expected):
    flagged, _ = _off_the_password_thread(source, rel)
    assert bool(flagged) == (expected == "flag")


def test_every_password_hash_and_check_runs_on_the_password_thread():
    offenders: list[str] = []
    handed: dict[str, int] = {}
    for rel in _scanned():
        if rel == PASSWORD_UTILS:
            continue  # its import-time dummy hash runs before the app serves a request
        flagged, count = _off_the_password_thread((BACKEND_DIR / rel).read_text(encoding="utf-8"), rel)
        offenders.extend(f"{rel}:{line}" for line in flagged)
        if count:
            handed[rel] = count
    # register, login, reset and the change's check and hash: a walk that finds none must not pass as clean.
    assert handed == {"app/routers/auth.py": 5}, handed
    assert not offenders, (
        f"A password hash or check off the password thread: {offenders}. Await it as "
        "in_password_thread(get_password_hash, ...) or in_password_thread(verify_password, ...): one thread "
        "bounds Argon2id's 32 MiB a call to one call at a time per instance."
    )
