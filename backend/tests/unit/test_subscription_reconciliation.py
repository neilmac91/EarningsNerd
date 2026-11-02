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
from app.services.posthog_client import EVENT_TRIAL_STARTED
from app.utils.datetimes import utcnow


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
@pytest.mark.parametrize("scope", ["checkout", "deletion", "unknown", "initial"])
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
    else:
        payload = _event(user_id)
    spy = Mock(side_effect=AssertionError("out-of-scope event contacted Stripe"))
    monkeypatch.setattr(worker, "retrieve_subscription_snapshot", spy)
    assert await _deliver(payload) == {"status": "success"}
    spy.assert_not_called()
    state = _state(billing)
    assert state[0] == ("free" if scope == "deletion" else "pro")
    assert state[5] == 1


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


# ── Events for another subscription (E98) ────────────────────────────────────────────────────────
# Once the account has a binding, a created/updated event for another subscription reads the bound one,
# then its own, through the real reader and transport. The binding goes to whichever Stripe ranks first
# (grants Pro, then newer ``created``, then higher ID); the payload's claim never decides.

def _sub(sub_id, status, created, *, customer="cus_current", trial_end=None):
    return {"object": "subscription", "id": sub_id, "customer": customer, "status": status, "created": created,
            "trial_end": trial_end, "cancel_at_period_end": False,
            "items": {"data": [{"price": {"id": f"price_{sub_id}"}, "current_period_end": 1900000000}]}}


def _stripe_holds(monkeypatch, snapshots, *, failure_for=None, failure=None, status_code=200):
    """Answer each subscription read by the ID it asks for (``snapshots`` maps it to Stripe's answer), through
    the real StripeClient/RequestsClient; return the IDs read in order, the session and the transport calls."""
    read = []

    def request(method, url, **_):
        sub_id = url.rsplit("/", 1)[-1]
        read.append(sub_id)
        if sub_id == failure_for:
            if failure is not None:
                raise failure
            body = {"error": {"message": "provider unavailable", "type": "api_error"}}
            return SimpleNamespace(content=json.dumps(body).encode(), status_code=status_code, headers={})
        return SimpleNamespace(content=json.dumps(snapshots[sub_id]).encode(), status_code=200, headers={})

    session = SimpleNamespace(request=Mock(side_effect=request), close=Mock())
    real_transport, real_client = reader.stripe.RequestsClient, reader.stripe.StripeClient
    transport_calls = []

    def make_transport(**kwargs):
        transport_calls.append(kwargs)
        return real_transport(session=session, **kwargs)

    client_spy = Mock(side_effect=real_client)
    monkeypatch.setattr(reader.stripe, "RequestsClient", make_transport)
    monkeypatch.setattr(reader.stripe, "StripeClient", client_spy)
    return read, session, transport_calls, client_spy


def _bind(billing, sub_id, status):
    """The account's binding as the local row and the User mirror hold it after its own events."""
    engine, user_id = billing
    with Session(engine) as db:
        user = db.get(User, user_id)
        user.subscription.stripe_subscription_id = user.stripe_subscription_id = sub_id
        user.subscription.status = status
        user.subscription.plan = "pro" if status in ("active", "trialing") else "free"
        user.is_pro = status in ("active", "trialing")
        db.commit()


def _delivery(user_id, sub_id, status="active", *, event_id="evt_cross", kind="customer.subscription.updated", **fields):
    payload = _event(user_id, status, kind, id=sub_id, **fields)
    return {**payload, "id": event_id}


