"""New-filing alert models: per-user notification preferences + a send/dedup log.

`NotificationPreferences` is one row per user (form-type opt-ins, channel, digest cadence, and a
Pro-gated realtime flag). `NotificationLog` is the dedup + audit ledger — a unique
``(user_id, filing_id, channel)`` makes a double-send impossible even under concurrent/retried
scans (the same role `stripe_events` plays for the Stripe webhook).

Kept portable like the rest of the schema: plain ``String`` not PG enums, ``DateTime(timezone=True)``
so the same tables work on Postgres (prod) and SQLite (tests).
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

# Channels / digest cadences kept as validated strings (not enums) for SQLite portability.
CHANNEL_EMAIL = "email"
CHANNEL_IN_APP = "in_app"


class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    notify_10k = Column(Boolean, nullable=False, default=True)
    notify_10q = Column(Boolean, nullable=False, default=True)
    notify_8k = Column(Boolean, nullable=False, default=False)   # Pro-gated (eightk_coverage)
    # FPI alert opt-ins (Phase 5). 20-F/40-F = foreign annual report (free, default on like 10-K).
    # 6-K = foreign interim/furnished (free, default OFF + digest-only — 6-Ks are frequent and
    # heterogeneous, so a default-on realtime would be spammy).
    notify_20f = Column(Boolean, nullable=False, default=True)
    notify_6k = Column(Boolean, nullable=False, default=False)
    channel = Column(String(20), nullable=False, default=CHANNEL_EMAIL)   # email | in_app
    digest = Column(String(20), nullable=False, default="daily")          # immediate | daily | weekly
    realtime = Column(Boolean, nullable=False, default=False)             # Pro-gated (realtime_alerts)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="notification_preferences")


class NotificationLog(Base):
    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filing_id = Column(Integer, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(20), nullable=False, default=CHANNEL_EMAIL)
    status = Column(String(20), nullable=False, default="sent")   # sent | failed | skipped
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="notification_logs")

    __table_args__ = (
        UniqueConstraint("user_id", "filing_id", "channel", name="uq_notification_log_user_filing_channel"),
    )
