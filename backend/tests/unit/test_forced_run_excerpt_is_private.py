"""A forced run keeps the excerpt it builds to itself until finalize stores it with its summary.

Codex 4365089688 on #1545: two forced precomputes of one filing that overlapped left a kept summary
beside the rejected run's excerpt, because the precompute cleared the stored excerpt before its run
and put it back afterwards, and the second run captured the first's new excerpt as "stored". These run
the real orchestrator and the real ``get_or_cache_excerpt`` (only SEC, the provider and the extraction
are faked): in one process (the second run joins the first through the in-flight registry) and in two
(each process has its own registry, so both lead), plus the Pro "Regenerate" / refresh-stale variant
(a summary stored beside no excerpt) and the commit the excerpt shares with its summary. Finalize reads
the cache row after the summary's row lock, so a save that committed while this one waited is what it
replaces. A replacing run that ends with no excerpt clears the stored one only when it was asked to rebuild it
(a forced precompute, whose stored excerpt is stale); every other forced run reused the stored excerpt as its
grounding and keeps it, as an unforced first generation does. A kept or failed run writes none.
"""
import asyncio
import threading
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import pytest

from app.services.precompute_service import precompute_one
from tests.unit.test_precompute_service import (
    FRESH_EXCERPT,
    STORED_EXCERPT,
    STORED_FULL,
    _patch_sec,
    _sec_filing,
    _seed_forced,
    _stored,
)

FRESH_B = "Item 7. MD&A excerpt the second run builds."
OTHER_SUMMARY = "# Other\n\nThe other process's replacing summary."
OTHER_EXCERPT = "Item 7. MD&A excerpt the other process's run built and stored with its summary."


def _real_builder(values):
    from app.services import summary_generation_service, summary_pipeline

    return (
        patch.object(summary_pipeline, "get_or_cache_excerpt", summary_generation_service.get_or_cache_excerpt),
        patch.object(summary_pipeline.openai_service, "extract_critical_sections", MagicMock(side_effect=values)),
    )


def test_two_overlapping_forced_precomputes_in_one_process(monkeypatch):
    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import reset_inflight, stream_boundaries

    ticker, acc, filing_id, summary_id, _ = _seed_forced()
    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def provider(*_a, **_k):
            entered.set()
            await release.wait()
            raise TimeoutError("budget exhausted")

        builder, regex = _real_builder([FRESH_EXCERPT] * 4)
        with stream_boundaries() as summarize, builder, regex:
            summarize.side_effect = provider
            first = asyncio.create_task(precompute_one(ticker, "10-K", force=True))
            await asyncio.wait_for(entered.wait(), 10)
            mid_run = _stored(filing_id)[3]
            leader = summary_pipeline._inflight_generations[filing_id]
            joined, original_wait = asyncio.Event(), leader.wait

            async def wait():
                joined.set()
                return await original_wait()

            leader.wait = wait
            second = asyncio.create_task(precompute_one(ticker, "10-K", force=True))
            await asyncio.wait_for(joined.wait(), 10)
            release.set()
            return mid_run, (await first)["status"], (await second)["status"]

    reset_inflight()
    try:
        mid_run, first, second = asyncio.run(scenario())
    finally:
        reset_inflight()
    assert (first, second) == ("kept", "kept")
    assert _stored(filing_id) == (1, summary_id, STORED_FULL, STORED_EXCERPT)
    assert mid_run == STORED_EXCERPT


