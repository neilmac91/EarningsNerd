"""Social sign-in persistence behind ``/api/auth/{google,apple}`` and ``/api/auth/connections``.

Moved out of ``app.routers.auth`` so the router stays HTTP only
(``tests/unit/test_router_orm_ceilings_allowlist.py``): the single-use OAuth state rows, the
new-account gate and creation, resolving a provider identity to a User (existing link, linkable
verified account, or new account), the refresh-token commit that closes a sign-in, and listing or
unlinking providers. The router keeps the HTTP side: rate limits, the state cookies and their HMAC,
the provider token exchange and id-token verification, redirects, mail and audit rows. Refusals
reach it as the small exceptions below, carrying the ``/login?error=`` code where there is one.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import InviteCode, OAuthAccount, OAuthState, User
from app.services import invite_service, refresh_token_service

logger = logging.getLogger(__name__)

# Lifetime of an OAuth state row; the router gives its state cookies the same max-age.
OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes


class OAuthSignInRefused(Exception):
    """The provider identity may not sign in; ``error_code`` is the ``/login?error=`` value."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


class OAuthAccountConflictError(Exception):
    """The sign-in's commit lost a concurrent first-sign-in race (IntegrityError); rolled back."""


class ProviderNotLinkedError(Exception):
    """The user has no link for the provider being unlinked."""


class LastSignInMethodError(Exception):
    """Unlinking the provider would leave the user with no way to sign in."""


# ─── New accounts (shared by Google and Apple) ─────────────────────────────────

def oauth_new_account_gate(
    db: Session, *, email: str, email_verified: bool, invite_code_hash: Optional[str]
) -> tuple[Optional[str], Optional[InviteCode]]:
    """Decide whether a social sign-in may create a NEW User (linking is decided by the callers).

    Returns ``(error_code, invite)``. ``error_code`` is None when creation may proceed, else the
    ``/login?error=`` code to redirect with: ``email_unverified`` when the provider has not verified
    the address (an unverified claim never seeds an account), ``invite_required`` when
    REGISTRATION_MODE is invite_only and the sign-in carries no valid invite. ``invite`` is the
    validated invite the caller must redeem in the SAME transaction as the insert (None in public
    mode). Mirrors the register() gate; tests/unit/test_oauth_invite_gate.py keeps every ``User(``
    construction on the account-creation paths behind it.
    """
    if not email_verified:
        return "email_unverified", None
    if settings.REGISTRATION_MODE != "invite_only":
        return None, None
    invite = invite_service.validate_invite_hash(db, invite_code_hash, email)
    if invite is None:
        return "invite_required", None
    return None, invite


def oauth_create_account(
    db: Session,
    *,
    provider: str,
    email: str,
    full_name: Optional[str],
    email_verified: bool,
    invite_code_hash: Optional[str],
) -> tuple[Optional[User], Optional[str]]:
    """Create the User for a first social sign-in, or say why not.

    Returns ``(user, None)`` with the row flushed but not committed (``mint_oauth_refresh_token``
    commits it together with the provider link and the session), or ``(None, error_code)`` after
    rolling back. When invite-only mode requires an invite it is consumed here, inside the same
    transaction, so a lost redemption race never leaves an account behind.
    """
    error_code, invite = oauth_new_account_gate(
        db, email=email, email_verified=email_verified, invite_code_hash=invite_code_hash
    )
    if error_code:
        return None, error_code
    user = User(email=email, full_name=full_name, hashed_password=None, email_verified=email_verified)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # Lost a concurrent first-sign-in race for the same email.
        db.rollback()
        logger.warning("%s OAuth IntegrityError creating account", provider)
        return None, f"{provider}_account_conflict"
    if invite is not None:
        if not invite_service.redeem_invite(db, invite, user, commit=False):
            db.rollback()
            return None, "invite_required"
        user.is_beta = True
    return user, None


# ─── Single-use state rows ─────────────────────────────────────────────────────

