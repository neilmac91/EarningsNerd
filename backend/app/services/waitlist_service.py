from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
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


class WaitlistAlreadyJoined(Exception):
    """The email is already on the waitlist; carries the existing row for the response."""

    def __init__(self, signup: WaitlistSignup) -> None:
        self.signup = signup
        super().__init__("already registered")


class WaitlistReferralNotFound(Exception):
    """The submitted referral code matches no signup (router: 400 ``invalid_referral``)."""


class WaitlistSignupFailed(Exception):
    """The insert hit an IntegrityError and no row exists for the email (router: 500)."""


@dataclass(frozen=True)
class WaitlistJoin:
    signup: WaitlistSignup
    referrer: Optional[WaitlistSignup]
    total_signups: int


def find_signup_by_email(db: Session, email: str) -> Optional[WaitlistSignup]:
    return db.query(WaitlistSignup).filter(WaitlistSignup.email == email).first()


def count_signups(db: Session) -> int:
    return db.query(func.count(WaitlistSignup.id)).scalar() or 0


def count_referrals(db: Session, referral_code: str) -> int:
    return (
        db.query(func.count(WaitlistSignup.id))
        .filter(WaitlistSignup.referred_by == referral_code)
        .scalar()
        or 0
    )


def create_signup(
    db: Session,
    *,
    email: str,
    name: Optional[str],
    referral_code: Optional[str],
    source: Optional[str],
) -> WaitlistJoin:
    """Insert a signup, bumping the referrer's priority in the same commit.

    Moved from ``POST /api/waitlist/join``. An IntegrityError on the commit rolls back both the
    insert and the bump, then re-reads the email: a concurrent join of the same address raises
    ``WaitlistAlreadyJoined`` like the up-front check does.
    """
    existing = find_signup_by_email(db, email)
    if existing:
        raise WaitlistAlreadyJoined(existing)

    referrer: Optional[WaitlistSignup] = None
    if referral_code:
        referrer = (
            db.query(WaitlistSignup)
            .filter(WaitlistSignup.referral_code == referral_code)
            .first()
        )
        if not referrer:
            raise WaitlistReferralNotFound()
        referrer.priority_score += 1

    total_signups = count_signups(db)
    base_position = total_signups + 1
    new_referral_code = generate_unique_referral_code(db)

    signup = WaitlistSignup(
        email=email,
        name=name,
        referral_code=new_referral_code,
        referred_by=referral_code,
        source=source,
        position=base_position,
        priority_score=0,
    )
    db.add(signup)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = find_signup_by_email(db, email)
        if existing:
            raise WaitlistAlreadyJoined(existing)
        raise WaitlistSignupFailed()

    db.refresh(signup)
    if referrer:
        db.refresh(referrer)
    return WaitlistJoin(signup=signup, referrer=referrer, total_signups=total_signups)


def mark_welcome_email_sent(db: Session, signup: WaitlistSignup) -> None:
    signup.welcome_email_sent = True
    db.commit()


def rollback_welcome_email_sent(db: Session) -> None:
    """Discard a pending ``welcome_email_sent`` flag; the signup itself is already committed."""
    db.rollback()


def mark_email_verified(db: Session, email: str) -> bool:
    """False when no signup carries ``email`` (router: 404); nothing is written then."""
    signup = find_signup_by_email(db, email)
    if not signup:
        return False
    signup.email_verified = True
    db.commit()
    return True
