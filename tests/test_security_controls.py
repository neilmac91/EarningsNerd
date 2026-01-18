import os
import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request


os.environ.setdefault("SECRET_KEY", "test-secret-key")


def _load_auth_module():
    module = importlib.import_module("app.routers.auth")
    return importlib.reload(module)


def test_password_policy_enforced():
    auth = _load_auth_module()

    # Valid password should pass
    valid = auth.UserCreate(email="test@example.com", password="StrongPass123", full_name=None)
    assert valid.password == "StrongPass123"

    with pytest.raises(ValueError):
        auth.UserCreate(email="test@example.com", password="short", full_name=None)
    with pytest.raises(ValueError):
        auth.UserCreate(email="test@example.com", password="alllowercase123", full_name=None)
    with pytest.raises(ValueError):
        auth.UserCreate(email="test@example.com", password="ALLUPPERCASE123", full_name=None)
    with pytest.raises(ValueError):
        auth.UserCreate(email="test@example.com", password="NoNumbersHere", full_name=None)


def _make_request(ip: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
        "client": (ip, 1234),
    }
    return Request(scope)


def test_rate_limiter_blocks_after_limit():
    from app.services.rate_limiter import RateLimiter, enforce_rate_limit

    limiter = RateLimiter(limit=1, window_seconds=60)
    request = _make_request()

    # First request should pass
    enforce_rate_limit(request, limiter, "login", error_detail="Too many attempts")

    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit(request, limiter, "login", error_detail="Too many attempts")
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_stripe_price_allowlist_rejects_unknown_price():
    subscriptions = importlib.import_module("app.routers.subscriptions")
    subscriptions.settings.STRIPE_SECRET_KEY = "sk_test_123"
    subscriptions.settings.STRIPE_PRICE_MONTHLY_ID = "price_monthly"
    subscriptions.settings.STRIPE_PRICE_YEARLY_ID = "price_yearly"

    dummy_user = SimpleNamespace(
        id=1,
        email="test@example.com",
        stripe_customer_id=None,
    )

    with pytest.raises(HTTPException) as exc:
        await subscriptions.create_checkout_session(
            price_id="price_invalid",
            current_user=dummy_user,
            db=object(),
        )
    assert exc.value.status_code == 400
