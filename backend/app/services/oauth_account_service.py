"""Social sign-in persistence behind ``/api/auth/{google,apple}`` and ``/api/auth/connections``.

Moved out of ``app.routers.auth`` so the router stays HTTP only
(``tests/unit/test_router_orm_ceilings_allowlist.py``): the single-use OAuth state rows, the
new-account gate and creation, resolving a provider identity to a User (existing link, linkable
verified account, or new account), the commit that closes a sign-in (with its refresh token, or with
its one-time session handoff when the start asked for one, and that handoff's redemption: E29 (5)),
and listing or unlinking providers. The router keeps the HTTP
side: rate limits, the state, handoff and session cookies and the state cookies' HMAC, the provider
token exchange and id-token verification, redirects, mail and audit rows. Refusals reach it as the
small exceptions below, carrying the ``/login?error=`` code where there is one.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import InviteCode, OAuthAccount, OAuthState, SessionHandoff, User
from app.services import invite_service, refresh_token_service
from app.services.account_agreement_service import (
    AcceptedAccountAgreement, AgreementRequired, require_current_agreement, stage_account_agreement,
)
from app.services.legal_readiness_service import is_collection_available
from app.utils.datetimes import utcnow

# Lifetime of an OAuth state row; the router gives its state cookies the same max-age.
OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes
# Lifetime of a sign-in's session handoff (E29 (5)); the router gives the binding cookie the same max-age. The
# landing page posts its code as it loads, so two minutes covers a slow connection, and a code that leaked (it
# rides in a URL fragment, which no request log records) is dead soon after.
SESSION_HANDOFF_TTL_SECONDS = 120
# The longest code or binder a redemption reads: each is ``secrets.token_urlsafe(32)``, 43 ASCII characters.
_HANDOFF_SECRET_MAX_LENGTH = 128


class OAuthSignInRefused(Exception):
    """The provider identity may not sign in; ``error_code`` is the ``/login?error=`` value.

    ``lost_create_race`` marks a new account's insert that lost a concurrent first sign-in for the
    same email (already rolled back): the router logs that case before redirecting.
    """

    def __init__(self, error_code: str, *, lost_create_race: bool = False) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.lost_create_race = lost_create_race


class OAuthAccountConflictError(Exception):
    """The sign-in's commit lost a concurrent first-sign-in race (IntegrityError); rolled back."""


class ProviderNotLinkedError(Exception):
    """The user has no link for the provider being unlinked."""


class LastSignInMethodError(Exception):
    """Unlinking the provider would leave the user with no way to sign in."""


# ─── New accounts (shared by Google and Apple) ─────────────────────────────────

def oauth_new_account_gate(
    db: Session, *, email: str, email_verified: bool, invite_code_hash: Optional[str],
    agreement: AcceptedAccountAgreement | None = None,
) -> tuple[Optional[str], Optional[InviteCode]]:
    """Decide whether a social sign-in may create a NEW User (linking is decided by the callers).

    Returns ``(error_code, invite)``. ``error_code`` is None when creation may proceed, else the
    ``/login?error=`` code to redirect with: ``registration_unavailable`` while collection is held,
    ``account_agreement_required`` without current signup assent, ``email_unverified`` when the provider has not verified
    the address (an unverified claim never seeds an account), ``invite_required`` when
    REGISTRATION_MODE is invite_only and the sign-in carries no valid invite. ``invite`` is the
    validated invite the caller must redeem in the SAME transaction as the insert (None in public
    mode). Mirrors the register() gate; tests/unit/test_oauth_invite_gate.py keeps every ``User(``
    construction in app/ behind it (register()'s ``create_password_account`` is gated in register).
    """
    if not is_collection_available():
        return "registration_unavailable", None
    try:
        require_current_agreement(agreement)
    except AgreementRequired:
        return "account_agreement_required", None
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
    agreement: AcceptedAccountAgreement | None = None,
) -> tuple[Optional[User], Optional[str]]:
    """Create the User for a first social sign-in, or say why not.

    Returns ``(user, None)`` with the row flushed but not committed (``mint_oauth_refresh_token`` or
    ``commit_oauth_sign_in`` commits it together with the provider link and the session), or ``(None, error_code)`` when the
    gate refuses or (after rolling back) the invite's redemption is refused, the invite redeemed or
    revoked since it validated. When invite-only mode requires an invite it is consumed here, inside
    the same transaction, so a refused redemption never leaves an account behind. An insert that
    loses a concurrent first sign-in for the same email is rolled back and raises
    :class:`OAuthSignInRefused` with ``lost_create_race`` set.
    """
    error_code, invite = oauth_new_account_gate(
        db, email=email, email_verified=email_verified, invite_code_hash=invite_code_hash, agreement=agreement,
    )
    if error_code:
        return None, error_code
    user = User(email=email, full_name=full_name, hashed_password=None, email_verified=email_verified)
    db.add(user)
    try:
        db.flush()
        stage_account_agreement(db, user, agreement, source=provider)
    except IntegrityError:
        # Lost a concurrent first-sign-in race for the same email. The router logs it.
        db.rollback()
        raise OAuthSignInRefused(f"{provider}_account_conflict", lost_create_race=True) from None
    if invite is not None:
        if not invite_service.redeem_invite(db, invite, user, commit=False):
            db.rollback()
            return None, "invite_required"
        user.is_beta = True
    return user, None


