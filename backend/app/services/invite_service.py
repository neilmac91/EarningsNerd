"""Closed-beta invite lifecycle: mint magic links, validate, and single-use redeem.

Tokens follow the email-verification pattern in ``auth.py`` — only the SHA-256 hash is stored; the
raw token lives only in the magic link. Eligibility is recorded on the ``User`` (``is_beta``) at
redemption, so the checkout promo never depends on a client-supplied parameter. The admin surface
(``routers/admin.py``) lists, revokes and re-issues invites through the functions at the bottom.
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
from app.services.auth_validation import is_valid_unicode


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
    commit: bool = True,
) -> tuple[InviteCode, str, str]:
    """Create an invite and return (row, raw_token, magic_link). The raw token is shown once.

    ``commit=False`` flushes the row into the caller's open transaction instead, so an emailed invitation commits its
    link and its delivery record together (invite_delivery_service), or neither."""
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
    if commit:
        db.commit()
        db.refresh(invite)
    else:
        db.flush()
    return invite, raw, build_invite_link(raw)


def hash_invite_token(raw: str) -> str:
    """The stored form of an invite token. Callers that must carry an invite across a redirect
    (the OAuth state row) keep this hash, never the raw token."""
    return _hash_token(raw)


def validate_invite(db: Session, raw_token: Optional[str], email: str) -> Optional[InviteCode]:
    """Return a usable invite for this registration, or None if it's missing / invalid / revoked /
    already used / expired / bound to a different email. Never raises on a bad token: one that is not valid text
    (a lone surrogate, which no minted invite holds) is no invite, where its hash's encode raised a 500 (E97)."""
    if not raw_token or not is_valid_unicode(raw_token):
        return None
    return validate_invite_hash(db, _hash_token(raw_token), email)


def live_invite(db: Session, code_hash: Optional[str]) -> Optional[InviteCode]:
    """The invite ``code_hash`` names while it is still usable (exists, not revoked, unused, unexpired), else None.
    The email binding is checked at redemption, when the address is known; this is the cheap pre-check an OAuth start
    uses before it persists anything for the invite."""
    if not code_hash:
        return None
    invite = db.query(InviteCode).filter(InviteCode.code_hash == code_hash).first()
    if invite is None or invite.is_revoked or invite.used_at is not None or _is_expired(invite):
        return None
    return invite


def invite_hash_is_live(db: Session, code_hash: Optional[str]) -> bool:
    """True when ``code_hash`` names an invite that is still usable (``live_invite``)."""
    return live_invite(db, code_hash) is not None


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


def redeem_invite(
    db: Session, invite: InviteCode, user, *, commit: bool = True, cohort: Optional[str] = None,
) -> bool:
    """Atomically mark a single-use invite redeemed for ``user``. Returns False if a concurrent
    registration already consumed it, an admin revoked it since it validated, or it expired since it
    validated (guarded ``UPDATE ... WHERE used_at IS NULL AND is_revoked IS false AND expires_at >= now``;
    E201). The password registration validates the invite before its breached-password check and its
    hash, seconds that an invite can expire in, so the expiry is part of the guard rather than a check
    made only at validation (EN-BETA PB-01). On PostgreSQL a redemption that waits behind a revoke's or
    re-issue's row lock re-checks the row when that transaction commits, so it is refused too.

    ``cohort`` is the invited cohort when that exception, not collection, admits the account
    (``legal_readiness_service.require_account_admission``): the guard then also requires the row to
    carry exactly that cohort and to be bound to ``user``'s address, so the redemption decides on the
    invite as stored, never on the copy an earlier unit read and released.

    ``commit=False`` leaves the UPDATE in the caller's open transaction, so a registration commits
    (or rolls back) the new account and the redemption together."""
    now = _now()
    conditions = [
        InviteCode.id == invite.id,
        InviteCode.used_at.is_(None),
        InviteCode.is_revoked.is_(False),
        InviteCode.expires_at >= now,  # validate_invite's test, inverted: _is_expired is exp < now
    ]
    if cohort is not None:
        # Both stored lower-cased and stripped: a mint normalizes the address, a registration's schema the account's.
        conditions += [InviteCode.cohort == cohort, InviteCode.email == (user.email or "").strip().lower()]
    result = db.execute(
        update(InviteCode)
        .where(*conditions)
        .values(used_at=now, user_id=user.id)
        # Not evaluated in Python against the session's copy: SQLite hands back a naive expires_at, which no aware
        # instant compares with. The callers read nothing of the invite before the commit or rollback that ends the
        # transaction, and either expires the session's copy, so nothing reads it stale.
        .execution_options(synchronize_session=False)
    )
    if commit:
        db.commit()
    return result.rowcount == 1


