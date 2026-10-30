"""Durable ownership is a DB receipt; retries/observers cannot create or charge extra work.

These use real persistence and the existing pipeline with only external provider seams mocked.
PostgreSQL locking/race coverage lives in test_summary_job_transactions.py.
"""
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models import Summary, SummaryJob, User, UserUsage, UsageReservation
from app.services import summary_job_store as store, summary_jobs as jobs
from app.services import subscription_service as usage
from app.services.ai.provider_requests import signal_provider_start
from app.utils.datetimes import ensure_utc, utcnow
from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, seed_company_filing, stream_boundaries, reset_inflight


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    reset_inflight()
    with SessionLocal() as db:
        before = {row.id for row in db.query(SummaryJob.id)}
    yield
    with SessionLocal() as db:
        db.query(SummaryJob).filter(SummaryJob.id.notin_(before)).delete(synchronize_session=False)
        db.commit()


@pytest.fixture
def user_id():
    with SessionLocal() as db:
        user = User(email=f"job-{uuid4().hex}@example.test")
        db.add(user)
        db.commit()
        return user.id


def _new(user_id):
    return store.ensure_job(seed_company_filing(), user_id)


def _lease(user_id):
    view = _new(user_id)
    return view, store.claim_job(view.job_id, view.generation)


def _receipt(view):
    with SessionLocal() as db:
        row = db.get(SummaryJob, view.job_id)
        return row.charge_state, row.reservation_token, row.charge_month


def _usage(user_id):
    with SessionLocal() as db:
        row = db.query(UserUsage).filter_by(user_id=user_id, month=usage.get_current_month()).first()
        return row.summary_count if row else 0


def test_disabled_durable_never_creates_work(monkeypatch, user_id):
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", False)
    with pytest.raises(store.SummaryJobUnavailable, match="disabled"):
        _new(user_id)


def test_ready_and_join_do_not_spend_generation_budget(user_id):
    seen = []
    filing_id = seed_company_filing()
    first = store.ensure_job(filing_id, user_id, admit_new=lambda: seen.append(1))
    joined = store.ensure_job(filing_id, user_id, admit_new=lambda: seen.append(2))
    assert first.created and not joined.created and joined.job_id == first.job_id
    with SessionLocal() as db:
        summary = Summary(filing_id=filing_id, business_overview="A complete grounded company summary.")
        db.add(summary)
        db.commit()
        summary_id = summary.id
    cached = store.ensure_job(filing_id, user_id, admit_new=lambda: seen.append(3))
    assert cached.status == "complete" and cached.summary_id == summary_id
    assert seen == [1]


def test_creation_checks_entitlement_and_account_backlog(user_id, monkeypatch):
    monkeypatch.setattr(settings, "SUMMARY_JOB_MAX_PENDING_PER_ACCOUNT", 1)
    first = _new(user_id)
    with pytest.raises(store.SummaryJobUnavailable, match="pending"):
        _new(user_id)
    assert store.ensure_job(first.filing_id, user_id).job_id == first.job_id
    with SessionLocal() as db:
        db.add(UserUsage(user_id=user_id, month=usage.get_current_month(), summary_count=5))
        db.commit()
    with pytest.raises(store.SummaryJobUnavailable, match="allowance"):
        _new(user_id)


def test_preparation_has_no_default_paid_budget():
    with pytest.raises(store.SummaryJobUnavailable, match="budget"):
        store.ensure_job(seed_company_filing(), None, system=True)


def test_expired_owner_cannot_heartbeat_charge_or_publish(user_id):
    view, old = _lease(user_id)
    assert store.claim_job(view.job_id, view.generation) is None
    with SessionLocal() as db:
        row = db.get(SummaryJob, view.job_id)
        row.lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
    replacement = store.claim_job(view.job_id, view.generation)
    assert replacement.token != old.token
    for action in (store.heartbeat, store.charge_job_usage):
        with pytest.raises(store.SummaryJobLeaseLost):
            action(old)
    with SessionLocal() as db, pytest.raises(store.SummaryJobLeaseLost):
        store.lock_job_for_result(db, old)


def test_crash_receipt_reused_and_refund_is_idempotent(user_id):
    view, lease = _lease(user_id)
    assert store.reserve_job_usage(lease)[0]
    month = store.charge_job_usage(lease)
    assert store.charge_job_usage(lease) == month
    assert _usage(user_id) == 1
    assert _receipt(view) == ("charged", None, month)
    with SessionLocal() as db:
        db.get(SummaryJob, view.job_id).lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
    resumed = store.claim_job(view.job_id, view.generation)
    assert store.reserve_job_usage(resumed)[-1] is None  # existing durable charge, no second reservation
    assert store.charge_job_usage(resumed) == month
    assert _usage(user_id) == 1
    store.refund_job_usage(resumed)
    store.refund_job_usage(resumed)
    assert _usage(user_id) == 0
    assert _receipt(view)[0] == "refunded"


