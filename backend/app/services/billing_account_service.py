"""The billing routes' database units (``app/routers/subscriptions.py``).

They read the reader's ``subscriptions`` row and store the Stripe customer checkout creates for
them. Neither writes entitlement state: ``subscription_sync.py`` does, for the Stripe webhook and
the registration reverse trial. Plan truth stays in ``entitlements.py``.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Subscription, User


def find_subscription(db: Session, user_id: int) -> Optional[Subscription]:
    """The user's ``subscriptions`` row (one per user, of any status), or None before their first."""
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def save_stripe_customer_id(db: Session, user: User, customer_id: str) -> None:
    """Store the Stripe customer checkout created for ``user`` and commit it. Checkout calls this
    before it creates the checkout session, so a Stripe failure after that keeps the customer for
    the next attempt."""
    user.stripe_customer_id = customer_id
    db.commit()
