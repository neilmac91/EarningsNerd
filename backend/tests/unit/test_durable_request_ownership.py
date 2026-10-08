"""Durable handoffs stop local work; summary enrichment never outlives its request."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import settings
from app.routers import analysis
from app.services import summary_pipeline as pipeline
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries


@pytest.fixture(autouse=True)
def durable_ownership_mode(monkeypatch):
    """Exercise the new ownership policy only in the explicitly enabled rollout."""
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)


@pytest.fixture
def coverage_request(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = None
    company = SimpleNamespace(id=51, ticker="TEST", name="Test company")
    monkeypatch.setattr(analysis, "_get_company", lambda *_: company)
    monkeypatch.setattr(analysis, "enforce_rate_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        analysis.trend_analysis_service, "available_periods",
        lambda *_: {"annual": [], "quarterly": []},
    )
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(analysis, "COVERAGE_SYNC_WAIT_SECONDS", 0.01)
    return {"ticker": "TEST", "request": SimpleNamespace(), "current_user": SimpleNamespace(id=1), "db": db}


@pytest.mark.asyncio
async def test_coverage_handoff_stops_local_sync_before_durable_acceptance(monkeypatch, coverage_request):
    stopped = asyncio.Event()

    async def stalled(_company_id):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def accept(kind, payload, **kwargs):
        assert stopped.is_set(), "queue delivery must not race an abandoned request attempt"
        assert (kind, payload, kwargs) == (
            "companyfacts", {"company_id": 51},
            {"dedupe_key": "companyfacts:51", "dedupe_seconds": 60},
        )

    enqueue = AsyncMock(side_effect=accept)
    monkeypatch.setattr(analysis, "_ingest_with_own_session", stalled)
    monkeypatch.setattr(analysis, "enqueue_task", enqueue)
    response = await analysis.get_coverage(**coverage_request)
    assert response.syncing is True
    assert response.supported is True
    assert response.synced_at is None
    enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_coverage_enqueue_failure_does_not_claim_syncing(monkeypatch, coverage_request):
    stopped = asyncio.Event()

    async def stalled(_company_id):
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(analysis, "_ingest_with_own_session", stalled)
    monkeypatch.setattr(analysis, "enqueue_task", AsyncMock(side_effect=RuntimeError("queue unavailable")))
    with pytest.raises(RuntimeError, match="queue unavailable"):
        await analysis.get_coverage(**coverage_request)
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_cancelled_coverage_request_stops_ingest_without_enqueue(monkeypatch, coverage_request):
    entered, stopped = asyncio.Event(), asyncio.Event()

    async def stalled(_company_id):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    enqueue = AsyncMock()
    monkeypatch.setattr(analysis, "_ingest_with_own_session", stalled)
    monkeypatch.setattr(analysis, "enqueue_task", enqueue)
    task = asyncio.create_task(analysis.get_coverage(**coverage_request))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_fast_coverage_keeps_ifrs_response_without_enqueue(monkeypatch, coverage_request):
    enqueue = AsyncMock()
    monkeypatch.setattr(
        analysis, "_ingest_with_own_session", AsyncMock(return_value={"unsupported_ifrs": True}),
    )
    monkeypatch.setattr(analysis, "enqueue_task", enqueue)
    response = await analysis.get_coverage(**coverage_request)
    assert response.syncing is False
    assert response.supported is False
    assert response.reason == "ifrs_filer"
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_coverage_follower_keeps_syncing_when_timed_out_leader_hands_off(monkeypatch, coverage_request):
    entered, leader_stopped = asyncio.Event(), asyncio.Event()
    calls = 0

    async def coalesced_ingest(_company_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                leader_stopped.set()
        await leader_stopped.wait()
        return {"waited": True, "synced": False}

    enqueue = AsyncMock()
    monkeypatch.setattr(analysis, "_ingest_with_own_session", coalesced_ingest)
    monkeypatch.setattr(analysis, "enqueue_task", enqueue)
    leader = asyncio.create_task(analysis.get_coverage(**coverage_request))
    await entered.wait()
    # The follower's later deadline lets it observe the leader's cancellation rather than timing
    # out itself; its unsynced result must still join the same durable delivery.
    monkeypatch.setattr(analysis, "COVERAGE_SYNC_WAIT_SECONDS", 1.0)
    follower = asyncio.create_task(analysis.get_coverage(**coverage_request))
    try:
        responses = await asyncio.gather(leader, follower)
        assert all(response.syncing for response in responses)
        assert enqueue.await_count == 2
        assert enqueue.await_args_list[0] == enqueue.await_args_list[1]
    finally:
        for task in (leader, follower):
            if not task.done():
                task.cancel()
        await asyncio.gather(leader, follower, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["document_error", "disconnect"])
async def test_summary_stops_enrichment_before_releasing_leadership(monkeypatch, stop):
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    reset_inflight()
    filing_id = seed_company_filing()
    entered = {name: asyncio.Event() for name in ("xbrl", "sections", "document")}
    stopped = set()
    release = pipeline._release_inflight

    async def blocked(name):
        entered[name].set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.add(name)

    async def document(*_args, **_kwargs):
        entered["document"].set()
        await entered["xbrl"].wait()
        await entered["sections"].wait()
        if stop == "document_error":
            raise RuntimeError("document unavailable")
        await blocked("document")

    def checked_release(*args):
        expected = {"xbrl", "sections"} if stop == "document_error" else set(entered)
        assert expected <= stopped, "request siblings must finish cleanup before leadership releases"
        release(*args)

    async def consume():
        return [event async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None,
            telemetry_distinct_id="offline", telemetry_entry_point=None, telemetry_ctx={},
        )]

    with stream_boundaries(), monkeypatch.context() as patch:
        patch.setattr(settings, "USE_EDGARTOOLS_SECTIONS", True)
        patch.setattr(pipeline.xbrl_service, "get_xbrl_data", lambda *_: blocked("xbrl"))
        patch.setattr(pipeline.xbrl_service, "get_filing_sections", lambda *_: blocked("sections"))
        patch.setattr(pipeline.sec_edgar_service, "get_filing_document", document)
        patch.setattr(pipeline, "_release_inflight", checked_release)
        task = asyncio.create_task(consume())
        try:
            if stop == "disconnect":
                await asyncio.gather(*(event.wait() for event in entered.values()))
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                frames = await task
                assert any(frame["type"] == "error" for frame in frames)
            assert filing_id not in pipeline._inflight_generations
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            reset_inflight()


@pytest.mark.asyncio
async def test_valid_excerpt_cache_does_not_fetch_a_document_for_noop_refresh(monkeypatch):
    from app.database import engine, SessionLocal
    from app.models import Base, FilingContentCache
    from app.utils.datetimes import utcnow

    Base.metadata.create_all(bind=engine)
    reset_inflight()
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        db.add(FilingContentCache(
            filing_id=filing_id, critical_excerpt="Existing accession excerpt",
            created_at=utcnow(), updated_at=utcnow(),
        ))
        db.commit()
    with stream_boundaries(), monkeypatch.context() as patch:
        document = AsyncMock(side_effect=AssertionError("valid excerpt refresh performs no useful write"))
        patch.setattr(pipeline.sec_edgar_service, "get_filing_document", document)
        try:
            frames = [event async for event in pipeline.stream_filing_summary(
                filing_id=filing_id, current_user=None, user_id=None,
                telemetry_distinct_id="offline", telemetry_entry_point=None, telemetry_ctx={},
            )]
            assert any(frame.get("message") == "Cached content found. Loading immediately..." for frame in frames)
            document.assert_not_awaited()
        finally:
            reset_inflight()


@pytest.mark.asyncio
@pytest.mark.parametrize("worker_kind", ["edgar", "sql"])
async def test_summary_disconnect_joins_actual_worker_before_releasing_leadership(monkeypatch, worker_kind):
    from app.database import engine
    from app.models import Base
    from app.services.edgar.async_executor import run_in_executor
    from app.services.request_work import RequestWork, run_owned_sync

    Base.metadata.create_all(bind=engine)
    reset_inflight()
    filing_id = seed_company_filing()
    entered, finish, closed = (threading.Event() for _ in range(3))
    draining = asyncio.Event()
    release = pipeline._release_inflight

    def real_worker():
        entered.set()
        try:
            assert finish.wait(5), "test did not release its controlled synchronous worker"
            return None
        finally:
            closed.set()

    async def xbrl(*_args):
        dispatch = run_in_executor if worker_kind == "edgar" else run_owned_sync
        return await dispatch(real_worker)

    async def document(*_args, **_kwargs):
        await asyncio.Event().wait()

    class CheckedWork(RequestWork):
        async def drain(self):
            draining.set()
            await super().drain()

    def checked_release(*args):
        assert closed.is_set(), "async cancellation abandoned a real running worker"
        release(*args)

    async def consume():
        return [event async for event in pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None,
            telemetry_distinct_id="offline", telemetry_entry_point=None, telemetry_ctx={},
        )]

    with stream_boundaries(), monkeypatch.context() as patch:
        patch.setattr(settings, "USE_EDGARTOOLS_SECTIONS", False)
        patch.setattr(pipeline, "RequestWork", CheckedWork)
        patch.setattr(pipeline.xbrl_service, "get_xbrl_data", xbrl)
        patch.setattr(pipeline.sec_edgar_service, "get_filing_document", document)
        patch.setattr(pipeline, "_release_inflight", checked_release)
        task = asyncio.create_task(consume())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            await asyncio.wait_for(draining.wait(), 2)
            assert not task.done(), "the request ended while its actual worker was still running"
            assert not closed.is_set()
            finish.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
            assert filing_id not in pipeline._inflight_generations
        finally:
            finish.set()
            await asyncio.gather(task, return_exceptions=True)
            reset_inflight()


@pytest.mark.asyncio
async def test_edgar_timeout_is_visible_before_owned_worker_drain():
    from app.services.edgar.async_executor import run_in_executor_with_timeout
    from app.services.edgar.exceptions import EdgarTimeoutError
    from app.services.request_work import request_work_scope

    entered, finish, closed = (threading.Event() for _ in range(3))
    timed_out = asyncio.Event()

    def real_worker():
        entered.set()
        try:
            assert finish.wait(5), "test did not release its controlled synchronous worker"
        finally:
            closed.set()

    async def request():
        async with request_work_scope():
            with pytest.raises(EdgarTimeoutError):
                await run_in_executor_with_timeout(real_worker, timeout=0.01)
            timed_out.set()

    task = asyncio.create_task(request())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.wait_for(timed_out.wait(), 2)
        assert not closed.is_set()
        assert not task.done(), "a timed-out waiter hid a still-running worker from scope cleanup"
        finish.set()
        await asyncio.wait_for(task, 2)
        assert closed.is_set()
    finally:
        finish.set()
        await asyncio.gather(task, return_exceptions=True)
