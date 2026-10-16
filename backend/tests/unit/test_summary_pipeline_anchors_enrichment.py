"""Pre-refactor characterization anchor for ``stream_filing_summary`` — the enrichment group.

These tests PIN how the orchestrator runs and joins its enrichment (the XBRL fetch + facts upsert,
concurrent with the document fetch; the section parse of the fetched document; the excerpt build)
into the provider call, so the decomposition into stage modules proved ZERO observable change. The
section parse moved after the document fetch in E28 (it now reads the fetched HTML, with no SEC
request); B2 and B4 pin the new call.
Every assertion is on an observable: yielded event dicts, DB rows, mock call lists, the
``record_progress`` sequence, the in-flight registry, the generation semaphore and the exact log
text the code formats.
"""
import asyncio
import inspect
import logging
import time
from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Filing, FilingContentCache, Summary
from app.services import facts_service, summary_generation_service, summary_pipeline
from app.utils.datetimes import utcnow
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

LOGGER = "app.services.summary_pipeline"
DOC_TEXT = "ENRICHMENT FILING TEXT " * 40
# Filing-instance series shape (the integration enrichment test's), as ``get_xbrl_data`` returns it.
XBRL = {
    "revenue": [{"value": 996347000000, "period": "2025-12-31", "period_start": "2025-01-01",
                 "currency": "USD", "form": "10-K", "raw_tag": "us-gaap:Revenues"}],
    "reporting_currency": "USD",
}
SECTIONS = {"item_1a": "Risk text", "item_7": "MD&A text"}
FETCHED = {"type": "progress", "stage": "fetching", "message": "File validated and fetched successfully", "percent": 15}
STARTING_PARSING = {"type": "progress", "stage": "parsing", "message": "Starting parsing...", "percent": 15}
STEP_5 = {"type": "progress", "stage": "summarizing", "message": "Step 5: Generating investor-focused summary...", "percent": 50}


@pytest.fixture(autouse=True)
def _tables_and_registry():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


async def _drain(filing_id: int) -> list[dict]:
    """Headless drain shape (the background/cron path)."""
    return [event async for event in summary_pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    )]


def _filing_fields(filing_id: int) -> tuple[str, str, str]:
    with SessionLocal() as db:
        filing = db.get(Filing, filing_id)
        return filing.accession_number, filing.company.cik, filing.document_url


def _pipeline_logs(caplog) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == LOGGER]


def _progress_stages(record_progress: MagicMock) -> list[tuple[int, str, dict]]:
    """``(filing_id, stage, kwargs)`` per ``record_progress`` call; the first arg is always a session."""
    assert all(isinstance(c.args[0], Session) for c in record_progress.call_args_list)
    return [(c.args[1], c.args[2], c.kwargs) for c in record_progress.call_args_list]


def _assert_complete(events: list[dict]) -> int:
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    return events[-1]["summary_id"]


# ------------------------------------------------------- B1: facts upsert failure inside update_xbrl_sync

