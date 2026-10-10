"""Pre-refactor characterization anchor for ``stream_filing_summary`` — the admission group.

These tests PIN the orchestrator's behaviour on its admission branches (filing lookup, the stored
summary short-circuit, the NULL-timestamp content-cache fallback, the quota / fair-use block, and
the late-claim fresh re-read of the dedup loop) exactly as it runs today, so the upcoming
decomposition into stage modules can prove ZERO observable change. Every assertion is on an
observable: yielded event dicts, DB rows, mock call lists, the in-flight registry, the generation
semaphore, and the exact log text the code formats.
"""
import asyncio
import logging
import uuid
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import uuid4

import pytest

from app.database import SessionLocal, engine
from app.models import Base, FilingContentCache, Summary, User
from app.services import summary_pipeline
from app.services.summary_pipeline import (
    EVENT_GENERATION_STARTED,
    EVENT_PAYWALL_HIT,
    GenerationUserSnapshot,
)
from app.services.summary_request_evidence import SummaryRequestEvidence
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

LOGGER = "app.services.summary_pipeline"
INITIALIZING = {"type": "progress", "stage": "initializing", "message": "Initializing...", "percent": 0}
MISSING_FILING_ID = 2_000_000_000


@pytest.fixture(autouse=True)
def _tables_and_registry():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


def _evidence(filing_id: int) -> SummaryRequestEvidence:
    return SummaryRequestEvidence(
        consent=True, account_id=17, filing_id=filing_id, logical_request_id=uuid4(),
        client_attempt=1, transport_attempt=1, entry_point=None,
    )


def _seed_user() -> int:
    with SessionLocal() as db:
        user = User(email=f"adm-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        db.commit()
        return user.id


async def _drain(filing_id: int, **overrides) -> list[dict]:
    """Headless drain shape (the background/cron path); ``overrides`` reach the generator."""
    kwargs = dict(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    )
    kwargs.update(overrides)
    return [event async for event in summary_pipeline.stream_filing_summary(**kwargs)]


def _pipeline_logs(caplog) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == LOGGER]


# --------------------------------------------------------------------------- A1: filing not found

@pytest.mark.asyncio
async def test_unknown_filing_yields_only_initializing_and_not_found_error(caplog):
    """A filing id with no row ends the stream after exactly two events, logs the WARNING, marks
    the evidence reason, never reaches the provider and leaves no in-flight slot behind."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    evidence = _evidence(MISSING_FILING_ID)
    with stream_boundaries() as summarize:
        events = await _drain(MISSING_FILING_ID, request_evidence=evidence)
    assert events == [INITIALIZING, {"type": "error", "message": "Filing not found"}]
    assert (logging.WARNING, f"[stream:{MISSING_FILING_ID}] Filing not found during stream generation.") in _pipeline_logs(caplog)
    assert evidence.reason == "filing_not_found"
    assert evidence.summary_service_invoked is False
    summarize.assert_not_called()
    assert MISSING_FILING_ID not in summary_pipeline._inflight_generations


# ------------------------------------------------------- A2: stored summary served without evidence

@pytest.mark.asyncio
async def test_stored_summary_is_served_as_the_second_and_last_event(caplog):
    """An existing Summary row short-circuits the pipeline: the complete event carries exactly
    ``summary`` + ``summary_id`` (no ``percent``), no stage is recorded and nothing is fetched."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        stored = Summary(filing_id=filing_id, business_overview="STORED")
        db.add(stored)
        db.commit()
        stored_id = stored.id
    record_progress = MagicMock()
    with stream_boundaries() as summarize, patch.object(summary_pipeline, "record_progress", record_progress):
        events = await _drain(filing_id)
    assert events == [INITIALIZING, {"type": "complete", "summary": "STORED", "summary_id": stored_id}]
    assert (logging.INFO, f"[stream:{filing_id}] Existing summary found. Returning it.") in _pipeline_logs(caplog)
    summarize.assert_not_called()
    record_progress.assert_not_called()
    assert filing_id not in summary_pipeline._inflight_generations


