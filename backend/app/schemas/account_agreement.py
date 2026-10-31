"""Explicit account eligibility and Terms acceptance at the public input boundary."""
from pydantic import BaseModel, StrictBool, StrictStr, field_validator

from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION


class AccountAgreementInput(BaseModel):
    adult_eligible: StrictBool
    terms_accepted: StrictBool
    terms_version: StrictStr
    eligibility_version: StrictStr

    @field_validator("adult_eligible", "terms_accepted")
    @classmethod
    def require_affirmative(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Confirm adulthood and accept the Terms to create an account.")
        return value

    @field_validator("terms_version")
    @classmethod
    def current_terms(cls, value: str) -> str:
        if value != TERMS_VERSION:
            raise ValueError("Review the current Terms before creating an account.")
        return value

    @field_validator("eligibility_version")
    @classmethod
    def current_eligibility(cls, value: str) -> str:
        if value != ELIGIBILITY_VERSION:
            raise ValueError("Review the current account eligibility requirements.")
        return value
