"""Pre-refactor characterization anchor for ``stream_filing_summary`` — the failure group.

These tests PIN the orchestrator's behaviour on the paths where its own bookkeeping fails or a
failure message has to be classified: a refund that cannot be written, a lease release that cannot
be written, ``record_progress`` failing inside the timeout and generic failure handlers, which
exception messages pass through to the client verbatim, and the generic failure path's progress
and funnel records. Every assertion is on an observable: yielded event dicts, DB rows, mock call
lists, the in-flight registry, the generation semaphore and the exact log text the code formats.
"""
import logging
import uuid
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from app.database import SessionLocal, engine
from app.models import Base, Summary, UsageReservation, User, UserUsage
from app.services import summary_pipeline
from app.services.ai.provider_requests import signal_provider_start
from app.services.subscription_service import get_current_month
from app.services.summary_pipeline import (
    EVENT_GENERATION_FAILED,
    EVENT_GENERATION_STARTED,
    EVENT_GENERATION_TIMED_OUT,
    GenerationUserSnapshot,
)
from tests.support.summary_stream_harness import (
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

LOGGER = "app.services.summary_pipeline"
INITIALIZING = {"type": "progress", "stage": "initializing", "message": "Initializing...", "percent": 0}
GENERIC_FAILURE = {"type": "error", "message": "Unable to retrieve this filing at the moment — please try again shortly."}
TIMED_OUT = {"type": "error", "message": "Summary generation timed out. Please try again."}


@pytest.fixture(autouse=True)
def _tables_and_registry():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


def _seed_user() -> int:
    with SessionLocal() as db:
        user = User(email=f"fail-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        db.commit()
        return user.id


def _state(user_id: int) -> tuple[int, int]:
    """(open reservations, counted units this month) for ``user_id``."""
    with SessionLocal() as db:
        reservations = db.query(UsageReservation).filter_by(user_id=user_id).count()
        bucket = db.query(UserUsage).filter_by(user_id=user_id, month=get_current_month()).first()
        return reservations, (bucket.summary_count if bucket else 0)


async def _drain(filing_id: int, **overrides) -> list[dict]:
    """Headless drain shape by default; ``overrides`` reach the generator (a user-facing shape passes
    ``current_user=GenerationUserSnapshot(...)`` as the SSE route does)."""
    kwargs = dict(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    )
    kwargs.update(overrides)
    return [event async for event in summary_pipeline.stream_filing_summary(**kwargs)]


def _pipeline_logs(caplog) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == LOGGER]


def _terminals(events: list[dict]) -> list[dict]:
    return [e for e in events if e["type"] in {"complete", "partial", "error"}]


def _summary_rows(filing_id: int) -> int:
    with SessionLocal() as db:
        return db.query(Summary).filter(Summary.filing_id == filing_id).count()


def _failing_record_progress():
    """A ``record_progress`` stand-in that only fails the ``error`` write."""
    real = summary_pipeline.record_progress

    def record(session, filing_id, stage, **kwargs):
        if stage == "error":
            raise RuntimeError("db down")
        return real(session, filing_id, stage, **kwargs)

    return MagicMock(side_effect=record)


# ------------------------------------------------------------ F1: the refund write itself fails

@pytest.mark.asyncio
async def test_refund_failure_is_logged_and_the_counted_unit_stays_counted(caplog):
    """A unit counted at provider start is refunded for an error payload; when that refund write
    raises, the WARNING names the reason and the error, the provider's message is still the only
    terminal, and the unit stays counted with no lease left (the failure is never masked)."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    user_id, filing_id = _seed_user(), seed_company_filing()

    async def signal_then_error(*args, **kwargs):
        signal_provider_start()  # the request is issued: the pipeline counts the unit from here
        return {"status": "error", "message": "model unavailable"}

    refund = MagicMock(side_effect=RuntimeError("refund db down"))
    with stream_boundaries() as summarize, patch.object(summary_pipeline, "refund_summary_use", refund):
        summarize.side_effect = signal_then_error
        events = await _drain(
            filing_id, current_user=GenerationUserSnapshot(user_id, False, None), user_id=user_id,
            telemetry_distinct_id=str(user_id),
        )

    assert events[-1] == {"type": "error", "message": "model unavailable"}
    assert _terminals(events) == [events[-1]]
    refund.assert_called_once()
    assert refund.call_args.args[:2] == (user_id, get_current_month())
    assert (
        logging.WARNING,
        f"[stream:{filing_id}] Could not refund usage unit (provider returned an error payload): refund db down",
    ) in _pipeline_logs(caplog)
    assert not any("Refunded the usage unit" in m for _, m in _pipeline_logs(caplog))
    assert _state(user_id) == (0, 1)
    assert _summary_rows(filing_id) == 0
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------ F2: the lease release in cleanup fails

@pytest.mark.asyncio
async def test_release_failure_in_cleanup_is_logged_and_the_lease_row_survives(caplog):
    """A provider failure before any start signal leaves the admission lease held; cleanup releases
    it, and when that write raises the WARNING is logged, the generic error is the only terminal,
    the lease row survives (nothing counted) and the slot and leadership are still given back."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    user_id, filing_id = _seed_user(), seed_company_filing()
    release = MagicMock(side_effect=RuntimeError("release db down"))
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    with stream_boundaries() as summarize, patch.object(summary_pipeline, "release_reservation", release):
        summarize.side_effect = RuntimeError("provider down")
        events = await _drain(
            filing_id, current_user=GenerationUserSnapshot(user_id, False, None), user_id=user_id,
            telemetry_distinct_id=str(user_id),
        )

    assert events[-1] == GENERIC_FAILURE
    assert _terminals(events) == [events[-1]]
    release.assert_called_once()
    assert (logging.WARNING, f"[stream:{filing_id}] Could not release usage reservation: release db down") in _pipeline_logs(caplog)
    assert (logging.ERROR, f"[stream:{filing_id}] Error in streaming summary: provider down") in _pipeline_logs(caplog)
    assert _state(user_id) == (1, 0)
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------- F3: record_progress fails inside the timeout handler

@pytest.mark.asyncio
async def test_timeout_handler_survives_a_failing_error_progress_write(caplog):
    """A follower whose wait budget is exhausted takes the pipeline-timeout path: when the ``error``
    progress write raises, the ERROR is logged with a traceback, the timeout message is still the
    only terminal, the funnel records STARTED then TIMED_OUT, and the active leader keeps its slot."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    leader = summary_pipeline._claim_inflight(filing_id)
    record_progress = _failing_record_progress()
    funnel = MagicMock()
    try:
        with stream_boundaries() as summarize, \
                patch.object(summary_pipeline, "INFLIGHT_WAIT_CAP_SECONDS", 0), \
                patch.object(summary_pipeline, "record_progress", record_progress), \
                patch.object(summary_pipeline, "capture_funnel_event", funnel):
            events = await _drain(filing_id, emit_funnel_telemetry=True)
        assert summary_pipeline._inflight_generations.get(filing_id) is leader
        assert not leader.is_set()
    finally:
        summary_pipeline._release_inflight(filing_id, leader)

    assert events[-1] == TIMED_OUT
    assert _terminals(events) == [events[-1]]
    assert [e["stage"] for e in events if e["type"] == "progress"] == ["initializing", "queued"]
    summarize.assert_not_called()
    assert record_progress.call_args_list == [call(ANY, filing_id, "error", error="Pipeline timeout")]
    error_records = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.ERROR]
    assert [r.getMessage() for r in error_records] == [
        f"[stream:{filing_id}] Failed to record pipeline timeout error: db down"
    ]
    assert error_records[0].exc_info is not None and error_records[0].exc_info[0] is RuntimeError
    assert (logging.WARNING, f"[stream:{filing_id}] Pipeline timeout after 120s") in _pipeline_logs(caplog)
    assert funnel.call_args_list == [
        call("offline", EVENT_GENERATION_STARTED, entry_point=None),
        call("offline", EVENT_GENERATION_TIMED_OUT, duration_ms=ANY, result_type="timeout", entry_point=None),
    ]
    assert isinstance(funnel.call_args_list[1].kwargs["duration_ms"], int)


# ------------------------------------- F4: record_progress fails inside the generic handler

@pytest.mark.asyncio
async def test_generic_handler_survives_a_failing_error_progress_write(caplog):
    """When the provider raises and the ``error`` progress write raises too, both failures are
    logged at ERROR (the second with a traceback) and the generic message is still the only
    terminal; nothing is persisted."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    record_progress = _failing_record_progress()
    with stream_boundaries() as summarize, patch.object(summary_pipeline, "record_progress", record_progress):
        summarize.side_effect = RuntimeError("provider down")
        events = await _drain(filing_id)

    assert events[-1] == GENERIC_FAILURE
    assert _terminals(events) == [events[-1]]
    error_records = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.ERROR]
    assert [r.getMessage() for r in error_records] == [
        f"[stream:{filing_id}] Error in streaming summary: provider down",
        f"[stream:{filing_id}] Failed to record streaming error: db down",
    ]
    assert error_records[1].exc_info is not None and error_records[1].exc_info[0] is RuntimeError
    assert [c.args[2] for c in record_progress.call_args_list] == [
        "fetching", "parsing", "analyzing", "summarizing", "error",
    ]
    assert _summary_rows(filing_id) == 0
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------ F5: which failure messages reach the client verbatim