@pytest.mark.asyncio
async def test_facts_upsert_failure_is_non_fatal_after_the_xbrl_commit(caplog):
    """A failing ``process_filing_facts`` is swallowed INSIDE ``update_xbrl_sync``: the stream
    completes, ``Filing.xbrl_data`` (committed just before the facts call) stays persisted, the
    ONLY warning is the exc_info-carrying facts line (never the outer persistence/XBRL warnings),
    and the provider still receives the freshly extracted metrics."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing(filing_type="10-K")
    expected_metrics = summary_pipeline.xbrl_service.extract_standardized_metrics(deepcopy(XBRL))
    facts = MagicMock(side_effect=RuntimeError("facts down"))
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=deepcopy(XBRL))), \
            patch.object(facts_service, "process_filing_facts", facts):
        events = await _drain(filing_id)

    summary_id = _assert_complete(events)
    facts.assert_called_once()
    session_arg, filing_arg = facts.call_args.args
    assert isinstance(session_arg, Session)
    assert sa_inspect(filing_arg).identity == (filing_id,)
    assert facts.call_args.kwargs == {"standardized": expected_metrics}
    summarize.assert_awaited_once()
    assert summarize.await_args.kwargs["xbrl_metrics"] == expected_metrics
    with SessionLocal() as db:
        assert db.get(Filing, filing_id).xbrl_data == XBRL
        assert db.query(Summary).filter_by(filing_id=filing_id).one().id == summary_id
    warnings = [r for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]
    assert [r.getMessage() for r in warnings] == [f"[stream:{filing_id}] facts upsert failed (non-fatal)"]
    assert warnings[0].exc_info[0] is RuntimeError
    assert str(warnings[0].exc_info[1]) == "facts down"
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# --------------------------------------------------------------------- B2: edgartools section parse fails

@pytest.mark.asyncio
async def test_section_parse_failure_warns_and_builds_the_excerpt_without_sections(caplog):
    """A raising ``get_filing_sections`` is contained in ``parse_sections``: the exact WARNING is
    logged, the excerpt builder runs on the fetched document with ``sections=None`` (the regex
    fallback), and the stream still completes."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    accession, _, _ = _filing_fields(filing_id)
    sections = AsyncMock(side_effect=RuntimeError("edgartools down"))
    excerpt = MagicMock(return_value="EXCERPT")
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", True), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=DOC_TEXT)), \
            patch.object(summary_pipeline.xbrl_service, "get_filing_sections", sections), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt):
        events = await _drain(filing_id)

    _assert_complete(events)
    assert (logging.WARNING, f"[stream:{filing_id}] Section parse failed: edgartools down") in _pipeline_logs(caplog)
    sections.assert_awaited_once_with(accession, "10-K", html=DOC_TEXT)
    excerpt.assert_called_once()
    assert isinstance(excerpt.call_args.args[0], Session)
    assert sa_inspect(excerpt.call_args.args[1]).identity == (filing_id,)
    assert excerpt.call_args.args[2] == DOC_TEXT
    assert excerpt.call_args.kwargs == {"sections": None}
    assert summarize.await_args.kwargs["filing_excerpt"] == "EXCERPT"
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------- B3: legacy aggregate-only section_coverage {} (arc 1149->1157)

@pytest.mark.asyncio
async def test_empty_legacy_section_coverage_skips_the_coverage_progress_write():
    """An aggregate-only ``section_coverage`` of ``{}`` survives the finalizer unchanged (legacy
    shape) and is falsy, so NO ``record_progress`` call carries ``section_coverage`` — the stage
    sequence is the five bare stages — while the stored row keeps ``{}`` and the stream completes."""
    filing_id = seed_company_filing()
    payload = {**deepcopy(CANONICAL_PAYLOAD), "raw_summary": {
        "sections": {"business_overview": "Acme Corp designs and sells widgets."}, "section_coverage": {},
    }}
    record_progress = MagicMock()
    with stream_boundaries(payload=payload), patch.object(summary_pipeline, "record_progress", record_progress):
        events = await _drain(filing_id)

    summary_id = _assert_complete(events)
    assert _progress_stages(record_progress) == [
        (filing_id, "fetching", {}), (filing_id, "parsing", {}), (filing_id, "analyzing", {}),
        (filing_id, "summarizing", {}), (filing_id, "completed", {}),
    ]
    with SessionLocal() as db:
        row = db.query(Summary).filter_by(filing_id=filing_id).one()
        assert row.id == summary_id
        assert row.raw_summary["section_coverage"] == {}
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------- B4: edgartools sections flow into extract_excerpt_sync

@pytest.mark.asyncio
async def test_edgartools_sections_reach_the_excerpt_builder_inside_extract_excerpt_sync():
    """Sections parsed from the fetched document are handed to ``get_or_cache_excerpt`` as
    ``sections=`` from the thread-pool unit named ``extract_excerpt_sync`` (dispatched through
    ``run_in_threadpool`` exactly once)."""
    filing_id = seed_company_filing()
    accession, _, _ = _filing_fields(filing_id)
    threadpool_names: list[str] = []
    original_run = summary_pipeline.run_in_threadpool

    async def recording_run(func, *args, **kwargs):
        threadpool_names.append(func.__name__)
        return await original_run(func, *args, **kwargs)

    excerpt_calls: list[tuple[str, dict | None]] = []

    def excerpt(db, filing, filing_text, sections=None):
        excerpt_calls.append((inspect.currentframe().f_back.f_code.co_name, sections))
        return "EXCERPT"

    get_sections = AsyncMock(return_value=deepcopy(SECTIONS))
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", True), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=DOC_TEXT)), \
            patch.object(summary_pipeline.xbrl_service, "get_filing_sections", get_sections), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt), \
            patch.object(summary_pipeline, "run_in_threadpool", recording_run):
        events = await _drain(filing_id)

    _assert_complete(events)
    get_sections.assert_awaited_once_with(accession, "10-K", html=DOC_TEXT)
    assert excerpt_calls == [("extract_excerpt_sync", SECTIONS)]
    assert threadpool_names.count("extract_excerpt_sync") == 1
    assert summarize.await_args.kwargs["filing_excerpt"] == "EXCERPT"
    assert filing_id not in summary_pipeline._inflight_generations


