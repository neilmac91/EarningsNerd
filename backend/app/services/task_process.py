"""Isolated task entrypoint. stdin carries identifiers, never credentials or document content."""
from __future__ import annotations

import asyncio
import logging
import sys

from app.services.background_task_runner import run_background_task
from app.services.durable_tasks import TaskEnvelope
from app.services.request_work import request_work_scope


async def _execute(envelope: TaskEnvelope) -> None:
    async with request_work_scope():
        await run_background_task(envelope)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    try:
        envelope = TaskEnvelope.model_validate_json(sys.stdin.read(28_001))
        asyncio.run(_execute(envelope))
    except Exception:
        logging.exception("Isolated task failed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
