import sys
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


def _load_app(tmp_path):
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/test_api.db"
    os.environ["OPENAI_API_KEY"] = ""

    for module_name in list(sys.modules):
        if module_name == "main" or module_name.startswith("app."):
            sys.modules.pop(module_name)

    import app.config
    import app.database
    import app.models
    import app.routers.auth
    import app.routers.summaries
    import main

    app.database.Base.metadata.create_all(bind=app.database.engine)

    return main.app


def _seed_filing():
    from app.database import SessionLocal
    from app.models import Company, Filing

    with SessionLocal() as session:
        company = Company(
            cik="0000000000",
            ticker="TEST",
            name="Test Corp",
            exchange="NASDAQ",
        )
        session.add(company)
        session.commit()
        session.refresh(company)

        filing = Filing(
            company_id=company.id,
            accession_number="0000000000-00-000000",
            filing_type="10-K",
            filing_date=datetime.now(timezone.utc),
            period_end_date=datetime.now(timezone.utc),
            document_url="https://example.com/document",
            sec_url="https://example.com/sec",
        )
        session.add(filing)
        session.commit()
        session.refresh(filing)
        return filing.id


def _register_user(client: TestClient, email: str = "user@example.com"):
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPass123", "full_name": "Test User"},
    )
    assert response.status_code == 200
    return response


def test_auth_cookie_allows_me(tmp_path):
    app = _load_app(tmp_path)
    client = TestClient(app)

    response = _register_user(client)
    assert "set-cookie" in response.headers

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["email"] == "user@example.com"


def test_security_headers_present_on_api_responses(tmp_path):
    app = _load_app(tmp_path)
    client = TestClient(app)

    _register_user(client)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"
    assert response.headers.get("Content-Security-Policy") == "default-src 'none'"
    assert "Strict-Transport-Security" not in response.headers


def test_email_normalization_accepts_case_insensitive_login(tmp_path):
    app = _load_app(tmp_path)
    client = TestClient(app)

    _register_user(client, email="CaseSensitive@Example.com")
    login = client.post(
        "/api/auth/login",
        json={"email": "casesensitive@example.com", "password": "StrongPass123"},
    )
    assert login.status_code == 200


def test_summary_requires_auth_and_rate_limits(tmp_path, monkeypatch):
    app = _load_app(tmp_path)
    client = TestClient(app)

    filing_id = _seed_filing()

    unauth_response = client.post(f"/api/summaries/filing/{filing_id}/generate")
    assert unauth_response.status_code == 401

    _register_user(client, email="rate@example.com")

    import app.routers.summaries as summaries
    from app.services.rate_limiter import RateLimiter

    async def _noop_background(*args, **kwargs):
        return None

    monkeypatch.setattr(summaries, "_generate_summary_background", _noop_background)
    summaries.SUMMARY_LIMITER = RateLimiter(limit=1, window_seconds=60)

    ok_response = client.post(f"/api/summaries/filing/{filing_id}/generate")
    assert ok_response.status_code == 200

    limited_response = client.post(f"/api/summaries/filing/{filing_id}/generate")
    assert limited_response.status_code == 429
