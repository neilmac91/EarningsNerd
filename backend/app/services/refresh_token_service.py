"""Refresh-token lifecycle: issue, rotate (single-use), and revoke.

Refresh tokens are opaque random strings. Only their SHA-256 hash is stored, so the
database never holds a usable credential. Every refresh rotates the token (the old one is
revoked and points at its replacement); presenting a token that was already rotated away is
treated as a reuse/theft signal and revokes the user's entire active chain. A token revoked any
other way (logout, logout-all, a password change or reset, or that theft sweep) is simply refused.

Each write of a user's tokens (a rotation, a revocation, the sweep) first takes the account's users
row lock and reads what it writes under it, so two of them for one user run one after the other, on
one API instance or across both (``_lock_user_tokens``).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models import RefreshToken, User

logger = logging.getLogger(__name__)


class RefreshTokenError(Exception):
    """Raised when a refresh token is missing, invalid, or expired."""


class RefreshTokenReuseError(RefreshTokenError):
    """Raised when a rotated-away refresh token is replayed (reuse/theft signal).

    Distinct from the base error because handling it modifies the database (the user's
    active token chain is revoked), so the caller must commit — whereas a missing/expired/
    unknown token makes no writes and must not trigger a commit on unauthenticated traffic.
    """


def _lock_user_tokens(db: Session, user_id: int) -> None:
    """Take ``user_id``'s users row lock for the rest of the caller's transaction.

    Every writer of a user's refresh tokens takes it before it reads the tokens it writes. Two
    refreshes with one cookie both read the token live otherwise, and both mint a successor. A
    refresh racing a logout or logout-all writes on its stale read, leaving a live successor. A
    guarded UPDATE alone would not stop the logout-all case: its bulk UPDATE sees only rows committed
    when it starts, so a successor committed after that survives it. The lock makes the second
    writer wait for the first's commit, and the reads it then makes see that commit (READ
    COMMITTED). FOR NO KEY UPDATE: it serializes these writers but not the foreign-key checks of
    inserts elsewhere that name the user. Unbounded, as the holders are short transactions, and a
    timeout would turn a moment's wait into a failed refresh. SQLite ignores it."""
    db.query(User.id).filter(User.id == user_id).with_for_update(key_share=True).first()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    # Peppered with SECRET_KEY: a bare SHA-256 of an IPv4 is brute-forceable (the ~4.2B address
    # space is precomputable), so the secret is what makes the stored hash non-reversible.
    return hashlib.sha256(f"{ip}:{settings.SECRET_KEY}".encode("utf-8")).hexdigest()


def create_refresh_token(
    db: Session,
    user: User,
    *,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> Tuple[RefreshToken, str]:
    """Mint and persist a new refresh token for ``user``; return ``(token, raw_token)``.

    The raw token is returned to the caller (to set as a cookie) and is never stored —
    only its hash is. The flushed ``RefreshToken`` is returned too so callers can link a
    rotation chain without re-querying. The caller is responsible for committing the session.
    """
    raw_token = secrets.token_urlsafe(48)
    token = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=(user_agent or "")[:500] or None,
        ip_hash=_hash_ip(ip),
    )
    db.add(token)
    db.flush()  # assign token.id without forcing the caller's commit boundary
    return token, raw_token


