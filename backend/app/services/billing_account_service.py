"""The billing routes' database units (``app/routers/subscriptions.py``).

They read the reader's ``subscriptions`` row and store the Stripe customer checkout creates for
them, unless another checkout stored one first. Neither writes entitlement state:
``subscription_sync.py`` does, for the Stripe webhook and the registration reverse trial. Plan
truth stays in ``entitlements.py``.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Subscription, User


def find_subscription(db: Session, user_id: int) -> Optional[Subscription]:
    """The user's ``subscriptions`` row (one per user, of any status), or None before their first."""
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def claim_stripe_customer_id(db: Session, user: User, customer_id: str) -> Optional[str]:
    """Store the Stripe customer checkout created for ``user`` unless the account already has one,
    commit, and return the account's customer: this one, or the one another checkout stored first.

    Checkout checks for a customer as the auth lookup loaded the user, so two checkouts of one
    account can each find none and create one. The write lands only while the column is empty, so
    the customer stored first stays and the other checkout uses it, on one instance or across two
    (under READ COMMITTED a second writer waits for the first's row lock, then finds the column
    set). Written over, the first checkout's session would name a customer the account no longer
    holds, and its payment would be refused as ``customer_mismatch`` (E166). Checkout calls this
    before it creates the checkout session, so a Stripe failure after that keeps the customer for
    the next attempt.
    """
    user_id = user.id
    db.query(User).filter(User.id == user_id, User.stripe_customer_id.is_(None)).update(
        {User.stripe_customer_id: customer_id}, synchronize_session=False)
    db.commit()
    return db.query(User.stripe_customer_id).filter(User.id == user_id).scalar()
