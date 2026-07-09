"""
Unit tests for POST /api/subscriptions/create-checkout-session (beta coupon + card-required trial).

Cohort guarantees pinned here:
- Beta ($0 forever coupon): the 100%-off promo is applied ONLY for a user whose ``is_beta`` flag is
  set — written server-side at invite redemption, never from a request parameter — paired with
  ``payment_method_collection="if_required"`` so a zeroed amount collects no card, and NO trial.
- First-time MONTHLY subscriber: a card-required 7-day trial —
  ``subscription_data.trial_period_days`` + ``missing_payment_method: cancel`` +
  ``payment_method_collection="always"`` (with a trial the amount due today is $0, so
  ``if_required`` would skip the card and Stripe could never auto-charge on day 8).
- Everyone else (yearly, repeat subscriber, trial disabled): plain paid checkout with
  ``if_required`` and no ``subscription_data``.

The endpoint is mocked at the Stripe boundary; we assert on the kwargs passed to
``stripe.checkout.Session.create`` — no network, no DB (the test user already has a Stripe customer
id, so the Customer.create + db.commit branch is skipped). The mocked DB's
``query().filter().first()`` stands in for the prior-Subscription lookup: a MagicMock (truthy) means
"has subscribed before" (the autouse default), ``None`` means "first-time subscriber".
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


def _use_first_time_subscriber_db():
    """Swap the mocked DB for one whose prior-Subscription lookup returns None — the endpoint then
    sees a first-time subscriber (trial-eligible)."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    app.dependency_overrides[get_db] = lambda: db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    """Default: a verified, non-beta user with an existing Stripe customer + a resolvable price id.
    The bare MagicMock DB returns a truthy ``query().filter().first()`` — i.e. a PRIOR Subscription
    row exists, so the default cohort is a repeat subscriber (no trial)."""
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


def test_repeat_subscriber_gets_plain_checkout(client):
    """A repeat subscriber (prior Subscription row exists — the autouse default) gets no trial and
    keeps the ``if_required`` no-card lever (Stripe still collects a card on a non-zero total)."""
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs["payment_method_collection"] == "if_required"
    assert kwargs["mode"] == "subscription"
    assert "subscription_data" not in kwargs  # no trial for a repeat subscriber


def test_first_time_monthly_subscriber_gets_card_required_trial(client):
    """The trial cohort: first-time subscriber + monthly price + PRO_TRIAL_DAYS>0 →
    trial_period_days with the missing-card cancel backstop, and the card is ALWAYS collected —
    with a trial the amount due today is $0, so ``if_required`` would skip the card and Stripe
    could never auto-charge at trial end."""
    _use_first_time_subscriber_db()
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs["subscription_data"] == {
        "trial_period_days": settings.PRO_TRIAL_DAYS,
        "trial_settings": {"end_behavior": {"missing_payment_method": "cancel"}},
    }
    assert kwargs["payment_method_collection"] == "always"


def test_yearly_checkout_gets_no_trial(client, monkeypatch):
    """The trial is monthly-only: a first-time subscriber on the YEARLY price gets a plain paid
    checkout (no subscription_data, if_required)."""
    monkeypatch.setattr(settings, "STRIPE_PRICE_YEARLY_ID", "price_yearly_test")
    _use_first_time_subscriber_db()
    kwargs = _create_and_capture(client, price_id="price_yearly_test")
    assert "subscription_data" not in kwargs
    assert kwargs["payment_method_collection"] == "if_required"


def test_trial_disabled_when_pro_trial_days_zero(client, monkeypatch):
    """PRO_TRIAL_DAYS=0 turns the trial off entirely — even a first-time monthly subscriber gets a
    plain paid checkout."""
    monkeypatch.setattr(settings, "PRO_TRIAL_DAYS", 0)
    _use_first_time_subscriber_db()
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert "subscription_data" not in kwargs
    assert kwargs["payment_method_collection"] == "if_required"


def test_beta_user_gets_coupon_not_trial(client, monkeypatch):
    """Cohorts are mutually exclusive: a beta user (even a first-time monthly subscriber) gets the
    $0-forever coupon path — no trial, and ``if_required`` so no card is collected on a $0 total."""
    monkeypatch.setattr(settings, "STRIPE_BETA_PROMO_CODE_ID", "promo_beta_123")
    app.dependency_overrides[get_current_user] = lambda: _user(id=4, is_beta=True)
    _use_first_time_subscriber_db()
    kwargs = _create_and_capture(client, price_id="price_monthly_test")
    assert kwargs["discounts"] == [{"promotion_code": "promo_beta_123"}]
    assert "subscription_data" not in kwargs
    assert kwargs["payment_method_collection"] == "if_required"


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
