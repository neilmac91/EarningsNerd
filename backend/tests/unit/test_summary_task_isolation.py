"""Summary delivery cannot silently spend the account-mail queue or worker capacity.

Cloud Tasks/JWKS HTTP is answered in memory here; the companion loopback test exercises
independent real worker processes and fixture children. Neither proves deployed cloud isolation.
"""
from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest

from app.config import settings
from app.services import background_task_runner as runner, durable_tasks as transport
from app.services import task_process_service as processes, task_routing as routing
from app.services.durable_tasks import TaskEnvelope, TaskUnavailable
from app.utils.datetimes import utcnow


@pytest.fixture
def isolated_routes(monkeypatch):
    for key, value in {
        "DURABLE_TASKS_ENABLED": True, "TASKS_PROJECT_ID": "test-project",
        "TASKS_LOCATION": "us-west1", "TASKS_QUEUE": "background",
        "TASKS_WORKER_URL": "https://background-worker-uw.a.run.app",
        "TASKS_INVOKER_EMAIL": "background@test-project.iam.gserviceaccount.com",
        "SUMMARY_TASKS_QUEUE": "summaries",
        "SUMMARY_TASKS_WORKER_URL": "https://summary-worker-uw.a.run.app",
        "SUMMARY_TASKS_INVOKER_EMAIL": "summary@test-project.iam.gserviceaccount.com",
        "TASKS_WORKER_ROLE": "background",
    }.items():
        monkeypatch.setattr(settings, key, value)


@pytest.mark.asyncio
async def test_summary_and_existing_kinds_keep_distinct_routes_and_stable_names(isolated_routes, monkeypatch):
    seen = []

    def respond(request):
        seen.append((str(request.url), json.loads(request.content)["task"]))
        return httpx.Response(409 if len(seen) == 2 else 200, json={}, request=request)

    client = httpx.AsyncClient
    monkeypatch.setattr(transport, "_access_token", AsyncMock(return_value="unused-test-token"))
    monkeypatch.setattr(transport.httpx, "AsyncClient", lambda **kw: client(transport=httpx.MockTransport(respond), **kw))
    payload = {"job_id": "a" * 32, "generation": 1}
    first = await transport.enqueue_task("summary", payload, dedupe_key="fixed-dispatch")
    second = await transport.enqueue_task("summary", payload, dedupe_key="fixed-dispatch")
    assert first == second and "/queues/summaries/tasks/" in first
    task = seen[0][1]
    assert task == seen[1][1]
    assert json.loads(base64.b64decode(task["httpRequest"]["body"])) == {"kind": "summary", "payload": payload}
    assert task["httpRequest"]["url"] == settings.SUMMARY_TASKS_WORKER_URL + "/internal/tasks/execute"
    assert task["httpRequest"]["oidcToken"] == {
        "audience": settings.SUMMARY_TASKS_WORKER_URL,
        "serviceAccountEmail": settings.SUMMARY_TASKS_INVOKER_EMAIL,
    }
    # Isolating the queue changes its namespace, not the logical dispatch hash.
    monkeypatch.setattr(settings, "SUMMARY_TASKS_QUEUE", "summaries-replacement")
    moved = await transport.enqueue_task("summary", payload, dedupe_key="fixed-dispatch")
    assert moved.rsplit("/", 1)[1] == first.rsplit("/", 1)[1]
    cases = [
        ("account_mail", {"email": "fixture@example.com", "mail": "verification"}),
        ("filings", {"company_id": 7, "filing_types": ["10-Q"]}),
        ("history", {"company_id": 7}), ("companyfacts", {"company_id": 7}),
        ("internal_job", {"job": "filing_scan"}), ("probe", {}),
    ]
    for kind, body in cases:
        name = await transport.enqueue_task(kind, body, dedupe_key=f"existing-{kind}")
        assert "/queues/background/tasks/" in name
        assert seen[-1][1]["httpRequest"]["url"] == settings.TASKS_WORKER_URL + "/internal/tasks/execute"
        assert seen[-1][1]["httpRequest"]["oidcToken"]["serviceAccountEmail"] == settings.TASKS_INVOKER_EMAIL


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [
    ("SUMMARY_TASKS_QUEUE", ""), ("SUMMARY_TASKS_QUEUE", "background"),
    ("SUMMARY_TASKS_QUEUE", "invalid/name"), ("SUMMARY_TASKS_QUEUE", "query?name"),
    ("SUMMARY_TASKS_WORKER_URL", ""), ("SUMMARY_TASKS_WORKER_URL", "http://summary-worker-uw.a.run.app"),
    ("SUMMARY_TASKS_WORKER_URL", "https://BACKGROUND-WORKER-uw.a.run.app:443/"),
    ("SUMMARY_TASKS_WORKER_URL", "https://summary-worker-uw.a.run.app:8443"),
    ("SUMMARY_TASKS_WORKER_URL", "https://summary-worker-uw.a.run.app?target=background"),
    ("SUMMARY_TASKS_WORKER_URL", "https://[invalid"),
    ("SUMMARY_TASKS_INVOKER_EMAIL", ""), ("SUMMARY_TASKS_INVOKER_EMAIL", "not-a-service-account"),
    ("DURABLE_TASKS_ENABLED", False),
])
async def test_invalid_summary_route_fails_before_any_metadata_or_queue_request(
    isolated_routes, monkeypatch, field, value,
):
    monkeypatch.setattr(settings, field, value)
    metadata = AsyncMock(side_effect=AssertionError("metadata must not be reached"))
    monkeypatch.setattr(transport, "_access_token", metadata)
    with pytest.raises(TaskUnavailable):
        await transport.enqueue_task("summary", {"job_id": "b" * 32, "generation": 1})
    metadata.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_summary_configuration_does_not_disable_existing_background_work(isolated_routes, monkeypatch):
    for field in ("SUMMARY_TASKS_QUEUE", "SUMMARY_TASKS_WORKER_URL", "SUMMARY_TASKS_INVOKER_EMAIL"):
        monkeypatch.setattr(settings, field, "")
    assert routing.task_route("account_mail") == routing.background_route()
    assert routing.worker_route() == routing.background_route()
    with pytest.raises(TaskUnavailable):
        routing.task_route("summary")


