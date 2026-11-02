"""One bounded recovery pass across scan, scheduled and manual callers.

A private PostgreSQL session advisory lock covers the pass without holding a row
lock or transaction over queue HTTP. Its separate one-slot pool avoids borrowing
the last application connection while the pass needs short job transactions.
Cancellation drains those actual SQL workers before releasing ownership. The
20-second budget stops new work; cleanup is not a process-kill deadline and a
remote task create already accepted can still finish. Stable task names retain
the ambiguity recovery contract.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from contextvars import ContextVar
import threading
import time
from typing import Callable, TypeVar

import anyio
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import database
from app.services.durable_tasks import TaskUnavailable
from app.services.request_work import RequestWork, run_executor_work

RECOVERY_BUDGET_SECONDS = 20.0
SQL_STATEMENT_SECONDS = 3.0
# "SUMRECOV" in ASCII: one database-wide pass, not one lock per filing/account.
RECOVERY_LOCK_KEY = int.from_bytes(b"SUMRECOV", "big")
_deadline: ContextVar[float | None] = ContextVar("summary_recovery_deadline", default=None)
_owner: ContextVar[_RecoveryOwner | None] = ContextVar("summary_recovery_owner", default=None)
_slot = threading.Lock()
_engine: Engine | None = None
_executor: ThreadPoolExecutor | None = None
T = TypeVar("T")


class SummaryRecoveryUnavailable(TaskUnavailable):
    """Closed recovery refusal; internal HTTP keeps its existing safe 503 contract."""


def _guard_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None or getattr(_executor, "_shutdown", False):
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="summary_recovery_")
    return _executor


async def _guard_call(call: Callable[[], T]) -> T:
    """Guard calls cannot queue behind unrelated request-pool waiters.

    The nonblocking local permit admits one pass, and that pass awaits each
    owned call before another; this executor cannot accumulate recovery work.
    """
    return await run_executor_work(_guard_executor(), call)


def _remaining() -> float | None:
    deadline = _deadline.get()
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SummaryRecoveryUnavailable("Summary recovery deadline exceeded")
    return remaining


def apply_sql_budget(db: Session) -> None:
    """Bound only recovery's short job transactions; ordinary dispatch is unchanged."""
    remaining = _remaining()
    if remaining is None or db.get_bind().dialect.name != "postgresql":
        return
    milliseconds = max(1, int(min(SQL_STATEMENT_SECONDS, remaining) * 1000))
    db.execute(select(func.set_config("statement_timeout", f"{milliseconds}ms", True)))
    db.execute(select(func.set_config("lock_timeout", f"{min(1000, milliseconds)}ms", True)))


def _guard_engine() -> Engine:
    global _engine
    if _engine is None:
        # Like the shared SEC coordinator, reuse the safely parsed URL and bound
        # this extra connection independently of every producer's ordinary pool.
        _engine = create_engine(
            database._DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=0.25,
            pool_recycle=300, isolation_level="AUTOCOMMIT",
            connect_args={
                "connect_timeout": 2, "tcp_user_timeout": 2000,
                "keepalives": 1, "keepalives_idle": 2,
                "keepalives_interval": 1, "keepalives_count": 2,
            },
        )
    return _engine


