"""Versioned integration with the pinned EdgarTools transport owners.

Only the manager instance's limiter/transport factories and one SGML fallback are adapted.
No HTTPX class/global function or installed dependency file is changed.
"""
from __future__ import annotations

from importlib.metadata import version
from inspect import signature

from httpxthrottlecache import HttpxThrottleCache
from httpxthrottlecache._compat import httpx
from httpxthrottlecache.filecache.transport import CachingTransport
from httpxthrottlecache.ratelimiter import AsyncRateLimitingTransport, RateLimitingTransport

from app.config import settings
from app.services import sec_request_gate as gate

_SUPPORTED = {
    "edgartools": "5.62.1", "httpxthrottlecache": "0.6.1",
    "pyrate-limiter": "4.3.0", "httpx2": "2.13.0", "httpx": "0.28.1",
}


class _ResponseFeedback(httpx.BaseTransport):
    def __init__(self, transport: httpx.BaseTransport):
        self.transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.transport.handle_request(request)
        try:
            gate.record_response_sync(response.status_code, response.headers.get("Retry-After"))
        except BaseException:
            response.close()
            raise
        return response

    def close(self) -> None:
        self.transport.close()


class _AsyncResponseFeedback(httpx.AsyncBaseTransport):
    def __init__(self, transport: httpx.AsyncBaseTransport):
        self.transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self.transport.handle_async_request(request)
        try:
            await gate.record_response_async(response.status_code, response.headers.get("Retry-After"))
        except BaseException:
            await response.aclose()
            raise
        return response

    async def aclose(self) -> None:
        await self.transport.aclose()


class FeedbackManager(HttpxThrottleCache):
    """Pinned instance transport factory: observe responses BELOW the disk cache."""

    def _get_transport(self, bypass_cache: bool, httpx_transport_params: dict) -> httpx.BaseTransport:
        outer = super()._get_transport(bypass_cache, httpx_transport_params)
        inner = outer.transport if isinstance(outer, CachingTransport) else outer
        if not isinstance(inner, RateLimitingTransport):
            raise gate.SECAdmissionUnavailable("SEC synchronous transport shape changed")
        wrapped = _ResponseFeedback(inner)
        if isinstance(outer, CachingTransport):
            outer.transport = wrapped
            return outer
        return wrapped

    def _get_async_transport(self, bypass_cache: bool, httpx_transport_params: dict) -> httpx.AsyncBaseTransport:
        outer = super()._get_async_transport(bypass_cache, httpx_transport_params)
        inner = outer.transport if isinstance(outer, CachingTransport) else outer
        if not isinstance(inner, AsyncRateLimitingTransport):
            raise gate.SECAdmissionUnavailable("SEC asynchronous transport shape changed")
        wrapped = _AsyncResponseFeedback(inner)
        if isinstance(outer, CachingTransport):
            outer.transport = wrapped
            return outer
        return wrapped


def _copy_manager(original: HttpxThrottleCache, *, uncached: bool = False) -> FeedbackManager:
    """Copy the supported dataclass configuration, never an open client/lock."""
    manager = FeedbackManager(
        httpx_params=original.httpx_params.copy(),
        cache_rules={host: rules.copy() for host, rules in original.cache_rules.items()},
        rate_limiter_enabled=True, cache_mode="Disabled" if uncached else original.cache_mode,
        request_per_sec_limit=original.request_per_sec_limit,
        rate_limiter=original.rate_limiter,
        user_agent=original.user_agent, user_agent_factory=original.user_agent_factory,
        cache_dir=original.cache_dir,
    )
    manager.proxy = original.proxy
    return manager


class FleetAdmissionLimiter:
    """The transport ignores booleans: every denial must RAISE before sending."""

    def __init__(self, local_limiter):
        self.local_limiter = local_limiter

    def try_acquire(self, name: str) -> bool:
        deadline = gate.admission_deadline()
        if not self.local_limiter.try_acquire(name, timeout=gate._remaining(deadline)):
            raise gate.SECAdmissionUnavailable("SEC local admission wait expired", retryable=True)
        gate.acquire_sync(deadline=deadline)
        return True

    async def try_acquire_async(self, name: str) -> bool:
        deadline = gate.admission_deadline()
        if not await self.local_limiter.try_acquire_async(name, timeout=gate._remaining(deadline)):
            raise gate.SECAdmissionUnavailable("SEC local admission wait expired", retryable=True)
        await gate.acquire_async(deadline=deadline)
        return True


def _managed_uncached_sgml(url: str) -> str:
    from edgar.httpclient import HTTP_MGR

    if not isinstance(HTTP_MGR, FeedbackManager) or not isinstance(HTTP_MGR.rate_limiter, FleetAdmissionLimiter):
        raise gate.SECAdmissionUnavailable("SEC managed transport configuration changed")
    # A cached manager ignores bypass_cache on later calls. A fresh uncached
    # manager shares its exact limiter, identity, TLS and effective proxy instead.
    # Constructor environment handling may overwrite proxy; restore the original
    # effective value before opening the client (never expose it in errors/logs).
    with _copy_manager(HTTP_MGR, uncached=True) as manager:
        with manager.http_client() as client:
            return client.get(url).text


def install_edgar_admission() -> None:
    """Install before any client opens; unknown dependency shape fails closed."""
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return
    from edgar import httpclient
    from edgar.sgml import sgml_common

    HTTP_MGR = httpclient.HTTP_MGR
    if isinstance(HTTP_MGR.rate_limiter, FleetAdmissionLimiter):
        if not isinstance(HTTP_MGR, FeedbackManager) or sgml_common._fetch_url_directly is not _managed_uncached_sgml:
            raise gate.SECAdmissionUnavailable("SEC managed SGML configuration changed")
        return
    if (
        any(version(package) != expected for package, expected in _SUPPORTED.items())
        or list(signature(sgml_common._fetch_url_directly).parameters) != ["url"]
        or any(list(signature(getattr(HttpxThrottleCache, method)).parameters)
               != ["self", "bypass_cache", "httpx_transport_params"]
               for method in ("_get_transport", "_get_async_transport"))
        or HTTP_MGR._client is not None
        or not HTTP_MGR.rate_limiter_enabled
        or HTTP_MGR.rate_limiter is None
        or HTTP_MGR.httpx_params.get("proxy") is not None
        or HTTP_MGR.httpx_params.get("mounts") is not None
    ):
        raise gate.SECAdmissionUnavailable("SEC managed transport setup is unsupported")
    manager = _copy_manager(HTTP_MGR)
    manager.rate_limiter = FleetAdmissionLimiter(HTTP_MGR.rate_limiter)
    httpclient.HTTP_MGR = manager
    sgml_common._fetch_url_directly = _managed_uncached_sgml
