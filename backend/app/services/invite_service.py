"""Closed-beta invite lifecycle: mint magic links, validate, and single-use redeem.

Tokens follow the email-verification pattern in ``auth.py`` — only the SHA-256 hash is stored; the
raw token lives only in the magic link. Eligibility is recorded on the ``User`` (``is_beta``) at
redemption, so the checkout promo never depends on a client-supplied parameter.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.invite import InviteCode


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(invite: InviteCode) -> bool:
    """tz-safe expiry check (Postgres returns tz-aware, SQLite naive — treat naive as UTC)."""
    exp = invite.expires_at
    if exp is None:
        return False
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < _now()


def build_invite_link(raw_token: str) -> str:
    return f"{settings.FRONTEND_URL}/register?invite={raw_token}"


def mint_invite(
    db: Session,
    *,
    created_by: Optional[int],
    email: Optional[str] = None,
    expires_in_hours: Optional[int] = None,
    cohort: Optional[str] = None,
) -> tuple[InviteCode, str, str]:
    """Create an invite and return (row, raw_token, magic_link). The raw token is shown once."""
    raw = secrets.token_urlsafe(32)
    hours = expires_in_hours or settings.INVITE_EXPIRY_HOURS
    invite = InviteCode(
        code_hash=_hash_token(raw),
        email=(email.strip().lower() if email else None),
        cohort=((cohort.strip() or None) if cohort else None),
        expires_at=_now() + timedelta(hours=hours),
        created_by=created_by,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite, raw, build_invite_link(raw)


def hash_invite_token(raw: str) -> str:
    """The stored form of an invite token. Callers that must carry an invite across a redirect
    (the OAuth state row) keep this hash, never the raw token."""
    return _hash_token(raw)


def validate_invite(db: Session, raw_token: Optional[str], email: str) -> Optional[InviteCode]:
    """Return a usable invite for this registration, or None if it's missing / invalid / revoked /
    already used / expired / bound to a different email. Never raises on a bad token."""
    if not raw_token:
        return None
    return validate_invite_hash(db, _hash_token(raw_token), email)


def validate_invite_hash(db: Session, code_hash: Optional[str], email: str) -> Optional[InviteCode]:
    """``validate_invite`` for a caller holding only the token's hash (see ``hash_invite_token``)."""
    if not code_hash:
        return None
    invite = db.query(InviteCode).filter(InviteCode.code_hash == code_hash).first()
    if invite is None or invite.is_revoked or invite.used_at is not None or _is_expired(invite):
        return None
    if invite.email and invite.email.strip().lower() != (email or "").strip().lower():
        return None
    return invite


def redeem_invite(db: Session, invite: InviteCode, user, *, commit: bool = True) -> bool:
    """Atomically mark a single-use invite redeemed for ``user``. Returns False if a concurrent
    registration already consumed it (guarded ``UPDATE ... WHERE used_at IS NULL``).

    ``commit=False`` leaves the UPDATE in the caller's open transaction, so a registration commits
    (or rolls back) the new account and the redemption together."""
    result = db.execute(
        update(InviteCode)
        .where(InviteCode.id == invite.id, InviteCode.used_at.is_(None))
        .values(used_at=_now(), user_id=user.id)
    )
    if commit:
        db.commit()
    return result.rowcount == 1
