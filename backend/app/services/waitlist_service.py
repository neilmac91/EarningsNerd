from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import WaitlistSignup


REFERRAL_CODE_LENGTH = 8
REFERRAL_BONUS = 5
VERIFY_TOKEN_DAYS = 7


def generate_referral_code(length: int = REFERRAL_CODE_LENGTH) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_unique_referral_code(db: Session, max_attempts: int = 25) -> str:
    for _ in range(max_attempts):
        code = generate_referral_code()
        exists = (
            db.query(WaitlistSignup.id)
            .filter(WaitlistSignup.referral_code == code)
            .first()
        )
        if not exists:
            return code
    raise RuntimeError("Failed to generate a unique referral code.")


def calculate_waitlist_position(base_position: int, priority_score: int) -> int:
    position = base_position - (priority_score * REFERRAL_BONUS)
    return max(1, position)


def create_verification_token(email: str, referral_code: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "ref": referral_code,
        "type": "waitlist_verify",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=VERIFY_TOKEN_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def build_referral_link(referral_code: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}?ref={referral_code}"


def build_verification_link(token: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/api/waitlist/verify/{token}"
