"""Week 7 security-hardening regression tests.

Covers two fixes from the pre-beta security sweep:
  - REGISTRATION_MODE fails CLOSED: a typo'd value is rejected at config load instead of silently
    opening public registration (the gate triggers only on an exact "invite_only" match).
  - JWT decode honors the configured clock-skew leeway, so a slightly-future token (NTP skew across
    Cloud Run instances) is not rejected as "not yet valid".
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import jwt
from pydantic import ValidationError

from app.config import Settings, settings


def _make_settings(**overrides) -> Settings:
    # _env_file=None isolates the test from a developer's local .env overriding settings values.
    base = {"SECRET_KEY": "test-secret-key-not-the-default-value", "ENVIRONMENT": "development", "_env_file": None}
    base.update(overrides)
    return Settings(**base)


# ── REGISTRATION_MODE fail-closed validator ───────────────────────────────────

def test_registration_mode_normalizes_case_and_whitespace():
    # Realistic Secret Manager mistakes (case, a trailing newline/space) resolve, not break.
    assert _make_settings(REGISTRATION_MODE="INVITE_ONLY").REGISTRATION_MODE == "invite_only"
    assert _make_settings(REGISTRATION_MODE=" invite_only\n").REGISTRATION_MODE == "invite_only"
    assert _make_settings(REGISTRATION_MODE="Public").REGISTRATION_MODE == "public"


def test_registration_mode_empty_is_documented_public_default():
    assert _make_settings(REGISTRATION_MODE="").REGISTRATION_MODE == "public"


@pytest.mark.parametrize("bad", ["invite-only", "inviteonly", "invite", "closed", "true", "open"])
def test_registration_mode_rejects_typos_fail_closed(bad):
    # A typo must crash config load (old healthy revision keeps serving) — never silently open signup.
    with pytest.raises(ValidationError):
        _make_settings(REGISTRATION_MODE=bad)


# ── JWT clock-skew leeway ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_dependencies_honor_configured_leeway(monkeypatch):
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials
    from starlette.requests import Request

    from app.routers import auth as auth_module

    assert settings.JWT_LEEWAY_SECONDS > 0  # dead config would re-open the skew bug

    now = datetime.now(timezone.utc)
    skewed = {
        "sub": "skew@example.com",
        "iat": now + timedelta(seconds=5),
        "nbf": now + timedelta(seconds=5),
        "exp": now + timedelta(minutes=5),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": "test-skew",
    }
    token = jwt.encode(skewed, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    user = SimpleNamespace(id=1, email="skew@example.com", is_active=True, is_beta=False)
    monkeypatch.setattr(auth_module.auth_account_service, "find_user_by_email",
                        lambda _db, email: user if email == user.email else None)
    request = Request({"type": "http", "headers": []})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # With the configured leeway, a token whose nbf/iat is in the (near) future authenticates.
    assert await auth_module.get_current_user(request, credentials, None) is user
    assert await auth_module.get_current_user_optional(request, credentials, None) is user

    # Without leeway, the same token is rejected as not yet valid.
    monkeypatch.setattr(settings, "JWT_LEEWAY_SECONDS", 0)
    with pytest.raises(HTTPException) as refused:
        await auth_module.get_current_user(request, credentials, None)
    assert refused.value.status_code == 401
    assert await auth_module.get_current_user_optional(request, credentials, None) is None
