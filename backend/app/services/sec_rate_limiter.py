"""
SEC EDGAR Rate Limiter with Exponential Backoff

SEC enforces a strict 10 requests/second limit. Exceeding this results in IP blocking.
This module provides a robust rate limiter with:
- Token bucket algorithm for rate limiting
- Exponential backoff on rate limit errors
- Async-safe implementation
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional, TypeVar, Awaitable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Cap on how long we'll honor a server-sent Retry-After, so a misbehaving or hostile
# header can't park a worker indefinitely.
MAX_RETRY_AFTER_SECONDS = 120.0


class SECRateLimitError(Exception):
    """Raised when SEC rate limit is exceeded after all retries"""
    pass


class SECRateLimiter:
    """
    SEC-compliant rate limiter with exponential backoff.

    Implements a token bucket algorithm to ensure we stay under
    SEC's 10 requests/second limit, with automatic retry and
    exponential backoff when rate limits are hit.
    """

    def __init__(
        self,
        requests_per_second: int = None,
        max_retries: int = None,
        base_backoff_seconds: float = None,
    ):
        self.requests_per_second = requests_per_second or settings.SEC_RATE_LIMIT_PER_SECOND
        self.max_retries = max_retries or settings.SEC_MAX_RETRIES
        self.base_backoff_seconds = base_backoff_seconds or settings.SEC_BASE_BACKOFF_SECONDS

        # Token bucket state
        self._tokens = float(self.requests_per_second)
        self._last_update = time.monotonic()
        # Lazy lock initialization for event loop safety (created on first use)
        self._lock: Optional[asyncio.Lock] = None

        # Request tracking for monitoring
        self._total_requests = 0
        self._rate_limit_hits = 0

    def _get_lock(self) -> asyncio.Lock:
        """Get or create the rate limiter lock (lazy initialization for event loop safety)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _wait_for_token(self) -> None:
        """Wait until a token is available in the bucket"""
        async with self._get_lock():
            now = time.monotonic()
            time_passed = now - self._last_update
            self._last_update = now

            # Refill tokens based on time passed
            self._tokens = min(
                float(self.requests_per_second),
                self._tokens + time_passed * self.requests_per_second
            )

            if self._tokens < 1.0:
                # Wait for token to become available
                wait_time = (1.0 - self._tokens) / self.requests_per_second
                logger.debug(f"Rate limiter: waiting {wait_time:.3f}s for token")
                await asyncio.sleep(wait_time)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0

            self._total_requests += 1

    async def execute(
        self,
        request_fn: Callable[[], Awaitable[T]],
    ) -> T:
        """
        Execute a request with rate limiting.

        Args:
            request_fn: Async function that makes the SEC request

        Returns:
            The result of request_fn

        Raises:
            SECRateLimitError: If max retries exceeded
        """
        await self._wait_for_token()
        return await request_fn()

    async def execute_with_backoff(
        self,
        request_fn: Callable[[], Awaitable[T]],
        is_rate_limit_error: Callable[[Exception], bool] = None,
    ) -> T:
        """
        Execute a request with rate limiting and exponential backoff on failures.

        Args:
            request_fn: Async function that makes the SEC request
            is_rate_limit_error: Function to check if exception is rate limit error

        Returns:
            The result of request_fn

        Raises:
            SECRateLimitError: If max retries exceeded
        """
        if is_rate_limit_error is None:
            is_rate_limit_error = self._is_rate_limit_error

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                await self._wait_for_token()
                return await request_fn()
            except Exception as e:
                last_exception = e

                if not is_rate_limit_error(e):
                    # Not a rate limit error, re-raise immediately
                    raise

                self._rate_limit_hits += 1

                if attempt < self.max_retries - 1:
                    # Calculate backoff with jitter
                    backoff = self.base_backoff_seconds * (2 ** attempt)
                    # Add small random jitter (0-10% of backoff)
                    jitter = backoff * 0.1 * (time.monotonic() % 1)
                    total_wait = backoff + jitter

                    # Honor SEC's Retry-After header when present (capped) — it is the
                    # authoritative cool-off and overrides our computed backoff when longer.
                    retry_after = self._retry_after_seconds(e)
                    if retry_after is not None:
                        total_wait = max(total_wait, min(retry_after, MAX_RETRY_AFTER_SECONDS))

                    logger.warning(
                        f"SEC rate limit hit (attempt {attempt + 1}/{self.max_retries}), "
                        f"backing off for {total_wait:.2f}s"
                        + (f" (Retry-After={retry_after:.0f}s)" if retry_after is not None else "")
                    )
                    await asyncio.sleep(total_wait)

        logger.error(
            f"SEC rate limit: max retries ({self.max_retries}) exceeded"
        )
        raise SECRateLimitError(
            f"Max retries ({self.max_retries}) exceeded for SEC request"
        ) from last_exception

    @staticmethod
    def _is_rate_limit_error(exception: Exception) -> bool:
        """Check if exception indicates a rate limit error"""
        if isinstance(exception, httpx.HTTPStatusError):
            # SEC returns 429 for rate limiting
            return exception.response.status_code == 429

        error_msg = str(exception).lower()
        return any(phrase in error_msg for phrase in [
            "rate limit",
            "too many requests",
            "429",
            "throttl",
        ])

    @staticmethod
    def _retry_after_seconds(exception: Exception) -> Optional[float]:
        """Parse a ``Retry-After`` header off a 429, in seconds (numeric or HTTP-date).

        Returns ``None`` when the exception isn't an HTTP error, has no header, or the
        header can't be parsed. Negative/expired values clamp to 0.0.
        """
        if not isinstance(exception, httpx.HTTPStatusError):
            return None
        header = exception.response.headers.get("Retry-After")
        if not header:
            return None
        header = header.strip()

        # delta-seconds form (the common case).
        try:
            return max(0.0, float(header))
        except ValueError:
            pass

        # HTTP-date form. parsedate_to_datetime raises (not returns None) on bad input;
        # catch broadly so a malformed header can never crash the rate limiter.
        try:
            when = parsedate_to_datetime(header)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except Exception:
            return None

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            "total_requests": self._total_requests,
            "rate_limit_hits": self._rate_limit_hits,
            "current_tokens": self._tokens,
            "requests_per_second": self.requests_per_second,
        }


# Singleton instance for shared rate limiting across the application
sec_rate_limiter = SECRateLimiter()
