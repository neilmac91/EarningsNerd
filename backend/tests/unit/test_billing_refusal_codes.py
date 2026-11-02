"""Checkout's and the billing portal's refusals, and the one error code among them (E31).

``docs/audit/contracts/error-codes.md`` §3 registers one billing refusal: checkout's unverified-email 403. It answers
its unchanged status and words plus ``"code": "email_verification_required"``, which the browser's verification
prompt opens on (``frontend/lib/api/client.ts``), whatever the words say. Before ``main.py`` registers the handler,
FastAPI's own answer is exactly the uncoded one, so the producer and the registration deploy in either order (§6 (3)).
Every other refusal of the two routes carries no code, its status and words unchanged (§3: no row, no code).

Each request runs through a real ASGI app as a signed-in account, and no refusal reaches Stripe.
"""
from __future__ import annotations

from unittest.mock import Mock
from uuid import uuid4

import pytest
import stripe
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Subscription, User
from app.routers import auth, subscriptions
from app.services import legal_readiness_service
from main import app

VERIFY_FIRST = "Verify your email address before you subscribe."


@pytest.fixture(autouse=True)
def _no_stripe(monkeypatch):
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    for owner, method in ((stripe.Customer, "create"), (stripe.Customer, "retrieve"),
                          (stripe.checkout.Session, "create"), (stripe.billing_portal.Session, "create")):
        monkeypatch.setattr(owner, method, Mock(side_effect=AssertionError("a refusal reached Stripe")))


def _signed_in(*, verified: bool = True, customer_id: str | None = "cus_refused", subscription: str | None = None):
    email = f"billing-code-{uuid4().hex}@example.com"
    with SessionLocal() as db:
        user = User(email=email, email_verified=verified, is_active=True, stripe_customer_id=customer_id)
        db.add(user)
        db.flush()
        if subscription:
            db.add(Subscription(user_id=user.id, plan="pro", status=subscription))
        db.commit()
    return {"Authorization": f"Bearer {auth.create_access_token({'sub': email})}"}


def _checkout(asgi: FastAPI, headers: dict[str, str], price_id: str = "monthly"):
    with TestClient(asgi) as client:
        return client.post("/api/subscriptions/create-checkout-session", params={"price_id": price_id}, headers=headers)


def _without_the_handler() -> FastAPI:
    """The billing routes as they answer before ``main.py`` registers ``coded_http_exception_handler``."""
    bare = FastAPI()
    bare.include_router(subscriptions.router, prefix="/api/subscriptions")
    return bare


@pytest.fixture
def checkout_open(monkeypatch):
    monkeypatch.setattr(legal_readiness_service, "is_checkout_available", lambda: True)


def test_an_unverified_checkout_answers_its_403_and_words_with_the_verification_code(checkout_open):
    response = _checkout(app, _signed_in(verified=False))

    assert response.status_code == 403
    assert response.json() == {"detail": VERIFY_FIRST, "code": "email_verification_required"}


def test_before_the_handler_is_registered_the_unverified_403_answers_as_it_did(checkout_open):
    response = _checkout(_without_the_handler(), _signed_in(verified=False))

    assert (response.status_code, response.json()) == (403, {"detail": VERIFY_FIRST})


@pytest.mark.parametrize("asgi", [app, _without_the_handler()], ids=["registered", "unregistered"])
@pytest.mark.parametrize("refusal,expected", [
    ("closed", (503, "New subscriptions are not available yet. You can still manage existing billing in Settings.")),
    ("entitled", (409, "You already have an active subscription. Manage it from the billing portal.")),
    ("unconfigured", (500, "Checkout is not available right now.")),
    ("unknown price", (400, "That plan is not available. Reload the page and try again.")),
    ("portal without a customer", (400, "No subscription found")),
])
def test_every_other_billing_refusal_keeps_its_answer_and_carries_no_code(monkeypatch, asgi, refusal, expected):
    if refusal != "closed":
        monkeypatch.setattr(legal_readiness_service, "is_checkout_available", lambda: True)
    if refusal == "unconfigured":
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "")
    headers = _signed_in(subscription="active" if refusal == "entitled" else None,
                         customer_id=None if refusal == "portal without a customer" else "cus_refused")

    if refusal == "portal without a customer":
        with TestClient(asgi) as client:
            response = client.post("/api/subscriptions/create-portal-session", headers=headers)
    else:
        response = _checkout(asgi, headers, price_id="lifetime" if refusal == "unknown price" else "monthly")

    status, detail = expected
    assert (response.status_code, response.json()) == (status, {"detail": detail})
