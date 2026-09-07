"""Process-wide admission gate for provider (LLM) requests.

Every wire call to the AI provider — summary primary and fallback attempts, section recovery,
Copilot chat and Analysis narration — passes through ``admit`` so one process never holds more
than ``settings.AI_PROVIDER_MAX_INFLIGHT`` streams on the shared key. Until E09b nothing bounded
the chat paths at all: each Cloud Run instance could hold up to its request concurrency in
provider streams, and provider 429/5xx replies fed the retry loop instead of a queue.

The gate is a slot, not a rate: a request waits for a slot only as long as its own remaining
budget, so a saturated process fails callers fast (``TimeoutError``, which the existing
classifiers treat like any other timeout) rather than stacking them behind the provider.
Process scope, like the generation semaphore and the L1 caches: fleet totals are the sum over
instances and job logs (``docs/OPERATIONS.md``). Values at or below 0 disable the ceiling.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from app.config import settings

_UNBOUNDED = 2**31

_semaphore: Optional[asyncio.Semaphore] = None
_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None
_semaphore_limit: Optional[int] = None
_counters = {"in_flight": 0, "waiting": 0, "admitted": 0, "rejected": 0, "peak_in_flight": 0}


def limit() -> int:
    configured = settings.AI_PROVIDER_MAX_INFLIGHT
    return configured if configured > 0 else _UNBOUNDED


def _get_semaphore() -> asyncio.Semaphore:
    """Lazily built and keyed to the running loop (asyncio primitives bind on first contended
    await; pytest creates a loop per test) and to the configured limit, so a settings change is
    honoured by the next request instead of the next process."""
    global _semaphore, _semaphore_loop, _semaphore_limit
    loop = asyncio.get_running_loop()
    current = limit()
    if _semaphore is None or _semaphore_loop is not loop or _semaphore_limit != current:
        _semaphore = asyncio.Semaphore(current)
        _semaphore_loop = loop
        _semaphore_limit = current
    return _semaphore


@asynccontextmanager
async def admit(deadline_seconds: float) -> AsyncIterator[None]:
    """Hold one provider slot for the block; wait at most ``deadline_seconds`` for it.

    A wait that ends without a slot counts as ``rejected`` and releases nothing: past the deadline
    it raises ``TimeoutError`` without touching the wire, and a wait cancelled from outside (the
    caller's own budget firing in the same tick, or a client walking away) propagates the
    cancellation.
    """
    semaphore = _get_semaphore()
    _counters["waiting"] += 1
    try:
        async with asyncio.timeout(max(deadline_seconds, 0.0)):
            await semaphore.acquire()
    except TimeoutError:
        _counters["rejected"] += 1
        raise TimeoutError("Provider admission wait exceeded the request budget") from None
    except asyncio.CancelledError:
        _counters["rejected"] += 1
        raise
    finally:
        _counters["waiting"] -= 1
    _counters["admitted"] += 1
    _counters["in_flight"] += 1
    _counters["peak_in_flight"] = max(_counters["peak_in_flight"], _counters["in_flight"])
    try:
        yield
    finally:
        _counters["in_flight"] -= 1
        semaphore.release()


def snapshot() -> dict:
    """Counters for `/metrics`; reads only, never touches the semaphore."""
    return {"scope": "process", "limit": settings.AI_PROVIDER_MAX_INFLIGHT, **_counters}


def reset() -> None:
    """Tests only: forget the semaphore and zero the counters."""
    global _semaphore, _semaphore_loop, _semaphore_limit
    _semaphore = _semaphore_loop = _semaphore_limit = None
    for key in _counters:
        _counters[key] = 0
