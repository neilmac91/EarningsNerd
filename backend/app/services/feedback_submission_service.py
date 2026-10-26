"""Feedback receipts, leases and publication. SQL units contain no network or HTTP work.

Every writer locks the owner first, like account deletion. A submission's attempt token and
lease fence late workers; object manifests are committed before the first storage write.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackSubmissionStatus
from app.utils.datetimes import ensure_utc, iso_z, utcnow

LEASE_SECONDS = 120
MAX_SUBMISSIONS_PER_HOUR = 10
MAX_ATTEMPTS = 8


class FeedbackSubmissionError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SubmissionClaim:
    submission_id: str
    attempt_token: str | None
    receipt: FeedbackSubmissionStatus


@dataclass(frozen=True)
class AttachmentManifest:
    id: str
    object_key: str


@dataclass(frozen=True)
class PrivateMedia:
    object_key: str
    object_generation: str
    byte_count: int
    checksum: str


def payload_fingerprint(payload: FeedbackCreate, images: list[bytes]) -> str:
    """Compare actual bytes, including on completed replays; a client digest is never trusted."""
    canonical = {
        "payload": payload.model_dump(),
        "images": [hashlib.sha256(image).hexdigest() for image in images],
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bound_transaction(db: Session) -> None:
    """Bound lock/statement waits locally; never change pooled connection defaults."""
    if db.get_bind().dialect.name == "postgresql":
        db.scalar(select(func.set_config("lock_timeout", "3s", True)))
        db.scalar(select(func.set_config("statement_timeout", "10s", True)))


def _lock_owner(db: Session, owner_id: int) -> None:
    _bound_transaction(db)
    owner = db.query(User.id).filter(User.id == owner_id, User.is_active.is_(True)).with_for_update().first()
    if owner is None:
        raise FeedbackSubmissionError("owner_missing")


def _receipt(db: Session, row: FeedbackSubmission) -> FeedbackSubmissionStatus:
    feedback = None
    remaining = max(0, math.ceil((ensure_utc(row.lease_expires_at) - utcnow()).total_seconds()))
    state = row.state
    if state == "submitted":
        saved = db.get(Feedback, row.feedback_id)
        if saved is None:
            raise FeedbackSubmissionError("not_found")
        feedback = FeedbackResponse.model_validate(saved)
    elif state == "processing" and remaining == 0:
        state = "retryable"
    return FeedbackSubmissionStatus(
        submission_id=row.submission_key,
        state=state,
        retry_after_seconds=remaining if state == "processing" else None,
        feedback=feedback,
    )


def read_receipt(db: Session, owner_id: int, submission_key: str) -> FeedbackSubmissionStatus:
    _bound_transaction(db)
    row = db.query(FeedbackSubmission).filter_by(owner_id=owner_id, submission_key=submission_key).first()
    if row is None:
        raise FeedbackSubmissionError("not_found")
    return _receipt(db, row)


def claim_submission(db: Session, owner_id: int, submission_key: str, fingerprint: str) -> SubmissionClaim:
    """Atomically locate before charging. Completed/active replays consume no new-report quota."""
    _lock_owner(db, owner_id)
    now = utcnow()
    row = db.query(FeedbackSubmission).filter_by(owner_id=owner_id, submission_key=submission_key).with_for_update().first()
    if row is not None:
        if row.fingerprint != fingerprint:
            raise FeedbackSubmissionError("key_conflict")
        receipt = _receipt(db, row)
        if receipt.state != "retryable":
            return SubmissionClaim(row.id, None, receipt)
        if row.attempt_count >= MAX_ATTEMPTS:
            raise FeedbackSubmissionError("retry_limit")
        row.attempt_count += 1
    else:
        count = db.query(FeedbackSubmission.id).filter(
            FeedbackSubmission.owner_id == owner_id,
            FeedbackSubmission.created_at >= now - timedelta(hours=1),
        ).count()
        if count >= MAX_SUBMISSIONS_PER_HOUR:
            raise FeedbackSubmissionError("quota")
        row = FeedbackSubmission(
            id=str(uuid4()), owner_id=owner_id, submission_key=submission_key,
            fingerprint=fingerprint, attempt_count=1, created_at=now,
        )
        db.add(row)
    row.state = "processing"
    row.attempt_token = str(uuid4())
    row.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    row.updated_at = now
    result = SubmissionClaim(row.id, row.attempt_token, FeedbackSubmissionStatus(
        submission_id=submission_key, state="processing", retry_after_seconds=LEASE_SECONDS,
    ))
    db.commit()
    return result


def _current_attempt(db: Session, owner_id: int, claim: SubmissionClaim) -> FeedbackSubmission:
    _lock_owner(db, owner_id)
    row = db.query(FeedbackSubmission).filter_by(id=claim.submission_id, owner_id=owner_id).with_for_update().first()
    if (row is None or row.state != "processing" or row.attempt_token != claim.attempt_token
            or ensure_utc(row.lease_expires_at) <= utcnow()):
        raise FeedbackSubmissionError("stale_attempt")
    return row


def reserve_attachments(db: Session, owner_id: int, claim: SubmissionClaim, images: list) -> list[AttachmentManifest]:
    """Persist every key before any object write; images are already normalized, trusted DTOs."""
    from app.services.feedback_storage_service import make_feedback_object_key

    _current_attempt(db, owner_id, claim)
    now = utcnow()
    manifests = []
    for position, image in enumerate(images):
        attachment_id = str(uuid4())
        object_key = make_feedback_object_key(claim.attempt_token, attachment_id)
        db.add(FeedbackAttachment(
            id=attachment_id, submission_id=claim.submission_id, attempt_token=claim.attempt_token,
            owner_id=owner_id, object_key=object_key, checksum=image.sha256,
            content_type=image.content_type, width=image.width, height=image.height,
            byte_count=len(image.data), state="pending", created_at=now,
            position=position,
            deletion_due_at=now + timedelta(hours=24), cleanup_attempts=0,
        ))
        manifests.append(AttachmentManifest(attachment_id, object_key))
    db.commit()
    return manifests


def _new_feedback(db: Session, owner_id: int, payload: FeedbackCreate, ip_address: str) -> Feedback:
    row = Feedback(user_id=owner_id, type=payload.type, message=payload.message,
                   page_url=payload.page_url, status="new", ip_address=ip_address)
    db.add(row)
    db.flush()
    return row


def publish_submission(
    db: Session, owner_id: int, claim: SubmissionClaim, payload: FeedbackCreate,
    ip_address: str, generations: dict[str, str], retention_days: int,
) -> FeedbackResponse:
    row = _current_attempt(db, owner_id, claim)
    attachments = db.query(FeedbackAttachment).filter_by(
        submission_id=claim.submission_id, attempt_token=claim.attempt_token,
    ).with_for_update().all()
    if set(generations) != {attachment.id for attachment in attachments}:
        raise FeedbackSubmissionError("incomplete_upload")
    if any(attachment.state != "pending" or attachment.owner_id != owner_id for attachment in attachments):
        raise FeedbackSubmissionError("stale_attempt")
    saved = _new_feedback(db, owner_id, payload, ip_address)
    now = utcnow()
    for attachment in attachments:
        attachment.object_generation = generations[attachment.id]
        attachment.feedback_id = saved.id
        attachment.state = "available"
        attachment.expires_at = now + timedelta(days=retention_days)
        attachment.deletion_due_at = attachment.expires_at
    row.feedback_id = saved.id
    row.state = "submitted"
    row.updated_at = now
    if ensure_utc(row.lease_expires_at) <= now:
        raise FeedbackSubmissionError("stale_attempt")
    response = FeedbackResponse.model_validate(saved)
    db.commit()
    return response


def persist_legacy_feedback(db: Session, owner_id: int, payload: FeedbackCreate, ip_address: str) -> FeedbackResponse:
    """The original JSON contract shares publication without requiring a client identity."""
    _lock_owner(db, owner_id)
    saved = _new_feedback(db, owner_id, payload, ip_address)
    response = FeedbackResponse.model_validate(saved)
    db.commit()
    return response


def fail_attempt(db: Session, owner_id: int, claim: SubmissionClaim) -> None:
    """Called only after owned workers settle. A stale failure never changes the winning attempt."""
    _bound_transaction(db)
    owner = db.query(User.id).filter_by(id=owner_id).with_for_update().first()
    if owner is None:
        return  # Account deletion has already queued its manifests.
    row = db.query(FeedbackSubmission).filter_by(id=claim.submission_id, owner_id=owner_id).with_for_update().first()
    if row is None or row.state != "processing" or row.attempt_token != claim.attempt_token:
        return
    now = utcnow()
    row.state = "retryable"
    row.updated_at = now
    for attachment in db.query(FeedbackAttachment).filter_by(
        submission_id=row.id, attempt_token=claim.attempt_token, state="pending",
    ).with_for_update().all():
        attachment.state = "purge_pending"
        attachment.deletion_due_at = now
    db.commit()


def attachment_metadata(db: Session, feedback_ids: list[int]) -> dict[int, list[dict]]:
    """Batch the admin manifest read; failed attempts never appear as submitted screenshots."""
    result = {feedback_id: [] for feedback_id in feedback_ids}
    if not feedback_ids:
        return result
    now = utcnow()
    for row in db.query(FeedbackAttachment).filter(FeedbackAttachment.feedback_id.in_(feedback_ids)).order_by(
        FeedbackAttachment.created_at, FeedbackAttachment.position, FeedbackAttachment.id,
    ).all():
        if row.owner_id is None or row.state in ("purge_pending", "deleted"):
            availability = "deleted"
        elif row.expires_at is None or ensure_utc(row.expires_at) <= now:
            availability = "expired"
        else:
            availability = "available"
        result[row.feedback_id].append({
            "id": row.id, "content_type": row.content_type, "width": row.width, "height": row.height,
            "byte_count": row.byte_count, "expires_at": iso_z(ensure_utc(row.expires_at)) if row.expires_at else None,
            "availability": availability,
            "download_path": f"/api/feedback/attachments/{row.id}" if availability == "available" else None,
        })
    return result


def read_private_media(db: Session, attachment_id: str, owner_id: int) -> PrivateMedia:
    _bound_transaction(db)
    reader = db.query(User.id, User.is_admin).filter(User.id == owner_id, User.is_active.is_(True)).first()
    if reader is None:
        raise FeedbackSubmissionError("not_found")
    row = db.get(FeedbackAttachment, attachment_id)
    if row is None or row.feedback_id is None or (row.owner_id != owner_id and not reader.is_admin):
        raise FeedbackSubmissionError("not_found")
    if (row.owner_id is None or row.state != "available" or row.expires_at is None
            or ensure_utc(row.expires_at) <= utcnow() or not row.object_generation):
        raise FeedbackSubmissionError("gone")
    return PrivateMedia(row.object_key, row.object_generation, row.byte_count, row.checksum)
