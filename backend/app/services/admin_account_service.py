"""Provision new Free accounts for the authenticated admin endpoint.

Public signup retains its invite gate. This service never changes an existing account;
password setup reuses the single-use, inbox-verifying password reset flow.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, replace

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.services import audit_service, auth_account_service, email_service
from app.services.password_utils import get_password_hash

logger = logging.getLogger(__name__)


class FreeAccountAlreadyExistsError(Exception):
    """The email already belongs to an account, including a concurrent creation winner."""


@dataclass(frozen=True)
class FreeAccount:
    id: int
    email: str
    full_name: str | None
    is_pro: bool
    is_beta: bool
    is_admin: bool
    email_verified: bool
    emailed: bool = False


def _provision_account(
    db: Session, *, email: str, full_name: str | None, actor: User,
) -> tuple[FreeAccount, str, int, str]:
    """Run blocking reads, hashing and commits together off the request event loop."""
    # Commits expire every ORM instance in this session, including the authenticated admin.
    actor_id, actor_email = actor.id, actor.email
    if auth_account_service.find_user_by_email(db, email) is not None:
        raise FreeAccountAlreadyExistsError()

    # Discard the random initial password; only the inbox owner can choose a usable password.
    user = auth_account_service.create_password_account(
        db,
        email=email,
        hashed_password=get_password_hash(secrets.token_urlsafe(32)),
        full_name=full_name,
        invite=None,
    )
    if user is None:
        # Never issue a reset token for the account that won a concurrent email insert.
        raise FreeAccountAlreadyExistsError()

    account = FreeAccount(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_pro=user.is_pro,
        is_beta=user.is_beta,
        is_admin=user.is_admin,
        email_verified=user.email_verified,
    )
    raw_token = auth_account_service.issue_password_reset_token(db, user)
    return account, raw_token, actor_id, actor_email


async def create_free_account(
    db: Session, *, email: str, full_name: str | None, actor: User,
) -> FreeAccount:
    """Create only a new account, send its setup link, and record the admin action.

    The router authorizes the caller before invoking this service. Only plain snapshots
    cross back onto the event loop, so later token/audit commits cannot cause lazy SQL there.
    A mail failure leaves the new account recoverable through the normal forgot-password flow.
    """
    account, raw_token, actor_id, actor_email = await run_in_threadpool(
        _provision_account, db, email=email, full_name=full_name, actor=actor,
    )
    emailed = False
    try:
        await email_service.send_password_reset_email(
            to_email=account.email,
            name=account.full_name,
            reset_link=f"{settings.FRONTEND_URL}/reset-password?token={raw_token}",
        )
        emailed = True
    except Exception:
        # Provider exceptions can contain the token-bearing email body. Do not log their text.
        logger.warning("Free-account setup email not sent for user %s", account.id)

    await run_in_threadpool(
        audit_service.create_audit_log,
        db,
        action="free_account_created",
        user_id=actor_id,
        user_email=actor_email,
        entity_type="user",
        entity_id=str(account.id),
        details={"emailed": emailed},
    )
    return replace(account, emailed=emailed)
