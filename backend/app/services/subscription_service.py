from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import InstrumentedAttribute
from typing import Optional
from app.models import User, UserUsage, UsageReservation
from app.utils.datetimes import utcnow
# FREE_TIER_SUMMARY_LIMIT now lives in entitlements (single source of truth); re-exported here
# (redundant alias = intentional re-export) so existing
# `from app.services.subscription_service import FREE_TIER_SUMMARY_LIMIT` keeps working.
from app.services.entitlements import get_entitlements
from app.services.entitlements import FREE_TIER_SUMMARY_LIMIT as FREE_TIER_SUMMARY_LIMIT
from app.config import settings

def get_current_month() -> str:
    """Get current month in YYYY-MM format"""
    return datetime.now(timezone.utc).strftime("%Y-%m")

def get_user_usage_count(user_id: int, month: str, db: Session) -> int:
    """Get user's summary count for the current month"""
    usage = db.query(UserUsage).filter(
        UserUsage.user_id == user_id,
        UserUsage.month == month
    ).first()
    
    return usage.summary_count if usage else 0

def _increment_monthly_counter(user_id: int, month: str, db: Session, column: InstrumentedAttribute) -> None:
    """Increment one selected historical bucket; serialize only first-row creation.

    All current writers use this protocol. It neither repairs old duplicates nor protects
    concurrent admission, and old revisions must drain before first-use serialization holds.
    Lock waits are transaction-local and bounded; failures propagate without ambiguous retries.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.set_config(
            "lock_timeout", f"{settings.USAGE_COUNTER_LOCK_TIMEOUT_MS}ms", True,
        )))

    def selected_bucket():
        return db.query(UserUsage.id).filter(UserUsage.user_id == user_id, UserUsage.month == month).first()

    selected = selected_bucket()
    if selected is None:
        # A usage row cannot lock its own absence. Serialize first use on its existing parent;
        # existing buckets skip this lock so Stripe provider reads do not block ordinary meters.
        db.query(User.id).filter(User.id == user_id).with_for_update().first()
        selected = selected_bucket()
        if selected is None:
            usage = UserUsage(user_id=user_id, month=month, summary_count=0, qa_count=0, analysis_count=0)
            db.add(usage)
            db.flush()
            selected_id = usage.id
        else:
            selected_id = selected.id
    else:
        selected_id = selected.id

    # Preserve .first() history semantics; only the selected bucket and requested counter change.
    # SQL arithmetic does not reuse a stale SQLAlchemy identity-map value.
    db.query(UserUsage).filter(UserUsage.id == selected_id).update(
        {column: func.coalesce(column, 0) + 1, UserUsage.updated_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )
    db.commit()


def increment_user_usage(user_id: int, month: str, db: Session):
    """Increment the monthly summary counter at the existing completion call sites."""
    _increment_monthly_counter(user_id, month, db, UserUsage.summary_count)

def check_usage_limit(user: User, db: Session) -> tuple[bool, int, Optional[int]]:
    """Check if user can generate more summaries. Returns (can_generate, current_count, limit).

    Free tier is a visible billing cap. Pro is billing-unlimited (``monthly_summary_limit is None``)
    but still subject to an INVISIBLE fair-use ceiling (``PRO_SUMMARY_MONTHLY_CAP``) that bounds
    runaway spend from a compromised/scripted account — same philosophy as ``check_qa_limit``. On a
    Pro block the returned ``limit`` is the fair-use cap; the caller renders a generic message (not
    an upsell) so the ceiling stays invisible.
    """
    month = get_current_month()
    limit = get_entitlements(user).monthly_summary_limit
    if limit is None:
        cap = settings.PRO_SUMMARY_MONTHLY_CAP
        if not cap:  # 0/None disables the ceiling → truly unlimited
            return True, 0, None
        current_count = get_user_usage_count(user.id, month, db)
        if current_count >= cap:
            return False, current_count, cap
        return True, current_count, None

    current_count = get_user_usage_count(user.id, month, db)

    if current_count >= limit:
        return False, current_count, limit

    return True, current_count, limit


SUMMARY_RESERVATION_KIND = "summary"


def _set_transaction_lock_timeout(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.set_config(
            "lock_timeout", f"{settings.USAGE_COUNTER_LOCK_TIMEOUT_MS}ms", True,
        )))


def reserve_summary_use(user: User, db: Session) -> tuple[bool, int, Optional[int], Optional[str]]:
    """Admit one summary generation and hold its quota unit under a short lease (E07b).

    ``check_usage_limit`` is a plain read, so concurrent requests could all pass the cap and
    each complete. This is the serialized decision: one transaction takes the account's
    ``users`` row lock (bounded by ``USAGE_COUNTER_LOCK_TIMEOUT_MS``), counts completed uses
    plus unexpired reservations, and only then inserts a reservation. Returns
    ``(admitted, completed_count, limit, token)`` with the same limit semantics as
    ``check_usage_limit`` (Free cap visible; Pro fair-use cap reported only on a block; truly
    unlimited Pro returns no token). The caller converts or releases the token; a process
    death leaves a row that admission ignores once ``expires_at`` passes and sweeps on the
    account's next admission. No historical duplicate repair; Redis is not involved.
    """
    limit = get_entitlements(user).monthly_summary_limit
    unlimited = limit is None
    if unlimited:
        cap = settings.PRO_SUMMARY_MONTHLY_CAP
        if not cap:
            return True, 0, None, None
        limit = cap
    month = get_current_month()
    now = utcnow()
    _set_transaction_lock_timeout(db)
    db.query(User.id).filter(User.id == user.id).with_for_update().first()
    db.query(UsageReservation).filter(
        UsageReservation.user_id == user.id, UsageReservation.expires_at <= now,
    ).delete(synchronize_session=False)
    # READ COMMITTED gives each statement its own snapshot and a completion (delete lease +
    # increment) does not take the users lock once the bucket exists, so read the leases FIRST:
    # a conversion landing between the two reads then counts once as a lease and once as a
    # completed use (a conservative block), never zero times (an over-admission).
    active = db.query(func.count(UsageReservation.id)).filter(
        UsageReservation.user_id == user.id,
        UsageReservation.month == month,
        UsageReservation.kind == SUMMARY_RESERVATION_KIND,
        UsageReservation.expires_at > now,
    ).scalar() or 0
    completed = get_user_usage_count(user.id, month, db)
    if completed + active >= limit:
        db.rollback()
        return False, completed, limit, None
    token = uuid4().hex
    db.add(UsageReservation(
        user_id=user.id, month=month, kind=SUMMARY_RESERVATION_KIND, token=token,
        expires_at=now + timedelta(seconds=settings.USAGE_RESERVATION_TTL_SECONDS), created_at=now,
    ))
    db.commit()
    return True, completed, (None if unlimited else limit), token


def release_reservation(token: Optional[str], db: Session, *, commit: bool = True) -> None:
    """Drop a reservation (idempotent). ``commit=False`` lets a completion delete it in the same
    transaction as the counter increment, so a unit is never both reserved and counted."""
    if not token:
        return
    db.query(UsageReservation).filter(UsageReservation.token == token).delete(synchronize_session=False)
    if commit:
        db.commit()


def get_user_qa_count(user_id: int, month: str, db: Session) -> int:
    """Get user's Copilot Q&A question count for the given month."""
    usage = db.query(UserUsage).filter(
        UserUsage.user_id == user_id,
        UserUsage.month == month
    ).first()

    return (usage.qa_count or 0) if usage else 0


