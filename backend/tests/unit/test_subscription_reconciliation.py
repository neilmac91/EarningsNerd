"""Current-ID reconciliation against a mocked real Stripe SDK transport, without network calls."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app import database
from app.config import MIN_SECRET_KEY_LENGTH, Settings, settings
from app.database import Base
from app.models import StripeEvent, Subscription, User
from app.routers import subscriptions
from app.services import stripe_subscription_reader as reader
from app.services import subscription_webhook_service as worker
from app.services.entitlements import get_plan


@pytest.fixture
def billing(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'reconciliation.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[User.__table__, Subscription.__table__, StripeEvent.__table__])
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, autoflush=False))
    monkeypatch.setattr(worker, "capture_event", Mock())
    with Session(engine) as db:
        user = User(email="reconcile@example.com", email_verified=True, is_pro=True,
                    stripe_customer_id="cus_current", stripe_subscription_id="sub_current")
        user.subscription = Subscription(plan="pro", status="active", stripe_customer_id="cus_current",
                                         stripe_subscription_id="sub_current", stripe_price_id="price_before")
        db.add(user)
        db.commit()
        user_id = user.id
    yield engine, user_id
    engine.dispose()


def _snapshot(status="past_due"):
    return {"object": "subscription", "id": "sub_current", "customer": "cus_current", "status": status,
            "trial_end": None, "current_period_end": 1800000000, "cancel_at_period_end": True,
            "items": {"data": [{"price": {"id": "price_current"}, "current_period_end": 1900000000}]}}


def _event(user_id, status="active", kind="customer.subscription.updated", **overrides):
    obj = {"id": "sub_current", "customer": "cus_current", "status": status, **overrides}
    if kind == "checkout.session.completed":
        obj = {"subscription": "sub_current", "customer": "cus_current", "metadata": {"user_id": str(user_id)}}
    return {"id": "evt_reconcile", "type": kind, "data": {"object": obj}}


async def _deliver(payload):
    async def receive():
        return {"type": "http.request", "body": json.dumps(payload).encode(), "more_body": False}
    request = Request({"type": "http", "method": "POST", "path": "/api/subscriptions/webhook", "headers": []}, receive)
    with patch.object(subscriptions.stripe.Webhook, "construct_event", return_value=object()):
        return await subscriptions.stripe_webhook(request, stripe_signature="verified-test-signature")


def _state(billing):
    engine, user_id = billing
    with Session(engine) as db:
        user = db.get(User, user_id)
        sub = user.subscription
        return (get_plan(user).value, user.is_pro, user.stripe_subscription_id, user.stripe_customer_id,
                (sub.status, sub.stripe_subscription_id, sub.stripe_customer_id, sub.stripe_price_id,
                 sub.current_period_end, sub.trial_end, sub.cancel_at_period_end) if sub else None,
                db.query(StripeEvent).count())


def _transport(monkeypatch, payload=None, *, status_code=200, failure=None):
    """Use real StripeClient/RequestsClient parsing/retry machinery with a fake requests session."""
    response = SimpleNamespace(content=json.dumps(payload).encode(), status_code=status_code, headers={})
    session = SimpleNamespace(request=Mock(return_value=response, side_effect=failure), close=Mock())
    real_transport, real_client = reader.stripe.RequestsClient, reader.stripe.StripeClient
    transport_calls = []

    def make_transport(**kwargs):
        transport_calls.append(kwargs)
        return real_transport(session=session, **kwargs)

    client_spy = Mock(side_effect=real_client)
    monkeypatch.setattr(reader.stripe, "RequestsClient", make_transport)
    monkeypatch.setattr(reader.stripe, "StripeClient", client_spy)
    return session, transport_calls, client_spy


@pytest.mark.asyncio
@pytest.mark.parametrize("incoming,current,kind", [
    ("active", "past_due", "customer.subscription.updated"),
    ("past_due", "active", "customer.subscription.updated"),
    ("active", "canceled", "customer.subscription.updated"),
    ("trialing", "active", "customer.subscription.created"),
])
async def test_current_state_wins_and_duplicate_skips_provider(billing, monkeypatch, incoming, current, kind):
    session, _, _ = _transport(monkeypatch, _snapshot(current))
    payload = _event(billing[1], incoming, kind)
    assert await _deliver(payload) == {"status": "success"}
    state = _state(billing)
    assert state[0] == ("pro" if current == "active" else "free")
    assert state[4][0] == current
    assert state[4][3] == "price_current"
    assert state[4][4].year == 2030  # recursive item-level period wins over legacy top level
    assert state[4][6] is True
    assert state[5] == 1
    session.request.assert_called_once()
    assert session.request.call_args.args[:2] == ("get", "https://api.stripe.com/v1/subscriptions/sub_current")
    # A duplicate must not read again, even if the provider is now unreachable.
    session.request.side_effect = AssertionError("duplicate contacted Stripe")
    assert await _deliver(payload) == {"status": "success", "idempotent": True}
    assert _state(billing) == state
    assert session.request.call_count == 1


@pytest.mark.parametrize("field", ["STRIPE_RECONCILIATION_CONNECT_TIMEOUT_SECONDS", "STRIPE_RECONCILIATION_READ_TIMEOUT_SECONDS"])
@pytest.mark.parametrize("value", [0, -1, 11, float("inf"), float("nan")])
def test_reconciliation_timeouts_are_positive_finite_bounded(field, value):
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="x" * MIN_SECRET_KEY_LENGTH, _env_file=None, **{field: value})


@pytest.mark.parametrize("failure", [None, requests.exceptions.Timeout("read timed out"), requests.exceptions.ConnectionError("connection failed")])
def test_dedicated_transport_limits_and_cleanup(monkeypatch, failure):
    monkeypatch.setattr(settings, "STRIPE_RECONCILIATION_CONNECT_TIMEOUT_SECONDS", 1.25)
    monkeypatch.setattr(settings, "STRIPE_RECONCILIATION_READ_TIMEOUT_SECONDS", 2.5)
    session, calls, client_spy = _transport(monkeypatch, _snapshot(), failure=failure)
    if failure:
        with pytest.raises(reader.SubscriptionReconciliationUnavailable):
            reader.retrieve_subscription_snapshot("sub_current", "cus_current")
    else:
        assert reader.retrieve_subscription_snapshot("sub_current", "cus_current") == _snapshot()
    assert calls == [{"timeout": (1.25, 2.5)}]
    assert client_spy.call_args.kwargs["max_network_retries"] == 0
    assert session.request.call_args.kwargs["timeout"] == (1.25, 2.5)
    session.request.assert_called_once()
    session.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,status_code", [
    (requests.exceptions.Timeout("read timed out"), 200),
    (requests.exceptions.ConnectionError("connection failed"), 200),
    (None, 429), (None, 500), (None, 404),
])
async def test_provider_failure_is_retryable_unprocessed_and_does_not_fallback(billing, monkeypatch, failure, status_code):
    response = {"error": {"message": "provider unavailable", "type": "api_error"}}
    session, _, _ = _transport(monkeypatch, response, failure=failure, status_code=status_code)
    before = _state(billing)
    with pytest.raises(HTTPException) as error:
        await _deliver(_event(billing[1], "past_due"))
    assert error.value.status_code == 503
    assert _state(billing) == before
    session.request.assert_called_once()  # no in-lock SDK retry/backoff
    session.close.assert_called_once()
    worker.capture_event.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"id": "sub_other"}, {"customer": "cus_other"}, {"customer": None},
    {"status": None}, {"status": "future_unknown_status"},
    {"trial_end": "tomorrow"}, {"trial_end": True}, {"trial_end": 10**18},
    {"current_period_end": -1}, {"cancel_at_period_end": "false"},
    {"items": None}, {"items": {"data": "not-a-list"}},
    {"items": {"data": [None]}}, {"items": {"data": [{"current_period_end": "tomorrow"}]}},
    {"items": {"data": [{"price": None}]}}, {"items": {"data": [{"price": {"id": 123}}]}},
])
async def test_malformed_provider_snapshot_cannot_change_billing(billing, monkeypatch, changes):
    snapshot = {**_snapshot(), **copy.deepcopy(changes)}
    session, _, _ = _transport(monkeypatch, snapshot)
    before = _state(billing)
    with pytest.raises(HTTPException) as error:
        await _deliver(_event(billing[1]))
    assert error.value.status_code == 503
    assert _state(billing) == before
    session.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("scope", ["checkout", "deletion", "unknown", "initial", "different"])
async def test_outside_current_id_scope_preserves_existing_behavior_without_read(billing, monkeypatch, scope):
    engine, user_id = billing
    if scope == "initial":
        with Session(engine) as db:
            user = db.get(User, user_id)
            db.delete(user.subscription)
            user.stripe_subscription_id = None
            db.commit()
    if scope == "checkout":
        payload = _event(user_id, kind="checkout.session.completed")
    elif scope == "deletion":
        payload = _event(user_id, kind="customer.subscription.deleted")
    elif scope == "unknown":
        payload = _event(user_id, id="sub_unknown", customer="cus_unknown")
    elif scope == "different":
        payload = _event(user_id, id="sub_replacement")
    else:
        payload = _event(user_id)
    spy = Mock(side_effect=AssertionError("out-of-scope event contacted Stripe"))
    monkeypatch.setattr(worker, "retrieve_subscription_snapshot", spy)
    assert await _deliver(payload) == {"status": "success"}
    spy.assert_not_called()
    state = _state(billing)
    assert state[0] == ("free" if scope == "deletion" else "pro")
    assert state[5] == 1
    if scope == "different":
        assert state[2] == "sub_replacement"  # existing replacement behavior is deliberately unchanged


@pytest.mark.asyncio
@pytest.mark.parametrize("binding", ["row_precedes_mirror", "mirror_only"])
async def test_current_binding_uses_row_then_user_mirror(billing, monkeypatch, binding):
    engine, user_id = billing
    with Session(engine) as db:
        user = db.get(User, user_id)
        if binding == "row_precedes_mirror":
            user.stripe_subscription_id = "sub_stale_mirror"
        else:
            db.delete(user.subscription)
        db.commit()
    session, _, _ = _transport(monkeypatch, _snapshot())
    assert await _deliver(_event(user_id)) == {"status": "success"}
    session.request.assert_called_once()
    assert _state(billing)[0] == "free"
