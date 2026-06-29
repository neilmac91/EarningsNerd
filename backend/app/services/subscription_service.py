from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional
from app.models import User, UserUsage
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

def increment_user_usage(user_id: int, month: str, db: Session):
    """Increment user's summary count for the current month"""
    usage = db.query(UserUsage).filter(
        UserUsage.user_id == user_id,
        UserUsage.month == month
    ).first()
    
    if usage:
        usage.summary_count += 1
        usage.updated_at = datetime.now(timezone.utc)
    else:
        usage = UserUsage(
            user_id=user_id,
            month=month,
            summary_count=1
        )
        db.add(usage)
    
    db.commit()

def check_usage_limit(user: User, db: Session) -> tuple[bool, int, Optional[int]]:
    """Check if user can generate more summaries. Returns (can_generate, current_count, limit)"""
    limit = get_entitlements(user).monthly_summary_limit
    if limit is None:
        return True, 0, None  # unlimited (e.g. pro)

    month = get_current_month()
    current_count = get_user_usage_count(user.id, month, db)

    if current_count >= limit:
        return False, current_count, limit

    return True, current_count, limit


def get_user_qa_count(user_id: int, month: str, db: Session) -> int:
    """Get user's Copilot Q&A question count for the given month."""
    usage = db.query(UserUsage).filter(
        UserUsage.user_id == user_id,
        UserUsage.month == month
    ).first()

    return (usage.qa_count or 0) if usage else 0


def increment_user_qa(user_id: int, month: str, db: Session) -> None:
    """Increment user's Copilot Q&A question count for the given month."""
    usage = db.query(UserUsage).filter(
        UserUsage.user_id == user_id,
        UserUsage.month == month
    ).first()

    if usage:
        usage.qa_count = (usage.qa_count or 0) + 1
        usage.updated_at = datetime.now(timezone.utc)
    else:
        usage = UserUsage(
            user_id=user_id,
            month=month,
            summary_count=0,
            qa_count=1,
        )
        db.add(usage)

    db.commit()


def increment_user_copilot_free_taste(user_id: int, db: Session) -> None:
    """Increment a Free user's *lifetime* Copilot free-taste counter (roadmap 2.2).

    Lifetime (lives on ``users``), so it's keyed only by user — unlike the monthly ``qa_count`` on
    ``user_usage``. Metered after a successful answer; Pro users never reach this path.

    Atomic DB-level increment (not read-modify-write) so concurrent questions — a double-click or
    parallel requests — can't lose an update and let a Free user slip past the 3-question cap.
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
