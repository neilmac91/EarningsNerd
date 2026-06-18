"""
Stripe webhook tests for POST /api/subscriptions/webhook.

The paid critical path previously had zero test coverage. These verify signature
handling and that a well-formed event is processed.

IMPORTANT (regression): stripe-python v15's ``StripeObject`` is NOT dict-like —
``.get()`` raises ``AttributeError``. ``construct_event`` returns a ``StripeObject``,
so the handler must process the *raw payload* (plain dicts), not the returned object.
These tests therefore mock ``construct_event`` to return a real ``StripeObject`` while
the event JSON is sent as the request body, mirroring production exactly. Asserting on
the parsed dict (rather than the mock return) is what makes them catch the v15 break.
"""

import json
from unittest.mock import patch

import pytest
import stripe
from stripe import StripeObject
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _stripe_object(event: dict) -> StripeObject:
    """Build a StripeObject as construct_event returns in stripe-python v15 (no .get())."""
    return StripeObject.construct_from(event, "sk_test")


def _post(client: TestClient, event: dict):
    """POST the event as the raw body, with construct_event mocked to verify + return a StripeObject."""
    payload = json.dumps(event).encode()
    with patch(
        "app.routers.subscriptions.stripe.Webhook.construct_event",
        return_value=_stripe_object(event),
    ):
        return client.post(
            "/api/subscriptions/webhook",
            content=payload,
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )


def test_missing_signature_header_returns_400(client):
    """No stripe-signature header is a client error (400), not a 500."""
    resp = client.post("/api/subscriptions/webhook", content=b"{}")
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


def test_invalid_signature_returns_400(client):
    """A failed signature verification returns 400 so Stripe doesn't retry."""
    with patch(
        "app.routers.subscriptions.stripe.Webhook.construct_event",
        side_effect=stripe.error.SignatureVerificationError("bad sig", "sig-header"),
    ):
        resp = client.post(
            "/api/subscriptions/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid signature"


def test_malformed_payload_returns_400(client):
    """A ValueError from construct_event (bad payload) returns 400."""
    with patch(
        "app.routers.subscriptions.stripe.Webhook.construct_event",
        side_effect=ValueError("bad payload"),
    ):
        resp = client.post(
            "/api/subscriptions/webhook",
            content=b"not-json",
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid payload"


@pytest.mark.requires_db
def test_malformed_event_metadata_returns_400(client):
    """A verified event missing metadata.user_id is a 400 (unprocessable), not a 500.

    Returning 400 stops Stripe from endlessly retrying an event we can never process.
    """
    event = {
        "id": "evt_meta",
        "type": "checkout.session.completed",
        "data": {"object": {"subscription": "sub_test_123", "metadata": {}}},
    }
    resp = _post(client, event)
    assert resp.status_code == 400
    assert "malformed" in resp.json()["detail"].lower()


@pytest.mark.requires_db
def test_valid_event_for_unknown_user_is_accepted(client):
    """A verified checkout.session.completed for a non-existent user is a no-op 200.

    Regression for the stripe v15 ``StripeObject`` break: construct_event returns a
    StripeObject (no .get()); processing the raw payload as a dict must succeed (200),
    not raise AttributeError('get') → 500.
    """
    event = {
        "id": "evt_unknown_user",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": "sub_test_123",
                "metadata": {"user_id": "99999999", "plan": "pro"},
            }
        },
    }
    resp = _post(client, event)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


@pytest.mark.requires_db
def test_subscription_created_stripeobject_does_not_500(client):
    """customer.subscription.created delivered as a StripeObject must not 500 on .get().

    This is the exact production failure: `event.get("id")` / `obj.get(...)` on a v15
    StripeObject raised AttributeError('get') → HTTP 500, so no payment was ever recorded.
    """
    event = {
        "id": "evt_sub_created",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_unknown_999",
                "customer": "cus_unknown_999",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_x"}}]},
                "current_period_end": 1893456000,
                "trial_end": None,
                "cancel_at_period_end": False,
            }
        },
    }
    resp = _post(client, event)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
