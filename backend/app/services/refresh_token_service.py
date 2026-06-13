"""Refresh-token lifecycle: issue, rotate (single-use), and revoke.

Refresh tokens are opaque random strings. Only their SHA-256 hash is stored, so the
database never holds a usable credential. Every refresh rotates the token (the old one is
revoked and points at its replacement); presenting an already-revoked token is treated as a
reuse/theft signal and revokes the user's entire active chain.
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
    """Raised when an already-revoked refresh token is replayed (reuse/theft signal).

    Distinct from the base error because handling it modifies the database (the user's
    active token chain is revoked), so the caller must commit — whereas a missing/expired/
    unknown token makes no writes and must not trigger a commit on unauthenticated traffic.
    """


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


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
    Reuse of a revoked token revokes the user's entire active chain (theft mitigation).
    The caller is responsible for committing the session.
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

    now = datetime.utcnow()

    if token.revoked_at is not None:
        # A revoked token is being replayed — the legitimate holder already rotated it, so
        # this is a stolen/leaked copy. Revoke every active token for the user.
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
    if token is None or token.revoked_at is not None:
        return False
    token.revoked_at = datetime.utcnow()
    return True


def revoke_all_for_user(db: Session, user_id: int) -> int:
    """Revoke all of a user's active refresh tokens. Returns the number revoked."""
    now = datetime.utcnow()
    count = (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )
    return count
