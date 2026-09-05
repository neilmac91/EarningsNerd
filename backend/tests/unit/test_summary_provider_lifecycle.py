"""Drive the real summary generator against an owned blocked SDK stream, without live I/O."""

import asyncio
from contextlib import suppress

import httpx2
import pytest

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
