"""New collection requires an explicitly published notice; private drafts never leave the API."""
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.database import get_db
from app.routers import contact, watchlist
from app.services import contact_submission_service, legal_readiness_service as legal, waitlist_service
from main import app


def test_settings_default_closed_without_operator_details():
    configured = Settings(_env_file=None)
    assert configured.LEGAL_COLLECTION_ENABLED is False
    assert configured.LEGAL_OPERATOR_PUBLISHED is False
    assert configured.LEGAL_OPERATOR_NAME == ""
    assert configured.LEGAL_OPERATOR_POSTAL_ADDRESS == ""
    assert configured.LEGAL_OPERATOR_COUNTRY == ""
    assert configured.LEGAL_OPERATOR_EMAIL == ""
    assert legal.is_checkout_available() is False
    assert legal.is_marketing_available() is False


@pytest.mark.parametrize("missing", [
    "LEGAL_OPERATOR_NAME", "LEGAL_OPERATOR_POSTAL_ADDRESS", "LEGAL_OPERATOR_COUNTRY", "LEGAL_OPERATOR_EMAIL",
])
def test_incomplete_operator_is_neither_published_nor_ready(collection_ready, monkeypatch, missing):
    monkeypatch.setattr(settings, missing, " ")
    assert legal.public_operator() is None
    assert legal.is_collection_available() is False


@pytest.mark.parametrize("field,value", [
    ("LEGAL_OPERATOR_NAME", "TODO"),
    ("LEGAL_OPERATOR_EMAIL", "not-an-email"),
    ("LEGAL_OPERATOR_POSTAL_ADDRESS", "address\x00tail"),
])
def test_invalid_notice_does_not_enable_collection(collection_ready, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    assert legal.public_operator() is None
    assert legal.is_collection_available() is False


def test_private_draft_values_never_leave_the_api(collection_ready, monkeypatch):
    monkeypatch.setattr(settings, "LEGAL_OPERATOR_PUBLISHED", False)
    response = TestClient(app).get("/api/legal/readiness")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "collection_available": False,
        "checkout_available": False,
        "marketing_available": False,
        "terms_version": legal.TERMS_VERSION,
        "eligibility_version": legal.ELIGIBILITY_VERSION,
        "operator": None,
    }
    for value in (settings.LEGAL_OPERATOR_NAME, settings.LEGAL_OPERATOR_POSTAL_ADDRESS, settings.LEGAL_OPERATOR_EMAIL):
        assert value not in response.text


def test_complete_published_notice_opens_only_explicitly_enabled_collection(collection_ready, monkeypatch):
    client = TestClient(app)
    response = client.get("/api/legal/readiness")
    assert response.json()["collection_available"] is True
    assert response.json()["operator"] == {
        "legal_name": "Test Operator", "postal_address": "1 Test Street, Test City",
        "country": "CH", "contact_email": "legal@example.com",
    }
    assert response.json()["checkout_available"] is False
    assert response.json()["marketing_available"] is False
    monkeypatch.setattr(settings, "LEGAL_COLLECTION_ENABLED", False)
    closed = client.get("/api/legal/readiness").json()
    assert closed["collection_available"] is False
    # Notice remains readable while collection is paused; rights information is not hidden.
    assert closed["operator"] == response.json()["operator"]


class _ForbiddenSession:
    def __getattr__(self, name):
        raise AssertionError(f"Closed collection touched the database: {name}")


@pytest.mark.parametrize("path,payload,router", [
    ("/api/waitlist/join", {"email": "reader@example.com", "name": "Reader"}, watchlist),
    ("/api/contact/", {
        "name": "Reader", "email": "reader@example.com", "subject": "Question",
        "message": "A question about the application.",
    }, contact),
])
def test_closed_routes_refuse_before_captcha_persistence_or_mail(monkeypatch, path, payload, router):
    captcha = AsyncMock(side_effect=AssertionError("CAPTCHA must not run"))
    monkeypatch.setattr(router, "enforce_turnstile", captcha)
    prior = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: _ForbiddenSession()
    try:
        response = TestClient(app).post(path, json=payload)
        assert response.status_code == 503
        assert response.json()["detail"] == legal.COLLECTION_UNAVAILABLE_MESSAGE
        captcha.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(prior)


def test_collection_services_cannot_bypass_the_hold():
    with pytest.raises(legal.CollectionUnavailable):
        waitlist_service.create_signup(
            _ForbiddenSession(), email="reader@example.com", name=None, referral_code=None, source=None,
        )
    with pytest.raises(legal.CollectionUnavailable):
        contact_submission_service.persist_contact_submission(
            _ForbiddenSession(), name="Reader", email="reader@example.com", subject=None,
            message="Question", ip_address="hashed", logger=logging.getLogger(__name__),
        )
