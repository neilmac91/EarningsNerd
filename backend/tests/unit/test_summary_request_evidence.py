"""Request evidence must conserve outcomes without changing the locked SSE contract."""
import asyncio
from contextlib import aclosing
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal, engine
from app.models import Base, Summary
from app.routers.auth import get_current_user
from app.services import summary_pipeline as pipeline
from app.services import summary_request_evidence as evidence_module
from app.services.summary_request_evidence import SummaryRequestEvidence
from main import app
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries


@pytest.fixture(autouse=True)
def boundary(monkeypatch):
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    capture = MagicMock()
    monkeypatch.setattr(evidence_module, "capture_funnel_event", capture)
    monkeypatch.setattr(pipeline, "capture_funnel_event", capture)
    stand_in = SimpleNamespace(id=987654321, is_pro=False, subscription=None,
                               email="evidence@example.com", is_active=True)
    app.dependency_overrides[get_current_user] = lambda: stand_in
    # Rate limiting is exercised separately below without sharing buckets across tests.
    from app.routers import summaries
    summaries.SUMMARY_LIMITER._hits.clear()
    yield capture
    app.dependency_overrides.pop(get_current_user, None)
    reset_inflight()


def observations(capture):
    return [(call.args[1], call.kwargs) for call in capture.call_args_list
            if call.args[1].startswith("summary_request_")]


def terminal(capture):
    events = observations(capture)
    assert [event for event, _ in events] == ["summary_request_started", "summary_request_finished"]
    assert events[0][1]["request_id"] == events[1][1]["request_id"]
    assert events[1][1]["duration_ms"] >= 0
    return events[1][1]


def evidence(filing_id):
    return SummaryRequestEvidence(consent=True, account_id=17, filing_id=filing_id,
                                  logical_request_id=uuid4(), client_attempt=1,
                                  transport_attempt=1, entry_point=None)


async def consume_pipeline(fid, item, *, current_user=None):
    async def frames():
        async with aclosing(pipeline.stream_filing_summary(
            filing_id=fid, current_user=current_user, user_id=None,
            telemetry_distinct_id="17", telemetry_entry_point=None, telemetry_ctx={},
            emit_funnel_telemetry=False, request_evidence=item,
        )) as events:
            async for event in events:
                item.observe_terminal(event)
                yield event
    return [frame async for frame in item.wrap_stream(frames())]


def test_real_route_fresh_and_cached_requests_use_server_identity_and_unique_ids(boundary):
    fid, action = seed_company_filing(), str(uuid4())
    query = f"analytics_consent=true&logical_request_id={action}&client_attempt=1&transport_attempt=2&ph_id=someone-else"
    with stream_boundaries(), TestClient(app) as client:
        response = client.post(f"/api/summaries/filing/{fid}/generate-stream?{query}")
        assert response.status_code == 200
        fresh = terminal(boundary)
        assert fresh["outcome"] == "complete"
        assert fresh["delivery_path"] == "generation"
        assert fresh["summary_service_invoked"] is True
        assert fresh["logical_request_id"] == action
        assert fresh["account_id_at_event"] == "987654321"
        assert fresh["transport_attempt"] == 2
        assert all(call.args[0] == "987654321" for call in boundary.call_args_list)
        boundary.reset_mock()
        assert client.post(f"/api/summaries/filing/{fid}/generate-stream?{query}").status_code == 200
        cached = terminal(boundary)
        assert cached["delivery_path"] == "router_cache"
        assert cached["summary_service_invoked"] is False
        assert cached["summary_id"] == fresh["summary_id"]
        assert cached["request_id"] != fresh["request_id"]


@pytest.mark.parametrize("query", ["", "?analytics_consent=false&ph_id=someone-else"])
def test_real_route_requires_explicit_consent_for_request_and_legacy_events(boundary, query):
    fid = seed_company_filing()
    with stream_boundaries(), TestClient(app) as client:
        assert client.post(f"/api/summaries/filing/{fid}/generate-stream{query}").status_code == 200
        assert client.post(f"/api/summaries/filing/{fid}/generate-stream{query}").status_code == 200
    boundary.assert_not_called()


@pytest.mark.parametrize("failure", ["missing", "force", "rate_limit"])
def test_route_rejections_have_one_terminal(boundary, monkeypatch, failure):
    from app.routers import summaries
    from fastapi import HTTPException
    fid = seed_company_filing()
    query = "?analytics_consent=true"
    expected = 404
    if failure == "missing":
        fid = 2_000_000_000
    elif failure == "force":
        with SessionLocal() as db:
            db.add(Summary(filing_id=fid, business_overview="cached"))
            db.commit()
        query += "&force=true"
        expected = 403
    else:
        def reject(*args, **kwargs):
            raise HTTPException(status_code=429, detail="Limited")
        monkeypatch.setattr(summaries, "enforce_rate_limit", reject)
        expected = 429
    with TestClient(app) as client:
        assert client.post(f"/api/summaries/filing/{fid}/generate-stream{query}").status_code == expected
    result = terminal(boundary)
    assert result["outcome"] == "rejected"
    assert result["reason"] == f"http_{expected}"
    assert result["summary_service_invoked"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["pipeline_cache", "coalesced", "timeout", "quota", "fair_use", "generated_error"])
