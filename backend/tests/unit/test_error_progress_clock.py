"""E217: a run's error progress write starts the row's clock only when the error is a leader's first write.

E216 starts a run's clock (``started_at``, ``elapsed_seconds``) at the fetch stage's write, an admitted run's first. A
run that failed before that write wrote only its error (``failure.timed_out``, ``failure.failed``), which kept the clock
of the row an earlier run left: a leader that timed out waiting for a generation slot left the watchlist reading
7,200 s beside its error on a two-hour-old row. ``GenerationRun.error_starts_clock`` now asks the writer to start the
clock for a leader, the run holding the filing's claim, whose fetch stage's write has not returned. A follower's error
goes to the row its live leader owns. A run that fails in ``load_filing``, before the in-flight registry is read, cannot
tell whether a live leader in its own process owns the row, and a run whose claim itself raises holds no claim, which
the rule goes by: all of them keep the clock, as does a leader whose fetch stage has written. The error still marks a
live leader's row as before; only the clock is this change's.

Each case drives the one orchestrator offline (``stream_boundaries``) with the real writer and reads the row after. The
service's clock is pinned, so each elapsed time is exact; SQLite's date functions keep milliseconds, which the tolerance
allows for. The cases past the fetch stage move the clock on when SEC EDGAR or the provider is called, and a timeout case
fires the pipeline's backstop, a real deadline, at the moment it chooses.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app import database
from app.database import Base, SessionLocal, engine
from app.models import FilingContentCache, SummaryGenerationProgress
from app.services import summary_generation_service, summary_pipeline
from tests.support.summary_stream_harness import reset_inflight, seed_company_filing, stream_boundaries

NOW = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)
# An earlier run's error row, two hours old; and a live leader's row, 30 s into its run.
EARLIER = NOW - timedelta(hours=2)
LIVE_START = NOW - timedelta(seconds=30)


@pytest.fixture
def clock(monkeypatch):
    """The service's clock, pinned to ``NOW``; a case moves it on by assigning ``clock.now``."""
    clock = SimpleNamespace(now=NOW)
    monkeypatch.setattr(summary_generation_service, "utcnow", lambda: clock.now)
    return clock


@pytest.fixture(autouse=True)
def pipeline_tables():
    """The test database the one orchestrator runs on, as its anchors set it up."""
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


def _seed(filing_id, *, stage, started_at, error=None):
    with SessionLocal() as db:
        db.add(SummaryGenerationProgress(filing_id=filing_id, stage=stage, started_at=started_at,
                                         updated_at=started_at + timedelta(seconds=10), elapsed_seconds=10.0,
                                         error=error))
        db.commit()


def _seed_fresh_cache(filing_id):
    """A content cache admission trusts (created now, so under its 24 hours), which the fetch stage reads instead of
    fetching the filing."""
    with SessionLocal() as db:
        db.add(FilingContentCache(filing_id=filing_id, critical_excerpt="EXCERPT"))
        db.commit()


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _row(filing_id):
    with SessionLocal() as db:
        row = db.get(SummaryGenerationProgress, filing_id)
        return row.stage, _aware(row.started_at), row.elapsed_seconds, row.error


async def _drain(filing_id):
    return [event async for event in summary_pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False)]


def _backstop(monkeypatch):
    """The pipeline's backstop as a real deadline that fires when the case calls the function returned, rather than
    after a budget that would race the stages before it."""
    deadline = asyncio.timeout(None)
    monkeypatch.setattr(summary_pipeline, "asyncio", SimpleNamespace(
        **{**vars(asyncio), "timeout": lambda _seconds: deadline}))
    return lambda: deadline.reschedule(asyncio.get_running_loop().time())


def _no_free_slot(monkeypatch):
    """Every generation slot held, and the backstop firing as the leader starts to wait for one."""
    fire_backstop = _backstop(monkeypatch)

    class NoFreeSlot(asyncio.Semaphore):
        async def acquire(self):
            fire_backstop()
            return await super().acquire()

    monkeypatch.setattr(summary_pipeline, "_get_generation_semaphore", lambda: NoFreeSlot(0))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["slot_timeout", "admission_raises"])
async def test_a_leaders_error_before_its_fetch_stage_starts_the_clock(clock, monkeypatch, failure):
    """A leader that times out waiting for a generation slot, or whose admission raises, fails with the error as its
    first write: the row an earlier run left counts from that error, not from two hours before."""
    filing_id = seed_company_filing()
    _seed(filing_id, stage="error", started_at=EARLIER, error="an earlier failure")
    if failure == "slot_timeout":
        _no_free_slot(monkeypatch)
        expected = "Pipeline timeout"
    else:
        monkeypatch.setattr(summary_pipeline, "_get_generation_semaphore", _raise("no slot table"))
        expected = "no slot table"
    with stream_boundaries() as summarize:
        events = await _drain(filing_id)
    assert events[-1]["type"] == "error"
    summarize.assert_not_called()
    assert _row(filing_id) == ("error", NOW, 0.0, expected)


