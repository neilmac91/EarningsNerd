"""
Unit tests for POST /api/subscriptions/create-checkout-session (closed-beta, roadmap Week 1).

Two guarantees underpin the no-credit-card beta flow:
- ``payment_method_collection="if_required"`` is ALWAYS set, so a promo that zeroes the amount
  due collects no card (a paying customer with a non-zero total still gets a card field).
- The promo is applied CONDITIONALLY. Stripe rejects a session that sets both
  ``allow_promotion_codes`` and ``discounts`` ("you cannot specify both ..."). The magic-link path
  (``apply_beta_promo=true`` + a configured promo) pre-applies ``discounts``; otherwise
  ``allow_promotion_codes`` lets the customer enter a code manually.

The endpoint is mocked at the Stripe boundary; we assert on the kwargs passed to
``stripe.checkout.Session.create`` — no network, no DB (the test user already has a Stripe
customer id, so the Customer.create + db.commit branch is skipped).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.config import settings
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


def test_payment_method_collection_is_if_required(client, monkeypatch):
    """The no-card lever is set on every session, regardless of path."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs["payment_method_collection"] == "if_required"
    assert kwargs["mode"] == "subscription"


def test_manual_path_allows_promotion_codes(client, monkeypatch):
    """Default checkout lets the customer enter a code; never both parameters together."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs.get("allow_promotion_codes") is True
    assert "discounts" not in kwargs


def test_magic_link_path_preapplies_discount(client, monkeypatch):
    """apply_beta_promo pre-applies the configured promo and never sets allow_promotion_codes."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    kwargs = _create_and_capture(
        client, price_id="price_monthly_test", apply_beta_promo=True
    )
    assert kwargs["discounts"] == [{"promotion_code": "promo_beta_123"}]
    assert "allow_promotion_codes" not in kwargs  # Stripe 400s if both are present


def test_magic_link_without_configured_promo_falls_back_to_manual(client, monkeypatch):
    """Requesting the promo with none configured degrades safely to manual entry."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "")
    kwargs = _create_and_capture(
        client, price_id="price_monthly_test", apply_beta_promo=True
    )
    assert kwargs.get("allow_promotion_codes") is True
    assert "discounts" not in kwargs


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
