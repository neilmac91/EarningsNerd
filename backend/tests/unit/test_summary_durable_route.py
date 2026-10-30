"""Exercise authenticated durable admission, recovery and observer ownership with real DB jobs."""
import asyncio
from contextlib import aclosing
from datetime import timedelta
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from app.config import settings
from app.database import SessionLocal
from app.models import Summary, SummaryGenerationProgress, SummaryJob, User
from app.routers import summaries
from app.routers.auth import get_current_user
from app.services import summary_job_store as store, summary_jobs as jobs
from app.services import summary_request_evidence as evidence_module
from app.services.rate_limiter import ActiveStreamLimiter, RateLimiter
from app.utils.datetimes import utcnow
from main import app
from tests.support.summary_stream_harness import seed_company_filing, stream_boundaries


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(summaries, "SUMMARY_LIMITER", RateLimiter(limit=5, window_seconds=60))
    monkeypatch.setattr(summaries, "SUMMARY_REQUEST_LIMITER", RateLimiter(limit=60, window_seconds=60))
    monkeypatch.setattr(summaries, "SUMMARY_STREAM_LIMITER", ActiveStreamLimiter(limit=4))
    with SessionLocal() as db:
        user = User(email=f"durable-route-{uuid4().hex}@example.test")
        db.add(user)
        db.commit()
        user_id = user.id
    actor = SimpleNamespace(id=user_id, is_pro=False, subscription=None, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: actor
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    real_observer = jobs.observe_job

    async def first_frame(view):
        # HTTP clients below observe one real frame; no fake generation runs in their request.
        async with aclosing(real_observer(view)) as observer:
            yield await anext(observer)

    monkeypatch.setattr(jobs, "observe_job", first_frame)
    capture = MagicMock()
    monkeypatch.setattr(evidence_module, "capture_funnel_event", capture)
    yield SimpleNamespace(actor=actor, enqueue=enqueue, capture=capture, real_observer=real_observer)
    app.dependency_overrides.pop(get_current_user, None)
    assert summaries.SUMMARY_STREAM_LIMITER._active == {}
    with SessionLocal() as db:
        db.query(SummaryJob).filter_by(user_id=user_id).delete()
        db.commit()


def route(fid):
    return f"/api/summaries/filing/{fid}/generate-stream"


def frames(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_create_join_worker_completion_and_reconnect_share_one_job_and_creation_charge(boundary):
    fid = seed_company_filing()
    with stream_boundaries() as provider, TestClient(app) as client:
        first = client.post(route(fid))
        joined = client.post(route(fid))
        assert first.status_code == joined.status_code == 200
        assert frames(first)[0]["job_id"] == frames(joined)[0]["job_id"]
        provider.assert_not_called()
        boundary.enqueue.assert_awaited_once()
        assert len(summaries.SUMMARY_LIMITER._hits[f"summary:{boundary.actor.id}"]) == 1
        view = store.read_filing_job(fid)
        assert view.last_dispatched_at is not None
        asyncio.run(jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation}))
        provider.assert_awaited_once()
        completed = client.get(f"/api/summaries/filing/{fid}/progress").json()
        assert completed["stage"] == "completed"
        assert frames(client.post(route(fid)))[-1]["summary_id"] == completed["summary_id"]
        assert client.get(f"/api/summaries/filing/{fid}").json()["id"] == completed["summary_id"]
        boundary.enqueue.assert_awaited_once()


def test_queue_timeout_retains_pending_intent_then_retry_dispatches_same_job_without_new_charge(boundary):
    fid = seed_company_filing()
    boundary.enqueue.side_effect = TimeoutError("private transport text")
    with TestClient(app) as client:
        failed = client.post(route(fid))
        assert failed.status_code == 503 and failed.headers["Retry-After"] == "5"
        assert "private" not in failed.text
        pending = client.get(f"/api/summaries/filing/{fid}/progress").json()
        assert pending["status"] == "dispatch_pending" and pending["stage"] == "pending"
        before = store.read_filing_job(fid)
        assert before.last_dispatched_at is None
        first_key = boundary.enqueue.call_args.kwargs["dedupe_key"]
        boundary.enqueue.side_effect = None
        assert client.post(route(fid)).status_code == 200
        after = store.read_filing_job(fid)
        assert (after.job_id, after.generation) == (before.job_id, before.generation)
        assert after.last_dispatched_at is not None
        assert boundary.enqueue.call_args.kwargs["dedupe_key"] == first_key
        assert len(summaries.SUMMARY_LIMITER._hits[f"summary:{boundary.actor.id}"]) == 1


def test_unacknowledged_false_dispatch_does_not_claim_a_handoff(boundary, monkeypatch):
    fid = seed_company_filing()
    monkeypatch.setattr(jobs, "dispatch_job", AsyncMock(return_value=False))
    with TestClient(app) as client:
        assert client.post(route(fid)).status_code == 503
    assert store.read_filing_job(fid).last_dispatched_at is None


def test_observation_deadline_releases_stream_without_cancelling_durable_job(boundary, monkeypatch):
    fid = seed_company_filing()
    monkeypatch.setattr(settings, "STREAM_TIMEOUT", 0)
    monkeypatch.setattr(jobs, "observe_job", boundary.real_observer)
    with TestClient(app) as client:
        observed = client.post(route(fid) + "?analytics_consent=true")
    assert frames(observed)[-1]["message"] == "The summary is still preparing. Try again to reconnect."
    assert store.read_filing_job(fid).status == "queued"
    assert boundary.capture.call_args.kwargs["reason"] == "observer_timeout"
    assert boundary.capture.call_args.kwargs["summary_service_invoked"] is False