@pytest.mark.asyncio
async def test_sections_flag_off_skips_the_parse_and_builds_the_regex_excerpt():
    """With ``USE_EDGARTOOLS_SECTIONS`` off a 10-K never awaits the section parse: the excerpt builder
    runs on the fetched document with ``sections=None``."""
    filing_id = seed_company_filing()
    get_sections = AsyncMock(return_value=deepcopy(SECTIONS))
    excerpt = MagicMock(return_value="EXCERPT")
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", False), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=DOC_TEXT)), \
            patch.object(summary_pipeline.xbrl_service, "get_filing_sections", get_sections), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt):
        events = await _drain(filing_id)

    _assert_complete(events)
    get_sections.assert_not_awaited()
    excerpt.assert_called_once()
    assert excerpt.call_args.args[2] == DOC_TEXT
    assert excerpt.call_args.kwargs == {"sections": None}
    assert summarize.await_args.kwargs["filing_excerpt"] == "EXCERPT"


@pytest.mark.asyncio
async def test_a_stale_stored_excerpt_is_reused_without_a_section_parse():
    """A stored excerpt past its 24-hour window still sends generation through the document fetch,
    but the real ``get_or_cache_excerpt`` returns the stored excerpt as it is, so no section parse is
    started for it."""
    filing_id = seed_company_filing()
    stale = utcnow() - timedelta(days=2)
    with SessionLocal() as db:
        db.add(FilingContentCache(filing_id=filing_id, critical_excerpt="STORED EXCERPT",
                                  created_at=stale, updated_at=stale))
        db.commit()
    get_sections = AsyncMock(return_value=deepcopy(SECTIONS))
    fetch_document = AsyncMock(return_value=DOC_TEXT)
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", True), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_document), \
            patch.object(summary_pipeline.xbrl_service, "get_filing_sections", get_sections), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", summary_generation_service.get_or_cache_excerpt):
        events = await _drain(filing_id)

    _assert_complete(events)
    fetch_document.assert_awaited_once()
    get_sections.assert_not_awaited()
    assert summarize.await_args.kwargs["filing_excerpt"] == "STORED EXCERPT"


async def _never_done(record=None):
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        if record is not None:
            record.append("parse cancelled")
        raise


def _slow_excerpt(seconds, value="EXCERPT"):
    """A ``get_or_cache_excerpt`` stand-in whose build takes ``seconds`` in its worker thread."""
    def build(*_args, **_kwargs):
        time.sleep(seconds)
        return value
    return MagicMock(side_effect=build)


@pytest.mark.asyncio
async def test_the_join_after_the_section_parse_is_a_fresh_one():
    """The excerpt waits for the section parse before the join, as before E28, and the join that
    follows is the full ``CONTEXT_ENRICHMENT_TIMEOUT_SECONDS``: a slow parse takes nothing from XBRL's
    wait or from the excerpt build. The parse here outlasts the join's whole budget, so a parse
    awaited inside the join (the excerpt task waiting on it) would cancel the excerpt and fail."""
    filing_id = seed_company_filing()
    joins = []
    real_wait_for = asyncio.wait_for

    async def spy(aw, timeout=None):
        if isinstance(aw, asyncio.Future) and not isinstance(aw, asyncio.Task):  # the join's gather
            joins.append(timeout)
        return await real_wait_for(aw, timeout)

    async def slow_parse(*_args, **_kwargs):
        await asyncio.sleep(0.6)
        return deepcopy(SECTIONS)

    excerpt = MagicMock(return_value="EXCERPT")
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", True), \
            patch.object(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", 0.3), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", AsyncMock(return_value=DOC_TEXT)), \
            patch.object(summary_pipeline.xbrl_service, "get_filing_sections", slow_parse), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt), \
            patch.object(asyncio, "wait_for", spy):
        events = await real_wait_for(_drain(filing_id), 10)

    _assert_complete(events)
    assert joins == [0.3]
    assert excerpt.call_args.kwargs == {"sections": SECTIONS}
    assert summarize.await_args.kwargs["filing_excerpt"] == "EXCERPT"


