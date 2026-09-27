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


@pytest.mark.asyncio
async def test_same_filing_attachment_preserves_binary_bytes_and_transport_limits(monkeypatch):
    import hashlib
    from app.services.edgar import compat

    cik = "0000320193"
    accession = "0000320193-23-000077"
    filename = "chart image.gif"
    attachment_url = (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019323000077/"
        "chart%20image.gif"
    )
    text_url = "https://sec.example/selected.htm"
    raw = b"GIF89a\x00\xff\xfe\x80binary"
    text_raw = b"<p>caf\xe9</p>"
    requests = []
    limiter_calls = 0
    breaker_enters = 0
    waits = []
    attachment = {"mode": "success", "retry_calls": 0}
    stream_reads = {"identity": 0, "compressed": 0}

    class ObservedStream(httpx.AsyncByteStream):
        def __init__(self, payload, label):
            self.payload = payload
            self.label = label

        async def __aiter__(self):
            stream_reads[self.label] += 1
            midpoint = len(self.payload) // 2
            yield self.payload[:midpoint]
            yield self.payload[midpoint:]

    def respond(request):
        requests.append(request)
        if str(request.url) == attachment_url:
            if attachment["mode"] == "redirect":
                return httpx.Response(
                    302,
                    headers={"location": "https://outside.example/chart.gif"},
                )
            if attachment["mode"] == "compressed":
                return httpx.Response(
                    200,
                    stream=ObservedStream(b"compressed-body", "compressed"),
                    headers={"content-encoding": "gzip"},
                )
            if attachment["mode"] == "retry":
                attachment["retry_calls"] += 1
                if attachment["retry_calls"] == 1:
                    return httpx.Response(503)
            # The deliberately low header proves the streamed decoded-entity limit does not
            # trust Content-Length. Non-UTF-8 bytes prove there is no text round trip.
            return httpx.Response(
                200,
                stream=ObservedStream(raw, "identity"),
                headers={
                    "content-type": "image/gif",
                    "content-encoding": "identity",
                    "content-length": "1",
                    "etag": '"binary-etag"',
                    "last-modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                },
            )
        if str(request.url) == text_url:
            return httpx.Response(
                200,
                content=text_raw,
                headers={"content-type": "text/html; charset=iso-8859-1"},
            )
        return httpx.Response(404)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        compat.httpx,
        "AsyncClient",
        lambda: real_client(transport=httpx.MockTransport(respond)),
    )

    class Breaker:
        async def __aenter__(self):
            nonlocal breaker_enters
            breaker_enters += 1
            return self

        async def __aexit__(self, *args):
            return False

    async def execute(fn):
        nonlocal limiter_calls
        limiter_calls += 1
        return await fn()

    async def sleep(delay):
        waits.append(delay)

    monkeypatch.setattr(compat, "edgar_circuit_breaker", Breaker())
    monkeypatch.setattr(compat.sec_rate_limiter, "execute", execute)
    monkeypatch.setattr(asyncio, "sleep", sleep)

    content, source = await compat.sec_edgar_service.get_filing_attachment_bytes(
        cik, accession, filename
    )
    assert content == raw
    assert source == {
        "schema_version": 1,
        "representation": "httpx_identity_entity_bytes",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "cik": "320193",
        "accession_number": "000032019323000077",
        "filename": filename,
        "requested_url": attachment_url,
        "final_url": attachment_url,
        "status_code": 200,
        "content_type": "image/gif",
        "content_encoding": "identity",
        "content_length": "1",
        "etag": '"binary-etag"',
        "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        "physical_attempts": 1,
    }
    assert requests[0].headers["user-agent"] == compat.EDGAR_IDENTITY
    assert requests[0].headers["accept-encoding"] == "identity"
    assert stream_reads["identity"] == 1

    # The pre-existing decoded-text API keeps its response.text behavior.
    assert await compat.sec_edgar_service.get_filing_document(text_url) == text_raw.decode(
        "iso-8859-1"
    )

    monkeypatch.setattr(compat, "MAX_SEC_ATTACHMENT_BYTES", len(raw) - 1)
    with pytest.raises(compat.EdgarError, match="SEC attachment exceeds") as error:
        await compat.sec_edgar_service.get_filing_attachment_bytes(
            cik, accession, filename, max_retries=1
        )
    assert error.value.context == {
        "requested_url": attachment_url,
        "physical_attempts": 1,
    }
    assert [str(request.url) for request in requests] == [
        attachment_url,
        text_url,
        attachment_url,
    ]
    assert limiter_calls == 3
    assert breaker_enters == 3

    # Unsafe filename forms fail before entering the transport owner.
    request_count = len(requests)
    for unsafe_filename in (
        "",
        ".",
        "../chart.gif",
        "/chart.gif",
        "chart.gif?version=1",
        "chart.gif#page",
        "chart\n.gif",
    ):
        with pytest.raises(ValueError, match="filename"):
            await compat.sec_edgar_service.get_filing_attachment_bytes(
                cik, accession, unsafe_filename
            )
    assert len(requests) == request_count
    assert limiter_calls == breaker_enters == 3

    # Redirects are an explicit failure and never result in a second physical request.
    monkeypatch.setattr(compat, "MAX_SEC_ATTACHMENT_BYTES", 32 * 1024 * 1024)
    attachment["mode"] = "redirect"
    with pytest.raises(compat.EdgarError, match="Redirect response") as redirect_error:
        await compat.sec_edgar_service.get_filing_attachment_bytes(
            cik, accession, filename, max_retries=1
        )
    assert redirect_error.value.context["physical_attempts"] == 1
    assert len(requests) == request_count + 1

    # A server that ignores Accept-Encoding is rejected from headers without consuming its body.
    attachment["mode"] = "compressed"
    with pytest.raises(compat.EdgarError, match="non-identity") as compressed_error:
        await compat.sec_edgar_service.get_filing_attachment_bytes(
            cik, accession, filename, max_retries=1
        )
    assert compressed_error.value.context["physical_attempts"] == 1
    assert stream_reads["compressed"] == 0
    assert len(requests) == request_count + 2

    # An explicitly requested retry records both physical attempts and the owned backoff.
    attachment.update(mode="retry", retry_calls=0)
    retry_content, retry_source = await compat.sec_edgar_service.get_filing_attachment_bytes(
        cik, accession, filename, max_retries=2
    )
    assert retry_content == raw
    assert retry_source == {**source, "physical_attempts": 2}
    assert attachment["retry_calls"] == 2
    assert waits == [1]
    assert len(requests) == request_count + 4
    assert limiter_calls == 7
    assert breaker_enters == 6