def store_oauth_state(db: Session, state: str, nonce: str, invite_code_hash: Optional[str]) -> None:
    """Stage a single-use ``state`` row (10-minute TTL) after GC-ing expired rows; the caller commits.

    Apple always needs one (its form_post callback is checked against the row's nonce); Google only
    when the sign-in carries an invite, which rides on the row as its hash so the callback can
    validate and redeem it. Naive UTC throughout (see the OAuthState model) so the comparison is
    naive-vs-naive on both Postgres and SQLite.
    """
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)
    db.add(OAuthState(
        state=state,
        nonce=nonce,
        invite_code_hash=invite_code_hash,
        expires_at=now + timedelta(seconds=OAUTH_STATE_TTL_SECONDS),
    ))


def consume_oauth_state(db: Session, state: str) -> Optional[tuple[str, Optional[str]]]:
    """Delete the row for ``state`` and return its ``(nonce, invite_code_hash)``, or None when the
    state is unknown or expired (an expired row is deleted too). Single-use by construction."""
    row = db.query(OAuthState).filter_by(state=state).first()
    if row is None:
        return None
    live = row.expires_at >= datetime.utcnow()
    nonce, invite_code_hash = row.nonce, row.invite_code_hash
    db.delete(row)
    db.commit()
    return (nonce, invite_code_hash) if live else None


def live_invite_hash(db: Session, invite: Optional[str]) -> Optional[str]:
    """The hash of ``invite`` when it names a usable invite, else None: an OAuth start persists
    nothing for an unknown, revoked, used or expired token (the callback then sees no invite)."""
    if not invite:
        return None
    code_hash = invite_service.hash_invite_token(invite)
    return code_hash if invite_service.invite_hash_is_live(db, code_hash) else None


def save_google_state(db: Session, state: str, invite: Optional[str]) -> None:
    """Commit a state row carrying the invite's hash when ``invite`` is live; otherwise persist
    nothing (a plain Google sign-in needs no row: its state rides in the SameSite=Lax cookie)."""
    invite_code_hash = live_invite_hash(db, invite)
    if invite_code_hash is not None:
        # The nonce column is NOT NULL but unused for Google (no OIDC nonce in this flow).
        store_oauth_state(db, state, secrets.token_urlsafe(32), invite_code_hash)
        db.commit()


def save_apple_state(db: Session, state: str, raw_nonce: str, invite: Optional[str]) -> None:
    """Commit Apple's state row: the raw nonce its callback checks, plus the invite's hash when live."""
    store_oauth_state(db, state, raw_nonce, live_invite_hash(db, invite))
    db.commit()


# ─── Resolving a provider identity to a User ───────────────────────────────────

def resolve_google_user(
    db: Session,
    *,
    subject: str,
    email: str,
    email_verified: bool,
    full_name: Optional[str],
    invite_code_hash: Optional[str],
) -> tuple[User, bool]:
    """Return ``(user, linked_existing)`` for a verified Google identity, with the provider link (if
    new) and ``last_login_at`` staged for ``mint_oauth_refresh_token`` to commit.

    Order: existing link → existing account (linked only when both sides verified the email; else
    ``google_account_conflict``, since a new insert would hit the UNIQUE constraint) → new account
    through the gate. Raises :class:`OAuthSignInRefused` with the redirect's error code.
    """
    oauth_row = (
        db.query(OAuthAccount)
        .filter_by(provider="google", provider_account_id=subject)
        .first()
    )

    linked_existing = False
    if oauth_row:
        user = oauth_row.user
    else:
        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            # Link to an existing account only when both sides have a verified email; otherwise a
            # new insert would hit the UNIQUE constraint.
            if not (existing.email_verified and email_verified):
                raise OAuthSignInRefused("google_account_conflict")
            user = existing
            linked_existing = True
        else:
            user, error_code = oauth_create_account(
                db,
                provider="google",
                email=email,
                full_name=full_name,
                email_verified=email_verified,
                invite_code_hash=invite_code_hash,
            )
            if user is None:
                raise OAuthSignInRefused(error_code)
        db.add(OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=subject,
            provider_email=email,
        ))

    user.last_login_at = datetime.now(timezone.utc)
    return user, linked_existing