# ─── Single-use state rows ─────────────────────────────────────────────────────

def store_oauth_state(
    db: Session, state: str, nonce: str, invite_code_hash: Optional[str],
    agreement: AcceptedAccountAgreement | None = None, *, session_handoff: bool = False,
) -> None:
    """Stage a single-use ``state`` row (10-minute TTL) after GC-ing expired rows; the caller commits.

    Both providers require one, even for a login without signup assent. The optional invite
    rides on the row as its hash so the callback can validate and redeem it. ``session_handoff``
    records whether the start asked for the one-time session handoff (E29 (5)): only a frontend with
    the ``/auth/complete`` landing page asks, and the callback hands off only then. Naive UTC for
    expiry (see the OAuthState model) so the comparison is naive-vs-naive on both Postgres and SQLite.
    """
    now = datetime.utcnow()
    db.query(OAuthState).filter(OAuthState.expires_at < now).delete(synchronize_session=False)
    db.add(OAuthState(
        state=state,
        nonce=nonce,
        invite_code_hash=invite_code_hash,
        agreement_terms_version=agreement.terms_version if agreement else None,
        agreement_eligibility_version=agreement.eligibility_version if agreement else None,
        agreement_accepted_at=agreement.accepted_at if agreement else None,
        session_handoff=session_handoff,
        expires_at=now + timedelta(seconds=OAUTH_STATE_TTL_SECONDS),
    ))


def consume_oauth_state(
    db: Session, state: str,
) -> Optional[tuple[str, Optional[str], AcceptedAccountAgreement | None, bool]]:
    """Atomically consume state and its signup evidence; concurrent callbacks cannot share it.

    Returns ``(nonce, invite_code_hash, agreement, session_handoff)``, or None. ``session_handoff`` is
    True only when the start asked for the handoff; False or NULL (a row written before the column
    existed) is False, and the callback then sets the session cookies on its redirect (E29 (5)).

    DELETE RETURNING supplies the winning row in one statement on PostgreSQL and SQLite. Expired
    state is deleted too, but cannot authorize creation. The caller still verifies browser binding.
    """
    row = db.execute(delete(OAuthState).where(OAuthState.state == state).returning(
        OAuthState.nonce, OAuthState.invite_code_hash, OAuthState.expires_at,
        OAuthState.agreement_terms_version, OAuthState.agreement_eligibility_version,
        OAuthState.agreement_accepted_at, OAuthState.session_handoff,
    )).first()
    db.commit()
    if row is None or row.expires_at < datetime.utcnow():
        return None
    agreement = None
    if row.agreement_terms_version and row.agreement_eligibility_version and row.agreement_accepted_at:
        agreement = AcceptedAccountAgreement(
            row.agreement_terms_version, row.agreement_eligibility_version, row.agreement_accepted_at,
        )
    return row.nonce, row.invite_code_hash, agreement, row.session_handoff is True


def live_invite_hash(db: Session, invite: Optional[str]) -> Optional[str]:
    """The hash of ``invite`` when it names a usable invite, else None: an OAuth start persists
    nothing for an unknown, revoked, used or expired token (the callback then sees no invite)."""
    if not invite:
        return None
    code_hash = invite_service.hash_invite_token(invite)
    return code_hash if invite_service.invite_hash_is_live(db, code_hash) else None


