"""Persist contact submissions; the router owns request policy and notifications."""

from logging import Logger

from sqlalchemy.orm import Session

from app.models import ContactSubmission


class ContactPersistenceError(Exception):
    """The protected persistence block failed; its original exception is the cause."""


def persist_contact_submission(
    db: Session,
    *,
    name: str,
    email: str,
    subject: str | None,
    message: str,
    ip_address: str,
    logger: Logger,
) -> ContactSubmission:
    # Construction stays outside the protected transaction, as in the HTTP adapter.
    db_submission = ContactSubmission(
        name=name,
        email=email,
        subject=subject,
        message=message,
        status="new",
        ip_address=ip_address,
    )

    try:
        db.add(db_submission)
        db.commit()
        db.refresh(db_submission)
        logger.info(f"Contact submission created: ID={db_submission.id}")
    except Exception as e:
        # A rollback failure still propagates directly; only the original failure is mapped.
        db.rollback()
        raise ContactPersistenceError from e

    return db_submission
