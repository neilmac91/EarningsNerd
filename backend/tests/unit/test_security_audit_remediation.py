"""Security-audit remediation regression tests — Batch 1 (config & IP-trust hardening).

Covers:
  - H1: SECRET_KEY validation now rejects empty, known-placeholder, and too-short keys in EVERY
    environment (the old guard only blocked one literal, only in production, and was dead code).
  - M8: get_client_ip never trusts the spoofable left-most X-Forwarded-For entry, and ignores the
    header entirely when TRUSTED_PROXY_HOPS <= 0 (falling back to the direct socket peer). The
    default hop count is now 1 (direct Cloud Run ingress).
"""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import Settings, WEAK_SECRET_KEY_VALUES, MIN_SECRET_KEY_LENGTH
from app.services import rate_limiter


def _settings(**overrides) -> Settings:
    # _env_file=None isolates these config tests from a developer's local backend/.env, which
    # would otherwise supply values (e.g. TRUSTED_PROXY_HOPS) and break the defaults assertion.
    return Settings(_env_file=None, **overrides)


# ── H1: SECRET_KEY strength enforcement ───────────────────────────────────────

def test_secret_key_rejects_empty():
    with pytest.raises(ValidationError):
        _settings(SECRET_KEY="")


@pytest.mark.parametrize("placeholder", sorted(WEAK_SECRET_KEY_VALUES))
def test_secret_key_rejects_known_placeholders(placeholder):
    # The .env.example placeholder is 33 chars — over the length floor — so it must be rejected by
    # name, not just by length. This is the exact "copy the example and forget to change it" case.
    with pytest.raises(ValidationError):
        _settings(SECRET_KEY=placeholder)


def test_secret_key_rejects_short_keys():
    with pytest.raises(ValidationError):
        _settings(SECRET_KEY="a" * (MIN_SECRET_KEY_LENGTH - 1))


def test_secret_key_accepts_strong_key():
    strong = "s3cure-random-" + "r" * 40  # 54 chars, not a placeholder
    assert _settings(SECRET_KEY=strong).SECRET_KEY == strong


# ── M8: spoofing-resistant client IP ──────────────────────────────────────────

class _FakeRequest:
    """Minimal duck-typed stand-in for a Starlette Request (only what get_client_ip touches)."""

    def __init__(self, xff=None, client_host=None):
        self.headers = {"x-forwarded-for": xff} if xff is not None else {}
        self.client = SimpleNamespace(host=client_host) if client_host is not None else None


def test_client_ip_uses_trusted_rightmost_hop(monkeypatch):
    monkeypatch.setattr(rate_limiter.settings, "TRUSTED_PROXY_HOPS", 1)
    # Client forges "9.9.9.9"; the single trusted proxy appends the real "5.5.5.5" on the right.
    req = _FakeRequest(xff="9.9.9.9, 5.5.5.5", client_host="10.0.0.1")
    assert rate_limiter.get_client_ip(req) == "5.5.5.5"


def test_client_ip_never_returns_spoofable_leftmost(monkeypatch):
    monkeypatch.setattr(rate_limiter.settings, "TRUSTED_PROXY_HOPS", 1)
    req = _FakeRequest(xff="1.1.1.1, 2.2.2.2, 3.3.3.3", client_host=None)
    # Only the right-most (proxy-appended) entry is trusted; attacker-controlled left entries ignored.
    assert rate_limiter.get_client_ip(req) == "3.3.3.3"


def test_client_ip_ignores_xff_when_hops_zero(monkeypatch):
    monkeypatch.setattr(rate_limiter.settings, "TRUSTED_PROXY_HOPS", 0)
    req = _FakeRequest(xff="9.9.9.9", client_host="7.7.7.7")
    # hops <= 0 must NOT trust the header at all — fall back to the direct socket peer.
    assert rate_limiter.get_client_ip(req) == "7.7.7.7"


def test_client_ip_unknown_without_client_or_trusted_header(monkeypatch):
    monkeypatch.setattr(rate_limiter.settings, "TRUSTED_PROXY_HOPS", 1)
    assert rate_limiter.get_client_ip(_FakeRequest(xff=None, client_host=None)) == "unknown"


def test_trusted_proxy_hops_defaults_to_one(monkeypatch):
    # The safe default for the documented deployment (direct Cloud Run ingress = 1 hop).
    monkeypatch.delenv("TRUSTED_PROXY_HOPS", raising=False)
    assert Settings(SECRET_KEY="s" * 48).TRUSTED_PROXY_HOPS == 1
