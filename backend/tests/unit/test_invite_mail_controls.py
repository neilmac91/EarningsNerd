"""Requested beta-invitation email (EN-BETA PB-01) through the real admin, unsubscribe and webhook routes.

Only the provider transport is replaced (``email_service.send_email``); readiness, persistence, the routes and the
signature check are real. The cases pin what the controls promise:

- readiness names the conditions that hold collection and invitation email, never their values;
- an emailed invitation needs the recipient's recorded request, is refused for a suppressed address and for an
  address that already holds a live link (so a repeated submit, a retry or a second tab mints no second link), and
  is sent once, with its delivery's idempotency key and tag;
- each provider outcome is recorded as what it is: accepted (not delivered), failed (nothing sent) or unknown (it may
  have been sent), and nothing is ever retried blind;
- a re-send reuses the request the link was first emailed under, refuses before revoking anything, and makes one
  replacement however often it is pressed;
- the unsubscribe link suppresses its address for every later invitation, and requested account mail still goes;
- a signed webhook moves a delivery up its evidence order and never down, a duplicate changes nothing, a permanent
  bounce, a complaint or the provider's suppression suppresses the address, and an unsigned or forged one records
  nothing.

The lock order between a send and an opt-out is proven on PostgreSQL in
``tests/integration/test_admin_invite_transactions.py``.
"""
import base64
import hashlib
import hmac
import json
import re
from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog, InviteCode, User
from app.models.invite_mail import InviteDelivery, MailRecipient
from app.routers.auth import create_access_token
from app.services import (
    email_service,
    invite_delivery_service,
    invite_service,
    legal_readiness_service,
    mail_suppression_service,
    resend_webhook_service,
)
from app.services.resend_service import ResendAmbiguousError, ResendPermanentError, ResendRetryableError
from app.utils.datetimes import utcnow
from main import app
from tests.support.account_agreement import ACCOUNT_AGREEMENT

pytestmark = pytest.mark.requires_db

# Built, not written out: a Svix signing secret is base64 after "whsec_" (the signature test pins Svix's own vector).
WEBHOOK_SECRET = "whsec_" + base64.b64encode(b"pb-01 synthetic webhook signing key").decode()
# A tester's password for the real registration route, built rather than written out, like the secret above, so
# the secret scan reads no credential in this file (CI's secret-scan; .gitleaksignore).
TESTER_PASSWORD = "-".join(("Tester", "Pass", "2026", "Ok"))
PERMISSION = {"requested_via": "message", "requested_on": utcnow().date().isoformat()}
UNSUBSCRIBE_LINK = re.compile(r"/email/unsubscribe#token=([A-Za-z0-9_-]+)")
INVITE_LINK = re.compile(r"/register\?invite=([A-Za-z0-9_-]+)")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin():
    address = f"invitation-admin-{uuid4().hex}@example.com"
    with SessionLocal() as db:
        user = User(email=address, is_admin=True, email_verified=True)
        db.add(user)
        db.commit()
        return {"id": user.id, "headers": {"Authorization": f"Bearer {create_access_token({'sub': address})}"}}