@pytest.mark.asyncio
async def test_a_followers_error_keeps_the_live_leaders_clock(clock):
    """A follower whose wait budget runs out writes its timeout onto the live leader's row, which keeps counting from
    the leader's start."""
    filing_id = seed_company_filing()
    _seed(filing_id, stage="analyzing", started_at=LIVE_START)
    leader = summary_pipeline._claim_inflight(filing_id)
    try:
        with stream_boundaries() as summarize, patch.object(summary_pipeline, "INFLIGHT_WAIT_CAP_SECONDS", 0):
            events = await _drain(filing_id)
        assert summary_pipeline._inflight_generations.get(filing_id) is leader
    finally:
        summary_pipeline._release_inflight(filing_id, leader)
    assert events[-1]["type"] == "error"
    summarize.assert_not_called()
    assert _row(filing_id) == ("error", LIVE_START, pytest.approx(30.0, abs=1e-3), "Pipeline timeout")


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [
    "provider_raises", "provider_raises_from_cache", "provider_raises_for_a_6k", "backstop_in_generation",
    "backstop_in_sec_fetch"])
async def test_a_leaders_error_after_its_fetch_stage_keeps_its_own_clock(clock, monkeypatch, failure):
    """A leader that fails 5 s after its fetch stage started the clock counts its error from that start: when its
    provider raises (``failure.failed``) after any of the fetch stage's three branches (SEC EDGAR's document, a fresh
    content cache that fetches nothing, a 6-K's exhibits), and when the backstop fires (``failure.timed_out``) as it
    waits for the provider, or for SEC EDGAR's document between its fetch stage's write and its parsing stage's."""
    filing_id = seed_company_filing(filing_type="6-K" if failure == "provider_raises_for_a_6k" else "10-K")
    _seed(filing_id, stage="error", started_at=EARLIER, error="an earlier failure")
    if failure == "provider_raises_from_cache":
        _seed_fresh_cache(filing_id)
    if failure == "provider_raises_for_a_6k":
        monkeypatch.setattr(summary_pipeline, "get_sixk_text", AsyncMock(return_value="Exhibit 99.1: the quarter."))
    fire_backstop = _backstop(monkeypatch) if failure.startswith("backstop") else None

    async def five_seconds_on(*args, **kwargs):
        clock.now = NOW + timedelta(seconds=5)
        if fire_backstop is None:
            raise RuntimeError("provider down")
        fire_backstop()
        await asyncio.Event().wait()  # the run's release cancels this wait once the backstop has fired

    with stream_boundaries() as summarize:
        sec_fetch = summary_pipeline.sec_edgar_service.get_filing_document
        if failure == "backstop_in_sec_fetch":
            sec_fetch.side_effect = five_seconds_on
        else:
            summarize.side_effect = five_seconds_on
        events = await _drain(filing_id)
    assert events[-1]["type"] == "error"
    assert sec_fetch.call_count == (0 if failure in ("provider_raises_from_cache", "provider_raises_for_a_6k") else 1)
    assert summarize.call_count == (0 if failure == "backstop_in_sec_fetch" else 1)
    expected = "Pipeline timeout" if failure.startswith("backstop") else "provider down"
    assert _row(filing_id) == ("error", NOW, pytest.approx(5.0, abs=1e-3), expected)


@pytest.mark.asyncio
async def test_a_leaders_error_after_a_failed_fetch_write_starts_the_clock(clock, monkeypatch):
    """The fetch stage's write raises before it lands, so the run's error is still its first write: the flag is set
    only once that write has returned, and the error restarts the earlier run's clock."""
    filing_id = seed_company_filing()
    _seed(filing_id, stage="error", started_at=EARLIER, error="an earlier failure")
    real = summary_pipeline.record_progress

    def fetch_write_fails(db, progress_filing_id, stage, **kwargs):
        if stage == "fetching":
            raise RuntimeError("progress table locked")
        return real(db, progress_filing_id, stage, **kwargs)

    monkeypatch.setattr(summary_pipeline, "record_progress", fetch_write_fails)
    with stream_boundaries() as summarize:
        events = await _drain(filing_id)
    assert events[-1]["type"] == "error"
    summarize.assert_not_called()
    assert _row(filing_id) == ("error", NOW, 0.0, "progress table locked")


class _FirstSessionFails:
    """``database.SessionLocal`` whose first session, ``load_filing``'s read, fails to open; the rest are real."""

    def __init__(self, real):
        self.real, self.calls = real, 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("database unavailable")
        return self.real(*args, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["load_filing_raises", "claim_raises"])
async def test_a_run_that_fails_before_its_claim_keeps_the_rows_clock(clock, monkeypatch, failure):
    """A run whose ``load_filing`` read fails has not read the in-flight registry, so it cannot tell whether a live
    leader in its own process owns the row: here one does, 30 s into its run, and the row keeps counting from its
    start. A run whose claim itself raises, after a read that found no local leader, keeps the clock too: the rule
    goes by the claim."""
    filing_id = seed_company_filing()
    _seed(filing_id, stage="analyzing", started_at=LIVE_START)
    leader = None
    if failure == "load_filing_raises":
        leader = summary_pipeline._claim_inflight(filing_id)
        monkeypatch.setattr(database, "SessionLocal", _FirstSessionFails(database.SessionLocal))
        expected = "database unavailable"
    else:
        monkeypatch.setattr(summary_pipeline, "_claim_inflight", _raise("registry down"))
        expected = "registry down"
    try:
        with stream_boundaries() as summarize:
            events = await _drain(filing_id)
    finally:
        if leader is not None:
            summary_pipeline._release_inflight(filing_id, leader)
    assert events[-1]["type"] == "error"
    summarize.assert_not_called()
    assert _row(filing_id) == ("error", LIVE_START, pytest.approx(30.0, abs=1e-3), expected)


def _raise(message):
    def raises(*args, **kwargs):
        raise RuntimeError(message)
    return raises