@pytest.mark.asyncio
@pytest.mark.parametrize("a_status", ["canceled", "unpaid", "past_due", "incomplete_expired", "elapsed_trial"])
@pytest.mark.parametrize("b_status", ["incomplete", "incomplete_expired", "canceled"])
async def test_a_stale_old_event_cannot_restore_the_old_binding_or_pro(billing, monkeypatch, a_status, b_status):
    """A recorded A-to-B binding, then old A's "active" update delivered late while Stripe holds A as ended,
    unpaid or past its trial and B never became active: B stays bound and the account stays Free (E98 (1))."""
    _bind(billing, "sub_b", b_status)
    a = (_sub("sub_a", "trialing", 1000, trial_end=1000000000) if a_status == "elapsed_trial"
         else _sub("sub_a", a_status, 1000))
    read, _, _, _ = _stripe_holds(monkeypatch, {"sub_a": a, "sub_b": _sub("sub_b", b_status, 2000)})
    before = _state(billing)

    assert await _deliver(_delivery(billing[1], "sub_a", "active")) == {"status": "success"}

    assert _state(billing) == before[:5] + (1,)  # binding, plan, mirror and row unchanged; the event recorded
    assert (before[0], before[2]) == ("free", "sub_b")
    assert read == ["sub_b", "sub_a"]
    worker.capture_event.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("bound,candidate,winner,plan", [
    pytest.param(_sub("sub_b", "incomplete", 2000), _sub("sub_a", "active", 1000), "sub_a", "pro",
                 id="old_still_billed_rebinds"),
    pytest.param(_sub("sub_b", "active", 2000), _sub("sub_a", "past_due", 1000), "sub_b", "pro",
                 id="active_replacement_kept"),
    pytest.param(_sub("sub_a", "past_due", 1000), _sub("sub_b", "incomplete", 2000), "sub_b", "free",
                 id="resubscribe_newer_inactive_binds"),
    pytest.param(_sub("sub_a", "active", 1000), _sub("sub_b", "active", 2000), "sub_b", "pro", id="newer_of_two_live"),
    pytest.param(_sub("sub_b", "active", 2000), _sub("sub_a", "active", 1000), "sub_b", "pro",
                 id="older_of_two_live_ignored"),
    pytest.param(_sub("sub_a", "active", 1000), _sub("sub_b", "active", 1000), "sub_b", "pro",
                 id="same_second_higher_id"),
])
async def test_another_subscription_takes_the_binding_only_when_stripe_ranks_it_first(
        billing, monkeypatch, bound, candidate, winner, plan):
    """The payload always claims "active"; only Stripe's state decides, and the winner is written as Stripe
    holds it (its status and price). A losing candidate writes nothing, the bound row included. This
    supersedes the cross-ID no-read scope of test_outside_current_id_scope_preserves_existing_behavior_without_read."""
    _bind(billing, bound["id"], bound["status"])
    read, _, _, _ = _stripe_holds(monkeypatch, {bound["id"]: bound, candidate["id"]: candidate})
    before = _state(billing)

    assert await _deliver(_delivery(billing[1], candidate["id"], "active")) == {"status": "success"}

    state = _state(billing)
    assert (state[0], state[2], state[4][1]) == (plan, winner, winner)
    if winner == candidate["id"]:
        assert (state[4][0], state[4][3]) == (candidate["status"], f"price_{candidate['id']}")
    else:
        assert state[:5] == before[:5]
    assert read == [bound["id"], candidate["id"]]


@pytest.mark.asyncio
async def test_a_stranded_entitled_row_heals_on_the_replacements_event(billing, monkeypatch):
    """The old bug's leftover: the local row holds A as active while Stripe has A canceled, and replacement B
    never activated. B's next event is ranked on Stripe's state of both, not the stale row, so B binds and
    the unpaid Pro ends."""
    _bind(billing, "sub_a", "active")
    _stripe_holds(monkeypatch, {"sub_a": _sub("sub_a", "canceled", 1000),
                                "sub_b": _sub("sub_b", "incomplete_expired", 2000)})

    assert await _deliver(_delivery(billing[1], "sub_b", "incomplete_expired")) == {"status": "success"}

    state = _state(billing)
    assert (state[0], state[1], state[2], state[4][0]) == ("free", False, "sub_b", "incomplete_expired")


@pytest.mark.asyncio
async def test_a_stale_old_event_after_the_replacements_deletion_cannot_rebind(billing, monkeypatch):
    """B's deletion (its own ID, no read) clears the mirror and keeps B on the row; old A's late "active"
    update is then ranked against B, both canceled at Stripe, and changes nothing."""
    _bind(billing, "sub_b", "active")
    read, _, _, _ = _stripe_holds(monkeypatch, {"sub_a": _sub("sub_a", "canceled", 1000),
                                                "sub_b": _sub("sub_b", "canceled", 2000)})
    deletion = _delivery(billing[1], "sub_b", event_id="evt_b_deleted", kind="customer.subscription.deleted")
    assert await _deliver(deletion) == {"status": "success"}
    assert read == []
    after_deletion = _state(billing)

    assert await _deliver(_delivery(billing[1], "sub_a", "active")) == {"status": "success"}

    assert _state(billing) == after_deletion[:5] + (2,)
    assert (after_deletion[0], after_deletion[2], after_deletion[4][:2]) == ("free", None, ("canceled", "sub_b"))
    assert read == ["sub_b", "sub_a"]


@pytest.mark.asyncio
async def test_a_cross_subscription_event_on_a_mirror_only_binding_writes_one_row(billing, monkeypatch):
    """With the binding on the User mirror alone, the winner is written once: no second pending row, which
    the unique user_id would refuse."""
    engine, user_id = billing
    with Session(engine) as db:
        user = db.get(User, user_id)
        db.delete(user.subscription)
        user.stripe_subscription_id, user.is_pro = "sub_a", False
        db.commit()
    _stripe_holds(monkeypatch, {"sub_a": _sub("sub_a", "canceled", 1000), "sub_b": _sub("sub_b", "active", 2000)})

    assert await _deliver(_delivery(user_id, "sub_b", "active")) == {"status": "success"}

    with Session(engine) as db:
        assert db.query(Subscription).filter(Subscription.user_id == user_id).count() == 1
    assert _state(billing)[:3] == ("pro", True, "sub_b")


