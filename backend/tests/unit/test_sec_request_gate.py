"""Fail-closed fleet admission and real HTTPX redirect/cancellation boundaries."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from app.services import sec_request_gate as gate


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(gate.settings, "SEC_DISTRIBUTED_LIMIT_ENABLED", True)


def test_default_off_never_opens_coordinator(monkeypatch):
    monkeypatch.setattr(gate.settings, "SEC_DISTRIBUTED_LIMIT_ENABLED", False)
    get_gate = Mock(side_effect=AssertionError("unexpected DB access"))
    monkeypatch.setattr(gate, "_get_gate", get_gate)
    assert gate.sec_request_options() == {}
    gate.acquire_sync()
    asyncio.run(gate.acquire_async())
    get_gate.assert_not_called()


@pytest.mark.asyncio
async def test_actual_httpx_redirects_and_retry_each_get_one_grant(enabled, monkeypatch):
    grants, sends = [], []

    async def acquire():
        grants.append(len(sends))

    async def send(request):
        sends.append(request.url.path)
        hop = int(request.url.path.strip("/"))
        return httpx.Response(302, headers={"location": f"/{hop + 1}"}) if hop < 2 else httpx.Response(200)

    monkeypatch.setattr(gate, "acquire_async", acquire)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(send), **gate.sec_request_options(),
    ) as client:
        await client.get("https://fixture.invalid/0", follow_redirects=True)
        await client.get("https://fixture.invalid/2")
    assert sends == ["/0", "/1", "/2", "/2"]
    assert grants == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_proxy_mount_still_runs_owned_client_hook(enabled, monkeypatch):
    events = []

    async def acquire():
        events.append("grant")

    async def send(self, request):
        events.append("send")
        return httpx.Response(200, request=request)

    monkeypatch.setattr(gate, "acquire_async", acquire)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    async with httpx.AsyncClient(proxy="http://proxy.invalid:3128", **gate.sec_request_options()) as client:
        await client.get("https://fixture.invalid/document")
    assert events == ["grant", "send"]


@pytest.mark.asyncio
async def test_coordinator_failure_never_reaches_http_transport(enabled, monkeypatch):
    async def unavailable():
        raise gate.SECAdmissionUnavailable("SEC admission coordinator is unavailable")

    monkeypatch.setattr(gate, "_try_grant_async", unavailable)
    send = Mock(return_value=httpx.Response(200))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(send), **gate.sec_request_options(),
    ) as client:
        with pytest.raises(gate.SECAdmissionUnavailable):
            await client.get("https://fixture.invalid/document")
    send.assert_not_called()


def test_db_exception_message_is_not_exposed():
    engine = Mock()
    subject = gate.PostgresRequestGate(engine)
    subject._sessions.begin = Mock(side_effect=ValueError("synthetic-private-password-and-email@example.invalid"))
    with pytest.raises(gate.SECAdmissionUnavailable) as caught:
        subject.try_grant()
    assert str(caught.value) == "SEC admission coordinator is unavailable"
    assert caught.value.__suppress_context__


def test_sync_deadline_checks_after_db_before_send(enabled, monkeypatch):
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(gate, "time", SimpleNamespace(monotonic=lambda: clock.now))

    def delayed_grant():
        clock.now = 111.0
        return gate.AdmissionDecision(0, datetime.now(timezone.utc))

    monkeypatch.setattr(gate, "_get_gate", lambda: SimpleNamespace(try_grant=delayed_grant))
    with pytest.raises(gate.SECAdmissionUnavailable, match="expired"):
        gate.acquire_sync()


@pytest.mark.asyncio
async def test_cancelled_waiter_cannot_send_after_db_finishes(enabled, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(gate, "_executor", executor)
    monkeypatch.setattr(gate, "_async_slot", threading.BoundedSemaphore(1))

    def blocked_grant():
        entered.set()
        assert release.wait(3), "test did not release its DB fixture"
        return gate.AdmissionDecision(0, datetime.now(timezone.utc))

    monkeypatch.setattr(gate, "_get_gate", lambda: SimpleNamespace(try_grant=blocked_grant))
    send = Mock(return_value=httpx.Response(200))
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(send), **gate.sec_request_options(),
        ) as client:
            pending = asyncio.create_task(client.get("https://fixture.invalid/document"))
            async with asyncio.timeout(2):
                while not entered.is_set():
                    await asyncio.sleep(0)
            # A second async attempt cannot submit an unbounded queued DB unit.
            assert (await gate._try_grant_async()).granted_at is None
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            release.set()
    finally:
        release.set()
        executor.shutdown(wait=True)
    send.assert_not_called()
    assert gate._async_slot.acquire(blocking=False)
    gate._async_slot.release()


@pytest.mark.asyncio
async def test_outer_document_deadline_during_admission_does_not_trip_sec_breaker(enabled, monkeypatch):
    from app.services.edgar import compat
    from app.services.edgar.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

    breaker = CircuitBreaker("local-admission", CircuitBreakerConfig(failure_threshold=1))
    monkeypatch.setattr(compat, "edgar_circuit_breaker", breaker)
    real_client = httpx.AsyncClient
    send = Mock(return_value=httpx.Response(200))
    monkeypatch.setattr(compat.httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(send),
    ))

    async def wait_forever():
        await asyncio.Event().wait()

    async def immediately(call):
        return await call()

    monkeypatch.setattr(gate, "acquire_async", wait_forever)
    monkeypatch.setattr(compat.sec_rate_limiter, "execute", immediately)
    with pytest.raises(compat.EdgarError) as caught:
        await compat.sec_edgar_service.get_filing_document_with_source(
            "https://fixture.invalid/document", timeout=0.02,
        )
    assert caught.value.code == "EDGAR_WAIT_TIMEOUT"
    assert not breaker.is_open
    send.assert_not_called()


@pytest.mark.parametrize("status,header,seconds,indefinite", [
    (429, None, 1, False), (429, "invalid", 1, False),
    (429, "0", 0, False), (429, "600", 600, False),
    (503, " 3600 ", 3600, False), (429, "0" * 5000 + "3", 3, False),
    (429, "9" * 5000, None, True),
])
def test_retry_after_never_shortens_positive_hints(status, header, seconds, indefinite):
    hint = gate.response_cooldown(status, header)
    assert hint.seconds == seconds
    assert hint.indefinite is indefinite


def test_http_date_is_absolute_utc_and_success_ignores_header():
    hint = gate.response_cooldown(503, "Wed, 21 Oct 2099 07:28:00 GMT")
    assert hint.until == datetime(2099, 10, 21, 7, 28, tzinfo=timezone.utc)
    assert gate.response_cooldown(200, "3600") is None
    assert gate.response_cooldown(503, "invalid") is None


@pytest.mark.asyncio
async def test_disconnect_does_not_discard_already_observed_feedback(enabled, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    persisted = []

    async def db_attempt(call):
        entered.set()
        await release.wait()
        return call()

    monkeypatch.setattr(gate, "_db_attempt", db_attempt)
    monkeypatch.setattr(gate, "_get_gate", lambda: SimpleNamespace(
        try_defer=lambda hint: persisted.append(hint.seconds) or True,
    ))
    caller = asyncio.create_task(gate.record_response_async(429, "60"))
    await asyncio.wait_for(entered.wait(), timeout=2)
    caller.cancel()
    with pytest.raises(asyncio.CancelledError):
        await caller
    release.set()
    await asyncio.gather(*gate._feedback_tasks)
    assert persisted == [60]


@pytest.mark.asyncio
async def test_feedback_coordinator_error_closes_owned_client_response(enabled, monkeypatch):
    class Body(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b"refused"

        async def aclose(self):
            self.closed = True

    body = Body()

    async def admit():
        pass

    async def unavailable(hint):
        raise gate.SECAdmissionUnavailable("SEC cooldown coordinator is unavailable")

    monkeypatch.setattr(gate, "acquire_async", admit)
    monkeypatch.setattr(gate, "_persist_cooldown", unavailable)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": "60"}, stream=body)),
        **gate.sec_request_options(),
    ) as client:
        with pytest.raises(gate.SECAdmissionUnavailable):
            await client.get("https://fixture.invalid/document")
    assert body.closed


@pytest.mark.parametrize("failure,expected_attempts", [("admission", 0), ("feedback", 1)])
@pytest.mark.asyncio
async def test_attachment_counts_only_admitted_transport_attempts(enabled, monkeypatch, failure, expected_attempts):
    from app.services.edgar import compat
    from app.services.edgar.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

    sends = []
    real_client = httpx.AsyncClient

    def send(request):
        sends.append(request.url.path)
        return httpx.Response(429, headers={"Retry-After": "60"}, request=request)

    monkeypatch.setattr(compat.httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(send),
    ))
    monkeypatch.setattr(compat, "edgar_circuit_breaker", CircuitBreaker("attachment-gate", CircuitBreakerConfig()))

    async def acquire():
        if failure == "admission":
            raise gate.SECAdmissionUnavailable("SEC admission coordinator is unavailable")

    async def unavailable(hint):
        raise gate.SECAdmissionUnavailable("SEC cooldown coordinator is unavailable")

    async def execute(call):
        return await call()

    monkeypatch.setattr(gate, "acquire_async", acquire)
    monkeypatch.setattr(gate, "_persist_cooldown", unavailable)
    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    with pytest.raises(compat.EdgarError) as error:
        await compat.sec_edgar_service.get_filing_attachment_bytes(
            "320193", "0000320193-23-000077", "chart.gif",
        )
    assert error.value.context["physical_attempts"] == expected_attempts
    assert len(sends) == expected_attempts