def save_google_state(
    db: Session, state: str, invite: Optional[str], agreement: AcceptedAccountAgreement | None = None,
    session_handoff: bool = False,
) -> None:
    """Commit one-time state for Google login/signup, with any live invite and explicit assent, and whether
    the start asked for the session handoff."""
    invite_code_hash = live_invite_hash(db, invite)
    # The nonce column is NOT NULL but unused for Google (no OIDC nonce in this flow).
    store_oauth_state(
        db, state, secrets.token_urlsafe(32), invite_code_hash, agreement, session_handoff=session_handoff,
    )
    db.commit()


def save_apple_state(
    db: Session, state: str, raw_nonce: str, invite: Optional[str],
    agreement: AcceptedAccountAgreement | None = None, session_handoff: bool = False,
) -> None:
    """Commit Apple's state row: the raw nonce its callback checks, plus the invite's hash when live, and
    whether the start asked for the session handoff."""
    store_oauth_state(
        db, state, raw_nonce, live_invite_hash(db, invite), agreement, session_handoff=session_handoff,
    )
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
    agreement: AcceptedAccountAgreement | None = None,
) -> tuple[User, bool, bool]:
    """Return ``(user, linked_existing, created)`` for a verified Google identity, with the provider
    link (if new) and ``last_login_at`` staged for ``mint_oauth_refresh_token`` or ``commit_oauth_sign_in``
    to commit.

    Order: existing link → existing account (linked only when both sides verified the email; else
    ``google_account_conflict``, since a new insert would hit the UNIQUE constraint) → new account
    through the gate. ``created`` is True only on that last branch: the sign-in creates the account,
    and the router writes its register row once the sign-in commits. Raises
    :class:`OAuthSignInRefused` with the redirect's error code.
    """
    oauth_row = (
        db.query(OAuthAccount)
        .filter_by(provider="google", provider_account_id=subject)
        .first()
    )

    linked_existing = False
    created = False
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
                agreement=agreement,
            )
            if user is None:
                raise OAuthSignInRefused(error_code)
            created = True
        db.add(OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=subject,
            provider_email=email,
        ))

    user.last_login_at = datetime.now(timezone.utc)
    return user, linked_existing, created


def resolve_apple_user(
    db: Session,
    *,
    subject: str,
    email: Optional[str],
    email_verified: bool,
    full_name: Optional[str],
    invite_code_hash: Optional[str],
    agreement: AcceptedAccountAgreement | None = None,
) -> tuple[User, bool, bool]:
    """Return ``(user, linked_existing, created)`` for a verified Apple identity, with the provider
    link (if new), a first-authorization name fill-in and ``last_login_at`` staged for
    ``mint_oauth_refresh_token`` or ``commit_oauth_sign_in`` to commit.

    Order: existing link → existing verified account → new account (``created``, as for Google).
    Without an existing link Apple must supply an email (``apple_missing_claims``); an existing
    account that cannot be safely linked is ``apple_account_conflict``. Raises
    :class:`OAuthSignInRefused` with the error code.
    """
    oauth_row = db.query(OAuthAccount).filter_by(
        provider="apple", provider_account_id=subject
    ).first()

    linked_existing = False
    created = False
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
                agreement=agreement,
            )
            if user_obj is None:
                raise OAuthSignInRefused(error_code)
            created = True

        db.add(OAuthAccount(
            user_id=user_obj.id,
            provider="apple",
            provider_account_id=subject,
            provider_email=email,
        ))

    user_obj.last_login_at = datetime.now(timezone.utc)
    return user_obj, linked_existing, created


