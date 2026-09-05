"""Job lifecycle bookkeeping in independent transactions, never in the job's business session.

A killed process leaves a running attempt. Only fully successful, non-dry runs advance last
success. Services may keep their best-effort API behavior: the CLI converts their error counters
into a failed execution after persisting the outcome. No schema DDL belongs here.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterator
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import JobRun
from app.utils.datetimes import iso_z, utcnow

logger = logging.getLogger(__name__)

# Maximum scheduled interval (not average): Notable's overnight gap is 14 hours.
JOB_CADENCES = {
    "pregenerate": timedelta(days=7),
    "filing-scan": timedelta(hours=1),
    "filing-digest": timedelta(days=1),
    "backfill-facts": timedelta(days=7),
    "earnings-calendar-refresh": timedelta(days=1),
    "earnings-day-alerts": timedelta(days=1),
    "notable-filings": timedelta(hours=14),
    "data-quality-report": timedelta(days=7),
}
ERROR_COUNTERS = frozenset({
    "source_errors", "errors", "extract_errors", "alerts_failed", "digests_failed",
    "failed", "commit_failed", "generation_failed", "missing_urls", "unsupported_form",
    "company_not_found",
})


class JobRunFailed(RuntimeError):
    """The service returned, but some requested work failed."""


@dataclass
class JobAttempt:
    counters: dict = field(default_factory=dict)

    def record(self, stats: dict) -> None:
        # Counts only: do not persist IDs, user emails, raw exceptions or provider payloads.
        self.counters.update({k: v for k, v in stats.items() if isinstance(v, (int, float, bool))})


def _finish(run_id: str, status: str, attempt: JobAttempt, error_type: str | None = None) -> None:
    with SessionLocal() as db:
        row = db.get(JobRun, run_id)
        row.finished_at = utcnow()
        row.status = status
        row.counters = attempt.counters
        row.error_type = error_type
        db.commit()


@contextmanager
def track_job(name: str, *, dry_run: bool = False) -> Iterator[JobAttempt]:
    """Persist an attempt before work, then its honest outcome, using independent sessions."""
    run_id = str(uuid4())
    attempt = JobAttempt()
    with SessionLocal() as db:
        db.add(JobRun(id=run_id, job_name=name, started_at=utcnow(), status="running"))
        db.commit()
    try:
        yield attempt
        if any(attempt.counters.get(key, 0) for key in ERROR_COUNTERS):
            raise JobRunFailed(f"{name}: work failed; see persisted counters")
    except BaseException as exc:
        try:
            _finish(run_id, "failed", attempt, type(exc).__name__[:120])
        except Exception:
            logger.exception("Could not finish job heartbeat %s; preserving original failure", name)
        raise
    else:
        _finish(run_id, "dry_run" if dry_run else "succeeded", attempt)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def job_health(db: Session, *, now: datetime | None = None) -> list[dict]:
    """Every expected job is visible, including jobs never created or never observed."""
    now = _aware(now or utcnow())
    successes = dict(db.query(JobRun.job_name, func.max(JobRun.finished_at)).filter(
        JobRun.status == "succeeded",
    ).group_by(JobRun.job_name).all())
    output = []
    for name, cadence in JOB_CADENCES.items():
        latest = db.query(JobRun).filter(JobRun.job_name == name).order_by(
            JobRun.started_at.desc(), JobRun.id.desc(),
        ).first()
        last_success = successes.get(name)
        stale = last_success is None or now - _aware(last_success) > 2 * cadence
        output.append({
            "job": name,
            "last_success": iso_z(_aware(last_success)) if last_success else None,
            "latest_status": latest.status if latest else "never_observed",
            "latest_started_at": iso_z(_aware(latest.started_at)) if latest else None,
            "stale": stale,
            "cadence_hours": cadence.total_seconds() / 3600,
            "counters": latest.counters if latest else None,
        })
    return output
