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

import app.database
from app.routers import internal

_LOGGER = "app.routers.internal"


class _Stats:
    """A stats object that logs through ``as_dict()``, as RefreshStats and ScanStats do."""

    def as_dict(self) -> dict:
        return {"rows": 3}


# (runner, runner args, service module, service function, expected call args after the session,
#  expected call kwargs, the log label, whether the log line formats ``stats.as_dict()``)
RUNNERS = [
    (internal._run_filing_scan, (), "filing_scan_service", "run_filing_scan", (), {},
     "Filing scan", False),
    (internal._run_daily_digest, (), "filing_scan_service", "run_daily_digest", (), {},
     "Daily digest", False),
    (internal._run_retention_purge, (True,), "retention_service", "run_retention_purge", (),
     {"dry_run": True}, "Retention purge", False),
    (internal._run_earnings_refresh, (), "earnings_calendar_service", "run_refresh", (), {},
     "Earnings-calendar refresh", True),
    (internal._run_earnings_alerts, (), "earnings_alert_service", "send_earnings_day_alerts", (), {},
     "Earnings-day alerts", False),
    (internal._run_backfill_facts, (), "facts_service", "backfill_facts", (), {},
     "Facts backfill", False),
    (internal._run_notable_filings_scan, (7,), "notable_filings_service", "run_scan", (),
     {"days": 7}, "Notable-filings scan", True),
    (internal._run_sync_companyfacts, (["AAPL"], True, 5, True), "facts_service",
     "sync_companyfacts_batch", (), {"tickers": ["AAPL"], "watchlist_only": True, "limit": 5, "force": True},
     "Companyfacts sync", False),
    (internal._run_backfill_filing_history, (["AAPL"], False, None), "filing_history_service",
     "batch_backfill", (), {"tickers": ["AAPL"], "watchlist_only": False, "limit": None},
     "Filing-history backfill", False),
    # An empty ticker list reaches the service as None, which selects by the other filters.
    (internal._run_sync_companyfacts, ([], False, None, False), "facts_service", "sync_companyfacts_batch", (),
     {"tickers": None, "watchlist_only": False, "limit": None, "force": False}, "Companyfacts sync", False),
    (internal._run_backfill_filing_history, ([], True, 2), "filing_history_service", "batch_backfill", (),
     {"tickers": None, "watchlist_only": True, "limit": 2}, "Filing-history backfill", False),
]
IDS = [runner.__name__ for runner, *_ in RUNNERS[:-2]] + [
    "_run_sync_companyfacts-no-tickers", "_run_backfill_filing_history-no-tickers",
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
    sync = runner.__name__ in SYNC_RUNNERS
    mock = (MagicMock if sync else AsyncMock)(name=function, return_value=result, side_effect=error)
    monkeypatch.setattr(_service(module_name), function, mock)
    return mock


def test_the_threadpool_runners_stay_synchronous():
    for runner, *_ in RUNNERS:
        assert inspect.iscoroutinefunction(runner) is (runner.__name__ not in SYNC_RUNNERS), runner.__name__


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner", "args", "module_name", "function", "call_args", "call_kwargs", "label", "as_dict"),
    RUNNERS, ids=IDS,
)
async def test_a_run_hands_its_own_session_to_the_job_logs_the_stats_and_closes(
    monkeypatch, caplog, runner, args, module_name, function, call_args, call_kwargs, label, as_dict,
):
    session = _session(monkeypatch)
    stats = _Stats() if as_dict else {"rows": 3}
    job = _install(monkeypatch, module_name, function, runner, result=stats)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        await _invoke(runner, args)

    job.assert_called_once_with(session, *call_args, **call_kwargs)
    session.close.assert_called_once_with()
    records = [(r.name, r.levelno, r.getMessage()) for r in caplog.records if r.name == _LOGGER]
    assert records == [(_LOGGER, logging.INFO, f"{label} (internal trigger) complete: {{'rows': 3}}")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("runner", "args", "module_name", "function", "call_args", "call_kwargs", "label", "as_dict"),
    RUNNERS, ids=IDS,
)
async def test_a_failed_run_logs_the_error_and_still_closes_its_session(
    monkeypatch, caplog, runner, args, module_name, function, call_args, call_kwargs, label, as_dict,
):
    session = _session(monkeypatch)
    error = RuntimeError(f"{function} failed")
    _install(monkeypatch, module_name, function, runner, error=error)

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        await _invoke(runner, args)  # the failure is logged, never raised out of the background task

    session.close.assert_called_once_with()
    records = [r for r in caplog.records if r.name == _LOGGER]
    assert [(r.levelno, r.getMessage()) for r in records] == [(logging.ERROR, f"{label} (internal trigger) failed")]
    assert records[0].exc_info is not None and records[0].exc_info[1] is error
