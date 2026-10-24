"""A forced run keeps the excerpt it builds to itself until finalize stores it with its summary.

Codex 4365089688 on #1545: two forced precomputes of one filing that overlapped left a kept summary
beside the rejected run's excerpt, because the precompute cleared the stored excerpt before its run
and put it back afterwards, and the second run captured the first's new excerpt as "stored". These run
the real orchestrator and the real ``get_or_cache_excerpt`` (only SEC, the provider and the extraction
are faked): in one process (the second run joins the first through the in-flight registry) and in two
(each process has its own registry, so both lead), plus the Pro "Regenerate" / refresh-stale variant
(a summary stored beside no excerpt) and the commit the excerpt shares with its summary. Finalize reads
the cache row after the summary's row lock, so a save that committed while this one waited is what it
replaces; and a replacing run with no excerpt clears the stored one, while a kept or failed run writes none.
"""
import asyncio
from contextlib import contextmanager
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


async def _drain_forced(filing_id, **flags):
    from app.services import summary_pipeline

    events = []
    async for event in summary_pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="t",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
        force_regenerate=True, **flags,
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


@pytest.mark.parametrize("with_summary", [True, False], ids=["update", "insert"])
def test_a_replacing_forced_run_with_no_excerpt_clears_the_stored_one(with_summary):
    # The run's excerpt build failed (or the enrichment join dropped it): its summary was generated from the
    # filing text through the AI layer's own extraction, so a stored excerpt left beside it would be what
    # citation verification and the Risks projection read it against (provenance prefers the excerpt).
    # Without an excerpt or XBRL the run is partial, so the stored summary it replaces is partial too (the
    # one-click Regenerate's case); with none stored, the stored excerpt is a failed unforced run's.
    from app.database import SessionLocal
    from app.models import Summary
    from app.services import summary_pipeline
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, reset_inflight, stream_boundaries

    _t, _a, filing_id, summary_id, _u = _seed_forced(with_summary=with_summary)
    with SessionLocal() as db:
        db.query(Summary).filter(Summary.filing_id == filing_id).update(
            {Summary.raw_summary: {"sections": {}, "quality": {"tier": "partial"}}}, synchronize_session=False)
        db.commit()
    reset_inflight()
    try:
        with stream_boundaries() as summarize, \
                patch.object(summary_pipeline, "get_or_cache_excerpt", MagicMock(return_value=None)):
            events = asyncio.run(_drain_forced(filing_id, rebuild_excerpt=True))
    finally:
        reset_inflight()
    assert summarize.await_args.kwargs["filing_excerpt"] is None
    assert events[-1]["type"] == "complete"
    assert _stored(filing_id) == (
        1, summary_id if with_summary else ANY, CANONICAL_PAYLOAD["business_overview"], None)


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
    ("replace_excerpt", "stored", "excerpt", "after"),
    [
        (False, STORED_EXCERPT, FRESH_EXCERPT, STORED_EXCERPT),  # an unforced write never overwrites
        (False, None, FRESH_EXCERPT, FRESH_EXCERPT),             # ... and fills an empty one
        (False, STORED_EXCERPT, None, STORED_EXCERPT),           # ... and clears nothing
        (True, STORED_EXCERPT, FRESH_EXCERPT, FRESH_EXCERPT),    # a replacing forced run stores its own
        (True, STORED_EXCERPT, None, None),                      # ... none included
    ],
)
def test_the_cache_helper_stores_a_replacing_runs_excerpt_and_only_fills_otherwise(replace_excerpt, stored, excerpt, after):
    from app.services.content_cache import upsert_content_cache

    cache = SimpleNamespace(critical_excerpt=stored, risk_source_text=None, sections_payload=None)
    upsert_content_cache(MagicMock(), 1, cache, excerpt=excerpt, sections_payload={"risks": []},
                         replace_excerpt=replace_excerpt)
    assert cache.critical_excerpt == after
