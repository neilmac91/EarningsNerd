"""Gate: no policy-valid password reaches bcrypt over its 72-byte limit (CLAUDE.md rule 12).

The policy (``validate_password_strength``) caps a password at 128 CHARACTERS, up to 512 UTF-8
bytes; bcrypt reads only the first 72 BYTES. bcrypt 4 dropped the rest silently, but bcrypt 5
(pinned in requirements.txt) raises ``ValueError`` instead, and nothing above the hash catches it:
register, reset-password and change-password answered 500 for a long passphrase or for about 37
non-ASCII characters, and login refused such a password even against the hash bcrypt 4 had made.

``password_utils`` now hands bcrypt the first 72 bytes of the UTF-8 encoding in both
``get_password_hash`` and ``verify_password``, exactly what bcrypt 4 hashed, so every stored hash
keeps verifying and there is no new hash format. Bytes past 72 do not contribute to the hash.

Real endpoints against the app's SQLite database, like the rest of the auth suite. SQLite hands
``DateTime(timezone=True)`` columns back naive while PostgreSQL hands them back aware; the
``_postgres_shaped_expiries`` fixture gives the reset-token expiry the production shape.
"""
import uuid
from datetime import timezone
from unittest.mock import AsyncMock

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.services import auth_account_service, password_utils
from app.services.password_utils import get_password_hash, validate_password_strength, verify_password
from tests.support.summary_stream_harness import reset_rate_limiters

ASCII_87 = "correct horse battery staple " * 3  # 87 chars, 87 bytes  # gitleaks:allow
CYRILLIC_42 = "пароль" * 7  # 42 chars, 84 bytes  # gitleaks:allow
ASCII_72 = "a1b2c3d4" * 9  # 72 chars, exactly 72 bytes  # gitleaks:allow
STRADDLE = "x" * 71 + "é" + "tail"  # "é" is bytes 72-73, so the limit cuts it in half  # gitleaks:allow
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
    legacy_hash = bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4)).decode("utf-8")
    assert verify_password(password, legacy_hash)


# ── the endpoints ────────────────────────────────────────────────────────────

@pytest.mark.requires_db
@LONG_PASSWORDS
def test_register_accepts_a_long_password_and_login_takes_it(client, password):
    email = _email()
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
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


@pytest.mark.requires_db
@LONG_PASSWORDS
def test_login_takes_a_long_password_against_its_bcrypt4_hash(client, password):
    email = _email()
    _create_user(email, bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=4)).decode("utf-8"))
    assert _login(client, email, password).status_code == 200
