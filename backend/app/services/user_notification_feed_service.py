"""The in-app bell: recent filing alerts from ``notification_log``, the unread count, and marking
the bell as opened.

An alert is read when it was logged at or before ``notifications_seen_at`` and unread when logged
after it; ``recent_notifications`` and ``unread_count`` apply the two halves of that one rule.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company, Filing, NotificationLog, User


@dataclass(frozen=True)
class NotificationFeedEntry:
    """One alert row for the bell, with the raw stored timestamps."""
    id: int                     # notification_log row id
    filing_id: int
    ticker: str
    company_name: str
    filing_type: str
    filing_date: Optional[datetime]
    created_at: Optional[datetime]   # when the alert was logged
    read: bool                  # logged at/before the user last opened the bell


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Treat naive datetimes (SQLite) as UTC so aware/naive comparisons never raise."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def unread_count(db: Session, user: User) -> int:
    """Count of successfully-sent alerts logged since the user last opened the bell.

    One aggregate statement (E10c): the bell polls this every minute per open session and the
    log is never purged, so the count must not grow with account age. ``created_at`` is a
    timezone-aware column; an aware-UTC bound value compares correctly on PostgreSQL
    (timestamptz) and on SQLite (both sides are rendered as naive UTC text).
    """
    query = db.query(func.count(NotificationLog.id)).filter(
        NotificationLog.user_id == user.id, NotificationLog.status == "sent"
    )
    seen = _as_utc(user.notifications_seen_at)
    if seen is not None:
        query = query.filter(NotificationLog.created_at > seen)
    return query.scalar() or 0


def recent_notifications(db: Session, user: User, limit: int) -> List[NotificationFeedEntry]:
    """Recent successfully-sent filing alerts, newest first, at most ``limit``.

    Reads the same ``notification_log`` rows the alert scanner writes (channel-agnostic), so no
    extra delivery path is needed — opening the bell surfaces whatever alerts were recorded.
    """
    seen = _as_utc(user.notifications_seen_at)
    rows = (
        db.query(NotificationLog, Filing, Company)
        .join(Filing, NotificationLog.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(
            NotificationLog.user_id == user.id,
            NotificationLog.status == "sent",
        )
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        NotificationFeedEntry(
            id=log.id,
            filing_id=filing.id,
            ticker=company.ticker,
            company_name=company.name,
            filing_type=filing.filing_type,
            filing_date=filing.filing_date,
            created_at=log.created_at,
            read=bool(seen and (c := _as_utc(log.created_at)) and c <= seen),
        )
        for log, filing, company in rows
    ]


def mark_seen(db: Session, current_user: User) -> User:
    """Stamp ``notifications_seen_at`` and commit; return the user the response is built from.

    Fetch the real row via ``db.get`` and mutate it directly (rather than a bulk UPDATE) so the
    response is built from a fresh, in-session user — robust regardless of ``expire_on_commit`` — and
    so it works for the test stand-in (a non-session user) too: with no row, the stand-in is
    returned unchanged.
    """
    user = db.get(User, current_user.id)
    if user is not None:
        user.notifications_seen_at = datetime.now(timezone.utc)
        db.commit()
    else:
        user = current_user
    return user
