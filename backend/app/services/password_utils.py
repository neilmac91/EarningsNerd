"""Password hashing + policy (bcrypt) — extracted from the auth router (roadmap S3).

Pure crypto/policy helpers, no HTTP concern. Re-exported by ``app.routers.auth`` so the endpoints,
the Pydantic validators, and the existing test imports keep the same surface. Moved verbatim; since
then hash and verify cut the password to bcrypt's 72-byte limit themselves (``_bcrypt_input``).
"""
from __future__ import annotations

import secrets

import bcrypt

from app.config import settings

# bcrypt work factor — pinned explicitly rather than relying on the library default so the cost
# is visible and stable across bcrypt upgrades.
BCRYPT_ROUNDS = 12
# Generous upper bound in characters (NIST 800-63B: accept long passphrases); up to 512 UTF-8 bytes.
PASSWORD_MAX_LENGTH = 128
# bcrypt reads only the first 72 bytes of a password. bcrypt 4 dropped the rest silently; bcrypt 5
# raises ValueError instead, so hash and verify cut the input here (see ``_bcrypt_input``).
BCRYPT_MAX_PASSWORD_BYTES = 72


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


def _bcrypt_input(password: str) -> bytes:
    """The bytes bcrypt reads: the UTF-8 encoding cut to bcrypt's 72-byte limit.

    Exactly bcrypt 4's implicit truncation, so every stored hash keeps verifying and there is no
    new hash format; bytes past 72 do not contribute to the hash. The cut may split a multibyte
    character, as bcrypt 4's did. Breach screening sees the whole password and, when the cut drops
    anything, :func:`bcrypt_screen_texts` as well.
    """
    return password.encode('utf-8')[:BCRYPT_MAX_PASSWORD_BYTES]


def bcrypt_screen_texts(password: str) -> tuple[str, ...]:
    """What breach screening checks besides the whole password, when the 72-byte cut drops anything.

    A password over the limit authenticates with its first 72 bytes alone, so any breached text that
    shares those bytes logs in to the account, whatever tail the user typed after it. The first text
    is the shortest whole-character prefix that covers all 72 bytes: it shares bcrypt's key exactly.
    When byte 72 falls inside a multibyte character, that prefix ends with the whole split character
    (its kept bytes are part of the key), and the whole characters before the split are screened too:
    a breached prefix there is one partial character (one to three bytes) away from the key. The first
    text is the whole password when the password ends on the split character, so the caller skips a
    text equal to the password. Empty when the password fits, since the whole password is then
    exactly what is hashed. Out of reach: another character that shares the split character's kept
    bytes (``"À"`` for ``"é"``) also opens the account; exact-match screening checks the user's own.
    """
    encoded = password.encode('utf-8')
    if len(encoded) <= BCRYPT_MAX_PASSWORD_BYTES:
        return ()
    # Valid UTF-8 cut short can only end in part of one character, which 'ignore' drops.
    before_split = encoded[:BCRYPT_MAX_PASSWORD_BYTES].decode('utf-8', errors='ignore')
    if len(before_split.encode('utf-8')) == BCRYPT_MAX_PASSWORD_BYTES:  # the cut falls between characters
        return (before_split,)
    return (password[: len(before_split) + 1], before_split)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password - supports both bcrypt and passlib formats"""
    if not hashed_password:
        return False
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
    """Hash password using bcrypt with an explicitly-pinned work factor."""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(_bcrypt_input(password), salt)
    return hashed.decode('utf-8')


# A fixed bcrypt hash of a random value. On login for an unknown email we verify the supplied
# password against this so the request does the same expensive bcrypt work as a known-email
# request — removing the timing side-channel that would otherwise reveal whether an email exists.
_DUMMY_PASSWORD_HASH = get_password_hash(secrets.token_urlsafe(32))
