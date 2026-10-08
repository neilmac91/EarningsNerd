"""Password-account persistence behind ``/api/auth``: the account lookup, registration, the single-use
email-verification and password-reset tokens, and the writes around a password login, reset or change.

Moved out of ``app.routers.auth`` so the router stays HTTP only
(``tests/unit/test_router_orm_ceilings_allowlist.py``). The router keeps every HTTP concern: rate
limits, Turnstile, the invite gate, the breached-password check, the bcrypt calls (off the event
loop), cookies, mail, audit rows and telemetry. Only a token's SHA-256 is stored; the raw value
travels in the emailed link. The two token exceptions are what the router maps to its 400s.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InviteCode, User
from app.services import invite_service, login_lockout, subscription_sync
from app.services.refresh_token_service import revoke_all_for_user

EMAIL_VERIFY_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_HOURS = 1


class AccountTokenInvalidError(Exception):
    """No account holds this verification or reset token (unknown, or already used)."""


class AccountTokenExpiredError(Exception):
    """The token names an account, but its expiry has passed."""


class ReverseTrialError(Exception):
    """Granting or committing the reverse trial failed; the grant was rolled back. ``__cause__`` is
    the original error."""


def _generate_token() -> tuple[str, str]:
    """Return (raw_token_to_email, sha256_hash_to_store). Never store the raw token."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def find_user_by_email(db: Session, email: str) -> Optional[User]:
    """The account for ``email`` (normalised by the request schema), or None. One query, no writes.

    The auth dependencies await this through ``run_in_threadpool``: pool checkout can wait, and
    keeping it off the event loop lets other requests finish and run their request-owned Session
    cleanup, returning pool slots (lessons/ops-auth-lookups-must-let-request-cleanup-progress.md).
    """
    return db.query(User).filter(User.email == email).first()


def create_password_account(
    db: Session,
    *,
    email: str,
    hashed_password: str,
    full_name: Optional[str],
    invite: Optional[InviteCode],
) -> Optional[User]:
    """Create and commit an unverified password account; None when no account may result.

    ``invite`` is the closed-beta invite the register handler already validated (None in public
    mode). None covers a lost redemption race and a lost concurrent-create race for the same email;
    the caller answers both with its opaque response.
    """
    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        email_verified=False,
    )
    db.add(user)
    try:
        db.flush()
        # Closed beta: consume the (already-validated) single-use invite in the SAME transaction as
        # the insert and tag the user beta-eligible, so the 100%-off promo applies at checkout. A
        # lost redemption race rolls the account back too (the invite's single-use invariant holds),
        # and a failed insert never burns an invite.
        if invite is not None:
            if not invite_service.redeem_invite(db, invite, user, commit=False):
                db.rollback()
                return None
            user.is_beta = True
        db.commit()
        db.refresh(user)
    except IntegrityError:
        # Lost a concurrent-create race for the same email — stay opaque (treat as existing).
        db.rollback()
        return None
    return user


def issue_email_verification_token(db: Session, user: User) -> str:
    """Store a new verification token's hash with its 24-hour expiry, commit, and return the raw
    token for the link. It replaces any earlier token, so only the latest link works."""
    raw_token, hashed = _generate_token()
    user.email_verification_token = hashed
    user.email_verification_expires = datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFY_EXPIRY_HOURS)
    db.commit()
    return raw_token


def record_password_login(db: Session, user: User, email: str) -> None:
    """A successful password login: reset the account's lockout and stamp ``last_login_at``,
    committed together (see ``login_lockout.clear_failures``)."""
    login_lockout.clear_failures(db, email)  # a successful login resets the lockout
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()


def verify_email_token(db: Session, raw_token: str) -> User:
    """Mark the account holding ``raw_token`` verified, burn the token and commit.

    Raises :class:`AccountTokenInvalidError` for an unknown or used token and
    :class:`AccountTokenExpiredError` for an expired one; neither writes anything.
    """
    hashed = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    user = db.query(User).filter(User.email_verification_token == hashed).first()
    if not user:
        raise AccountTokenInvalidError()
    if user.email_verification_expires and user.email_verification_expires < now:
        raise AccountTokenExpiredError()

    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    db.commit()
    return user


def commit_reverse_trial(db: Session, user: User, days: int) -> None:
    """Grant the no-card reverse trial and commit it in its own transaction, so a failure cannot undo
    the verification committed before it. On failure the grant is rolled back and
    :class:`ReverseTrialError` raised from the original error; a failing rollback propagates as is.
    The caller decides eligibility (``entitlements.is_pro_user``)."""
    try:
        subscription_sync.start_reverse_trial(db, user, days)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise ReverseTrialError() from exc


def issue_password_reset_token(db: Session, user: User) -> str:
    """Store a new reset token's hash with its 1-hour expiry, commit, and return the raw token."""
    raw_token, hashed = _generate_token()
    user.password_reset_token = hashed
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_EXPIRY_HOURS)
    db.commit()
    return raw_token


def find_password_reset_user(db: Session, raw_token: str) -> User:
    """The account holding the reset token ``raw_token``. Raises :class:`AccountTokenInvalidError`
    or :class:`AccountTokenExpiredError`; writes nothing."""
    hashed = _hash_token(raw_token)
    now = datetime.now(timezone.utc)

    user = db.query(User).filter(User.password_reset_token == hashed).first()
    if not user:
        raise AccountTokenInvalidError()
    if user.password_reset_expires and user.password_reset_expires < now:
        raise AccountTokenExpiredError()
    return user


def complete_password_reset(db: Session, user: User, hashed_password: str) -> None:
    """Set the new password, burn the reset token, confirm the email, revoke every session, commit."""
    user.hashed_password = hashed_password
    user.password_reset_token = None
    user.password_reset_expires = None
    # The user proved control of their inbox, so confirm the email too.
    user.email_verified = True
    # Reset is account recovery: revoke every existing session so a stolen/active refresh token
    # can't outlive the reset. The attacker is evicted; the legitimate owner logs in fresh.
    revoke_all_for_user(db, user.id)
    db.commit()


def stage_password_change(db: Session, user: User, hashed_password: str) -> None:
    """Set the new password and revoke every refresh token, WITHOUT committing.

    The caller's session re-issue (``issue_session`` → ``refresh_token_service.mint_refresh_token``)
    commits the change, the revocation and this device's new token together, so a failure there
    rolls the whole change back (no password-changed-but-500 inconsistency).
    """
    user.hashed_password = hashed_password
    revoke_all_for_user(db, user.id)