@pytest.mark.asyncio
async def test_worker_identity_is_bound_to_its_role_not_the_task_body(isolated_routes, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())), "kid": "isolated-fixture"}
    monkeypatch.setattr(transport, "_get_google_jwks", AsyncMock(return_value={"keys": [jwk]}))

    def token(role):
        route = routing.summary_route() if role == "summary" else routing.background_route()
        return jwt.encode({
            "iss": "https://accounts.google.com", "aud": route.worker_url, "sub": "fixture",
            "email": route.invoker_email, "email_verified": True,
            "exp": int(utcnow().timestamp()) + 600,
        }, key, algorithm="RS256", headers={"kid": "isolated-fixture"})

    for role, other in (("background", "summary"), ("summary", "background")):
        monkeypatch.setattr(settings, "TASKS_WORKER_ROLE", role)
        await transport.verify_task_identity(token(role))
        with pytest.raises((jwt.PyJWTError, ValueError)):
            await transport.verify_task_identity(token(other))
    monkeypatch.setattr(settings, "TASKS_WORKER_ROLE", "unknown")
    with pytest.raises(TaskUnavailable):
        await transport.verify_task_identity(token("summary"))


@pytest.mark.asyncio
@pytest.mark.parametrize("role,kind", [("background", "summary"), ("summary", "account_mail"), ("summary", "internal_job")])
async def test_wrong_kind_is_refused_before_spawn_and_again_in_the_child_runner(monkeypatch, role, kind):
    monkeypatch.setattr(settings, "TASKS_WORKER_ROLE", role)
    monkeypatch.setattr(settings, "TASKS_WORKER_PROCESS", True)
    spawn = AsyncMock(side_effect=AssertionError("wrong kind must not spawn"))
    monkeypatch.setattr(processes.asyncio, "create_subprocess_exec", spawn)
    envelope = TaskEnvelope(kind=kind, payload={})
    with pytest.raises(TaskUnavailable, match="not served"):
        await processes.run_task_process(envelope)
    spawn.assert_not_awaited()
    with pytest.raises(TaskUnavailable, match="not served"):
        await runner.run_background_task(envelope)