async def test_real_pipeline_outcome_paths(boundary, monkeypatch, mode):
    fid = seed_company_filing()
    item = evidence(fid)
    item.delivery_path = "pipeline"
    current_user = None
    leader = None
    if mode == "pipeline_cache":
        with SessionLocal() as db:
            db.add(Summary(filing_id=fid, business_overview="cached"))
            db.commit()
    elif mode in {"coalesced", "timeout"}:
        leader = pipeline._claim_inflight(fid)
        if mode == "timeout":
            monkeypatch.setattr(pipeline, "INFLIGHT_WAIT_CAP_SECONDS", 0)
        else:
            original = pipeline.run_in_threadpool
            async def complete_leader(func, *args, **kwargs):
                result = await original(func, *args, **kwargs)
                if func.__name__ == "get_filing_and_summary_sync":
                    with SessionLocal() as db:
                        db.add(Summary(filing_id=fid, business_overview="leader"))
                        db.commit()
                    leader.set()
                return result
            monkeypatch.setattr(pipeline, "run_in_threadpool", complete_leader)
    elif mode in {"quota", "fair_use"}:
        current_user = SimpleNamespace(id=17)
        monkeypatch.setattr(pipeline, "_check_usage_and_plan",
                            lambda *_: (False, 10, 10, mode == "fair_use", None))
    payload = {"status": "error", "message": "offline failure"} if mode == "generated_error" else None
    try:
        with stream_boundaries(payload=payload) as generate:
            frames = await consume_pipeline(fid, item, current_user=current_user)
            result = terminal(boundary)
            if mode in {"pipeline_cache", "coalesced"}:
                assert frames[-1]["type"] == result["outcome"] == "complete"
                assert result["delivery_path"] == mode
                assert result["summary_id"] == frames[-1]["summary_id"]
            elif mode == "timeout":
                assert result["outcome"] == "timed_out"
                assert result["delivery_path"] == "coalesced"
            else:
                assert result["outcome"] == "error"
                if mode != "generated_error":
                    assert result["reason"] == ("monthly_quota" if mode == "quota" else "fair_use")
            assert result["summary_service_invoked"] is (mode == "generated_error")
            if mode != "generated_error":
                generate.assert_not_called()
    finally:
        if leader:
            pipeline._release_inflight(fid, leader)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["cancelled", "closed", "incomplete", "complete_then_closed"])
async def test_stream_exit_conserves_terminal_and_closes_producer(boundary, mode):
    item = evidence(1)
    closed = False
    async def producer():
        nonlocal closed
        try:
            if mode == "complete_then_closed":
                item.observe_terminal({"type": "complete", "summary_id": 3})
            yield "frame"
            if mode == "cancelled":
                raise asyncio.CancelledError
        finally:
            closed = True
    stream = item.wrap_stream(producer())
    await anext(stream)
    if mode in {"closed", "complete_then_closed"}:
        await stream.aclose()
    elif mode == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            await anext(stream)
    else:
        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    result = terminal(boundary)
    assert result["outcome"] == {"closed": "cancelled", "complete_then_closed": "complete"}.get(mode, mode)
    assert closed


@pytest.mark.asyncio
@pytest.mark.parametrize("spec", ["2.3", "2.4"])
@pytest.mark.parametrize("stop", ["start", "body", "terminal_body", "unexpected_error"])
async def test_actual_response_closes_at_send_boundary_before_return(boundary, spec, stop):
    from app.routers.summaries import SummaryStreamResponse
    from starlette.requests import ClientDisconnect

    item = evidence(1)
    item.start()
    send_blocked = asyncio.Event()
    producer_closed, provider_closed = [], []
    provider = None

    async def provider_work():
        try:
            await asyncio.Event().wait()
        finally:
            provider_closed.append(True)

    async def producer():
        nonlocal provider
        provider = asyncio.create_task(provider_work())
        await asyncio.sleep(0)
        try:
            if stop == "terminal_body":
                item.observe_terminal({"type": "complete", "summary_id": 3})
            yield "data: {}\n\n"
            await asyncio.Event().wait()
        finally:
            provider.cancel()
            await asyncio.gather(provider, return_exceptions=True)
            producer_closed.append(True)

    async def send(message):
        target = "http.response.start" if stop == "start" else "http.response.body"
        if message["type"] == target:
            send_blocked.set()
            if stop == "unexpected_error":
                raise RuntimeError("offline unexpected send failure")
            if spec == "2.4":
                raise OSError("offline disconnected socket")
            await asyncio.Event().wait()

    async def receive():
        await send_blocked.wait()
        return {"type": "http.disconnect"}

    response = SummaryStreamResponse(producer(), item)
    try:
        call = response({"type": "http", "asgi": {"spec_version": spec}}, receive, send)
        if stop == "unexpected_error":
            with pytest.raises(RuntimeError, match="offline unexpected"):
                await asyncio.wait_for(call, 2)
        elif spec == "2.4":
            with pytest.raises(ClientDisconnect):
                await asyncio.wait_for(call, 2)
        else:
            await asyncio.wait_for(call, 2)
        result = terminal(boundary)
        expected = {"terminal_body": "complete", "unexpected_error": "error"}.get(stop, "cancelled")
        assert result["outcome"] == expected
        if stop != "start":
            assert provider_closed == producer_closed == [True]
            assert provider.done()
        else:
            assert provider is None
    finally:
        # Fault injection must also clean up; assertions above run before this cleanup.
        await response.owned_stream.aclose()
