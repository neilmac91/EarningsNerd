"""Short transactions for shared summary ownership, outbox intents and usage receipts.

No transaction spans SEC, model or Cloud Tasks I/O. PostgreSQL row locks serialize
ownership and counters; the final Summary write takes the same job lock and checks
the generation/token, so a worker whose lease expired cannot publish a stale result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from uuid import uuid4
from random import uniform

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal
from app.models import Filing, Summary, SummaryJob, SummaryPreparationBudget, UsageReservation, User
from app.services.entitlements import get_entitlements
from app.services.summary_placeholders import is_summary_ready
from app.services.provenance_service import source_safe_business_overview
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION
from app.services import subscription_service
from app.utils.datetimes import ensure_utc, utcnow


class SummaryJobUnavailable(RuntimeError):
    """Safe typed route refusal; callers must not imply a running job."""

    def __init__(self, message: str, *, code: str = "summary_unavailable", status_code: int = 503,
                 retry_after_seconds: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class SummaryJobLeaseLost(RuntimeError):
    """This worker no longer has authority to write or charge for the job."""


@dataclass(frozen=True)
class SummaryJobLease:
    job_id: str
    filing_id: int
    generation: int
    token: str


@dataclass(frozen=True)
class JobView:
    job_id: str | None
    filing_id: int
    generation: int
    status: str
    stage: str
    summary_id: int | None
    error_code: str | None
    retry_at: datetime | None
    created: bool = False
    last_dispatched_at: datetime | None = None


def _view(row: SummaryJob, *, created: bool = False) -> JobView:
    return JobView(row.id, row.filing_id, row.generation, row.status, row.stage,
                   row.summary_id, row.error_code,
                   ensure_utc(row.next_attempt_at) if row.status in {"retry_wait", "failed"} else None, created,
                   ensure_utc(row.last_dispatched_at) if row.last_dispatched_at else None)


def _lock_timeout(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.set_config("lock_timeout", "3000ms", True)))


def lock_job_for_result(db: Session, lease: SummaryJobLease) -> SummaryJob:
    """Fence within the caller's result transaction; caller owns its commit.

Every version shares the filing's single job row. Holding this lock through the
Summary commit prevents lease reassignment between checking authority and writing.
"""
    _lock_timeout(db)
    row = db.query(SummaryJob).filter(SummaryJob.id == lease.job_id).with_for_update().first()
    if (row is None or row.filing_id != lease.filing_id or row.generation != lease.generation
            or row.lease_token != lease.token or row.status != "running"
            or row.lease_until is None or ensure_utc(row.lease_until) <= utcnow()):
        raise SummaryJobLeaseLost("Summary generation ownership expired")
    return row


def ensure_job(
    filing_id: int, user_id: int | None, *, force: bool = False, system: bool = False, retry_failed: bool = False,
    admit_new: Callable[[], None] | None = None,
) -> JobView:
    """Join or create a server-owned job; validate the actor before creating work.

