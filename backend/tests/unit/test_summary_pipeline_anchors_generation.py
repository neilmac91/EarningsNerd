"""Pre-refactor characterization anchor for ``stream_filing_summary`` — the generation group.

These tests PIN the orchestrator's behaviour across the provider/heartbeat stage exactly as it runs
today — the in-stage 75s AI fallback, the section-preview queue behind ``STREAM_SECTION_REVEAL``, a
provider task cancelled from outside the pipeline, the ``record_progress`` failure on the
error-payload path, and the shape of the summarizing heartbeats — so the upcoming decomposition into
stage modules can prove ZERO observable change. Every assertion is on an observable: yielded event
dicts, DB rows, mock call args, the in-flight registry, the generation semaphore, and the exact log
text the code formats.
"""
import asyncio
import logging
import re
import time
import types
from copy import deepcopy
from typing import Callable, Optional
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary, SummaryGenerationProgress
from app.services import summary_pipeline
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

LOGGER = "app.services.summary_pipeline"
DOCUMENT_TEXT = "FILING DOCUMENT TEXT " * 40
STEP_FIVE = {
    "type": "progress", "stage": "summarizing",
    "message": "Step 5: Generating investor-focused summary...", "percent": 50,
}
SUMMARIZE_MESSAGES = [
    "Analyzing financial highlights...",
    "Cross-referencing with XBRL data...",
    "Extracting key metrics from MD&A...",
]
AI_TIMEOUT_WARNING = r"\[stream:{filing_id}\] AI summarization timed out after \d+\.\ds\. Switching to fallback\."


@pytest.fixture(autouse=True)
def _tables_and_registry():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


async def _drain(filing_id: int, on_event: Optional[Callable[[dict], None]] = None) -> list[dict]:
    """Headless drain shape (the background/cron path); ``on_event`` runs between generator turns."""
    events: list[dict] = []
    async for event in summary_pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    ):
        events.append(event)
        if on_event is not None:
            on_event(event)
    return events


def _pipeline_logs(caplog) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == LOGGER]


def _without_elapsed(events: list[dict]) -> list[dict]:
    """Mask the wall-clock field only; every carrier must still have it as an ``int``."""
    masked = []
    for event in events:
        if "elapsed_seconds" in event:
            assert isinstance(event["elapsed_seconds"], int), event
            masked.append({k: v for k, v in event.items() if k != "elapsed_seconds"})
        else:
            masked.append(event)
    return masked


def _summarizing(events: list[dict]) -> list[dict]:
    """Every summarizing-stage event (Step 5, previews, heartbeats) in order, wall-clock masked."""
    return _without_elapsed([e for e in events if e.get("stage") == "summarizing"])


def _is_heartbeat(event: dict) -> bool:
    return event["type"] == "progress" and event.get("stage") == "summarizing" and "heartbeat_count" in event


def _heartbeat(index: int) -> dict:
    return {
        "type": "progress", "stage": "summarizing", "message": SUMMARIZE_MESSAGES[index],
        "heartbeat_count": index, "percent": 50 + 2 * index,
    }


def _terminals(events: list[dict]) -> list[dict]:
    return [e for e in events if e["type"] in {"complete", "partial", "error"}]


def _summary_rows(filing_id: int) -> list[int]:
    with SessionLocal() as db:
        return [row.id for row in db.query(Summary).filter(Summary.filing_id == filing_id).all()]


def _progress_row(filing_id: int) -> Optional[tuple[str, Optional[str]]]:
    with SessionLocal() as db:
        row = db.get(SummaryGenerationProgress, filing_id)
        return (row.stage, row.error) if row else None


def _fallback_kwargs(filing_id: int) -> dict:
    """The exact ``generate_xbrl_summary`` kwargs the pipeline builds for the harness seed."""
    with SessionLocal() as db:
        filing_date = db.get(Filing, filing_id).filing_date.isoformat()
    return {
        "xbrl_data": None, "company_name": "Harness Co", "filing_date": filing_date,
        "filing_text": DOCUMENT_TEXT, "filing_type": "10-K", "filing_excerpt": "EXCERPT",
    }


def _shifted_clock(shift: list[float]) -> types.SimpleNamespace:
    """A ``summary_pipeline.time`` stand-in: the real module's attributes with ``time()`` advanced by
    ``shift[0]`` seconds, so the in-stage deadline can be crossed without sleeping."""
    real_time = time.time
    return types.SimpleNamespace(**{**vars(time), "time": lambda: real_time() + shift[0]})


