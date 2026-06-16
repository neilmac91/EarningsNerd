"""Unit tests for the auth/security-hardening additions:

- HaveIBeenPwned breached-password screening (k-anonymity, fail-open)
- RateLimiter.is_exhausted (read-only peek)
- Entitlements mapping (plan -> limits)
"""
import asyncio
import hashlib
from types import SimpleNamespace

import pytest

from app.services import pwned_passwords as pwned
from app.services.rate_limiter import RateLimiter
from app.services.entitlements import get_entitlements, Plan, FREE_TIER_SUMMARY_LIMIT


# ── HIBP breached-password screening ─────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    """Stands in for httpx.AsyncClient; returns a canned range-API body (or raises)."""

    def __init__(self, *, body: str | None = None, error: Exception | None = None):
        self._body = body
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._body or "")


def _suffix_for(password: str) -> str:
    return hashlib.sha1(password.encode()).hexdigest().upper()[5:]


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def enable_pwned(monkeypatch):
    monkeypatch.setattr(pwned.settings, "PWNED_PASSWORD_CHECK_ENABLED", True)


def test_pwned_password_detected(monkeypatch, enable_pwned):
    pw = "password123"
    body = f"{_suffix_for(pw)}:42\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:1"
    monkeypatch.setattr(pwned.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient(body=body))
    assert _run(pwned.is_password_pwned(pw)) is True


def test_padding_count_zero_is_not_a_hit(monkeypatch, enable_pwned):
    pw = "password123"
    body = f"{_suffix_for(pw)}:0"  # HIBP Add-Padding decoy
    monkeypatch.setattr(pwned.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient(body=body))
    assert _run(pwned.is_password_pwned(pw)) is False


def test_password_not_in_corpus(monkeypatch, enable_pwned):
    pw = "a-very-unique-passphrase-xyz"
    body = "0000000000000000000000000000000000A:5\n1111111111111111111111111111111111B:9"
    monkeypatch.setattr(pwned.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient(body=body))
    assert _run(pwned.is_password_pwned(pw)) is False


def test_network_error_fails_open(monkeypatch, enable_pwned):
    monkeypatch.setattr(
        pwned.httpx, "AsyncClient", lambda *a, **k: _FakeAsyncClient(error=RuntimeError("boom"))
    )
    assert _run(pwned.is_password_pwned("password123")) is False


def test_disabled_skips_check(monkeypatch):
    monkeypatch.setattr(pwned.settings, "PWNED_PASSWORD_CHECK_ENABLED", False)

    def _boom(*a, **k):  # must never be called when disabled
        raise AssertionError("network must not be touched when the check is disabled")

    monkeypatch.setattr(pwned.httpx, "AsyncClient", _boom)
    assert _run(pwned.is_password_pwned("password123")) is False


# ── RateLimiter.is_exhausted ─────────────────────────────────────────────────────

def test_is_exhausted_reflects_limit():
    rl = RateLimiter(limit=3, window_seconds=60)
    assert rl.is_exhausted("k") is False
    for _ in range(3):
        assert rl.allow("k") is True
    assert rl.is_exhausted("k") is True
    assert rl.allow("k") is False


def test_is_exhausted_is_a_peek_and_records_nothing():
    rl = RateLimiter(limit=2, window_seconds=60)
    for _ in range(10):
        rl.is_exhausted("k")  # peeking must not consume the budget
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.is_exhausted("k") is True


# ── Entitlements ─────────────────────────────────────────────────────────────────

def test_free_user_entitlements():
    ent = get_entitlements(SimpleNamespace(is_pro=False))
    assert ent.plan is Plan.FREE
    assert ent.monthly_summary_limit == FREE_TIER_SUMMARY_LIMIT == 5
    assert ent.has_unlimited_summaries is False


def test_pro_user_entitlements():
    ent = get_entitlements(SimpleNamespace(is_pro=True))
    assert ent.plan is Plan.PRO
    assert ent.monthly_summary_limit is None
    assert ent.has_unlimited_summaries is True
    assert ent.can_export is True


def test_subscription_service_reexports_limit():
    from app.services.subscription_service import FREE_TIER_SUMMARY_LIMIT as svc_limit

    assert svc_limit == 5