@pytest.mark.parametrize("second_outcome", ["kept", "generated"])
def test_two_overlapping_forced_precomputes_in_two_processes(monkeypatch, second_outcome):
    # Each process has its own in-flight registry, so both runs lead.
    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries

    ticker, acc, filing_id, summary_id, _ = _seed_forced()
    _patch_sec(monkeypatch, filings=[_sec_filing(acc)])

    async def scenario():
        entered = [asyncio.Event(), asyncio.Event()]
        release = [asyncio.Event(), asyncio.Event()]
        calls = []

        async def provider(*_a, **_k):
            i = len(calls)
            calls.append(i)
            entered[i].set()
            await release[i].wait()
            if i == 0 or second_outcome == "kept":
                raise TimeoutError("budget exhausted")
            return {**CANONICAL_PAYLOAD, "business_overview": "# Second\n\nA fresh full analysis."}

        builder, regex = _real_builder([FRESH_EXCERPT, FRESH_B, FRESH_B, FRESH_B])
        registry = summary_pipeline._inflight_generations
        with stream_boundaries() as summarize, builder, regex:
            summarize.side_effect = provider
            first = asyncio.create_task(precompute_one(ticker, "10-K", force=True))
            await asyncio.wait_for(entered[0].wait(), 10)
            # The other process: the second run claims its slot in a registry of its own, so it leads
            # too. The swap ends once that slot is claimed, so the first run releases its slot in this
            # registry (a release reads the module's registry when it runs).
            with patch.object(summary_pipeline, "_inflight_generations", {}):
                second = asyncio.create_task(precompute_one(ticker, "10-K", force=True))
                await asyncio.wait_for(entered[1].wait(), 10)
            release[0].set()
            first_status = (await first)["status"]
            release[1].set()
            return first_status, (await second)["status"], filing_id in registry

    reset_inflight()
    try:
        first, second, slot_left = asyncio.run(scenario())
    finally:
        reset_inflight()
    assert not slot_left  # the first run released the slot it claimed here
    count, row_id, overview, excerpt = _stored(filing_id)
    assert (count, row_id) == (1, summary_id)
    if second_outcome == "kept":
        assert (first, second) == ("kept", "kept")
        assert (overview, excerpt) == (STORED_FULL, STORED_EXCERPT)
    else:
        assert (first, second) == ("kept", "generated")
        assert (overview, excerpt) == ("# Second\n\nA fresh full analysis.", FRESH_B)


def test_a_forced_run_kept_beside_no_excerpt_stores_none(monkeypatch):
    # The Pro "Regenerate" / refresh-stale variant: nothing is cleared, but no excerpt is stored either.
    from app.services.summary_generation_service import generate_summary_background
    from tests.support.summary_stream_harness import reset_inflight, stream_boundaries

    _ticker, _acc, filing_id, summary_id, _ = _seed_forced(excerpt=None)
    builder, regex = _real_builder([FRESH_EXCERPT] * 2)
    reset_inflight()
    try:
        with stream_boundaries() as summarize, builder, regex:
            summarize.side_effect = TimeoutError("budget exhausted")
            asyncio.run(generate_summary_background(filing_id, None, force_regenerate=True))
    finally:
        reset_inflight()
    assert _stored(filing_id) == (1, summary_id, STORED_FULL, None)


async def _drain_forced(filing_id, *, force_regenerate=True, **flags):
    from app.services import summary_pipeline

    events = []
    async for event in summary_pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="t",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
        force_regenerate=force_regenerate, **flags,
    ):
        events.append(event)
    return events


def test_a_forced_rebuild_parses_sections_past_a_stored_excerpt():
    from unittest.mock import AsyncMock

    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import reset_inflight, stream_boundaries

    _t, _a, filing_id, _sid, _u = _seed_forced()  # a fresh (<24 h) stored excerpt
    sections = {"risk": "Item 1A text", "mda": "Item 7 text"}
    excerpt = MagicMock(return_value=FRESH_EXCERPT)
    get_sections = AsyncMock(return_value=sections)
    reset_inflight()
    try:
        with stream_boundaries() as summarize, \
                patch.object(summary_pipeline.settings, "USE_EDGARTOOLS_SECTIONS", True), \
                patch.object(summary_pipeline.xbrl_service, "get_filing_sections", get_sections), \
                patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt):
            asyncio.run(_drain_forced(filing_id, rebuild_excerpt=True))
    finally:
        reset_inflight()
    get_sections.assert_awaited_once()
    assert excerpt.call_args.kwargs == {"sections": sections, "persist": False, "reuse_stored": False}
    assert summarize.await_args.kwargs["filing_excerpt"] == FRESH_EXCERPT


def test_a_replacing_forced_run_stores_its_excerpt_in_the_summarys_commit():
    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import reset_inflight, stream_boundaries

    _t, _a, filing_id, summary_id, _u = _seed_forced()
    real_upsert = summary_pipeline.upsert_content_cache

    def upsert_then_fail(*args, **kwargs):
        real_upsert(*args, **kwargs)
        raise RuntimeError("commit never reached")

    builder, regex = _real_builder([FRESH_EXCERPT] * 2)
    reset_inflight()
    try:
        with stream_boundaries(), builder, regex, \
                patch.object(summary_pipeline, "upsert_content_cache", upsert_then_fail):
            events = asyncio.run(_drain_forced(filing_id, rebuild_excerpt=True))
    finally:
        reset_inflight()
    assert events[-1]["type"] == "error"
    assert _stored(filing_id) == (1, summary_id, STORED_FULL, STORED_EXCERPT)


