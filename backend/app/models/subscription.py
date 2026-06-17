"""Subscription + Stripe-event models.

`Subscription` is the durable, queryable record of a user's billing state — the single source
of truth that `entitlements.py` reads (``User.is_pro`` remains a denormalised mirror kept in sync
by the Stripe webhook, for back-compat with existing reads).

`StripeEvent` records processed webhook event ids so a duplicate delivery (Stripe retries, or
at-least-once delivery) is a no-op and can never double-apply an entitlement change.

Kept deliberately portable: status/plan are plain strings (not PG enums) and datetimes use
``DateTime(timezone=True)`` so the same schema works on Postgres (prod) and SQLite (tests).
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base

# Stripe subscription statuses we treat as "entitled to Pro". `trialing` is the reverse trial.
ACTIVE_STATUSES = frozenset({"active", "trialing"})


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    # One subscription row per user (1:1). Unique enforces it at the DB level.
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan = Column(String(20), nullable=False, default="free")          # free | pro
    status = Column(String(20), nullable=False, default="active")      # active|trialing|past_due|canceled|incomplete
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=True, index=True)
    stripe_price_id = Column(String, nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="subscription")


class StripeEvent(Base):
    """Idempotency ledger: one row per processed Stripe webhook event id."""
    __tablename__ = "stripe_events"

    # Stripe's event id (e.g. ``evt_123``) is the natural primary key.
    event_id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
