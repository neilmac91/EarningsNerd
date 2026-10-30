"""Refresh-token lifecycle: issue, rotate (single-use), and revoke.

Refresh tokens are opaque random strings. Only their SHA-256 hash is stored, so the
database never holds a usable credential. Every refresh rotates the token (the old one is
revoked and points at its replacement); presenting a token that was already rotated away is
treated as a reuse/theft signal and revokes that token's chain: the live tokens its rotations lead to
(E96; ``docs/audit/contracts/refresh-chain-migration.md``). The account's other sessions are left alone.
A token revoked any other way (logout, logout-all, a password change or reset, or that theft sweep) is
simply refused.

Every rotation and revocation of a user's tokens (a refresh, logout, logout-all, the sweep, a password
change or reset) first takes the account's users row lock and reads what it writes under it, so two of
them for one user run one after the other, on one API instance or across both (``lock_user_tokens``).
A token minted at sign-in writes no existing row and takes no lock, except a password login's: a password
login and a password change take the lock, and act only while the hash they verified is still the account's
(``auth_account_service.record_password_login`` and ``stage_password_change``, E121).
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.models import RefreshToken, User
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)


class RefreshTokenError(Exception):
    """Raised when a refresh token is missing, invalid, or expired."""


class RefreshTokenReuseError(RefreshTokenError):
    """Raised when a rotated-away refresh token is replayed (reuse/theft signal).

    Distinct from the base error because handling it modifies the database (the replayed
    token's chain is revoked: the live tokens its rotations lead to), so the caller must commit — whereas a missing/expired/
    unknown token makes no writes and must not trigger a commit on unauthenticated traffic.
    """


def lock_user_tokens(db: Session, user_id: int) -> None:
    """Take ``user_id``'s users row lock for the rest of the caller's transaction.

    Every rotation and revocation of a user's refresh tokens takes it before it reads the tokens it
    writes. Two refreshes with one cookie both read the token live otherwise, and both mint a
    successor. A refresh racing a logout or logout-all writes on its stale read, leaving a live
    successor. A guarded UPDATE alone would not stop the logout-all case: its bulk UPDATE sees only
    rows committed when it starts, so a successor committed after that survives it. The lock makes
    the second writer wait for the first's commit, and the reads it then makes see that commit (READ
    COMMITTED). The account's deletion takes it as well (``user_account_service._lock_account``), as its
    cascade deletes the tokens, and so do a password login and a password change before they check the
    hash they verified (``auth_account_service.record_password_login`` and ``stage_password_change``), a
    password reset before it reads the account it writes (``complete_password_reset_by_id``), and an unlink
    before it counts the account's sign-in methods (``oauth_account_service.unlink_oauth_provider``).
    FOR NO KEY UPDATE: it serializes these writers but not the foreign-key checks of inserts that name
    the user, a sign-in's new token among them. Unbounded, as the holders are short transactions, except a
    Stripe delivery, which can hold the row across a bounded Stripe read (``watchlist_service.lock_watch_rows``
    says so too), and a timeout would turn a moment's wait into a failed refresh. SQLite ignores it."""
    db.query(User.id).filter(User.id == user_id).with_for_update(key_share=True).first()


def _read_again(db: Session, token: RefreshToken) -> Optional[RefreshToken]:
    """``token`` as committed now, read under the users row lock, or ``None`` once it is gone (the
    account deleted while this request waited, or a dead token purged)."""
    return db.query(RefreshToken).filter(RefreshToken.id == token.id).populate_existing().first()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _is_token_shaped(raw_token: Optional[str]) -> bool:
    """Whether ``raw_token`` could be a token this module minted: ``secrets.token_urlsafe`` writes ASCII. Anything
    else is refused as unknown before its hash, whose encode raised on a lone surrogate and answered 500 (E97's
    review)."""
    return bool(raw_token) and raw_token.isascii()


