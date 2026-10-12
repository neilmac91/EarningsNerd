"""Admin triage of beta feedback: list recent rows with the submitter's email, set a row's status.

Called by ``routers/admin.py`` (GET /api/admin/feedback, PATCH /api/admin/feedback/{id}). The
router keeps the admin gate, the 404, the audit row and the response shape.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import User
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackStatus, FeedbackType


def list_feedback(
    db: Session,
    *,
    feedback_status: Optional[FeedbackStatus],
    feedback_type: Optional[FeedbackType],
) -> list[tuple[Feedback, Optional[str]]]:
    """Recent feedback (newest first, capped at 200) as (row, submitter email) pairs.

    The LEFT OUTER JOIN keeps rows whose ``user_id`` is null or whose user was deleted (FK is
    ON DELETE SET NULL); either filter narrows the result when provided.
    """
    query = (
        db.query(Feedback, User.email)
        .outerjoin(User, Feedback.user_id == User.id)
    )
    if feedback_status is not None:
        query = query.filter(Feedback.status == feedback_status)
    if feedback_type is not None:
        query = query.filter(Feedback.type == feedback_type)
    return query.order_by(Feedback.created_at.desc()).limit(200).all()


def set_feedback_status(db: Session, feedback_id: int, new_status: FeedbackStatus) -> Optional[Feedback]:
    """Set a feedback row's triage status and commit; None when no row has that id."""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        return None
    feedback.status = new_status
    db.commit()
    db.refresh(feedback)
    return feedback


def submitter_email(db: Session, feedback: Feedback) -> Optional[str]:
    """The submitter's current email, or None when the row has no user or the user is gone."""
    # Re-resolve the submitter's email (null-safe when user_id is null/deleted).
    user_email = None
    if feedback.user_id is not None:
        submitter = db.query(User).filter(User.id == feedback.user_id).first()
        user_email = submitter.email if submitter else None
    return user_email
