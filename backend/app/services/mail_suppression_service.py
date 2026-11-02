"""The address-level suppression list and the per-address lock that orders a send after an opt-out (EN-BETA PB-01).

An address is known here only as ``recipient_hash``: SHA-256 of the address as invites normalise it (trimmed, lower
case), under a fixed domain prefix. It is not peppered with ``SECRET_KEY`` as the login lockout's is: rotating that key
would silently forget every opt-out, and the controls would mail people who asked to stop. The cost is that the hash
of a known address can be recomputed, so it is pseudonymous data, kept because an opt-out cannot be honoured without
recognising the address again (docs/LEGAL_READINESS.md, "Invitation email").

``lock_recipient`` creates the address's row if it is missing and holds its row lock to the caller's commit. A send
takes it before it reads the suppression and commits its delivery as "sending"; an unsubscribe and a suppressing
webhook take it before they write. On PostgreSQL an opt-out that commits first is seen by the send, which then sends
nothing, and one that comes second waits for the send's commit and applies to every later send: a send authorised
before an opt-out committed may still go out, none authorised after it does. SQLite, which the tests use, serialises
writers on the whole database instead.

Suppression covers requested invitations and any future promotional mail. Requested account mail (verification,
password reset, the security notices) never reads it.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.invite_mail import SUPPRESSION_REASONS, MailRecipient
from app.utils.datetimes import utcnow

_HASH_PREFIX = "earningsnerd-mail-recipient-v1:"


def normalize_address(address: str) -> str:
    return (address or "").strip().lower()


def recipient_hash(address: str) -> str:
    return hashlib.sha256(f"{_HASH_PREFIX}{normalize_address(address)}".encode("utf-8")).hexdigest()


def _insert_for(db: Session):
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": postgres_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise ValueError(f"Unsupported mail-suppression database dialect: {dialect}")
    return insert


def lock_recipient(db: Session, hashed: str) -> MailRecipient:
    """The address's row, created if missing, under its row lock until the caller commits or rolls back.

    The insert does nothing on a conflict, so two first sends to one address both find the one row; the second waits
    for the first's transaction at the unique index, then at the row lock. ``populate_existing`` re-reads a row the
    session already holds, so a caller that read it before the lock sees what the lock's holder committed.
    """
    now = utcnow()
    statement = _insert_for(db)(MailRecipient).values(recipient_hash=hashed, created_at=now, updated_at=now)
    db.execute(statement.on_conflict_do_nothing(index_elements=[MailRecipient.recipient_hash]))
    return (
        db.query(MailRecipient)
        .filter(MailRecipient.recipient_hash == hashed)
        .with_for_update()
        .populate_existing()
        .one()
    )


def suppress_locked(recipient: MailRecipient, reason: str, event: str) -> bool:
    """Suppress a locked recipient; the first suppression stands. True when this call suppressed it."""
    if reason not in SUPPRESSION_REASONS:
        raise ValueError(f"Unknown suppression reason: {reason}")
    if recipient.suppressed_at is not None:
        return False
    now = utcnow()
    recipient.suppressed_at = now
    recipient.suppression_reason = reason
    recipient.suppression_event = event[:80]
    recipient.updated_at = now
    return True


def suppress(db: Session, hashed: str, reason: str, event: str) -> bool:
    """Lock the address's row and suppress it, in the caller's transaction (the caller commits)."""
    return suppress_locked(lock_recipient(db, hashed), reason, event)


def suppression_for(db: Session, hashes: Iterable[str]) -> dict[str, Optional[str]]:
    """The suppression reason of each suppressed address among ``hashes`` (an unsuppressed one is absent)."""
    wanted = sorted(set(hashes))
    if not wanted:
        return {}
    rows = (
        db.query(MailRecipient.recipient_hash, MailRecipient.suppression_reason)
        .filter(MailRecipient.recipient_hash.in_(wanted), MailRecipient.suppressed_at.is_not(None))
        .all()
    )
    return {row.recipient_hash: row.suppression_reason for row in rows}
