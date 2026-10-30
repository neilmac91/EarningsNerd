"""Password hashing + policy — extracted from the auth router (roadmap S3).

Pure crypto/policy helpers, no HTTP concern. Re-exported by ``app.routers.auth`` so the endpoints,
the Pydantic validators, and the existing test imports keep the same surface.

A new or changed password is hashed with Argon2id over the whole password (E97); ``verify_password``
dispatches on the stored hash's scheme marker. A hash made before then is bcrypt, keyed on the password's
first 72 bytes (``_bcrypt_input``), and keeps verifying exactly as it did; nothing rewrites it on a login,
so it changes only when its owner sets a new password. Every hash and verify runs on the password thread
(``in_password_thread``), never on the event loop or its default executor.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
import secrets
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

import bcrypt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings
from app.services.auth_validation import is_valid_unicode

_T = TypeVar("_T")

# Argon2id's costs, pinned (as bcrypt's work factor was) so a library upgrade cannot move them. Measured on
# one CPU on 2026-10-30 against current guidance (E97): RFC 9106 section 4 picks the memory first, then the
# most passes the time budget allows, and the budget here is bcrypt-12's verify, so an unknown email checked
# against the dummy hash below costs what a bcrypt account's check does. On Python 3.11 with production's pins,
# paired call by call over six processes, nine passes ran 9.5 ms under a bcrypt-12 check at the median (ten ran
# 16.5 ms over); the gap on Cloud Run is unmeasured. 32 MiB is half RFC 9106's second recommended 64 MiB (its
# first needs 2 GiB, past this 1 GiB service) and, at nine passes, over seven times OWASP's minimum
# memory-passes (19 MiB x 2). One lane: on one vCPU more lanes are no faster, and their threads take the CPU
# from the event loop. A hash records its own costs, so changing these leaves every stored hash verifying.
ARGON2_TIME_COST = 9
ARGON2_MEMORY_COST_KIB = 32 * 1024
ARGON2_PARALLELISM = 1
_ARGON2_MARKER = "$argon2id$"
_ARGON2 = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST_KIB,
    parallelism=ARGON2_PARALLELISM,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
# bcrypt's marker: ``$2`` and a variant letter (bcrypt 5 checks ``$2a$``, ``$2b$``, ``$2x$`` and ``$2y$``).
_BCRYPT_MARKER = "$2"
# Generous upper bound in characters (NIST 800-63B: accept long passphrases); up to 512 UTF-8 bytes.
PASSWORD_MAX_LENGTH = 128
# The most a password checked against a stored hash may hold (login, the change's current password): eight times
# what a new password may, so no password a policy let in is refused, and a bound on the bytes the check reads. An
# Argon2id check reads every byte, a bcrypt one 72, so without it a long enough password would make the unknown-email
# dummy measurably slower than a legacy account's check (E97: +54 ms at 30 MB; nothing past 4 KB here).
CHECKED_PASSWORD_MAX_LENGTH = 8 * PASSWORD_MAX_LENGTH
# bcrypt reads only the first 72 bytes of a password. bcrypt 4 dropped the rest silently; bcrypt 5
# raises ValueError instead, so a legacy hash's check cuts the input here (see ``_bcrypt_input``).
BCRYPT_MAX_PASSWORD_BYTES = 72

# One thread for every hash and verify, of either scheme (E97). On the service's one vCPU more threads add no
# throughput, and each Argon2 call in flight holds 32 MiB: measured, 40 logins at once finished sooner on one
# thread than on one each, and held 33 MiB at their peak against 1.28 GiB, more than the 1 GiB instance has.
# A request queues here holding no default-executor thread, which the loop shares with other work.
_PASSWORD_THREADS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="password_hash")


def validate_password_strength(value: str) -> str:
    """Validate a password against policy.

    NIST 800-63B-aligned: enforce length, not arbitrary composition rules (no forced
    upper/lower/digit). Breach screening (HaveIBeenPwned) is done in the endpoints because a
    synchronous Pydantic validator cannot perform the async network call. A password that is not
    valid Unicode (a lone surrogate, which no keyboard types) is refused first: it encodes to no
    UTF-8, so the breach check and the hash would raise on it (``auth_validation``, E97).
    """
    if not is_valid_unicode(value):
        raise ValueError("Password contains a character that is not valid text.")
    if len(value) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")
    return value


def bound_checked_password(value: str | None) -> str | None:
    """A password to check against a stored hash, refused past ``CHECKED_PASSWORD_MAX_LENGTH`` characters.

    A validator, not a field constraint: a constrained ``str`` refuses a lone surrogate itself, where login and the
    current-password check answer such a password as any wrong one (E97). It applies no policy."""
    if value is not None and len(value) > CHECKED_PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {CHECKED_PASSWORD_MAX_LENGTH} characters.")
    return value


def _bcrypt_input(password: str) -> bytes:
    """The bytes a legacy bcrypt hash was keyed on: the UTF-8 encoding cut to bcrypt's 72-byte limit.

    Exactly bcrypt 4's implicit truncation, so every bcrypt hash stored before E97 keeps verifying; bytes
    past 72 never contributed to one. The cut may split a multibyte character, as bcrypt 4's did. No new
    hash is bcrypt: a new or changed password is Argon2id over every byte.
    """
    return password.encode('utf-8')[:BCRYPT_MAX_PASSWORD_BYTES]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check ``plain_password`` against a stored hash by the hash's scheme marker; never raises.

    An Argon2id hash is checked over the whole password, at the costs it records. A bcrypt hash takes the
    check every stored hash took before E97, unchanged (``_verify_bcrypt``). Anything else (empty, another
    Argon2 variant or scheme, garbage) fails closed before any library sees it. A password that is not valid
    text, which login does not validate, is a miss, and so is anything but text on either side, as it was when every
    value reached the bcrypt check and its ``except``.
    """
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str) or not hashed_password:
        return False
    if hashed_password.startswith(_ARGON2_MARKER):
        try:
            return _ARGON2.verify(hashed_password, plain_password)
        except (VerificationError, InvalidHashError, UnicodeEncodeError):  # a mismatch, a malformed hash
            return False
    if hashed_password.startswith(_BCRYPT_MARKER):
        return _verify_bcrypt(plain_password, hashed_password)
    return False


def _verify_bcrypt(plain_password: str, hashed_password: str) -> bool:
    """A legacy bcrypt hash's check, as ``verify_password`` ran it for every hash before E97."""
    try:
        return bcrypt.checkpw(_bcrypt_input(plain_password), hashed_password.encode('utf-8'))
    except Exception:
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    """An Argon2id hash of the whole password, at the pinned costs, with its own random salt."""
    return _ARGON2.hash(password)


async def in_password_thread(work: Callable[..., _T], *args: object) -> _T:
    """``asyncio.to_thread(work, *args)`` on the password thread, with the same context copy."""
    call = functools.partial(contextvars.copy_context().run, work, *args)
    return await asyncio.get_running_loop().run_in_executor(_PASSWORD_THREADS, call)


# A fixed Argon2id hash of a random value, at the same costs. On login for an unknown email the supplied
# password is checked against it, so the request performs comparable expensive work to reduce timing
# differences between known and unknown accounts. A legacy bcrypt check's timing may still differ (see
# the costs above); the gap is measured on one CPU and remains unmeasured on Cloud Run.
_DUMMY_PASSWORD_HASH = get_password_hash(secrets.token_urlsafe(32))
