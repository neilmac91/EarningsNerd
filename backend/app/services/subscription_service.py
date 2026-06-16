from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional
from app.models import User, UserUsage
# FREE_TIER_SUMMARY_LIMIT now lives in entitlements (single source of truth); re-exported here
# (redundant alias = intentional re-export) so existing
# `from app.services.subscription_service import FREE_TIER_SUMMARY_LIMIT` keeps working.
from app.services.entitlements import get_entitlements
from app.services.entitlements import FREE_TIER_SUMMARY_LIMIT as FREE_TIER_SUMMARY_LIMIT

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
