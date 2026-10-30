"""Durable ownership is a DB receipt; retries/observers cannot create or charge extra work.

These use real persistence and the existing pipeline with only external provider seams mocked.
PostgreSQL locking/race coverage lives in test_summary_job_transactions.py.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.config import settings
from app.database import SessionLocal
from app.models import Summary, SummaryJob, SummaryPreparationBudget, User, UserUsage, UsageReservation
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
        db.query(SummaryPreparationBudget).delete(synchronize_session=False)
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


def test_system_daily_admission_budget_is_not_refilled_by_failure(monkeypatch):
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_SCAN", 2)
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_DAY", 1)
    view = store.ensure_job(seed_company_filing(), None, system=True)
    assert not store.ensure_job(view.filing_id, None, system=True).created
    lease = store.claim_job(view.job_id, view.generation)
    store.finish_job(lease, {"type": "error", "code": "source_unavailable"})
    with pytest.raises(store.SummaryJobUnavailable, match="daily"):
        store.ensure_job(seed_company_filing(), None, system=True)
    with SessionLocal() as db:
        assert db.query(SummaryPreparationBudget).one().admissions == 1


def test_system_daily_budget_and_job_creation_roll_back_together(monkeypatch):
    from sqlalchemy import event
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_SCAN", 2)
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_DAY", 1)
    filing_id = seed_company_filing()
    def reject_insert(mapper, connection, target):
        raise RuntimeError("job insert rejected")
    event.listen(SummaryJob, "before_insert", reject_insert)
    try:
        with pytest.raises(RuntimeError):
            store.ensure_job(filing_id, None, system=True)
    finally:
        event.remove(SummaryJob, "before_insert", reject_insert)
    view = store.ensure_job(filing_id, None, system=True)
    assert view.created
    with SessionLocal() as db:
        assert db.query(SummaryPreparationBudget).one().admissions == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 429, 503])
async def test_real_worker_source_transient_then_success_schedules_and_charges_once(user_id, monkeypatch, status):
    import httpx
    from app.services import summary_pipeline as pipeline
    view = _new(user_id)
    request = httpx.Request("GET", "https://example.test/filing.htm")
    response = httpx.Response(status, headers={"Retry-After": "73"}, request=request)
    source_error = httpx.HTTPStatusError("transient", request=request, response=response)
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    async def provider(*args, **kwargs):
        signal_provider_start()
        return CANONICAL_PAYLOAD
    with stream_boundaries() as summarize, monkeypatch.context() as local_patch:
        summarize.side_effect = provider
        local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(side_effect=source_error))
        before = utcnow()
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        retry = store.read_job(view.job_id, view.generation)
        assert retry.status == "retry_wait" and retry.retry_at >= before + timedelta(seconds=73)
        assert enqueue.call_args.kwargs["schedule_at"] == retry.retry_at
        assert _usage(user_id) == 0 and summarize.await_count == 0
        with SessionLocal() as db:
            db.get(SummaryJob, view.job_id).next_attempt_at = utcnow() - timedelta(seconds=1)
            db.commit()
        local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value="FILING TEXT " * 100))
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        assert store.read_job(view.job_id, view.generation).status == "complete"
        assert _usage(user_id) == 1 and summarize.await_count == 1


@pytest.mark.asyncio
async def test_source403_is_terminal_and_long429_honors_cooldown_after_horizon(user_id, monkeypatch):
    import httpx
    from app.services import summary_pipeline as pipeline
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    for status, delay in [(403, 73), (429, 3700)]:
        view = _new(user_id)
        request = httpx.Request("GET", "https://example.test/filing.htm")
        response = httpx.Response(status, headers={"Retry-After": str(delay)}, request=request)
        error = httpx.HTTPStatusError("source failure", request=request, response=response)
        with stream_boundaries() as provider, monkeypatch.context() as local_patch:
            local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(side_effect=error))
            before = utcnow()
            await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
            failed = store.read_job(view.job_id, view.generation)
            assert failed.status == "failed" and failed.retry_at >= before + timedelta(seconds=delay)
            provider.assert_not_awaited()
        with pytest.raises(store.SummaryJobUnavailable) as blocked:
            store.ensure_job(view.filing_id, user_id, retry_failed=True)
        assert blocked.value.retry_after_seconds >= delay - 1
        if status == 429:
            with monkeypatch.context() as clock_patch:
                clock_patch.setattr(store, "utcnow", lambda: failed.retry_at + timedelta(seconds=1))
                reopened = store.ensure_job(view.filing_id, user_id, retry_failed=True)
                assert reopened.created and reopened.generation == view.generation + 1
    enqueue.assert_not_awaited()
    assert _usage(user_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["999999999999", "9" * 5000, "Fri, 31 Dec 9999 23:59:59 GMT"],
                         ids=["finite-huge", "beyond-integer-limit", "last-calendar-date"])
async def test_unrepresentable_source_cooldown_persists_terminal_hold(user_id, monkeypatch, header):
    import json
    import httpx
    from app.services import summary_pipeline as pipeline
    from app.services.summary_job_progress import durable_progress_answer
    view = _new(user_id)
    request = httpx.Request("GET", "https://example.test/filing.htm")
    response = httpx.Response(429, headers={"Retry-After": header}, request=request)
    error = httpx.HTTPStatusError("source unavailable", request=request, response=response)
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    with stream_boundaries() as provider, monkeypatch.context() as local_patch:
        local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(side_effect=error))
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        provider.assert_not_awaited()
    failed = store.read_job(view.job_id, view.generation)
    assert failed.status == "failed" and failed.error_code == "sec_rate_limited"
    assert failed.retry_at >= datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    with SessionLocal() as db:
        row = db.get(SummaryJob, view.job_id)
        assert row.lease_token is None and row.reservation_token is None
        progress = durable_progress_answer(db, view.filing_id)
    observed = [event async for event in jobs.observe_job(failed)]
    for wire in [progress, observed[-1]]:
        json.dumps(wire, allow_nan=False)
        assert 10**11 < wire["retry_after_seconds"] < 2**53 / 1000
    assert observed[-1]["retryable"] is False
    with pytest.raises(store.SummaryJobUnavailable) as blocked:
        store.ensure_job(view.filing_id, user_id, retry_failed=True)
    assert blocked.value.retry_after_seconds > 10**11
    assert store.claim_job(view.job_id, view.generation) is None
    assert await jobs.recover_due_jobs() == 0
    assert _usage(user_id) == 0
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_enabled_pipeline_rejects_legacy_or_stale_ownership_before_sec(user_id, monkeypatch):
    from app.services import summary_pipeline as pipeline
    view, lease = _lease(user_id)
    with SessionLocal() as db:
        db.get(SummaryJob, view.job_id).lease_until = utcnow() - timedelta(seconds=1)
        db.commit()
    with stream_boundaries() as provider:
        source = pipeline.sec_edgar_service.get_filing_document
        for supplied in (None, lease):
            events = [item async for item in pipeline.stream_filing_summary(
                filing_id=view.filing_id, current_user=None, user_id=None,
                telemetry_distinct_id="internal", telemetry_entry_point=None, telemetry_ctx={},
                emit_funnel_telemetry=False, durable_lease=supplied,
            )]
            assert events[-1]["code"] == "generation_paused"
        source.assert_not_awaited()
        provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_ready_refresh_preserves_fresh_xbrl_but_repair_does_not(user_id, monkeypatch):
    from app.services import summary_pipeline as pipeline
    with SessionLocal() as db:
        db.get(User, user_id).is_pro = True
        db.commit()
    for ready in (False, True):
        filing_id = seed_company_filing()
        with SessionLocal() as db:
            db.add(Summary(filing_id=filing_id, business_overview="Ready full summary." if ready else ""))
            db.commit()
        view = store.ensure_job(filing_id, user_id, force=ready)
        with stream_boundaries():
            xbrl = pipeline.xbrl_service.get_xbrl_data
            await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
            assert xbrl.call_args.kwargs.get("refresh", False) is ready
        assert store.read_job(view.job_id, view.generation).status == "complete"


@pytest.mark.asyncio
async def test_durable_pipeline_deadline_refunds_and_schedules_bounded_retry(user_id, monkeypatch):
    from app.services import summary_pipeline as pipeline
    view = _new(user_id)
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    monkeypatch.setattr(pipeline, "PIPELINE_TIMEOUT_SECONDS", 0.5)
    async def blocked_provider(*args, **kwargs):
        signal_provider_start()
        await asyncio.Event().wait()
    with stream_boundaries() as summarize:
        summarize.side_effect = blocked_provider
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        summarize.assert_awaited_once()
    assert store.read_job(view.job_id, view.generation).status == "retry_wait"
    assert _usage(user_id) == 0
    enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_deactivated_account_is_terminal_before_provider(user_id):
    view = _new(user_id)
    with SessionLocal() as db:
        db.get(User, user_id).is_active = False
        db.commit()
    with stream_boundaries() as summarize:
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        summarize.assert_not_awaited()
    assert store.read_job(view.job_id, view.generation).status == "failed"
    assert _usage(user_id) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("remaining", [None, 90.4])
@pytest.mark.parametrize("wrapped", [False, True])
async def test_open_breaker_is_retryable_with_typed_remaining_cooldown(user_id, monkeypatch, remaining, wrapped):
    from app.services import summary_pipeline as pipeline
    view = _new(user_id)
    monkeypatch.setattr(pipeline.edgar_circuit_breaker.config, "recovery_timeout", 43)
    error = pipeline.CircuitOpenError("sec_edgar", time_until_recovery=remaining)
    if wrapped:
        error = pipeline.EdgarError("document unavailable", cause=error)
    enqueue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", enqueue)
    before = utcnow()
    with stream_boundaries() as provider, monkeypatch.context() as local_patch:
        local_patch.setattr(pipeline.sec_edgar_service, "get_filing_document", AsyncMock(side_effect=error))
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        provider.assert_not_awaited()
    retry = store.read_job(view.job_id, view.generation)
    assert retry.status == "retry_wait" and retry.error_code == "filing_source_unavailable"
    assert retry.retry_at >= before + timedelta(seconds=43 if remaining is None else 91)
    assert _usage(user_id) == 0
    enqueue.assert_awaited_once()


def test_admission_pause_serves_reads_and_joins_but_blocks_every_new_job(user_id, monkeypatch):
    queued = _new(user_id)
    failed, lease = _lease(user_id)
    store.finish_job(lease, {"type": "error"})
    ready_id, fresh_id = seed_company_filing(), seed_company_filing()
    with SessionLocal() as db:
        db.get(User, user_id).is_pro = True
        db.get(SummaryJob, failed.job_id).next_attempt_at = utcnow() - timedelta(seconds=1)
        db.add(Summary(filing_id=ready_id, business_overview="Existing grounded summary."))
        db.commit()
    admitted = []
    monkeypatch.setattr(settings, "SUMMARY_NEW_JOBS_PAUSED", True)
    assert store.ensure_job(queued.filing_id, user_id).job_id == queued.job_id
    assert store.ensure_job(ready_id, user_id).status == "complete"
    assert store.ensure_job(failed.filing_id, user_id).status == "failed"
    for filing_id, kwargs in [(fresh_id, {}), (ready_id, {"force": True}),
                              (failed.filing_id, {"retry_failed": True})]:
        with pytest.raises(store.SummaryJobUnavailable, match="paused") as refused:
            store.ensure_job(filing_id, user_id, admit_new=lambda: admitted.append(1), **kwargs)
        assert refused.value.status_code == 503
    assert admitted == []
    assert store.read_filing_job(fresh_id) is None and store.read_filing_job(ready_id) is None
    assert store.read_filing_job(failed.filing_id).generation == failed.generation
    assert _usage(user_id) == 0


@pytest.mark.asyncio
async def test_existing_durable_worker_finishes_and_charges_once_while_new_jobs_paused(user_id, monkeypatch):
    view = _new(user_id)
    monkeypatch.setattr(settings, "SUMMARY_NEW_JOBS_PAUSED", True)
    with stream_boundaries() as provider:
        await jobs.run_summary_task({"job_id": view.job_id, "generation": view.generation})
        provider.assert_awaited_once()
    assert store.read_job(view.job_id, view.generation).status == "complete"
    assert _usage(user_id) == 1 and _receipt(view)[0] == "settled"


@pytest.mark.asyncio
async def test_paused_legacy_pipeline_serves_cached_and_active_results_without_new_source_work(monkeypatch):
    from app.services import summary_pipeline as pipeline
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", False)
    monkeypatch.setattr(settings, "SUMMARY_NEW_JOBS_PAUSED", True)
    ready_id, fresh_id, active_id = seed_company_filing(), seed_company_filing(), seed_company_filing()
    with SessionLocal() as db:
        db.add(Summary(filing_id=ready_id, business_overview="Existing grounded summary."))
        db.commit()
    calls = []
    def stream(filing_id):
        return pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None,
            telemetry_distinct_id="offline", telemetry_entry_point=None, telemetry_ctx={},
            emit_funnel_telemetry=False, admit_generation=lambda: calls.append(1),
        )
    leader = pipeline._claim_inflight(active_id)
    try:
        with stream_boundaries() as provider:
            cached = [event async for event in stream(ready_id)]
            assert cached[-1]["type"] == "complete"
            refused = [event async for event in stream(fresh_id)]
            assert refused[-1]["code"] == "generation_paused"
            joined = []
            async for event in stream(active_id):
                joined.append(event)
                if event.get("stage") == "queued":
                    with SessionLocal() as db:
                        db.add(Summary(filing_id=active_id, business_overview="The existing producer finished."))
                        db.commit()
                    pipeline._release_inflight(active_id, leader)
            assert joined[-1]["type"] == "complete"
            provider.assert_not_awaited()
            pipeline.sec_edgar_service.get_filing_document.assert_not_awaited()
        assert calls == []
    finally:
        pipeline._release_inflight(active_id, leader)
