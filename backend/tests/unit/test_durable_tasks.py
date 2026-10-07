"""Boundary and acknowledgement guarantees for request-based CPU task delivery."""
from __future__ import annotations

import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI

from app.config import settings
from app.routers import tasks
from app.routers import filings
from app.services import durable_tasks as transport, filing_history_service as history
from app.utils.datetimes import utcnow


@pytest.fixture
def configured(monkeypatch):
    for key, value in {
        "DURABLE_TASKS_ENABLED": True, "TASKS_PROJECT_ID": "test-project",
        "TASKS_LOCATION": "us-west1", "TASKS_QUEUE": "background",
        "TASKS_WORKER_URL": "https://worker-xyz-uw.a.run.app",
        "TASKS_INVOKER_EMAIL": "task-worker@test-project.iam.gserviceaccount.com",
    }.items():
        monkeypatch.setattr(settings, key, value)


@pytest.mark.asyncio
async def test_task_auth_requires_signed_matching_audience_and_identity(configured, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-key"
    monkeypatch.setattr(transport, "_get_google_jwks", AsyncMock(return_value={"keys": [jwk]}))
    claims = {
        "iss": "https://accounts.google.com", "aud": settings.TASKS_WORKER_URL,
        "sub": "1234", "email": settings.TASKS_INVOKER_EMAIL, "email_verified": True,
        "exp": int(utcnow().timestamp()) + 600,
    }

    def token(fields, signing_key=key):
        return jwt.encode(fields, signing_key, algorithm="RS256", headers={"kid": "test-key"})

    await transport.verify_task_identity(token(claims))
    variants = [
        {**claims, "aud": "https://unrelated.example"},
        {**claims, "email": "other@test-project.iam.gserviceaccount.com"},
        {**claims, "email_verified": False},
        {**claims, "iss": "https://unrelated.example"},
        {**claims, "exp": int(utcnow().timestamp()) - 600},
    ]
    for invalid in variants:
        with pytest.raises((ValueError, jwt.PyJWTError)):
            await transport.verify_task_identity(token(invalid))
    with pytest.raises(jwt.PyJWTError):
        await transport.verify_task_identity(token(claims, rsa.generate_private_key(public_exponent=65537, key_size=2048)))


@pytest.mark.asyncio
async def test_enqueue_is_bounded_deduplicated_and_never_contains_credentials(configured, monkeypatch):
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(409 if len(requests) > 1 else 200, request=request, json={})

    client = httpx.AsyncClient
    monkeypatch.setattr(transport, "_access_token", AsyncMock(return_value="metadata-only-token"))
    monkeypatch.setattr(transport.httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs))
    first = await transport.enqueue_task("companyfacts", {"company_id": 7}, dedupe_key="company:7")
    assert await transport.enqueue_task("companyfacts", {"company_id": 7}, dedupe_key="company:7") == first
    task = requests[0]["task"]
    assert task["name"] == requests[1]["task"]["name"]
    assert task["httpRequest"]["oidcToken"] == {
        "serviceAccountEmail": settings.TASKS_INVOKER_EMAIL, "audience": settings.TASKS_WORKER_URL,
    }
    body = json.loads(base64.b64decode(task["httpRequest"]["body"]))
    assert body == {"kind": "companyfacts", "payload": {"company_id": 7}}
    assert "metadata-only-token" not in json.dumps(requests)
    assert task["dispatchDeadline"] == "540s"
    with pytest.raises(ValueError):
        await transport.enqueue_task("companyfacts", {"company_id": 7, "document": "private"})


@pytest.mark.asyncio
async def test_queue_failure_is_not_reported_as_accepted(configured, monkeypatch):
    monkeypatch.setattr(transport, "_access_token", AsyncMock(side_effect=httpx.ConnectError("offline")))
    with pytest.raises(transport.TaskUnavailable):
        await transport.enqueue_task("companyfacts", {"company_id": 7})
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", False)
    with pytest.raises(transport.TaskUnavailable):
        await transport.enqueue_task("companyfacts", {"company_id": 7})


@pytest.mark.asyncio
async def test_worker_authenticates_before_work_and_acknowledges_only_finished_work(monkeypatch):
    app = FastAPI()
    app.include_router(tasks.router, prefix="/internal")
    work = AsyncMock()
    monkeypatch.setattr(tasks, "run_background_task", work)
    identity = AsyncMock()
    monkeypatch.setattr(tasks, "verify_task_identity", identity)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        body = {"kind": "companyfacts", "payload": {"company_id": 7}}
        rejected = await client.post("/internal/tasks/execute", json=body, headers={"X-CloudTasks-QueueName": "background"})
        assert rejected.status_code == 401
        work.assert_not_awaited()
        good = await client.post("/internal/tasks/execute", json=body, headers={"Authorization": "Bearer signed"})
        assert good.status_code == 200
        work.assert_awaited_once()
        work.side_effect = RuntimeError("persistence failed")
        failed = await client.post("/internal/tasks/execute", json=body, headers={"Authorization": "Bearer signed"})
        assert failed.status_code == 503
        assert failed.json()["detail"] == "Task failed; retry delivery"


def test_partial_history_keeps_retry_eligible_without_losing_inserted_rows(monkeypatch):
    company = SimpleNamespace(ticker="TEST", history_backfilled_at=None)
    db = SimpleNamespace(commit=lambda: None)
    monkeypatch.setattr(history.filing_scan_service, "upsert_filings", lambda *args: [object()])
    with pytest.raises(RuntimeError, match="incomplete"):
        history._persist_history_rows(db, company, rows=[], windows=4, windows_ok=3, require_complete=True)
    assert company.history_backfilled_at is None
    stats = history._persist_history_rows(db, company, rows=[], windows=4, windows_ok=4, require_complete=True)
    assert company.history_backfilled_at is not None
    assert stats["windows_ok"] == 4


@pytest.mark.asyncio
async def test_repeat_cached_visits_do_not_wait_on_the_control_plane(monkeypatch):
    monkeypatch.setattr(filings, "_visit_task_handoffs", {})
    clock = SimpleNamespace(timestamp=lambda: 101)
    monkeypatch.setattr(filings, "utcnow", lambda: clock)
    enqueue = AsyncMock()
    monkeypatch.setattr(filings, "enqueue_task", enqueue)
    args = ("filings", {"company_id": 7, "filing_types": ["10-K"]})
    await filings._enqueue_visit_task(*args, key="filings:7", seconds=100)
    await filings._enqueue_visit_task(*args, key="filings:7", seconds=100)
    enqueue.assert_awaited_once()
    clock.timestamp = lambda: 201
    await filings._enqueue_visit_task(*args, key="filings:7", seconds=100)
    assert enqueue.await_count == 2
