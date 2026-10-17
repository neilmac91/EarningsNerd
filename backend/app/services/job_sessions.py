"""Run one job in a database session of its own, for work that outlives its request.

A FastAPI background task runs after the response, when the request's ``get_db`` session is
already closed, so a detached job opens its own session and closes it however the job ends. The
``/internal/jobs/*`` triggers' flag-off runs use these (``app/routers/internal.py``). The router
passes the service function by its own module attribute, so a test that patches that function
still reaches the call, and it keeps the log lines around the call.

``SessionLocal`` is imported at call time, as the router's runners did, so a test that patches
``app.database.SessionLocal`` reaches these helpers too.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Concatenate, ParamSpec, TypeVar

from sqlalchemy.orm import Session

P = ParamSpec("P")
T = TypeVar("T")


async def run_in_own_session(
    job: Callable[Concatenate[Session, P], Awaitable[T]], /, *args: P.args, **kwargs: P.kwargs,
) -> T:
    """Await ``job(db, *args, **kwargs)`` in a new session and close it however the job ends."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return await job(db, *args, **kwargs)
    finally:
        db.close()


def run_in_own_session_sync(
    job: Callable[Concatenate[Session, P], T], /, *args: P.args, **kwargs: P.kwargs,
) -> T:
    """``run_in_own_session`` for a synchronous job. Call it from a plain-function background task,
    which FastAPI runs in its threadpool, so the job stays off the event loop."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return job(db, *args, **kwargs)
    finally:
        db.close()