@pytest.mark.parametrize(
    "raised, expected",
    [
        ("Unable to complete this analysis right now", "Unable to complete this analysis right now"),
        ("Unable to retrieve " + "x" * 231, ("Unable to retrieve " + "x" * 231)[:200]),
        ("kaboom", GENERIC_FAILURE["message"]),
    ],
    ids=["unable_to_complete_passes_through", "unable_to_retrieve_is_cut_at_200", "anything_else_is_generic"],
)
@pytest.mark.asyncio
async def test_failure_message_classification_and_the_failed_funnel_event(raised: str, expected: str):
    """Messages that already read ``Unable to retrieve``/``Unable to complete`` reach the client
    verbatim (cut at 200 characters); every other exception becomes the generic retrieval error.
    The failed funnel event always carries the raw message cut at 200 plus the telemetry context."""
    filing_id = seed_company_filing()
    funnel = MagicMock()
    with stream_boundaries() as summarize, patch.object(summary_pipeline, "capture_funnel_event", funnel):
        summarize.side_effect = RuntimeError(raised)
        events = await _drain(
            filing_id, emit_funnel_telemetry=True, telemetry_entry_point="generate_button",
            telemetry_ctx={"surface": "filing_page"},
        )

    assert events[-1] == {"type": "error", "message": expected}
    assert len(expected) <= 200
    assert _terminals(events) == [events[-1]]
    assert funnel.call_args_list == [
        call("offline", EVENT_GENERATION_STARTED, entry_point="generate_button", surface="filing_page"),
        call("offline", EVENT_GENERATION_FAILED, duration_ms=ANY, result_type="error", entry_point="generate_button",
             error=raised[:200], surface="filing_page"),
    ]
    assert filing_id not in summary_pipeline._inflight_generations


