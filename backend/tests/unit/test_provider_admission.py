"""E09b: one process-wide admission gate in front of every provider wire call.

Locks: (1) at most AI_PROVIDER_MAX_INFLIGHT requests reach the wire concurrently across the
summary and chat paths; (2) a chat stream holds its slot for its whole life and releases it on
the consumer's aclose(); (3) a wait is bounded by the caller's own budget, counted as rejected,
makes no wire call and leaks no slot. Requests are offline (mock transports on the real SDK).
"""
import asyncio

import httpx2
import pytest

from app.config import settings
from app.services.ai import provider_admission, provider_requests as requests
from tests.unit.test_provider_resilience import KW, chunk, completion, event, service_for


@pytest.fixture(autouse=True)
def fresh_gate(monkeypatch):
    provider_admission.reset()
    monkeypatch.setattr(requests, "retry_delay", lambda *args: 0)
    yield
    provider_admission.reset()


def _blocked_stream(entered: asyncio.Event, release: asyncio.Event, closed: list):
    class Blocked(httpx2.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await release.wait()
            yield event(chunk("ok"))
            yield b"data: [DONE]\n\n"

        async def aclose(self):
            closed.append(True)

    return Blocked()


@pytest.mark.asyncio
async def test_limit_holds_the_second_request_off_the_wire_until_the_first_releases(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_MAX_INFLIGHT", 1)
    calls, closed = [], []
    entered, release = asyncio.Event(), asyncio.Event()

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                                   stream=_blocked_stream(entered, release, closed))
        return httpx2.Response(200, json=completion())

    async with service_for(handler) as service:
        first = asyncio.create_task(service._request_content(KW, stream_cb=lambda _: None))
        await entered.wait()
        second = asyncio.create_task(service._request_content(KW))
        await asyncio.sleep(0.05)
        assert len(calls) == 1, "second request must not reach the wire while the slot is held"
        snap = provider_admission.snapshot()
        assert (snap["in_flight"], snap["waiting"], snap["admitted"], snap["rejected"]) == (1, 1, 1, 0)
        release.set()
        assert await first == "ok"
        assert await second == '{"fresh":true}'
    assert len(calls) == 2
    snap = provider_admission.snapshot()
    assert (snap["in_flight"], snap["waiting"], snap["admitted"], snap["peak_in_flight"]) == (0, 0, 2, 1)


@pytest.mark.asyncio
async def test_chat_stream_holds_its_slot_until_the_consumer_closes_it(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_MAX_INFLIGHT", 1)
    calls, closed = [], []
    entered, release = asyncio.Event(), asyncio.Event()

    class Trickle(httpx2.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            yield event(chunk("first"))
            await release.wait()
            yield event(chunk("second"))
            yield b"data: [DONE]\n\n"

        async def aclose(self):
            closed.append(True)

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=Trickle())
        return httpx2.Response(200, json=completion())

    async with service_for(handler) as service:
        chat = service.stream_chat([{"role": "user", "content": "hi"}])
        assert await chat.__anext__() == "first"
        summary = asyncio.create_task(service._request_content(KW))
        await asyncio.sleep(0.05)
        assert len(calls) == 1, "an open chat stream holds the only slot"
        assert provider_admission.snapshot()["waiting"] == 1
        await chat.aclose()  # the consumer walks away mid-stream
        assert closed == [True]
        assert await summary == '{"fresh":true}'
    assert len(calls) == 2
    assert provider_admission.snapshot()["in_flight"] == 0


@pytest.mark.asyncio
async def test_wait_is_bounded_by_the_budget_and_leaks_no_slot(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_MAX_INFLIGHT", 1)
    calls, closed = [], []
    entered, release = asyncio.Event(), asyncio.Event()

    def handler(req):
        calls.append(req)
        if len(calls) == 1:
            return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                                   stream=_blocked_stream(entered, release, closed))
        return httpx2.Response(200, json=completion())

    async with service_for(handler) as service:
        holder = asyncio.create_task(service._request_content(KW, stream_cb=lambda _: None))
        await entered.wait()
        monkeypatch.setattr(requests, "SUMMARY_SECONDS", 0.05)  # the waiter's budget only
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(service._request_content(KW), timeout=2.0)
        assert len(calls) == 1, "a rejected wait never touches the wire"
        snap = provider_admission.snapshot()
        assert snap["rejected"] == 1 and snap["waiting"] == 0 and snap["in_flight"] == 1
        release.set()
        assert await holder == "ok"
        assert provider_admission.snapshot()["in_flight"] == 0
        monkeypatch.setattr(requests, "SUMMARY_SECONDS", 5.0)
        assert await service._request_content(KW) == '{"fresh":true}'
    assert len(calls) == 2


def test_zero_disables_the_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "AI_PROVIDER_MAX_INFLIGHT", 0)
    assert provider_admission.limit() == 2**31
