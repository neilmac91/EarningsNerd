"""The /internal/jobs/* triggers' flag-off runs: each one owns a session and logs its own outcome.

With ``DURABLE_TASKS_ENABLED`` off, a trigger answers 202 and detaches its job as a FastAPI
background task (``test_internal_jobs.py`` drives that through HTTP). The runner then opens a
session of its own, hands it to one service call, logs the stats or the failure on the router's
logger and closes the session, whether the job succeeds or raises. A failure never escapes the
runner. ``_run_retention_purge`` and ``_run_backfill_facts`` are plain functions, so FastAPI runs
them in its threadpool, off the event loop; the rest are coroutines.
"""
from __future__ import annotations

import inspect
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks, Response

import app.database
from app.config import settings
from app.routers import internal

_LOGGER = "app.routers.internal"


class _Stats:
    """A stats object that logs through ``as_dict()``, as RefreshStats and ScanStats do."""

    def as_dict(self) -> dict:
        return {"rows": 3}


# (runner, runner args, service module, service function, the call's kwargs after the session, the log
#  label, whether the log line formats ``stats.as_dict()``)
RUNNERS = [
    pytest.param(internal._run_filing_scan, (), "filing_scan_service", "run_filing_scan", {},
                 "Filing scan", False, id="filing_scan"),
    pytest.param(internal._run_daily_digest, (), "filing_scan_service", "run_daily_digest", {},
                 "Daily digest", False, id="daily_digest"),
    pytest.param(internal._run_retention_purge, (True,), "retention_service", "run_retention_purge",
                 {"dry_run": True}, "Retention purge", False, id="retention_purge"),
    pytest.param(internal._run_earnings_refresh, (), "earnings_calendar_service", "run_refresh", {},
                 "Earnings-calendar refresh", True, id="earnings_refresh"),
    pytest.param(internal._run_earnings_alerts, (), "earnings_alert_service", "send_earnings_day_alerts", {},
                 "Earnings-day alerts", False, id="earnings_alerts"),
    pytest.param(internal._run_backfill_facts, (), "facts_service", "backfill_facts", {},
                 "Facts backfill", False, id="backfill_facts"),
    pytest.param(internal._run_notable_filings_scan, (7,), "notable_filings_service", "run_scan",
                 {"days": 7}, "Notable-filings scan", True, id="notable_filings_scan"),
    pytest.param(internal._run_sync_companyfacts, (["AAPL"], True, 5, True), "facts_service",
                 "sync_companyfacts_batch", {"tickers": ["AAPL"], "watchlist_only": True, "limit": 5, "force": True},
                 "Companyfacts sync", False, id="sync_companyfacts"),
    pytest.param(internal._run_backfill_filing_history, (["AAPL"], False, None), "filing_history_service",
                 "batch_backfill", {"tickers": ["AAPL"], "watchlist_only": False, "limit": None},
                 "Filing-history backfill", False, id="backfill_filing_history"),
    # An empty ticker list reaches the service as None, which selects by the other filters.
    pytest.param(internal._run_sync_companyfacts, ([], False, None, False), "facts_service",
                 "sync_companyfacts_batch", {"tickers": None, "watchlist_only": False, "limit": None, "force": False},
                 "Companyfacts sync", False, id="sync_companyfacts-no-tickers"),
    pytest.param(internal._run_backfill_filing_history, ([], True, 2), "filing_history_service",
                 "batch_backfill", {"tickers": None, "watchlist_only": True, "limit": 2},
                 "Filing-history backfill", False, id="backfill_filing_history-no-tickers"),
]
SYNC_RUNNERS = {"_run_retention_purge", "_run_backfill_facts"}


def _service(module_name: str):
    from app import services

    __import__(f"app.services.{module_name}")
    return getattr(services, module_name)


def _session(monkeypatch) -> MagicMock:
    session = MagicMock(name="session")
    monkeypatch.setattr(app.database, "SessionLocal", lambda: session)
    return session


async def _invoke(runner, args):
    result = runner(*args)
    if inspect.isawaitable(result):
        await result


def _install(monkeypatch, module_name: str, function: str, runner, *, result=None, error=None):
    """Stand in for the service function. ``open_while_running`` records, each time the job body
    runs, whether its session was still open: an async mock runs its side effect when it is
    awaited, so a session closed before the await shows up as False."""
    open_while_running: list[bool] = []

    def body(db, *args, **kwargs):
        open_while_running.append(not db.close.called)
        if error is not None:
            raise error
        return result

    sync = runner.__name__ in SYNC_RUNNERS
    mock = (MagicMock if sync else AsyncMock)(name=function, side_effect=body)
    monkeypatch.setattr(_service(module_name), function, mock)
    return mock, open_while_running


