"""Durable screenshot cleanup; known keys survive account deletion and failed object I/O.

Each claim/acknowledgement owns a short SQL unit. No connection is checked out while Google
is contacted. Overlapping jobs skip leased claims, and acknowledgements compare the claim
counter so a delayed attempt cannot overwrite a newer outcome.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import struct
from time import monotonic
from uuid import uuid4
import zlib

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
from app.services.feedback_storage_service import FeedbackStorage, FeedbackStorageError, make_feedback_object_key
from app.utils.datetimes import ensure_utc, utcnow


CLAIM_DURATION = timedelta(minutes=15)
REMOVAL_TARGET = timedelta(hours=24)
MAX_RUN_SECONDS = 450.0


def _probe_png() -> bytes:
    def chunk(kind: bytes, content: bytes) -> bytes:
        return struct.pack("!I", len(content)) + kind + content + struct.pack("!I", zlib.crc32(kind + content))
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b"")
    )


@dataclass(frozen=True)
class _CleanupClaim:
    attachment_id: str
    object_key: str
    generation: str | None
    attempt: int


def enqueue_owner_media_deletion(db: Session, owner_id: int, *, now: datetime | None = None) -> None:
    """Run inside account deletion, after its users row lock and before its commit.

    A pending write may already be executing without a DB connection. Revoke access now,
    but retain the normal 24-hour orphan grace before inspecting its object. An unknown
    404 remains a periodically checked tombstone, because the server can commit late.
    """
    now = ensure_utc(now or utcnow())
    rows = db.query(FeedbackAttachment).filter(FeedbackAttachment.owner_id == owner_id).all()
    for attachment in rows:
        attachment.owner_id = None
        if attachment.deleted_at is not None:
            continue
        pending_write = attachment.feedback_id is None
        safe_after = ensure_utc(attachment.created_at) + timedelta(hours=24) if pending_write else now
        attachment.state = "purge_pending"
        attachment.deletion_due_at = max(now, safe_after)
    db.query(FeedbackSubmission).filter(FeedbackSubmission.owner_id == owner_id).update(
        {"owner_id": None, "state": "retryable", "updated_at": now}, synchronize_session=False,
    )
    # Match PostgreSQL SET NULL even in the SQLite test harness; text reports remain retained.
    db.query(Feedback).filter(Feedback.user_id == owner_id).update(
        {"user_id": None}, synchronize_session=False,
    )


def _due(db: Session, now: datetime):
    return db.query(FeedbackAttachment).filter(
        FeedbackAttachment.deleted_at.is_(None),
        FeedbackAttachment.deletion_due_at <= now,
        FeedbackAttachment.state.in_(("pending", "available", "purge_pending", "absent_unknown")),
    )


def _claim(session_factory: Callable[[], Session], now: datetime) -> _CleanupClaim | None:
    with session_factory() as db:
        row = _due(db, now).filter(or_(
            FeedbackAttachment.last_cleanup_attempt_at.is_(None),
            FeedbackAttachment.last_cleanup_attempt_at <= now - CLAIM_DURATION,
        )).order_by(
            case((FeedbackAttachment.state == "absent_unknown", 1), else_=0),
            FeedbackAttachment.last_cleanup_attempt_at.asc().nullsfirst(),
            FeedbackAttachment.deletion_due_at, FeedbackAttachment.id,
        ).with_for_update(
            skip_locked=True,
        ).first()
        if row is None:
            return None
        row.state = "purge_pending"
        row.cleanup_attempts += 1
        row.last_cleanup_attempt_at = now
        claim = _CleanupClaim(row.id, row.object_key, row.object_generation, row.cleanup_attempts)
        db.commit()
        return claim


def _acknowledge(
    session_factory: Callable[[], Session], claim: _CleanupClaim, now: datetime, error: str | None,
    *, absent_unknown: bool = False, observed_generation: str | None = None,
) -> None:
    with session_factory() as db:
        row = db.query(FeedbackAttachment).filter(
            FeedbackAttachment.id == claim.attachment_id,
            FeedbackAttachment.state == "purge_pending",
            FeedbackAttachment.deleted_at.is_(None),
            FeedbackAttachment.cleanup_attempts == claim.attempt,
        ).with_for_update().first()
        if row is None:
            return
        row.last_cleanup_error = error
        if observed_generation is not None:
            row.object_generation = observed_generation
        if error is None and absent_unknown:
            row.state = "absent_unknown"
            row.deletion_due_at = now + timedelta(days=1)
        elif error is None:
            row.state = "deleted"
            row.deleted_at = now
        db.commit()


def run_feedback_media_cleanup(
    session_factory: Callable[[], Session], storage: FeedbackStorage | None, *, dry_run: bool = False,
    batch_size: int = 100, now: datetime | None = None, deadline_seconds: float = MAX_RUN_SECONDS,
) -> dict[str, int | bool]:
    """Process one bounded run, returning content-free counters for the job ledger.

    Dry runs do not claim rows or contact storage. A failure retains the complete manifest
    for a future hourly run; neither failed work nor an overdue backlog counts as healthy.
    """
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be between 1 and 1000")
    if not 0 < deadline_seconds <= MAX_RUN_SECONDS:
        raise ValueError("deadline_seconds must be positive and at most 450")
    if not dry_run and storage is None:
        raise ValueError("object storage is required for cleanup")
    now = ensure_utc(now or utcnow())
    stats: dict[str, int | bool] = {
        "dry_run": dry_run, "eligible": 0, "deleted": 0, "errors": 0, "overdue": 0, "pending_verification": 0,
    }
    with session_factory() as db:
        stats["eligible"] = _due(db, now).count()
    started = monotonic()
    if not dry_run:
        for _ in range(batch_size):
            if monotonic() - started >= deadline_seconds:
                break
            claim = _claim(session_factory, now)
            if claim is None:
                break
            error = None
            observed_generation = None
            try:
                assert storage is not None
                observed_generation = storage.delete(claim.object_key, claim.generation)
            except FeedbackStorageError as exc:
                error = exc.code if exc.code in (
                    "storage_unavailable", "storage_not_configured", "generation_conflict",
                    "invalid_object_key", "invalid_generation",
                ) else "storage_error"
            except Exception:
                error = "storage_error"
            absent_unknown = error is None and claim.generation is None and observed_generation is None
            _acknowledge(
                session_factory, claim, now, error, absent_unknown=absent_unknown,
                observed_generation=observed_generation,
            )
            if error:
                stats["errors"] += 1
            elif not absent_unknown:
                stats["deleted"] += 1
    with session_factory() as db:
        stats["overdue"] = _due(db, now).filter(
            FeedbackAttachment.object_generation.is_not(None),
            FeedbackAttachment.deletion_due_at <= now - REMOVAL_TARGET,
        ).count()
        stats["pending_verification"] = db.query(FeedbackAttachment).filter(
            FeedbackAttachment.state == "absent_unknown", FeedbackAttachment.deleted_at.is_(None),
        ).count()
    return stats


def verify_feedback_media_storage(
    session_factory: Callable[[], Session], storage: FeedbackStorage, *, now: datetime | None = None,
) -> dict[str, int]:
    """Exercise real create/read/delete with a durable, ownerless synthetic manifest.

    The manifest precedes any object write. A killed probe therefore leaves cleanup evidence,
    and no screenshot is readable through the user/admin API because it has no owner.
    """
    now = ensure_utc(now or utcnow())
    data = _probe_png()
    submission_id, attempt_token, attachment_id = (str(uuid4()) for _ in range(3))
    object_key = make_feedback_object_key(attempt_token, attachment_id)
    with session_factory() as db:
        db.add(FeedbackSubmission(
            id=submission_id, owner_id=None, submission_key=str(uuid4()),
            fingerprint=hashlib.sha256(data).hexdigest(), state="retryable", attempt_token=attempt_token,
            lease_expires_at=now, attempt_count=1, created_at=now, updated_at=now,
        ))
        db.flush()
        db.add(FeedbackAttachment(
            id=attachment_id, submission_id=submission_id, attempt_token=attempt_token, owner_id=None,
            object_key=object_key, checksum=hashlib.sha256(data).hexdigest(), content_type="image/png",
            width=1, height=1, byte_count=len(data), state="purge_pending", created_at=now,
            deletion_due_at=now, cleanup_attempts=1, last_cleanup_attempt_at=now,
        ))
        db.commit()
    claim = _CleanupClaim(attachment_id, object_key, None, 1)
    stats = {"storage_verified": 0, "deleted": 0, "errors": 0, "pending_verification": 0}
    generation = None
    try:
        generation = storage.upload(object_key, data)
        with session_factory() as db:
            db.query(FeedbackAttachment).filter(FeedbackAttachment.id == attachment_id).update(
                {"object_generation": generation}, synchronize_session=False,
            )
            db.commit()
        if storage.download(object_key, generation) != data:
            raise FeedbackStorageError("probe_content_mismatch")
        stats["storage_verified"] = 1
    except Exception:
        stats["errors"] += 1
    finally:
        error = None
        observed_generation = None
        try:
            observed_generation = storage.delete(object_key, generation)
            stats["deleted"] = int(generation is not None or observed_generation is not None)
        except Exception:
            stats["errors"] += 1
            error = "storage_error"
        absent_unknown = error is None and generation is None and observed_generation is None
        stats["pending_verification"] = int(absent_unknown)
        _acknowledge(
            session_factory, claim, now, error, absent_unknown=absent_unknown,
            observed_generation=observed_generation,
        )
    return stats
