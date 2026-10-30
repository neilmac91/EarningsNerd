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
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import logging
import random
import threading
import time
from typing import Callable, TypeVar

from sqlalchemy import DateTime, cast, create_engine, func, literal, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import SessionLocal
from app.models.sec_request_gate import SECRequestGate

MIN_INTERVAL_SECONDS = 0.125
_BUSY_WAIT_SECONDS = 0.025
logger = logging.getLogger(__name__)
T = TypeVar("T")


class SECAdmissionUnavailable(Exception):
    """Local coordinator failure; never evidence of an upstream SEC 429."""


@dataclass(frozen=True)
class AdmissionDecision:
    wait_seconds: float
    granted_at: datetime | None = None


@dataclass(frozen=True)
class Cooldown:
    seconds: int | None = None
    until: datetime | None = None
    indefinite: bool = False


def response_cooldown(status: int, retry_after: str | None) -> Cooldown | None:
    """Parse without shortening a positive server hint or retaining raw headers."""
    if status not in {429, 503}:
        return None
    header = (retry_after or "").strip()
    if header.isascii() and header.isdigit():
        digits = header.lstrip("0") or "0"
        # Avoid int()'s digit limit and datetime overflow. PostgreSQL infinity
        # preserves an unrepresentably long positive hint without a finite cap.
        return Cooldown(indefinite=True) if len(digits) > 18 else Cooldown(seconds=int(digits))
    if header:
        try:
            until = parsedate_to_datetime(header)
            until = until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until.astimezone(timezone.utc)
            return Cooldown(until=until)
        except (TypeError, ValueError, OverflowError):
            pass
    # A refusal without a usable hint still pauses the fleet briefly. A 503
    # without a hint retains the owner's existing transient-error behavior.
    return Cooldown(seconds=1) if status == 429 else None


class PostgresRequestGate:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._attempt_lock = threading.Lock()
        self._sessions = sessionmaker(**{**SessionLocal.kw, "bind": engine})

    def _locked_row(self, db: Session) -> SECRequestGate:
        if self.engine.dialect.name != "postgresql":
            raise SECAdmissionUnavailable("SEC admission requires PostgreSQL")
        db.execute(select(func.set_config("TimeZone", "UTC", True)))
        db.execute(select(func.set_config("statement_timeout", "500ms", True)))
        db.execute(select(func.set_config("lock_timeout", "100ms", True)))
        row = db.execute(select(SECRequestGate).where(SECRequestGate.id == 1).with_for_update(nowait=True)).scalar_one_or_none()
        if row is None:
            raise SECAdmissionUnavailable("SEC admission state is unavailable")
        return row

    def try_grant(self) -> AdmissionDecision:
        """Commit one due permit, or return a delay without retaining a lock.

        The clock is read after the NOWAIT row lock. A failed commit never
        returns a permit. A missing row/table and all non-contention DB errors
        fail closed; exception messages can contain credentials and are hidden.
        """
        if not self._attempt_lock.acquire(blocking=False):
            return AdmissionDecision(_BUSY_WAIT_SECONDS)
        try:
            with self._sessions.begin() as db:
                row = self._locked_row(db)
                due = max(row.next_admission_at, row.cooldown_until)
                now = db.execute(select(func.clock_timestamp())).scalar_one()
                if due > now:
                    decision = AdmissionDecision((due - now).total_seconds())
                else:
                    row.next_admission_at = now + timedelta(seconds=MIN_INTERVAL_SECONDS)
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

    def try_defer(self, hint: Cooldown) -> bool:
        """Persist the maximum embargo; a shorter/older hint cannot reopen it."""
        if not self._attempt_lock.acquire(blocking=False):
            return False
        try:
            with self._sessions.begin() as db:
                row = self._locked_row(db)
                now = db.execute(select(func.clock_timestamp())).scalar_one()
                try:
                    until = hint.until if hint.until is not None else now + timedelta(seconds=hint.seconds or 0)
                except OverflowError:
                    until = None
                if hint.indefinite or until is None:
                    row.cooldown_until = cast(literal("infinity"), DateTime(timezone=True))
                elif until > row.cooldown_until:
                    row.cooldown_until = until
            return True
        except DBAPIError as exc:
            if getattr(exc.orig, "pgcode", None) == "55P03":
                return False
            raise SECAdmissionUnavailable("SEC cooldown coordinator is unavailable") from None
        except SECAdmissionUnavailable:
            raise
        except Exception:
            raise SECAdmissionUnavailable("SEC cooldown coordinator is unavailable") from None
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


async def _db_attempt(call: Callable[[], T]) -> T | None:
    global _executor
    if not _async_slot.acquire(blocking=False):
        return None
    try:
        with _gate_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sec_admission")
        # The unit owns its short transaction. Cancellation may waste one
        # committed permit but can never schedule an HTTP request from this worker.
        future = _executor.submit(call)
    except BaseException:
        _async_slot.release()
        raise
    future.add_done_callback(lambda _: _async_slot.release())
    return await asyncio.wrap_future(future)


async def _try_grant_async() -> AdmissionDecision:
    result = await _db_attempt(lambda: _get_gate().try_grant())
    return result if result is not None else AdmissionDecision(_BUSY_WAIT_SECONDS)


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


def record_response_sync(status: int, retry_after: str | None) -> None:
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return
    hint = response_cooldown(status, retry_after)
    if hint is None:
        return
    deadline = admission_deadline()
    while True:
        _remaining(deadline)
        if _get_gate().try_defer(hint):
            return
        time.sleep(min(_BUSY_WAIT_SECONDS, _remaining(deadline)))


async def _persist_cooldown(hint: Cooldown) -> None:
    deadline = admission_deadline()
    try:
        async with asyncio.timeout(_remaining(deadline)):
            while True:
                _remaining(deadline)
                if await _db_attempt(lambda: _get_gate().try_defer(hint)):
                    return
                await asyncio.sleep(min(_BUSY_WAIT_SECONDS, _remaining(deadline)))
    except TimeoutError:
        raise SECAdmissionUnavailable("SEC cooldown persistence wait expired") from None


_feedback_tasks: set[asyncio.Task] = set()


def _feedback_finished(task: asyncio.Task) -> None:
    _feedback_tasks.discard(task)
    if not task.cancelled() and task.exception() is not None:
        # Never log a driver exception/header/URL. Consume failures even when the
        # caller disconnected while this bounded feedback task was running.
        logger.warning("SEC shared cooldown persistence failed")


async def record_response_async(status: int, retry_after: str | None) -> None:
    if not settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        return
    hint = response_cooldown(status, retry_after)
    if hint is None:
        return
    # Once a refusal arrives, cancellation of its caller must not discard the
    # feedback merely because the one DB slot is currently busy. The task owns
    # only bounded DB work; it cannot issue another HTTP request.
    task = asyncio.create_task(_persist_cooldown(hint))
    _feedback_tasks.add(task)
    task.add_done_callback(_feedback_finished)
    await asyncio.shield(task)


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

    async def feedback(response) -> None:
        await record_response_async(response.status_code, response.headers.get("Retry-After"))

    return {"event_hooks": {"request": [admit], "response": [feedback]}}