def test_the_threadpool_runners_stay_synchronous():
    for runner in {param.values[0] for param in RUNNERS}:
        assert inspect.iscoroutinefunction(runner) is (runner.__name__ not in SYNC_RUNNERS), runner.__name__


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner", "args", "module_name", "function", "call_kwargs", "label", "as_dict"), RUNNERS,
)
async def test_a_run_hands_its_own_session_to_the_job_logs_the_stats_and_closes(
    monkeypatch, caplog, runner, args, module_name, function, call_kwargs, label, as_dict,
):
    session = _session(monkeypatch)
    stats = _Stats() if as_dict else {"rows": 3}
    job, open_while_running = _install(monkeypatch, module_name, function, runner, result=stats)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        await _invoke(runner, args)

    job.assert_called_once_with(session, **call_kwargs)
    assert open_while_running == [True]  # the job ran on its session before the close
    session.close.assert_called_once_with()
    records = [(r.name, r.levelno, r.getMessage()) for r in caplog.records if r.name == _LOGGER]
    assert records == [(_LOGGER, logging.INFO, f"{label} (internal trigger) complete: {{'rows': 3}}")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner", "args", "module_name", "function", "call_kwargs", "label", "as_dict"), RUNNERS,
)
async def test_a_failed_run_logs_the_error_and_still_closes_its_session(
    monkeypatch, caplog, runner, args, module_name, function, call_kwargs, label, as_dict,
):
    session = _session(monkeypatch)
    error = RuntimeError(f"{function} failed")
    _, open_while_running = _install(monkeypatch, module_name, function, runner, error=error)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        await _invoke(runner, args)  # the failure is logged, never raised out of the background task

    assert open_while_running == [True]
    session.close.assert_called_once_with()
    records = [r for r in caplog.records if r.name == _LOGGER]
    assert [(r.levelno, r.getMessage()) for r in records] == [(logging.ERROR, f"{label} (internal trigger) failed")]
    assert records[0].exc_info is not None and records[0].exc_info[1] is error


# (endpoint call, the runner it detaches, that runner's args, the 202 body)
FLAG_OFF_TRIGGERS = [
    pytest.param(lambda bg: internal.trigger_filing_scan(bg), internal._run_filing_scan, (),
                 {"status": "accepted", "job": "filing-scan"}, id="filing-scan"),
    pytest.param(lambda bg: internal.trigger_filing_digest(bg), internal._run_daily_digest, (),
                 {"status": "accepted", "job": "filing-digest"}, id="filing-digest"),
    pytest.param(lambda bg: internal.trigger_retention_purge(bg, dry_run=True), internal._run_retention_purge, (True,),
                 {"status": "accepted", "job": "retention-purge", "dry_run": True}, id="retention-purge"),
    pytest.param(lambda bg: internal.trigger_earnings_refresh(bg), internal._run_earnings_refresh, (),
                 {"status": "accepted", "job": "earnings-calendar-refresh"}, id="earnings-calendar-refresh"),
    pytest.param(lambda bg: internal.trigger_earnings_alerts(bg), internal._run_earnings_alerts, (),
                 {"status": "accepted", "job": "earnings-day-alerts"}, id="earnings-day-alerts"),
    # The flag-off run backfills every filing and does not read ``limit``; the durable path forwards it.
    pytest.param(lambda bg: internal.trigger_backfill_facts(bg, limit=10), internal._run_backfill_facts, (),
                 {"status": "accepted", "job": "backfill-facts"}, id="backfill-facts"),
    pytest.param(lambda bg: internal.trigger_notable_filings_scan(bg, internal.NotableFilingsScanRequest(days=7)),
                 internal._run_notable_filings_scan, (7,),
                 {"status": "accepted", "job": "notable-filings-scan", "days": 7}, id="notable-filings-scan"),
    pytest.param(lambda bg: internal.trigger_sync_companyfacts(internal.SyncCompanyfactsRequest(
                     tickers=[" aapl ", "", "msft"], watchlist_only=True, limit=5, force=True), bg),
                 internal._run_sync_companyfacts, (["AAPL", "MSFT"], True, 5, True),
                 {"status": "accepted", "job": "sync-companyfacts", "tickers": 2, "watchlist_only": True},
                 id="sync-companyfacts"),
    pytest.param(lambda bg: internal.trigger_backfill_filing_history(internal.BackfillFilingHistoryRequest(
                     tickers=["aapl"], limit=3), bg),
                 internal._run_backfill_filing_history, (["AAPL"], False, 3),
                 {"status": "accepted", "job": "backfill-filing-history", "tickers": 1, "watchlist_only": False},
                 id="backfill-filing-history"),
    pytest.param(lambda bg: internal.trigger_precompute(internal.PrecomputeRequest(
                     tickers=["aapl"], forms=[" 10-q "]), bg, Response()),
                 internal._run_precompute, (["AAPL"], ["10-Q"], False),
                 {"status": "accepted", "job": "precompute", "tickers": 1, "forms": ["10-Q"]}, id="precompute"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("call", "runner", "runner_args", "body"), FLAG_OFF_TRIGGERS)
async def test_a_flag_off_trigger_answers_202_and_detaches_its_runner_with_the_request_arguments(
    monkeypatch, call, runner, runner_args, body,
):
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", False)
    background = BackgroundTasks()

    assert await call(background) == body
    assert [(task.func, task.args, task.kwargs) for task in background.tasks] == [(runner, runner_args, {})]
