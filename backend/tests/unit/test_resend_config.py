"""Tests for the Resend (outbound email) startup validation.

Email is on the verify-first signup path, so these guard against the most common
misconfiguration: a From address that won't actually deliver to real users.
"""
from app.config import settings

_VERIFIED = "EarningsNerd <hello@inbound.earningsnerd.io>"


def test_resend_config_flags_resend_dev_sender(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key_1234567890")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "EarningsNerd <onboarding@resend.dev>")
    ok, warnings = settings.validate_resend_config()
    assert ok is False
    assert any("resend.dev" in w for w in warnings)


def test_resend_config_accepts_verified_domain(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key_1234567890")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", _VERIFIED)
    ok, warnings = settings.validate_resend_config()
    assert ok is True
    assert warnings == []


def test_resend_config_flags_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", _VERIFIED)
    ok, warnings = settings.validate_resend_config()
    assert ok is False
    assert any("RESEND_API_KEY" in w for w in warnings)


def test_resend_config_flags_empty_from(monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key_1234567890")
    monkeypatch.setattr(settings, "RESEND_FROM_EMAIL", "")
    ok, warnings = settings.validate_resend_config()
    assert ok is False
    assert any("empty" in w.lower() for w in warnings)
