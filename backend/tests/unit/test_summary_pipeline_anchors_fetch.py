"""Pre-refactor characterization anchor for ``stream_filing_summary`` — the fetch group.

These tests PIN the orchestrator's behaviour on its document-fetch branches (the SEC fetch
heartbeat loop, the empty-document failure, and the 6-K exhibit/cover-page grounding path with its
extractor-failure, no-text and success outcomes) exactly as it runs today, so the upcoming
decomposition into stage modules can prove ZERO observable change. Every assertion is on an
observable: yielded event dicts, DB rows, mock call lists, the in-flight registry, the generation
semaphore, and the exact log text the code formats.
"""
import asyncio
import logging
from copy import deepcopy
from typing import Callable, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary
from app.services import summary_pipeline
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

LOGGER = "app.services.summary_pipeline"
INITIALIZING = {"type": "progress", "stage": "initializing", "message": "Initializing...", "percent": 0}
STEP_ONE = {
    "type": "progress", "stage": "fetching",
    "message": "Step 1: File Validation - Confirming document is accessible and parsable...", "percent": 5,
}
FETCHED_OK = {"type": "progress", "stage": "fetching", "message": "File validated and fetched successfully", "percent": 15}
SIXK_RETRIEVING = {"type": "progress", "stage": "fetching", "message": "Retrieving 6-K exhibits from EDGAR...", "percent": 10}
SIXK_FETCHED = {"type": "progress", "stage": "fetching", "message": "6-K exhibits fetched", "percent": 15}
SEC_FETCH_ERROR = {"type": "error", "message": "Unable to retrieve this filing at the moment — please try again shortly."}
SIXK_FETCH_ERROR = {"type": "error", "message": "Unable to retrieve this 6-K at the moment — please try again shortly."}
FETCH_MESSAGES = [
    "Connecting to SEC EDGAR...",
    "Downloading filing document...",
    "Retrieving full document text...",
    "Processing SEC response...",
]
DOCUMENT_TEXT = "FILING DOCUMENT TEXT " * 40


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


def _fetching(events: list[dict]) -> list[dict]:
    return _without_elapsed([e for e in events if e.get("stage") == "fetching"])


def _terminals(events: list[dict]) -> list[dict]:
    return [e for e in events if e["type"] in {"complete", "partial", "error"}]


def _stages(record_progress: MagicMock) -> list[str]:
    """``record_progress(session, filing_id, stage, ...)`` — the stage is the third positional."""
    return [c.args[2] for c in record_progress.call_args_list]


def _filing_identity(filing_id: int) -> tuple[str, str, str]:
    with SessionLocal() as db:
        filing = db.get(Filing, filing_id)
        return filing.document_url, filing.accession_number, filing.company.cik


def _summary_rows(filing_id: int) -> list[int]:
    with SessionLocal() as db:
        return [row.id for row in db.query(Summary).filter(Summary.filing_id == filing_id).all()]


# ----------------------------------------------------------------- C1: SEC fetch heartbeat loop

@pytest.mark.asyncio
async def test_sec_fetch_heartbeats_rotate_messages_and_cap_percent_at_15(caplog):
    """While the SEC fetch runs, every heartbeat interval yields a fetching progress event whose
    message rotates through the four FETCH_MESSAGES and whose percent climbs 5 → 15 (one point per
    beat, capped), each logged at INFO numbered from 1; the fetch result then yields the 15% success
    event and the stream completes."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    release = asyncio.Event()
    heartbeats_seen = 0

    async def fetch_until_released(url: str, timeout: float) -> str:
        await release.wait()
        return DOCUMENT_TEXT

    def release_after_twelve_heartbeats(event: dict) -> None:
        nonlocal heartbeats_seen
        if event.get("stage") == "fetching" and event.get("message") in FETCH_MESSAGES:
            heartbeats_seen += 1
            if heartbeats_seen == 12:
                release.set()

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.02), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_until_released):
        events = await _drain(filing_id, on_event=release_after_twelve_heartbeats)

    expected_heartbeats = [
        {"type": "progress", "stage": "fetching", "message": message, "percent": percent}
        for message, percent in zip(FETCH_MESSAGES * 3, [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15])
    ]
    assert _fetching(events) == [STEP_ONE, *expected_heartbeats, FETCHED_OK]
    heartbeat_logs = [m for level, m in _pipeline_logs(caplog) if level == logging.INFO and "SEC fetch heartbeat" in m]
    assert heartbeat_logs == [
        f"[stream:{filing_id}] SEC fetch heartbeat {n}: {message}"
        for n, message in enumerate(FETCH_MESSAGES * 3, start=1)
    ]
    assert (logging.INFO, f"[stream:{filing_id}] SEC fetch completed. Text length: {len(DOCUMENT_TEXT)}") in _pipeline_logs(caplog)
    summarize.assert_awaited_once()
    assert summarize.await_args.args[0] == DOCUMENT_TEXT
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    assert _terminals(events) == [events[-1]]
    assert _summary_rows(filing_id) == [events[-1]["summary_id"]]
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------------------------ C2: empty SEC document

@pytest.mark.asyncio
async def test_empty_sec_document_ends_the_stream_with_the_retrieval_error(caplog):
    """An empty fetch result is a fetch failure: the stream ends with the generic retrieval error
    as its only terminal (no parsing stage, no provider call, no Summary row, no ``error`` progress
    record), logs the ValueError text at ERROR with a traceback, and gives back the generation slot
    and in-flight leadership."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    record_progress = MagicMock(wraps=summary_pipeline.record_progress)
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value="")), \
            patch.object(summary_pipeline, "record_progress", record_progress):
        events = await _drain(filing_id)

    assert _without_elapsed(events) == [INITIALIZING, STEP_ONE, SEC_FETCH_ERROR]
    assert _terminals(events) == [events[-1]]
    error_records = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.ERROR]
    assert [r.getMessage() for r in error_records] == [
        f"[stream:{filing_id}] Error fetching SEC document: Filing document is empty or inaccessible"
    ]
    assert error_records[0].exc_info is not None and error_records[0].exc_info[0] is ValueError
    assert _stages(record_progress) == ["fetching"]
    summarize.assert_not_called()
    assert _summary_rows(filing_id) == []
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------- C3: 6-K exhibit extractor raises (fallback)

