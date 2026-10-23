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
2 s and 3 s, and the serving-price read runs one at a time per process
(``lessons/ops-stripe-calls-wait-on-threads-of-their-own.md``). The account deletion calls Stripe on the
loop until E171 hands its cancellation here. Gate: ``tests/unit/test_stripe_threads_allowlist.py``.
"""
from __future__ import annotations

import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")

_STRIPE_THREADS = ThreadPoolExecutor(max_workers=8, thread_name_prefix="stripe_call")


async def run_on_stripe_threads(func: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    """``asyncio.to_thread`` on the Stripe threads: the same context copy and cancellation."""
    call = functools.partial(contextvars.copy_context().run, func, *args, **kwargs)
    return await asyncio.get_running_loop().run_in_executor(_STRIPE_THREADS, call)