# -------------------------------------- F6: the headless generic failure path's records

@pytest.mark.asyncio
async def test_headless_provider_failure_records_error_progress_and_persists_nothing(caplog):
    """The background drain shape on a provider exception: the ``error`` progress write carries the
    message, no Summary row exists, the ERROR log names the exception, the stream's non-progress
    events are the single generic error, and (with no lease) nothing is refunded or released."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    record_progress = MagicMock(wraps=summary_pipeline.record_progress)
    refund, release = MagicMock(), MagicMock()
    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline, "record_progress", record_progress), \
            patch.object(summary_pipeline, "refund_summary_use", refund), \
            patch.object(summary_pipeline, "release_reservation", release):
        summarize.side_effect = RuntimeError("kaboom")
        events = await _drain(filing_id)

    assert events[0] == INITIALIZING
    assert [e for e in events if e["type"] != "progress"] == [GENERIC_FAILURE]
    assert record_progress.call_args_list[-1] == call(ANY, filing_id, "error", error="kaboom")
    assert (logging.ERROR, f"[stream:{filing_id}] Error in streaming summary: kaboom") in _pipeline_logs(caplog)
    refund.assert_not_called()
    release.assert_not_called()
    assert _summary_rows(filing_id) == 0
    assert filing_id not in summary_pipeline._inflight_generations
