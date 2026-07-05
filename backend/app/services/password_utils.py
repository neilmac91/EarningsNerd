"""Password hashing + policy (bcrypt) — extracted from the auth router (roadmap S3).

Pure crypto/policy helpers, no HTTP concern. Re-exported by ``app.routers.auth`` so the endpoints,
the Pydantic validators, and the existing test imports keep the same surface. Behavior-preserving:
functions and constants moved verbatim.
"""
from __future__ import annotations

import secrets

import bcrypt

from app.config import settings

# bcrypt work factor — pinned explicitly rather than relying on the library default so the cost
# is visible and stable across bcrypt upgrades.
BCRYPT_ROUNDS = 12
# Generous upper bound (NIST 800-63B: accept long passphrases). Note: bcrypt only considers the
# first 72 bytes of the password; longer inputs are silently truncated by the algorithm.
PASSWORD_MAX_LENGTH = 128


def validate_password_strength(value: str) -> str:
    """Validate a password against policy.

    NIST 800-63B-aligned: enforce length, not arbitrary composition rules (no forced
    upper/lower/digit). Breach screening (HaveIBeenPwned) is done in the endpoints because a
    synchronous Pydantic validator cannot perform the async network call.
    """
    if len(value) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")
    return value


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - supports both bcrypt and passlib formats"""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        try:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with an explicitly-pinned work factor."""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


# A fixed bcrypt hash of a random value. On login for an unknown email we verify the supplied
# password against this so the request does the same expensive bcrypt work as a known-email
# request — removing the timing side-channel that would otherwise reveal whether an email exists.
_DUMMY_PASSWORD_HASH = get_password_hash(secrets.token_urlsafe(32))
