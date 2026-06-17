"""Sync Stripe billing state into our `subscriptions` table (the entitlement source of truth).

The Stripe webhook is the *only* writer of entitlement state — we never grant Pro from the
checkout success redirect. All mutations here also keep the denormalised ``User.is_pro`` mirror in
lock-step so existing reads stay correct.

Everything is written defensively (missing fields, unknown users, duplicate deliveries) because
webhook payloads are partially-trusted and delivered at-least-once.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import StripeEvent, Subscription, User
from app.models.subscription import ACTIVE_STATUSES

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- idempotency

def is_event_processed(db: Session, event_id: Optional[str]) -> bool:
    """True if we've already handled this Stripe event id (idempotency guard)."""
    if not event_id:
        return False
    return db.query(StripeEvent.event_id).filter(StripeEvent.event_id == event_id).first() is not None


def mark_event_processed(db: Session, event_id: Optional[str], event_type: str) -> None:
    """Record an event id so a duplicate delivery is a no-op. Caller commits."""
    if not event_id:
        return
    db.add(StripeEvent(event_id=event_id, type=event_type))


# --------------------------------------------------------------------------- helpers

def _ts_to_dt(ts: Any) -> Optional[datetime]:
    """Stripe unix timestamp → tz-aware UTC datetime (or None)."""
    if ts in (None, "", 0):
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _price_id_from_sub(sub: dict) -> Optional[str]:
    try:
        return sub["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        return None


def _get_or_create_subscription(db: Session, user: User) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if sub is None:
        sub = Subscription(user_id=user.id, plan="free", status="incomplete")
        db.add(sub)
    return sub


def _apply_mirror(user: User, status: str) -> None:
    """Keep ``User.is_pro`` consistent with the subscription status."""
    user.is_pro = status in ACTIVE_STATUSES


# --------------------------------------------------------------------------- event handlers

def apply_checkout_completed(db: Session, session_obj: dict) -> Optional[User]:
    """Handle ``checkout.session.completed``: link Stripe ids and grant Pro.

    Period/trial details arrive on the following ``customer.subscription.*`` event; here we only
    establish the link + entitlement. Returns the affected user (or None if unknown).
    """
    metadata = session_obj.get("metadata") or {}
    user_id = int(metadata["user_id"])  # KeyError/ValueError → caller maps to 400
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    stripe_sub_id = session_obj.get("subscription")
    stripe_customer_id = session_obj.get("customer")

    sub = _get_or_create_subscription(db, user)
    sub.plan = "pro"
    sub.status = "active"
    sub.stripe_subscription_id = stripe_sub_id or sub.stripe_subscription_id
    sub.stripe_customer_id = stripe_customer_id or sub.stripe_customer_id
    sub.stripe_price_id = metadata.get("price_id") or sub.stripe_price_id

    # Mirror onto User (back-compat reads).
    if stripe_sub_id:
        user.stripe_subscription_id = stripe_sub_id
    if stripe_customer_id:
        user.stripe_customer_id = stripe_customer_id
    _apply_mirror(user, sub.status)
    return user


def apply_subscription_upsert(db: Session, sub_obj: dict) -> Optional[User]:
    """Handle ``customer.subscription.created`` / ``.updated``: full state from the Stripe object."""
    stripe_sub_id = sub_obj.get("id")
    stripe_customer_id = sub_obj.get("customer")
    status = (sub_obj.get("status") or "incomplete").lower()

    user = _find_user(db, stripe_sub_id, stripe_customer_id)
    if not user:
        return None

    sub = _get_or_create_subscription(db, user)
    sub.status = status
    sub.plan = "pro" if status in ACTIVE_STATUSES else "free"
    sub.stripe_subscription_id = stripe_sub_id or sub.stripe_subscription_id
    sub.stripe_customer_id = stripe_customer_id or sub.stripe_customer_id
    sub.stripe_price_id = _price_id_from_sub(sub_obj) or sub.stripe_price_id
    sub.current_period_end = _ts_to_dt(sub_obj.get("current_period_end")) or sub.current_period_end
    sub.trial_end = _ts_to_dt(sub_obj.get("trial_end"))
    sub.cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))

    if stripe_sub_id:
        user.stripe_subscription_id = stripe_sub_id
    if stripe_customer_id:
        user.stripe_customer_id = stripe_customer_id
    _apply_mirror(user, status)
    return user


def apply_subscription_deleted(db: Session, sub_obj: dict) -> Optional[User]:
    """Handle ``customer.subscription.deleted``: downgrade to free."""
    user = _find_user(db, sub_obj.get("id"), sub_obj.get("customer"))
    if not user:
        return None

    sub = _get_or_create_subscription(db, user)
    sub.status = "canceled"
    sub.plan = "free"
    sub.cancel_at_period_end = False
    user.is_pro = False
    user.stripe_subscription_id = None
    return user


def _find_user(db: Session, stripe_sub_id: Optional[str], stripe_customer_id: Optional[str]) -> Optional[User]:
    """Locate the owner of a Stripe subscription, by sub id first then customer id."""
    if stripe_sub_id:
        sub = db.query(Subscription).filter(Subscription.stripe_subscription_id == stripe_sub_id).first()
        if sub:
            return db.query(User).filter(User.id == sub.user_id).first()
        user = db.query(User).filter(User.stripe_subscription_id == stripe_sub_id).first()
        if user:
            return user
    if stripe_customer_id:
        sub = db.query(Subscription).filter(Subscription.stripe_customer_id == stripe_customer_id).first()
        if sub:
            return db.query(User).filter(User.id == sub.user_id).first()
        return db.query(User).filter(User.stripe_customer_id == stripe_customer_id).first()
    return None


# --------------------------------------------------------------------------- reverse trial

def start_reverse_trial(db: Session, user: User, days: int) -> Subscription:
    """Grant a no-card reverse trial: a ``trialing`` Pro subscription for ``days`` days.

    Idempotent-ish: won't downgrade or reset a user who already has an active/trialing
    subscription. Caller commits.
    """
    existing = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if existing and existing.status in ACTIVE_STATUSES:
        return existing

    sub = existing or Subscription(user_id=user.id)
    sub.plan = "pro"
    sub.status = "trialing"
    sub.trial_end = datetime.now(timezone.utc) + timedelta(days=days)
    sub.cancel_at_period_end = False
    if existing is None:
        db.add(sub)
    user.is_pro = True
    return sub