@contextmanager
def _another_save_commits_while_this_one_waits_for_the_row_lock(filing_id):
    """Another process's replacing save commits its summary and excerpt just before this run's row-locked
    Summary read. On PostgreSQL (READ COMMITTED) that read waits for the other save's commit and then
    returns its row; SQLite has no row locks, so the commit is placed at that read by hand."""
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    from app.database import SessionLocal
    from app.models import FilingContentCache, Summary

    fired = []

    def commit_the_other_save():
        with SessionLocal() as db:
            db.query(Summary).filter(Summary.filing_id == filing_id).update(
                {Summary.business_overview: OTHER_SUMMARY}, synchronize_session=False)
            cache = db.get(FilingContentCache, filing_id)
            if cache is None:
                db.add(FilingContentCache(filing_id=filing_id, critical_excerpt=OTHER_EXCERPT))
            else:
                cache.critical_excerpt = OTHER_EXCERPT
            db.commit()

    def before_the_row_lock(state):
        statement = state.statement
        if fired or not state.is_select or getattr(statement, "_for_update_arg", None) is None:
            return
        if any(d.get("entity") is Summary for d in getattr(statement, "column_descriptions", None) or []):
            fired.append(True)
            commit_the_other_save()

    event.listen(Session, "do_orm_execute", before_the_row_lock)
    try:
        yield fired
    finally:
        event.remove(Session, "do_orm_execute", before_the_row_lock)


@pytest.mark.parametrize("with_cache", [True, False], ids=["cache-row", "no-cache-row"])
def test_a_replacing_forced_run_stores_its_excerpt_over_a_save_committed_while_it_waited(with_cache):
    # Two replacing forced runs in two processes: the other's save commits while this one waits for the
    # summary's row lock. With a cache row, this run reused the stored excerpt, equal to the value a read
    # before the wait loaded, so assigning it there wrote nothing and left the other run's excerpt beside
    # this run's summary. With none, the other save created the row, which a read before the wait missed:
    # this run inserted it again and failed on its key. Finalize reads the cache row after the lock.
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries

    _t, _a, filing_id, summary_id, _u = _seed_forced(with_cache=with_cache)
    builder, regex = _real_builder([FRESH_B] * 2)
    reset_inflight()
    try:
        with stream_boundaries(), builder, regex, \
                _another_save_commits_while_this_one_waits_for_the_row_lock(filing_id) as fired:
            events = asyncio.run(_drain_forced(filing_id))
    finally:
        reset_inflight()
    assert fired == [True]
    assert events[-1] == {"type": "complete", "summary_id": summary_id, "percent": 100}
    assert _stored(filing_id) == (
        1, summary_id, CANONICAL_PAYLOAD["business_overview"], STORED_EXCERPT if with_cache else FRESH_B)


