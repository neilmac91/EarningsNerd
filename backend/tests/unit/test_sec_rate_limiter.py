"""Unit tests for SEC token accounting and Retry-After handling."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.services.sec_rate_limiter import (
    MAX_RETRY_AFTER_SECONDS,
    SECRateLimiter,
    SECRateLimitError,
)


def _http_429(retry_after: str | None) -> httpx.HTTPStatusError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    request = httpx.Request("GET", "https://efts.sec.gov/LATEST/search-index")
    response = httpx.Response(429, headers=headers, request=request)
    return httpx.HTTPStatusError("429", request=request, response=response)


class TestRetryAfterParsing:
    def test_numeric_seconds(self):
        assert SECRateLimiter._retry_after_seconds(_http_429("30")) == 30.0

    def test_negative_seconds_clamps_to_zero(self):
        assert SECRateLimiter._retry_after_seconds(_http_429("-5")) == 0.0

    def test_nan_returns_none(self):
        # float("nan") parses but must not propagate to asyncio.sleep(nan).
        assert SECRateLimiter._retry_after_seconds(_http_429("nan")) is None

    def test_missing_header(self):
        assert SECRateLimiter._retry_after_seconds(_http_429(None)) is None

    def test_unparseable_header(self):
        assert SECRateLimiter._retry_after_seconds(_http_429("soon")) is None

    def test_non_http_error(self):
        assert SECRateLimiter._retry_after_seconds(ValueError("nope")) is None

    def test_http_date(self):
        # A far-future HTTP-date yields a positive delta; an epoch-past one clamps to 0.
        future = SECRateLimiter._retry_after_seconds(
            _http_429("Wed, 21 Oct 2099 07:28:00 GMT")
        )
        assert future is not None and future > 0
        past = SECRateLimiter._retry_after_seconds(
            _http_429("Wed, 21 Oct 2015 07:28:00 GMT")
        )
        assert past == 0.0

    def test_float_like_values_rejected(self):
        # "1e9"/"inf"/"30.5" are not RFC 7231 delta-seconds (1*DIGIT). They must fall through
        # to None (→ normal exponential backoff) rather than being honored as a (120s-capped)
        # multi-second stall, which float() parsing would have allowed.
        assert SECRateLimiter._retry_after_seconds(_http_429("1e9")) is None
        assert SECRateLimiter._retry_after_seconds(_http_429("inf")) is None
        assert SECRateLimiter._retry_after_seconds(_http_429("30.5")) is None


@pytest.mark.asyncio
class TestRetryAfterHonored:
    async def test_waits_at_least_retry_after(self, monkeypatch):
        waits: list[float] = []

        async def _fake_sleep(seconds):
            waits.append(seconds)

        monkeypatch.setattr("app.services.sec_rate_limiter.asyncio.sleep", _fake_sleep)

        limiter = SECRateLimiter(requests_per_second=100, max_retries=2, base_backoff_seconds=0.5)
        calls = {"n": 0}

        async def _request():
            calls["n"] += 1
            if calls["n"] == 1:
                raise _http_429("45")  # > computed backoff (0.5) → Retry-After wins
            return "ok"

        result = await limiter.execute_with_backoff(_request)
        assert result == "ok"
        # The backoff sleep honored Retry-After (45s) rather than the ~0.5s computed value.
        assert any(w >= 45.0 for w in waits)

    async def test_retry_after_is_capped(self, monkeypatch):
        waits: list[float] = []

        async def _fake_sleep(seconds):
            waits.append(seconds)

        monkeypatch.setattr("app.services.sec_rate_limiter.asyncio.sleep", _fake_sleep)

        limiter = SECRateLimiter(requests_per_second=100, max_retries=2, base_backoff_seconds=0.5)

        async def _request():
            raise _http_429("99999")  # absurd header must be capped

        with pytest.raises(SECRateLimitError):
            await limiter.execute_with_backoff(_request)
        assert waits and max(waits) <= MAX_RETRY_AFTER_SECONDS


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["sequential", "concurrent", "delayed_wakeup", "cancelled_wait"])
async def test_elapsed_refill_is_spent_once(monkeypatch, scenario):
    """A burst is allowed, but every later admission needs fresh elapsed time."""
    clock = SimpleNamespace(now=100.0)
    real_sleep = asyncio.sleep
    cancel_next_wait = scenario == "cancelled_wait"
    waits: list[float] = []
    admitted: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        nonlocal cancel_next_wait
        waits.append(seconds)
        if cancel_next_wait:
            cancel_next_wait = False
            clock.now += seconds / 2
            raise asyncio.CancelledError
        clock.now += seconds + (0.25 if scenario == "delayed_wakeup" else 0)
        # Yield so concurrent callers contend on the real asyncio lock.
        await real_sleep(0)

    monkeypatch.setattr(
        "app.services.sec_rate_limiter.time",
        SimpleNamespace(monotonic=lambda: clock.now),
    )
    monkeypatch.setattr("app.services.sec_rate_limiter.asyncio.sleep", fake_sleep)
    limiter = SECRateLimiter(requests_per_second=4)

    async def request() -> None:
        admitted.append(clock.now)

    for _ in range(4):
        await limiter.execute(request)
    assert admitted == [100.0] * 4
    assert waits == []

    if scenario == "cancelled_wait":
        with pytest.raises(asyncio.CancelledError):
            await limiter.execute(request)
        assert admitted == [100.0] * 4

    if scenario == "concurrent":
        await asyncio.gather(*(limiter.execute(request) for _ in range(4)))
    else:
        for _ in range(4):
            await limiter.execute(request)

    interval = 0.5 if scenario == "delayed_wakeup" else 0.25
    assert admitted[4:] == pytest.approx([100.0 + interval * i for i in range(1, 5)])
    assert limiter.get_stats()["total_requests"] == 8

    # Idle time restores the declared burst without accumulating beyond its cap.
    clock.now += 10
    idle_end = clock.now
    for _ in range(5):
        await limiter.execute(request)
    assert admitted[-5:-1] == [idle_end] * 4
    assert admitted[-1] == pytest.approx(idle_end + interval)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["direct", "retry", "redirect", "observation_failure", "cancel_observation"])
async def test_document_source_observation_preserves_transport_and_decoded_text(monkeypatch, mode):
    import hashlib
    from app.services.edgar import compat

    url = "https://sec.example/selected.htm"
    final_url = "https://sec.example/final.htm" if mode == "redirect" else url
    raw = b" <html><body>caf\xe9</body></html>\n"
    expected = raw.decode("iso-8859-1")
    calls = []
    waits = []

    def respond(request):
        calls.append(str(request.url))
        if mode == "retry" and len(calls) == 1:
            return httpx.Response(503)
        if mode == "redirect" and str(request.url) == url:
            return httpx.Response(302, headers={"location": final_url})
        return httpx.Response(200, content=raw, headers={"content-type": "text/html; charset=iso-8859-1"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(compat.httpx, "AsyncClient", lambda: real_client(transport=httpx.MockTransport(respond)))

    class Breaker:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    async def execute(fn):
        return await fn()

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(compat, "edgar_circuit_breaker", Breaker())
    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    old = await compat.sec_edgar_service.get_filing_document(url)
    old_calls, old_waits = list(calls), list(waits)
    calls.clear()
    waits.clear()
    if mode in {"observation_failure", "cancel_observation"}:
        def broken_observer(*args):
            if mode == "cancel_observation":
                raise asyncio.CancelledError()
            raise ValueError("optional metadata failed")
        monkeypatch.setattr(compat, "_decoded_source_provenance", broken_observer)
    if mode == "cancel_observation":
        with pytest.raises(asyncio.CancelledError):
            await compat.sec_edgar_service.get_filing_document_with_source(url)
    else:
        text, source = await compat.sec_edgar_service.get_filing_document_with_source(url)
        assert text == old == expected
        if mode == "observation_failure":
            assert source is None
        else:
            assert source == {
                "schema_version": 1, "representation": "httpx_decoded_response_text_utf8",
                "sha256": hashlib.sha256(expected.encode("utf-8")).hexdigest(),
                "characters": len(expected), "requested_url": url, "final_url": final_url,
                "content_type": "text/html; charset=iso-8859-1",
            }
            assert source["sha256"] != hashlib.sha256(raw).hexdigest()
    assert calls == old_calls
    assert len(calls) == (2 if mode in {"retry", "redirect"} else 1)
    assert waits == old_waits == ([1] if mode == "retry" else [])
