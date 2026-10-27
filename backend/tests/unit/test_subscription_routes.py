"""The subscription routes' database reads and the checkout's customer-id write, on a real database.

``test_checkout_session.py`` pins checkout's Stripe kwargs with a mocked session. This file pins
what that mock cannot:

- ``GET /api/subscriptions/subscription`` serves the reader's own ``subscriptions`` row (never
  another user's), and the ``User`` mirror when there is none.
- Checkout's first-time-trial check counts only the reader's own row, of any status.
- A user with no Stripe customer gets one, and checkout commits its id before the checkout session
  is created, so a Stripe failure after that point still keeps the customer; no other account's
  customer changes.
- Two checkouts of one account that each found no customer check out with the one stored first,
  never one written over it (E166), and an account deleted while checkout creates its customer gets
  no checkout session.
- Checkout's plan comes from the reader's own row when there is one, not the ``is_pro`` mirror (E144).
- A Stripe failure in checkout or the billing portal answers the route's fixed 400 detail and logs its
  error's class and Stripe's request id alone: Stripe's message, which can quote the key's last four
  characters or name a customer, reaches neither the answer nor a log (E18).

The reader is loaded through the request's own ``get_db`` session, as ``get_current_user`` does, so
checkout's first unit reads it, and the row its plan loads, on that session and releases the session
before any Stripe call, as in production.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Callable
from unittest.mock import MagicMock, patch

import httpx
import pytest
import stripe
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Subscription, User
from app.routers.auth import get_current_user
from app.services import legal_readiness_service
from main import app

PERIOD_END = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
CHECKOUT_FAILED = "Nothing was charged. Try again in a moment."
PORTAL_FAILED = "The billing portal could not open. Try again in a moment."


@pytest.fixture(autouse=True)
def _tables(monkeypatch):
    # Exercise the existing billing contracts behind the separately tested launch hold.
    monkeypatch.setattr(legal_readiness_service, "is_checkout_available", lambda: True)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _new_user(*, stripe_customer_id: str | None = "cus_user", **fields) -> str:
    email = f"sub-{uuid.uuid4().hex[:10]}@example.com"
    with SessionLocal() as db:
        db.add(User(email=email, email_verified=True, stripe_customer_id=stripe_customer_id, **fields))
        db.commit()
    return email


def _add_subscription(email: str, **fields) -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).one()
        db.add(Subscription(user_id=user.id, **fields))
        db.commit()


def _sign_in(email: str) -> None:
    """``get_current_user``'s shape: the reader comes from the request's own ``get_db`` session."""

    def current_user(db: Session = Depends(get_db)) -> User:
        return db.query(User).filter(User.email == email).one()

    app.dependency_overrides[get_current_user] = current_user


def _stored_customer_id(email: str) -> str | None:
    with SessionLocal() as db:
        return db.query(User.stripe_customer_id).filter(User.email == email).scalar()


def test_status_without_a_row_serves_the_user_mirror(client):
    email = _new_user(stripe_customer_id="cus_mirror", stripe_subscription_id="sub_mirror")
    _sign_in(email)

    resp = client.get("/api/subscriptions/subscription")

    assert resp.status_code == 200
    assert resp.json() == {
        "is_pro": False, "stripe_customer_id": "cus_mirror", "stripe_subscription_id": "sub_mirror",
        "subscription_status": None, "plan": "free", "status": None, "trial_end": None,
        "current_period_end": None, "cancel_at_period_end": False,
    }


def test_status_serves_the_readers_own_row(client):
    email = _new_user(stripe_customer_id="cus_mirror", stripe_subscription_id="sub_mirror")  # the row wins over both
    _add_subscription(
        email, plan="pro", status="active", stripe_customer_id="cus_row", stripe_subscription_id="sub_row",
        current_period_end=PERIOD_END, cancel_at_period_end=True,
    )
    _sign_in(email)

    body = client.get("/api/subscriptions/subscription").json()

    assert body["current_period_end"].startswith("2030-01-02T03:04:05")
    del body["current_period_end"]
    assert body == {
        "is_pro": True, "stripe_customer_id": "cus_row", "stripe_subscription_id": "sub_row",
        "subscription_status": "active", "plan": "pro", "status": "active", "trial_end": None,
        "cancel_at_period_end": True,
    }


def test_status_never_serves_another_users_row(client):
    other = _new_user(stripe_customer_id="cus_other")
    _add_subscription(other, plan="pro", status="active", stripe_customer_id="cus_other_row",
                      stripe_subscription_id="sub_other_row")
    reader = _new_user(stripe_customer_id="cus_reader")
    _sign_in(reader)

    body = client.get("/api/subscriptions/subscription").json()

    assert (body["stripe_customer_id"], body["stripe_subscription_id"], body["status"]) == ("cus_reader", None, None)


def _retrieved(customer_id):
    """``Customer.retrieve`` as stripe-python answers it: an id that is not a string is refused before any
    request, so a checkout that retrieves a customer it has not got answers 400, as in production."""
    if not isinstance(customer_id, str):
        raise stripe.error.InvalidRequestError(f"Customer instance has invalid ID: {customer_id!r}", "id")
    return SimpleNamespace(id=customer_id)


def _checkout(client, monkeypatch, *, session_error: Exception | None = None,
              customer_created: Callable[..., SimpleNamespace] | None = None):
    """Post a monthly checkout with Stripe mocked; return (response, Customer.create, Session.create).
    ``customer_created``, when given, runs as ``Customer.create`` and returns its customer."""
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    monkeypatch.setattr(settings, "PRO_TRIAL_DAYS", 7)
    session = MagicMock(url="https://checkout.stripe.test/session")
    with patch.object(stripe.Customer, "create", return_value=SimpleNamespace(id="cus_new"),
                      side_effect=customer_created) as create_customer, \
            patch.object(stripe.Customer, "retrieve", side_effect=_retrieved), \
            patch.object(stripe.checkout.Session, "create", return_value=session,
                         side_effect=session_error) as create_session:
        resp = client.post("/api/subscriptions/create-checkout-session", params={"price_id": "monthly"})
    return resp, create_customer, create_session


@pytest.mark.parametrize("prior", [None, "canceled", "another user's active row"])
def test_the_first_time_trial_counts_only_the_readers_own_row_of_any_status(client, monkeypatch, prior):
    if prior == "another user's active row":
        _add_subscription(_new_user(), plan="pro", status="active")
    email = _new_user()
    if prior == "canceled":
        _add_subscription(email, plan="pro", status="canceled")
    _sign_in(email)

    resp, _, create_session = _checkout(client, monkeypatch)

    assert resp.status_code == 200, resp.text
    trial = create_session.call_args.kwargs.get("subscription_data")
    assert (trial is not None) is (prior != "canceled"), trial


def test_checkout_creates_and_stores_a_missing_stripe_customer(client, monkeypatch):
    email = _new_user(stripe_customer_id=None)
    bystander = _new_user(stripe_customer_id=None)
    _sign_in(email)

    resp, create_customer, create_session = _checkout(client, monkeypatch)

    assert resp.status_code == 200, resp.text
    create_customer.assert_called_once()
    assert create_customer.call_args.kwargs["email"] == email
    assert create_session.call_args.kwargs["customer"] == "cus_new"
    assert _stored_customer_id(email) == "cus_new"
    assert _stored_customer_id(bystander) is None  # the claim writes the reader's row alone


def test_the_customer_id_is_committed_before_the_checkout_session_is_created(client, monkeypatch):
    email = _new_user(stripe_customer_id=None)
    _sign_in(email)

    resp, _, _ = _checkout(client, monkeypatch, session_error=stripe.error.APIConnectionError("checkout down"))

    assert resp.status_code == 400
    assert resp.json() == {"detail": CHECKOUT_FAILED}
    assert _stored_customer_id(email) == "cus_new"  # the next attempt reuses this customer


# What Stripe's messages can say: a masked key's last four characters ("Zq9X") and a customer's id. Built at run
# time, so no secret scanner reads a key in this file.
_KEY_TAIL = "Zq9X"
_PROVIDER_TEXT = f"Invalid API Key provided: {'sk_' + 'live_'}{'*' * 20}{_KEY_TAIL}. No such customer: 'cus_planted'"
_LEAKS = (_KEY_TAIL, "sk_live", "cus_planted", "Invalid API Key", "No such customer")

_STRIPE_FAILURES = [
    pytest.param(lambda: stripe.error.AuthenticationError(_PROVIDER_TEXT, http_status=401,
                                                          headers={"request-id": "req_E18auth"}),
                 "AuthenticationError", "req_E18auth", id="invalid-key"),
    pytest.param(lambda: stripe.error.InvalidRequestError(_PROVIDER_TEXT, "customer", code="resource_missing",
                                                          http_status=404, headers={"request-id": "req_E18miss"}),
                 "InvalidRequestError", "req_E18miss", id="no-such-customer"),
    pytest.param(lambda: stripe.error.APIConnectionError(_PROVIDER_TEXT), "APIConnectionError", "unknown",
                 id="no-answer"),
    # A request id is provider text too: one of another shape is left out.
    pytest.param(lambda: stripe.error.RateLimitError(_PROVIDER_TEXT, http_status=429,
                                                     headers={"request-id": f"req_{_KEY_TAIL} {_PROVIDER_TEXT}"}),
                 "RateLimitError", "unknown", id="request-id-of-another-shape"),
]


@pytest.mark.parametrize("route", ["checkout", "portal"])
@pytest.mark.parametrize("error,error_class,request_id", _STRIPE_FAILURES)
def test_a_stripe_failure_answers_a_fixed_detail_and_logs_its_class_and_request_id_alone(
        client, monkeypatch, caplog, route, error, error_class, request_id):
    """Stripe's message can quote the key's last four characters or name a customer: the route answers its
    fixed 400 detail, and its one log line names the call, the error's class and Stripe's request id, no
    account, customer or provider text (E18). Each record is read whole (its message, arguments, extra
    fields and exception), as the production formatters and Sentry's logging integration read it, since
    ``caplog.text`` renders the message alone."""
    email = _new_user(stripe_customer_id="cus_existing")
    _sign_in(email)
    caplog.set_level(logging.DEBUG)

    if route == "checkout":
        resp, _, _ = _checkout(client, monkeypatch, session_error=error())
        call, detail = "Checkout", CHECKOUT_FAILED
    else:
        with patch.object(stripe.billing_portal.Session, "create", side_effect=error()):
            resp = client.post("/api/subscriptions/create-portal-session")
        call, detail = "Billing portal", PORTAL_FAILED

    assert resp.status_code == 400
    assert resp.json() == {"detail": detail}
    records = [repr(vars(record)) for record in caplog.records]
    for leak in _LEAKS:
        assert leak not in resp.text
        assert not [record for record in records if leak in record]
    [line] = [r.getMessage() for r in caplog.records if r.name == "app.routers.subscriptions"]
    assert line == f"{call} failed at Stripe ({error_class}, request {request_id})"


def test_an_existing_customer_is_retrieved_not_recreated(client, monkeypatch):
    email = _new_user(stripe_customer_id="cus_existing")
    _sign_in(email)

    resp, create_customer, create_session = _checkout(client, monkeypatch)

    assert resp.status_code == 200, resp.text
    create_customer.assert_not_called()
    assert create_session.call_args.kwargs["customer"] == "cus_existing"
    assert _stored_customer_id(email) == "cus_existing"


def test_a_customer_another_checkout_stored_first_stays_and_is_checked_out_with(client, monkeypatch):
    """Another checkout of the account stores its customer after this request's lookup read none. That
    customer stays, and this checkout's session uses it: written over, the other session would name a
    customer the account no longer holds, and a payment through it would be refused (E166)."""
    email = _new_user(stripe_customer_id=None)
    _sign_in(email)

    def stored_first_by_another_checkout(**_):
        with SessionLocal() as db:
            db.query(User).filter(User.email == email).update({User.stripe_customer_id: "cus_first"})
            db.commit()
        return SimpleNamespace(id="cus_new")

    resp, create_customer, create_session = _checkout(client, monkeypatch,
                                                      customer_created=stored_first_by_another_checkout)

    assert resp.status_code == 200, resp.text
    create_customer.assert_called_once()
    assert create_session.call_args.kwargs["customer"] == "cus_first"
    assert _stored_customer_id(email) == "cus_first"


def test_a_checkout_whose_account_is_deleted_while_its_customer_is_created_opens_no_session(client, monkeypatch):
    """The account is deleted (from another tab) while checkout creates its customer, so the claim
    finds no account: checkout answers 500, as when it read the deleted row, and creates no checkout
    session."""
    email = _new_user(stripe_customer_id=None)
    _sign_in(email)

    def account_deleted_meanwhile(**_):
        with SessionLocal() as db:
            db.query(User).filter(User.email == email).delete()
            db.commit()
        return SimpleNamespace(id="cus_new")

    resp, create_customer, create_session = _checkout(client, monkeypatch, customer_created=account_deleted_meanwhile)

    assert resp.status_code == 500
    assert resp.json()["detail"] == "Checkout is not available right now."
    create_customer.assert_called_once()
    create_session.assert_not_called()


@pytest.mark.parametrize("row,mirror,answer", [
    ({"status": "active"}, False, 409),
    ({"status": "trialing", "trial_end": datetime.now(timezone.utc) - timedelta(days=3)}, True, 200),
], ids=["active-row-mirror-free", "lapsed-trial-mirror-pro"])
def test_checkout_reads_the_plan_from_the_readers_row_not_its_mirror(client, monkeypatch, row, mirror, answer):
    """Checkout reads the plan in its first unit, while the reader is in the request's session, so the
    reader's own row decides it. Read after the release, the detached reader's row would not load and
    the plan would fall back to the ``is_pro`` mirror (E144). An active row whose mirror reads Free is
    refused a second checkout (#619's double billing), and a lapsed trial whose mirror still reads Pro
    checks out, with no second trial."""
    email = _new_user(is_pro=mirror)
    _add_subscription(email, plan="pro", **row)
    _sign_in(email)

    resp, _, create_session = _checkout(client, monkeypatch)

    assert resp.status_code == answer, resp.text
    if answer == 409:
        create_session.assert_not_called()
    else:
        assert "subscription_data" not in create_session.call_args.kwargs


@pytest.mark.asyncio
async def test_two_checkouts_whose_lookups_both_read_no_customer_check_out_with_one(monkeypatch):
    """Two checkouts of one account whose auth lookups both read the account before either stores a
    customer (two tabs; a barrier holds each lookup until both have read) each create one, and both
    sessions use the customer stored first, through the real ``get_current_user`` (E166)."""
    from app.routers import auth
    from app.services import auth_account_service

    email = _new_user(stripe_customer_id=None)
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    monkeypatch.setattr(settings, "PRO_TRIAL_DAYS", 7)
    monkeypatch.setattr(app, "dependency_overrides", {})
    both_read = threading.Barrier(2, timeout=10)
    find_user_by_email = auth_account_service.find_user_by_email

    def find_then_wait_for_the_other(db, address):
        user = find_user_by_email(db, address)
        both_read.wait()
        return user

    monkeypatch.setattr(auth_account_service, "find_user_by_email", find_then_wait_for_the_other)
    customers = iter(["cus_1", "cus_2"])
    token = auth.create_access_token({"sub": email})
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    with patch.object(stripe.Customer, "create", side_effect=lambda **_: SimpleNamespace(id=next(customers))) \
            as create_customer, \
            patch.object(stripe.Customer, "retrieve", side_effect=lambda cid: SimpleNamespace(id=cid)), \
            patch.object(stripe.checkout.Session, "create",
                         return_value=MagicMock(url="https://checkout.stripe.test/session")) as create_session:
        async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                     headers={"Authorization": f"Bearer {token}"}) as http:
            responses = await asyncio.gather(*[
                http.post("/api/subscriptions/create-checkout-session", params={"price_id": "monthly"})
                for _ in range(2)])

    assert [response.status_code for response in responses] == [200, 200], [r.text for r in responses]
    assert create_customer.call_count == 2  # each lookup read no customer
    # Whichever claim lands first wins (on the loop, the first body's; off it, either): both sessions use it.
    stored = _stored_customer_id(email)
    assert stored in {"cus_1", "cus_2"}
    assert [call.kwargs["customer"] for call in create_session.call_args_list] == [stored, stored]
