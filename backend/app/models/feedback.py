from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func

from app.database import Base


class Feedback(Base):
    """In-dashboard beta feedback (bug report / feature request / general).

    Authenticated-only and kept separate from ``ContactSubmission`` so beta signal stays isolated
    from public contact-form traffic. ``user_id`` is captured for follow-up; ``ip_address`` is stored
    hashed (privacy), mirroring the contact pipeline.
    """

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # bug | feature | general — validated at the schema layer.
    type = Column(String(20), default="general", nullable=False, index=True)
    message = Column(Text, nullable=False)
    page_url = Column(String(500), nullable=True)
    status = Column(String(20), default="new", nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class FeedbackSubmission(Base):
    """An owner-scoped receipt and fenced processing lease, independent of object I/O."""

    __tablename__ = "feedback_submissions"
    __table_args__ = (
        UniqueConstraint("owner_id", "submission_key", name="uq_feedback_submission_owner_key"),
        Index("ix_feedback_submissions_owner_created", "owner_id", "created_at"),
    )

    id = Column(String(36), primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submission_key = Column(String(36), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    state = Column(String(20), nullable=False)
    attempt_token = Column(String(36), nullable=False)
    attempt_count = Column(Integer, nullable=False, default=1)
    lease_expires_at = Column(DateTime(timezone=True), nullable=False)
    feedback_id = Column(Integer, ForeignKey("feedback.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class FeedbackAttachment(Base):
    """Durable object manifest. Never cascade away an unconfirmed storage deletion."""

    __tablename__ = "feedback_attachments"
    __table_args__ = (
        Index("ix_feedback_attachments_cleanup", "state", "deletion_due_at"),
        Index("ix_feedback_attachments_feedback", "feedback_id"),
        Index("ix_feedback_attachments_owner", "owner_id"),
        Index("ix_feedback_attachments_submission", "submission_id", "attempt_token"),
    )

    id = Column(String(36), primary_key=True)
    submission_id = Column(String(36), ForeignKey("feedback_submissions.id", ondelete="RESTRICT"), nullable=False)
    attempt_token = Column(String(36), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    feedback_id = Column(Integer, ForeignKey("feedback.id", ondelete="SET NULL"), nullable=True)
    object_key = Column(String(200), nullable=False, unique=True)
    object_generation = Column(String(40), nullable=True)
    checksum = Column(String(64), nullable=False)
    content_type = Column(String(30), nullable=False, default="image/png")
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    byte_count = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False, default=0)
    state = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    deletion_due_at = Column(DateTime(timezone=True), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    cleanup_attempts = Column(Integer, nullable=False, default=0)
    last_cleanup_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_cleanup_error = Column(String(80), nullable=True)
