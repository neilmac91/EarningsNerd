"""The subscription routes' database reads and the checkout's customer-id write, on a real database.

``test_checkout_session.py`` pins checkout's Stripe kwargs with a mocked session. This file pins
what that mock cannot:

- ``GET /api/subscriptions/subscription`` serves the reader's own ``subscriptions`` row (never
  another user's), and the ``User`` mirror when there is none.
- Checkout's first-time-trial check counts only the reader's own row, of any status.
- A user with no Stripe customer gets one, and checkout commits its id before the checkout session
  is created, so a Stripe failure after that point still keeps the customer.

The reader is loaded through the request's own ``get_db`` session, as ``get_current_user`` does, so
a write on it rides the route's commit exactly as in production.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import stripe
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Subscription, User
from app.routers.auth import get_current_user
from main import app

PERIOD_END = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _tables():
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
    email = _new_user(stripe_customer_id="cus_mirror")
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


def _checkout(client, monkeypatch, *, session_error: Exception | None = None):
    """Post a monthly checkout with Stripe mocked; return (response, Customer.create, Session.create)."""
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    monkeypatch.setattr(settings, "PRO_TRIAL_DAYS", 7)
    session = MagicMock(url="https://checkout.stripe.test/session")
    with patch.object(stripe.Customer, "create", return_value=SimpleNamespace(id="cus_new")) as create_customer, \
            patch.object(stripe.Customer, "retrieve", side_effect=lambda cid: SimpleNamespace(id=cid)), \
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
    _sign_in(email)

    resp, create_customer, create_session = _checkout(client, monkeypatch)

    assert resp.status_code == 200, resp.text
    create_customer.assert_called_once()
    assert create_customer.call_args.kwargs["email"] == email
    assert create_session.call_args.kwargs["customer"] == "cus_new"
    assert _stored_customer_id(email) == "cus_new"


def test_the_customer_id_is_committed_before_the_checkout_session_is_created(client, monkeypatch):
    email = _new_user(stripe_customer_id=None)
    _sign_in(email)

    resp, _, _ = _checkout(client, monkeypatch, session_error=stripe.error.APIConnectionError("checkout down"))

    assert resp.status_code == 400
    assert resp.json()["detail"].startswith("Stripe error:")
    assert _stored_customer_id(email) == "cus_new"  # the next attempt reuses this customer


def test_an_existing_customer_is_retrieved_not_recreated(client, monkeypatch):
    email = _new_user(stripe_customer_id="cus_existing")
    _sign_in(email)

    resp, create_customer, create_session = _checkout(client, monkeypatch)

    assert resp.status_code == 200, resp.text
    create_customer.assert_not_called()
    assert create_session.call_args.kwargs["customer"] == "cus_existing"
    assert _stored_customer_id(email) == "cus_existing"