def resolve_apple_user(
    db: Session,
    *,
    subject: str,
    email: Optional[str],
    email_verified: bool,
    full_name: Optional[str],
    invite_code_hash: Optional[str],
) -> tuple[User, bool]:
    """Return ``(user, linked_existing)`` for a verified Apple identity, with the provider link (if
    new), a first-authorization name fill-in and ``last_login_at`` staged for
    ``mint_oauth_refresh_token`` to commit.

    Order: existing link → existing verified account → new account. Without an existing link Apple
    must supply an email (``apple_missing_claims``); an existing account that cannot be safely
    linked is ``apple_account_conflict``. Raises :class:`OAuthSignInRefused` with the error code.
    """
    oauth_row = db.query(OAuthAccount).filter_by(
        provider="apple", provider_account_id=subject
    ).first()

    linked_existing = False
    if oauth_row:
        user_obj = oauth_row.user
        if full_name and not user_obj.full_name:
            user_obj.full_name = full_name
    else:
        if not email:
            # No email and no existing link — can't create an account
            raise OAuthSignInRefused("apple_missing_claims")

        existing = db.query(User).filter(func.lower(User.email) == email).first()
        if existing:
            if existing.email_verified and email_verified:
                user_obj = existing
                linked_existing = True
                if full_name and not user_obj.full_name:
                    user_obj.full_name = full_name
            else:
                # Email exists but can't be safely linked (unverified on either side).
                # Attempting a new insert would hit the UNIQUE constraint.
                raise OAuthSignInRefused("apple_account_conflict")
        else:
            user_obj, error_code = oauth_create_account(
                db,
                provider="apple",
                email=email,
                full_name=full_name,
                email_verified=email_verified,
                invite_code_hash=invite_code_hash,
            )
            if user_obj is None:
                raise OAuthSignInRefused(error_code)

        db.add(OAuthAccount(
            user_id=user_obj.id,
            provider="apple",
            provider_account_id=subject,
            provider_email=email,
        ))

    user_obj.last_login_at = datetime.now(timezone.utc)
    return user_obj, linked_existing


def mint_oauth_refresh_token(
    db: Session, user: User, *, user_agent: Optional[str], ip: Optional[str]
) -> str:
    """Mint and commit the sign-in's refresh token, committing what the resolve staged with it (a
    new account and redeemed invite, the provider link, ``last_login_at``). Returns the raw token.

    A concurrent first sign-in for the same identity loses here with ``IntegrityError`` (the token's
    flush or the commit): the session is rolled back and :class:`OAuthAccountConflictError` raised.
    """
    try:
        return refresh_token_service.mint_refresh_token(db, user, user_agent=user_agent, ip=ip)
    except IntegrityError:
        db.rollback()
        raise OAuthAccountConflictError() from None


# ─── Connections ───────────────────────────────────────────────────────────────

def list_oauth_accounts(db: Session, user_id: int) -> list[OAuthAccount]:
    """The user's linked provider identities."""
    return db.query(OAuthAccount).filter(OAuthAccount.user_id == user_id).all()


def unlink_oauth_provider(db: Session, user: User, provider: str) -> None:
    """Delete the user's link for ``provider`` and commit, unless it is their last sign-in method.

    Raises :class:`ProviderNotLinkedError` when there is no such link and
    :class:`LastSignInMethodError` when removing it would leave neither a password nor another link.
    """
    rows = list_oauth_accounts(db, user.id)
    target = next((r for r in rows if r.provider == provider), None)
    if not target:
        raise ProviderNotLinkedError()

    # Lockout guard: after removing this provider the user must keep at least one credential
    # (a password or another linked provider).
    remaining = (1 if user.hashed_password else 0) + (len(rows) - 1)
    if remaining < 1:
        raise LastSignInMethodError()

    db.delete(target)
    db.commit()