class InviteNotFoundError(Exception):
    """No invite has the requested id (the admin router maps it to 404 "Invite not found")."""


class InviteAlreadyRedeemedError(Exception):
    """The invite was redeemed, so it can be neither revoked nor re-sent (409 "Invite already redeemed")."""


def invite_status(invite: InviteCode) -> str:
    # "used" outranks "revoked": once an invite has been redeemed, that fact is the truth worth
    # surfacing even if the row also carries a revoke flag (e.g. legacy data), so redemption
    # history is never masked.
    if invite.used_at is not None:
        return "used"
    if invite.is_revoked:
        return "revoked"
    exp = invite.expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return "expired"
    return "pending"


def list_recent_invites(db: Session) -> list[InviteCode]:
    """The 200 most recently created invites, newest first."""
    return db.query(InviteCode).order_by(InviteCode.created_at.desc()).limit(200).all()


def _unused_invite_locked(db: Session, invite_id: int) -> InviteCode:
    """The unused invite ``invite_id``, read under its row lock until the caller's commit (E171).

    The admin router runs a revoke or re-issue in the thread pool, where a registration on the same
    instance, as on the other, can redeem the invite between the check and the write. On PostgreSQL a
    redemption that wrote first is waited for and seen, so the check refuses the redeemed invite instead
    of revoking it or minting its replacement; one that comes second waits for the commit and finds the
    invite revoked (``redeem_invite``, E201). SQLite, which the tests use, has no row locks, so there a
    redemption that commits between the check and the write is not seen. An entity query hands back an
    invite the session still holds unchanged, so ``populate_existing`` re-reads it: a caller that kept an
    invite it read before the lock sees the redemption too."""
    invite = (
        db.query(InviteCode)
        .filter(InviteCode.id == invite_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not invite:
        raise InviteNotFoundError(invite_id)
    if invite.used_at is not None:
        # A redeemed invite can't be "un-redeemed"; revoking it would only corrupt its status.
        raise InviteAlreadyRedeemedError(invite_id)
    return invite


def lock_unused_invite(db: Session, invite_id: int) -> InviteCode:
    """The unused invite ``invite_id`` under its row lock until the caller's commit (see ``_unused_invite_locked``)."""
    return _unused_invite_locked(db, invite_id)


def pending_invite_for_address(db: Session, email: str, *, exclude_invite_id: Optional[int] = None) -> Optional[int]:
    """The id of a live invite (unused, unrevoked, unexpired) bound to ``email``, other than ``exclude_invite_id``.

    An emailed invitation and a re-issue of a bound one refuse to make a second live link for an address while one is
    live (invite_delivery_service), so a repeated submit or a retry cannot mail two different links."""
    query = db.query(InviteCode.id).filter(
        InviteCode.email == (email or "").strip().lower(),
        InviteCode.used_at.is_(None),
        InviteCode.is_revoked.is_(False),
        InviteCode.expires_at >= _now(),
    )
    if exclude_invite_id is not None:
        query = query.filter(InviteCode.id != exclude_invite_id)
    row = query.order_by(InviteCode.id).first()
    return row.id if row is not None else None


def revoke_invite(db: Session, invite_id: int) -> InviteCode:
    """Revoke an unused invite so its link can no longer be redeemed, and commit."""
    invite = _unused_invite_locked(db, invite_id)
    invite.is_revoked = True
    db.commit()
    return invite


def reissue_invite(
    db: Session,
    invite_id: int,
    *,
    created_by: Optional[int],
    expires_in_hours: Optional[int],
    commit: bool = True,
) -> tuple[InviteCode, str, str]:
    """Revoke an unused invite and mint its replacement (same email + cohort); returns ``mint_invite``'s
    (row, raw_token, magic_link). ``commit=False`` leaves both in the caller's transaction, as ``mint_invite``'s."""
    old = _unused_invite_locked(db, invite_id)

    # Revoke the old invite BEFORE minting the replacement so there is never a window in which two
    # links for the same invitee are simultaneously redeemable. mint_invite's commit persists the
    # revoke (on the already-tracked ``old`` row) and the new row in a single transaction.
    old.is_revoked = True
    return mint_invite(
        db,
        created_by=created_by,
        email=old.email,
        expires_in_hours=expires_in_hours,
        cohort=old.cohort,
        commit=commit,
    )


def invite_has_delivery_recipient(db: Session, invite_id: int) -> bool:
    """Read whether reissue would send mail, before any existing link is revoked or replaced."""
    invite = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
    if invite is None:
        raise InviteNotFoundError(invite_id)
    if invite.used_at is not None:
        raise InviteAlreadyRedeemedError(invite_id)
    return bool(invite.email)
