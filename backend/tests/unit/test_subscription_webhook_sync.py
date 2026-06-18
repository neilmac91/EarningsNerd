"""Webhook → Subscription sync + idempotency (the paid critical path).

Verifies that a verified Stripe event creates/updates the `subscriptions` row, mirrors `is_pro`,
and that a duplicate delivery (same event id) is a no-op. construct_event is mocked so we don't
need a real signing secret beyond the conftest mock.
"""
import json
import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from stripe import StripeObject
from fastapi.testclient import TestClient

from main import app
from app.services.subscription_sync import _current_period_end_from_sub


def test_current_period_end_prefers_item_level():
    """Stripe API 2025-10-29 moved current_period_end onto items; read it there."""
    sub = {"current_period_end": None, "items": {"data": [{"current_period_end": 1784414367}]}}
    assert _current_period_end_from_sub(sub) == 1784414367


def test_current_period_end_falls_back_to_top_level():
    """Older API versions still put it at the top level."""
    sub = {"current_period_end": 1700000000, "items": {"data": [{}]}}
    assert _current_period_end_from_sub(sub) == 1700000000


def test_current_period_end_missing_returns_none():
    assert _current_period_end_from_sub({"items": {"data": []}}) is None


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@contextmanager
def _temp_user(**overrides):
    """Create a throwaway user (and clean up its subscription + the user) around a test."""
    from app.database import SessionLocal
    from app.models import User, Subscription

    db = SessionLocal()
    user = User(
        email=f"sub-test-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        email_verified=True,
        **overrides,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    try:
        yield user_id
    finally:
        db = SessionLocal()
        db.query(Subscription).filter(Subscription.user_id == user_id).delete()
        db.query(User).filter(User.id == user_id).delete()
        db.commit()
        db.close()


def _post_event(client, event):
    # The handler processes the verified raw payload (stripe v15 StripeObject isn't dict-like),
    # so the event must be sent as the body; construct_event only verifies the signature here.
    payload = json.dumps(event).encode()
    with patch(
        "app.routers.subscriptions.stripe.Webhook.construct_event",
        return_value=StripeObject.construct_from(event, "sk_test"),
    ):
        return client.post(
            "/api/subscriptions/webhook",
            content=payload,
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )


def _fetch(user_id):
    from app.database import SessionLocal
    from app.models import User, Subscription

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
        # Detach scalars we need so callers can read them after the session closes.
        return (
            (user.is_pro if user else None),
            (sub.plan if sub else None),
            (sub.status if sub else None),
            (sub.stripe_subscription_id if sub else None),
        )
    finally:
        db.close()


@pytest.mark.requires_db
def test_checkout_completed_creates_subscription_and_mirrors_is_pro(client):
    with _temp_user(is_pro=False) as user_id:
        event = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "subscription": "sub_abc123",
                    "customer": "cus_abc123",
                    "metadata": {"user_id": str(user_id), "plan": "pro", "price_id": "price_x"},
                }
            },
        }
        resp = _post_event(client, event)
        assert resp.status_code == 200

        is_pro, plan, status, stripe_sub_id = _fetch(user_id)
        assert is_pro is True
        assert plan == "pro"
        assert status == "active"
        assert stripe_sub_id == "sub_abc123"


def _checkout_event(user_id, sub_id, customer_id):
    """A checkout.session.completed event — the step that links Stripe ids to the user."""
    return {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": sub_id,
                "customer": customer_id,
                "metadata": {"user_id": str(user_id), "plan": "pro", "price_id": "price_x"},
            }
        },
    }


def _set_is_pro(user_id, value):
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    db.query(User).filter(User.id == user_id).update({"is_pro": value})
    db.commit()
    db.close()


def _delete_events(*event_ids):
    from app.database import SessionLocal
    from app.models import StripeEvent

    db = SessionLocal()
    db.query(StripeEvent).filter(StripeEvent.event_id.in_(event_ids)).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.mark.requires_db
def test_duplicate_event_is_idempotent(client):
    """Re-delivering the same event id must short-circuit without re-applying state."""
    with _temp_user(is_pro=False) as user_id:
        # Link the Stripe ids first (real flow), so later subscription.* events resolve the user.
        checkout = _checkout_event(user_id, "sub_idem_1", "cus_idem_1")
        assert _post_event(client, checkout).status_code == 200
        assert _fetch(user_id)[0] is True

        event_id = f"evt_{uuid.uuid4().hex}"
        event = {
            "id": event_id,
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_idem_1",
                    "customer": "cus_idem_1",
                    "status": "active",
                    "cancel_at_period_end": False,
                    "items": {"data": [{"price": {"id": "price_x"}}]},
                }
            },
        }
        # Drift is_pro, then deliver the event once: it should re-apply (set is_pro True).
        _set_is_pro(user_id, False)
        assert _post_event(client, event).status_code == 200
        assert _fetch(user_id)[0] is True  # proves the event WOULD apply

        # Drift again, then re-deliver the SAME event id: idempotency must NOT re-apply.
        _set_is_pro(user_id, False)
        resp = _post_event(client, event)
        assert resp.status_code == 200
        assert resp.json().get("idempotent") is True
        assert _fetch(user_id)[0] is False  # stayed drifted → re-apply was skipped

        _delete_events(checkout["id"], event_id)


@pytest.mark.requires_db
def test_subscription_deleted_downgrades_to_free(client):
    with _temp_user(is_pro=False) as user_id:
        # Link ids + grant Pro via checkout, then cancel.
        checkout = _checkout_event(user_id, "sub_del_1", "cus_del_1")
        assert _post_event(client, checkout).status_code == 200
        assert _fetch(user_id)[0] is True

        deleted = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_del_1", "customer": "cus_del_1", "status": "canceled"}},
        }
        assert _post_event(client, deleted).status_code == 200

        is_pro, plan, status, _ = _fetch(user_id)
        assert is_pro is False
        assert plan == "free"
        assert status == "canceled"

        _delete_events(checkout["id"], deleted["id"])
