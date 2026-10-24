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
    fresh read of it), so it is saved even if ``current_user`` is not this session's. With no row (an
    account deleted since the lookup) a rename fails, a 500, as it did before. The profile is read
    before the commit, which expires the row: read after it, the row would be loaded again on a new
    checkout."""
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
    it, and PostgreSQL aborts one of the two.

    The delete goes through the row this session holds, read after the lock (``db.get``): the route
    releases its session before its third-party calls, so ``current_user`` is no longer this session's.
    With no row (the account deleted since the lookup, as by a second deletion at once) it raises, and
    the route answers 500, as it did before (the deletion-failure policy is F18's)."""
    db.query(User.id).filter(User.id == current_user.id).with_for_update().first()
    user = db.get(User, current_user.id)
    if user is None:
        raise LookupError(f"Account {current_user.id} was deleted after its lookup")
    db.delete(user)
    db.commit()


def rollback_account_deletion(db: Session) -> None:
    """Discard whatever a failed deletion left pending in the request's session."""
    db.rollback()