def test_creation_refusal_and_active_cap_cannot_create_durable_work(boundary):
    fid = seed_company_filing()
    key = f"summary:{boundary.actor.id}"
    for _ in range(5):
        summaries.SUMMARY_LIMITER.allow(key)
    with TestClient(app) as client:
        limited = client.post(route(fid))
        assert limited.status_code == 429 and limited.json()["code"] == "summary_rate_limited"
        assert store.read_filing_job(fid) is None
        assert not summaries.SUMMARY_STREAM_LIMITER._active
        held = [summaries.SUMMARY_STREAM_LIMITER.try_acquire(key) for _ in range(4)]
        try:
            assert client.post(route(fid)).status_code == 429
            assert store.read_filing_job(fid) is None
        finally:
            for release in held:
                release()
    boundary.enqueue.assert_not_awaited()


def test_free_force_cannot_refresh_ready_summary_but_can_recover_failed_job_after_cooldown(boundary):
    fid = seed_company_filing()
    with SessionLocal() as db:
        db.add(Summary(filing_id=fid, business_overview="A ready grounded summary."))
        db.commit()
    with TestClient(app) as client:
        assert client.post(route(fid) + "?force=true").status_code == 403
        assert store.read_filing_job(fid) is None
        failed_id = seed_company_filing()
        view = store.ensure_job(failed_id, boundary.actor.id)
        lease = store.claim_job(view.job_id, view.generation)
        store.finish_job(lease, {"type": "error", "retryable": False})
        refused = client.post(route(failed_id) + "?retry_failed=true")
        assert refused.status_code == 429 and int(refused.headers["Retry-After"]) > 0
        with SessionLocal() as db:
            db.get(SummaryJob, view.job_id).next_attempt_at = utcnow() - timedelta(seconds=1)
            db.commit()
        assert frames(client.post(route(failed_id)))[-1]["type"] == "error"
        assert store.read_filing_job(failed_id).generation == view.generation
        boundary.enqueue.assert_not_awaited()
        assert client.post(route(failed_id) + "?retry_failed=true").status_code == 200
        reopened = store.read_filing_job(failed_id)
        assert reopened.job_id == view.job_id and reopened.generation == view.generation + 1
        with SessionLocal() as db:
            assert db.get(SummaryJob, view.job_id).force is False


@pytest.mark.parametrize("state", ["queued", "running", "retry_wait", "complete", "partial"])
def test_progress_ignores_old_summary_and_stale_legacy_progress_until_matching_result(boundary, state):
    fid = seed_company_filing()
    view = store.ensure_job(fid, boundary.actor.id)
    with SessionLocal() as db:
        old = Summary(filing_id=fid, business_overview="A retained prior summary.")
        db.add(old)
        db.add(SummaryGenerationProgress(filing_id=fid, stage="error", error="old failure"))
        job = db.get(SummaryJob, view.job_id)
        job.status, job.stage = state, "fetching"
        job.last_dispatched_at = utcnow()
        db.commit()
    with TestClient(app) as client:
        answer = client.get(f"/api/summaries/filing/{fid}/progress").json()
    assert answer["stage"] == ("error" if state in {"complete", "partial"} else "fetching")
    assert "summary_id" not in answer
    assert answer["job_id"] == view.job_id


@pytest.mark.asyncio
async def test_disconnect_closes_observer_only_and_worker_can_still_finish(boundary, monkeypatch):
    fid = seed_company_filing()
    monkeypatch.setattr(jobs, "observe_job", boundary.real_observer)
    request = SimpleNamespace(client=None)
    with SessionLocal() as db:
        response = await summaries.generate_summary_stream(
            fid, request, current_user=boundary.actor, db=db, analytics_consent=True,
            logical_request_id=None, client_attempt=None, transport_attempt=None,
        )

    async def receive():
        return {"type": "http.request"}

    async def disconnected_send(message):
        if message["type"] == "http.response.body":
            raise ClientDisconnect()

    with pytest.raises(ClientDisconnect):
        await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, disconnected_send)
    view = store.read_filing_job(fid)
    assert view.status == "queued"
    event = boundary.capture.call_args.kwargs
    assert event["outcome"] == "cancelled" and event["reason"] == "observer_disconnected"
    assert event["generation_ownership"] == "durable_worker"
    with stream_boundaries() as provider:
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
    provider.assert_awaited_once()
    assert store.read_filing_job(fid).status == "complete"


@pytest.mark.parametrize("flag", ["SUMMARY_DURABLE_GENERATION_ENABLED", "DURABLE_TASKS_ENABLED"])
def test_disabled_ownership_retains_legacy_but_missing_task_delivery_fails_closed(boundary, monkeypatch, flag):
    monkeypatch.setattr(settings, flag, False)
    fid = seed_company_filing()
    with stream_boundaries() as provider, TestClient(app) as client:
        response = client.post(route(fid))
        if flag == "SUMMARY_DURABLE_GENERATION_ENABLED":
            assert frames(response)[-1]["type"] == "complete"
            provider.assert_awaited_once()
        else:
            assert response.status_code == 503 and response.json()["code"] == "generation_paused"
            provider.assert_not_awaited()
    boundary.enqueue.assert_not_awaited()
    assert store.read_filing_job(fid) is None
