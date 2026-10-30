"""Bounded preparation for newly notified filings and repair of queue handoffs.

Discovery email delivery does not depend on preparation succeeding. The job store
owns the shared daily budget and deduplicates work across scan runs and replicas.
Both preparation caps default to zero; this module never invokes the model itself.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

from app.config import settings
from app.services.request_work import run_owned_sync

logger = logging.getLogger(__name__)


def preparation_cap() -> int:
    if not settings.SUMMARY_DURABLE_GENERATION_ENABLED or not settings.DURABLE_TASKS_ENABLED:
        return 0
    if settings.SUMMARY_PREWARM_MAX_PER_DAY <= 0:
        return 0
    return settings.SUMMARY_PREWARM_MAX_PER_SCAN


async def recover_summary_handoffs() -> int:
    """The existing scan provides a real, bounded recovery invocation."""
    if not settings.SUMMARY_DURABLE_GENERATION_ENABLED or not settings.DURABLE_TASKS_ENABLED:
        return 0
    from app.services.summary_jobs import recover_due_jobs

    try:
        return await recover_due_jobs(limit=20)
    except Exception as exc:
        # A queue outage must not suppress filing discovery mail. No upstream text,
        # account identifiers or credentials enter this operational classification.
        logger.warning("Summary handoff recovery unavailable class=%s", type(exc).__name__)
        return 0


async def prepare_notified_filings(filing_ids: Iterable[int]) -> int:
    """Attempt at most the configured number of distinct candidate handoffs.

The caller supplies filings with a newly committed eligible realtime notification.
The daily store budget counts new jobs even if queue delivery subsequently fails;
the persisted outbox is recovered on later scans. Failures never expand this cohort.
"""
    cap = preparation_cap()
    if cap <= 0:
        return 0
    from app.services.summary_job_store import ensure_job
    from app.services.summary_jobs import dispatch_job

    seen: set[int] = set()
    accepted = 0
    for filing_id in filing_ids:
        if filing_id in seen:
            continue
        if len(seen) >= cap:
            break
        seen.add(filing_id)
        try:
            view = await run_owned_sync(ensure_job, filing_id, None, system=True)
            if view.job_id is not None:
                accepted += int(await dispatch_job(view.job_id, view.generation))
        except Exception as exc:
            logger.warning("Summary preparation unavailable filing=%s class=%s", filing_id, type(exc).__name__)
    return accepted
