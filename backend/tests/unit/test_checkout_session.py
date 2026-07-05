"""
Unit tests for POST /api/subscriptions/create-checkout-session (closed beta).

Two guarantees underpin the no-credit-card beta flow:
- ``payment_method_collection="if_required"`` is always set, so when a 100%-off promo zeroes the
  amount due, Checkout collects no card. A paying customer with a non-zero total still gets a card.
- The 100%-off promo is applied ONLY for a user whose ``is_beta`` flag is set — which is written
  server-side at invite redemption (Week 2), never from a request parameter. So a non-beta user (or
  anyone flipping a stray query param) gets no discount, and Stripe never sees a conflicting
  ``allow_promotion_codes`` + ``discounts`` pair.

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


def _user(**overrides):
    base = dict(id=1, email="beta@example.com", email_verified=True, stripe_customer_id="cus_test")
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    """Default: a verified, non-beta user with an existing Stripe customer + a resolvable price id."""
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_db] = lambda: MagicMock()
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


def test_non_beta_user_gets_no_discount(client, monkeypatch):
    """A non-beta user gets no promo applied — even with a promo configured."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert "discounts" not in kwargs
    assert "allow_promotion_codes" not in kwargs


def test_stray_query_param_cannot_self_grant_discount(client, monkeypatch):
    """A non-beta user passing the removed apply_beta_promo=true must still get no discount —
    eligibility is server-side only (regression guard for the Week-1 self-grant hole)."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    kwargs = _create_and_capture(
        client, price_id="price_monthly_test", apply_beta_promo=True
    )
    assert "discounts" not in kwargs


def test_beta_user_gets_promo_preapplied(client, monkeypatch):
    """A beta-eligible user (server-set is_beta) gets the 100%-off promo pre-applied via discounts."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    app.dependency_overrides[get_current_user] = lambda: _user(id=2, is_beta=True)
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs["discounts"] == [{"promotion_code": "promo_beta_123"}]
    assert "allow_promotion_codes" not in kwargs  # never both — Stripe 400s otherwise


def test_beta_user_no_discount_when_promo_unconfigured(client, monkeypatch):
    """A beta user with no promo id configured falls back to a normal (paid) checkout, not a 500."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "")
    app.dependency_overrides[get_current_user] = lambda: _user(id=3, is_beta=True)
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
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


def test_beta_promo_id_rejects_coupon_id():
    """A coupon id ('co_…') or raw code is the common misconfig — reject it at config load."""
    with pytest.raises(ValidationError):
        Settings(STRIPE_BETA_PROMO_CODE_ID="co_123abc")


def test_beta_promo_id_accepts_promo_id_and_empty():
    """A 'promo_…' Promotion Code id is valid; empty (feature off) is valid."""
    assert Settings(STRIPE_BETA_PROMO_CODE_ID="promo_123").STRIPE_BETA_PROMO_CODE_ID == "promo_123"
    assert Settings(STRIPE_BETA_PROMO_CODE_ID="").STRIPE_BETA_PROMO_CODE_ID == ""


def test_unknown_price_id_is_rejected_with_400(client):
    """Allowlist negative path: an unsupported price_id → 400 (guards ``_resolve_price_id`` → None).

    Promoted into the Wave 0 anchor set (PR #546 review): the deleted orphan
    ``test_security_controls.py`` was the only test covering this rejection, so loosening the
    allowlist would otherwise ship silently. The autouse fixture provides a verified user with a
    Stripe customer; conftest sets ``STRIPE_SECRET_KEY``, so the endpoint reaches the price check
    rather than the not-configured 500.
    """
    resp = client.post(
        "/api/subscriptions/create-checkout-session",
        params={"price_id": "price_not_on_the_allowlist"},
    )
    assert resp.status_code == 400
    assert "Invalid price_id" in resp.json()["detail"]