def mint_oauth_refresh_token(
    db: Session, user: User, *, user_agent: Optional[str], ip: Optional[str]
) -> str:
    """Mint and commit the sign-in's refresh token, committing what the resolve staged with it (a
    new account and redeemed invite, the provider link, ``last_login_at``). Returns the raw token.
    Main's path, kept until E29 (5)'s follow-up retires it: the commit of a callback whose start did not
    ask for the session handoff, which then sets the session cookies on its redirect home;
    ``commit_oauth_sign_in`` is the commit of a start that asked.

    A concurrent first sign-in for the same identity loses here with ``IntegrityError`` (the token's
    flush or the commit): the session is rolled back and :class:`OAuthAccountConflictError` raised.
    No lock serializes two callbacks for one identity, or two sign-ups with one invite: they interleave in
    their routes' thread-pool units on one instance, as they always could across the API's instances (E121).
    The unique ``users.email``, the unique ``uq_oauth_provider_account`` and the invite's guarded redemption
    decide. The loser is refused by the resolve (a new account's lost create race, ``invite_required``) or,
    for a link to an existing account, loses here, with nothing of its own committed; the PostgreSQL races in
    ``tests/integration/test_refresh_rotation_transactions.py`` pin each, for this commit and for
    ``commit_oauth_sign_in``'s (their ``commit`` parameter).
    """
    try:
        return refresh_token_service.mint_refresh_token(db, user, user_agent=user_agent, ip=ip)
    except IntegrityError:
        db.rollback()
        raise OAuthAccountConflictError() from None


def _hash_handoff_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


def _is_handoff_secret(raw: Optional[str]) -> bool:
    """Whether ``raw`` could be a code or binder this module minted: ``secrets.token_urlsafe`` writes ASCII. Anything
    else (missing, empty, oversized, or not ASCII, a lone surrogate among them, whose encode would raise) is refused
    before its hash, with no query, as refresh_token_service refuses a token of the wrong shape."""
    return isinstance(raw, str) and 0 < len(raw) <= _HANDOFF_SECRET_MAX_LENGTH and raw.isascii()


def commit_oauth_sign_in(db: Session, user: User) -> tuple[str, str]:
    """Commit what the resolve staged (a new account and redeemed invite, the provider link, ``last_login_at``)
    together with a one-time session handoff for ``user``, for a start that asked for it (E29 (5)), and return its
    raw ``(code, binder)``: the code the
    callback puts in its redirect's URL fragment, and the value of the cookie that binds the handoff to the browser
    the callback answers. Only their SHA-256 hashes are stored (``SessionHandoff``). The callback sets no session
    cookie: the landing page's post exchanges the code under the session cookies' lock (``redeem_session_handoff``),
    and that post's answer sets them (E29 (5)). The same commit deletes the handoffs already expired, as a start
    deletes the expired states (``store_oauth_state``).

    A concurrent first sign-in for the same identity loses here with ``IntegrityError`` (the commit's flush): the
    session is rolled back and :class:`OAuthAccountConflictError` raised. No lock serializes two callbacks for one
    identity, or two sign-ups with one invite: they interleave in their routes' thread-pool units on one instance, as
    they always could across the API's instances (E121). The unique ``users.email``, the unique
    ``uq_oauth_provider_account`` and the invite's guarded redemption decide. The loser is refused by the resolve (a
    new account's lost create race, ``invite_required``) or, for a link to an existing account, loses here, with
    nothing of its own committed; the PostgreSQL races in ``tests/integration/test_refresh_rotation_transactions.py``
    pin each.
    """
    now = utcnow()
    code, binder = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(SessionHandoff(
        code_hash=_hash_handoff_secret(code),
        binder_hash=_hash_handoff_secret(binder),
        user_id=user.id,
        expires_at=now + timedelta(seconds=SESSION_HANDOFF_TTL_SECONDS),
        created_at=now,
    ))
    try:
        # The sign-in's own rows first, as the refresh token's flush sent them before the handoff (a lost race fails
        # here, holding nothing else), then the expired handoffs, then the commit.
        db.flush()
        db.query(SessionHandoff).filter(SessionHandoff.expires_at < now).delete(synchronize_session=False)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise OAuthAccountConflictError() from None
    return code, binder