def _live_descendants(db: Session, token: RefreshToken) -> list[int]:
    """The ids of the live tokens ``token``'s rotations lead to: its chain from here on (E96).

    One recursive query follows ``replaced_by_id`` forward from ``token``, and only through a link to a token of
    the same user with a higher id (rotation mints the successor after the token it replaces), so a cross-user or
    backward link, or a cycle, ends the walk instead of reaching another account's sessions. A link the walk does
    not follow is logged with ids only. Revoked descendants are left as they are; live ones are returned whatever
    their expiry, so a later clock or setting change cannot revive one. The caller holds the users row lock."""
    chain = (
        select(RefreshToken.id, RefreshToken.user_id, RefreshToken.replaced_by_id, RefreshToken.revoked_at)
        .where(RefreshToken.id == token.id)
        .cte("refresh_chain", recursive=True)
    )
    successor = aliased(RefreshToken)
    # ``union``, not ``union_all``: a row met twice ends the recursion, a belt behind the increasing-id guard.
    chain = chain.union(
        select(successor.id, successor.user_id, successor.replaced_by_id, successor.revoked_at)
        .join(chain, successor.id == chain.c.replaced_by_id)
        .where(successor.user_id == chain.c.user_id, successor.id > chain.c.id)
    )
    rows = db.execute(select(chain.c.id, chain.c.replaced_by_id, chain.c.revoked_at)).all()
    reached = {row.id for row in rows}
    unfollowed = [
        row.id for row in rows
        if row.replaced_by_id is not None and (row.replaced_by_id <= row.id or row.replaced_by_id not in reached)
    ]
    if unfollowed:
        logger.warning(
            "Refresh chain of user_id=%s has links the walk did not follow, from token id(s) %s",
            token.user_id,
            unfollowed,
        )
    return [row.id for row in rows if row.id != token.id and row.revoked_at is None]


