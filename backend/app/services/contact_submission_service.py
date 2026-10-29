"""Persist contact submissions; the router owns request policy and notifications."""
from __future__ import annotations

from logging import Logger

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ContactSubmission, User
from app.services.entitlements import Plan, get_plan
from app.services.legal_readiness_service import require_collection_available


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
    require_collection_available()
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


def sender_plan(db: Session, email: str) -> Plan | None:
    """The plan of the account that uses ``email``, matched without regard to case, or None when no
    account does. The team's notice names it so a Pro member's message can be answered first, the
    priority support D-050 keeps by hand. The address is the one the form was given, unverified."""
    user = db.query(User).filter(func.lower(User.email) == email.strip().lower()).first()
    return None if user is None else get_plan(user)
