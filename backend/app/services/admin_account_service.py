"""Refuse direct admin provisioning: only the account holder can accept account requirements.

The authenticated endpoint remains as an explicit refusal so older admin clients cannot silently
bypass signup. Administrators can issue existing invitation links instead. No account, reset token,
mail or invented agreement is created here.
"""
from app.models import User


class AccountInvitationRequired(Exception):
    """The recipient must complete signup through an invitation."""


async def create_free_account(*, email: str, full_name: str | None, actor: User) -> None:
    raise AccountInvitationRequired(
        "Use an invitation so the recipient can accept the account requirements."
    )