def rotate_refresh_token(
    db: Session,
    raw_token: str,
    *,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> Tuple[User, str]:
    """Validate ``raw_token``, rotate it, and return ``(user, new_raw_token)``.

    Single-use rotation: the presented token is revoked and superseded by a fresh one.
    Raises :class:`RefreshTokenError` if the token is unknown, expired, or already revoked.
    Replaying a token that was already rotated away revokes the user's entire active chain and
    raises :class:`RefreshTokenReuseError` (theft mitigation); a token revoked without rotation
    writes nothing. The caller is responsible for committing the session.
    """
    if not raw_token:
        raise RefreshTokenError("Missing refresh token")

    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash_token(raw_token))
        .first()
    )
    if token is None:
        raise RefreshTokenError("Unknown refresh token")
    _lock_user_tokens(db, token.user_id)
    db.refresh(token)  # read again under the lock: a rotation or revocation committed since shows here

    now = datetime.utcnow()

    if token.revoked_at is not None:
        if token.replaced_by_id is None:
            # Revoked without rotation (logout, logout-all, a password change or reset, or the
            # theft sweep below): its holder was signed out, nobody holds a successor, and the
            # token grants nothing. Refusing it is enough; sweeping would only revoke the sessions
            # the user signed in to since.
            raise RefreshTokenError("Refresh token has been revoked")
        # A rotated-away token is being replayed — the legitimate holder already rotated it, so
        # this is a stolen/leaked copy. Revoke every active token for the user. The sweep is
        # user-wide, so it also ends sessions minted after a later reset or logout-all
        # (lessons/arch-only-a-rotated-refresh-token-signals-theft.md).
        revoked = revoke_all_for_user(db, token.user_id)
        logger.warning(
            "Refresh token reuse detected for user_id=%s; revoked %s active token(s)",
            token.user_id,
            revoked,
        )
        raise RefreshTokenReuseError("Refresh token has already been used")

    if token.expires_at < now:
        raise RefreshTokenError("Refresh token has expired")

    user = db.query(User).filter(User.id == token.user_id).first()
    if user is None or not user.is_active:
        raise RefreshTokenError("User is no longer active")

    new_token, new_raw_token = create_refresh_token(db, user, user_agent=user_agent, ip=ip)
    token.revoked_at = now
    # Link the rotation chain for auditability / reuse detection (no extra query needed —
    # the flushed replacement already has its id).
    token.replaced_by_id = new_token.id

    return user, new_raw_token


def revoke_refresh_token(db: Session, raw_token: Optional[str]) -> bool:
    """Revoke a single refresh token (e.g. on logout). Returns True if one was revoked.

    Idempotent and best-effort: unknown or already-revoked tokens return False. The caller
    is responsible for committing the session.
    """
    if not raw_token:
        return False
    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash_token(raw_token))
        .first()
    )
    if token is None:
        return False
    _lock_user_tokens(db, token.user_id)
    db.refresh(token)  # read again under the lock, as a rotation does
    if token.revoked_at is not None:
        return False
    token.revoked_at = datetime.utcnow()
    return True


def revoke_all_for_user(db: Session, user_id: int) -> int:
    """Revoke all of a user's active refresh tokens. Returns the number revoked.

    Under the users row lock, so the bulk UPDATE starts after any rotation of this user's has committed
    and revokes its successor too."""
    _lock_user_tokens(db, user_id)
    now = datetime.utcnow()
    count = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )
    return count


# ─── Committing wrappers for the HTTP layer ────────────────────────────────────
# The functions above leave the commit to their caller. These own it, so app/routers/auth.py
# reaches the session only by handing it over.

def mint_refresh_token(
    db: Session,
    user: User,
    *,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
    commit: bool = True,
) -> str:
    """Mint a refresh token for ``user`` and return its raw value (the cookie).

    Commits by default, together with whatever the caller has pending (a password change, an OAuth
    link). ``commit=False`` leaves the commit to the caller. An ``IntegrityError`` from the flush or
    the commit propagates unchanged; the session then needs the caller's rollback.
    """
    _, raw_token = create_refresh_token(db, user, user_agent=user_agent, ip=ip)
    if commit:
        db.commit()
    return raw_token


def rotate_and_commit(
    db: Session,
    raw_token: str,
    *,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> Tuple[User, str]:
    """Rotate ``raw_token`` and commit; return ``(user, new_raw_token)``.

    A replayed rotated-away token's chain revocation is committed before the same
    :class:`RefreshTokenReuseError` propagates. Any other :class:`RefreshTokenError` made no writes
    and commits nothing.
    """
    try:
        user, new_raw_token = rotate_refresh_token(db, raw_token, user_agent=user_agent, ip=ip)
        db.commit()
    except RefreshTokenReuseError:
        db.commit()
        raise
    return user, new_raw_token


def revoke_and_commit(db: Session, raw_token: Optional[str]) -> bool:
    """Revoke one refresh token (logout) and commit when one was revoked. Returns whether it was."""
    if revoke_refresh_token(db, raw_token):
        db.commit()
        return True
    return False


def revoke_all_and_commit(db: Session, user_id: int) -> int:
    """Revoke all of a user's active refresh tokens (sign out everywhere), commit, return the count."""
    revoked = revoke_all_for_user(db, user_id)
    db.commit()
    return revoked
