from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional
from app.models import User, UserUsage

# Constants
FREE_TIER_SUMMARY_LIMIT = 5

def get_current_month() -> str:
    """Get current month in YYYY-MM format"""
    return datetime.now().strftime("%Y-%m")

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
        usage.updated_at = datetime.now()
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
    if user.is_pro:
        return True, 0, None  # Pro users have unlimited
    
    month = get_current_month()
    current_count = get_user_usage_count(user.id, month, db)
    
    if current_count >= FREE_TIER_SUMMARY_LIMIT:
        return False, current_count, FREE_TIER_SUMMARY_LIMIT
    
    return True, current_count, FREE_TIER_SUMMARY_LIMIT
