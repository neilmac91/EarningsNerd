"""Durable, anti-enumeration per-account failed-login lockout.

Replaces the in-memory ``ACCOUNT_LOGIN_FAIL_LIMITER``. Two properties matter:

- **Durable.** State lives in the ``login_attempts`` table, so the lockout holds across Cloud Run
  instances and survives restarts/deploys. The in-memory limiter was per-process — diluted N-fold
  by autoscaling and wiped on every restart.
- **Anti-enumeration.** Keyed on a hash of the email, *not* the ``User`` row, so a non-existent
  address accumulates failures and locks exactly like a real one. A user-row lockout would return
  429 only for real accounts (401 for unknown emails) — an account-enumeration oracle the login
  path otherwise works hard to avoid.

The email hash is peppered with ``SECRET_KEY`` (a bare SHA-256 of an email is reversible from a
wordlist), so raw emails are never stored.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, case, func, or_
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LoginAttempt

# Mirrors the retired in-memory limiter: 10 failures locks the account for 15 minutes.
LOCKOUT_THRESHOLD = 10
LOCKOUT_SECONDS = 900


def _email_hash(email: str) -> str:
    normalized = (email or "").strip().lower()
    return hashlib.sha256(f"{normalized}:{settings.SECRET_KEY}".encode("utf-8")).hexdigest()


def _as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Postgres returns tz-aware datetimes, SQLite naive — coerce so comparisons are safe on both."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def seconds_until_unlock(db: Session, email: str) -> Optional[int]:
    """If the account is currently locked, return the remaining lock time in seconds (>= 1); else None."""
    row = db.query(LoginAttempt).filter(LoginAttempt.email_hash == _email_hash(email)).first()
    if row is None:
        return None
    locked_until = _as_aware(row.locked_until)
    if locked_until is None:
        return None
    now = datetime.now(timezone.utc)
    if locked_until > now:
        return max(1, int((locked_until - now).total_seconds()))
    return None


def record_failure(db: Session, email: str) -> None:
    """Atomically count one failed login (existent email or not) and commit its lock state.

    The existing primary key serializes concurrent insert/update and success-clear operations.
    This counts completed failures; it does not reserve credential checks already in progress.
    """
    email_hash = _email_hash(email)
    now = datetime.now(timezone.utc)
    expired_lock = and_(LoginAttempt.locked_until.is_not(None), LoginAttempt.locked_until <= now)
    stale_unlocked = and_(
        LoginAttempt.locked_until.is_(None),
        LoginAttempt.updated_at.is_not(None),
        LoginAttempt.updated_at < now - timedelta(seconds=LOCKOUT_SECONDS),
    )
    next_count = case(
        (or_(expired_lock, stale_unlocked), 1),
        else_=func.coalesce(LoginAttempt.failed_count, 0) + 1,
    )
    next_lock = case(
        (next_count >= LOCKOUT_THRESHOLD, now + timedelta(seconds=LOCKOUT_SECONDS)),
        (expired_lock, None),
        else_=LoginAttempt.locked_until,
    )
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": postgres_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise ValueError(f"Unsupported login-lockout database dialect: {dialect}")
    # Omit updated_at on INSERT, retaining its existing server default. On conflict, stamp every
    # failure explicitly, including the net-zero 1 -> reset -> 1 case pinned by the behavior tests.
    statement = insert(LoginAttempt).values(email_hash=email_hash, failed_count=1)
    statement = statement.on_conflict_do_update(
        index_elements=[LoginAttempt.email_hash],
        set_={"failed_count": next_count, "locked_until": next_lock, "updated_at": now},
    )
    db.execute(statement)
    db.commit()


def clear_failures(db: Session, email: str) -> None:
    """Drop any lockout state for ``email`` after a successful login.

    The DELETE runs in the caller's transaction and is deliberately NOT committed here: ``login``
    commits it together with ``last_login_at`` in a single round-trip, so the lockout reset and the
    login timestamp land atomically (two separate commits could half-apply if the server crashed
    between them, and cost an extra round-trip on every successful login)."""
    db.query(LoginAttempt).filter(
        LoginAttempt.email_hash == _email_hash(email)
    ).delete(synchronize_session=False)
