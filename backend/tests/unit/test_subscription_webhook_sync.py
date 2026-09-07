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
    ), patch(
        "app.services.subscription_webhook_service.retrieve_subscription_snapshot",
        return_value=event["data"]["object"],
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


def _resolved_plan(user_id):
    """Resolve the plan through the REAL entitlements resolver (subscription row first).

    Distinct from _fetch, which reads the denormalised User.is_pro mirror + raw row fields: this
    exercises get_plan() against the actual webhook-written Subscription, proving Pro is revoked
    end-to-end and not merely in the mirror.
    """
    from app.database import SessionLocal
    from app.models import User
    from app.services.entitlements import get_plan

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return get_plan(user).value if user else None
    finally:
        db.close()


@pytest.mark.requires_db
def test_subscription_past_due_downgrades_to_free(client):
    """Money-OFF via customer.subscription.updated -> past_due (delinquent payment).

    Closes a founder-review gap: the deleted/canceled path is covered by
    test_subscription_deleted_downgrades_to_free, but the *past_due* money-OFF path had NO
    webhook-level test (the only past_due coverage was a resolver-level parametrize over a
    SimpleNamespace in test_entitlements.py, never a webhook through the handler). If status
    mirroring regressed to downgrade only on canceled/deleted, a delinquent subscriber would keep
    Pro indefinitely and nothing would fail. This posts a real past_due update through the actual
    webhook handler for a currently-Pro user and asserts the money is off.
    """
    with _temp_user(is_pro=False) as user_id:
        # Link ids + grant Pro via checkout (user is now Pro/active), then go delinquent.
        checkout = _checkout_event(user_id, "sub_pastdue_1", "cus_pastdue_1")
        assert _post_event(client, checkout).status_code == 200
        assert _fetch(user_id)[0] is True

        past_due = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_pastdue_1",
                    "customer": "cus_pastdue_1",
                    "status": "past_due",
                    "cancel_at_period_end": False,
                    "items": {"data": [{"price": {"id": "price_x"}}]},
                }
            },
        }
        assert _post_event(client, past_due).status_code == 200

        is_pro, plan, status, _ = _fetch(user_id)
        assert is_pro is False          # denormalised User.is_pro mirror cleared
        assert plan == "free"           # subscription row downgraded off Pro
        assert status == "past_due"     # ...but status faithfully mirrors the delinquency
        # Entitlements resolver (not just the mirror) revokes Pro end-to-end.
        assert _resolved_plan(user_id) == "free"

        _delete_events(checkout["id"], past_due["id"])


def _event_recorded(event_id):
    from app.database import SessionLocal
    from app.models import StripeEvent

    db = SessionLocal()
    try:
        return db.query(StripeEvent.event_id).filter(StripeEvent.event_id == event_id).first() is not None
    finally:
        db.close()


@pytest.mark.requires_db
def test_invoice_payment_failed_keeps_entitlement_and_records_the_event(client):
    """Dunning policy: a failed invoice never revokes Pro; only subscription status events do.

    The policy lived only in a comment in `_apply_event`. If the handler ever "helped" by
    downgrading on payment_failed, a customer inside Stripe's retry window would lose Pro on the
    first declined card and nothing would fail. Posts a real payment_failed for a Pro user and
    asserts money stays ON, through the mirror and the entitlements resolver, while the event is
    still recorded so a redelivery is a no-op.
    """
    with _temp_user(is_pro=False) as user_id:
        checkout = _checkout_event(user_id, "sub_dun_1", "cus_dun_1")
        assert _post_event(client, checkout).status_code == 200
        assert _fetch(user_id)[0] is True

        failed = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "invoice.payment_failed",
            "data": {"object": {"id": "in_dun_1", "subscription": "sub_dun_1", "customer": "cus_dun_1"}},
        }
        with patch("app.services.subscription_webhook_service.capture_event") as capture:
            assert _post_event(client, failed).status_code == 200
        capture.assert_not_called()

        is_pro, plan, status, sub_id = _fetch(user_id)
        assert is_pro is True
        assert plan == "pro"
        assert status == "active"
        assert sub_id == "sub_dun_1"
        assert _resolved_plan(user_id) == "pro"
        assert _event_recorded(failed["id"])
        assert _post_event(client, failed).json().get("idempotent") is True

        _delete_events(checkout["id"], failed["id"])


@pytest.mark.requires_db
def test_trial_will_end_emits_analytics_only(client):
    """trial_will_end is an analytics signal for the bound user and changes no entitlement."""
    with _temp_user(is_pro=False) as user_id:
        checkout = _checkout_event(user_id, "sub_twe_1", "cus_twe_1")
        assert _post_event(client, checkout).status_code == 200

        warning = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "customer.subscription.trial_will_end",
            "data": {"object": {"id": "sub_twe_1", "customer": "cus_twe_1", "trial_end": 1790000000}},
        }
        with patch("app.services.subscription_webhook_service.capture_event") as capture:
            assert _post_event(client, warning).status_code == 200
        capture.assert_called_once_with(str(user_id), "trial_will_end", {"trial_end": 1790000000})

        is_pro, plan, status, _ = _fetch(user_id)
        assert (is_pro, plan, status) == (True, "pro", "active")
        assert _event_recorded(warning["id"])

        _delete_events(checkout["id"], warning["id"])


@pytest.mark.requires_db
def test_unhandled_event_type_is_a_recorded_no_op(client):
    """An event type the handler does not act on (here `invoice.paid`, which is deliberately not
    payment evidence) returns 200, touches no user, emits nothing, and is recorded so Stripe stops
    redelivering it."""
    with _temp_user(is_pro=False) as user_id:
        checkout = _checkout_event(user_id, "sub_unk_1", "cus_unk_1")
        assert _post_event(client, checkout).status_code == 200

        stray = {
            "id": f"evt_{uuid.uuid4().hex}",
            "type": "invoice.paid",
            "data": {"object": {"id": "in_unk_1", "subscription": "sub_unk_1", "customer": "cus_unk_1"}},
        }
        with patch("app.services.subscription_webhook_service.capture_event") as capture:
            response = _post_event(client, stray)
        assert response.status_code == 200
        capture.assert_not_called()
        assert _fetch(user_id)[:3] == (True, "pro", "active")
        assert _event_recorded(stray["id"])
        assert _post_event(client, stray).json().get("idempotent") is True

        _delete_events(checkout["id"], stray["id"])
