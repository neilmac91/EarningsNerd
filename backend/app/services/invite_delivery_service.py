"""Requested beta-invitation email: permission, send-time suppression, the per-link ledger and provider feedback.

The admin router runs each step as its own unit (routers/admin.py); nothing here holds a connection across the
provider call.

1. ``prepare_invite_send`` / ``prepare_reissue``: under the address's lock (mail_suppression_service), refuse a
   suppressed address and a second live link for it, mint the link, and commit it together with its delivery row,
   status "sending", which records the logical send (``delivery_ref``) and the permission it rests on: the admin's
   record of how and when the recipient asked for an invitation. The raw link and unsubscribe token leave only in
   the returned value, for the email; neither is stored or logged.
2. ``deliver``: the email (``email_service.send_invite_email``), with Idempotency-Key ``en-invite-<ref>`` and the
   tag ``en_invite_delivery=<ref>``, so the provider's events find the row even when its answer to the call was lost.
   Each outcome is classified: accepted (the provider took it, which is not delivery), failed (nothing was sent), or
   unknown (it may have been sent).
3. ``record_send_outcome``: a fenced write that moves only a "sending" row, so a provider event that arrived first
   stands. An unknown outcome is never retried: the admin's re-send revokes the link and mails a new one.
4. ``apply_provider_event``: a signed webhook moves a row up its evidence order (accepted, delayed, delivered, then
   bounced, failed or suppressed, then complained) and never down, so a duplicate or a late event changes nothing;
   a permanent bounce, a complaint or the provider's suppression suppresses the address.
5. ``unsubscribe``: the token from the email suppresses its address, whatever the link's state.
"""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.invite import InviteCode
from app.models.invite_mail import (
    PERMISSION_VIA,
    STATUS_ACCEPTED,
    STATUS_BOUNCED,
    STATUS_COMPLAINED,
    STATUS_DELAYED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_SENDING,
    STATUS_SUPPRESSED,
    STATUS_UNKNOWN,
    SUPPRESSED_BY_PROVIDER,
    SUPPRESSED_COMPLAINT,
    SUPPRESSED_HARD_BOUNCE,
    SUPPRESSED_UNSUBSCRIBED,
    InviteDelivery,
)
from app.services import email_service, invite_service, mail_suppression_service
from app.services.auth_validation import is_valid_unicode
from app.services.resend_service import ResendAmbiguousError, ResendPermanentError, ResendRetryableError
from app.services.resend_webhook_service import (
    BOUNCE_PERMANENT,
    EVENT_BOUNCED,
    EVENT_COMPLAINED,
    EVENT_DELAYED,
    EVENT_DELIVERED,
    EVENT_FAILED,
    EVENT_SENT,
    EVENT_SUPPRESSED,
    ProviderEvent,
)
from app.utils.datetimes import ensure_utc, iso_z, utcnow

logger = logging.getLogger(__name__)

# A row still "sending" this long after its commit lost its outcome (the process stopped mid-call): it reads unknown.
STALE_SENDING = timedelta(minutes=5)
# The longest raw unsubscribe token the route reads; a minted one is 43 characters.
MAX_UNSUBSCRIBE_TOKEN = 200

# The order of a send's evidence; a provider event moves a row only up it. A local outcome (no event applied yet)
# ranks below every event, so the first signed event always applies.
_RANK = {
    STATUS_ACCEPTED: 1,
    STATUS_DELAYED: 2,
    STATUS_DELIVERED: 3,
    STATUS_BOUNCED: 4,
    STATUS_FAILED: 4,
    STATUS_SUPPRESSED: 4,
    STATUS_COMPLAINED: 5,
}
_EVENT_STATUS = {
    EVENT_SENT: STATUS_ACCEPTED,
    EVENT_DELAYED: STATUS_DELAYED,
    EVENT_DELIVERED: STATUS_DELIVERED,
    EVENT_BOUNCED: STATUS_BOUNCED,
    EVENT_FAILED: STATUS_FAILED,
    EVENT_SUPPRESSED: STATUS_SUPPRESSED,
    EVENT_COMPLAINED: STATUS_COMPLAINED,
}
# What an emailed invitation's response may call sent: the provider took it.
PROVIDER_TOOK = frozenset({STATUS_ACCEPTED, STATUS_DELAYED, STATUS_DELIVERED})

