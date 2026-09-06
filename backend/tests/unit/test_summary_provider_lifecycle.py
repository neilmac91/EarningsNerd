"""Drive the real summary generator against an owned blocked SDK stream, without live I/O."""

import asyncio
from contextlib import suppress
from copy import deepcopy
import threading
from types import SimpleNamespace

import httpx2
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings
from app.services import summary_pipeline as pipeline
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries
from tests.unit.test_provider_resilience import KW, service_for


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["close", "cancel", "timeout", "service_timeout"])
async def test_pipeline_stops_owned_sdk_task_before_releasing_slot(stop, monkeypatch):
    from app.services.ai import provider_requests
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    original_summary = pipeline.openai_service.summarize_filing
    original_heartbeat = settings.STREAM_HEARTBEAT_INTERVAL
    reset_inflight()
    filing_id = seed_company_filing()
    entered, closed, calls = asyncio.Event(), [], []
    release = pipeline._release_inflight

    def checked_release(*args):
        assert closed, "provider stream must close before releasing generation leadership"
        return release(*args)

    monkeypatch.setattr(pipeline, "_release_inflight", checked_release)

    class Blocked(httpx2.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            closed.append(True)

    def handler(req):
        calls.append(req)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Blocked())

    async with service_for(handler) as service:

        async def generate(*args, **kwargs):
            await service._request_content(KW, stream_cb=lambda _: None)
            raise AssertionError("blocked request returned")

        service.generate_structured_summary = generate
        with stream_boundaries(), monkeypatch.context() as patch:
            patch.setattr(pipeline.openai_service, "summarize_filing", service.summarize_filing)
            patch.setattr(settings, "STREAM_HEARTBEAT_INTERVAL", 0.01)
            if stop == "service_timeout":
                patch.setattr(provider_requests, "SUMMARY_SECONDS", 0.04)
                patch.setattr(
                    pipeline, "generate_xbrl_summary", lambda **kwargs: {**CANONICAL_PAYLOAD, "status": "partial"}
                )
            if stop == "timeout":
                patch.setattr(pipeline, "PIPELINE_TIMEOUT_SECONDS", 0.12)
            gen = pipeline.stream_filing_summary(
                filing_id=filing_id,
                current_user=None,
                user_id=None,
                telemetry_distinct_id="offline",
                telemetry_entry_point="offline",
                telemetry_ctx={},
            )
            try:
                # Advance until the provider has started and the generator yields a heartbeat.
                while True:
                    frame = await anext(gen)
                    if entered.is_set() and frame.get("stage") == "summarizing":
                        break
                if stop == "close":
                    await gen.aclose()
                elif stop == "cancel":
                    task = asyncio.create_task(anext(gen))
                    await asyncio.sleep(0)
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                else:
                    frames = [frame async for frame in gen]
                    expected = "partial" if stop == "service_timeout" else "error"
                    assert any(frame["type"] == expected for frame in frames)
                assert closed and len(calls) == 1
                assert filing_id not in pipeline._inflight_generations
            finally:
                with suppress(RuntimeError):
                    await gen.aclose()
                reset_inflight()

    # Exercise fixture teardown too: outer monkeypatch must not restore the harness's mocks.
    monkeypatch.undo()
    assert pipeline.openai_service.summarize_filing == original_summary
    assert settings.STREAM_HEARTBEAT_INTERVAL == original_heartbeat


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["provider", "follower", "semaphore", "background", "route", "cached_route", "db_worker"])
@pytest.mark.parametrize("stop", ["complete", "cancel"])
async def test_generation_waits_release_database_connections(boundary, stop, tmp_path, monkeypatch):
    """A one-connection pool remains available while generation/streaming is suspended."""
    from app import database
    from app.models import Base, Summary
    from app.routers import summaries
    from app.routers.auth import get_current_user
    from app.services import summary_generation_service as background
    from main import app
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD
    import httpx

    engine = create_engine(
        f"sqlite:///{tmp_path / 'lifetime.db'}", connect_args={"check_same_thread": False},
        poolclass=QueuePool, pool_size=1, max_overflow=0, pool_timeout=0.05,
    )
    Base.metadata.create_all(engine)
    ownership_errors = []
    block_next_query = False
    query_entered, query_finish, query_closed = (threading.Event() for _ in range(3))

    class OwnedSession(Session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.owner = threading.get_ident()
            self.blocked = False

        def execute(self, *args, **kwargs):
            nonlocal block_next_query
            result = super().execute(*args, **kwargs)
            if block_next_query:
                block_next_query = False
                self.blocked = True
                query_entered.set()
                assert query_finish.wait(2), "test did not release the DB worker"
            return result

        def close(self):
            if self.owner != threading.get_ident():
                ownership_errors.append((self.owner, threading.get_ident()))
            super().close()
            if self.blocked:
                query_closed.set()

    sessions = sessionmaker(bind=engine, class_=OwnedSession)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(background, "SessionLocal", sessions)
    filing_id = seed_company_filing()
    ready, finish = asyncio.Event(), asyncio.Event()
    events = []
    reset_inflight()
    leader = pipeline._claim_inflight(filing_id) if boundary == "follower" else None

    class QueuedSemaphore(asyncio.Semaphore):
        async def acquire(self):
            ready.set()
            return await super().acquire()

    semaphore = QueuedSemaphore(0)
    if boundary == "semaphore":
        monkeypatch.setattr(pipeline, "_get_generation_semaphore", lambda: semaphore)

    async def blocked_provider(*args, **kwargs):
        ready.set()
        await finish.wait()
        return deepcopy(CANONICAL_PAYLOAD)

    async def consume():
        if boundary == "background":
            await background.generate_summary_background(filing_id, None)
        else:
            async for frame in pipeline.stream_filing_summary(
                filing_id=filing_id, current_user=None, user_id=None,
                telemetry_distinct_id="offline", telemetry_entry_point=None, telemetry_ctx={},
            ):
                events.append(frame)
                if frame.get("stage") == "queued":
                    ready.set()

    old_overrides = app.dependency_overrides.copy()

    async def request_db():
        with sessions() as db:
            yield db

    async def checked_app(scope, receive, send):
        async def checked_send(message):
            if message["type"] == "http.response.start":
                assert engine.pool.checkedout() == 0, "request transaction survived into SSE"
                if boundary == "cached_route":
                    ready.set()
                    await finish.wait()
            await send(message)
        await app(scope, receive, checked_send)

    async def request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=checked_app), base_url="http://test") as client:
            response = await client.post(f"/api/summaries/filing/{filing_id}/generate-stream")
            assert response.status_code == 200
            assert '"type": "complete"' in response.text

    if boundary in {"route", "cached_route"}:
        app.dependency_overrides[database.get_db] = request_db
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
            id=987654321, is_pro=False, subscription=None, email="offline@example.com", is_active=True,
        )
        monkeypatch.setattr(summaries, "enforce_rate_limit", lambda *a, **k: None)
    if boundary == "cached_route":
        with sessions() as db:
            db.add(Summary(filing_id=filing_id, business_overview="STORED"))
            db.commit()

    task = None
    try:
        with stream_boundaries(), monkeypatch.context() as patch:
            patch.setattr(pipeline.openai_service, "summarize_filing", blocked_provider)
            patch.setattr(settings, "STREAM_HEARTBEAT_INTERVAL", 0.01)
            block_next_query = boundary == "db_worker"
            task = asyncio.create_task(request() if boundary in {"route", "cached_route"} else consume())
            if boundary == "db_worker":
                assert await asyncio.to_thread(query_entered.wait, 2)
                if stop == "cancel":
                    task.cancel()
                    await asyncio.sleep(0)
                    assert not query_closed.is_set(), "coroutine closed a worker's active transaction"
                query_finish.set()
                assert await asyncio.to_thread(query_closed.wait, 2)
                if stop == "cancel":
                    with pytest.raises(asyncio.CancelledError):
                        await task
                    assert engine.pool.checkedout() == 0
                    assert ownership_errors == []
                    return
            await asyncio.wait_for(ready.wait(), timeout=2)
            assert engine.pool.checkedout() == 0, f"{boundary} retained a DB connection"
            with sessions() as independent:
                assert independent.execute(text("SELECT 1")).scalar_one() == 1
            if stop == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                if leader is not None:
                    with sessions() as db:
                        db.add(Summary(filing_id=filing_id, business_overview="LEADER"))
                        db.commit()
                    pipeline._release_inflight(filing_id, leader)
                if boundary == "semaphore":
                    semaphore.release()
                finish.set()
                await asyncio.wait_for(task, timeout=2)
                with sessions() as db:
                    assert db.query(Summary).filter_by(filing_id=filing_id).count() == 1
            assert engine.pool.checkedout() == 0
            assert ownership_errors == [], "session cleanup moved outside its owning worker"
    finally:
        finish.set()
        query_finish.set()
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        reset_inflight()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        engine.dispose()