@contextmanager
def _the_run_ends_with_no_excerpt(how, late_excerpt):
    """Build no excerpt, or keep its worker pending until the real enrichment join cancels it."""
    from app.services import summary_pipeline

    started, finished = threading.Event(), threading.Event()
    release, join_cancelled = threading.Event(), threading.Event()
    run_in_threadpool = summary_pipeline.run_in_threadpool

    def late(*_a, **_k):
        started.set()
        try:
            assert release.wait(5), "excerpt worker was never released"
            return late_excerpt
        finally:
            finished.set()

    async def release_on_join_cancellation(func, *args, **kwargs):
        if getattr(func, "__name__", None) != "extract_excerpt_sync":
            return await run_in_threadpool(func, *args, **kwargs)
        worker = asyncio.create_task(run_in_threadpool(func, *args, **kwargs))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            # Observe the real join's cancellation before an owned offload drains its worker.
            join_cancelled.set()
            release.set()
            await asyncio.gather(worker, return_exceptions=True)
            raise

    builder = {
        "none": MagicMock(return_value=None),
        "raises": MagicMock(side_effect=RuntimeError("database blip")),
        "join-dropped": MagicMock(side_effect=late),
    }[how]
    with ExitStack() as stack:
        stack.enter_context(patch.object(summary_pipeline, "get_or_cache_excerpt", builder))
        if how == "join-dropped":
            stack.enter_context(patch.object(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", 0.05))
            stack.enter_context(patch.object(summary_pipeline, "run_in_threadpool", release_on_join_cancellation))
        try:
            yield builder
        finally:
            release.set()  # Always unblock a started worker, including on an earlier test failure.
            if started.is_set():
                assert finished.wait(5)
        if how == "join-dropped":
            assert join_cancelled.is_set(), "excerpt did not outlast the enrichment join"


def _a_partial_stored_summary(filing_id):
    # Without an excerpt or XBRL the run is partial, so keep-better lets it replace only a summary ranked no
    # higher: the one-click Regenerate's case.
    from app.database import SessionLocal
    from app.models import Summary

    with SessionLocal() as db:
        db.query(Summary).filter(Summary.filing_id == filing_id).update(
            {Summary.raw_summary: {"sections": {}, "quality": {"tier": "partial"}}}, synchronize_session=False)
        db.commit()


@pytest.mark.parametrize("how", ["none", "raises", "join-dropped"])
@pytest.mark.parametrize("with_summary", [True, False], ids=["update", "insert"])
def test_a_replacing_rebuild_with_no_excerpt_clears_the_stale_stored_one(with_summary, how):
    # A forced precompute asks its run to rebuild the excerpt (rebuild_excerpt) because the stored one was built
    # by an older extraction; main's precompute cleared it before generating. When the rebuild ends with none,
    # the summary it writes was generated from the AI layer's own extraction of the filing text, so the stale
    # excerpt is cleared rather than left as what citation verification and Copilot read that summary against.
    # That is the stored state main's precompute left when its build produced nothing or raised; when the join
    # dropped the build, main's uncancelled thread stored it late, and here the clear stands (the lesson's
    # Limits). With none stored, the stored excerpt is a failed unforced run's, and the INSERT clears it too.
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries

    _t, _a, filing_id, summary_id, _u = _seed_forced(with_summary=with_summary)
    _a_partial_stored_summary(filing_id)
    reset_inflight()
    try:
        with stream_boundaries() as summarize, _the_run_ends_with_no_excerpt(how, FRESH_EXCERPT) as builder:
            events = asyncio.run(_drain_forced(filing_id, rebuild_excerpt=True))
    finally:
        reset_inflight()
    assert builder.call_args.kwargs["reuse_stored"] is False
    assert summarize.await_args.kwargs["filing_excerpt"] is None
    assert events[-1]["type"] == "complete"
    assert _stored(filing_id) == (
        1, summary_id if with_summary else ANY, CANONICAL_PAYLOAD["business_overview"], None)


def _past_the_24_hour_window(filing_id):
    # A forced run takes a stored excerpt younger than 24 h straight from the cache check (admission); an older
    # one it reads through get_or_cache_excerpt, which returns it as it is.
    from app.database import SessionLocal
    from app.models import FilingContentCache

    aged = datetime.now(timezone.utc) - timedelta(days=3)
    with SessionLocal() as db:
        db.query(FilingContentCache).filter(FilingContentCache.filing_id == filing_id).update(
            {FilingContentCache.created_at: aged, FilingContentCache.updated_at: aged}, synchronize_session=False)
        db.commit()


@pytest.mark.parametrize("how", ["raises", "join-dropped"])
@pytest.mark.parametrize("with_summary", [True, False], ids=["update", "insert"])
def test_a_replacing_forced_run_without_a_rebuild_keeps_the_stored_excerpt_it_lost(with_summary, how):
    # Pro Regenerate, refresh_unready, the summary_refresh drains and the admin regenerate force without a
    # rebuild: the run reuses the stored excerpt as its grounding. When its excerpt thread raises or the
    # enrichment join drops it, the summary it writes still replaces the stored one, and the stored excerpt
    # (the same filing's text) stays: cleared, Copilot would have no cached filing text and every non-Risks
    # citation an empty source, until the next forced run that replaces the summary.
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries

    _t, _a, filing_id, summary_id, _u = _seed_forced(with_summary=with_summary)
    _a_partial_stored_summary(filing_id)
    _past_the_24_hour_window(filing_id)
    reset_inflight()
    try:
        with stream_boundaries() as summarize, _the_run_ends_with_no_excerpt(how, STORED_EXCERPT) as builder:
            events = asyncio.run(_drain_forced(filing_id))
    finally:
        reset_inflight()
    assert builder.call_args.kwargs == {"sections": None, "persist": False}
    assert summarize.await_args.kwargs["filing_excerpt"] is None
    assert events[-1]["type"] == "complete"
    assert _stored(filing_id) == (
        1, summary_id if with_summary else ANY, CANONICAL_PAYLOAD["business_overview"], STORED_EXCERPT)


@pytest.mark.parametrize("how", ["raises", "join-dropped"])
def test_an_unforced_first_generation_that_lost_its_excerpt_keeps_the_stored_one(how):
    # An unforced first generation (no stored summary) beside a stored excerpt, a failed earlier run's, past
    # its 24 h window so the run reads it through get_or_cache_excerpt: when that thread raises or the join
    # drops it, the run INSERTs its summary and the stored excerpt stays. Only a rebuild clears it.
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries

    _t, _a, filing_id, _sid, _u = _seed_forced(with_summary=False)
    _past_the_24_hour_window(filing_id)
    reset_inflight()
    try:
        with stream_boundaries() as summarize, _the_run_ends_with_no_excerpt(how, STORED_EXCERPT) as builder:
            events = asyncio.run(_drain_forced(filing_id, force_regenerate=False))
    finally:
        reset_inflight()
    assert builder.call_args.kwargs == {"sections": None}
    assert summarize.await_args.kwargs["filing_excerpt"] is None
    assert events[-1]["type"] == "complete"
    assert _stored(filing_id) == (1, ANY, CANONICAL_PAYLOAD["business_overview"], STORED_EXCERPT)


@pytest.mark.parametrize("outcome", ["kept", "failed"])
def test_a_kept_or_failed_forced_run_with_no_excerpt_clears_nothing(outcome):
    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import reset_inflight, stream_boundaries

    _t, _a, filing_id, summary_id, _u = _seed_forced()
    payload = {"status": "error", "message": "provider down"} if outcome == "failed" else None
    reset_inflight()
    try:
        with stream_boundaries(payload=payload) as summarize, \
                patch.object(summary_pipeline, "get_or_cache_excerpt", MagicMock(return_value=None)):
            if outcome == "kept":
                summarize.side_effect = TimeoutError("budget exhausted")
            asyncio.run(_drain_forced(filing_id, rebuild_excerpt=True))
    finally:
        reset_inflight()
    assert _stored(filing_id) == (1, summary_id, STORED_FULL, STORED_EXCERPT)


@pytest.mark.parametrize(
    ("replace_excerpt", "clear_stale_excerpt", "stored", "excerpt", "after"),
    [
        pytest.param(False, False, STORED_EXCERPT, FRESH_EXCERPT, STORED_EXCERPT, id="unforced-never-overwrites"),
        pytest.param(False, False, None, FRESH_EXCERPT, FRESH_EXCERPT, id="unforced-fills-an-empty-one"),
        pytest.param(False, False, STORED_EXCERPT, None, STORED_EXCERPT, id="unforced-clears-nothing"),
        pytest.param(True, False, STORED_EXCERPT, FRESH_EXCERPT, FRESH_EXCERPT, id="replacing-run-stores-its-own"),
        pytest.param(True, False, STORED_EXCERPT, None, STORED_EXCERPT, id="replacing-reuse-with-none-keeps"),
        pytest.param(True, True, STORED_EXCERPT, None, None, id="replacing-rebuild-with-none-clears"),
    ],
)
def test_the_cache_helper_stores_a_replacing_runs_excerpt_and_clears_a_stale_one_only_for_a_rebuild(
        replace_excerpt, clear_stale_excerpt, stored, excerpt, after):
    from app.services.content_cache import upsert_content_cache

    cache = SimpleNamespace(critical_excerpt=stored, risk_source_text=None, sections_payload=None)
    upsert_content_cache(MagicMock(), 1, cache, excerpt=excerpt, sections_payload={"risks": []},
                         replace_excerpt=replace_excerpt, clear_stale_excerpt=clear_stale_excerpt)
    assert cache.critical_excerpt == after
