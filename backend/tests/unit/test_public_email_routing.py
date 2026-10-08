"""Capture real outbound payloads and routing without contacting an email provider."""
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from main import app
from app.routers import feedback
from app.services import resend_service

_REAL_CLIENT = httpx.AsyncClient


@pytest.mark.asyncio
async def test_transactional_reply_to_default_and_override(monkeypatch):
    captured = []

    def respond(request):
        import json

        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "email_test"})

    monkeypatch.setattr(resend_service.settings, "RESEND_API_KEY", "test-provider-credential")
    monkeypatch.setattr(resend_service.settings, "RESEND_FROM_EMAIL", "Verified <sender@example.com>")
    monkeypatch.setattr(resend_service.settings, "RESEND_REPLY_TO_EMAIL", "support@example.com")
    monkeypatch.setattr(
        resend_service.httpx, "AsyncClient",
        lambda **kwargs: _REAL_CLIENT(transport=httpx.MockTransport(respond), **kwargs),
    )

    await resend_service.send_email(["recipient@example.com"], "Account", "<p>Hello</p>")
    await resend_service.send_email(
        ["support@example.com"], "Contact", "<p>Message</p>", reply_to="customer@example.com",
    )

    assert captured[0]["from"] == captured[1]["from"] == "Verified <sender@example.com>"
    assert captured[0]["reply_to"] == "support@example.com"
    assert captured[1]["reply_to"] == "customer@example.com"


@pytest.mark.asyncio
async def test_feedback_destination_does_not_follow_transactional_sender(monkeypatch):
    captured = []

    async def send(**kwargs):
        captured.append(kwargs)
        return {"id": "email_test"}

    monkeypatch.setattr(feedback, "send_email", send)
    monkeypatch.setattr(feedback.settings, "RESEND_FROM_EMAIL", "Verified <sender@example.com>")
    monkeypatch.setattr(feedback.settings, "FEEDBACK_NOTIFICATION_EMAIL", "support@example.com")
    await feedback._notify_admin(
        SimpleNamespace(id=42, email="customer@example.com"),
        SimpleNamespace(id=1, type="bug", message="I found a broken link", page_url="/contact"),
    )

    assert captured[0]["to"] == ["support@example.com"]
    assert captured[0]["reply_to"] == "customer@example.com"


def test_api_security_contact_is_anonymous_and_redirects_to_canonical_https():
    with TestClient(app) as client:
        response = client.get("/.well-known/security.txt", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://www.earningsnerd.io/.well-known/security.txt"
