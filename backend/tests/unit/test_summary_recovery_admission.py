"""REGN recovery: ready reads/followers bypass creation limits; new owners never do."""
import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.error_codes import ErrorCode, sse_error
from app.models import Base, Summary, SummaryGenerationProgress
from app.routers import summaries
from app.routers.auth import get_current_user
from app.services import summary_pipeline as pipeline
from app.services.edgar.exceptions import EdgarError, EdgarRateLimitError
from app.services.rate_limiter import RateLimiter
from app.services.summary_request_evidence import SummaryRequestEvidence
from main import app
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries


@pytest.fixture(autouse=True)
def boundary():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    user = SimpleNamespace(id=987654321, is_pro=False, subscription=None,
                           email="recovery@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)
    reset_inflight()


def frames(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def exhaust_creation(user):
    for _ in range(summaries.SUMMARY_LIMITER.limit):
        assert summaries.SUMMARY_LIMITER.allow(f"summary:{user.id}")


@pytest.mark.parametrize("pro", [False, True])
def test_ready_replay_survives_creation_cooldown_without_spending_a_generation(boundary, pro):
    boundary.is_pro = pro
    filing_id = seed_company_filing()
    with SessionLocal() as session:
        session.add(Summary(filing_id=filing_id, business_overview="A ready filing summary."))
        session.commit()
    exhaust_creation(boundary)
    with stream_boundaries() as provider, TestClient(app) as client:
        response = client.post(f"/api/summaries/filing/{filing_id}/generate-stream")
    assert response.status_code == 200
    assert frames(response)[-1]["type"] == "complete"
    provider.assert_not_called()


def test_new_work_is_refused_before_usage_reservation_or_source_fetch(boundary, monkeypatch):
    filing_id = seed_company_filing()
    exhaust_creation(boundary)
    usage = MagicMock(side_effect=AssertionError("refused work reserved quota"))
    monkeypatch.setattr(pipeline, "_check_usage_and_plan", usage)
    with stream_boundaries() as provider, TestClient(app) as client:
        source = pipeline.sec_edgar_service.get_filing_document
        response = client.post(f"/api/summaries/filing/{filing_id}/generate-stream")
    terminal = frames(response)[-1]
    assert terminal["type"] == "error"
    assert terminal["message"] == "Too many summary requests. Try again shortly."
    assert terminal["code"] == "summary_rate_limited"
    assert 1 <= terminal["retry_after_seconds"] <= 60
    assert terminal["request_id"]
    source.assert_not_called()
    provider.assert_not_called()
    usage.assert_not_called()
    assert filing_id not in pipeline._inflight_generations


def test_replay_still_has_independent_request_abuse_protection(boundary, monkeypatch):
    monkeypatch.setattr(summaries, "SUMMARY_REQUEST_LIMITER", RateLimiter(limit=2, window_seconds=60))
    filing_id = seed_company_filing()
    with SessionLocal() as session:
        session.add(Summary(filing_id=filing_id, business_overview="A ready filing summary."))
        session.commit()
    with TestClient(app) as client:
        route = f"/api/summaries/filing/{filing_id}/generate-stream"
        assert client.post(route).status_code == 200
        assert client.post(route).status_code == 200
        refused = client.post(route)
    assert refused.status_code == 429
    assert refused.json()["code"] == "summary_rate_limited"
    assert 1 <= int(refused.headers["Retry-After"]) <= 60
    assert not summaries.SUMMARY_LIMITER._hits


@pytest.mark.asyncio
async def test_concurrent_follower_joins_even_when_leader_spent_last_creation_slot(boundary, monkeypatch):
    monkeypatch.setattr(summaries, "SUMMARY_LIMITER", RateLimiter(limit=1, window_seconds=60))
    filing_id = seed_company_filing()
    fetching, release_fetch, joined = asyncio.Event(), asyncio.Event(), asyncio.Event()
    real_info = pipeline.logger.info

    def observe_join(message, *args, **kwargs):
        if "Joining in-flight generation" in message:
            joined.set()
        real_info(message, *args, **kwargs)

    async def fetch(*args, **kwargs):
        fetching.set()
        await release_fetch.wait()
        return "FILING DOCUMENT TEXT " * 40

    monkeypatch.setattr(pipeline.logger, "info", observe_join)
    tasks = []
    with stream_boundaries() as provider, monkeypatch.context() as local_patch:
        local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(side_effect=fetch))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            route = f"/api/summaries/filing/{filing_id}/generate-stream"
            try:
                tasks.append(asyncio.create_task(client.post(route)))
                await asyncio.wait_for(fetching.wait(), 3)
                tasks.append(asyncio.create_task(client.post(route)))
                await asyncio.wait_for(joined.wait(), 3)
                release_fetch.set()
                responses = await asyncio.wait_for(asyncio.gather(*tasks), 3)
                terminals = [frames(response)[-1] for response in responses]
                assert all(item["type"] == "complete" for item in terminals)
                assert terminals[0]["summary_id"] == terminals[1]["summary_id"]
                assert len(summaries.SUMMARY_LIMITER._hits[f"summary:{boundary.id}"]) == 1
                provider.assert_awaited_once()
            finally:
                release_fetch.set()
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_failed_leaders_successor_must_pass_creation_gate(monkeypatch):
    filing_id = seed_company_filing()
    leader = pipeline._claim_inflight(filing_id)
    refuse = MagicMock(return_value=sse_error("Try later", ErrorCode.SUMMARY_RATE_LIMITED))
    with stream_boundaries() as provider:
        events = []
        async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
            admit_generation=refuse,
        ):
            events.append(event)
            if event.get("stage") == "queued":
                refuse.assert_not_called()
                pipeline._release_inflight(filing_id, leader)
    assert events[-1]["code"] == "summary_rate_limited"
    refuse.assert_called_once()
    provider.assert_not_called()
    assert filing_id not in pipeline._inflight_generations


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("status,code", [(429, "sec_rate_limited"), (503, "filing_source_unavailable")])
async def test_source_failure_persists_terminal_and_safe_typed_evidence(monkeypatch, caplog, wrapped, status, code):
    filing_id = seed_company_filing()
    request = httpx.Request("GET", "https://source.invalid/private-url-marker")
    response = httpx.Response(status, headers={"Retry-After": "73"}, request=request)
    error = httpx.HTTPStatusError("private-error-marker", request=request, response=response)
    if wrapped:
        error = EdgarError("private-wrapper-marker", cause=error)
    item = SummaryRequestEvidence(consent=False, account_id=987654321, filing_id=filing_id,
                                  logical_request_id=None, client_attempt=None, transport_attempt=None,
                                  entry_point="private-entry-marker")
    capture = MagicMock()
    monkeypatch.setattr("app.services.summary_request_evidence.capture_funnel_event", capture)
    caplog.set_level(logging.INFO)
    with stream_boundaries() as provider, monkeypatch.context() as local_patch:
        local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(side_effect=error))
        events = [event async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False, request_evidence=item,
        )]
    item.observe_terminal(events[-1])
    terminal = events[-1]
    assert terminal["code"] == code
    assert terminal["retry_after_seconds"] == 73
    assert terminal["request_id"] == item.properties["request_id"]
    assert item.reason == code
    with SessionLocal() as session:
        progress = session.query(SummaryGenerationProgress).filter_by(filing_id=filing_id).one()
        assert (progress.stage, progress.error) == ("error", code)
    provider.assert_not_called()
    capture.assert_not_called()
    diagnostic = "\n".join(record.getMessage() for record in caplog.records
                           if "Source fetch failed" in record.getMessage()
                           or "summary_request_finished" in record.getMessage())
    assert f"upstream_status={status}" in diagnostic
    assert "summary_service_invoked=False" in diagnostic
    for private in ("private-url-marker", "private-error-marker", "private-wrapper-marker",
                    "private-entry-marker", "987654321"):
        assert private not in diagnostic


def test_source_failure_uses_new_transport_cooldown_without_httpx_cause():
    from app.services.summary_stages.failure import _source_failure_details

    error = EdgarRateLimitError(retry_after=181, context={"status_code": 429})
    code, status, kind, delay = _source_failure_details(error)
    assert (code.value, status, kind, delay) == ("sec_rate_limited", 429, "EdgarRateLimitError", 181)
