"""Awaited workers for internal HTTP job triggers, with bounded durable fanout.

Scheduled Cloud Run jobs remain the primary fleet-wide mechanism. HTTP cohorts are frozen
before acceptance, then split into one company or ticker/form per task. A planner retry reuses
the request id and child task names. Forced paid generation is excluded: without a durable
generation-attempt ledger, retrying it can delete a completed summary and spend twice.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator

from app.config import settings
from app.services.durable_tasks import enqueue_task
from app.services.request_work import run_owned_sync

logger = logging.getLogger(__name__)
MAX_DURABLE_COHORT = 50
RequestId = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Ticker = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^\S+$")]


class _TaskBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: RequestId


class _SimpleTask(_TaskBase):
    job: Literal["filing-scan", "filing-digest", "earnings-calendar-refresh", "earnings-day-alerts"]


class _RetentionTask(_TaskBase):
    job: Literal["retention-purge"]
    dry_run: bool = False


class _NotableTask(_TaskBase):
    job: Literal["notable-filings-scan"]
    days: Annotated[int, Field(ge=0, le=14)] | None = None


class _CohortTask(_TaskBase):
    job: Literal["sync-companyfacts", "backfill-filing-history", "backfill-facts"]
    stage: Literal["plan", "run"] = "plan"
    tickers: Annotated[list[Ticker], Field(max_length=MAX_DURABLE_COHORT)]
    force: bool = False

    @model_validator(mode="after")
    def bounded_child(self) -> _CohortTask:
        if self.stage == "run" and len(self.tickers) != 1:
            raise ValueError("A cohort worker must contain exactly one ticker.")
        if self.force and self.job != "sync-companyfacts":
            raise ValueError("Force is supported only for companyfacts refresh.")
        return self


class _PrecomputeTask(_TaskBase):
    job: Literal["precompute"]
    stage: Literal["plan", "run"] = "plan"
    tickers: Annotated[list[Ticker], Field(min_length=1, max_length=MAX_DURABLE_COHORT)]
    forms: Annotated[list[Literal["10-K", "10-Q", "20-F"]], Field(min_length=1, max_length=3)]
    force: Literal[False] = False

    @model_validator(mode="after")
    def bounded_generation(self) -> _PrecomputeTask:
        jobs = len(self.tickers) * len(self.forms)
        if jobs > MAX_DURABLE_COHORT:
            raise ValueError("Durable precompute is capped at 50 ticker/form pairs per request.")
        if self.stage == "run" and jobs != 1:
            raise ValueError("A precompute worker must contain exactly one ticker/form pair.")
        return self


_TASK_PAYLOAD = TypeAdapter(Annotated[
    _SimpleTask | _RetentionTask | _NotableTask | _CohortTask | _PrecomputeTask,
    Field(discriminator="job"),
])


def _resolve_cohort_tickers(
    job: str, tickers: list[str], watchlist_only: bool, limit: int | None,
) -> list[str]:
    """Return scalar identities and close the read session before any queue/network operation."""
    from app.database import SessionLocal
    from app.models import Company, Filing, Watchlist

    if limit is not None and not 1 <= limit <= MAX_DURABLE_COHORT:
        raise ValueError("Durable HTTP cohorts require a limit between 1 and 50.")
    if len(tickers) > MAX_DURABLE_COHORT:
        raise ValueError("Durable HTTP cohorts are capped at 50 tickers; split the request.")
    cap = limit or MAX_DURABLE_COHORT
    if job == "backfill-filing-history":
        cap = min(cap, settings.HISTORY_BACKFILL_MAX_COMPANIES)
    with SessionLocal() as db:
        query = db.query(Company.ticker)
        if tickers:
            query = query.filter(Company.ticker.in_(tickers))
        elif watchlist_only:
            query = query.filter(Company.id.in_(db.query(Watchlist.company_id).distinct()))
        if job == "backfill-facts":
            # Select companies through a subquery rather than DISTINCT ticker plus ORDER BY id,
            # which PostgreSQL rejects because the ordered column is outside the DISTINCT list.
            query = query.filter(Company.id.in_(
                db.query(Filing.company_id).filter(Filing.xbrl_data.isnot(None)).distinct()
            ))
        if job == "backfill-filing-history" and not tickers and not watchlist_only:
            query = query.order_by(Company.history_backfilled_at.is_(None).desc(), Company.id)
        else:
            query = query.order_by(Company.id)
        # An explicitly requested limit is the operator's selected cohort, not hidden truncation.
        rows = query.limit(cap if limit is not None else cap + 1).all()
        if limit is None and len(rows) > cap:
            raise ValueError(
                f"This cohort exceeds the durable HTTP limit of {cap} companies. "
                "Specify an explicit smaller cohort/limit or use the existing Cloud Run job."
            )
        return list(dict.fromkeys(row[0].strip().upper() for row in rows))


async def enqueue_internal_job(job: str, arguments: dict[str, Any] | None = None) -> dict[str, int]:
    """Prepare and durably accept one trigger; failures propagate before HTTP 202 is returned."""
    arguments = arguments or {}
    payload: dict[str, Any] = {"job": job, "request_id": uuid4().hex}
    accepted: dict[str, int] = {}
    if job in {"sync-companyfacts", "backfill-filing-history", "backfill-facts"}:
        tickers = list(dict.fromkeys(arguments.get("tickers", [])))
        selected = await run_owned_sync(
            _resolve_cohort_tickers, job, tickers,
            arguments.get("watchlist_only", False), arguments.get("limit"),
        )
        payload.update(tickers=selected, force=arguments.get("force", False))
        accepted = {"cohort_limit": MAX_DURABLE_COHORT, "selected_tickers": len(selected)}
    elif job == "precompute":
        if arguments.get("force", False):
            raise ValueError(
                "Forced precompute is unavailable with durable HTTP tasks because retries could "
                "repeat paid generation. Use an explicit operator-run precompute job instead."
            )
        payload.update(
            tickers=list(dict.fromkeys(arguments["tickers"])),
            forms=list(dict.fromkeys(arguments["forms"])),
        )
        accepted = {"task_limit": MAX_DURABLE_COHORT}
    else:
        payload.update(arguments)
    task = _TASK_PAYLOAD.validate_python(payload)
    await enqueue_task("internal_job", task.model_dump())
    return accepted


def _check_stats(job: str, stats: Any) -> None:
    """A partial failure must be retried, rather than acknowledged as a completed task."""
    values = stats.as_dict() if hasattr(stats, "as_dict") else stats
    failures = {
        key: value for key, value in values.items()
        if (key in {"failed", "errors", "source_errors", "extract_errors", "error"}
            or key.endswith("_failed"))
        and value
    }
    if failures:
        raise RuntimeError(f"Internal task {job} reported incomplete work: {failures}")


def _run_sync_task(task: _RetentionTask | _CohortTask) -> None:
    from app.database import SessionLocal
    from app.services import facts_service, retention_service

    with SessionLocal() as db:
        if isinstance(task, _RetentionTask):
            stats = retention_service.run_retention_purge(db, dry_run=task.dry_run)
        else:
            stats = facts_service.backfill_facts(db, tickers=task.tickers)
        _check_stats(task.job, stats)
        logger.info("Internal durable %s complete: %s", task.job, stats)


async def run_internal_task(payload: dict[str, Any]) -> None:
    """Validate queued input at the worker boundary and await all work before acknowledgement."""
    task = _TASK_PAYLOAD.validate_python(payload)
    if isinstance(task, (_CohortTask, _PrecomputeTask)) and task.stage == "plan":
        forms = task.forms if isinstance(task, _PrecomputeTask) else [None]
        for ticker in task.tickers:
            for form in forms:
                child = task.model_dump()
                child.update(stage="run", tickers=[ticker])
                if form is not None:
                    child["forms"] = [form]
                await enqueue_task(
                    "internal_job", child,
                    dedupe_key=f"internal:{task.request_id}:{task.job}:{ticker}:{form or ''}",
                    dedupe_seconds=None,
                )
        return
    if isinstance(task, _PrecomputeTask):
        from app.services import precompute_service

        result = await precompute_service.precompute_one(task.tickers[0], task.forms[0], force=False)
        if result["status"] in {"error", "generation_failed", "unknown"}:
            raise RuntimeError(f"Internal precompute did not complete: {result['status']}")
        logger.info("Internal durable precompute complete: %s", result["status"])
        return
    if isinstance(task, _RetentionTask) or task.job == "backfill-facts":
        await run_owned_sync(_run_sync_task, task)
        return

    from app.database import SessionLocal
    from app.services import (
        earnings_alert_service, earnings_calendar_service, facts_service,
        filing_history_service, filing_scan_service, notable_filings_service,
    )

    if task.job == "backfill-filing-history":
        from app.models import Company

        with SessionLocal() as db:
            company_id = db.query(Company.id).filter(Company.ticker == task.tickers[0]).scalar()
        if company_id is not None:
            # This path releases the lookup session before EFTS I/O and stamps only complete
            # window coverage. Explicit internal triggers preserve their historical re-fetch
            # behavior; accession dedupe protects persistence across a repeated delivery.
            stats = await filing_history_service.backfill_company_by_id(
                company_id, session_factory=SessionLocal, require_complete=True, force=True,
            )
            if stats is not None:
                _check_stats(task.job, stats)
                logger.info("Internal durable %s complete: %s", task.job, stats)
        return

    with SessionLocal() as db:
        if task.job == "filing-scan":
            stats = await filing_scan_service.run_filing_scan(db)
        elif task.job == "filing-digest":
            stats = await filing_scan_service.run_daily_digest(db)
        elif task.job == "earnings-calendar-refresh":
            stats = await earnings_calendar_service.run_refresh(db)
        elif task.job == "earnings-day-alerts":
            stats = await earnings_alert_service.send_earnings_day_alerts(db)
        elif isinstance(task, _NotableTask):
            stats = await notable_filings_service.run_scan(db, days=task.days)
        elif task.job == "sync-companyfacts":
            stats = await facts_service.sync_companyfacts_batch(db, tickers=task.tickers, force=task.force)
        else:
            raise RuntimeError(f"Unsupported internal task: {task.job}")
        _check_stats(task.job, stats)
        values = stats.as_dict() if hasattr(stats, "as_dict") else stats
        logger.info("Internal durable %s complete: %s", task.job, values)