def _assert_completed_and_persisted(events: list[dict], filing_id: int) -> None:
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    assert _terminals(events) == [events[-1]]
    assert _summary_rows(filing_id) == [events[-1]["summary_id"]]
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------------- D1: in-stage 75s AI fallback

@pytest.mark.asyncio
async def test_in_stage_ai_timeout_cancels_the_provider_and_serves_the_xbrl_fallback(caplog):
    """Once more than 75s have passed in the summarizing stage, the heartbeat turn logs the timeout
    at WARNING, cancels the provider task (its cleanup runs), calls the deterministic XBRL fallback
    exactly once with the full filing context, and the stream still completes with a persisted
    Summary — no heartbeat is emitted on that turn."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    shift = [0.0]
    provider = {"cancelled": False}

    async def hang_until_cancelled(*args, **kwargs):
        shift[0] = 80.0  # the stage clock jumps past the deadline as soon as the provider starts
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            provider["cancelled"] = True
            raise

    fallback = MagicMock(return_value=deepcopy(CANONICAL_PAYLOAD))
    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.02), \
            patch.object(summary_pipeline, "time", _shifted_clock(shift)), \
            patch.object(summary_pipeline, "generate_xbrl_summary", fallback):
        summarize.side_effect = hang_until_cancelled
        events = await _drain(filing_id)

    warnings = [m for level, m in _pipeline_logs(caplog) if level == logging.WARNING]
    assert len(warnings) == 1, warnings
    assert re.fullmatch(AI_TIMEOUT_WARNING.format(filing_id=filing_id), warnings[0]), warnings[0]
    assert provider["cancelled"] is True
    assert fallback.call_args_list == [call(**_fallback_kwargs(filing_id))]
    assert _summarizing(events) == [STEP_FIVE]
    _assert_completed_and_persisted(events, filing_id)


# ----------------------------------------------------- D2: section previews (STREAM_SECTION_REVEAL)

@pytest.mark.asyncio
async def test_section_reveal_coalesces_queued_previews_into_the_next_heartbeat_turn(caplog):
    """With the flag on, ``summarize_filing`` receives an async ``stream_cb``; two previews queued
    before a heartbeat turn surface as ONE ``preview`` event carrying only the latest markdown (in
    place of that turn's heartbeat), and the following turn is a plain heartbeat whose counter kept
    advancing (count 1, 52%, the second rotating message)."""
    filing_id = seed_company_filing()
    preview_seen, heartbeat_after_preview = asyncio.Event(), asyncio.Event()

    async def stream_two_previews(*args, **kwargs):
        stream_cb = kwargs["stream_cb"]
        assert stream_cb is not None
        await stream_cb("# p1")
        await stream_cb("# p2")
        await preview_seen.wait()
        await heartbeat_after_preview.wait()
        return deepcopy(CANONICAL_PAYLOAD)

    def choreograph(event: dict) -> None:
        if event["type"] == "preview":
            preview_seen.set()
        elif preview_seen.is_set() and _is_heartbeat(event):
            heartbeat_after_preview.set()

    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline.settings, "STREAM_SECTION_REVEAL", True), \
            patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.02):
        summarize.side_effect = stream_two_previews
        events = await _drain(filing_id, on_event=choreograph)

    assert summarize.await_args.kwargs["stream_cb"] is not None
    assert _summarizing(events) == [
        STEP_FIVE,
        {"type": "preview", "stage": "summarizing", "markdown": "# p2", "heartbeat_count": 0, "percent": 50},
        _heartbeat(1),
    ]
    _assert_completed_and_persisted(events, filing_id)


@pytest.mark.asyncio
async def test_section_reveal_off_passes_no_stream_cb_and_emits_only_heartbeats():
    """With the flag off (the default), ``summarize_filing`` receives ``stream_cb=None`` and the
    heartbeat loop never yields a ``preview`` event — only the plain heartbeat."""
    filing_id = seed_company_filing()
    first_heartbeat = asyncio.Event()

    async def wait_for_one_heartbeat(*args, **kwargs):
        assert kwargs["stream_cb"] is None
        await first_heartbeat.wait()
        return deepcopy(CANONICAL_PAYLOAD)

    def release_on_heartbeat(event: dict) -> None:
        if _is_heartbeat(event):
            first_heartbeat.set()

    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline.settings, "STREAM_SECTION_REVEAL", False), \
            patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.02):
        summarize.side_effect = wait_for_one_heartbeat
        events = await _drain(filing_id, on_event=release_on_heartbeat)

    assert summarize.await_args.kwargs["stream_cb"] is None
    assert [e for e in events if e["type"] == "preview"] == []
    assert _summarizing(events) == [STEP_FIVE, _heartbeat(0)]
    _assert_completed_and_persisted(events, filing_id)


# --------------------------------------------- D3: provider task cancelled by someone else

@pytest.mark.asyncio
async def test_provider_task_cancelled_from_outside_falls_back_silently_and_completes(caplog):
    """A provider task that ends cancelled while the pipeline itself is NOT being cancelled is
    treated as a provider failure: the XBRL fallback is called once with the full filing context,
    nothing is logged at WARNING or above, and the stream completes with a persisted Summary."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()

    async def cancel_self(*args, **kwargs):
        asyncio.current_task().cancel()
        await asyncio.sleep(0)  # the cancellation lands here; the task finishes cancelled

    fallback = MagicMock(return_value=deepcopy(CANONICAL_PAYLOAD))
    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline, "generate_xbrl_summary", fallback):
        summarize.side_effect = cancel_self
        events = await _drain(filing_id)

    summarize.assert_awaited_once()
    assert fallback.call_args_list == [call(**_fallback_kwargs(filing_id))]
    assert [m for level, m in _pipeline_logs(caplog) if level >= logging.WARNING] == []
    assert [e for e in events if e["type"] == "error"] == []
    assert _summarizing(events) == [STEP_FIVE]
    _assert_completed_and_persisted(events, filing_id)


