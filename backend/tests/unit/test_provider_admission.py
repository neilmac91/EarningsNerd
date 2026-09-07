"""E09b: one process-wide admission gate for the chat provider streams.

Locks: (1) at most AI_CHAT_MAX_INFLIGHT chat streams reach the wire concurrently, and a chat
stream holds its slot for its whole life, releasing it on the consumer's aclose(); (2) the
summary path is counted but never queues behind chat; (3) a chat wait is bounded by its own
deadline, counted as rejected, makes no wire call and leaks no slot; (4) time spent waiting for
a slot is not added to the chat's wall-clock budget. Requests are offline (mock transports on
the real SDK).
"""
import asyncio

import httpx2
import pytest

from app.config import settings
from app.services.ai import copilot_chat, provider_admission, provider_requests as requests
from tests.unit.test_provider_resilience import KW, chunk, completion, event, service_for

MESSAGES = [{"role": "user", "content": "hi"}]


@pytest.fixture(autouse=True)
def fresh_gate(monkeypatch):
    provider_admission.reset()
    monkeypatch.setattr(settings, "AI_CHAT_MAX_INFLIGHT", 1)
    monkeypatch.setattr(requests, "retry_delay", lambda *args: 0)
    yield
    provider_admission.reset()


class Trickle(httpx2.AsyncByteStream):
    """First chunk at once, then blocked until `release` (never, by default); closable."""

    def __init__(self, release: asyncio.Event | None = None):
        self.release = release or asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        yield event(chunk("first"))
        await self.release.wait()
        yield event(chunk("second"))
        yield b"data: [DONE]\n\n"

    async def aclose(self):
        self.closed = True


def _handler(calls, streams):
    def handler(req):
        calls.append(req)
        response = streams[len(calls) - 1]
        if isinstance(response, Trickle):
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=response)
        return httpx2.Response(200, json=response)

    return handler


async def _first(chat):
    return await asyncio.wait_for(chat.__anext__(), timeout=2.0)


@pytest.mark.asyncio
async def test_chat_limit_holds_the_second_stream_off_the_wire_until_the_first_closes():
    calls, holder, follower = [], Trickle(), Trickle()
    async with service_for(_handler(calls, [holder, follower])) as service:
        first = service.stream_chat(MESSAGES)
        assert await _first(first) == "first"
        second = service.stream_chat(MESSAGES)
        task = asyncio.create_task(_first(second))
        await asyncio.sleep(0.05)
        assert len(calls) == 1, "the second chat must not reach the wire while the slot is held"
        snap = provider_admission.snapshot()
        assert (snap["chat_in_flight"], snap["waiting"], snap["admitted"], snap["rejected"]) == (1, 1, 1, 0)
        await first.aclose()  # the consumer walks away mid-stream
        assert holder.closed
        assert await task == "first"
        assert len(calls) == 2
        await second.aclose()
    snap = provider_admission.snapshot()
    assert (snap["in_flight"], snap["chat_in_flight"], snap["waiting"], snap["admitted"], snap["peak_in_flight"]) == (
        0, 0, 0, 2, 1
    )


@pytest.mark.asyncio
async def test_summary_path_is_counted_but_never_queues_behind_chat():
    calls = []
    async with service_for(_handler(calls, [Trickle(), completion()])) as service:
        chat = service.stream_chat(MESSAGES)
        assert await _first(chat) == "first"
        assert await asyncio.wait_for(service._request_content(KW), timeout=2.0) == '{"fresh":true}'
        assert len(calls) == 2, "a summary attempt reaches the wire while chat holds the only slot"
        snap = provider_admission.snapshot()
        assert (snap["in_flight"], snap["chat_in_flight"], snap["waiting"], snap["admitted"]) == (1, 1, 0, 2)
        assert snap["peak_in_flight"] == 2
        await chat.aclose()
    assert provider_admission.snapshot()["in_flight"] == 0


@pytest.mark.asyncio
async def test_chat_wait_is_bounded_by_its_own_deadline_and_leaks_no_slot(monkeypatch):
    calls = []
    async with service_for(_handler(calls, [Trickle(), Trickle()])) as service:
        holder = service.stream_chat(MESSAGES)
        assert await _first(holder) == "first"
        monkeypatch.setattr(copilot_chat, "_CHAT_SECONDS", 0.05)  # the waiter's budget only
        waiter = service.stream_chat(MESSAGES)
        assert (await _first(waiter)).startswith(copilot_chat.STREAM_ERROR_SENTINEL)
        await waiter.aclose()
        assert len(calls) == 1, "a rejected wait never touches the wire"
        snap = provider_admission.snapshot()
        assert snap["rejected"] == 1 and snap["waiting"] == 0 and snap["chat_in_flight"] == 1
        await holder.aclose()
        assert provider_admission.snapshot()["chat_in_flight"] == 0
        monkeypatch.setattr(copilot_chat, "_CHAT_SECONDS", 5.0)
        third = service.stream_chat(MESSAGES)
        assert await _first(third) == "first"
        await third.aclose()
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_time_spent_waiting_for_a_slot_is_not_added_to_the_chat_budget(monkeypatch):
    """A stream admitted after waiting W seconds is still cut at its original deadline, not at
    deadline + W: otherwise contention would extend slot occupancy, which extends contention.
    One task consumes the waiter throughout, as one request task does in production. The short
    budget is patched only once the holder streams (the SDK's cold first call can cost 0.4 s)."""
    calls = []
    async with service_for(_handler(calls, [Trickle(), Trickle()])) as service:
        holder = service.stream_chat(MESSAGES)
        assert await _first(holder) == "first"
        monkeypatch.setattr(copilot_chat, "_CHAT_SECONDS", 1.0)  # the waiter's budget only

        async def consume():
            started = asyncio.get_running_loop().time()
            waiter = service.stream_chat(MESSAGES)
            try:
                first = await waiter.__anext__()
                second = await waiter.__anext__()
            finally:
                await waiter.aclose()
            return first, second, asyncio.get_running_loop().time() - started

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.4)
        await holder.aclose()  # the slot frees at ~0.4 s; the waiter's deadline is at 1.0 s
        first, second, elapsed = await asyncio.wait_for(task, timeout=3.0)
        assert first == "first"
        assert second.startswith(copilot_chat.STREAM_ERROR_SENTINEL)
        assert elapsed < 1.2, f"stream ran past its original deadline: {elapsed:.2f}s"  # the bug gives >= 1.4
    assert provider_admission.snapshot()["in_flight"] == 0


def test_zero_disables_the_ceiling(monkeypatch):
    monkeypatch.setattr(settings, "AI_CHAT_MAX_INFLIGHT", 0)
    assert provider_admission.limit() == 2**31
