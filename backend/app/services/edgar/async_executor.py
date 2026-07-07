"""
Async Executor for EdgarTools

EdgarTools is a synchronous library, but our FastAPI backend is async.
This module provides utilities to run EdgarTools operations in a dedicated
thread pool without blocking the event loop.

Usage:
    from app.services.edgar.async_executor import run_in_executor

    # Run synchronous EdgarTools call asynchronously
    company = await run_in_executor(Company, "AAPL")

    # With timeout
    company = await run_in_executor_with_timeout(
        lambda: Company("AAPL"),
        timeout=30.0
    )
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Callable, TypeVar, ParamSpec, Awaitable

from .config import EDGAR_THREAD_POOL_SIZE, EDGAR_DEFAULT_TIMEOUT_SECONDS
from .exceptions import EdgarTimeoutError, translate_edgartools_exception
from .circuit_breaker import edgar_circuit_breaker

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

# Dedicated thread pool for EdgarTools operations. Using a dedicated pool prevents EdgarTools from
# consuming threads needed by other async operations. Created lazily via _get_executor() so that a
# prior shutdown (app lifespan teardown, or a test that ran the app lifespan) auto-heals: submitting
# work after shutdown would otherwise raise "cannot schedule new futures after shutdown" forever.
_edgar_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    """Return a live EdgarTools thread pool, (re)creating it if it was never started or was shut down."""
    global _edgar_executor
    ex = _edgar_executor
    if ex is None or getattr(ex, "_shutdown", False):
        ex = ThreadPoolExecutor(
            max_workers=EDGAR_THREAD_POOL_SIZE,
            thread_name_prefix="edgar_",
        )
        _edgar_executor = ex
    return ex


async def run_in_executor(
    func: Callable[..., T],
    *args,
    **kwargs
) -> T:
    """
    Run a synchronous function in the EdgarTools thread pool.

    This allows synchronous EdgarTools calls to be awaited without
    blocking the async event loop.

    Args:
        func: Synchronous function to execute
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        The return value of func

    Raises:
        EdgarError: Translated from any EdgarTools exception
    """
    loop = asyncio.get_running_loop()

    try:
        # Run the sync function in our dedicated thread pool (lazily (re)created if shut down)
        result = await loop.run_in_executor(
            _get_executor(),
            lambda: func(*args, **kwargs)
        )
        return result
    except Exception as exc:
        # Translate EdgarTools exceptions to our types
        raise translate_edgartools_exception(exc) from exc


async def run_in_executor_with_timeout(
    func: Callable[[], T],
    timeout: float = EDGAR_DEFAULT_TIMEOUT_SECONDS,
) -> T:
    """
    Run a synchronous function with a timeout.

    Args:
        func: Zero-argument callable (use lambda for args)
        timeout: Maximum seconds to wait

    Returns:
        The return value of func

    Raises:
        EdgarTimeoutError: If the operation times out
        EdgarError: Translated from any EdgarTools exception

    Example:
        company = await run_in_executor_with_timeout(
            lambda: Company("AAPL"),
            timeout=30.0
        )
    """
    try:
        return await asyncio.wait_for(
            run_in_executor(func),
            timeout=timeout
        )
    except asyncio.TimeoutError as exc:
        raise EdgarTimeoutError(
            message=f"EdgarTools operation timed out after {timeout}s",
            timeout_seconds=timeout,
            cause=exc,
        )


async def run_with_circuit_breaker(
    func: Callable[[], T],
    timeout: float = EDGAR_DEFAULT_TIMEOUT_SECONDS,
    use_circuit_breaker: bool = True,
) -> T:
    """
    Run a synchronous function with timeout and circuit breaker protection.

    This is the recommended way to call EdgarTools operations in production.
    It combines timeout handling with circuit breaker protection for resilience.

    Args:
        func: Zero-argument callable (use lambda for args)
        timeout: Maximum seconds to wait
        use_circuit_breaker: Whether to use circuit breaker (default True)

    Returns:
        The return value of func

    Raises:
        CircuitOpenError: If the circuit breaker is open
        EdgarTimeoutError: If the operation times out
        EdgarError: Translated from any EdgarTools exception

    Example:
        company = await run_with_circuit_breaker(
            lambda: Company("AAPL"),
            timeout=30.0
        )
    """
    if not use_circuit_breaker:
        return await run_in_executor_with_timeout(func, timeout)

    async with edgar_circuit_breaker:
        return await run_in_executor_with_timeout(func, timeout)


def async_edgar(func: Callable[P, T]) -> Callable[P, Awaitable[T]]:
    """
    Decorator to convert a synchronous EdgarTools function to async.

    Usage:
        @async_edgar
        def get_company(ticker: str) -> Company:
            return Company(ticker)

        # Now can be awaited
        company = await get_company("AAPL")
    """
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return await run_in_executor(func, *args, **kwargs)
    return wrapper


class AsyncEdgarContext:
    """
    Context manager for batching EdgarTools operations.

    This can be used to ensure proper cleanup and provide
    a clean interface for multiple operations.

    Usage:
        async with AsyncEdgarContext() as ctx:
            company = await ctx.run(Company, "AAPL")
            filings = await ctx.run(lambda: company.get_filings(form="10-K"))
    """

    def __init__(self, timeout: float = EDGAR_DEFAULT_TIMEOUT_SECONDS):
        self.timeout = timeout
        self._operations_count = 0

    async def __aenter__(self) -> "AsyncEdgarContext":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        logger.debug(f"AsyncEdgarContext completed {self._operations_count} operations")

    async def run(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Run a synchronous function within this context."""
        self._operations_count += 1
        return await run_in_executor_with_timeout(
            lambda: func(*args, **kwargs),
            timeout=self.timeout
        )


def get_executor_stats() -> dict:
    """
    Get statistics about the EdgarTools thread pool.

    Useful for monitoring and debugging.
    """
    ex = _edgar_executor
    return {
        "max_workers": EDGAR_THREAD_POOL_SIZE,
        "thread_name_prefix": "edgar_",
        # ThreadPoolExecutor doesn't expose active count directly,
        # but we can check if threads are being used via _threads
        "threads_created": len(ex._threads) if ex is not None and hasattr(ex, '_threads') else 0,
    }


def shutdown_executor(wait: bool = True) -> None:
    """
    Shutdown the EdgarTools thread pool.

    Call this during application shutdown to ensure clean cleanup. Clears the module reference so a
    subsequent submission auto-heals via _get_executor() (relevant when the app lifespan runs more
    than once in a process, e.g. across tests) rather than failing permanently.

    Args:
        wait: Whether to wait for pending operations to complete
    """
    global _edgar_executor
    ex = _edgar_executor
    if ex is None:
        return
    logger.info("Shutting down EdgarTools thread pool")
    ex.shutdown(wait=wait)
    _edgar_executor = None