# ------------------------------------ D4: record_progress failure on the error-payload path

@pytest.mark.asyncio
async def test_record_progress_failure_on_the_error_payload_path_is_logged_and_the_error_streams(caplog):
    """When the provider returns an error payload and the ``error`` progress write itself raises,
    the failure is logged at ERROR with a traceback and swallowed: the stream still ends with the
    provider's message as its only terminal, no Summary row is written, the progress row stays at
    ``summarizing`` with no error, and the slot and leadership are released."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    real_record_progress = summary_pipeline.record_progress

    def fail_on_error_stage(session, filing_id_, stage, **kwargs):
        if stage == "error":
            raise RuntimeError("db down")
        return real_record_progress(session, filing_id_, stage, **kwargs)

    record_progress = MagicMock(side_effect=fail_on_error_stage)
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    with stream_boundaries(payload={"status": "error", "message": "boom"}), \
            patch.object(summary_pipeline, "record_progress", record_progress):
        events = await _drain(filing_id)

    error_records = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.ERROR]
    assert [r.getMessage() for r in error_records] == [
        f"[stream:{filing_id}] Failed to record AI error progress: db down"
    ]
    assert error_records[0].exc_info is not None and error_records[0].exc_info[0] is RuntimeError
    assert events[-1] == {"type": "error", "message": "boom"}
    assert _terminals(events) == [events[-1]]
    assert [e for e in events if e["type"] == "chunk"] == []
    assert [c.args[2] for c in record_progress.call_args_list] == [
        "fetching", "parsing", "analyzing", "summarizing", "error",
    ]
    assert record_progress.call_args_list[-1] == call(ANY, filing_id, "error", error="boom")
    assert _progress_row(filing_id) == ("summarizing", None)
    assert _summary_rows(filing_id) == []
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------------- D5: summarizing heartbeat shape

@pytest.mark.asyncio
async def test_summarizing_heartbeats_rotate_messages_and_climb_two_percent_per_beat():
    """While the provider runs, each heartbeat interval yields a summarizing progress event with the
    next rotating message, a zero-based ``heartbeat_count`` and a percent of 50 + 2 per beat (plus an
    integer ``elapsed_seconds``); the provider result then ends the loop and the stream completes."""
    filing_id = seed_company_filing()
    third_heartbeat = asyncio.Event()
    heartbeats_seen = 0

    async def wait_for_three_heartbeats(*args, **kwargs):
        await third_heartbeat.wait()
        return deepcopy(CANONICAL_PAYLOAD)

    def release_after_three(event: dict) -> None:
        nonlocal heartbeats_seen
        if _is_heartbeat(event):
            heartbeats_seen += 1
            if heartbeats_seen == 3:
                third_heartbeat.set()

    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.02):
        summarize.side_effect = wait_for_three_heartbeats
        events = await _drain(filing_id, on_event=release_after_three)

    assert _summarizing(events) == [STEP_FIVE, _heartbeat(0), _heartbeat(1), _heartbeat(2)]
    _assert_completed_and_persisted(events, filing_id)