_ERROR_KIND = re.compile(r"[^A-Za-z0-9_:]")


@dataclass(frozen=True)
class Permission:
    """The admin's record that the recipient asked for an invitation: how, and on which day."""

    via: str
    requested_on: date

    def __post_init__(self) -> None:
        if self.via not in PERMISSION_VIA:
            raise ValueError(f"Unknown permission channel: {self.via}")


class RecipientSuppressed(Exception):
    """The address unsubscribed, bounced permanently, complained or is on the provider's suppression list."""

    def __init__(self, reason: Optional[str]):
        super().__init__(reason)
        self.reason = reason


class InvitePendingForAddress(Exception):
    """Another live invite is bound to this address, so a second link is not made for it."""

    def __init__(self, invite_id: int):
        super().__init__(invite_id)
        self.invite_id = invite_id


class InviteNotBound(Exception):
    """An emailed re-send needs the invite to be bound to an address."""


class PermissionRequired(Exception):
    """An emailed re-send of a link never emailed before needs the recipient's request recorded."""


@dataclass(frozen=True)
class PreparedInvite:
    """A committed link (and, when emailed, its delivery row), with the raw values the email alone carries."""

    issued: dict
    delivery_id: Optional[int] = None
    delivery_ref: Optional[str] = None
    unsubscribe_link: Optional[str] = None


@dataclass(frozen=True)
class SendOutcome:
    status: str
    provider_email_id: Optional[str] = None
    error_kind: Optional[str] = None


def build_unsubscribe_link(raw_token: str) -> str:
    """The page that takes the opt-out (frontend/app/email/unsubscribe/page.tsx). The token rides in the fragment,
    which no request carries, so no server or proxy log records it; the page posts it only when its reader asks."""
    return f"{settings.FRONTEND_URL}/email/unsubscribe#token={raw_token}"


def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issued_fields(invite: InviteCode, link: str) -> dict:
    """A minted invite's response fields, read in its unit while the row is loaded (E171)."""
    return {
        "id": invite.id,
        "email": invite.email,
        "invite_link": link,
        "expires_at": invite.expires_at,
        "cohort": invite.cohort,
    }


