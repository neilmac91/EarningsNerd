"""Recovery contenders and cancellations cannot outlive or steal one pass's ownership."""
import asyncio
from threading import Event
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.services import summary_jobs as jobs, summary_recovery as recovery


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)


@pytest.mark.asyncio
async def test_recovery_contender_does_not_read_or_dispatch(monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    reads = []
    monkeypatch.setattr(jobs.store, "due_jobs", lambda limit: reads.append(limit) or [("one", 1)])

    async def dispatch(*args, **kwargs):
        if entered.is_set():
            return True  # A broken contender must fail promptly, not deadlock the test.
        entered.set()
        await release.wait()
        return True

    monkeypatch.setattr(jobs, "dispatch_job", dispatch)
    first = asyncio.create_task(jobs.recover_due_jobs())
    try:
        await asyncio.wait_for(entered.wait(), 10)
        assert await jobs.recover_due_jobs() == 0
        assert reads == [20]
    finally:
        release.set()
        assert await first == 1
    assert not recovery._slot.locked()


@pytest.mark.asyncio
async def test_one_deadline_covers_entire_batch_and_preserves_pending_work(monkeypatch):
    deadlines = []
    configured = []
    entered = asyncio.Event()
    calls = []
    original_timeout = asyncio.timeout

    def timeout(seconds):
        configured.append(seconds)
        scope = original_timeout(seconds)
        deadlines.append(scope)
        return scope

    monkeypatch.setattr(recovery.asyncio, "timeout", timeout)
    monkeypatch.setattr(jobs.store, "due_jobs", lambda limit: [("first", 1), ("second", 1), ("third", 1)])

    async def dispatch(job_id, *args, **kwargs):
        calls.append(job_id)
        if job_id == "second":
            entered.set()
            await asyncio.Future()
        return True

    monkeypatch.setattr(jobs, "dispatch_job", dispatch)
    task = asyncio.create_task(jobs.recover_due_jobs())
    try:
        await asyncio.wait_for(entered.wait(), 10)
        from main import get_timeout_for_path
        assert configured == [recovery.RECOVERY_BUDGET_SECONDS]
        assert recovery.RECOVERY_BUDGET_SECONDS < get_timeout_for_path("/internal/jobs/summary-recovery")
        assert len(deadlines) == 1
        deadlines[0].reschedule(asyncio.get_running_loop().time() - 1)
        with pytest.raises(recovery.SummaryRecoveryUnavailable, match="deadline"):
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert deadlines[0].expired()
    assert calls == ["first", "second"]
    assert not recovery._slot.locked()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["acquire", "selection", "acknowledgement"])
async def test_repeated_cancellation_drains_actual_sql_before_unlock(monkeypatch, phase):
    started, release, finished = Event(), Event(), Event()
    draining = asyncio.Event()
    closed = []
    original_drain = recovery.RequestWork.drain
    original_release = recovery._RecoveryOwner.release

    def blocked(value):
        started.set()
        try:
            assert release.wait(10), "test did not release its SQL worker"
            return value
        finally:
            finished.set()

    async def drain(self):
        draining.set()
        await original_drain(self)

    def close(self):
        closed.append(finished.is_set())
        original_release(self)

    monkeypatch.setattr(recovery.RequestWork, "drain", drain)
    monkeypatch.setattr(recovery._RecoveryOwner, "release", close)
    monkeypatch.setattr(jobs.store, "due_jobs", lambda limit: [("one", 1)])
    monkeypatch.setattr(jobs.store, "dispatch_intent", lambda *a, **k: ("stable", None))
    monkeypatch.setattr(jobs, "enqueue_task", AsyncMock(return_value="task"))
    monkeypatch.setattr(jobs.store, "mark_dispatched", lambda *a: None)
    if phase == "acquire":
        monkeypatch.setattr(recovery._RecoveryOwner, "acquire", lambda self: blocked(True))
    elif phase == "selection":
        monkeypatch.setattr(jobs.store, "due_jobs", lambda limit: blocked([("one", 1)]))
    else:
        monkeypatch.setattr(jobs.store, "mark_dispatched", lambda *a: blocked(None))
    task = asyncio.create_task(jobs.recover_due_jobs())
    try:
        assert await asyncio.to_thread(started.wait, 10)
        task.cancel()
        await asyncio.wait_for(draining.wait(), 10)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert await jobs.recover_due_jobs() == 0
        assert closed == []
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert closed == [True]
    assert not recovery._slot.locked()


@pytest.mark.asyncio
async def test_lost_guard_is_checked_after_intent_before_network(monkeypatch):
    monkeypatch.setattr(jobs.store, "due_jobs", lambda limit: [("one", 1)])
    monkeypatch.setattr(jobs.store, "dispatch_intent", lambda *a, **k: ("stable", None))
    queue = AsyncMock()
    monkeypatch.setattr(jobs, "enqueue_task", queue)

    def lost(self):
        raise recovery.SummaryRecoveryUnavailable("Summary recovery ownership was lost")

    monkeypatch.setattr(recovery._RecoveryOwner, "check", lost)
    with pytest.raises(recovery.SummaryRecoveryUnavailable, match="ownership"):
        await jobs.recover_due_jobs()
    queue.assert_not_awaited()
    assert not recovery._slot.locked()


@pytest.mark.asyncio
async def test_storage_errors_are_closed_and_release_the_local_slot(monkeypatch):
    def fail(self):
        raise OperationalError("private-driver-address", {}, RuntimeError("private-driver-detail"))

    monkeypatch.setattr(recovery._RecoveryOwner, "acquire", fail)
    with pytest.raises(recovery.SummaryRecoveryUnavailable, match="storage") as raised:
        await jobs.recover_due_jobs()
    assert "private-driver" not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__
    assert not recovery._slot.locked()


def test_sql_budget_does_not_change_ordinary_dispatch():
    class NoDatabaseAccess:
        def get_bind(self):
            pytest.fail("ordinary dispatch must not open a recovery SQL budget")

    recovery.apply_sql_budget(NoDatabaseAccess())
