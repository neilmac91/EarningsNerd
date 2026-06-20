"""Unit tests for the SEC rate limiter's Retry-After handling."""

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
