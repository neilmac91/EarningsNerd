"""Unspent copies of the company-filings route's work budgets, for the tests that drive the route.

``app.routers.filings`` keeps two budgets as module state, like its handoff guard: the durable handoffs'
(``VISIT_TASK_BUDGET``, one per process) and the live SEC fetch's (``LIVE_FETCH_LIMITER``, per client IP).
Every TestClient request comes from one address, so a test that drives the route takes fresh copies, or
the tests before it in the same process would have spent them.
"""
import pytest

from app.routers import filings
from app.services.rate_limiter import RateLimiter


def unspend_filings_budgets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the running test production-sized budgets that nothing has spent."""
    for name in ("VISIT_TASK_BUDGET", "LIVE_FETCH_LIMITER"):
        spent = getattr(filings, name)
        monkeypatch.setattr(filings, name, RateLimiter(spent.limit, spent.window_seconds))
