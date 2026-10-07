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
        # A cancelled HTTP request or deadline must not leave a throttled child doing work.
        # Kill includes every worker thread in the child, then wait for OS process cleanup.
        with anyio.CancelScope(shield=True):
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()
