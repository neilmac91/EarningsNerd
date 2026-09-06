"""Actual waitlist token issuance and persisted verification honor bounded clock skew."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import WaitlistSignup
from app.routers import watchlist
from app.services import waitlist_service


@pytest.mark.asyncio
async def test_waitlist_verification_persists_only_within_configured_clock_skew(monkeypatch):
    verifier_now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
    issuer_skew = 5

    class VerifierDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return verifier_now if tz is None else verifier_now.astimezone(tz)

    class IssuerDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = verifier_now + timedelta(seconds=issuer_skew)
            return value if tz is None else value.astimezone(tz)

    monkeypatch.setattr(jwt.api_jwt, "datetime", VerifierDatetime)
    monkeypatch.setattr(waitlist_service, "datetime", IssuerDatetime)
    monkeypatch.setattr(watchlist.settings, "JWT_LEEWAY_SECONDS", 10)

    engine = create_engine("sqlite:///:memory:")
    try:
        WaitlistSignup.__table__.create(engine)
        with Session(engine) as db:
            within = WaitlistSignup(
                email="within@example.com", referral_code="within01", position=1,
                email_verified=False,
            )
            outside = WaitlistSignup(
                email="outside@example.com", referral_code="outside1", position=2,
                email_verified=False,
            )
            db.add_all([within, outside])
            db.commit()
            within_id, outside_id = within.id, outside.id

            token = waitlist_service.create_verification_token(within.email, within.referral_code)
            assert await watchlist.verify_waitlist_email(token, db) == {
                "success": True, "message": "Email verified.",
            }
            db.expire_all()
            assert db.get(WaitlistSignup, within_id).email_verified is True

            issuer_skew = 11
            token = waitlist_service.create_verification_token(outside.email, outside.referral_code)
            with pytest.raises(HTTPException) as caught:
                await watchlist.verify_waitlist_email(token, db)
            assert caught.value.status_code == 400
            assert caught.value.detail == "Invalid or expired token."
            db.expire_all()
            assert db.get(WaitlistSignup, outside_id).email_verified is False
            assert db.get(WaitlistSignup, within_id).email_verified is True
    finally:
        engine.dispose()
