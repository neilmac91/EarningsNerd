"""Invitation holds precede prospect writes, link replacement and transport dispatch.

Use real authenticated admin routes and persistence. Only outbound mail is replaced; collection
readiness uses the published synthetic notice fixture, and marketing stays actually closed.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import AuditLog, InviteCode, User
from app.routers.auth import create_access_token
from app.services import email_service, invite_service, legal_readiness_service
from main import app

pytestmark = pytest.mark.requires_db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_headers():
    address = f"invitation-admin-{uuid4().hex}@example.com"
    with SessionLocal() as db:
        db.add(User(email=address, is_admin=True, email_verified=True))
        db.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': address})}"}


@pytest.fixture
def delivery(monkeypatch):
    send = AsyncMock(return_value={"id": "synthetic-mail"})
    monkeypatch.setattr(email_service, "send_email", send)
    return send


def _snapshot():
    with SessionLocal() as db:
        return (
            [(row.id, row.code_hash, row.email, row.is_revoked, row.used_at)
             for row in db.query(InviteCode).order_by(InviteCode.id)],
            db.query(AuditLog).count(),
        )


def _existing_invite(email):
    with SessionLocal() as db:
        row, raw, _ = invite_service.mint_invite(db, created_by=None, email=email)
        return row.id, raw


@pytest.mark.parametrize("payload", [{}, {"email": "invitee@example.com"},
                                      {"email": "invitee@example.com", "send_email": True}])
def test_closed_collection_refuses_mint_without_invite_audit_or_mail(client, admin_headers, delivery, payload):
    assert legal_readiness_service.is_collection_available() is False
    before = _snapshot()

    response = client.post("/api/admin/invites", json=payload, headers=admin_headers)

    assert response.status_code == 503, response.text
    assert _snapshot() == before
    delivery.assert_not_awaited()


@pytest.mark.parametrize("email", [None, "invitee@example.com"])
def test_requested_email_refuses_before_mint_when_marketing_closed(
    client, admin_headers, delivery, collection_ready, email,
):
    assert legal_readiness_service.is_collection_available() is True
    assert legal_readiness_service.is_marketing_available() is False
    before = _snapshot()

    response = client.post("/api/admin/invites", json={"email": email, "send_email": True}, headers=admin_headers)

    assert response.status_code == 503, response.text
    assert "email delivery" in response.json()["detail"]
    assert _snapshot() == before
    delivery.assert_not_awaited()


@pytest.mark.parametrize("email", [None, "invitee@example.com"])
def test_manual_link_mint_requires_no_email_dispatch(client, admin_headers, delivery, collection_ready, email):
    assert legal_readiness_service.is_marketing_available() is False

    response = client.post("/api/admin/invites", json={"email": email, "send_email": False}, headers=admin_headers)

    assert response.status_code == 200, response.text
    assert response.json()["emailed"] is False
    raw = response.json()["invite_link"].split("invite=", 1)[1]
    with SessionLocal() as db:
        stored = invite_service.validate_invite(db, raw, email or "reader@example.com")
        assert stored is not None and stored.id == response.json()["id"]
        assert stored.code_hash != raw
    delivery.assert_not_awaited()


@pytest.mark.parametrize("email", [None, "invitee@example.com"])
def test_closed_collection_resend_preserves_original_link(client, admin_headers, delivery, email):
    invite_id, raw = _existing_invite(email)
    before = _snapshot()

    response = client.post(f"/api/admin/invites/{invite_id}/resend", json={}, headers=admin_headers)

    assert response.status_code == 503, response.text
    assert _snapshot() == before
    with SessionLocal() as db:
        assert invite_service.validate_invite(db, raw, email or "reader@example.com") is not None
    delivery.assert_not_awaited()


def test_email_bound_resend_refuses_before_revocation_or_replacement(
    client, admin_headers, delivery, collection_ready,
):
    assert legal_readiness_service.is_marketing_available() is False
    invite_id, raw = _existing_invite("invitee@example.com")
    before = _snapshot()

    response = client.post(f"/api/admin/invites/{invite_id}/resend", json={}, headers=admin_headers)

    assert response.status_code == 503, response.text
    assert "email delivery" in response.json()["detail"]
    assert _snapshot() == before
    with SessionLocal() as db:
        assert invite_service.validate_invite(db, raw, "invitee@example.com") is not None
    delivery.assert_not_awaited()


def test_unbound_manual_link_can_be_reissued_without_email(client, admin_headers, delivery, collection_ready):
    invite_id, raw = _existing_invite(None)

    response = client.post(f"/api/admin/invites/{invite_id}/resend", json={}, headers=admin_headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] != invite_id
    assert response.json()["revoked_invite_id"] == invite_id
    assert response.json()["emailed"] is False
    replacement = response.json()["invite_link"].split("invite=", 1)[1]
    with SessionLocal() as db:
        assert invite_service.validate_invite(db, raw, "reader@example.com") is None
        assert invite_service.validate_invite(db, replacement, "reader@example.com") is not None
    delivery.assert_not_awaited()


def test_closed_readiness_preserves_invitation_list_and_revoke(client, admin_headers, delivery):
    invite_id, raw = _existing_invite("invitee@example.com")

    listed = client.get("/api/admin/invites", headers=admin_headers)
    revoked = client.post(f"/api/admin/invites/{invite_id}/revoke", headers=admin_headers)

    assert listed.status_code == 200, listed.text
    assert any(row["id"] == invite_id for row in listed.json()["invites"])
    assert revoked.status_code == 200, revoked.text
    with SessionLocal() as db:
        assert invite_service.validate_invite(db, raw, "invitee@example.com") is None
    delivery.assert_not_awaited()


@pytest.mark.asyncio
async def test_invitation_sender_independently_refuses_while_marketing_closed(delivery):
    assert legal_readiness_service.is_marketing_available() is False

    with pytest.raises(email_service.PromotionalMailUnavailable, match="email delivery"):
        await email_service.send_invite_email(to_email="invitee@example.com", magic_link="https://example.com/invite")

    delivery.assert_not_awaited()


@pytest.mark.asyncio
async def test_dormant_invitation_copy_promises_account_access_without_pro(delivery, monkeypatch):
    # Inspect the dormant template without making delivery available in production.
    monkeypatch.setattr(legal_readiness_service, "is_marketing_available", lambda: True)
    link = "https://example.com/invite"

    await email_service.send_invite_email(to_email="invitee@example.com", magic_link=link)

    delivery.assert_awaited_once()
    for part in (delivery.call_args.kwargs["html"], delivery.call_args.kwargs["text"]):
        assert "You're invited to create an EarningsNerd account." in part
        assert link in part
        assert "Review the account requirements" in part
        assert "full pro" not in part.lower()
        assert "no card" not in part.lower()
        assert "no credit card" not in part.lower()
