"""Launch holds stop new purchases and promotion, without disabling existing account services.

These cases use the actual closed readiness decisions. The older cohort, customer ownership,
pool-lifetime and template suites explicitly open only their readiness seam to retain coverage
of those dormant contracts; they are not evidence that a deployment may open checkout or mail.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
import stripe
from fastapi.testclient import TestClient

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import User
from app.routers import auth, subscriptions
from app.services import email_service, legal_readiness_service
from main import app


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


def _authorization(customer_id: str | None, *, beta: bool = False) -> dict[str, str]:
    email = f"billing-readiness-{uuid4().hex}@example.com"
    with SessionLocal() as db:
        db.add(User(email=email, email_verified=True, is_active=True, is_beta=beta,
                    stripe_customer_id=customer_id))
        db.commit()
    return {"Authorization": f"Bearer {auth.create_access_token({'sub': email})}"}


@pytest.mark.parametrize("customer_id", [None, "cus_existing"])
@pytest.mark.parametrize("beta", [False, True])
def test_closed_checkout_refuses_before_any_stripe_call(client, monkeypatch, customer_id, beta):
    assert legal_readiness_service.is_checkout_available() is False
    monkeypatch.setattr(settings, "STRIPE_PRICE_MONTHLY_ID", "price_monthly_test")
    calls = []
    for owner, method in ((stripe.Customer, "create"), (stripe.Customer, "retrieve"),
                          (stripe.checkout.Session, "create")):
        call = Mock(side_effect=AssertionError("closed checkout reached Stripe"))
        monkeypatch.setattr(owner, method, call)
        calls.append(call)
    release = Mock(wraps=subscriptions.filing_list_service.release_request_session)
    monkeypatch.setattr(subscriptions.filing_list_service, "release_request_session", release)

    response = client.post("/api/subscriptions/create-checkout-session", params={"price_id": "monthly"},
                           headers=_authorization(customer_id, beta=beta))

    assert response.status_code == 503, response.text
    assert "New subscriptions are not available" in response.json()["detail"]
    release.assert_called_once()
    assert not release.call_args.args[0].in_transaction()
    for call in calls:
        call.assert_not_called()


def test_closed_checkout_preserves_existing_billing_management(client, monkeypatch):
    assert legal_readiness_service.is_checkout_available() is False
    portal = Mock(return_value=SimpleNamespace(url="https://portal.stripe.test/existing"))
    monkeypatch.setattr(stripe.billing_portal.Session, "create", portal)
    headers = _authorization("cus_existing")

    status = client.get("/api/subscriptions/subscription", headers=headers)
    response = client.post("/api/subscriptions/create-portal-session", headers=headers)

    assert status.status_code == 200, status.text
    assert status.json()["stripe_customer_id"] == "cus_existing"
    assert response.status_code == 200, response.text
    assert response.json() == {"url": "https://portal.stripe.test/existing"}
    portal.assert_called_once()
    assert portal.call_args.kwargs["customer"] == "cus_existing"


@pytest.mark.asyncio
async def test_closed_marketing_never_dispatches_a_referral_promotion(monkeypatch):
    assert legal_readiness_service.is_marketing_available() is False
    send = AsyncMock()
    monkeypatch.setattr(email_service, "send_email", send)

    await email_service.send_referral_success_email(
        to_email="reader@example.com", name="Reader", new_position=2,
        referral_link="https://example.com/waitlist?ref=example",
    )

    send.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("sender, arguments", [
    ("send_verification_email", {"verification_link": "https://example.com/verify"}),
    ("send_password_reset_email", {"reset_link": "https://example.com/reset"}),
    ("send_new_filing_alert", {"company_name": "Example", "ticker": "EX", "filing_type": "10-K",
                               "filing_date": "2026-10-23", "filing_id": 1}),
])
async def test_closed_marketing_preserves_requested_account_messages(monkeypatch, sender, arguments):
    assert legal_readiness_service.is_marketing_available() is False
    send = AsyncMock(return_value={"id": "mail_test"})
    monkeypatch.setattr(email_service, "send_email", send)

    await getattr(email_service, sender)(to_email="reader@example.com", name="Reader", **arguments)

    send.assert_awaited_once()
    assert send.call_args.kwargs["to"] == ["reader@example.com"]
    assert send.call_args.kwargs["html"]
    assert send.call_args.kwargs["text"]


@pytest.mark.asyncio
async def test_waitlist_confirmation_carries_verification_without_promotion(monkeypatch):
    send = AsyncMock(return_value={"id": "mail_test"})
    monkeypatch.setattr(email_service, "send_email", send)
    referral = "https://example.com/waitlist?ref=example"
    verification = "https://example.com/verify"

    await email_service.send_waitlist_welcome_email(
        to_email="reader@example.com", name="Reader", position=3,
        referral_link=referral, verification_link=verification,
    )

    send.assert_awaited_once()
    for part in (send.call_args.kwargs["html"], send.call_args.kwargs["text"]):
        assert verification in part
        assert "You're on the EarningsNerd waitlist." in part
        assert referral not in part
        assert "Share your referral" not in part
        assert "keep you posted" not in part