The router passes its expensive-work budget as admit_new. It is spent only under
the filing lock after ready/join checks. System callers must separately supply a
bounded, explicit prewarm cohort; the default cap of zero disallows them.
"""
    if not settings.SUMMARY_DURABLE_GENERATION_ENABLED or not settings.DURABLE_TASKS_ENABLED:
        raise SummaryJobUnavailable("Durable summary generation is disabled")
    if system and (user_id is not None or settings.SUMMARY_PREWARM_MAX_PER_SCAN <= 0
                   or settings.SUMMARY_PREWARM_MAX_PER_DAY <= 0):
        raise SummaryJobUnavailable("Summary preparation budget is disabled")
    if not system and user_id is None:
        raise SummaryJobUnavailable("A summary generation account is required", code="summary_account_required", status_code=401)
    now = utcnow()
    with SessionLocal() as db:
        _lock_timeout(db)
        filing = db.query(Filing).filter(Filing.id == filing_id).with_for_update().first()
        if filing is None:
            raise SummaryJobUnavailable("Filing not found", code="filing_not_found", status_code=404)
        user = None
        if not system:
            user = db.query(User).options(joinedload(User.subscription)).filter(User.id == user_id).first()
            if user is None or not user.is_active:
                raise SummaryJobUnavailable("The generation account is unavailable", code="summary_account_unavailable", status_code=403)
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        ready = summary is not None and is_summary_ready(
            source_safe_business_overview(summary, filing), (summary.raw_summary if isinstance(summary.raw_summary, dict) else {}).get("writer_error"),
        )
        if ready and not force:
            return JobView(None, filing_id, 0, "complete", "completed", summary.id, None, None)
        if force and ready and not system and not get_entitlements(user).has_unlimited_summaries:
            raise SummaryJobUnavailable("Regenerating a summary is a Pro feature.", code="summary_refresh_requires_pro", status_code=403)
        row = db.query(SummaryJob).filter(SummaryJob.filing_id == filing_id).with_for_update().first()
        if row is not None and row.status in {"queued", "running", "retry_wait"}:
            return _view(row)
        if row is not None and row.status == "failed":
            if not retry_failed:
                return _view(row)
            wait = max(0, int((ensure_utc(row.next_attempt_at) - now).total_seconds()) + 1)
            if wait:
                raise SummaryJobUnavailable("This summary can be retried shortly", code="summary_retry_wait",
                                            status_code=429, retry_after_seconds=wait)
        if user is not None:
            # One account lock serializes creation across DIFFERENT filings/instances. A
            # queued job does not hold a short-lived usage lease while waiting for capacity;
            # instead creation checks entitlement and bounds outstanding work, and the worker
            # rechecks/leases quota immediately before any provider work.
            db.query(User.id).filter(User.id == user.id).with_for_update().first()
            allowed, used, limit = subscription_service.check_usage_limit(user, db)
            if not allowed:
                pro = get_entitlements(user).has_unlimited_summaries
                raise SummaryJobUnavailable("Summary generation allowance is exhausted",
                                            code="pro_fair_use_limit" if pro else "free_allowance_exhausted",
                                            status_code=429 if pro else 403)
            pending = db.query(func.count(SummaryJob.id)).filter(
                SummaryJob.user_id == user.id, SummaryJob.status.in_(["queued", "running", "retry_wait"]),
            ).scalar() or 0
            capacity = settings.SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT
            if limit is not None:
                capacity = min(capacity, max(0, limit - used))
            if pending >= capacity:
                raise SummaryJobUnavailable("Your pending summaries must finish before starting more", code="summary_pending_limit", status_code=429)
        if admit_new is not None:
            admit_new()
        if system:
            _admit_system_budget(db, now)
        if row is None:
            row = SummaryJob(id=uuid4().hex, filing_id=filing_id, generation=1, created_at=now)
            db.add(row)
        else:
            row.generation += 1
        row.prompt_version = SUMMARY_PROMPT_VERSION
        row.status = "queued"
        row.stage = "queued"
        row.user_id = user_id
        row.system_funded = system
        row.force = force or (summary is not None and not ready)
        row.attempts = 0
        row.lease_token = None
        row.lease_until = None
        row.next_attempt_at = now
        row.last_dispatched_at = None
        row.dispatch_token = uuid4().hex
        row.error_code = None
        row.summary_id = None
        row.charge_state = "unreserved"
        row.charge_month = None
        row.reservation_token = None
        row.created_at = now
        row.updated_at = now
        db.commit()
        return _view(row, created=True)


def _admit_system_budget(db: Session, now: datetime) -> None:
    """Serialize global daily admissions inside the job transaction, never refill on failure.

    Budget bounds generation attempts by admissions * SUMMARY_JOB_MAX_ATTEMPTS.
    Provider-internal retries/tokens still require a reviewed per-attempt cost ceiling.
    """
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif db.get_bind().dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise SummaryJobUnavailable("The summary preparation budget requires supported storage")
    day = ensure_utc(now).date().isoformat()
    db.execute(insert(SummaryPreparationBudget).values(day=day, admissions=0).on_conflict_do_nothing(index_elements=["day"]))
    budget = db.query(SummaryPreparationBudget).filter(SummaryPreparationBudget.day == day).with_for_update().one()
    if budget.admissions >= settings.SUMMARY_PREWARM_MAX_PER_DAY:
        raise SummaryJobUnavailable("The daily summary preparation budget is exhausted",
                                    code="summary_prewarm_budget_exhausted")
    budget.admissions += 1


def settle_job_result(row: SummaryJob, summary_id: int, status: str) -> None:
    """Publish the terminal receipt inside the SAME fenced Summary transaction.

    The caller must already hold lock_job_for_result. A worker death immediately
    after commit cannot cause a force refresh to rerun or refund this result.
    """
    if row.charge_state == "charged":
        row.charge_state = "settled"
    row.summary_id = summary_id
    row.status = status if status in {"complete", "partial"} else "failed"
    row.stage = "completed" if row.status == "complete" else "partial" if row.status == "partial" else "error"
    row.error_code = "summary_generation_failed" if row.status == "failed" else None
    if row.status == "failed":
        row.next_attempt_at = utcnow() + timedelta(seconds=settings.SUMMARY_JOB_FAILED_RETRY_SECONDS)
    row.lease_token, row.lease_until, row.updated_at = None, None, utcnow()


def read_filing_job(filing_id: int) -> JobView | None:
    with SessionLocal() as db:
        row = db.query(SummaryJob).filter(SummaryJob.filing_id == filing_id).first()
        return _view(row) if row is not None else None


def read_job(job_id: str, generation: int) -> JobView | None:
    with SessionLocal() as db:
        row = db.get(SummaryJob, job_id)
        return _view(row) if row is not None and row.generation == generation else None


def claim_job(job_id: str, generation: int) -> SummaryJobLease | None:
    now = utcnow()
    with SessionLocal() as db:
        _lock_timeout(db)
        row = db.query(SummaryJob).filter(SummaryJob.id == job_id).with_for_update().first()
        if row is None or row.generation != generation or row.status in {"complete", "partial", "failed"}:
            return None
        if row.status == "running" and row.lease_until and ensure_utc(row.lease_until) > now:
            return None
        if ensure_utc(row.next_attempt_at) > now:
            return None
        if (row.attempts >= settings.SUMMARY_JOB_MAX_ATTEMPTS
                or ensure_utc(row.created_at) + timedelta(seconds=settings.SUMMARY_JOB_MAX_AGE_SECONDS) <= now):
            _refund_locked(db, row)
            row.status, row.stage, row.error_code = "failed", "error", "summary_recovery_exhausted"
            row.next_attempt_at = now + timedelta(seconds=settings.SUMMARY_JOB_FAILED_RETRY_SECONDS)
            row.updated_at = now
            db.commit()
            return None
        if not row.system_funded and (row.user_id is None or db.get(User, row.user_id) is None):
            row.status, row.stage, row.error_code = "failed", "error", "summary_account_unavailable"
            row.next_attempt_at = now + timedelta(seconds=settings.SUMMARY_JOB_FAILED_RETRY_SECONDS)
            db.commit()
            return None
        row.status, row.stage = "running", "initializing"
        row.prompt_version = SUMMARY_PROMPT_VERSION
        row.lease_token = uuid4().hex
        row.lease_until = now + timedelta(seconds=settings.SUMMARY_JOB_LEASE_SECONDS)
        row.attempts += 1
        row.updated_at = now
        db.commit()
        return SummaryJobLease(row.id, row.filing_id, row.generation, row.lease_token)


def heartbeat(lease: SummaryJobLease) -> None:
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        row.lease_until = utcnow() + timedelta(seconds=settings.SUMMARY_JOB_LEASE_SECONDS)
        row.updated_at = utcnow()
        db.commit()


def worker_inputs(lease: SummaryJobLease) -> tuple[object | None, int | None, bool]:
    from app.services.summary_pipeline import snapshot_generation_user
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        if row.system_funded:
            return None, None, row.force
        user = db.query(User).options(joinedload(User.subscription)).filter(User.id == row.user_id).first()
        if user is None or not user.is_active:
            raise SummaryJobUnavailable("The generation account is unavailable", code="summary_account_unavailable", status_code=403)
        return snapshot_generation_user(user, user.id), user.id, row.force


def reserve_job_usage(lease: SummaryJobLease) -> tuple[bool, int, int | None, bool, str | None]:
    """Reserve once, or reuse a durable receipt after a worker crash."""
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        if row.system_funded:
            return True, 0, None, True, None
        user = db.query(User).options(joinedload(User.subscription)).filter(User.id == row.user_id).first()
        if user is None or not user.is_active:
            raise SummaryJobUnavailable("The generation account is unavailable", code="summary_account_unavailable", status_code=403)
        unlimited = get_entitlements(user).has_unlimited_summaries
        if row.charge_state == "charged":
            return True, 0, None, unlimited, None
        reservation = db.query(UsageReservation).filter(UsageReservation.token == row.reservation_token).first()
        if reservation is not None and ensure_utc(reservation.expires_at) > utcnow():
            return True, 0, None, unlimited, reservation.token
        admitted, count, limit, token = subscription_service.reserve_summary_use(user, db, commit=False)
        if admitted:
            row.reservation_token, row.charge_state = token, "reserved"
        db.commit()
        return admitted, count, limit, unlimited, token


def charge_job_usage(lease: SummaryJobLease) -> str | None:
    """Receipt, lease conversion and counter increment commit atomically and at most once."""
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        if row.system_funded:
            return None
        if row.charge_state in {"charged", "settled"}:
            return row.charge_month
        if row.user_id is None:
            raise SummaryJobUnavailable("The generation account is unavailable", code="summary_account_unavailable", status_code=403)
        month = subscription_service.convert_reservation(row.reservation_token, db)
        if month is None:
            raise SummaryJobUnavailable("The summary usage reservation expired")
        subscription_service.increment_user_usage(row.user_id, month, db, commit=False)
        row.reservation_token, row.charge_state, row.charge_month = None, "charged", month
        db.commit()
        return month


def _refund_locked(db: Session, row: SummaryJob) -> None:
    if row.charge_state == "charged" and row.user_id is not None and row.charge_month:
        subscription_service.refund_summary_use(row.user_id, row.charge_month, db, commit=False)
        row.charge_state = "refunded"
    if row.reservation_token:
        subscription_service.convert_reservation(row.reservation_token, db)
        row.reservation_token = None
        if row.charge_state == "reserved":
            row.charge_state = "unreserved"


def refund_job_usage(lease: SummaryJobLease) -> None:
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        _refund_locked(db, row)
        db.commit()


def release_job_reservation(lease: SummaryJobLease) -> None:
    """Release only an unconverted reservation. A crashed charged run keeps its receipt."""
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        if row.reservation_token:
            subscription_service.convert_reservation(row.reservation_token, db)
            row.reservation_token = None
            if row.charge_state == "reserved":
                row.charge_state = "unreserved"
        db.commit()


def record_job_stage(lease: SummaryJobLease, stage: str) -> None:
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        row.stage = stage[:30]
        row.updated_at = utcnow()
        db.commit()


def finish_job(lease: SummaryJobLease, event: dict) -> JobView:
    with SessionLocal() as db:
        row = lock_job_for_result(db, lease)
        now = utcnow()
        kind = event.get("type")
        if kind in {"complete", "partial"}:
            row.summary_id = event.get("summary_id")
            row.status, row.stage = kind, "completed" if kind == "complete" else "partial"
            if row.charge_state == "charged":
                row.charge_state = "settled"
        else:
            _refund_locked(db, row)
            row.error_code = str(event.get("code") or "summary_generation_failed")[:60]
            retryable = event.get("retryable", False) is True
            age_limit = ensure_utc(row.created_at) + timedelta(seconds=settings.SUMMARY_JOB_MAX_AGE_SECONDS)
            delay = max(15 * 2 ** (row.attempts - 1), float(event.get("retry_after_seconds") or 0))
            next_at = now + timedelta(seconds=delay + uniform(0, min(5, delay / 5)))
            if retryable and row.attempts < settings.SUMMARY_JOB_MAX_ATTEMPTS and next_at < age_limit:
                row.status, row.stage, row.next_attempt_at = "retry_wait", "queued", next_at
                row.last_dispatched_at, row.dispatch_token = None, uuid4().hex
            else:
                row.status, row.stage = "failed", "error"
                row.next_attempt_at = now + timedelta(seconds=settings.SUMMARY_JOB_FAILED_RETRY_SECONDS)
        row.lease_token, row.lease_until, row.updated_at = None, None, now
        db.commit()
        return _view(row)


def dispatch_intent(job_id: str, generation: int, *, recover: bool = False) -> tuple[str, datetime] | None:
    """Return stable dispatch identity. Recovery rotates a stale intent, never a live lease."""
    with SessionLocal() as db:
        _lock_timeout(db)
        row = db.query(SummaryJob).filter(SummaryJob.id == job_id).with_for_update().first()
        now = utcnow()
        if row is None or row.generation != generation or row.status in {"complete", "partial", "failed"}:
            return None
        if row.status == "running" and row.lease_until and ensure_utc(row.lease_until) > now:
            return None
        if recover and row.last_dispatched_at is not None:
            if ensure_utc(row.last_dispatched_at) + timedelta(seconds=settings.SUMMARY_JOB_RECOVERY_SECONDS) > now:
                return None
            row.dispatch_token = uuid4().hex
            row.last_dispatched_at = None
            db.commit()
        return row.dispatch_token, ensure_utc(row.next_attempt_at)


def mark_dispatched(job_id: str, generation: int, token: str) -> None:
    with SessionLocal() as db:
        db.query(SummaryJob).filter(
            SummaryJob.id == job_id, SummaryJob.generation == generation, SummaryJob.dispatch_token == token,
        ).update({SummaryJob.last_dispatched_at: utcnow()}, synchronize_session=False)
        db.commit()


def due_jobs(limit: int) -> list[tuple[str, int]]:
    now = utcnow()
    with SessionLocal() as db:
        rows = db.query(SummaryJob.id, SummaryJob.generation).filter(
            or_(
                and_(SummaryJob.status.in_(["queued", "retry_wait"]),
                     or_(SummaryJob.last_dispatched_at.is_(None),
                         and_(SummaryJob.next_attempt_at <= now,
                              SummaryJob.last_dispatched_at <= now - timedelta(seconds=settings.SUMMARY_JOB_RECOVERY_SECONDS)))),
                and_(SummaryJob.status == "running", SummaryJob.lease_until <= now),
            ),
        ).order_by(SummaryJob.created_at).limit(max(1, min(limit, 50))).all()
        return [(row.id, row.generation) for row in rows]