@pytest.fixture
def mail_ready(collection_ready, monkeypatch):
    monkeypatch.setattr(settings, "LEGAL_INVITATION_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "synthetic-provider-key")
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", WEBHOOK_SECRET)
    assert legal_readiness_service.is_invitation_email_available()


@pytest.fixture
def transport(monkeypatch):
    """The provider: accepts every request, answering with an id of its own."""
    send = AsyncMock(side_effect=lambda **kwargs: {"id": f"em_{uuid4().hex[:12]}"})
    monkeypatch.setattr(email_service, "send_email", send)
    return send


def _address() -> str:
    return f"tester-{uuid4().hex[:10]}@example.com"


def _mint(client, admin, email, **body):
    return client.post(
        "/api/admin/invites",
        json={"email": email, "send_email": True, "permission": PERMISSION, **body},
        headers=admin["headers"],
    )


def _resend(client, admin, invite_id, **body):
    return client.post(f"/api/admin/invites/{invite_id}/resend", json=body, headers=admin["headers"])


def _delivery(invite_id: int) -> InviteDelivery | None:
    with SessionLocal() as db:
        return db.query(InviteDelivery).filter(InviteDelivery.invite_id == invite_id).first()


def _recipient(email: str) -> MailRecipient | None:
    with SessionLocal() as db:
        return db.query(MailRecipient).filter(
            MailRecipient.recipient_hash == mail_suppression_service.recipient_hash(email)).first()


def _bound(email: str) -> list[InviteCode]:
    with SessionLocal() as db:
        return db.query(InviteCode).filter(InviteCode.email == email.lower()).order_by(InviteCode.id).all()


def _token_from(send: AsyncMock, call: int = -1) -> str:
    return UNSUBSCRIBE_LINK.search(send.await_args_list[call].kwargs["html"]).group(1)


def _sign(body: bytes, svix_id: str, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> dict:
    stamp = str(timestamp if timestamp is not None else int(utcnow().timestamp()))
    encoded = secret.removeprefix("whsec_")
    key = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
    digest = hmac.new(key, f"{svix_id}.{stamp}.".encode() + body, hashlib.sha256).digest()
    return {"svix-id": svix_id, "svix-timestamp": stamp, "svix-signature": "v1," + base64.b64encode(digest).decode()}


def _event(client, event_type: str, data: dict, *, svix_id: str | None = None, headers: dict | None = None):
    body = json.dumps({"type": event_type, "created_at": "2026-11-02T12:00:00.000Z", "data": data}).encode()
    svix_id = svix_id or f"msg_{uuid4().hex}"
    return client.post("/api/webhooks/resend", content=body, headers=headers or _sign(body, svix_id))


def _tagged(delivery: InviteDelivery, **data) -> dict:
    return {"email_id": delivery.provider_email_id or "em_unknown", "to": ["recipient@example.com"],
            "tags": {"en_invite_delivery": delivery.delivery_ref}, **data}


# --------------------------------------------------------------------------------------------- readiness

def test_readiness_names_the_conditions_never_their_values(client, admin, monkeypatch):
    monkeypatch.setattr(settings, "LEGAL_OPERATOR_NAME", "Draft Operator Name GmbH")
    monkeypatch.setattr(settings, "LEGAL_OPERATOR_POSTAL_ADDRESS", "Draft Street 9")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", "")

    response = client.get("/api/admin/invites/readiness", headers=admin["headers"])

    assert response.status_code == 200, response.text
    assert response.json() == {
        "collection": {"available": False, "reasons": ["collection_disabled", "operator_unpublished"]},
        "invitation_email": {"available": False, "reasons": [
            "collection_unavailable", "invitation_email_disabled", "provider_unconfigured",
            "provider_feedback_unverified"]},
    }
    assert "Draft" not in response.text


def test_readiness_is_admin_only(client):
    address = f"reader-{uuid4().hex}@example.com"
    with SessionLocal() as db:
        db.add(User(email=address, email_verified=True))
        db.commit()
    headers = {"Authorization": f"Bearer {create_access_token({'sub': address})}"}
    assert client.get("/api/admin/invites/readiness", headers=headers).status_code == 403


def test_a_published_but_incomplete_operator_reads_incomplete(collection_ready, monkeypatch):
    monkeypatch.setattr(settings, "LEGAL_OPERATOR_POSTAL_ADDRESS", "TBD")
    assert legal_readiness_service.collection_readiness() == {"available": False, "reasons": ["operator_incomplete"]}
    assert legal_readiness_service.is_collection_available() is False


@pytest.mark.parametrize("setting, value, reason", [
    ("LEGAL_INVITATION_EMAIL_ENABLED", False, "invitation_email_disabled"),
    ("RESEND_API_KEY", "   ", "provider_unconfigured"),
    ("RESEND_WEBHOOK_SECRET", "", "provider_feedback_unverified"),
    ("RESEND_WEBHOOK_SECRET", "whsec_not base64!", "provider_feedback_unverified"),
    ("LEGAL_COLLECTION_ENABLED", False, "collection_unavailable"),
])
def test_each_condition_holds_invitation_email_alone(mail_ready, monkeypatch, setting, value, reason):
    monkeypatch.setattr(settings, setting, value)
    assert legal_readiness_service.invitation_email_readiness() == {"available": False, "reasons": [reason]}


# --------------------------------------------------------------------------------------------- the emailed mint

def test_an_emailed_invitation_records_its_request_and_is_sent_once_with_its_identity(
    client, admin, mail_ready, transport,
):
    email = _address()

    response = _mint(client, admin, email)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["emailed"] is True and body["delivery_status"] == "accepted"
    delivery = _delivery(body["id"])
    assert (delivery.status, delivery.permission_via, delivery.permission_requested_on.isoformat()) == (
        "accepted", "message", PERMISSION["requested_on"])
    assert delivery.created_by == admin["id"]
    assert delivery.recipient_hash == mail_suppression_service.recipient_hash(email)
    transport.assert_awaited_once()
    sent = transport.await_args.kwargs
    assert sent["to"] == [email]
    assert sent["idempotency_key"] == f"en-invite-{delivery.delivery_ref}"
    assert sent["tags"] == [{"name": resend_webhook_service.DELIVERY_TAG, "value": delivery.delivery_ref}]
    assert delivery.provider_email_id and delivery.provider_email_id.startswith("em_")
    raw = INVITE_LINK.search(body["invite_link"]).group(1)
    token = _token_from(transport)
    for part in (sent["html"], sent["text"]):
        assert body["invite_link"] in part
        assert f"/email/unsubscribe#token={token}" in part
        assert "you asked for an invitation" in part
    # Neither the link's token nor the unsubscribe token is stored, only their hashes.
    assert delivery.unsubscribe_token_hash == hashlib.sha256(token.encode()).hexdigest()
    stored = [value for value in vars(delivery).values() if isinstance(value, str)]
    assert not any(raw in value or token in value for value in stored)
    with SessionLocal() as db:
        audit = db.query(AuditLog).filter(AuditLog.action == "invite_minted",
                                          AuditLog.entity_id == str(body["id"])).one()
    assert audit.details == {"cohort": None, "emailed": True, "delivery_status": "accepted"}
    assert raw not in json.dumps(audit.details)


@pytest.mark.parametrize("permission, fragment", [
    (None, "Record how and when the recipient asked"),
    ({"requested_via": "carrier pigeon", "requested_on": PERMISSION["requested_on"]}, "requested_via"),
    ({"requested_via": "email", "requested_on": (utcnow().date() + timedelta(days=3)).isoformat()}, "future"),
    ({"requested_via": "email", "requested_on": (utcnow().date() - timedelta(days=400)).isoformat()}, "last year"),
    ({**PERMISSION, "consent": True}, "consent"),
])
def test_an_emailed_invitation_needs_the_recipients_own_request(
    client, admin, mail_ready, transport, permission, fragment,
):
    email = _address()
    body = {"email": email, "send_email": True}
    if permission is not None:
        body["permission"] = permission

    response = client.post("/api/admin/invites", json=body, headers=admin["headers"])

    assert response.status_code == 422, response.text
    assert fragment in response.text
    assert _bound(email) == [] and _recipient(email) is None
    transport.assert_not_awaited()


def test_held_invitation_email_writes_nothing_even_for_a_complete_request(client, admin, collection_ready, transport):
    email = _address()

    response = _mint(client, admin, email)

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Invitation email delivery is currently unavailable."
    assert _bound(email) == [] and _recipient(email) is None
    transport.assert_not_awaited()


def test_a_repeated_submit_mints_no_second_link(client, admin, mail_ready, transport):
    email = _address()
    first = _mint(client, admin, email)
    assert first.status_code == 200, first.text

    again = _mint(client, admin, email.upper())

    assert again.status_code == 409, again.text
    assert again.json()["detail"] == (
        f"A pending invitation already exists for this address (invite {first.json()['id']}). Re-send or revoke it.")
    assert [invite.id for invite in _bound(email)] == [first.json()["id"]]
    transport.assert_awaited_once()


def test_a_suppressed_address_is_refused_before_anything_is_written(client, admin, mail_ready, transport):
    email = _address()
    with SessionLocal() as db:
        mail_suppression_service.suppress(db, mail_suppression_service.recipient_hash(email), "complaint", "test")
        db.commit()

    response = _mint(client, admin, email)

    assert response.status_code == 409, response.text
    assert "unsubscribed from invitation emails, or its mail bounced or was reported as spam" in response.json()["detail"]
    assert _bound(email) == []
    transport.assert_not_awaited()


@pytest.mark.parametrize("error, status, kind", [
    (ResendRetryableError("429"), "failed", "provider_retryable"),
    (ResendPermanentError("422"), "failed", "provider_rejected"),
    (ResendAmbiguousError("read timeout"), "unknown", "provider_ambiguous"),
    (RuntimeError("a bug after the request left"), "unknown", "RuntimeError"),
])
def test_each_provider_outcome_is_recorded_as_what_it_is_and_never_retried(
    client, admin, mail_ready, transport, error, status, kind,
):
    transport.side_effect = error
    email = _address()

    response = _mint(client, admin, email)

    assert response.status_code == 200, response.text
    assert response.json()["emailed"] is False and response.json()["delivery_status"] == status
    assert "/register?invite=" in response.json()["invite_link"]  # the admin can still share it, or re-send it
    delivery = _delivery(response.json()["id"])
    assert (delivery.status, delivery.error_kind, delivery.provider_email_id) == (status, kind, None)
    transport.assert_awaited_once()


def test_the_sender_refuses_when_readiness_closes_after_the_route_checked(client, admin, mail_ready, transport,
                                                                         monkeypatch):
    answers = iter([True, False])  # the route's check, then the sender's own
    monkeypatch.setattr(legal_readiness_service, "is_invitation_email_available", lambda: next(answers))

    response = _mint(client, admin, _address())

    assert response.status_code == 200, response.text
    assert response.json()["delivery_status"] == "failed"
    assert _delivery(response.json()["id"]).error_kind == "held"
    transport.assert_not_awaited()


# --------------------------------------------------------------------------------------------- the re-send

def test_an_emailed_resend_reuses_the_first_request_and_replaces_the_link(client, admin, mail_ready, transport):
    email = _address()
    first = _mint(client, admin, email, permission={"requested_via": "call", "requested_on": PERMISSION["requested_on"]})
    old_raw = INVITE_LINK.search(first.json()["invite_link"]).group(1)

    resent = _resend(client, admin, first.json()["id"], send_email=True)

    assert resent.status_code == 200, resent.text
    assert resent.json()["revoked_invite_id"] == first.json()["id"]
    assert resent.json()["emailed"] is True
    replacement = _delivery(resent.json()["id"])
    assert replacement.permission_via == "call"
    assert replacement.delivery_ref != _delivery(first.json()["id"]).delivery_ref
    assert transport.await_count == 2
    assert transport.await_args.kwargs["html"].count(resent.json()["invite_link"]) >= 1
    with SessionLocal() as db:
        assert invite_service.validate_invite(db, old_raw, email) is None
        assert invite_service.validate_invite(db, INVITE_LINK.search(resent.json()["invite_link"]).group(1), email)


def test_a_resend_that_names_no_choice_emails_a_bound_invites_replacement(client, admin, mail_ready, transport):
    first = _mint(client, admin, _address())

    resent = _resend(client, admin, first.json()["id"])

    assert resent.status_code == 200, resent.text
    assert resent.json()["emailed"] is True
    assert transport.await_count == 2


def test_an_emailed_resend_of_a_link_never_emailed_needs_its_request(client, admin, mail_ready, transport):
    email = _address()
    manual = client.post("/api/admin/invites", json={"email": email}, headers=admin["headers"])
    raw = INVITE_LINK.search(manual.json()["invite_link"]).group(1)

    refused = _resend(client, admin, manual.json()["id"], send_email=True)

    assert refused.status_code == 422, refused.text
    with SessionLocal() as db:
        assert invite_service.validate_invite(db, raw, email) is not None  # nothing was revoked
    transport.assert_not_awaited()

    allowed = _resend(client, admin, manual.json()["id"], send_email=True, permission=PERMISSION)
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["emailed"] is True


def test_an_emailed_resend_of_an_unbound_link_is_refused(client, admin, mail_ready, transport):
    unbound = client.post("/api/admin/invites", json={}, headers=admin["headers"])

    refused = _resend(client, admin, unbound.json()["id"], send_email=True, permission=PERMISSION)

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"] == "This invitation isn't bound to an address, so it can't be emailed."
    with SessionLocal() as db:
        assert db.get(InviteCode, unbound.json()["id"]).is_revoked is False
    transport.assert_not_awaited()


@pytest.mark.parametrize("emailed", [True, False], ids=["emailed", "manual"])
def test_a_second_resend_of_one_invite_makes_no_second_live_link(client, admin, mail_ready, transport, emailed):
    email = _address()
    first = _mint(client, admin, email)
    replaced = _resend(client, admin, first.json()["id"], send_email=emailed)
    assert replaced.status_code == 200, replaced.text

    again = _resend(client, admin, first.json()["id"], send_email=emailed)

    assert again.status_code == 409, again.text
    assert f"(invite {replaced.json()['id']})" in again.json()["detail"]
    live = [invite.id for invite in _bound(email) if not invite.is_revoked and invite.used_at is None]
    assert live == [replaced.json()["id"]]
    assert transport.await_count == (2 if emailed else 1)


def test_a_manual_resend_of_a_bound_invite_sends_nothing(client, admin, mail_ready, transport, monkeypatch):
    """A re-send naming `send_email: false` re-issues an address-bound link as a link to share by hand (chief review
    6589171631 on #1965: within the manual-link scope). The replacement keeps the recipient and the cohort, the former
    link is revoked in the same transaction, the provider is called zero times, and through the real registration
    route the new link registers only its recipient while the former one registers no one. On main a re-send had no
    such selector: it re-issued a bound invite's link only by emailing it, behind email's readiness."""
    from app.routers import auth as auth_module

    monkeypatch.setattr(settings, "REGISTRATION_MODE", "invite_only")
    auth_module.REGISTER_LIMITER._hits.clear()
    email = _address()
    first = _mint(client, admin, email)
    former = INVITE_LINK.search(transport.await_args_list[0].kwargs["html"]).group(1)
    transport.reset_mock()

    resent = _resend(client, admin, first.json()["id"], send_email=False)

    assert resent.status_code == 200, resent.text
    assert resent.json()["emailed"] is False and resent.json()["delivery_status"] is None
    assert resent.json()["revoked_invite_id"] == first.json()["id"]
    assert _delivery(resent.json()["id"]) is None
    transport.assert_not_awaited()
    replacement = INVITE_LINK.search(resent.json()["invite_link"]).group(1)
    old_row, new_row = _bound(email)
    assert old_row.id == first.json()["id"] and old_row.is_revoked and old_row.used_at is None
    assert new_row.id == resent.json()["id"] and not new_row.is_revoked and new_row.used_at is None
    assert (new_row.email, new_row.cohort) == (old_row.email, old_row.cohort)

    def register(address: str, token: str):
        client.cookies.clear()
        return client.post("/api/auth/register", json={
            **ACCOUNT_AGREEMENT, "email": address, "password": TESTER_PASSWORD, "invite_code": token,
        })

    stranger = _address()
    assert register(stranger, replacement).status_code == 403  # another address: the replacement is bound
    assert register(email, former).status_code == 403  # the former link: revoked
    with SessionLocal() as db:
        assert db.query(User).filter(User.email.in_([stranger, email])).count() == 0
    assert register(email, replacement).status_code == 200  # its recipient
    with SessionLocal() as db:
        account = db.query(User).filter(User.email == email).one()
        assert db.get(InviteCode, new_row.id).user_id == account.id
    client.cookies.clear()


def test_a_manual_resend_adds_no_address_to_the_suppression_list(client, admin, collection_ready):
    """A manual re-issue sends nothing, so it adds no address to the suppression list (review of #1965): while
    invitation email is held, as this ships, a Resend of a bound invite leaves no row there, so the list holds only
    addresses invitation email was sent to or that opted out, bounced or complained."""
    email = _address()
    minted = client.post("/api/admin/invites", json={"email": email, "send_email": False}, headers=admin["headers"])
    assert minted.status_code == 200, minted.text

    resent = _resend(client, admin, minted.json()["id"], send_email=False)

    assert resent.status_code == 200, resent.text
    assert resent.json()["revoked_invite_id"] == minted.json()["id"]
    assert _recipient(email) is None


def test_a_webhook_whose_type_is_not_a_string_is_acknowledged_and_records_nothing(client, mail_ready):
    """Validated where it enters (rule 9): a signed delivery whose type is a list, an object or a number is no
    feedback. It answers 200, as an unknown type does, where a list or an object raised a 500 at the membership test,
    so the provider would have retried it for ever."""
    for odd in (["email.bounced"], {"type": "email.bounced"}, 7):
        body = json.dumps({"type": odd, "created_at": "2026-11-02T12:00:00.000Z", "data": {}}).encode()
        answer = client.post("/api/webhooks/resend", content=body, headers=_sign(body, f"msg_{uuid4().hex}"))
        assert answer.status_code == 200, (odd, answer.text)
    assert resend_webhook_service.parse_event(["email.bounced"], {}, "msg_1") is None


def test_an_id_with_a_trailing_newline_is_no_id():
    """The parser's patterns match the whole value: a 64-character email id with a trailing newline (65 characters,
    past its 64-character column, which failed every retry with 503) and a delivery ref with one are refused, where an
    end anchor let both through."""
    event = resend_webhook_service.parse_event(
        "email.delivered",
        {"email_id": "x" * 64 + "\n", "tags": {resend_webhook_service.DELIVERY_TAG: "a" * 32 + "\n"}},
        "msg_1",
    )
    assert event is not None and event.email_id is None and event.delivery_ref is None
    assert resend_webhook_service.parse_event("email.delivered", {}, "msg_1\n") is None


def test_an_emailed_resend_to_a_suppressed_address_refuses_before_revoking(client, admin, mail_ready, transport):
    email = _address()
    first = _mint(client, admin, email)
    assert client.post("/api/email/unsubscribe", json={"token": _token_from(transport)}).status_code == 200

    refused = _resend(client, admin, first.json()["id"], send_email=True)

    assert refused.status_code == 409, refused.text
    with SessionLocal() as db:
        assert db.get(InviteCode, first.json()["id"]).is_revoked is False
    # A link the admin shares by hand is not an email from us: the manual re-send still works.
    assert _resend(client, admin, first.json()["id"], send_email=False).status_code == 200
    transport.assert_awaited_once()


# --------------------------------------------------------------------------------------------- unsubscribe

def test_the_unsubscribe_link_suppresses_its_address_for_every_later_invitation(client, admin, mail_ready, transport):
    email = _address()
    first = _mint(client, admin, email)
    token = _token_from(transport)

    assert client.get("/api/email/unsubscribe").status_code == 405  # a scanner's fetch changes nothing
    done = client.post("/api/email/unsubscribe", json={"token": token})

    assert done.status_code == 200, done.text
    assert done.json() == {"status": "unsubscribed"}
    recipient = _recipient(email)
    assert recipient.suppression_reason == "unsubscribed"
    assert recipient.suppression_event == f"unsubscribe:{_delivery(first.json()['id']).delivery_ref}"
    assert client.post("/api/email/unsubscribe", json={"token": token}).json() == {"status": "unsubscribed"}
    # The live link stays redeemable: an opt-out stops mail, it does not take back an invitation.
    assert invite_service.invite_status(_bound(email)[0]) == "pending"
    invite_service_revoke = client.post(f"/api/admin/invites/{first.json()['id']}/revoke", headers=admin["headers"])
    assert invite_service_revoke.status_code == 200
    later = _mint(client, admin, email)
    assert later.status_code == 409, later.text
    transport.assert_awaited_once()


@pytest.mark.parametrize("body, status", [
    ({"token": "not-a-token-we-sent"}, 404),
    ({"token": ""}, 422),
    ({"token": "x" * 201}, 422),
    ({"token": "a", "email": "someone@example.com"}, 422),
])
def test_an_unsubscribe_without_a_token_we_sent_changes_nothing(client, body, status):
    before = None
    with SessionLocal() as db:
        before = db.query(MailRecipient).filter(MailRecipient.suppressed_at.is_not(None)).count()
    response = client.post("/api/email/unsubscribe", json=body)
    assert response.status_code == status, response.text
    with SessionLocal() as db:
        assert db.query(MailRecipient).filter(MailRecipient.suppressed_at.is_not(None)).count() == before


@pytest.mark.asyncio
async def test_requested_account_mail_never_reads_the_suppression_list(mail_ready, transport):
    email = _address()
    with SessionLocal() as db:
        mail_suppression_service.suppress(db, mail_suppression_service.recipient_hash(email), "unsubscribed", "test")
        db.commit()

    await email_service.send_password_reset_email(to_email=email, name=None, reset_link="https://e.test/reset?token=t")

    transport.assert_awaited_once()


def test_an_unsubscribe_after_a_send_was_authorised_stops_the_next_send_alone(collection_ready, mail_ready, transport):
    """The send authorised before the opt-out committed goes; none authorised after it does. (On PostgreSQL the
    opt-out waits for that send's commit: tests/integration/test_admin_invite_transactions.py.)"""
    import asyncio

    email = _address()
    permission = invite_delivery_service.Permission("email", utcnow().date())
    with SessionLocal() as db:
        first = invite_delivery_service.prepare_invite_send(
            db, created_by=None, email=email, expires_in_hours=None, cohort=None, permission=permission)
    token = first.unsubscribe_link.split("#token=", 1)[1]
    with SessionLocal() as db:
        assert invite_delivery_service.unsubscribe(db, token) is True

    outcome = asyncio.run(invite_delivery_service.deliver(first))

    assert outcome.status == "accepted"
    transport.assert_awaited_once()
    with SessionLocal() as db:
        invite_service.revoke_invite(db, first.issued["id"])
        with pytest.raises(invite_delivery_service.RecipientSuppressed):
            invite_delivery_service.prepare_invite_send(
                db, created_by=None, email=email, expires_in_hours=None, cohort=None, permission=permission)
    assert len(_bound(email)) == 1


# --------------------------------------------------------------------------------------------- provider feedback

def test_a_forged_or_stale_event_records_nothing(client, admin, mail_ready, transport):
    email = _address()
    delivery = _delivery(_mint(client, admin, email).json()["id"])
    body = json.dumps({"type": "email.complained", "data": _tagged(delivery, to=[email])}).encode()

    forged = client.post("/api/webhooks/resend", content=body, headers=_sign(body, "msg_forged", secret=(
        "whsec_" + base64.b64encode(b"another endpoint's key").decode())))
    stale = client.post("/api/webhooks/resend", content=body,
                        headers=_sign(body, "msg_stale", timestamp=int(utcnow().timestamp()) - 3600))

    assert (forged.status_code, stale.status_code) == (401, 401)
    assert _delivery(delivery.invite_id).status == "accepted"
    assert _recipient(email).suppressed_at is None


def test_signed_events_move_a_delivery_up_its_evidence_and_never_down(client, admin, mail_ready, transport):
    email = _address()
    delivery = _delivery(_mint(client, admin, email).json()["id"])

    assert _event(client, "email.delivered", _tagged(delivery), svix_id="msg_delivered").status_code == 200
    assert _delivery(delivery.invite_id).status == "delivered"
    # The same delivery again, and two older events arriving late: nothing moves.
    for event_type, svix_id in (("email.delivered", "msg_delivered"), ("email.sent", "msg_sent_late"),
                                ("email.delivery_delayed", "msg_delayed_late")):
        assert _event(client, event_type, _tagged(delivery), svix_id=svix_id).status_code == 200
        row = _delivery(delivery.invite_id)
        assert (row.status, row.last_event_id) == ("delivered", "msg_delivered")

    bounced = _event(client, "email.bounced", _tagged(delivery, to=[email], bounce={"type": "Permanent",
                                                                                      "subType": "General"}))
    assert bounced.status_code == 200
    row = _delivery(delivery.invite_id)
    assert (row.status, row.bounce_type) == ("bounced", "permanent")
    assert _recipient(email).suppression_reason == "hard_bounce"

    assert _event(client, "email.complained", _tagged(delivery, to=[email])).status_code == 200
    assert _delivery(delivery.invite_id).status == "complained"
    assert _recipient(email).suppression_reason == "hard_bounce"  # the first suppression stands


def test_a_temporary_bounce_suppresses_nothing(client, admin, mail_ready, transport):
    email = _address()
    delivery = _delivery(_mint(client, admin, email).json()["id"])

    _event(client, "email.bounced", _tagged(delivery, to=[email], bounce={"type": "Temporary"}))

    row = _delivery(delivery.invite_id)
    assert (row.status, row.bounce_type) == ("bounced", "temporary")
    assert _recipient(email).suppressed_at is None


def test_a_complaint_suppresses_its_address_whatever_mail_it_was_about(client, mail_ready):
    email = _address()

    response = _event(client, "email.complained", {"email_id": "em_an_alert", "to": [email.upper()],
                                                   "tags": {"category": "alert"}})

    assert response.status_code == 200, response.text
    assert _recipient(email).suppression_reason == "complaint"


@pytest.mark.parametrize("event_type, data, status, kind, reason", [
    ("email.failed", {"failed": {"reason": "reached_daily_quota"}}, "failed", "provider:reached_daily_quota", None),
    ("email.failed", {"failed": {"reason": "Not A Reason!"}}, "failed", "provider:unspecified", None),
    ("email.suppressed", {"suppressed": {"type": "OnAccountSuppressionList"}}, "suppressed",
     "provider_suppression_list", "provider_suppressed"),
])
def test_the_providers_own_refusals_are_recorded(client, admin, mail_ready, transport, event_type, data, status,
                                                 kind, reason):
    email = _address()
    delivery = _delivery(_mint(client, admin, email).json()["id"])

    assert _event(client, event_type, _tagged(delivery, to=[email], **data)).status_code == 200

    row = _delivery(delivery.invite_id)
    assert (row.status, row.error_kind) == (status, kind)
    assert (_recipient(email).suppression_reason) == reason


def test_a_lost_answer_is_resolved_by_the_providers_tagged_event(client, admin, mail_ready, transport):
    transport.side_effect = ResendAmbiguousError("read timeout")
    delivery = _delivery(_mint(client, admin, _address()).json()["id"])
    assert (delivery.status, delivery.provider_email_id) == ("unknown", None)

    _event(client, "email.delivered", {**_tagged(delivery), "email_id": "em_found_by_its_tag"})

    row = _delivery(delivery.invite_id)
    assert (row.status, row.provider_email_id) == ("delivered", "em_found_by_its_tag")
    transport.assert_awaited_once()


def test_an_event_that_arrives_before_the_calls_answer_stands(collection_ready, mail_ready, transport):
    permission = invite_delivery_service.Permission("email", utcnow().date())
    with SessionLocal() as db:
        prepared = invite_delivery_service.prepare_invite_send(
            db, created_by=None, email=_address(), expires_in_hours=None, cohort=None, permission=permission)
    event = resend_webhook_service.parse_event(
        "email.delivered", {"email_id": "em_early", "tags": {"en_invite_delivery": prepared.delivery_ref}},
        "msg_early")
    with SessionLocal() as db:
        invite_delivery_service.apply_provider_event(db, event)
    with SessionLocal() as db:
        status = invite_delivery_service.record_send_outcome(
            db, prepared.delivery_id, invite_delivery_service.SendOutcome("unknown", error_kind="provider_ambiguous"))
    assert status == "delivered"
    row = _delivery(prepared.issued["id"])
    assert (row.status, row.provider_email_id, row.error_kind) == ("delivered", "em_early", None)


def test_unauthenticated_feedback_is_not_recorded(client, collection_ready, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", "")  # outside production the check is then skipped
    assert settings.ENVIRONMENT != "production"
    email = _address()
    body = json.dumps({"type": "email.complained", "data": {"email_id": "em_x", "to": [email]}}).encode()

    response = client.post("/api/webhooks/resend", content=body,
                           headers={"svix-id": "msg_unsigned", "svix-timestamp": "0", "svix-signature": "v1,AAAA"})

    assert response.status_code == 200, response.text
    assert _recipient(email) is None


def test_a_failed_record_asks_the_provider_to_send_the_event_again(client, mail_ready, monkeypatch):
    email = _address()
    apply = invite_delivery_service.apply_provider_event
    failures = iter([RuntimeError("the database went away")])

    def once_unavailable(db, event):
        error = next(failures, None)
        if error is not None:
            raise error
        return apply(db, event)

    monkeypatch.setattr(invite_delivery_service, "apply_provider_event", once_unavailable)
    first = _event(client, "email.complained", {"email_id": "em_retry", "to": [email]}, svix_id="msg_retry")
    assert first.status_code == 503, first.text
    assert "the database went away" not in first.text
    assert _recipient(email) is None
    again = _event(client, "email.complained", {"email_id": "em_retry", "to": [email]}, svix_id="msg_retry")
    assert again.status_code == 200, again.text
    assert _recipient(email).suppression_reason == "complaint"


# --------------------------------------------------------------------------------------------- the admin list

def test_the_list_shows_each_emailed_invites_delivery_and_its_addresss_suppression(client, admin, mail_ready,
                                                                                   transport):
    emailed, manual = _address(), _address()
    emailed_id = _mint(client, admin, emailed).json()["id"]
    manual_id = client.post("/api/admin/invites", json={"email": manual}, headers=admin["headers"]).json()["id"]
    client.post("/api/email/unsubscribe", json={"token": _token_from(transport)})
    stale = _mint(client, admin, _address()).json()["id"]
    with SessionLocal() as db:  # a send whose process stopped mid-call: still "sending" long after its commit
        row = db.query(InviteDelivery).filter(InviteDelivery.invite_id == stale).one()
        row.status, row.updated_at = "sending", utcnow() - timedelta(minutes=10)
        db.commit()

    rows = {row["id"]: row for row in client.get("/api/admin/invites", headers=admin["headers"]).json()["invites"]}

    assert rows[emailed_id]["delivery"]["status"] == "accepted"
    assert rows[emailed_id]["delivery"]["permission_via"] == "message"
    assert rows[emailed_id]["email_suppression"] == "unsubscribed"
    assert rows[manual_id]["delivery"] is None and rows[manual_id]["email_suppression"] is None
    assert rows[stale]["delivery"]["status"] == "unknown"


def test_an_invites_expiry_is_bounded(client, admin, collection_ready):
    for hours in (0, -1, 721, 10**12):
        response = client.post("/api/admin/invites", json={"expires_in_hours": hours}, headers=admin["headers"])
        assert response.status_code == 422, (hours, response.text)


def test_a_resends_expiry_is_bounded_and_refused_before_revoking(client, admin, collection_ready):
    email = _address()
    first = client.post("/api/admin/invites", json={"email": email}, headers=admin["headers"])
    assert first.status_code == 200, first.text
    invite_id = first.json()["id"]
    with SessionLocal() as db:
        expires_at = db.get(InviteCode, invite_id).expires_at

    for hours in (0, -1, 721, 10**12):
        response = _resend(client, admin, invite_id, expires_in_hours=hours, send_email=False)
        assert response.status_code == 422, (hours, response.text)

    # Refused at the boundary: the invite is still live and unrevoked, and no replacement was minted.
    with SessionLocal() as db:
        invite = db.get(InviteCode, invite_id)
        assert invite.is_revoked is False and invite.used_at is None
        assert invite.expires_at == expires_at
    assert [row.id for row in _bound(email)] == [invite_id]


# --------------------------------------------------------------------------------------------- the boundary

def test_an_event_is_validated_where_it_enters():
    parse = resend_webhook_service.parse_event
    ref = "a" * 32
    assert parse("email.opened", {"email_id": "em_1"}, "msg_1") is None  # nothing the controls act on
    assert parse("email.delivered", {"email_id": "em_1"}, "bad id with spaces") is None
    assert parse("email.delivered", "not an object", "msg_1") is None
    as_object = parse("email.delivered", {"tags": {"en_invite_delivery": ref}, "to": "A@Example.com"}, "msg_1")
    as_list = parse("email.delivered", {"tags": [{"name": "en_invite_delivery", "value": ref}]}, "msg_2")
    assert (as_object.delivery_ref, as_object.recipients) == (ref, ("a@example.com",))
    assert as_list.delivery_ref == ref
    assert parse("email.delivered", {"tags": {"en_invite_delivery": "../../etc"}}, "msg_3").delivery_ref is None
    assert parse("email.delivered", {"to": ["not an address", 7, "b@example.com"]}, "msg_4").recipients == (
        "b@example.com",)
    assert parse("email.bounced", {"bounce": {"type": "Transient"}}, "msg_5").bounce_type == "temporary"
    assert parse("email.bounced", {}, "msg_6").bounce_type == "undetermined"
    assert parse("email.delivered", {"email_id": "x" * 65}, "msg_7").email_id is None
