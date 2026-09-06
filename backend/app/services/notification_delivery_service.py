"""Durable alert delivery (E11b-1): persist first, claim with a fence, send with no session open.

Selection (``filing_scan_service``) renders the exact email and calls :func:`create_batch`, which
commits the frozen payload, its provider idempotency key and the owned filings BEFORE any send.
:func:`drain` then walks due batches through fenced conditional transitions::

    ready ─claim─▶ claimed ─authorize─▶ sending ─finalize─▶ accepted | retryable | ambiguous
                     │                                        (retryable ─due─▶ ready-like claim)
                     └──recheck failed / window or attempts exhausted──▶ suppressed | ambiguous

Every transition is ``UPDATE … WHERE id = ? AND status = ? AND owner_token = ?`` with the
rowcount checked, so a stale worker can never reach the send. The ``sending`` transition is
committed, and the session holds no transaction, while the provider call runs; a fresh short
transaction finalises only the same owned attempt. An expired preparation claim is reclaimed;
an expired sending lease is not (the email may have been accepted) and the batch is parked as
``ambiguous`` for reconciliation, as is any batch whose replay window closed, whose attempts are
exhausted, or whose frozen payload no longer matches its key. The compatibility ``NotificationLog``
row and the watchlist watermark are written only when the provider accepts the email.

Historical ``NotificationLog`` rows are never mutated or replayed here. No queue, Redis or job
provisioning: the existing scheduled entry points call the scan services, which call ``drain``.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional
from uuid import uuid4

from sqlalchemy import func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, Filing, User, Watchlist
from app.models.notification_delivery import (
    KIND_FILING_REALTIME,
    STATUS_ACCEPTED,
    STATUS_AMBIGUOUS,
    STATUS_CLAIMED,
    STATUS_READY,
    STATUS_RETRYABLE,
    STATUS_SENDING,
    STATUS_SUPPRESSED,
    DeliveryBatch,
    DeliveryItem,
)
from app.models.notifications import CHANNEL_EMAIL
from app.services import resend_service
from app.services.entitlements import get_entitlements
from app.services.notification_service import evaluate_delivery, get_or_create_preferences
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)

# last_error_kind values (short, PII-free; surfaced only as counters and per-row reasons).
ERROR_PAYLOAD_DRIFT = "payload_drift"
ERROR_WINDOW_EXPIRED = "window_expired"
ERROR_LEASE_EXPIRED = "lease_expired"
ERROR_ATTEMPTS_EXHAUSTED = "attempts_exhausted"
ERROR_ELIGIBILITY_CHANGED = "eligibility_changed"
ERROR_PROVIDER_REJECTED = "provider_rejected"
ERROR_PROVIDER_RETRYABLE = "provider_retryable"
ERROR_PROVIDER_AMBIGUOUS = "provider_ambiguous"


@dataclass
class PreparedSend:
    """Everything the transport needs, loaded before the ``sending`` commit so no query runs
    while the provider call is in flight."""

    batch_id: int
    kind: str
    to_email: str
    from_email: str
    name: Optional[str]
    subject: str
    html: str
    idempotency_key: str
    items: list[dict] = field(default_factory=list)  # digest/alert item dicts (legacy sender shape)


Send = Callable[[PreparedSend], Awaitable[Optional[str]]]


@dataclass
class DrainStats:
    accepted: int = 0
    accepted_items: int = 0
    retryable: int = 0
    ambiguous: int = 0
    rejected: int = 0    # provider refused the payload (a delivery failure)
    suppressed: int = 0  # current eligibility forbids dispatch (not a failure)
    lost_claims: int = 0

    def as_dict(self) -> dict:
        return {
            "delivery_accepted": self.accepted,
            "delivery_retryable": self.retryable,
            "delivery_ambiguous": self.ambiguous,
            "delivery_rejected": self.rejected,
            "delivery_suppressed": self.suppressed,
        }


def payload_digest(subject: str, html: str, *, to_email: str, from_email: str) -> str:
    envelope = {"to": [to_email], "from": from_email, "subject": subject, "html": html}
    return hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- selection

def already_owned(db: Session, user_id: int, filing_id: int, channel: str = CHANNEL_EMAIL) -> bool:
    """A filing owned by any batch (whatever its state) is never selected again for this user."""
    return db.query(DeliveryItem.id).filter(
        DeliveryItem.user_id == user_id, DeliveryItem.filing_id == filing_id, DeliveryItem.channel == channel,
    ).first() is not None


def create_batch(
    db: Session,
    *,
    kind: str,
    user_id: int,
    subject: str,
    html: str,
    filing_ids: list[int],
    channel: str = CHANNEL_EMAIL,
    now: Optional[datetime] = None,
) -> Optional[DeliveryBatch]:
    """Commit the frozen payload, its idempotency key and the ordered owned filings, or nothing.

    Returns ``None`` when another batch already owns one of the filings for this user (the
    unique constraint fires inside a SAVEPOINT, so the caller's pending work survives).
    """
    now = now or utcnow()
    user = db.get(User, user_id)
    if user is None or not filing_ids:
        raise ValueError("Delivery selection requires a user and at least one filing")
    to_email, from_email = user.email, settings.RESEND_FROM_EMAIL
    batch = DeliveryBatch(
        to_email=to_email, from_email=from_email, expected_item_count=len(filing_ids),
        kind=kind, user_id=user_id, channel=channel, subject=subject, body_html=html,
        payload_sha256=payload_digest(subject, html, to_email=to_email, from_email=from_email), idempotency_key=uuid4().hex,
        status=STATUS_READY, attempts=0, created_at=now, updated_at=now,
    )
    batch.items = [
        DeliveryItem(user_id=user_id, filing_id=fid, channel=channel, position=i)
        for i, fid in enumerate(filing_ids)
    ]
    try:
        with db.begin_nested():
            db.add(batch)
            db.flush()
    except IntegrityError:
        return None
    db.commit()
    return batch


# --------------------------------------------------------------------------- fenced transitions
# Updates skip the ORM's in-Python session sync: SQLite hands back naive datetimes that the
# 'evaluate' strategy cannot compare with the aware clock; the database decides, and callers re-read.

def _transition(db: Session, batch_id: int, token: Optional[str], from_status: str, now: datetime, **values) -> bool:
    """One conditional update; True iff this worker still owned the batch in ``from_status``."""
    stmt = update(DeliveryBatch).where(
        DeliveryBatch.id == batch_id, DeliveryBatch.status == from_status, DeliveryBatch.owner_token == token,
    ).values(updated_at=now, **values)
    changed = db.execute(stmt.execution_options(synchronize_session=False)).rowcount == 1
    db.commit()
    return changed


def claim(db: Session, batch_id: int, owner_token: str, now: datetime) -> bool:
    """ready/retryable (due, unowned) → claimed under a short preparation lease."""
    stmt = update(DeliveryBatch).where(
        DeliveryBatch.id == batch_id,
        DeliveryBatch.status.in_([STATUS_READY, STATUS_RETRYABLE]),
        DeliveryBatch.owner_token.is_(None),
        or_(DeliveryBatch.next_attempt_at.is_(None), DeliveryBatch.next_attempt_at <= now),
    ).values(
        status=STATUS_CLAIMED, owner_token=owner_token, updated_at=now,
        lease_expires_at=now + timedelta(seconds=settings.DELIVERY_CLAIM_TTL_SECONDS),
    )
    changed = db.execute(stmt.execution_options(synchronize_session=False)).rowcount == 1
    db.commit()
    return changed


def authorize_send(db: Session, batch_id: int, owner_token: str, now: datetime) -> bool:
    """claimed → sending. Committed before any network I/O; anchors the replay window once."""
    stmt = update(DeliveryBatch).where(
        DeliveryBatch.id == batch_id, DeliveryBatch.status == STATUS_CLAIMED,
        DeliveryBatch.owner_token == owner_token, DeliveryBatch.lease_expires_at > now,
        or_(DeliveryBatch.first_dispatch_at.is_(None),
            DeliveryBatch.first_dispatch_at > now - timedelta(seconds=settings.DELIVERY_REPLAY_WINDOW_SECONDS)),
    ).values(
        status=STATUS_SENDING, attempts=DeliveryBatch.attempts + 1, updated_at=now,
        first_dispatch_at=func.coalesce(DeliveryBatch.first_dispatch_at, now),
        lease_expires_at=now + timedelta(seconds=settings.DELIVERY_SEND_TTL_SECONDS),
    )
    changed = db.execute(stmt.execution_options(synchronize_session=False)).rowcount == 1
    db.commit()
    return changed


def park(db: Session, batch_id: int, owner_token: Optional[str], from_status: str, status: str, reason: str, now: datetime) -> bool:
    """claimed/sending → suppressed or ambiguous (terminal), keeping the reason."""
    logger.debug("Delivery %s: %s -> %s (%s)", batch_id, from_status, status, reason)
    return _transition(
        db, batch_id, owner_token, from_status, now,
        status=status, owner_token=None, lease_expires_at=None, last_error_kind=reason,
    )


def finalize_retryable(db: Session, batch: DeliveryBatch, owner_token: str, now: datetime) -> bool:
    backoff = settings.DELIVERY_RETRY_BACKOFF_SECONDS * (2 ** max(0, batch.attempts - 1))
    return _transition(
        db, batch.id, owner_token, STATUS_SENDING, now,
        status=STATUS_RETRYABLE, owner_token=None, lease_expires_at=None,
        next_attempt_at=now + timedelta(seconds=backoff), last_error_kind=ERROR_PROVIDER_RETRYABLE,
    )


def finalize_accepted(db: Session, batch: DeliveryBatch, owner_token: str, provider_email_id: Optional[str], now: datetime) -> bool:
    """sending → accepted, and only then the compatibility log rows and watermarks, in one commit."""
    from app.services.filing_scan_service import _advance_watermark, _write_log  # single source of truth

    stmt = update(DeliveryBatch).where(
        DeliveryBatch.id == batch.id, DeliveryBatch.status == STATUS_SENDING, DeliveryBatch.owner_token == owner_token,
    ).values(
        status=STATUS_ACCEPTED, owner_token=None, lease_expires_at=None, last_error_kind=None,
        provider_email_id=(provider_email_id or None), updated_at=now,
    )
    if db.execute(stmt.execution_options(synchronize_session=False)).rowcount != 1:
        db.rollback()
        return False
    for item in batch.items:
        filing = db.get(Filing, item.filing_id)
        if filing is None:
            continue
        _write_log(db, item.user_id, item.filing_id, item.channel, "sent")
        watch = db.query(Watchlist).filter(
            Watchlist.user_id == item.user_id, Watchlist.company_id == filing.company_id,
        ).first()
        if watch is not None:
            _advance_watermark(watch, filing)
    db.commit()
    return True


def expire_stale(db: Session, now: datetime, *, kind: Optional[str] = None) -> dict:
    """Reclaim expired preparation claims; park expired sending leases and closed replay windows."""
    counts = {"reclaimed": 0, "lease_expired": 0, "window_expired": 0}
    window = timedelta(seconds=settings.DELIVERY_REPLAY_WINDOW_SECONDS)
    query = db.query(DeliveryBatch).filter(
        DeliveryBatch.status.in_([STATUS_CLAIMED, STATUS_SENDING, STATUS_RETRYABLE]),
    )
    if kind is not None:
        query = query.filter(DeliveryBatch.kind == kind)
    for batch in query.all():
        lease = _aware(batch.lease_expires_at)
        first = _aware(batch.first_dispatch_at)
        if batch.status == STATUS_CLAIMED and lease is not None and lease <= now:
            if _transition(db, batch.id, batch.owner_token, STATUS_CLAIMED, now,
                           status=STATUS_READY, owner_token=None, lease_expires_at=None):
                counts["reclaimed"] += 1
        elif batch.status == STATUS_SENDING and lease is not None and lease <= now:
            # The owner may have been accepted by the provider and died before finalising.
            if park(db, batch.id, batch.owner_token, STATUS_SENDING, STATUS_AMBIGUOUS, ERROR_LEASE_EXPIRED, now):
                counts["lease_expired"] += 1
        elif batch.status == STATUS_RETRYABLE and first is not None and first + window <= now:
            if _transition(db, batch.id, None, STATUS_RETRYABLE, now,
                           status=STATUS_AMBIGUOUS, last_error_kind=ERROR_WINDOW_EXPIRED, next_attempt_at=None):
                counts["window_expired"] += 1
    return counts


def due_batch_ids(db: Session, kind: str, now: datetime) -> list[int]:
    """Durable records only: selection never consults watchlist watermarks."""
    return [row[0] for row in db.query(DeliveryBatch.id).filter(
        DeliveryBatch.kind == kind,
        DeliveryBatch.status.in_([STATUS_READY, STATUS_RETRYABLE]),
        DeliveryBatch.owner_token.is_(None),
        or_(DeliveryBatch.next_attempt_at.is_(None), DeliveryBatch.next_attempt_at <= now),
    ).order_by(DeliveryBatch.id).all()]


# --------------------------------------------------------------------------- dispatch

def _item_dicts(db: Session, batch: DeliveryBatch) -> list[dict]:
    from app.services.filing_scan_service import _filing_date_str

    out = []
    for item in batch.items:
        filing = db.get(Filing, item.filing_id)
        company = db.get(Company, filing.company_id) if filing is not None else None
        if filing is None or company is None:
            continue
        out.append({
            "company_name": company.name, "ticker": company.ticker, "filing_type": filing.filing_type,
            "filing_date": _filing_date_str(filing.filing_date), "filing_id": filing.id, "filing_url": filing.sec_url,
        })
    return out


def _still_eligible(db: Session, batch: DeliveryBatch, user: User) -> bool:
    """Current user, watch, preference and entitlement state must still allow every owned item."""
    if (not user.is_active or user.email != batch.to_email
            or not batch.items or len(batch.items) != batch.expected_item_count):
        return False
    prefs = get_or_create_preferences(db, user.id)
    ent = get_entitlements(user)
    for item in batch.items:
        filing = db.get(Filing, item.filing_id)
        if filing is None:
            return False
        watched = db.query(Watchlist.id).filter(
            Watchlist.user_id == user.id, Watchlist.company_id == filing.company_id,
        ).first() is not None
        if not watched:
            return False
        eligible, realtime = evaluate_delivery(prefs, ent, filing.filing_type)
        if not eligible or (batch.kind == KIND_FILING_REALTIME and not realtime):
            return False
    return True


async def send_prepared(prepared: PreparedSend) -> Optional[str]:
    """Default transport: the frozen payload under its persisted idempotency key."""
    result = await resend_service.send_email(
        to=[prepared.to_email], subject=prepared.subject, html=prepared.html,
        idempotency_key=prepared.idempotency_key, from_email=prepared.from_email,
    )
    return str(result.get("id")) if isinstance(result, dict) and result.get("id") else None


async def drain(
    db: Session, *, kind: str, send: Optional[Send] = None,
    now: Optional[datetime] = None, clock: Optional[Callable[[], datetime]] = None,
) -> DrainStats:
    """Dispatch every due batch of ``kind`` through the fenced state machine."""
    # Explicit now remains a deterministic test seam; production always reads a live clock.
    fixed_now = _aware(now)
    if clock is None:
        clock = (lambda: fixed_now) if fixed_now is not None else utcnow
    send = send or send_prepared
    stats = DrainStats()
    now = clock()
    expired = expire_stale(db, now, kind=kind)
    stats.ambiguous += expired["lease_expired"] + expired["window_expired"]
    for batch_id in due_batch_ids(db, kind, now):
        now = clock()
        token = uuid4().hex
        if not claim(db, batch_id, token, now):
            stats.lost_claims += 1
            continue
        batch = db.get(DeliveryBatch, batch_id)
        db.refresh(batch)
        first = _aware(batch.first_dispatch_at)
        if batch.attempts >= settings.DELIVERY_MAX_ATTEMPTS:
            park(db, batch_id, token, STATUS_CLAIMED, STATUS_AMBIGUOUS, ERROR_ATTEMPTS_EXHAUSTED, now)
            stats.ambiguous += 1
            continue
        if first is not None and first + timedelta(seconds=settings.DELIVERY_REPLAY_WINDOW_SECONDS) <= now:
            park(db, batch_id, token, STATUS_CLAIMED, STATUS_AMBIGUOUS, ERROR_WINDOW_EXPIRED, now)
            stats.ambiguous += 1
            continue
        if payload_digest(batch.subject, batch.body_html, to_email=batch.to_email, from_email=batch.from_email) != batch.payload_sha256:
            park(db, batch_id, token, STATUS_CLAIMED, STATUS_AMBIGUOUS, ERROR_PAYLOAD_DRIFT, now)
            stats.ambiguous += 1
            continue
        user = db.get(User, batch.user_id)
        if user is None or not _still_eligible(db, batch, user):
            park(db, batch_id, token, STATUS_CLAIMED, STATUS_SUPPRESSED, ERROR_ELIGIBILITY_CHANGED, now)
            stats.suppressed += 1
            continue
        prepared = PreparedSend(
            batch_id=batch.id, kind=batch.kind, to_email=batch.to_email, from_email=batch.from_email, name=user.full_name,
            subject=batch.subject, html=batch.body_html, idempotency_key=batch.idempotency_key,
            items=_item_dicts(db, batch),
        )
        item_count = len(batch.items)
        now = clock()
        if not authorize_send(db, batch_id, token, now):
            stats.lost_claims += 1
            continue
        # The sending transition is committed and the session holds no transaction here.
        outcome, reason, provider_id = STATUS_ACCEPTED, None, None
        try:
            provider_id = await send(prepared)
        except resend_service.ResendRetryableError as e:
            outcome, reason = STATUS_RETRYABLE, ERROR_PROVIDER_RETRYABLE
            logger.warning("Delivery %s retryable: %s", batch_id, e.__class__.__name__)
        except resend_service.ResendPermanentError as e:
            outcome, reason = STATUS_SUPPRESSED, ERROR_PROVIDER_REJECTED
            logger.warning("Delivery %s rejected by provider: %s", batch_id, e.__class__.__name__)
        except asyncio.CancelledError:
            # Cancellation after bytes may have left: park for reconciliation, then propagate.
            park(db, batch_id, token, STATUS_SENDING, STATUS_AMBIGUOUS, ERROR_PROVIDER_AMBIGUOUS, clock())
            raise
        except Exception as e:  # timeouts, dropped connections, parse failures: acceptance unknown
            outcome, reason = STATUS_AMBIGUOUS, ERROR_PROVIDER_AMBIGUOUS
            logger.warning("Delivery %s outcome unknown: %s", batch_id, e.__class__.__name__)
        now = clock()
        batch = db.get(DeliveryBatch, batch_id)  # fresh short transaction for finalisation
        if outcome == STATUS_ACCEPTED:
            if finalize_accepted(db, batch, token, provider_id, now):
                stats.accepted += 1
                stats.accepted_items += item_count
            else:
                stats.lost_claims += 1
        elif outcome == STATUS_RETRYABLE:
            finalize_retryable(db, batch, token, now)
            stats.retryable += 1
        elif outcome == STATUS_SUPPRESSED:
            park(db, batch_id, token, STATUS_SENDING, STATUS_SUPPRESSED, reason, now)
            stats.rejected += 1
        else:
            park(db, batch_id, token, STATUS_SENDING, STATUS_AMBIGUOUS, reason, now)
            stats.ambiguous += 1
    return stats
