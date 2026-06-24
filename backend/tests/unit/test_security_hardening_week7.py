"""Week 7 security-hardening regression tests.

Covers two fixes from the pre-beta security sweep:
  - REGISTRATION_MODE fails CLOSED: a typo'd value is rejected at config load instead of silently
    opening public registration (the gate triggers only on an exact "invite_only" match).
  - JWT decode honors the configured clock-skew leeway, so a slightly-future token (NTP skew across
    Cloud Run instances) is not rejected as "not yet valid".
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from jose.exceptions import JWTError
from pydantic import ValidationError

from app.config import Settings, settings


def _make_settings(**overrides) -> Settings:
    base = {"SECRET_KEY": "test-secret-key-not-the-default", "ENVIRONMENT": "development"}
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

def test_jwt_decode_honors_configured_leeway():
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
    require = ["exp", "sub", "iat", "iss", "aud"]

    # Without leeway, a token whose nbf/iat is in the (near) future is rejected.
    with pytest.raises(JWTError):
        jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE, issuer=settings.JWT_ISSUER,
            options={"require": require},
        )

    # With the configured leeway (as get_current_user now passes), it decodes.
    decoded = jwt.decode(
        token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
        audience=settings.JWT_AUDIENCE, issuer=settings.JWT_ISSUER,
        options={"require": require, "leeway": settings.JWT_LEEWAY_SECONDS},
    )
    assert decoded["sub"] == "skew@example.com"
