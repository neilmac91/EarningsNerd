"""An agreement identifies the actual published policy, including its eligibility requirement.

Terms content/date drift is already gated in frontend legalTruth. This cross-layer check prevents
changing that date without invalidating a pending OAuth state's old Terms acceptance. Eligibility
wording is pinned independently so changing the requirement demands an explicit policy review.
"""
import re
from datetime import datetime
from pathlib import Path

from app.services.legal_readiness_service import ELIGIBILITY_VERSION, TERMS_VERSION

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"


def bundled_version(name: str) -> str:
    policy = (FRONTEND / "features/legal/policy.ts").read_text()
    match = re.search(rf"export const {name} = '([^']+)'", policy)
    assert match is not None, f"The browser must bind acceptance to its bundled {name}"
    return match.group(1)


def test_account_terms_version_matches_published_terms_date():
    dates = (FRONTEND / "lib/legalDates.ts").read_text()
    match = re.search(r"\bterms:\s*'([^']+)'", dates)
    assert match is not None, "The Terms publication date must remain explicit"
    published = datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat()
    assert TERMS_VERSION == published, "Bump backend Terms acceptance version with published Terms"
    assert bundled_version("ACCOUNT_TERMS_VERSION") == TERMS_VERSION


def test_eligibility_version_identifies_adult_and_local_adulthood_requirement():
    assert ELIGIBILITY_VERSION == "2026-10-24"
    assert bundled_version("ACCOUNT_ELIGIBILITY_VERSION") == ELIGIBILITY_VERSION
    form = (FRONTEND / "features/auth/components/RegisterForm.tsx").read_text()
    terms = (FRONTEND / "app/terms/page.tsx").read_text()
    assert "I am at least 18 and legally an adult where I live." in form
    assert "you must be at least 18 and legally an adult where you live." in terms
