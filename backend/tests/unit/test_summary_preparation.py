"""Bounded alert preparation never suppresses discovery mail during queue failure."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.config import settings
from app.services import summary_preparation as preparation


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_SCAN", 2)
    monkeypatch.setattr(settings, "SUMMARY_PREWARM_MAX_PER_DAY", 5)


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", ["SUMMARY_DURABLE_GENERATION_ENABLED", "DURABLE_TASKS_ENABLED",
                                    "SUMMARY_PREWARM_MAX_PER_SCAN", "SUMMARY_PREWARM_MAX_PER_DAY"])
async def test_preparation_has_no_admission_when_any_required_gate_is_disabled(enabled, monkeypatch, disabled):
    monkeypatch.setattr(settings, disabled, False if disabled.endswith("ENABLED") else 0)
    run = AsyncMock(side_effect=AssertionError("disabled preparation reached admission"))
    monkeypatch.setattr(preparation, "run_owned_sync", run)
    assert await preparation.prepare_notified_filings([1, 2]) == 0
    run.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_handoff_keeps_cohort_bounded_and_does_not_raise_into_alert_delivery(enabled, monkeypatch):
    from app.services import summary_job_store, summary_jobs

    created = []

    def ensure(filing_id, user_id, *, system):
        assert user_id is None and system is True
        created.append(filing_id)
        return SimpleNamespace(job_id=f"job-{filing_id}", generation=1)

    async def owned(function, *args, **kwargs):
        return function(*args, **kwargs)

    dispatch = AsyncMock(side_effect=[RuntimeError("synthetic upstream failure"), True])
    monkeypatch.setattr(preparation, "run_owned_sync", owned)
    monkeypatch.setattr(summary_job_store, "ensure_job", ensure)
    monkeypatch.setattr(summary_jobs, "dispatch_job", dispatch)
    assert await preparation.prepare_notified_filings([1, 1, 2, 3, 4]) == 1
    assert created == [1, 2]
    assert dispatch.await_count == 2


@pytest.mark.asyncio
async def test_completed_result_never_dispatches_a_paid_job(enabled, monkeypatch):
    from app.services import summary_job_store, summary_jobs

    monkeypatch.setattr(preparation, "run_owned_sync", AsyncMock(return_value=SimpleNamespace(job_id=None)))
    monkeypatch.setattr(summary_job_store, "ensure_job", Mock())
    dispatch = AsyncMock()
    monkeypatch.setattr(summary_jobs, "dispatch_job", dispatch)
    assert await preparation.prepare_notified_filings([1]) == 0
    dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_scan_recovery_is_bounded_and_queue_failure_does_not_abort_discovery(enabled, monkeypatch):
    from app.services import summary_jobs

    recover = AsyncMock(side_effect=RuntimeError("synthetic queue failure"))
    monkeypatch.setattr(summary_jobs, "recover_due_jobs", recover)
    assert await preparation.recover_summary_handoffs() == 0
    recover.assert_awaited_once_with(limit=20)


@pytest.mark.asyncio
async def test_scan_recovers_handoffs_even_when_no_new_company_is_due(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import Base
    from app.services.filing_scan_service import run_filing_scan

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    recover = AsyncMock(return_value=1)
    prepare = AsyncMock(return_value=0)
    monkeypatch.setattr(preparation, "recover_summary_handoffs", recover)
    monkeypatch.setattr(preparation, "preparation_cap", lambda: 0)
    monkeypatch.setattr(preparation, "prepare_notified_filings", prepare)
    try:
        with Session(engine) as db:
            stats = await run_filing_scan(db, fetch_filings=AsyncMock())
        assert stats["companies_scanned"] == 0
        recover.assert_awaited_once_with()
        prepare.assert_awaited_once_with([])
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_internal_recovery_requires_auth_and_confirms_dispatch_before_success(enabled, monkeypatch):
    from fastapi import FastAPI
    import httpx
    from app.routers import internal
    from app.services import summary_jobs
    from app.services.durable_tasks import TaskUnavailable

    monkeypatch.setattr(settings, "INTERNAL_JOB_TOKEN", "synthetic-recovery-token")
    app = FastAPI()
    app.include_router(internal.router, prefix="/internal")
    recover = AsyncMock(return_value=3)
    monkeypatch.setattr(summary_jobs, "recover_due_jobs", recover)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        path = "/internal/jobs/summary-recovery"
        assert (await client.post(path)).status_code == 401
        recover.assert_not_awaited()
        headers = {"X-Internal-Token": "synthetic-recovery-token"}
        response = await client.post(path, headers=headers)
        assert response.status_code == 200 and response.json() == {"status": "completed", "dispatched": 3}
        recover.assert_awaited_once_with(limit=20)
        recover.side_effect = TaskUnavailable("synthetic queue outage")
        assert (await client.post(path, headers=headers)).status_code == 503
        monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", False)
        assert (await client.post(path, headers=headers)).status_code == 409
