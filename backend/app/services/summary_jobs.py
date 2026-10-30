"""Durable delivery and observation of the one existing summary pipeline.

The browser observes persisted status; only the authenticated private task worker
owns generation. The existing filing scan (or an explicit internal recovery call)
must invoke recover_due_jobs to repair the database-to-queue handoff. This module
does not claim that an unconfigured independent scheduler exists.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing
import logging

from app.config import settings
from app.services.durable_tasks import SummaryTask, enqueue_task
from app.services.request_work import run_owned_sync
from app.services import summary_job_store as store
from app.utils.datetimes import utcnow

logger = logging.getLogger(__name__)


async def dispatch_job(job_id: str, generation: int, *, recover: bool = False) -> bool:
    """Confirm a scheduled task before the caller can claim a durable handoff."""
    if not settings.SUMMARY_DURABLE_GENERATION_ENABLED:
        raise store.SummaryJobUnavailable("Durable summary generation is disabled")
    intent = await run_owned_sync(store.dispatch_intent, job_id, generation, recover=recover)
    if intent is None:
        return False
    token, next_at = intent
    await enqueue_task(
        "summary", {"job_id": job_id, "generation": generation},
        dedupe_key=f"summary:{job_id}:{generation}:{token}",
        schedule_at=next_at,
    )
    await run_owned_sync(store.mark_dispatched, job_id, generation, token)
    return True


async def recover_due_jobs(limit: int = 20) -> int:
    """Bounded outbox recovery; the scheduler/scan owner determines its actual cadence."""
    if not settings.SUMMARY_DURABLE_GENERATION_ENABLED or not settings.DURABLE_TASKS_ENABLED:
        return 0
    count = 0
    for job_id, generation in await run_owned_sync(store.due_jobs, limit):
        count += int(await dispatch_job(job_id, generation, recover=True))
    return count


async def observe_job(view: store.JobView) -> AsyncIterator[dict]:
    """Existing SSE vocabulary; disconnect closes this observer, never the durable worker."""
    while True:
        if view.status in {"complete", "partial"}:
            yield {"type": view.status, "summary_id": view.summary_id,
                   **({"percent": 100} if view.status == "complete" else {})}
            return
        if view.status == "failed":
            delay = max(0, (view.retry_at - utcnow()).total_seconds()) if view.retry_at else 0
            yield {"type": "error", "message": "This summary could not finish. Try again later.",
                   "code": view.error_code or "summary_generation_failed", "retryable": False,
                   "retry_after_seconds": delay}
            return
        delay = max(0, (view.retry_at - utcnow()).total_seconds()) if view.retry_at else 0
        yield {"type": "progress", "stage": view.stage,
               "message": "Preparation is waiting to retry automatically." if delay else "Preparing this summary…",
               "job_id": view.job_id, "retry_after_seconds": delay}
        await asyncio.sleep(settings.STREAM_HEARTBEAT_INTERVAL)
        refreshed = await run_owned_sync(store.read_job, view.job_id, view.generation)
        if refreshed is None:
            yield {"type": "error", "message": "The summary changed. Reload to view its latest status.",
                   "code": "summary_job_replaced", "retryable": False}
            return
        view = refreshed


async def _heartbeat(lease: store.SummaryJobLease) -> None:
    while True:
        await asyncio.sleep(settings.SUMMARY_JOB_LEASE_SECONDS / 3)
        await run_owned_sync(store.heartbeat, lease)


async def _generate(lease: store.SummaryJobLease) -> dict:
    from app.services.summary_pipeline import stream_filing_summary
    actor, user_id, force, refresh_xbrl = await run_owned_sync(store.worker_inputs, lease)
    terminal = None
    async with aclosing(stream_filing_summary(
        filing_id=lease.filing_id, current_user=actor, user_id=user_id,
        telemetry_distinct_id="durable-summary", telemetry_entry_point=None, telemetry_ctx={},
        emit_funnel_telemetry=False, force_regenerate=force, refresh_xbrl=refresh_xbrl, durable_lease=lease,
    )) as events:
        async for event in events:
            if event.get("type") in {"complete", "partial", "error"}:
                terminal = event
            elif event.get("type") == "progress":
                await run_owned_sync(store.record_job_stage, lease, str(event.get("stage") or "queued"))
    return terminal or {"type": "error", "code": "summary_incomplete", "retryable": True}


async def run_summary_task(payload: dict) -> None:
    task = SummaryTask.model_validate(payload)
    if not settings.SUMMARY_DURABLE_GENERATION_ENABLED:
        raise store.SummaryJobUnavailable("Durable summary generation is disabled")
    lease = await run_owned_sync(store.claim_job, task.job_id, task.generation)
    if lease is None:
        return
    producer = asyncio.create_task(_generate(lease))
    heartbeat = asyncio.create_task(_heartbeat(lease))
    try:
        done, _ = await asyncio.wait({producer, heartbeat}, return_when=asyncio.FIRST_COMPLETED)
        if heartbeat in done:
            # A failed lease extension revokes this worker's permission to continue.
            await heartbeat
        terminal = await producer
    except store.SummaryJobLeaseLost:
        return  # a replacement owns recovery; an obsolete task must not mark its outcome
    except store.SummaryJobUnavailable as exc:
        terminal = {"type": "error", "code": exc.code, "retryable": exc.status_code == 503}
    except Exception as exc:
        logger.warning("Summary worker failed job=%s generation=%s class=%s",
                       task.job_id, task.generation, type(exc).__name__)
        terminal = {"type": "error", "code": "summary_worker_failed", "retryable": True}
    finally:
        for owned in (producer, heartbeat):
            if not owned.done():
                owned.cancel()
        await asyncio.gather(producer, heartbeat, return_exceptions=True)
    try:
        view = await run_owned_sync(store.finish_job, lease, terminal)
    except store.SummaryJobLeaseLost:
        # The fenced Summary commit publishes its terminal receipt atomically. A
        # completed run (or a replacement owner) has already revoked this lease.
        return
    if view.status == "retry_wait":
        await dispatch_job(task.job_id, task.generation)