def increment_user_qa(user_id: int, month: str, db: Session) -> None:
    """Increment the monthly Copilot counter at the existing completion call site."""
    _increment_monthly_counter(user_id, month, db, UserUsage.qa_count)


def increment_user_copilot_free_taste(user_id: int, db: Session) -> None:
    """Increment a Free user's *lifetime* Copilot free-taste counter (roadmap 2.2).

    Lifetime (lives on ``users``), so it's keyed only by user — unlike the monthly ``qa_count`` on
    ``user_usage``. Metered after a successful answer; Pro users never reach this path.

    Atomic DB-level increment (not read-modify-write) so concurrent questions — a double-click or
    parallel requests — cannot lose a completed-answer increment. Admission remains a separate
    check, so this alone does not prevent concurrent requests exceeding the taste allowance.
    """
    db.query(User).filter(User.id == user_id).update(
        {User.copilot_free_taste_used: User.copilot_free_taste_used + 1},
        synchronize_session=False,
    )
    db.commit()


def check_qa_limit(user: User, db: Session) -> tuple[bool, int, int]:
    """Check if a Pro user is under the Copilot monthly question cap.

    Returns ``(allowed, current_count, cap)``. The cap is a fair-use soft limit
    (``COPILOT_MONTHLY_QUESTION_CAP``) rather than a billing boundary — entitlement gating already
    restricts the feature to Pro, so this only protects against runaway/abusive volume.
    """
    cap = settings.COPILOT_MONTHLY_QUESTION_CAP
    month = get_current_month()
    current_count = get_user_qa_count(user.id, month, db)
    return current_count < cap, current_count, cap


def get_user_analysis_count(user_id: int, month: str, db: Session) -> int:
    """Get user's Multi-Period Analysis generation count for the given month."""
    usage = db.query(UserUsage).filter(
        UserUsage.user_id == user_id,
        UserUsage.month == month
    ).first()

    return (usage.analysis_count or 0) if usage else 0


def increment_user_analysis(user_id: int, month: str, db: Session) -> None:
    """Increment the monthly analysis counter at the existing completion call site."""
    _increment_monthly_counter(user_id, month, db, UserUsage.analysis_count)


def check_analysis_limit(user: User, db: Session) -> tuple[bool, int, int]:
    """Check if a Pro user is under the Multi-Period Analysis monthly cap.

    Same shape and philosophy as ``check_qa_limit``: ``(allowed, current_count, cap)``, a fair-use
    soft limit (``ANALYSIS_MONTHLY_CAP``) behind the ``can_analyze_trends`` entitlement — cached
    re-serves are never metered, so this only bounds fresh AI generations.
    """
    cap = settings.ANALYSIS_MONTHLY_CAP
    month = get_current_month()
    current_count = get_user_analysis_count(user.id, month, db)
    return current_count < cap, current_count, cap
