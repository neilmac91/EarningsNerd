"""Public availability and the explicitly published operator notice; never draft identity fields."""
from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.services import legal_readiness_service

router = APIRouter()


class OperatorNotice(BaseModel):
    legal_name: str
    postal_address: str
    country: str
    contact_email: str


class LegalReadiness(BaseModel):
    collection_available: bool
    checkout_available: bool
    marketing_available: bool
    terms_version: str
    eligibility_version: str
    operator: OperatorNotice | None


@router.get("/readiness", response_model=LegalReadiness)
def readiness(response: Response) -> LegalReadiness:
    # Browser callers recheck on each mount. Do not let a CDN preserve an earlier open state.
    response.headers["Cache-Control"] = "no-store"
    return LegalReadiness(
        collection_available=legal_readiness_service.is_collection_available(),
        checkout_available=legal_readiness_service.is_checkout_available(),
        marketing_available=legal_readiness_service.is_marketing_available(),
        terms_version=legal_readiness_service.TERMS_VERSION,
        eligibility_version=legal_readiness_service.ELIGIBILITY_VERSION,
        operator=legal_readiness_service.public_operator(),
    )