def _new_delivery(
    db: Session, invite: InviteCode, hashed: str, permission: Permission, created_by: Optional[int],
) -> tuple[InviteDelivery, str]:
    raw_unsubscribe = secrets.token_urlsafe(32)
    now = utcnow()
    delivery = InviteDelivery(
        invite_id=invite.id,
        recipient_hash=hashed,
        delivery_ref=uuid.uuid4().hex,
        unsubscribe_token_hash=_token_hash(raw_unsubscribe),
        status=STATUS_SENDING,
        permission_via=permission.via,
        permission_requested_on=permission.requested_on,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    db.add(delivery)
    db.flush()
    return delivery, raw_unsubscribe


def _refuse_suppressed(recipient) -> None:
    if recipient.suppressed_at is not None:
        raise RecipientSuppressed(recipient.suppression_reason)


def _refuse_second_live_link(db: Session, email: str, *, exclude_invite_id: Optional[int] = None) -> None:
    pending = invite_service.pending_invite_for_address(db, email, exclude_invite_id=exclude_invite_id)
    if pending is not None:
        raise InvitePendingForAddress(pending)


def prepare_invite_send(
    db: Session,
    *,
    created_by: Optional[int],
    email: str,
    expires_in_hours: Optional[int],
    cohort: Optional[str],
    permission: Permission,
) -> PreparedInvite:
    """Mint a link bound to ``email`` and commit it with its "sending" delivery, or refuse with nothing written.

    Under the address's lock: a suppressed address is refused (``RecipientSuppressed``), and so is a second live link
    (``InvitePendingForAddress``), so a repeated submit, a retried request or a second tab mints no second link; the
    second waits for the first's commit and then finds its link live. An opt-out that commits first is seen here."""
    hashed = mail_suppression_service.recipient_hash(email)
    try:
        recipient = mail_suppression_service.lock_recipient(db, hashed)
        _refuse_suppressed(recipient)
        _refuse_second_live_link(db, email)
        invite, _raw, link = invite_service.mint_invite(
            db, created_by=created_by, email=email, expires_in_hours=expires_in_hours, cohort=cohort, commit=False,
        )
        delivery, raw_unsubscribe = _new_delivery(db, invite, hashed, permission, created_by)
        prepared = PreparedInvite(
            issued=issued_fields(invite, link),
            delivery_id=delivery.id,
            delivery_ref=delivery.delivery_ref,
            unsubscribe_link=build_unsubscribe_link(raw_unsubscribe),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return prepared


def prepare_reissue(
    db: Session,
    invite_id: int,
    *,
    created_by: Optional[int],
    expires_in_hours: Optional[int],
    send_email: bool,
    permission: Optional[Permission],
) -> PreparedInvite:
    """Revoke an unused invite and mint its replacement (same email and cohort), and when ``send_email`` commit the
    replacement's "sending" delivery with them; or refuse with nothing written.

    A bound invite is re-issued under its address's lock and its own row lock, and refused while another live link is
    bound to the address, so two re-sends of one invite (a double press, a retry, two tabs) make one replacement: the
    second waits for the first's commit and then finds its replacement live. An emailed re-send also refuses a
    suppressed address, and needs the request the link was first emailed under, or ``permission`` when it never was.
    A manual re-send makes a link the admin shares; a suppressed address does not stop that."""
    try:
        current = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
        if current is None:
            raise invite_service.InviteNotFoundError(invite_id)
        if current.used_at is not None:
            raise invite_service.InviteAlreadyRedeemedError(invite_id)
        if send_email and not current.email:
            raise InviteNotBound(invite_id)
        hashed: Optional[str] = None
        if current.email:
            hashed = mail_suppression_service.recipient_hash(current.email)
            recipient = mail_suppression_service.lock_recipient(db, hashed)
            if send_email:
                _refuse_suppressed(recipient)
        old = invite_service.lock_unused_invite(db, invite_id)
        if old.email:
            _refuse_second_live_link(db, old.email, exclude_invite_id=invite_id)
        basis: Optional[Permission] = None
        if send_email:
            previous = db.query(InviteDelivery).filter(InviteDelivery.invite_id == invite_id).first()
            if previous is not None:
                basis = Permission(previous.permission_via, previous.permission_requested_on)
            elif permission is not None:
                basis = permission
            else:
                raise PermissionRequired(invite_id)
        invite, _raw, link = invite_service.reissue_invite(
            db, invite_id, created_by=created_by, expires_in_hours=expires_in_hours, commit=False,
        )
        if send_email and basis is not None and hashed is not None:
            delivery, raw_unsubscribe = _new_delivery(db, invite, hashed, basis, created_by)
            prepared = PreparedInvite(
                issued=issued_fields(invite, link),
                delivery_id=delivery.id,
                delivery_ref=delivery.delivery_ref,
                unsubscribe_link=build_unsubscribe_link(raw_unsubscribe),
            )
        else:
            prepared = PreparedInvite(issued=issued_fields(invite, link))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return prepared


def _error_kind(exc: BaseException) -> str:
    return _ERROR_KIND.sub("", type(exc).__name__)[:40] or "error"


async def deliver(prepared: PreparedInvite) -> SendOutcome:
    """Send one prepared invitation and classify what happened. Never raises; logs no address and no link."""
    if prepared.delivery_ref is None or prepared.unsubscribe_link is None:
        raise ValueError("deliver needs a prepared delivery")
    try:
        provider_email_id = await email_service.send_invite_email(
            to_email=prepared.issued["email"],
            magic_link=prepared.issued["invite_link"],
            unsubscribe_link=prepared.unsubscribe_link,
            delivery_ref=prepared.delivery_ref,
        )
    except email_service.PromotionalMailUnavailable:
        outcome = SendOutcome(STATUS_FAILED, error_kind="held")  # the sender's own readiness check refused it
    except ResendRetryableError:
        outcome = SendOutcome(STATUS_FAILED, error_kind="provider_retryable")  # no request reached the provider
    except ResendPermanentError:
        outcome = SendOutcome(STATUS_FAILED, error_kind="provider_rejected")
    except ResendAmbiguousError:
        outcome = SendOutcome(STATUS_UNKNOWN, error_kind="provider_ambiguous")
    except Exception as exc:  # noqa: BLE001 — an unclassified failure may have followed the request out
        outcome = SendOutcome(STATUS_UNKNOWN, error_kind=_error_kind(exc))
    else:
        valid = isinstance(provider_email_id, str) and 0 < len(provider_email_id) <= 64
        outcome = SendOutcome(STATUS_ACCEPTED, provider_email_id=provider_email_id if valid else None)
    if outcome.status != STATUS_ACCEPTED:
        logger.warning(
            "Invitation email for delivery %s ended %s (%s)", prepared.delivery_id, outcome.status, outcome.error_kind,
        )
    return outcome


def record_send_outcome(db: Session, delivery_id: int, outcome: SendOutcome) -> str:
    """Record the call's outcome on a row still "sending", commit, and return the row's status.

    A provider event that arrived before the call's answer has already moved the row, and it stands: this then only
    fills the provider's id where the event left none."""
    now = utcnow()
    moved = db.execute(
        update(InviteDelivery)
        .where(InviteDelivery.id == delivery_id, InviteDelivery.status == STATUS_SENDING)
        .values(
            status=outcome.status,
            provider_email_id=outcome.provider_email_id,
            error_kind=outcome.error_kind,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    ).rowcount
    if not moved and outcome.provider_email_id:
        db.execute(
            update(InviteDelivery)
            .where(InviteDelivery.id == delivery_id, InviteDelivery.provider_email_id.is_(None))
            .values(provider_email_id=outcome.provider_email_id, updated_at=now)
            .execution_options(synchronize_session=False)
        )
    db.commit()
    status = db.query(InviteDelivery.status).filter(InviteDelivery.id == delivery_id).scalar()
    return status or outcome.status


def unsubscribe(db: Session, raw_token: Optional[str]) -> bool:
    """Suppress the address an unsubscribe link was sent to, and commit. False when the token names no delivery.

    Idempotent: a second use, or one after a bounce or complaint suppressed the address, changes nothing and is
    still True, since the address is suppressed either way."""
    if not raw_token or len(raw_token) > MAX_UNSUBSCRIBE_TOKEN or not is_valid_unicode(raw_token):
        return False
    delivery = (
        db.query(InviteDelivery.recipient_hash, InviteDelivery.delivery_ref)
        .filter(InviteDelivery.unsubscribe_token_hash == _token_hash(raw_token))
        .first()
    )
    if delivery is None:
        return False
    try:
        mail_suppression_service.suppress(
            db, delivery.recipient_hash, SUPPRESSED_UNSUBSCRIBED, f"unsubscribe:{delivery.delivery_ref}",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def _view(delivery: InviteDelivery, now) -> dict:
    status = delivery.status
    if status == STATUS_SENDING and ensure_utc(delivery.updated_at) < now - STALE_SENDING:
        status = STATUS_UNKNOWN
    return {
        "status": status,
        "error_kind": delivery.error_kind,
        "bounce_type": delivery.bounce_type,
        "permission_via": delivery.permission_via,
        "permission_requested_on": delivery.permission_requested_on.isoformat(),
        "created_at": iso_z(ensure_utc(delivery.created_at)),
        "updated_at": iso_z(ensure_utc(delivery.updated_at)),
    }


def deliveries_for_invites(db: Session, invite_ids: Iterable[int]) -> dict[int, dict]:
    """Each emailed invite's delivery, as the admin list shows it; a row left "sending" reads unknown."""
    ids = sorted(set(invite_ids))
    if not ids:
        return {}
    now = utcnow()
    return {row.invite_id: _view(row, now) for row in db.query(InviteDelivery).filter(InviteDelivery.invite_id.in_(ids))}


def suppression_for_addresses(db: Session, addresses: Iterable[str]) -> dict[str, Optional[str]]:
    """The suppression reason of each suppressed address among ``addresses``, keyed by the address as given."""
    hashed = {mail_suppression_service.recipient_hash(a): a for a in addresses if a}
    found = mail_suppression_service.suppression_for(db, hashed)
    return {hashed[h]: reason for h, reason in found.items()}


def _correlate(db: Session, event: ProviderEvent) -> Optional[InviteDelivery]:
    """The delivery an event is about, under its row lock: by our tag first, which survives a lost answer, then by
    the provider's id."""
    query = db.query(InviteDelivery).with_for_update().populate_existing()
    if event.delivery_ref is not None:
        found = query.filter(InviteDelivery.delivery_ref == event.delivery_ref).first()
        if found is not None:
            return found
    if event.email_id is not None:
        return query.filter(InviteDelivery.provider_email_id == event.email_id).first()
    return None


def _suppression_reason(event: ProviderEvent) -> Optional[str]:
    if event.type == EVENT_COMPLAINED:
        return SUPPRESSED_COMPLAINT
    if event.type == EVENT_SUPPRESSED:
        return SUPPRESSED_BY_PROVIDER
    if event.type == EVENT_BOUNCED and event.bounce_type == BOUNCE_PERMANENT:
        return SUPPRESSED_HARD_BOUNCE
    return None


def apply_provider_event(db: Session, event: ProviderEvent) -> None:
    """Apply one signed provider event and commit: the delivery it is about moves up its evidence order (never down,
    so a duplicate, a retry or a late event changes nothing), and a permanent bounce, a complaint or the provider's
    suppression suppresses each address it names, for any of our mail, invitation or not."""
    try:
        delivery = _correlate(db, event)
        if delivery is not None and delivery.last_event_id != event.event_id:
            status = _EVENT_STATUS[event.type]
            current = 0 if delivery.last_event_id is None else _RANK.get(delivery.status, 0)
            now = utcnow()
            if _RANK[status] > current:
                delivery.status = status
                delivery.last_event_id = event.event_id
                delivery.last_event_at = now
                if event.type == EVENT_BOUNCED:
                    delivery.bounce_type = event.bounce_type
                elif event.type == EVENT_FAILED:
                    delivery.error_kind = f"provider:{event.failure_reason}"[:40]
                elif event.type == EVENT_SUPPRESSED:
                    delivery.error_kind = "provider_suppression_list"
            if delivery.provider_email_id is None and event.email_id is not None:
                delivery.provider_email_id = event.email_id
            delivery.updated_at = now
        reason = _suppression_reason(event)
        if reason is not None:
            hashes = {mail_suppression_service.recipient_hash(address) for address in event.recipients}
            if delivery is not None:
                hashes.add(delivery.recipient_hash)
            for hashed in sorted(hashes):
                mail_suppression_service.suppress(db, hashed, reason, f"resend:{event.event_id}")
        db.commit()
    except Exception:
        db.rollback()
        raise


__all__ = [
    "InviteNotBound",
    "InvitePendingForAddress",
    "Permission",
    "PermissionRequired",
    "PreparedInvite",
    "PROVIDER_TOOK",
    "RecipientSuppressed",
    "SendOutcome",
    "apply_provider_event",
    "build_unsubscribe_link",
    "issued_fields",
    "deliver",
    "deliveries_for_invites",
    "prepare_invite_send",
    "prepare_reissue",
    "record_send_outcome",
    "suppression_for_addresses",
    "unsubscribe",
]
