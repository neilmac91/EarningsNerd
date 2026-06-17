"""Token-gated internal job triggers (/internal/jobs/*)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_returns_503_when_token_not_configured(client):
    # conftest leaves INTERNAL_JOB_TOKEN unset → endpoint disabled.
    resp = client.post("/internal/jobs/filing-scan", headers={"X-Internal-Token": "anything"})
    assert resp.status_code == 503


def test_rejects_missing_or_wrong_token(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_JOB_TOKEN", "s3cret-token")
    assert client.post("/internal/jobs/filing-scan").status_code == 401
    assert client.post(
        "/internal/jobs/filing-scan", headers={"X-Internal-Token": "wrong"}
    ).status_code == 401


def test_valid_token_triggers_scan(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_JOB_TOKEN", "s3cret-token")
    with patch(
        "app.routers.internal.filing_scan_service.run_filing_scan", new=AsyncMock(return_value={})
    ) as mock_scan:
        resp = client.post(
            "/internal/jobs/filing-scan", headers={"X-Internal-Token": "s3cret-token"}
        )
    assert resp.status_code == 202
    assert resp.json()["job"] == "filing-scan"
    # TestClient runs background tasks after the response.
    mock_scan.assert_awaited_once()


def test_valid_token_triggers_digest(client, monkeypatch):
    monkeypatch.setattr(settings, "INTERNAL_JOB_TOKEN", "s3cret-token")
    with patch(
        "app.routers.internal.filing_scan_service.run_daily_digest", new=AsyncMock(return_value={})
    ) as mock_digest:
        resp = client.post(
            "/internal/jobs/filing-digest", headers={"X-Internal-Token": "s3cret-token"}
        )
    assert resp.status_code == 202
    assert resp.json()["job"] == "filing-digest"
    mock_digest.assert_awaited_once()
