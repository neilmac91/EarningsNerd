"""Unit tests for the auth/security-hardening additions:

- HaveIBeenPwned breached-password screening (k-anonymity, fail-open)
- RateLimiter.is_exhausted (read-only peek)
- Entitlements mapping (plan -> limits)
"""
import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import MIN_SECRET_KEY_LENGTH, Settings
from app.services import rate_limiter as rates

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


@pytest.fixture
def limiter_clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(rates, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(rates.settings, "RATE_LIMITER_MAX_KEYS", 2)
    return now


@pytest.mark.parametrize("value", [0, -1, 100001, 1.5, float("inf"), float("nan")])
def test_rate_limiter_key_ceiling_is_positive_integral_and_bounded(value):
    with pytest.raises(ValidationError):
        Settings(SECRET_KEY="x" * MIN_SECRET_KEY_LENGTH, _env_file=None, RATE_LIMITER_MAX_KEYS=value)


def test_key_capacity_rejects_new_keys_without_resetting_active_allowance(limiter_clock):
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("active")
    assert limiter.allow("other")
    for i in range(100):
        assert limiter.allow(f"new-{i}") is False
    assert len(limiter._hits) == 2
    assert limiter.allow("active")  # Existing keys keep their remaining allowance at capacity.
    assert limiter.allow("active") is False
    assert limiter.is_exhausted("active") is True
    assert limiter.is_exhausted("unseen") is False  # Peek remains about prior hits, not admission.
    assert limiter.retry_after("unseen") is None
    assert limiter.retry_after("active") == 60
    limiter._hits.clear()  # Existing contract fixtures reset only this dictionary.
    assert limiter.allow("new")
    assert limiter.allow("active")
    assert limiter.is_exhausted("active") is False


@pytest.mark.parametrize("method", ["allow", "is_exhausted", "retry_after"])
def test_expired_keys_are_removed_lazily_with_the_existing_strict_window(limiter_clock, method):
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.allow("old-a")
    assert limiter.allow("old-b")
    limiter_clock[0] = 60.0
    getattr(limiter, method)("probe")
    assert len(limiter._hits) == 2  # Exactly the boundary is still inside the original window.
    assert limiter.allow("probe") is False
    limiter_clock[0] = 60.001
    getattr(limiter, method)("probe")
    assert "old-a" not in limiter._hits and "old-b" not in limiter._hits
    if method != "allow":
        assert len(limiter._hits) == 0
        assert limiter.allow("probe")
    assert limiter.retry_after("old-a") is None


def test_successful_refresh_expires_idle_keys_without_discarding_recent_hits(limiter_clock):
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("refreshed")
    limiter_clock[0] = 1.0
    assert limiter.allow("idle")
    limiter_clock[0] = 10.0
    assert limiter.allow("refreshed")
    limiter_clock[0] = 62.0
    assert limiter.allow("new")  # idle expired even though refreshed was originally inserted first.
    assert "idle" not in limiter._hits
    assert limiter.allow("refreshed")  # Original t=0 hit expired, t=10 hit remains.
    assert limiter.allow("refreshed") is False


def test_denied_attempts_and_peeks_do_not_extend_key_retention(limiter_clock):
    limiter = RateLimiter(limit=1, window_seconds=60)
    assert limiter.allow("older")
    limiter_clock[0] = 1.0
    assert limiter.allow("newer")
    limiter_clock[0] = 30.0
    assert limiter.allow("older") is False
    assert limiter.is_exhausted("older") is True
    assert limiter.retry_after("older") == 30
    limiter_clock[0] = 60.5
    assert limiter.allow("new")  # The t=0 bucket expired; t=1 stays exhausted.
    assert limiter.is_exhausted("newer") is True
    assert limiter.allow("newer") is False


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