def test_failed_charge_rolls_back_counter_reservation_and_receipt(user_id, monkeypatch):
    view, lease = _lease(user_id)
    store.reserve_job_usage(lease)
    before = _receipt(view)
    original = usage.increment_user_usage

    def after_increment(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("process failure before atomic commit")

    monkeypatch.setattr(usage, "increment_user_usage", after_increment)
    with pytest.raises(RuntimeError):
        store.charge_job_usage(lease)
    assert _usage(user_id) == 0
    assert _receipt(view) == before
    with SessionLocal() as db:
        assert db.query(UsageReservation).filter_by(token=before[1]).count() == 1


def test_transient_failure_preserves_cooldown_and_exhaustion_is_terminal(user_id, monkeypatch):
    view, lease = _lease(user_id)
    before = utcnow()
    retry = store.finish_job(lease, {"type": "error", "code": "sec_throttled", "retryable": True,
                                   "retry_after_seconds": 125})
    assert retry.status == "retry_wait"
    assert retry.retry_at >= before + timedelta(seconds=125)
    assert store.claim_job(view.job_id, view.generation) is None
    with SessionLocal() as db:
        row = db.get(SummaryJob, view.job_id)
        row.next_attempt_at = utcnow() - timedelta(seconds=1)
        row.attempts = settings.SUMMARY_JOB_MAX_ATTEMPTS
        db.commit()
    assert store.claim_job(view.job_id, view.generation) is None
    assert store.read_job(view.job_id, view.generation).status == "failed"
    assert not store.ensure_job(view.filing_id, user_id).created


def test_deleted_account_never_turns_into_unmetered_system_job(user_id):
    view = _new(user_id)
    with SessionLocal() as db:
        db.get(SummaryJob, view.job_id).user_id = None
        db.commit()
    assert store.claim_job(view.job_id, view.generation) is None
    assert store.read_job(view.job_id, view.generation).error_code == "summary_account_unavailable"


@pytest.mark.asyncio
async def test_ambiguous_queue_create_reuses_identity_and_recovery_can_redispatch(user_id, monkeypatch):
    view = _new(user_id)
    enqueue = AsyncMock(side_effect=[TimeoutError("response lost"), None, None])
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    with pytest.raises(TimeoutError):
        await jobs.dispatch_job(view.job_id, view.generation)
    await jobs.dispatch_job(view.job_id, view.generation)
    first, second = enqueue.call_args_list
    assert first == second
    assert first.args == ("summary", {"job_id": view.job_id, "generation": 1})
    assert first.kwargs["schedule_at"] is not None
    with SessionLocal() as db:
        row = db.get(SummaryJob, view.job_id)
        row.last_dispatched_at = utcnow() - timedelta(seconds=settings.SUMMARY_JOB_RECOVERY_SECONDS + 1)
        db.commit()
    assert await jobs.recover_due_jobs() == 1
    assert enqueue.call_args.kwargs["dedupe_key"] != first.kwargs["dedupe_key"]


@pytest.mark.asyncio
async def test_observer_disconnect_does_not_cancel_worker(user_id):
    view, lease = _lease(user_id)
    observer = jobs.observe_job(view)
    event = await anext(observer)
    assert event["type"] == "progress"
    await observer.aclose()
    store.heartbeat(lease)
    assert store.read_job(view.job_id, view.generation).status == "running"


@pytest.mark.asyncio
async def test_worker_runs_existing_pipeline_once_and_commits_summary_receipt_charge(user_id):
    view = _new(user_id)
    async def provider(*args, **kwargs):
        signal_provider_start()
        await asyncio.sleep(0.02)
        return CANONICAL_PAYLOAD
    with stream_boundaries() as summarize:
        summarize.side_effect = provider
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        assert summarize.await_count == 1
    done = store.read_job(view.job_id, view.generation)
    assert done.status == "complete" and done.summary_id
    assert _receipt(view)[0] == "settled" and _usage(user_id) == 1
    with SessionLocal() as db:
        assert db.query(Summary).filter_by(filing_id=view.filing_id).count() == 1
        assert db.query(UsageReservation).filter_by(user_id=user_id).count() == 0
    events = [event async for event in jobs.observe_job(done)]
    assert events == [{"type": "complete", "summary_id": done.summary_id, "percent": 100}]


@pytest.mark.asyncio
async def test_worker_retries_transient_source_error_without_charging(user_id, monkeypatch):
    view = _new(user_id)
    monkeypatch.setattr(jobs, "_generate", AsyncMock(return_value={
        "type": "error", "code": "sec_throttled", "retryable": True, "retry_after_seconds": 90,
    }))
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
    retry = store.read_job(view.job_id, view.generation)
    assert retry.status == "retry_wait" and _usage(user_id) == 0
    assert ensure_utc(enqueue.call_args.kwargs["schedule_at"]) == retry.retry_at


def test_failed_manual_retry_waits_then_reopens_without_forcing_ready_summary(user_id):
    view, lease = _lease(user_id)
    store.finish_job(lease, {"type": "error", "code": "source_error"})
    with pytest.raises(store.SummaryJobUnavailable) as refused:
        store.ensure_job(view.filing_id, user_id, retry_failed=True)
    assert refused.value.status_code == 429 and refused.value.retry_after_seconds > 0
    with SessionLocal() as db:
        db.get(SummaryJob, view.job_id).next_attempt_at = utcnow() - timedelta(seconds=1)
        db.commit()
    reopened = store.ensure_job(view.filing_id, user_id, retry_failed=True)
    assert reopened.created and reopened.generation == view.generation + 1
    with SessionLocal() as db:
        db.add(Summary(filing_id=view.filing_id, business_overview="Completed in the meantime."))
        db.commit()
    cached = store.ensure_job(view.filing_id, user_id, retry_failed=True)
    assert cached.status == "complete" and not cached.created


def test_recovery_does_not_fill_batch_with_acknowledged_future_retries(user_id):
    view, lease = _lease(user_id)
    store.finish_job(lease, {"type": "error", "retryable": True, "retry_after_seconds": 600})
    with SessionLocal() as db:
        row = db.get(SummaryJob, view.job_id)
        row.last_dispatched_at = utcnow() - timedelta(seconds=settings.SUMMARY_JOB_RECOVERY_SECONDS + 1)
        db.commit()
    assert (view.job_id, view.generation) not in store.due_jobs(20)
