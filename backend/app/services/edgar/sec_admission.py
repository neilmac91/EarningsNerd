"""Versioned integration with the pinned EdgarTools transport owners.

Only the manager instance's limiter and one identified SGML fallback are adapted.
No HTTPX class/global function or installed dependency file is changed.
"""
from __future__ import annotations

from importlib.metadata import version
from inspect import signature

from app.config import settings
from app.services import sec_request_gate as gate

_SUPPORTED = {
    "edgartools": "5.62.1", "httpxthrottlecache": "0.6.1",
    "pyrate-limiter": "4.3.0", "httpx2": "2.13.0", "httpx": "0.28.1",
}


class FleetAdmissionLimiter:
    """The transport ignores booleans: every denial must RAISE before sending."""

    def __init__(self, local_limiter):
        self.local_limiter = local_limiter

    def try_acquire(self, name: str) -> bool:
        deadline = gate.admission_deadline()
        if not self.local_limiter.try_acquire(name, timeout=gate._remaining(deadline)):
            raise gate.SECAdmissionUnavailable("SEC local admission wait expired")
        gate.acquire_sync(deadline=deadline)
        return True

    async def try_acquire_async(self, name: str) -> bool:
        deadline = gate.admission_deadline()
        if not await self.local_limiter.try_acquire_async(name, timeout=gate._remaining(deadline)):
            raise gate.SECAdmissionUnavailable("SEC local admission wait expired")
        await gate.acquire_async(deadline=deadline)
        return True


def _managed_uncached_sgml(url: str) -> str:
    from edgar.httpclient import HTTP_MGR
    from httpxthrottlecache import HttpxThrottleCache

    if not isinstance(HTTP_MGR.rate_limiter, FleetAdmissionLimiter):
        raise gate.SECAdmissionUnavailable("SEC managed transport configuration changed")
    # A cached manager ignores bypass_cache on later calls. A fresh uncached
    # manager shares its exact limiter, identity, TLS and effective proxy instead.
    # Constructor environment handling may overwrite proxy; restore the original
    # effective value before opening the client (never expose it in errors/logs).
    with HttpxThrottleCache(
        httpx_params=HTTP_MGR.httpx_params.copy(), cache_mode="Disabled",
        rate_limiter=HTTP_MGR.rate_limiter, rate_limiter_enabled=True,
        user_agent=HTTP_MGR.user_agent, user_agent_factory=HTTP_MGR.user_agent_factory,
    ) as manager:
        manager.proxy = HTTP_MGR.proxy
        with manager.http_client() as client:
            return client.get(url).text


def install_edgar_admission() -> None:
    """Install before any client opens; unknown dependency shape fails closed."""
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return
    from edgar.httpclient import HTTP_MGR
    from edgar.sgml import sgml_common

    if isinstance(HTTP_MGR.rate_limiter, FleetAdmissionLimiter):
        if sgml_common._fetch_url_directly is not _managed_uncached_sgml:
            raise gate.SECAdmissionUnavailable("SEC managed SGML configuration changed")
        return
    if (
        any(version(package) != expected for package, expected in _SUPPORTED.items())
        or list(signature(sgml_common._fetch_url_directly).parameters) != ["url"]
        or HTTP_MGR._client is not None
        or not HTTP_MGR.rate_limiter_enabled
        or HTTP_MGR.rate_limiter is None
        or HTTP_MGR.httpx_params.get("proxy") is not None
        or HTTP_MGR.httpx_params.get("mounts") is not None
    ):
        raise gate.SECAdmissionUnavailable("SEC managed transport setup is unsupported")
    HTTP_MGR.rate_limiter = FleetAdmissionLimiter(HTTP_MGR.rate_limiter)
    sgml_common._fetch_url_directly = _managed_uncached_sgml
