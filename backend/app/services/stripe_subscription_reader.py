"""Current-subscription read boundary; independent of the global checkout Stripe client.

The transport limits connection/read inactivity and makes one attempt. These are not a total
wall-clock deadline: DNS and a progressing response can take longer. The calling worker retains
its account lock/session until the read finishes; never abandon that worker on a future timeout.
"""
from __future__ import annotations

import stripe
from contextlib import contextmanager
from collections.abc import Iterator

from app.config import settings

# Provider wire statuses, not entitlement rules (those remain in entitlements.py).
_SUBSCRIPTION_STATUSES = frozenset({
    "active", "trialing", "past_due", "canceled", "unpaid", "incomplete", "incomplete_expired", "paused",
})
_MAX_TIMESTAMP = 253402300799  # last whole second representable by Python's UTC datetime


class SubscriptionReconciliationUnavailable(Exception):
    """Current provider state could not be established; retry without recording the event."""


def _validate_timestamp(obj: dict, field: str) -> None:
    value = obj.get(field)
    if value is not None and (type(value) is not int or not 0 <= value <= _MAX_TIMESTAMP):
        raise ValueError(f"invalid subscription {field}")


def _validate_snapshot(snapshot: dict, subscription_id: str, customer_id: str | None) -> dict:
    if not isinstance(snapshot, dict) or snapshot.get("id") != subscription_id:
        raise ValueError("subscription identity does not match the requested ID")
    customer = snapshot.get("customer")
    if not isinstance(customer, str) or not customer.strip() or (customer_id and customer != customer_id):
        raise ValueError("subscription customer is missing or mismatched")
    status = snapshot.get("status")
    if not isinstance(status, str) or status not in _SUBSCRIPTION_STATUSES:
        raise ValueError("subscription status is missing or unsupported")
    for field in ("current_period_end", "trial_end"):
        _validate_timestamp(snapshot, field)
    if "cancel_at_period_end" in snapshot and type(snapshot["cancel_at_period_end"]) is not bool:
        raise ValueError("invalid subscription cancel_at_period_end")
    if "items" in snapshot:
        items = snapshot["items"]
        if not isinstance(items, dict) or not isinstance(items.get("data"), list):
            raise ValueError("invalid subscription items")
        for item in items["data"]:
            if not isinstance(item, dict):
                raise ValueError("invalid subscription item")
            _validate_timestamp(item, "current_period_end")
            if "price" in item:
                price = item["price"]
                if not isinstance(price, dict) or not isinstance(price.get("id"), str) or not price["id"].strip():
                    raise ValueError("invalid subscription price")
    return snapshot


@contextmanager
def _bounded_client() -> Iterator[stripe.StripeClient]:
    """Shared transport ownership for exact-ID billing reads; no global client mutation."""
    transport = stripe.RequestsClient(timeout=(
        settings.STRIPE_RECONCILIATION_CONNECT_TIMEOUT_SECONDS,
        settings.STRIPE_RECONCILIATION_READ_TIMEOUT_SECONDS,
    ))
    try:
        yield stripe.StripeClient(settings.STRIPE_SECRET_KEY, http_client=transport, max_network_retries=0)
    finally:
        transport.close()


def retrieve_subscription_snapshot(subscription_id: str, customer_id: str | None) -> dict:
    """Read/validate one exact subscription; close the dedicated transport on every outcome."""
    try:
        with _bounded_client() as client:
            snapshot = client.v1.subscriptions.retrieve(subscription_id).to_dict()
            return _validate_snapshot(snapshot, subscription_id, customer_id)
    except Exception as exc:
        # Provider/transport/response failures share one retryable boundary. Never return the stale
        # webhook object or expose provider error text/credentials in the HTTP response.
        raise SubscriptionReconciliationUnavailable("Current Stripe subscription state is unavailable") from exc


def retrieve_invoice_snapshot(invoice_id: str) -> dict:
    """Read one invoice for payment attribution; payment evidence validates the returned fields."""
    try:
        with _bounded_client() as client:
            snapshot = client.v1.invoices.retrieve(invoice_id).to_dict()
            if not isinstance(snapshot, dict) or snapshot.get("id") != invoice_id:
                raise ValueError("Invoice identity does not match requested ID")
            return snapshot
    except Exception as exc:
        raise SubscriptionReconciliationUnavailable("Current Stripe invoice state is unavailable") from exc
