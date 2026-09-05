"""Registry for the API process's main asyncio loop, for sync code that must run a coroutine.

asyncio primitives are not thread-safe and bind to the loop that first waits on them. The SEC rate
limiter (``sec_rate_limiter``) owns one such ``asyncio.Lock``; if a worker thread spun up its own
short-lived loop with ``asyncio.run`` while the API's loop was live, a contended acquire could bind
the lock to the wrong loop and every later SEC call on the main loop would raise "bound to a
different event loop" until restart. So sync bridges (FastAPI ``BackgroundTask`` bodies, threadpool
work) must hand coroutines to the app loop with ``asyncio.run_coroutine_threadsafe`` instead.

``main.py``'s lifespan registers the loop on startup and clears it on shutdown. Standalone
processes (Cloud Run jobs, scripts) never register one, and :func:`get_app_loop` returns ``None``
there — the bridge then owns a private loop via ``asyncio.run``, which is safe because no other
loop exists in that process.
"""
import asyncio
from typing import Optional

_app_loop: Optional[asyncio.AbstractEventLoop] = None


def set_app_loop(loop: Optional[asyncio.AbstractEventLoop]) -> None:
    """Register (or, with ``None``, clear) the process's long-lived application loop."""
    global _app_loop
    _app_loop = loop


def get_app_loop() -> Optional[asyncio.AbstractEventLoop]:
    """The registered application loop, or ``None`` if none is registered or it has closed."""
    loop = _app_loop
    if loop is None or loop.is_closed():
        return None
    return loop