def redeem_session_handoff(db: Session, raw_code: Optional[str], raw_binder: Optional[str]) -> Optional[User]:
    """Mark the handoff that ``raw_code`` and ``raw_binder`` name used, and return its account, or None: an unknown
    code, a code with another browser's binder or with none (the binding cookie missing), one already used, one
    expired, one whose account an account-wide revocation has signed out since (it deletes the account's handoffs:
    ``refresh_token_service.revoke_all_for_user``) and one whose account is inactive are all refused alike, and a code
    or binder of the wrong shape with no query at all (``_is_handoff_secret``).

    The account's users row lock comes first, as for every writer of its sessions (``refresh_token_service.
    lock_user_tokens``; the lock order in ``docs/audit/contracts/refresh-chain-migration.md`` §4): a plain read finds
    the handoff's account, the lock is taken, the account is read again under it, and one guarded UPDATE then decides
    (``used_at IS NULL`` and unexpired, for that code and that binder). So an exchange and a logout-all, a password
    change or a password reset of that account serialize: one that waits out a revocation finds its handoff deleted
    and is refused, and a revocation that waits out an exchange revokes the session the exchange minted. Of two
    redemptions of one code, the second waits at the lock for the first's commit, then reads the handoff used. A
    deletion of the account takes the same row ``FOR UPDATE`` before its cascade deletes the handoffs.

    Nothing commits here: the caller mints the session's refresh token and commits it with the redemption (the
    route's ``issue_session``), so a mint that fails leaves the handoff unused. A refusal writes nothing, and one
    made after the lock rolls back, releasing it (one before it leaves its read to the caller's release). ``synchronize_session=False``: the statement is the whole decision,
    and the ORM's in-Python evaluation of its criteria would compare SQLite's naive datetimes with the aware clock.
    """
    if not (_is_handoff_secret(raw_code) and _is_handoff_secret(raw_binder)):
        return None
    code_hash, binder_hash = _hash_handoff_secret(raw_code), _hash_handoff_secret(raw_binder)
    found = (
        db.query(SessionHandoff.user_id)
        .filter(SessionHandoff.code_hash == code_hash, SessionHandoff.binder_hash == binder_hash)
        .first()
    )
    if found is None:
        return None  # nothing was written or locked; the caller's release ends the read's transaction
    user_id = found.user_id
    refresh_token_service.lock_user_tokens(db, user_id)
    user = db.query(User).filter(User.id == user_id).populate_existing().first()
    if user is None or not user.is_active:
        db.rollback()  # releases the lock; nothing was written
        return None
    now = utcnow()
    redeemed = db.execute(
        update(SessionHandoff)
        .where(
            SessionHandoff.code_hash == code_hash,
            SessionHandoff.binder_hash == binder_hash,
            SessionHandoff.used_at.is_(None),
            SessionHandoff.expires_at >= now,
        )
        .values(used_at=now)
        .returning(SessionHandoff.user_id)
        .execution_options(synchronize_session=False)
    ).first()
    if redeemed is None:
        db.rollback()  # releases the lock; nothing was written
        return None
    return user


# ─── Connections ───────────────────────────────────────────────────────────────

def list_oauth_accounts(db: Session, user_id: int) -> list[OAuthAccount]:
    """The user's linked provider identities."""
    return db.query(OAuthAccount).filter(OAuthAccount.user_id == user_id).all()


def unlink_oauth_provider(db: Session, user_id: int, provider: str) -> None:
    """Delete the user's link for ``provider`` and commit, unless it is their last sign-in method.

    Under the account's users row lock (``refresh_token_service.lock_user_tokens``), taken before the guard
    reads the password and the links: two unlinks of one account, one per provider or a double click on one,
    run one after the other, and the second counts what the first left (READ COMMITTED). The password is read
    by a column query, not from a user the session loaded before the lock. The route runs this in the thread
    pool, where two requests on one instance interleave; on one instance's event loop they did not, and across
    the API's instances they always could (E121).

    Raises :class:`ProviderNotLinkedError` when there is no such link (an account deleted meanwhile has none)
    and :class:`LastSignInMethodError` when removing it would leave neither a password nor another link.
    """
    refresh_token_service.lock_user_tokens(db, user_id)
    has_password = bool(db.query(User.hashed_password).filter(User.id == user_id).scalar())
    rows = list_oauth_accounts(db, user_id)
    target = next((r for r in rows if r.provider == provider), None)
    if not target:
        raise ProviderNotLinkedError()

    # Lockout guard: after removing this provider the user must keep at least one credential
    # (a password or another linked provider).
    remaining = (1 if has_password else 0) + (len(rows) - 1)
    if remaining < 1:
        raise LastSignInMethodError()

    db.delete(target)
    db.commit()
