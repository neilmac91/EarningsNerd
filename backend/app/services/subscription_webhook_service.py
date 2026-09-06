"""Worker-owned Stripe transactions, serialized on each existing account's User row.

This prevents overlapping deliveries from racing the per-user subscription row. Current-ID
created/updated events read current Stripe state; cross-ID ordering and cross-user bindings remain
separate. No ORM objects escape the worker, and best-effort analytics run after commit and session closure.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import Subscription, User
from app.services import subscription_sync, billing_revenue_service
from app.services.posthog_client import EVENT_TRIAL_STARTED, capture_event
from app.services.stripe_subscription_reader import (
    SubscriptionReconciliationUnavailable, retrieve_invoice_snapshot, retrieve_subscription_snapshot,
)

logger = logging.getLogger(__name__)


class SubscriptionEventBusy(Exception):
    """The delivery must retry without recording a processed event or changing billing state."""


def _event_owner_id(db: Session, event_type: str, obj: dict) -> Optional[int]:
    if event_type == "checkout.session.completed":
        return int(obj["metadata"]["user_id"])
    if event_type.startswith("customer.subscription."):
        user = subscription_sync._find_user(db, obj.get("id"), obj.get("customer"))
    elif event_type == "invoice.payment_failed":
        user = subscription_sync._find_user(db, obj.get("subscription"), obj.get("customer"))
    else:
        return None
    return user.id if user else None


def _lock_event_owner(
    db: Session, event_type: str, obj: dict,
    payment: Optional[billing_revenue_service.PaymentEvidence] = None,
) -> Optional[User]:
    def resolve() -> Optional[int]:
        return (billing_revenue_service.payment_attribution(db, payment)[0] if payment is not None
                else _event_owner_id(db, event_type, obj))

    owner_id = resolve()
    if owner_id is None:
        return None
    user = db.query(User).filter(User.id == owner_id).populate_existing().with_for_update(nowait=True).first()
    if user is None:
        return None
    # Candidate resolution can load a subscription before the lock. Expire it and the user so
    # every handler/entitlement read sees state committed before this transaction acquired it.
    db.expire_all()
    if resolve() != owner_id:
        raise SubscriptionEventBusy("Stripe ownership changed while acquiring the account lock")
    return user


def _reconcile_current_subscription(db: Session, event_type: str, obj: dict, user: Optional[User]) -> dict:
    """Refresh only an already-bound ID; initial/replacement and signed deletion paths stay intact."""
    if user is None or event_type not in ("customer.subscription.created", "customer.subscription.updated"):
        return obj
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    current_id = (sub.stripe_subscription_id if sub else None) or user.stripe_subscription_id
    if not current_id or obj.get("id") != current_id:
        return obj
    customer_id = (sub.stripe_customer_id if sub else None) or user.stripe_customer_id
    return retrieve_subscription_snapshot(current_id, customer_id)


def _apply_event(db: Session, event_type: str, obj: dict, user: Optional[User]) -> list[tuple]:
    """Apply to the locked owner; return primitive analytics payloads for after the commit."""
    analytics = []
    if event_type == "checkout.session.completed" and user is not None:
        affected = subscription_sync.apply_checkout_completed(db, obj, user=user)
        if affected:
            metadata = obj.get("metadata", {}) or {}
            analytics.append((str(affected.id), "subscription_activated", {
                "plan": metadata.get("plan", "pro"),
                "price_id": metadata.get("price_id"),
                "billing_cycle": metadata.get("billing_cycle"),
                "stripe_subscription_id": obj.get("subscription"),
            }))
    elif event_type in ("customer.subscription.created", "customer.subscription.updated") and user is not None:
        subscription_sync.apply_subscription_upsert(db, obj, user=user)
        if event_type == "customer.subscription.created" and obj.get("status") == "trialing":
            analytics.append((str(user.id), EVENT_TRIAL_STARTED, {
                "source": "stripe", "trial_end": obj.get("trial_end"),
            }))
    elif event_type == "customer.subscription.deleted" and user is not None:
        subscription_sync.apply_subscription_deleted(db, obj, user=user)
    elif event_type == "invoice.payment_failed":
        # Preserve dunning policy: only subscription status events revoke entitlement.
        logger.info("Stripe invoice.payment_failed for customer %s", obj.get("customer"))
    elif event_type == "customer.subscription.trial_will_end" and user is not None:
        analytics.append((str(user.id), "trial_will_end", {"trial_end": obj.get("trial_end")}))
    return analytics


def process_stripe_event(event: dict) -> dict:
    """Run entirely in one worker thread, including Session creation and error cleanup."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        event_id, event_type, obj = event.get("id"), event["type"], event["data"]["object"]
        payment = None
        if event_type == "invoice_payment.paid":
            payment = billing_revenue_service.payment_from_event(event)
            if subscription_sync.is_event_processed(db, event_id):
                return {"status": "success", "idempotent": True}
            db.rollback()  # Release the receipt lookup transaction before the provider read.
            # No DB locks remain during this read. Unlike subscription reconciliation it
            # only enriches immutable allocation evidence, not an ordered entitlement snapshot.
            invoice = retrieve_invoice_snapshot(payment.invoice_id)
            try:
                payment = billing_revenue_service.with_invoice(payment, invoice)
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                raise SubscriptionReconciliationUnavailable("Stripe invoice evidence is unavailable") from exc
        user = _lock_event_owner(db, event_type, obj, payment)
        if subscription_sync.is_event_processed(db, event_id):
            return {"status": "success", "idempotent": True}
        if payment is not None:
            signal = billing_revenue_service.record_payment(db, payment, user)
            analytics = [signal] if signal else []
        else:
            obj = _reconcile_current_subscription(db, event_type, obj, user)
            analytics = _apply_event(db, event_type, obj, user)
        subscription_sync.mark_event_processed(db, event_id, event_type)
        db.commit()
    except DBAPIError as exc:
        db.rollback()
        if getattr(exc.orig, "pgcode", None) == "55P03":
            raise SubscriptionEventBusy("Stripe account lock is held by another delivery") from exc
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for distinct_id, name, properties in analytics:
        try:
            capture_event(distinct_id, name, properties)
        except Exception:
            logger.warning("Stripe analytics failed after commit event_id=%s name=%s", event_id, name)
    return {"status": "success"}
