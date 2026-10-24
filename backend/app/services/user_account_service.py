"""Account writes behind ``/api/users``: profile edits and the database step of account deletion.

The router keeps the third-party erasure (Stripe, PostHog, Sentry), the audit row, the cookies and
every log line; these functions are only the session work, in the transaction the router drives.
"""
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import User


def apply_profile_update(db: Session, current_user: User, data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the validated profile fields and commit (``data`` holds only the fields the client sent);
    return the profile the response shows.

    The write goes through the row this session holds (``db.get``: the auth lookup's own user, or a
    fresh read of it), so it is saved even if ``current_user`` is not this session's, as
    ``user_notification_feed_service.mark_seen`` does. The profile is read before the commit, which
    expires the row: read after it, the row would be loaded again on a new checkout."""
    user = db.get(User, current_user.id)
    if "full_name" in data:
        user.full_name = data["full_name"]
    profile = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_pro": user.is_pro,
    }
    db.commit()
    return profile


def delete_user(db: Session, current_user: User) -> None:
    """Delete the account row and commit; the ORM cascade removes the rows it owns.

    The account's row lock comes first, as every rotation and revocation of its refresh tokens takes
    it before their rows (``refresh_token_service.lock_user_tokens``). The cascade deletes those rows
    before the account's, so in the other order a logout or refresh racing the deletion deadlocks with
    it, and PostgreSQL aborts one of the two."""
    db.query(User.id).filter(User.id == current_user.id).with_for_update().first()
    db.delete(current_user)
    db.commit()


def rollback_account_deletion(db: Session) -> None:
    """Discard whatever a failed deletion left pending in the request's session."""
    db.rollback()
