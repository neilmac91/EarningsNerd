"""Stage current, explicit signup acceptance in the caller's account-creation transaction."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AccountAgreement, User
from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION
from app.utils.datetimes import utcnow


class AgreementRequired(ValueError):
    """New accounts require the account holder's current adulthood and Terms confirmations."""


@dataclass(frozen=True)
class AcceptedAccountAgreement:
    terms_version: str
    eligibility_version: str
    accepted_at: datetime


def accept_current_agreement() -> AcceptedAccountAgreement:
    """Called only after AccountAgreementInput validated the explicit public input."""
    return AcceptedAccountAgreement(TERMS_VERSION, ELIGIBILITY_VERSION, utcnow())


def require_current_agreement(agreement: AcceptedAccountAgreement | None) -> AcceptedAccountAgreement:
    # OAuth state is short lived, but may have been accepted under a superseded version before
    # a deployment. A new account must not turn that stored older choice into current evidence.
    if agreement is None or (agreement.terms_version, agreement.eligibility_version) != (
        TERMS_VERSION, ELIGIBILITY_VERSION,
    ):
        raise AgreementRequired("Review and accept the account requirements before creating an account.")
    return agreement


def stage_account_agreement(
    db: Session, user: User, agreement: AcceptedAccountAgreement, *, source: str,
) -> None:
    """No commit: a lost invite/account transaction rolls this row back with the new account."""
    db.add(AccountAgreement(
        user_id=user.id,
        adult_eligible=True,
        terms_accepted=True,
        terms_version=agreement.terms_version,
        eligibility_version=agreement.eligibility_version,
        accepted_at=agreement.accepted_at,
        source=source,
    ))
