"""Tests for the Resend (outbound email) startup validation.

Email is on the verify-first signup path, so these guard against the most common
misconfiguration: a From address that won't actually deliver to real users.
"""
from app.config import Settings, settings

_VERIFIED = "EarningsNerd <hello@inbound.earningsnerd.io>"


def test_from_email_strips_accidental_wrapping_quotes():
    # A quoted Secret Manager / .env value (the cause of Resend's 422 "Invalid `from` field").
    s = Settings(RESEND_FROM_EMAIL='"EarningsNerd <hello@inbound.earningsnerd.io>"')
    assert s.RESEND_FROM_EMAIL == "EarningsNerd <hello@inbound.earningsnerd.io>"


def test_from_email_keeps_legitimately_quoted_display_name():
    # A display name that's RFC-quoted (not wrapping the whole value) must be left intact.
    s = Settings(RESEND_FROM_EMAIL='"Earnings, Nerd" <hello@inbound.earningsnerd.io>')
    assert s.RESEND_FROM_EMAIL == '"Earnings, Nerd" <hello@inbound.earningsnerd.io>'


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
