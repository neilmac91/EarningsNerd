"""Account writes behind ``/api/users``: profile edits and the database step of account deletion.

The router keeps the third-party erasure (Stripe, PostHog, Sentry), the audit row, the cookies and
every log line; these functions are only the session work, in the transaction the router drives.
"""
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import User


def apply_profile_update(db: Session, current_user: User, data: Dict[str, Any]) -> None:
    """Apply the validated profile fields and commit (``data`` holds only the fields the client sent)."""
    if "full_name" in data:
        current_user.full_name = data["full_name"]
    db.commit()
    db.refresh(current_user)


def delete_user(db: Session, current_user: User) -> None:
    """Delete the account row and commit; the ORM cascade removes the rows it owns.

    The account's row lock comes first, as every rotation and revocation of its refresh tokens takes
    it before their rows (``refresh_token_service._lock_user_tokens``). The cascade deletes those rows
    before the account's, so in the other order a logout or refresh racing the deletion deadlocks with
    it, and PostgreSQL aborts one of the two."""
    db.query(User.id).filter(User.id == current_user.id).with_for_update().first()
    db.delete(current_user)
    db.commit()


def rollback_account_deletion(db: Session) -> None:
    """Discard whatever a failed deletion left pending in the request's session."""
    db.rollback()
