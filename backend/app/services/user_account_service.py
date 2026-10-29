"""Account writes behind ``/api/users``: profile edits and the database step of account deletion.

The router keeps the third-party erasure (Stripe, PostHog, Sentry), the cookies and every log line;
these functions are only the session work, in the transaction the router drives. The deletion's
audit row is part of that work: it commits with the deletion or not at all (F19).
"""
from typing import Any, Dict, Mapping

from sqlalchemy.orm import Session

from app.models import User
from app.services.audit_service import stage_user_deletion
from app.services.feedback_media_cleanup_service import enqueue_owner_media_deletion


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


def delete_account(db: Session, user_id: int, *, third_party_results: Mapping[str, str]) -> None:
    """The account's own deletion (``DELETE /api/users/me``): delete the account row with its
    ``user_deleted`` audit row and commit the two together; the ORM cascade removes the rows the
    account owns.

    The audit is staged under the lock, once the account is found, and records ``third_party_results``
    (the route's Stripe, PostHog and Sentry outcomes) and the email the locked row holds. The commit
    writes it with the deletion: a failed audit insert, deletion or commit raises before anything is
    committed, and the route's rollback discards both (F19), so no such deletion goes unaudited and no
    failed one is audited as a success. The provider actions it records have already
    run and are not undone. With the account already gone it raises ``LookupError`` (``_lock_account``)
    with no audit row staged."""
    email = _lock_account(db, user_id)
    stage_user_deletion(db, user_id, email, dict(third_party_results))
    _delete_locked_account(db, user_id)


def delete_user(db: Session, user_id: int) -> None:
    """Delete an account no person asked to delete, with no audit row, and commit: the feedback-media
    verifier's fixture accounts (``ops/feedback_media/verify_runtime.py``) and the feedback-media tests'.
    ``tests/unit/test_unaudited_deletion_callers_allowlist.py`` holds its callers, and those of the
    ``_delete_locked_account`` step it shares with ``delete_account``, to that list outside the tests. The lock and
    the cascade are ``delete_account``'s."""
    _lock_account(db, user_id)
    _delete_locked_account(db, user_id)


def _lock_account(db: Session, user_id: int) -> str:
    """Take the account's row lock and return its email.

    The account's row lock comes first, as every rotation and revocation of its refresh tokens takes
    it before their rows (``refresh_token_service.lock_user_tokens``). The cascade deletes those rows
    before the account's, so in the other order a logout or refresh racing the deletion deadlocks with
    it, and PostgreSQL aborts one of the two.

    The route hands over the account's id, as it releases its session before its third-party calls.
    The lock's own query decides whether the row is still there, since ``db.get`` would hand back a row
    this session loaded before another transaction deleted it: with none (the account deleted since the
    lookup, as by a second deletion at once) it raises ``LookupError`` naming the account, and the
    route answers its own 500 (the deletion-failure policy is F18's)."""
    account = db.query(User.id, User.email).filter(User.id == user_id).with_for_update().first()
    if account is None:
        raise LookupError(f"Account {user_id} was deleted after its lookup")
    return account.email


def _delete_locked_account(db: Session, user_id: int) -> None:
    enqueue_owner_media_deletion(db, user_id)
    db.delete(db.get(User, user_id))
    db.commit()


def rollback_account_deletion(db: Session) -> None:
    """Discard whatever a failed deletion left pending in the request's session."""
    db.rollback()
