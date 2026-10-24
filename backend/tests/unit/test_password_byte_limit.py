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

Real endpoints against the app's SQLite database, like the rest of the auth suite. SQLite hands
``DateTime(timezone=True)`` columns back naive while PostgreSQL hands them back aware; the
``_postgres_shaped_expiries`` fixture gives the reset-token expiry the production shape.
"""
import ast
import asyncio
import hashlib
import subprocess
import uuid
from datetime import timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bcrypt
import pytest
from tests.support.account_agreement import ACCOUNT_AGREEMENT

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm.attributes import set_committed_value

from main import app
from app.config import settings
from app.database import SessionLocal
from app.models import User
from app.routers.auth import create_access_token
from app.services import auth_account_service, password_utils, pwned_passwords
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
