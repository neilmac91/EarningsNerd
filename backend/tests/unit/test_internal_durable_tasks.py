"""Internal triggers acknowledge durable acceptance and workers expose incomplete work."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from pydantic import ValidationError

from app.config import settings
from app.routers import internal
from app.services.durable_tasks import TaskUnavailable
from app.services import internal_task_runner as runner

REQUEST_ID = "a" * 32


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,job,arguments", [
    (internal.trigger_filing_scan, "filing-scan", {}),
    (internal.trigger_filing_digest, "filing-digest", {}),
    (internal.trigger_retention_purge, "retention-purge", {"dry_run": True}),
    (internal.trigger_earnings_refresh, "earnings-calendar-refresh", {}),
    (internal.trigger_earnings_alerts, "earnings-day-alerts", {}),
    (internal.trigger_backfill_facts, "backfill-facts", {"limit": 10}),
    (internal.trigger_notable_filings_scan, "notable-filings-scan", {
        "req": internal.NotableFilingsScanRequest(days=7),
    }),
])
async def test_enabled_triggers_queue_instead_of_detaching(monkeypatch, endpoint, job, arguments):
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    accepted = AsyncMock(return_value={})
    monkeypatch.setattr(internal, "enqueue_internal_job", accepted)
    background = BackgroundTasks()
    result = await endpoint(background=background, **arguments)
    assert result["status"] == "accepted"
    assert accepted.await_args.args[0] == job
    assert background.tasks == []


@pytest.mark.asyncio
async def test_queue_failure_cannot_return_accepted_precompute(monkeypatch):
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    monkeypatch.setattr(internal, "enqueue_internal_job", AsyncMock(side_effect=TaskUnavailable("unavailable")))
    response = Response()
    background = BackgroundTasks()
    with pytest.raises(HTTPException) as error:
        await internal.trigger_precompute(
            internal.PrecomputeRequest(tickers=["AAPL"]), background, response,
        )
    assert error.value.status_code == 503
    assert response.status_code != 202
    assert background.tasks == []


@pytest.mark.asyncio
async def test_precompute_preview_keeps_synchronous_no_paid_generation_semantics(monkeypatch):
    from app.services import precompute_service

    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    accepted = AsyncMock()
    monkeypatch.setattr(internal, "enqueue_internal_job", accepted)
    preview = AsyncMock(return_value={"stats": {}, "results": []})
    monkeypatch.setattr(precompute_service, "precompute", preview)
    result = await internal.trigger_precompute(
        internal.PrecomputeRequest(tickers=["aapl"], dry_run=True, force=True),
        BackgroundTasks(), Response(),
    )
    assert result["dry_run"] is True
    preview.assert_awaited_once_with(["AAPL"], forms=["10-K"], force=False, dry_run=True)
    accepted.assert_not_awaited()


@pytest.mark.asyncio
async def test_selected_cohort_is_frozen_before_queue_acceptance(monkeypatch):
    resolve = Mock(return_value=["AAPL", "MSFT"])
    monkeypatch.setattr(runner, "_resolve_cohort_tickers", resolve)
    accepted = AsyncMock()
    monkeypatch.setattr(runner, "enqueue_task", accepted)
    result = await runner.enqueue_internal_job("sync-companyfacts", {"watchlist_only": True})
    resolve.assert_called_once_with("sync-companyfacts", [], True, None)
    assert result == {"cohort_limit": 50, "selected_tickers": 2}
    payload = accepted.await_args.args[1]
    assert payload["tickers"] == ["AAPL", "MSFT"]
    assert payload["stage"] == "plan"
    assert "watchlist_only" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,body,job", [
    (internal.trigger_sync_companyfacts, internal.SyncCompanyfactsRequest(tickers=["aapl"]), "sync-companyfacts"),
    (internal.trigger_backfill_filing_history, internal.BackfillFilingHistoryRequest(tickers=["aapl"]),
     "backfill-filing-history"),
])
async def test_cohort_trigger_reports_selected_bound(monkeypatch, endpoint, body, job):
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    enqueue = AsyncMock(return_value={"cohort_limit": 50, "selected_tickers": 1})
    monkeypatch.setattr(internal, "enqueue_internal_job", enqueue)
    background = BackgroundTasks()
    result = await endpoint(body, background)
    assert result["cohort_limit"] == 50
    assert result["selected_tickers"] == 1
    assert enqueue.await_args.args[0] == job
    assert enqueue.await_args.args[1]["tickers"] == ["AAPL"]
    assert background.tasks == []


@pytest.mark.asyncio
async def test_planner_retries_reuse_bounded_child_names(monkeypatch):
    payload = {
        "job": "precompute", "request_id": REQUEST_ID,
        "tickers": ["AAPL", "MSFT"], "forms": ["10-K", "10-Q"],
    }
    enqueue = AsyncMock(side_effect=[None, RuntimeError("queue unavailable")])
    monkeypatch.setattr(runner, "enqueue_task", enqueue)
    with pytest.raises(RuntimeError, match="queue unavailable"):
        await runner.run_internal_task(payload)
    first_name = enqueue.await_args_list[0].kwargs["dedupe_key"]
    enqueue.reset_mock(side_effect=True)
    await runner.run_internal_task(payload)
    assert enqueue.await_count == 4
    assert enqueue.await_args_list[0].kwargs["dedupe_key"] == first_name
    for call in enqueue.await_args_list:
        child = call.args[1]
        assert child["stage"] == "run"
        assert len(child["tickers"]) == len(child["forms"]) == 1
        assert call.kwargs["dedupe_seconds"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [
    {"tickers": ["AAPL"], "forms": ["10-K"], "force": True},
    {"tickers": [f"CO{i}" for i in range(26)], "forms": ["10-K", "10-Q"]},
])
async def test_unsafe_generation_request_is_rejected_before_enqueue(monkeypatch, arguments):
    enqueue = AsyncMock()
    monkeypatch.setattr(runner, "enqueue_task", enqueue)
    with pytest.raises(ValueError):
        await runner.enqueue_internal_job("precompute", arguments)
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"job": "filing-scan", "request_id": REQUEST_ID, "dry_run": True},
    {"job": "notable-filings-scan", "request_id": REQUEST_ID, "days": 15},
    {"job": "precompute", "request_id": REQUEST_ID, "tickers": ["AAPL"],
     "forms": ["10-K"], "force": True},
    {"job": "sync-companyfacts", "request_id": REQUEST_ID, "stage": "run",
     "tickers": ["AAPL", "MSFT"]},
])
async def test_worker_rejects_unsupported_payload_before_work(payload):
    with pytest.raises(ValidationError):
        await runner.run_internal_task(payload)


class _Session:
    closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


def test_implicit_large_cohort_is_rejected_without_silent_truncation(monkeypatch):
    import app.database

    query = Mock()
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [(f"CO{i}",) for i in range(51)]
    session = _Session()
    session.query = Mock(return_value=query)
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    with pytest.raises(ValueError, match="explicit smaller cohort"):
        runner._resolve_cohort_tickers("sync-companyfacts", [], False, None)
    query.limit.assert_called_once_with(51)
    assert session.closed


def test_explicit_small_limit_selects_requested_cohort(monkeypatch):
    import app.database

    query = Mock()
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [("AAPL",), ("MSFT",)]
    session = _Session()
    session.query = Mock(return_value=query)
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    assert runner._resolve_cohort_tickers("sync-companyfacts", [], False, 2) == ["AAPL", "MSFT"]
    query.limit.assert_called_once_with(2)
    assert session.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("job,module,function,stats", [
    ("filing-scan", "filing_scan_service", "run_filing_scan", {"source_errors": 1}),
    ("filing-digest", "filing_scan_service", "run_daily_digest", {"digests_failed": 1}),
    ("earnings-day-alerts", "earnings_alert_service", "send_earnings_day_alerts", {"failed": 1}),
    ("sync-companyfacts", "facts_service", "sync_companyfacts_batch", {"failed": 1}),
])
async def test_partial_failure_is_raised_and_worker_session_closed(monkeypatch, job, module, function, stats):
    import app.database
    from app import services

    session = _Session()
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    service = __import__(f"app.services.{module}", fromlist=[module])
    monkeypatch.setattr(services, module, service)
    action = AsyncMock(return_value=stats)
    monkeypatch.setattr(service, function, action)
    payload = {"job": job, "request_id": REQUEST_ID}
    if job in {"sync-companyfacts", "backfill-filing-history"}:
        payload.update(stage="run", tickers=["AAPL"])
    with pytest.raises(RuntimeError, match="incomplete work"):
        await runner.run_internal_task(payload)
    action.assert_awaited_once()
    assert session.closed


@pytest.mark.asyncio
async def test_history_worker_requires_complete_windows_and_releases_lookup_session(monkeypatch):
    import app.database
    from app.services import filing_history_service

    session = _Session()
    query = Mock()
    query.filter.return_value = query
    query.scalar.return_value = 12
    session.query = Mock(return_value=query)
    factory = Mock(return_value=session)
    monkeypatch.setattr(app.database, "SessionLocal", factory)

    async def backfill(company_id, *, session_factory, require_complete, force):
        assert session.closed
        assert company_id == 12
        assert session_factory is factory
        assert require_complete is True
        assert force is True
        raise RuntimeError("History backfill incomplete; retry missing windows")

    action = AsyncMock(side_effect=backfill)
    monkeypatch.setattr(filing_history_service, "backfill_company_by_id", action)
    with pytest.raises(RuntimeError, match="retry missing windows"):
        await runner.run_internal_task({
            "job": "backfill-filing-history", "request_id": REQUEST_ID,
            "stage": "run", "tickers": ["AAPL"],
        })
    action.assert_awaited_once()
    assert session.closed


@pytest.mark.asyncio
async def test_underlying_worker_exception_is_not_acknowledged(monkeypatch):
    import app.database
    from app.services import filing_scan_service

    session = _Session()
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    monkeypatch.setattr(filing_scan_service, "run_filing_scan", AsyncMock(side_effect=RuntimeError("source failed")))
    with pytest.raises(RuntimeError, match="source failed"):
        await runner.run_internal_task({"job": "filing-scan", "request_id": REQUEST_ID})
    assert session.closed


@pytest.mark.asyncio
async def test_refresh_commit_failure_is_not_acknowledged(monkeypatch):
    import app.database
    from app.services import earnings_calendar_service

    class Stats:
        def as_dict(self):
            return {"commit_failed": True, "source_errors": 0}

    session = _Session()
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    monkeypatch.setattr(earnings_calendar_service, "run_refresh", AsyncMock(return_value=Stats()))
    with pytest.raises(RuntimeError, match="commit_failed"):
        await runner.run_internal_task({"job": "earnings-calendar-refresh", "request_id": REQUEST_ID})
    assert session.closed


@pytest.mark.asyncio
async def test_retention_dry_run_is_awaited_in_worker(monkeypatch):
    import app.database
    from app.services import retention_service

    session = _Session()
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    action = Mock(return_value={"dry_run": True, "search_history_purged": 7})
    monkeypatch.setattr(retention_service, "run_retention_purge", action)
    await runner.run_internal_task({"job": "retention-purge", "request_id": REQUEST_ID, "dry_run": True})
    action.assert_called_once_with(session, dry_run=True)
    assert session.closed


@pytest.mark.asyncio
async def test_failed_precompute_is_not_acknowledged(monkeypatch):
    from app.services import precompute_service

    action = AsyncMock(return_value={"status": "generation_failed"})
    monkeypatch.setattr(precompute_service, "precompute_one", action)
    with pytest.raises(RuntimeError, match="generation_failed"):
        await runner.run_internal_task({
            "job": "precompute", "request_id": REQUEST_ID, "stage": "run",
            "tickers": ["AAPL"], "forms": ["10-K"],
        })
    action.assert_awaited_once_with("AAPL", "10-K", force=False)