@pytest.mark.asyncio
async def test_sixk_extractor_failure_falls_back_to_the_cover_document(caplog):
    """A raising 6-K exhibit extractor is logged at WARNING and swallowed: the cover document is
    fetched once with the 15s budget and becomes the grounding text, classified by the real
    pre-classifier into the provider's ``sixk_class``/``sixk_class_audit`` kwargs; XBRL is never
    fetched for a 6-K and the stream completes."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing(filing_type="6-K")
    document_url, _, _ = _filing_identity(filing_id)
    expected = summary_pipeline.classify_sixk_text("COVER PAGE TEXT")
    fetch_document = AsyncMock(return_value="COVER PAGE TEXT")
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "get_sixk_text", AsyncMock(side_effect=RuntimeError("boom"))), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_document):
        get_xbrl_data = summary_pipeline.xbrl_service.get_xbrl_data
        events = await _drain(filing_id)

    assert (logging.WARNING, f"[stream:{filing_id}] 6-K exhibit extraction failed: boom") in _pipeline_logs(caplog)
    fetch_document.assert_awaited_once_with(document_url, timeout=15.0)
    assert _fetching(events) == [STEP_ONE, SIXK_RETRIEVING, SIXK_FETCHED]
    summarize.assert_awaited_once()
    assert summarize.await_args.args[0] == "COVER PAGE TEXT"
    assert summarize.await_args.kwargs["sixk_class"] == expected.sixk_class
    assert summarize.await_args.kwargs["sixk_class_audit"] == expected.as_audit()
    get_xbrl_data.assert_not_awaited()
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    assert _terminals(events) == [events[-1]]
    assert _summary_rows(filing_id) == [events[-1]["summary_id"]]
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------ C4 + C5: 6-K with no grounding text from either source

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extractor_result, document_result",
    [(None, RuntimeError("edgar down")), ("", "")],
    ids=["extractor_none_document_raises", "both_sources_empty"],
)
async def test_sixk_without_any_grounding_text_ends_with_the_sixk_error(extractor_result, document_result):
    """When the exhibit extractor yields nothing and the cover-document fetch raises or is empty, the
    stream ends right after the 10% event with the 6-K-specific error as its only terminal: no
    provider call, no Summary row, only the ``fetching`` progress record, slot and leadership
    released."""
    filing_id = seed_company_filing(filing_type="6-K")
    document_url, accession, cik = _filing_identity(filing_id)
    fetch_document = (
        AsyncMock(side_effect=document_result) if isinstance(document_result, Exception)
        else AsyncMock(return_value=document_result)
    )
    get_sixk_text = AsyncMock(return_value=extractor_result)
    record_progress = MagicMock(wraps=summary_pipeline.record_progress)
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline, "get_sixk_text", get_sixk_text), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_document), \
            patch.object(summary_pipeline, "record_progress", record_progress):
        events = await _drain(filing_id)

    assert _without_elapsed(events) == [INITIALIZING, STEP_ONE, SIXK_RETRIEVING, SIXK_FETCH_ERROR]
    assert _terminals(events) == [events[-1]]
    get_sixk_text.assert_awaited_once_with(accession, cik)
    fetch_document.assert_awaited_once_with(document_url, timeout=15.0)
    assert _stages(record_progress) == ["fetching"]
    summarize.assert_not_called()
    assert _summary_rows(filing_id) == []
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------------------------- C6: 6-K success path

@pytest.mark.asyncio
async def test_sixk_exhibit_text_is_classified_once_and_handed_to_the_provider():
    """Exhibit text from the extractor is the grounding: the cover document is never fetched, the
    10% then 15% fetching events are yielded, ``classify_sixk_text`` runs exactly once on that text
    and its class + audit reach ``summarize_filing`` alongside the text itself."""
    filing_id = seed_company_filing(filing_type="6-K")
    _, accession, cik = _filing_identity(filing_id)
    exhibit_text = "EXHIBIT 99.1 Press release: revenue grew."
    real_classify = summary_pipeline.classify_sixk_text
    expected = real_classify(exhibit_text)
    classify = MagicMock(wraps=real_classify)
    get_sixk_text = AsyncMock(return_value=exhibit_text)
    fetch_document = AsyncMock(return_value="COVER PAGE TEXT")
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "get_sixk_text", get_sixk_text), \
            patch.object(summary_pipeline, "classify_sixk_text", classify), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_document):
        events = await _drain(filing_id)

    assert _fetching(events) == [STEP_ONE, SIXK_RETRIEVING, SIXK_FETCHED]
    get_sixk_text.assert_awaited_once_with(accession, cik)
    fetch_document.assert_not_awaited()
    classify.assert_called_once_with(exhibit_text)
    summarize.assert_awaited_once()
    assert summarize.await_args.args[0] == exhibit_text
    assert summarize.await_args.kwargs["sixk_class"] == expected.sixk_class
    assert summarize.await_args.kwargs["sixk_class_audit"] == expected.as_audit()
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    assert _terminals(events) == [events[-1]]
    assert _summary_rows(filing_id) == [events[-1]["summary_id"]]
    assert filing_id not in summary_pipeline._inflight_generations
