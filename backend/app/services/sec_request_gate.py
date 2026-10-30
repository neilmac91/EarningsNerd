"""Optional fleet SEC request admission, independent of request-owned DB sessions.

One PostgreSQL row spaces committed admissions by 125 ms. No future permits are
reserved, so an idle or restarted process gets no burst credit. This bounds
admissions, not socket writes after a process pause or connection-pool wait.
The switch stays off until every SEC caller uses it and old executions drain.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import threading
import time
from typing import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from app.config import settings

MIN_INTERVAL_SECONDS = 0.125
_BUSY_WAIT_SECONDS = 0.025


class SECAdmissionUnavailable(Exception):
    """Local coordinator failure; never evidence of an upstream SEC 429."""


@dataclass(frozen=True)
class AdmissionDecision:
    wait_seconds: float
    granted_at: datetime | None = None


class PostgresRequestGate:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._attempt_lock = threading.Lock()

    def try_grant(self) -> AdmissionDecision:
        """Commit one due permit, or return a delay without retaining a lock.

        The clock is read after the NOWAIT row lock. A failed commit never
        returns a permit. A missing row/table and all non-contention DB errors
        fail closed; exception messages can contain credentials and are hidden.
        """
        if not self._attempt_lock.acquire(blocking=False):
            return AdmissionDecision(_BUSY_WAIT_SECONDS)
        try:
            with self.engine.begin() as conn:
                if conn.dialect.name != "postgresql":
                    raise SECAdmissionUnavailable("SEC admission requires PostgreSQL")
                conn.execute(text("SET LOCAL statement_timeout = '500ms'"))
                conn.execute(text("SET LOCAL lock_timeout = '100ms'"))
                due = conn.execute(text(
                    "SELECT next_admission_at FROM earningsnerd_sec_request_gate "
                    "WHERE id = 1 FOR UPDATE NOWAIT"
                )).scalar_one_or_none()
                if due is None:
                    raise SECAdmissionUnavailable("SEC admission state is unavailable")
                now = conn.execute(text("SELECT clock_timestamp()")).scalar_one()
                if due > now:
                    decision = AdmissionDecision((due - now).total_seconds())
                else:
                    conn.execute(text(
                        "UPDATE earningsnerd_sec_request_gate SET next_admission_at = :due WHERE id = 1"
                    ), {"due": now + timedelta(seconds=MIN_INTERVAL_SECONDS)})
                    decision = AdmissionDecision(0.0, now)
            return decision
        except DBAPIError as exc:
            if getattr(exc.orig, "pgcode", None) == "55P03":
                return AdmissionDecision(_BUSY_WAIT_SECONDS)
            raise SECAdmissionUnavailable("SEC admission coordinator is unavailable") from None
        except SECAdmissionUnavailable:
            raise
        except Exception:
            raise SECAdmissionUnavailable("SEC admission coordinator is unavailable") from None
        finally:
            self._attempt_lock.release()


_gate: PostgresRequestGate | None = None
_gate_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
# At most one submitted async DB unit per process, with no unbounded executor
# queue. Sync callers contend through the gate's nonblocking attempt lock.
_async_slot = threading.BoundedSemaphore(1)


def _get_gate() -> PostgresRequestGate:
    global _gate
    with _gate_lock:
        if _gate is None:
            # Reuse the already safely parsed URL, never a second request-pool
            # checkout. This dedicated connection must enter the fleet DB budget.
            from app.database import _DATABASE_URL

            if _DATABASE_URL.get_backend_name() != "postgresql":
                raise SECAdmissionUnavailable("SEC admission requires PostgreSQL")
            engine = create_engine(
                _DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=0.25,
                pool_recycle=300,
                connect_args={
                    "connect_timeout": 2, "tcp_user_timeout": 2000,
                    "keepalives": 1, "keepalives_idle": 2,
                    "keepalives_interval": 1, "keepalives_count": 2,
                },
            )
            _gate = PostgresRequestGate(engine)
        return _gate


def admission_deadline() -> float:
    return time.monotonic() + settings.SEC_DISTRIBUTED_WAIT_SECONDS


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SECAdmissionUnavailable("SEC admission wait expired")
    return remaining


def _delay(decision: AdmissionDecision, deadline: float) -> float:
    return min(_remaining(deadline), min(max(decision.wait_seconds, 0.005), 0.25) + random.uniform(0, 0.01))


def acquire_sync(*, deadline: float | None = None) -> None:
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return
    deadline = min(deadline, admission_deadline()) if deadline is not None else admission_deadline()
    while True:
        _remaining(deadline)
        decision = _get_gate().try_grant()
        _remaining(deadline)  # A delayed DB return cannot authorize a late send.
        if decision.granted_at is not None:
            return
        time.sleep(_delay(decision, deadline))


async def _try_grant_async() -> AdmissionDecision:
    global _executor
    if not _async_slot.acquire(blocking=False):
        return AdmissionDecision(_BUSY_WAIT_SECONDS)
    try:
        with _gate_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sec_admission")
        # The unit owns its short transaction. Cancellation may waste one
        # committed permit but can never schedule an HTTP request from this worker.
        future = _executor.submit(lambda: _get_gate().try_grant())
    except BaseException:
        _async_slot.release()
        raise
    future.add_done_callback(lambda _: _async_slot.release())
    return await asyncio.wrap_future(future)


async def acquire_async(*, deadline: float | None = None) -> None:
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return
    deadline = min(deadline, admission_deadline()) if deadline is not None else admission_deadline()
    try:
        async with asyncio.timeout(_remaining(deadline)):
            while True:
                _remaining(deadline)
                decision = await _try_grant_async()
                _remaining(deadline)
                if decision.granted_at is not None:
                    return
                await asyncio.sleep(_delay(decision, deadline))
    except TimeoutError:
        raise SECAdmissionUnavailable("SEC admission wait expired") from None


def sec_request_options(*, on_wait: Callable[[bool], None] | None = None) -> dict:
    """Owned-client hooks run before EACH redirect/auth resend, with proxies intact.

    Existing local execute pacing precedes this shared admission. Native HTTPX
    connection retries must remain zero; arbitrary supplied retry transports are
    not supported. No global HTTPX state or other service's clients are changed.
    """
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return {}

    async def admit(request) -> None:
        if on_wait is not None:
            on_wait(True)
        await acquire_async()
        if on_wait is not None:
            on_wait(False)

    return {"event_hooks": {"request": [admit]}}