def _revoke(db: Session, token_ids: list[int], now: datetime) -> int:
    """Revoke those of ``token_ids`` still live, at ``now``; returns how many."""
    if not token_ids:
        return 0
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.id.in_(token_ids), RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )


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
    Replaying a token that was already rotated away revokes that token's chain (its live
    descendants, ``_live_descendants``) and raises :class:`RefreshTokenReuseError` (theft
    mitigation); a token revoked without rotation writes nothing. The caller is responsible for
    committing the session.
    """
    if not raw_token:
        raise RefreshTokenError("Missing refresh token")
    if not _is_token_shaped(raw_token):
        raise RefreshTokenError("Unknown refresh token")

    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash_token(raw_token))
        .first()
    )
    if token is None:
        raise RefreshTokenError("Unknown refresh token")
    lock_user_tokens(db, token.user_id)
    token = _read_again(db, token)  # a rotation, revocation or deletion committed since shows here
    if token is None:
        raise RefreshTokenError("Unknown refresh token")

    now = datetime.utcnow()

    if token.revoked_at is not None:
        if token.replaced_by_id is None:
            # Revoked without rotation (logout, logout-all, a password change or reset, or the
            # theft sweep below): its holder was signed out, nobody holds a successor, and the
            # token grants nothing. Refusing it is enough; sweeping would only revoke the sessions
            # the user signed in to since.
            raise RefreshTokenError("Refresh token has been revoked")
        # A rotated-away token is being replayed: two parties hold copies of it, and one of them holds the
        # chain's live tip. Revoke that chain, the live tokens this token's rotations lead to, and nothing else:
        # the account's other devices, and a session minted after a reset or logout-all, keep theirs (E96, no
        # grace window; lessons/arch-only-a-rotated-refresh-token-signals-theft.md).
        revoked = _revoke(db, _live_descendants(db, token), now)
        logger.warning(
            "Refresh token reuse detected for user_id=%s; revoked %s token(s) of its chain",
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


def revoke_refresh_token(db: Session, raw_token: Optional[str]) -> Optional[int]:
    """Revoke a single refresh token (e.g. on logout). Returns its user's id if one was revoked.

    Idempotent and best-effort: unknown or already-revoked tokens return None. A token that refreshes
    rotated away revokes its chain's live tip instead, the session it belonged to: a refresh may have
    taken the lock first with the same cookie, or another tab may have rotated the chain on, and their
    new cookie may reach the browser after the logout clears it. The walk is the replay sweep's
    (``_live_descendants``), so the two agree on what a chain is. The caller is responsible for
    committing the session.
    """
    if not _is_token_shaped(raw_token):
        return None
    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _hash_token(raw_token))
        .first()
    )
    if token is None:
        return None
    lock_user_tokens(db, token.user_id)
    token = _read_again(db, token)  # as a rotation does
    if token is None:
        return None
    if token.revoked_at is None:
        targets = [token]
    else:
        tips = _live_descendants(db, token)
        targets = db.query(RefreshToken).filter(RefreshToken.id.in_(tips)).all() if tips else []
    if not targets:
        return None
    # Attribute writes, flushed at the caller's commit, as before E96: the logout's failure contract (a token store
    # that refuses the write answers 503) is pinned on the flush (tests/unit/test_logout_failure_clears_cookies.py).
    now = datetime.utcnow()
    for target in targets:
        target.revoked_at = now
    return token.user_id


def revoke_all_for_user(db: Session, user_id: int) -> int:
    """Revoke all of a user's active refresh tokens. Returns the number revoked.

    Under the users row lock, so the bulk UPDATE starts after any rotation of this user's has committed
    and revokes its successor too."""
    lock_user_tokens(db, user_id)
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
) -> Tuple[User, str, str]:
    """Rotate ``raw_token`` and commit; return ``(user, new_raw_token, email)``.

    ``email`` is the account's address, read before the commit expires ``user``: the caller builds the
    access token from it, so no read after the commit can fail a rotation that committed, whose new token
    the client would then never get and whose next refresh would replay the one rotated away (E121).

    A replayed rotated-away token's chain revocation is committed before the same
    :class:`RefreshTokenReuseError` propagates. Any other :class:`RefreshTokenError` made no writes
    and commits nothing.
    """
    try:
        user, new_raw_token = rotate_refresh_token(db, raw_token, user_agent=user_agent, ip=ip)
        email = user.email
        db.commit()
    except RefreshTokenReuseError:
        db.commit()
        raise
    return user, new_raw_token, email


def revoke_and_commit(db: Session, raw_token: Optional[str]) -> Optional[Tuple[int, Optional[str]]]:
    """Revoke one refresh token (logout) and commit when one was revoked.

    Returns the ``(id, email)`` of the user whose session it ended, read under the users row lock before
    the commit expires the row, or ``None`` when it revoked none. A logout whose session token has
    expired knows its user only from this (E137).
    """
    user_id = revoke_refresh_token(db, raw_token)
    if user_id is None:
        return None
    email = db.query(User.email).filter(User.id == user_id).scalar()
    db.commit()
    return user_id, email


def live_token_owner(db: Session, raw_token: Optional[str]) -> Optional[Tuple[int, Optional[str]]]:
    """The ``(id, email)`` of the active user whose live refresh token ``raw_token`` is, or ``None``.

    Live: neither revoked (a rotated-away token is revoked too) nor expired, as a rotation would accept it.
    The logout of every session finds its user here once the access token has lapsed (E157 (2)), as a
    logout finds the session it ends from the same cookie. It reads and takes no lock: the revocation that
    follows takes the users row lock and revokes every live token of that user, a successor a refresh mints
    meanwhile included. ``expires_at`` is one of the sanctioned naive columns, compared here with a naive
    projection of the aware clock, as ``retention_service`` compares it.
    """
    if not _is_token_shaped(raw_token):
        return None
    now = utcnow().replace(tzinfo=None)
    owner = (
        db.query(User.id, User.email)
        .join(RefreshToken, RefreshToken.user_id == User.id)
        .filter(
            RefreshToken.token_hash == _hash_token(raw_token),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
            User.is_active.is_(True),
        )
        .first()
    )
    return (owner.id, owner.email) if owner else None


def revoke_all_and_commit(db: Session, user_id: int) -> int:
    """Revoke all of a user's active refresh tokens (sign out everywhere), commit, return the count."""
    revoked = revoke_all_for_user(db, user_id)
    db.commit()
    return revoked
