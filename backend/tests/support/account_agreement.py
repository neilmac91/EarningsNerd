"""Synthetic affirmative signup input for pre-existing auth/security scenarios.

Production defaults stay closed. Tests explicitly request ``collection_ready`` and these fields;
new negative tests send their own bodies so missing/false/stale evidence is never filled in for them.
"""
from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION

ACCOUNT_AGREEMENT = {
    "adult_eligible": True,
    "terms_accepted": True,
    "terms_version": TERMS_VERSION,
    "eligibility_version": ELIGIBILITY_VERSION,
}