@pytest.mark.asyncio
@pytest.mark.parametrize("side", ["bound", "candidate"])
@pytest.mark.parametrize("changes", [
    {"customer": "cus_other"}, {"created": None}, {"created": 0}, {"created": True}, {"created": "1000"},
    {"created": 10**18}, {"status": "future_unknown_status"}, {"id": "sub_other"},
], ids=["other_customer", "no_created", "zero_created", "bool_created", "text_created", "huge_created",
        "unknown_status", "other_id"])
async def test_a_malformed_or_foreign_snapshot_of_either_subscription_retries_without_change(
        billing, monkeypatch, side, changes):
    """Either read answering for another customer or with a snapshot that cannot be ranked leaves the event
    retryable and unrecorded, with no write to the row or the mirror (E98 (1), (2)); a failed bound read
    never reads the candidate."""
    _bind(billing, "sub_b", "incomplete")
    snapshots = {"sub_b": _sub("sub_b", "incomplete", 2000), "sub_a": _sub("sub_a", "active", 1000)}
    target = "sub_b" if side == "bound" else "sub_a"
    snapshots[target] = {**snapshots[target], **changes}
    read, _, _, _ = _stripe_holds(monkeypatch, snapshots)
    before = _state(billing)

    with pytest.raises(HTTPException) as error:
        await _deliver(_delivery(billing[1], "sub_a", "active"))

    assert error.value.status_code == 503
    assert _state(billing) == before
    assert read == (["sub_b"] if side == "bound" else ["sub_b", "sub_a"])
    worker.capture_event.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("side", ["bound", "candidate"])
@pytest.mark.parametrize("failure,status_code", [
    (requests.exceptions.Timeout("read timed out"), 200),
    (requests.exceptions.ConnectionError("connection failed"), 200),
    (None, 429), (None, 500), (None, 404),
])
async def test_a_provider_failure_on_either_read_retries_without_change(
        billing, monkeypatch, side, failure, status_code):
    """Each read makes one attempt on its own bounded transport, closed on every outcome; a failure leaves
    the event retryable and unrecorded with nothing written (E98 (2), (3))."""
    monkeypatch.setattr(settings, "STRIPE_RECONCILIATION_CONNECT_TIMEOUT_SECONDS", 1.25)
    monkeypatch.setattr(settings, "STRIPE_RECONCILIATION_READ_TIMEOUT_SECONDS", 2.5)
    _bind(billing, "sub_b", "incomplete")
    read, session, transport_calls, client_spy = _stripe_holds(
        monkeypatch, {"sub_b": _sub("sub_b", "incomplete", 2000), "sub_a": _sub("sub_a", "active", 1000)},
        failure_for="sub_b" if side == "bound" else "sub_a", failure=failure, status_code=status_code)
    before = _state(billing)

    with pytest.raises(HTTPException) as error:
        await _deliver(_delivery(billing[1], "sub_a", "active"))

    assert error.value.status_code == 503
    assert _state(billing) == before
    assert read == (["sub_b"] if side == "bound" else ["sub_b", "sub_a"])
    assert transport_calls == [{"timeout": (1.25, 2.5)}] * len(read)
    assert [call.kwargs["max_network_retries"] for call in client_spy.call_args_list] == [0] * len(read)
    assert session.close.call_count == len(read)
    worker.capture_event.assert_not_called()


@pytest.mark.asyncio
async def test_a_duplicate_cross_subscription_event_reads_nothing(billing, monkeypatch):
    _bind(billing, "sub_b", "incomplete")
    read, session, _, _ = _stripe_holds(monkeypatch, {"sub_b": _sub("sub_b", "incomplete", 2000),
                                                      "sub_a": _sub("sub_a", "active", 1000)})
    payload = _delivery(billing[1], "sub_a", "active")
    assert await _deliver(payload) == {"status": "success"}
    state = _state(billing)
    session.request.side_effect = AssertionError("duplicate contacted Stripe")

    assert await _deliver(payload) == {"status": "success", "idempotent": True}

    assert _state(billing) == state
    assert read == ["sub_b", "sub_a"]


@pytest.mark.asyncio
async def test_a_cross_subscription_future_trial_records_one_trial_start(billing, monkeypatch):
    """A newer subscription's created(trialing) that takes the binding records one trial start with Stripe's
    trial_end, not the payload's; its redelivery records none (E98 (5))."""
    future = int(utcnow().timestamp()) + 30 * 86400
    _bind(billing, "sub_a", "canceled")
    _stripe_holds(monkeypatch, {"sub_a": _sub("sub_a", "canceled", 1000),
                                "sub_b": _sub("sub_b", "trialing", 2000, trial_end=future)})
    payload = _delivery(billing[1], "sub_b", "trialing", kind="customer.subscription.created", trial_end=1)

    assert await _deliver(payload) == {"status": "success"}
    assert await _deliver(payload) == {"status": "success", "idempotent": True}

    worker.capture_event.assert_called_once_with(
        str(billing[1]), EVENT_TRIAL_STARTED, {"source": "stripe", "trial_end": future})
