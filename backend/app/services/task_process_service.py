"""Hard task deadline: kill and reap isolated work before ending its HTTP CPU allocation.

Async cancellation cannot terminate Python/native threads. A fresh exec also avoids sharing live
database connections with a forked child. Only the private, single-request worker enables this.
"""
from __future__ import annotations

import asyncio
import sys

import anyio

from app.config import settings
from app.services.durable_tasks import TaskEnvelope

_execution_lock = asyncio.Lock()


def _command() -> tuple[str, ...]:
    return (sys.executable, "-m", "app.services.task_process")


async def run_task_process(envelope: TaskEnvelope) -> None:
    if not settings.TASKS_WORKER_PROCESS:
        raise RuntimeError("Task execution is restricted to the private worker")
    if envelope.kind == "probe":
        if envelope.payload:
            raise ValueError("Probe tasks contain no business payload")
        return
    payload = envelope.model_dump_json().encode()
    if len(payload) > 28_000:
        raise ValueError("Task payload exceeds the control-message bound")
    # Upstream request accounting cannot prove a previous child has exited. Refuse overlap
    # promptly rather than wait outside the work deadline or double the SQL/memory budget.
    # Lock acquisition on this event loop cannot yield between the unlocked check and acquire.
    if _execution_lock.locked():
        raise RuntimeError("Task worker is busy; retry delivery")
    async with _execution_lock:
        process = await asyncio.create_subprocess_exec(
            *_command(), stdin=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(
                process.communicate(input=payload), timeout=settings.TASKS_WORK_TIMEOUT_SECONDS,
            )
            if process.returncode != 0:
                raise RuntimeError("Isolated task failed; retry delivery")
        finally:
            # Keep the permit until the native child is killed and reaped, even on cancellation.
            with anyio.CancelScope(shield=True):
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                await process.wait()
