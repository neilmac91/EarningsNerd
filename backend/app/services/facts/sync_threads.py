"""The companyfacts sync's own threads, off the event loop and out of its default executor.

``ingest_companyfacts_by_id``'s database units (the freshness read, a follower's re-read, the
persist) wait for a pool slot here. A slot holder can need a default-executor thread for its next
step (login keeps its connection checked out while it awaits bcrypt through ``asyncio.to_thread``),
so units waiting there could leave neither side able to move until the pool timed out; the Copilot's
lookups keep to threads of their own for the same reason (``copilot_chat._LOOKUP_THREADS``). A unit
holds no slot while it waits for a thread and needs no other thread while it holds one. Two threads
keep the sync to half of the API's four slots.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

import anyio

from app.services.facts.transport import logger

_T = TypeVar("_T")

_SYNC_THREADS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="companyfacts_sync")


def submit(unit: Callable[[], _T]) -> asyncio.Future[_T]:
    """``asyncio.to_thread`` on the sync's own threads: the same context copy."""
    call = functools.partial(contextvars.copy_context().run, unit)
    return asyncio.get_running_loop().run_in_executor(_SYNC_THREADS, call)


async def run_to_completion(unit: Callable[[], _T]) -> _T:
    """Run ``unit`` on the sync's threads and outlast a cancellation of the caller.

    A thread cannot be stopped, so a cancelled caller waits for the unit before the cancellation
    goes on: the leader's ``finally`` must not wake followers (or let another leader start) while
    its persist is still writing. In durable mode the coverage route cancels its sync task at its
    wait budget, or when its own request is cancelled. The wait is shielded from anyio's cancel
    scopes, which would otherwise cancel it again at every loop step; a second ``Task.cancel()``,
    which only the loop's teardown sends, ends it.
    """
    work = submit(unit)
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        with anyio.CancelScope(shield=True):
            await asyncio.wait({work})
        if not work.cancelled() and work.exception() is not None:
            # The cancellation is all the caller sees (the route's gather swallows it), so say here.
            logger.error("companyfacts sync unit failed after its caller was cancelled", exc_info=work.exception())
        raise
