"""Keep synchronous workers owned until their request has finished cleaning up.

An asyncio timeout cancels the waiter, not a running thread. Ownership records the
concurrent future, so cleanup can join the actual worker after that waiter exits.
Worker functions keep responsibility for opening and closing their own sessions.
"""

from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from functools import partial
from typing import Callable, TypeVar

import anyio
from fastapi.concurrency import run_in_threadpool

T = TypeVar("T")
_current_work: contextvars.ContextVar[RequestWork | None] = contextvars.ContextVar(
    "request_work", default=None,
)
_sync_executor: ThreadPoolExecutor | None = None


class RequestWork:
    """Actual worker futures belonging to one request or summary generation."""

    def __init__(self, *, enabled: bool = True) -> None:
        self._futures: set[Future] = set()
        self._closing = False
        self._enabled = enabled

    @contextmanager
    def activate(self):
        """Bind briefly around an await/task creation; never hold across a generator yield."""
        if not self._enabled:
            yield self
            return
        token = _current_work.set(self)
        try:
            yield self
        finally:
            _current_work.reset(token)

    def submit(self, executor: ThreadPoolExecutor, call: Callable[[], T]) -> Future[T]:
        if self._closing:
            raise RuntimeError("request work is already closing")
        future = executor.submit(call)
        self._futures.add(future)
        return future

    async def drain(self) -> None:
        """Cancel queued calls and join running calls, without abandoning their threads.

        There is deliberately no cleanup timeout: async deadlines cannot terminate
        Python threads. Socket/SQL operation timeouts remain the worker's concern.
        """
        self._closing = True
        futures = tuple(self._futures)
        for future in futures:
            future.cancel()  # succeeds only when the callable has not started
        if futures:
            with anyio.CancelScope(shield=True):
                await asyncio.gather(
                    *(asyncio.wrap_future(future) for future in futures),
                    return_exceptions=True,
                )
        self._futures.clear()


@asynccontextmanager
async def request_work_scope():
    """Own worker calls made by this request and inherited async child tasks."""
    work = RequestWork()
    with work.activate():
        try:
            yield work
        finally:
            await work.drain()


async def run_executor_work(
    executor: ThreadPoolExecutor, func: Callable[..., T], *args, **kwargs,
) -> T:
    """Await a real executor future, registering it with the active owner if any."""
    context = contextvars.copy_context()
    call = partial(context.run, partial(func, *args, **kwargs))
    work = _current_work.get()
    future = work.submit(executor, call) if work is not None else executor.submit(call)
    return await asyncio.wrap_future(future)


async def run_owned_sync(func: Callable[..., T], *args, **kwargs) -> T:
    """Dispatch a session-owning SQL/CPU unit separately from slow SEC workers.

    The 40-worker cap matches AnyIO's existing default thread capacity. Threads
    start lazily; running units always finish and close their own sessions.
    Without an owning scope retain the existing AnyIO dispatch/deadline contract;
    request callers opt into real-worker cleanup by activating their owner.
    """
    if _current_work.get() is None:
        return await run_in_threadpool(func, *args, **kwargs)
    global _sync_executor
    if _sync_executor is None or getattr(_sync_executor, "_shutdown", False):
        _sync_executor = ThreadPoolExecutor(max_workers=40, thread_name_prefix="request_")
    return await run_executor_work(_sync_executor, func, *args, **kwargs)