@pytest.mark.asyncio
async def test_force_regenerate_bypasses_the_stored_summary_and_updates_the_row_in_place():
    """``force_regenerate=True`` skips the short-circuit: the provider runs exactly once and the
    existing row keeps its id (bookmark FK) while its markdown is rewritten — never a second row."""
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        stored = Summary(filing_id=filing_id, business_overview="STORED")
        db.add(stored)
        db.commit()
        stored_id = stored.id
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize:
        events = await _drain(filing_id, force_regenerate=True)
    summarize.assert_awaited_once()
    assert events[-1] == {"type": "complete", "summary_id": stored_id, "percent": 100}
    chunk = next(e for e in events if e["type"] == "chunk")
    with SessionLocal() as db:
        rows = db.query(Summary).filter(Summary.filing_id == filing_id).all()
        assert [row.id for row in rows] == [stored_id]
        assert rows[0].business_overview == chunk["content"]
        assert rows[0].business_overview != "STORED"
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------- A3: content cache whose timestamps are both NULL

@pytest.mark.asyncio
async def test_content_cache_with_null_timestamps_is_treated_as_fresh(caplog):
    """A cached excerpt with NULL created_at/updated_at is dated "now" and served as a valid cache:
    the SEC fetch and excerpt extraction are skipped and the provider gets the excerpt with an
    empty filing text."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        db.add(FilingContentCache(filing_id=filing_id, critical_excerpt="CACHED EXCERPT"))
        db.commit()
        # The insert applies the server default; NULL both timestamps explicitly and prove it landed.
        db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).update(
            {"created_at": None, "updated_at": None}
        )
        db.commit()
    with SessionLocal() as db:
        cache = db.get(FilingContentCache, filing_id)
        assert (cache.critical_excerpt, cache.created_at, cache.updated_at) == ("CACHED EXCERPT", None, None)

    fetch_document = AsyncMock()
    get_or_cache_excerpt = MagicMock()
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", fetch_document), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", get_or_cache_excerpt):
        events = await _drain(filing_id)

    cached_event = {"type": "progress", "stage": "fetching", "message": "Cached content found. Loading immediately...", "percent": 15}
    assert cached_event in events
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    assert not any(e.get("message") == "File validated and fetched successfully" for e in events)
    fetch_document.assert_not_awaited()
    get_or_cache_excerpt.assert_not_called()
    summarize.assert_awaited_once()
    assert summarize.await_args.args[0] == ""
    assert summarize.await_args.kwargs["filing_excerpt"] == "CACHED EXCERPT"
    cache_logs = [m for lvl, m in _pipeline_logs(caplog) if lvl == logging.INFO and "Using cached content (age:" in m]
    assert len(cache_logs) == 1 and cache_logs[0].startswith(f"[stream:{filing_id}] Using cached content (age: ")


# ----------------------------------------- A4: quota block without evidence (+ the fair-use twin)

QUOTA_MESSAGE = "You've reached your monthly limit of 5 summaries. Upgrade to Pro for unlimited summaries."
FAIR_USE_MESSAGE = (
    "We've temporarily paused new summary generation on your account due "
    "to unusually high recent volume. Please try again later or contact support."
)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["monthly_quota", "fair_use"])
async def test_usage_block_yields_error_logs_and_funnel_without_touching_a_slot(caplog, mode):
    """A blocked Free user gets the upsell message + a paywall funnel event; a blocked Pro user
    (fair-use ceiling) gets the generic pause message and NO paywall event. Neither reaches the
    provider, holds a generation slot or leaves an in-flight entry."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    user_id, filing_id = _seed_user(), seed_company_filing()
    verdict = (False, 5, 5, False, None) if mode == "monthly_quota" else (False, 50, 50, True, None)
    capture = MagicMock()
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    with stream_boundaries() as summarize, \
            patch.object(summary_pipeline, "_check_usage_and_plan", lambda *_: verdict), \
            patch.object(summary_pipeline, "capture_funnel_event", capture):
        events = await _drain(
            filing_id, current_user=GenerationUserSnapshot(user_id, False, None), user_id=user_id,
            telemetry_distinct_id=str(user_id), telemetry_entry_point="generate_button",
            telemetry_ctx={"surface": "filing_page"}, emit_funnel_telemetry=True,
        )
    started = call(str(user_id), EVENT_GENERATION_STARTED, entry_point="generate_button", surface="filing_page")
    if mode == "monthly_quota":
        assert events == [INITIALIZING, {"type": "error", "message": QUOTA_MESSAGE}]
        assert (logging.WARNING, f"[stream:{filing_id}] User {user_id} exceeded monthly summary limit (5).") in _pipeline_logs(caplog)
        assert capture.call_args_list == [
            started,
            call(str(user_id), EVENT_PAYWALL_HIT, entry_point="generate_button", limit=5, summaries_used=5),
        ]
    else:
        assert events == [INITIALIZING, {"type": "error", "message": FAIR_USE_MESSAGE}]
        assert (logging.WARNING, f"[stream:{filing_id}] Pro user {user_id} hit summary fair-use ceiling (50).") in _pipeline_logs(caplog)
        assert capture.call_args_list == [started]
    summarize.assert_not_called()
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------- A5: coalesced delivery_path on the fresh re-read after a late claim

