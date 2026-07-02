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

from sqlalchemy.exc import IntegrityError
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
    """Count one failed login for ``email`` (existent or not) and lock it past the threshold."""
    email_hash = _email_hash(email)
    now = datetime.now(timezone.utc)
    row = db.query(LoginAttempt).filter(LoginAttempt.email_hash == email_hash).first()
    if row is None:
        db.add(LoginAttempt(email_hash=email_hash, failed_count=1))
        try:
            db.commit()
            return
        except IntegrityError:
            # A concurrent request inserted the same row first — fall through to increment it.
            db.rollback()
            row = db.query(LoginAttempt).filter(LoginAttempt.email_hash == email_hash).first()
            if row is None:
                return
    # Start a fresh window when either (a) a prior lock has fully expired, or (b) the last failure
    # was longer ago than the lock window. Without (b) failures would accumulate forever, so a user
    # who mistypes once every few weeks (never logging in successfully between) would eventually
    # lock — the retired in-memory limiter was a sliding 15-minute window and never did that.
    # updated_at carries the previous failure's time (onupdate=func.now() bumps it on each commit).
    locked_until = _as_aware(row.locked_until)
    last_failure = _as_aware(row.updated_at)
    if locked_until is not None and locked_until <= now:
        row.failed_count = 0
        row.locked_until = None
    elif (
        locked_until is None
        and last_failure is not None
        and (now - last_failure) > timedelta(seconds=LOCKOUT_SECONDS)
    ):
        row.failed_count = 0
    row.failed_count = (row.failed_count or 0) + 1
    if row.failed_count >= LOCKOUT_THRESHOLD:
        row.locked_until = now + timedelta(seconds=LOCKOUT_SECONDS)
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
