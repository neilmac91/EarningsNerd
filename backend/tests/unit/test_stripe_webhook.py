"""
Stripe webhook tests for POST /api/subscriptions/webhook.

The paid critical path previously had zero test coverage. These verify signature
handling and that a well-formed event is processed. Signature construction is
mocked at stripe.Webhook.construct_event so the tests don't depend on a real
Stripe signing secret beyond the mock set in conftest.
"""

from unittest.mock import patch

import pytest
import stripe
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


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
def test_valid_event_for_unknown_user_is_accepted(client):
    """A verified checkout.session.completed for a non-existent user is a no-op 200."""
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "subscription": "sub_test_123",
                "metadata": {"user_id": "99999999", "plan": "pro"},
            }
        },
    }
    with patch(
        "app.routers.subscriptions.stripe.Webhook.construct_event",
        return_value=event,
    ):
        resp = client.post(
            "/api/subscriptions/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=deadbeef"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