@pytest.mark.asyncio
async def test_late_claim_fresh_reread_marks_evidence_coalesced_without_generating():
    """A follower whose obsolete empty snapshot returns after a replacement already persisted and
    released must claim, re-read on a fresh session and serve that result as ``coalesced`` — never
    generate. The hook resets ``delivery_path`` when it releases the stale snapshot, so the final
    ``"coalesced"`` can only come from the re-read under the late claim, not from the earlier join."""
    filing_id = seed_company_filing()
    leader = summary_pipeline._claim_inflight(filing_id)
    evidence = _evidence(filing_id)
    joined, delayed_read, return_delayed = asyncio.Event(), asyncio.Event(), asyncio.Event()
    joins, held = 0, False
    original_run = summary_pipeline.run_in_threadpool

    async def delay_empty_read(func, *args, **kwargs):
        nonlocal held
        result = await original_run(func, *args, **kwargs)
        if (func.__name__ == "get_persisted_summary_fields" and result is None
                and asyncio.current_task().get_name() == "delayed-follower" and not held):
            held = True
            delayed_read.set()
            await return_delayed.wait()
            evidence.delivery_path = "probe"  # the join already wrote "coalesced"; only the re-read may restore it
        elif func.__name__ == "get_persisted_summary_fields" and result is None:
            # The replacement cannot persist before the delayed follower has its empty snapshot.
            await delayed_read.wait()
        return result

    async def consume(**overrides):
        nonlocal joins
        frames = []
        async for frame in summary_pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False, **overrides,
        ):
            frames.append(frame)
            if frame.get("stage") == "queued":
                joins += 1
                if joins == 2:
                    joined.set()
        return frames

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as generate, \
            patch.object(summary_pipeline, "run_in_threadpool", delay_empty_read):
        delayed = asyncio.create_task(consume(request_evidence=evidence), name="delayed-follower")
        replacement = asyncio.create_task(consume(), name="replacement-follower")
        try:
            await asyncio.wait_for(joined.wait(), 2)
            summary_pipeline._release_inflight(filing_id, leader)  # the leader failed without persisting
            await asyncio.wait_for(delayed_read.wait(), 2)
            completed = await asyncio.wait_for(replacement, 2)
            assert filing_id not in summary_pipeline._inflight_generations
            generate.assert_awaited_once()
            return_delayed.set()  # now return the obsolete empty snapshot
            resumed = await asyncio.wait_for(delayed, 2)
        finally:
            return_delayed.set()
            for task in (delayed, replacement):
                task.cancel()
            await asyncio.gather(delayed, replacement, return_exceptions=True)

    assert held  # the stale snapshot was held and the probe reset ran before the follower resumed
    generate.assert_awaited_once()  # the replacement generated; the delayed follower never did
    assert evidence.delivery_path == "coalesced"
    assert evidence.summary_service_invoked is False
    summary_id = next(f["summary_id"] for f in completed if f["type"] == "complete")
    assert [f["type"] for f in resumed] == ["progress", "progress", "complete"]
    assert resumed[1]["stage"] == "queued"
    assert resumed[1]["message"] == "Another request is already generating this analysis — joining it..."
    assert resumed[-1] == {"type": "complete", "summary": resumed[-1]["summary"], "summary_id": summary_id}
    assert filing_id not in summary_pipeline._inflight_generations
