"""The billing routes' Stripe calls, on threads of their own, out of anyio's default worker threads (E170).

stripe-python's global client is synchronous: a call waits up to 80 s to connect and 80 s for each read,
and retries twice (``stripe.max_network_retries``). Through ``run_in_threadpool``, checkout's and the
billing portal's calls took anyio's default worker threads, 40 tokens a process that the auth lookups and
every route's thread-pool units also take, so in a Stripe brownout 40 calls in flight on one instance would
hold every token, and every unit in the process would wait for one of them to return. Here they share
threads of their own: a call waiting for one holds no token and no pool slot, so the rest of the instance
keeps moving. Eight is a cap, not a pool to tune: a checkout makes two or three calls one after another
and the portal one, so eight let a few payers through at once while Stripe answers normally, and a
brownout holds at most these eight threads, which nothing else needs. ``stripe_subscription_reader.py``
keeps the default threads: its own client makes one attempt with connect and read-inactivity limits of
2 s and 3 s by default (at most 10 s each), and the serving-price read runs one at a time per process
(``lessons/ops-stripe-calls-wait-on-threads-of-their-own.md``). The account deletion calls Stripe on the
loop until E171 hands its cancellation here. Gate: ``tests/unit/test_stripe_threads_allowlist.py``.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
import inspect
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")

_STRIPE_THREADS = ThreadPoolExecutor(max_workers=8, thread_name_prefix="stripe_call")

# Where an iterator that may hold a walk comes from: stripe-python's own, and the builtins' and itertools', which
# can keep one lazy (a generator, ``filter``, ``map``, ``zip``, ``itertools.islice``).
_WALK_MODULES = frozenset({"stripe", "builtins", "itertools"})


async def run_on_stripe_threads(func: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    """``asyncio.to_thread`` on the Stripe threads: the same context copy and cancellation.

    It refuses work that may make its Stripe requests after it returns, where its result is used, on the event
    loop: before the call, a generator, coroutine or async generator function; after it, a result that is a
    coroutine, an async generator, or an iterator from stripe-python (a list's ``auto_paging_iter()``, whose
    later pages are fetched as it is iterated), the builtins or ``itertools``, any of which may hold a walk.
    Refused after the call, the work has run up to its return. A list or other Stripe object is not an
    iterator and passes, and so do a walk inside a container and an iterator from anywhere else, which the
    gate's scan and review hold.
    """
    if inspect.isgeneratorfunction(func) or inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func):
        raise TypeError(f"{func!r} runs where it is iterated or awaited; hand over work that finishes here")
    call = functools.partial(contextvars.copy_context().run, func, *args, **kwargs)
    result = await asyncio.get_running_loop().run_in_executor(_STRIPE_THREADS, call)
    if inspect.iscoroutine(result) or inspect.isasyncgen(result):
        if inspect.iscoroutine(result):
            result.close()  # never awaited, so it would warn when collected
        raise TypeError(f"{func!r} returned a {type(result).__name__}, which runs where it is awaited or iterated; "
                        "return finished work")
    if isinstance(result, Iterator) and type(result).__module__.split(".")[0] in _WALK_MODULES:
        raise TypeError(f"{func!r} returned an iterator ({type(result).__name__}), which may make its requests where "
                        "it is used; return finished work, such as a list")
    return result
