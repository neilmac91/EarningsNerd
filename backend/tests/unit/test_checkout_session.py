"""
Unit tests for POST /api/subscriptions/create-checkout-session (closed-beta, roadmap Week 1).

Week 1 ships only the no-card *lever*:
- ``payment_method_collection="if_required"`` is always set, so when the Week 2 invite flow applies
  a 100%-off promo and the amount due is $0, Checkout collects no card. A paying customer with a
  non-zero total still gets a card field.
- The promo itself is NOT applied here. Doing so from a client parameter would let any authenticated
  user self-grant free Pro; it is deferred to the Week 2 invite flow where it is gated on the user's
  beta eligibility server-side. So the session must carry NEITHER ``discounts`` nor
  ``allow_promotion_codes`` yet.

The endpoint is mocked at the Stripe boundary; we assert on the kwargs passed to
``stripe.checkout.Session.create`` — no network, no DB (the test user already has a Stripe customer
id, so the Customer.create + db.commit branch is skipped).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from main import app
from app.config import Settings, settings
from app.database import get_db
from app.routers.auth import get_current_user
from app.services.entitlements import Plan, get_entitlements, is_pro_user


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    """Inject a verified user with an existing Stripe customer and a resolvable price id."""
    user = SimpleNamespace(
        id=1,
        email="beta@example.com",
        email_verified=True,
        stripe_customer_id="cus_test",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    # conftest sets the Stripe secret/webhook keys but no price id; make "price_monthly_test" resolve.
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    yield
    app.dependency_overrides.clear()


def _create_and_capture(client, **params):
    """Call the endpoint with Stripe mocked; return the kwargs passed to Session.create."""
    session = MagicMock(url="https://checkout.stripe.test/session")
    with patch(
        "app.routers.subscriptions.stripe.Customer.retrieve",
        return_value=SimpleNamespace(id="cus_test"),
    ), patch(
        "app.routers.subscriptions.stripe.checkout.Session.create",
        return_value=session,
    ) as create:
        resp = client.post("/api/subscriptions/create-checkout-session", params=params)
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == "https://checkout.stripe.test/session"
    create.assert_called_once()
    return create.call_args.kwargs


def test_payment_method_collection_is_if_required(client):
    """The no-card lever is set on every subscription session."""
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs["payment_method_collection"] == "if_required"
    assert kwargs["mode"] == "subscription"


def test_no_promo_is_applied_in_week1(client):
    """Promo application is deferred to the Week 2 eligibility-gated path, so neither promo param is
    present yet — there is no way for a client to trigger the discount."""
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert "discounts" not in kwargs
    assert "allow_promotion_codes" not in kwargs


def test_apply_beta_promo_param_is_not_honored(client):
    """A stray ``apply_beta_promo=true`` (the removed param) must NOT apply any discount — it is an
    unknown query param now and is ignored, leaving the session promo-free."""
    kwargs = _create_and_capture(
        client, price_id="price_monthly_test", apply_beta_promo=True
    )
    assert "discounts" not in kwargs
    assert "allow_promotion_codes" not in kwargs


def test_zero_dollar_active_subscription_resolves_to_pro():
    """A 100%-off subscription is ``status='active'`` like any paid one — entitlements grant Pro on
    status alone (no amount floor), so the beta cohort gets full Pro with no further changes."""
    user = SimpleNamespace(
        is_pro=False,
        subscription=SimpleNamespace(status="active", trial_end=None),
    )
    ent = get_entitlements(user)
    assert ent.plan is Plan.PRO
    assert ent.monthly_summary_limit is None  # unlimited summaries
    assert ent.copilot is True
    assert is_pro_user(user) is True


def test_beta_promo_id_rejects_coupon_id():
    """A coupon id ('co_…') or raw code is the common misconfig — reject it at config load."""
    with pytest.raises(ValidationError):
        Settings(STRIPE_BETA_PROMO_CODE_ID="co_123abc")


def test_beta_promo_id_accepts_promo_id_and_empty():
    """A 'promo_…' Promotion Code id is valid; empty (feature off) is valid."""
    assert Settings(STRIPE_BETA_PROMO_CODE_ID="promo_123").STRIPE_BETA_PROMO_CODE_ID == "promo_123"
    assert Settings(STRIPE_BETA_PROMO_CODE_ID="").STRIPE_BETA_PROMO_CODE_ID == ""
