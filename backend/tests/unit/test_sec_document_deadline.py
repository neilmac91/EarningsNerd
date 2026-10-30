"""Primary-document pacing, retry classification and real-breaker fault injection."""
import asyncio

import httpx
import pytest

from app.services.edgar import compat
from app.services.edgar.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


@pytest.fixture
def transport(monkeypatch):
    requests = []
    sleeps = []
    real_client = httpx.AsyncClient
    breaker = CircuitBreaker("document-test", CircuitBreakerConfig(failure_threshold=2, recovery_timeout=3600))
    monkeypatch.setattr(compat, "edgar_circuit_breaker", breaker)

    async def execute(fn):
        return await fn()

    async def sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    monkeypatch.setattr(compat.random, "uniform", lambda low, high: high / 2)
    monkeypatch.setattr(asyncio, "sleep", sleep)

    def install(respond):
        def wrapped(request):
            requests.append(request)
            return respond(request)
        monkeypatch.setattr(
            compat.httpx, "AsyncClient", lambda: real_client(transport=httpx.MockTransport(wrapped)),
        )
    return install, requests, sleeps, breaker


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["connect", "timeout", 429, 503, 404, 403])
async def test_document_faults_reach_real_breaker_and_permanent_refusals_do_not_retry(transport, failure):
    install, requests, sleeps, breaker = transport

    def respond(request):
        if failure == "connect":
            raise httpx.ConnectError("synthetic", request=request)
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic", request=request)
        return httpx.Response(failure)

    install(respond)
    for _ in range(2):
        with pytest.raises(compat.EdgarError):
            await compat.sec_edgar_service.get_filing_document("https://sec.example/report.htm")
    transient = failure not in {403, 404}
    assert len(requests) == (6 if transient else 2)
    assert sleeps == ([0.5, 1, 0.5, 1] if transient else [])
    assert breaker.is_open is transient
    assert breaker.stats.failed_requests == 2
    if transient:
        with pytest.raises(compat.EdgarError, match="circuit breaker is open"):
            await compat.sec_edgar_service.get_filing_document("https://sec.example/report.htm")
        assert len(requests) == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("retry_after", ["60", "999999", "Wed, 21 Oct 2099 07:28:00 GMT"])
async def test_cooldown_outside_deadline_is_returned_without_sleep_or_early_retry(transport, status, retry_after):
    install, requests, sleeps, _ = transport
    install(lambda request: httpx.Response(status, headers={"Retry-After": retry_after}))
    with pytest.raises(compat.EdgarError) as result:
        await compat.sec_edgar_service.get_filing_document("https://sec.example/report.htm", timeout=15)
    assert result.value.context["status_code"] == status
    assert result.value.context["retry_after_seconds"] >= 60
    assert isinstance(result.value.cause, httpx.HTTPStatusError)
    assert len(requests) == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_retry_honors_cooldown_then_returns_decoded_document(transport):
    install, requests, sleeps, breaker = transport

    def respond(request):
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        return httpx.Response(200, text="<html>the filing</html>")

    install(respond)
    assert await compat.sec_edgar_service.get_filing_document("https://sec.example/report.htm", timeout=10) == "<html>the filing</html>"
    assert len(requests) == 2
    assert sleeps == [3]
    assert breaker.stats.successful_requests == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["admission", "request"])
async def test_total_deadline_cancels_blocked_work_and_only_network_wait_trips_breaker(monkeypatch, phase):
    breaker = CircuitBreaker("deadline-test", CircuitBreakerConfig(failure_threshold=1))
    monkeypatch.setattr(compat, "edgar_circuit_breaker", breaker)
    request_started = asyncio.Event()
    cancelled = asyncio.Event()
    never = asyncio.Event()
    real_client = httpx.AsyncClient

    async def block():
        try:
            await never.wait()
        finally:
            cancelled.set()

    async def respond(request):
        request_started.set()
        await block()

    async def execute(fn):
        if phase == "admission":
            await block()
        return await fn()

    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    monkeypatch.setattr(compat.httpx, "AsyncClient", lambda: real_client(transport=httpx.MockTransport(respond)))
    with pytest.raises(compat.EdgarError) as result:
        await asyncio.wait_for(
            compat.sec_edgar_service.get_filing_document("https://sec.example/report.htm", timeout=0.02),
            timeout=1,
        )
    assert result.value.code == ("EDGAR_WAIT_TIMEOUT" if phase == "admission" else "EDGAR_TIMEOUT")
    assert request_started.is_set() is (phase == "request")
    assert cancelled.is_set()
    assert breaker.is_open is (phase == "request")


@pytest.mark.asyncio
async def test_caller_cancellation_stays_cancellation(monkeypatch):
    entered = asyncio.Event()
    stopped = asyncio.Event()

    async def execute(fn):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    monkeypatch.setattr(compat, "edgar_circuit_breaker", CircuitBreaker("cancel-test"))
    task = asyncio.create_task(compat.sec_edgar_service.get_filing_document("https://sec.example/report.htm"))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()