@pytest.mark.asyncio
async def test_an_excerpt_the_join_drops_is_logged_and_a_slow_xbrl_alone_is_not(caplog):
    """When the join's deadline cancels the excerpt build itself, the stream says so and the provider
    gets no excerpt (the AI layer extracts its own). When only XBRL is slow, the excerpt arrives and
    nothing is logged about it."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    dropped, slow_xbrl = seed_company_filing(), seed_company_filing()
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", 0.05), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", _slow_excerpt(0.5)):
        await asyncio.wait_for(_drain(dropped), 10)
        dropped_excerpt = summarize.await_args.kwargs["filing_excerpt"]
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", 0.2), \
            patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", lambda *_a, **_k: _never_done()):
        await asyncio.wait_for(_drain(slow_xbrl), 10)
        slow_xbrl_excerpt = summarize.await_args.kwargs["filing_excerpt"]

    assert dropped_excerpt is None and slow_xbrl_excerpt == "EXCERPT"
    drop_lines = [m for _, m in _pipeline_logs(caplog) if "Excerpt not built by the enrichment join" in m]
    assert drop_lines == [f"[stream:{dropped}] Excerpt not built by the enrichment join; the AI layer extracts its own"]


# ------------------------------------------------------------ B5: a non-XBRL form (8-K) skips enrichment

@pytest.mark.asyncio
async def test_non_xbrl_form_skips_xbrl_and_sections_and_uses_the_sec_document_path():
    """An 8-K never awaits the XBRL fetch or the section parse (even with edgartools on), fetches the
    primary document through the SEC path, and the provider gets exactly the document text with
    ``xbrl_metrics=None`` and the regex excerpt."""
    filing_id = seed_company_filing(filing_type="8-K")
    _, _, document_url = _filing_fields(filing_id)
    get_xbrl_data = AsyncMock(return_value=deepcopy(XBRL))
    get_sections = AsyncMock(return_value=deepcopy(SECTIONS))
    fetch_document = AsyncMock(return_value=DOC_TEXT)
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", True), \
            patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", get_xbrl_data), \
            patch.object(summary_pipeline.xbrl_service, "get_filing_sections", get_sections), \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_document):
        events = await _drain(filing_id)

    _assert_complete(events)
    get_xbrl_data.assert_not_awaited()
    get_sections.assert_not_awaited()
    fetch_document.assert_awaited_once_with(document_url, timeout=15.0)
    assert FETCHED in events
    assert not any(e.get("message") == "Retrieving 6-K exhibits from EDGAR..." for e in events)
    summarize.assert_awaited_once()
    assert summarize.await_args.args == (DOC_TEXT, "Harness Co", "8-K")
    assert summarize.await_args.kwargs == {"xbrl_metrics": None, "filing_excerpt": "EXCERPT", "stream_cb": None}
    with SessionLocal() as db:
        assert db.get(Filing, filing_id).xbrl_data is None
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------- B6: the enrichment join's progress + record_progress sequence

@pytest.mark.asyncio
async def test_enrichment_join_progress_events_and_record_progress_stages_for_a_canonical_run():
    """Between 'Starting parsing...' and 'Step 5' a canonical run yields exactly six fixed progress
    dicts (no heartbeats, no elapsed_seconds), and ``record_progress`` sees the six stages in order,
    the fifth repeating 'summarizing' with the payload's aggregate-only coverage snapshot."""
    filing_id = seed_company_filing()
    record_progress = MagicMock()
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)), \
            patch.object(summary_pipeline, "record_progress", record_progress):
        events = await _drain(filing_id)

    _assert_complete(events)
    start, end = events.index(STARTING_PARSING), events.index(STEP_5)
    assert events[start:end + 1] == [
        STARTING_PARSING,
        {"type": "progress", "stage": "parsing", "percent": 20,
         "message": "Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)..."},
        {"type": "progress", "stage": "parsing", "message": "Parsing complete...", "percent": 25},
        {"type": "progress", "stage": "analyzing", "message": "Step 3: Content Analysis - Analyzing risk factors...", "percent": 35},
        {"type": "progress", "stage": "analyzing", "message": "Step 4: Generating financial overview...", "percent": 45},
        STEP_5,
    ]
    assert events[start - 1] == FETCHED
    assert _progress_stages(record_progress) == [
        (filing_id, "fetching", {}), (filing_id, "parsing", {}), (filing_id, "analyzing", {}),
        (filing_id, "summarizing", {}),
        (filing_id, "summarizing", {"section_coverage": {"covered_count": 5, "total_count": 7}}),
        (filing_id, "completed", {}),
    ]
    assert filing_id not in summary_pipeline._inflight_generations
