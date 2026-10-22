from __future__ import annotations

import secrets
import string
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import WaitlistSignup


REFERRAL_CODE_LENGTH = 8
REFERRAL_BONUS = 5
VERIFY_TOKEN_DAYS = 7

# A join reads, then writes: the referrer's priority it bumps, and the highest place held, which its
# own place follows. On the event loop the join ran them one at a time within the process; in the
# thread pool two joins on one referral link could both read the same priority and lose a credit, and
# two joins could take one place. ``create_signup`` holds this lock for its whole unit, taken before its first
# query: a waiter holds no connection, so a holder's checkout never waits for one a waiter holds.
# This lock reaches one process, and the API runs up to two instances, so the credit is one atomic
# UPDATE and the unit also takes the waitlist's place lock (``_lock_waitlist_places``), which every
# instance shares (E128).
_join_lock = threading.Lock()

# The key of the PostgreSQL advisory lock that gives each join a place of its own: "WAITLIST" in ASCII.
WAITLIST_PLACE_LOCK_KEY = 0x574149544C495354


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
    """The share link: /waitlist reads ``?ref=`` (WaitlistForm) with WAITLIST_MODE on or off; the homepage does not."""
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/waitlist?ref={referral_code}"


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


@dataclass(frozen=True)
class SignupView:
    """The signup fields the join route reads after its unit has released the session."""

    id: int
    email: str
    name: Optional[str]
    position: int
    priority_score: int
    referral_code: str

    @classmethod
    def of(cls, signup: WaitlistSignup) -> "SignupView":
        return cls(signup.id, signup.email, signup.name, signup.position, signup.priority_score,
                   signup.referral_code)


def find_signup_by_email(db: Session, email: str) -> Optional[WaitlistSignup]:
    return db.query(WaitlistSignup).filter(WaitlistSignup.email == email).first()


def count_signups(db: Session) -> int:
    return db.query(func.count(WaitlistSignup.id)).scalar() or 0


def _next_place(db: Session) -> int:
    """One past the highest place held, so a place stays its join's alone after a signup is deleted, which
    the count of signups would hand out again."""
    return (db.query(func.max(WaitlistSignup.position)).scalar() or 0) + 1


def _lock_waitlist_places(db: Session) -> None:
    """Take the waitlist's place lock for the rest of the caller's transaction (E128).

    A join's place is one past the highest place held (``_next_place``), so two joins that read it before
    either commits take one place. ``_join_lock`` serializes joins within one instance; this lock serializes
    them across the API's instances. A second join waits here for the first's commit, and its read of the
    highest place then sees that commit (READ COMMITTED). The list has no row every join could lock, so it is a
    transaction-level advisory lock: PostgreSQL releases it at the commit or rollback, so it never
    outlives the unit on a pooled connection. Unbounded, as its holders are short transactions. SQLite
    has no advisory locks, and its joins run in one process, under ``_join_lock``."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(WAITLIST_PLACE_LOCK_KEY)))


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
    ``WaitlistAlreadyJoined`` like the up-front check does. Joins in one process run one at a time
    (``_join_lock``), and across instances under the waitlist's place lock (``_lock_waitlist_places``).
    """
    with _join_lock:
        return _create_signup(
            db, email=email, name=name, referral_code=referral_code, source=source,
        )


def _create_signup(
    db: Session,
    *,
    email: str,
    name: Optional[str],
    referral_code: Optional[str],
    source: Optional[str],
) -> WaitlistJoin:
    _lock_waitlist_places(db)
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
        # The flush adds one to the stored score (SET priority_score = priority_score + 1), not the score
        # this unit read plus one, so a credit another join committed since that read is kept. The
        # commit's refresh below reads the score stored.
        referrer.priority_score = WaitlistSignup.priority_score + 1

    total_signups = count_signups(db)
    base_position = _next_place(db)
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


def mark_welcome_email_sent(db: Session, signup_id: int) -> None:
    """Flag the signup's welcome mail as sent. The join route calls it in its own unit after the
    send, and that unit's release rolls back a flag commit that fails. A signup gone by then fails
    the step as a failed flag commit does: the route logs it and answers ``email_sent`` false."""
    signup = db.get(WaitlistSignup, signup_id)
    if signup is None:
        raise LookupError(f"Waitlist signup {signup_id} is gone")
    signup.welcome_email_sent = True
    db.commit()


def mark_email_verified(db: Session, email: str) -> bool:
    """False when no signup carries ``email`` (router: 404); nothing is written then."""
    signup = find_signup_by_email(db, email)
    if not signup:
        return False
    signup.email_verified = True
    db.commit()
    return True