class _RecoveryOwner:
    def __init__(self) -> None:
        self.connection: Connection | None = None
        self.backend_pid: int | None = None

    def acquire(self) -> bool:
        _remaining()
        # SQLite is the existing single-process development/test fallback. It
        # gets local exclusion only; it is never evidence of fleet ownership.
        if database._DATABASE_URL.get_backend_name() == "sqlite":
            return True
        if database._DATABASE_URL.get_backend_name() != "postgresql":
            raise SummaryRecoveryUnavailable("Summary recovery requires supported storage")
        self.connection = _guard_engine().connect().execution_options(isolation_level="AUTOCOMMIT")
        connection = self.connection
        connection.execute(select(func.set_config("statement_timeout", "3000ms", False)))
        connection.execute(select(func.set_config("lock_timeout", "1000ms", False)))
        acquired = bool(connection.execute(select(func.pg_try_advisory_lock(RECOVERY_LOCK_KEY))).scalar_one())
        if acquired:
            self.backend_pid = connection.execute(select(func.pg_backend_pid())).scalar_one()
        # AUTOCOMMIT means no server transaction is open while queue I/O runs.
        connection.commit()
        return acquired

    def check(self) -> None:
        _remaining()
        if self.connection is not None:
            if self.connection.invalidated or self.backend_pid is None:
                raise SummaryRecoveryUnavailable("Summary recovery ownership was lost")
            pid = self.connection.execute(select(func.pg_backend_pid())).scalar_one()
            self.connection.commit()
            if pid != self.backend_pid:
                raise SummaryRecoveryUnavailable("Summary recovery ownership was lost")
        _remaining()

    def release(self) -> None:
        if self.connection is not None:
            try:
                # Physically close the owning session, including after an error:
                # a session advisory lock must never return to a reusable pool.
                self.connection.invalidate()
            finally:
                self.connection.close()
                self.connection = None


async def before_handoff() -> None:
    """Check the deadline and live lock session immediately before queue I/O."""
    owner = _owner.get()
    if owner is not None:
        await _guard_call(owner.check)


async def _release_owner(owner: _RecoveryOwner) -> None:
    """Finish mandatory disconnect even when the request is repeatedly cancelled.

    Own the concurrent future directly: RequestWork cancels queued calls, while
    asyncio shutdown cancels every Task, including shielded cleanup children.
    Neither can discard this mandatory release. The local permit remains held.
    """
    try:
        actual = _guard_executor().submit(owner.release)
    except RuntimeError:
        # An externally shut-down executor rejected submission: no worker owns
        # the connection. Mandatory cleanup may block this exceptional path.
        owner.release()
        return
    cleanup = asyncio.wrap_future(actual)
    cancelled = False
    while True:
        try:
            with anyio.CancelScope(shield=True):
                # AnyIO shielding alone does not intercept native Task.cancel().
                await asyncio.shield(cleanup)
            break
        except asyncio.CancelledError:
            cancelled = True
            if actual.cancelled():
                # Only the actual future proves the callable never started. An
                # externally cancelled queue cannot discard mandatory release.
                owner.release()
                break
            if actual.done():
                actual.result()  # Propagate an actual failure without retrying a terminal future.
                break
            if cleanup.cancelled():
                # A cancelled wrapper does not prove its thread stopped. Rejoin
                # the same actual future without spawning another disconnect.
                cleanup = asyncio.wrap_future(actual)
    if cancelled:
        raise asyncio.CancelledError


@asynccontextmanager
async def recovery_scope():
    """Yield whether this caller owns the pass; contenders return without waiting."""
    if not _slot.acquire(blocking=False):
        yield False
        return
    owner = _RecoveryOwner()
    work = RequestWork()
    deadline_token = _deadline.set(time.monotonic() + RECOVERY_BUDGET_SECONDS)
    owner_token = _owner.set(owner)
    try:
        with work.activate():
            try:
                async with asyncio.timeout(RECOVERY_BUDGET_SECONDS):
                    acquired = await _guard_call(owner.acquire)
                    yield acquired
            finally:
                # A canceled asyncio waiter cannot abandon a SQL thread then
                # release the advisory lock behind that thread's transaction.
                await work.drain()
    except TimeoutError:
        raise SummaryRecoveryUnavailable("Summary recovery deadline exceeded") from None
    except SQLAlchemyError:
        # DB driver messages can quote credentials/connection details.
        raise SummaryRecoveryUnavailable("Summary recovery storage is unavailable") from None
    finally:
        try:
            try:
                await _release_owner(owner)
            except SQLAlchemyError:
                raise SummaryRecoveryUnavailable("Summary recovery cleanup is unavailable") from None
        finally:
            _owner.reset(owner_token)
            _deadline.reset(deadline_token)
            _slot.release()
