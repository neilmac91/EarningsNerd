"""A3 in-flight dedup: concurrent first-requests for the same filing collapse to one generation.

The registry helpers are tested directly; the wait-and-serve path is exercised by driving the real
``stream_filing_summary`` generator while a simulated "leader" holds the slot, then persisting the
result + releasing — the waiter must serve it WITHOUT calling ``summarize_filing``.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services import summary_pipeline


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


def test_claim_and_release_registry():
    fid = 990001
    assert summary_pipeline._inflight_generations.get(fid) is None
    ev = summary_pipeline._claim_inflight(fid)
    assert summary_pipeline._inflight_generations.get(fid) is ev
    assert not ev.is_set()
    summary_pipeline._release_inflight(fid, ev)
    assert summary_pipeline._inflight_generations.get(fid) is None
    assert ev.is_set()


def test_release_does_not_evict_a_newer_leader():
    fid = 990002
    ev1 = summary_pipeline._claim_inflight(fid)
    ev2 = asyncio.Event()
    summary_pipeline._inflight_generations[fid] = ev2  # a newer leader took over the slot
    summary_pipeline._release_inflight(fid, ev1)  # the stale leader releases
    assert summary_pipeline._inflight_generations.get(fid) is ev2  # newer leader still owns it
    assert ev1.is_set()
    summary_pipeline._inflight_generations.pop(fid, None)


@pytest.mark.asyncio
async def test_waiter_serves_leader_result_without_regenerating(monkeypatch):
    from app.database import SessionLocal
    from app.models import Company, Filing, Summary

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        c = Company(cik=f"cik{suffix}", ticker=f"DD{suffix[:4].upper()}", name="Dedup Co")
        db.add(c)
        db.commit()
        db.refresh(c)
        f = Filing(
            company_id=c.id,
            accession_number=f"acc-{suffix}",
            filing_type="10-K",
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/d.htm",
            sec_url=f"https://sec.example/{suffix}/",
        )
        db.add(f)
        db.commit()
        db.refresh(f)
        fid = f.id

    monkeypatch.setattr(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 0.05)  # fast heartbeats
    gen_mock = AsyncMock()  # must NOT be called on the waiter path
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", gen_mock)

    leader_event = summary_pipeline._claim_inflight(fid)  # a leader is already generating

    async def finish_leader():
        await asyncio.sleep(0.2)  # let the waiter emit a couple of heartbeats first
        with SessionLocal() as db:
            db.add(Summary(filing_id=fid, business_overview="LEADER RESULT"))
            db.commit()
        summary_pipeline._release_inflight(fid, leader_event)

    task = asyncio.create_task(finish_leader())
    events = [
        ev
        async for ev in summary_pipeline.stream_filing_summary(
            filing_id=fid,
            current_user=None,
            user_id=None,
            telemetry_distinct_id="t",
            telemetry_entry_point=None,
            telemetry_ctx={},
        )
    ]
    await task

    assert any(e.get("type") == "complete" and e.get("summary") == "LEADER RESULT" for e in events)
    assert "queued" in [e.get("stage") for e in events if e.get("type") == "progress"]
    gen_mock.assert_not_called()  # dedup: served the leader's result, no second generation
    assert summary_pipeline._inflight_generations.get(fid) is None  # slot released


@pytest.mark.asyncio
@pytest.mark.parametrize("force_regenerate", [False, True])
async def test_failed_leader_elects_one_replacement_after_concurrent_reads(monkeypatch, force_regenerate):
    from copy import deepcopy
    from tests.support.summary_stream_harness import CANONICAL_PAYLOAD, seed_company_filing, stream_boundaries

    fid = seed_company_filing()
    old_leader = summary_pipeline._claim_inflight(fid)
    joined = asyncio.Event()
    all_reads = asyncio.Event()
    provider_started = asyncio.Event()
    competition_observed = asyncio.Event()
    finish = asyncio.Event()
    reads = joins = replacement_joins = calls = 0
    original_run = summary_pipeline.run_in_threadpool

    async def simultaneous_reads(func, *args, **kwargs):
        nonlocal reads
        result = await original_run(func, *args, **kwargs)
        if func.__name__ == "get_persisted_summary_fields" and reads < 3:
            # All three followers obtain the same empty DB snapshot before any may claim.
            reads += 1
            if reads == 3:
                all_reads.set()
            await all_reads.wait()
        return result

    async def provider(*args, **kwargs):
        nonlocal calls
        calls += 1
        provider_started.set()
        if calls > 1:
            competition_observed.set()
        await finish.wait()
        return deepcopy(CANONICAL_PAYLOAD)

    async def consume():
        nonlocal joins, replacement_joins
        frames, own_joins = [], 0
        async for frame in summary_pipeline.stream_filing_summary(
            filing_id=fid, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, force_regenerate=force_regenerate,
        ):
            frames.append(frame)
            if frame.get("stage") == "queued":
                own_joins += 1
                if own_joins == 1:
                    joins += 1
                    if joins == 3:
                        joined.set()
                else:
                    replacement_joins += 1
                    if replacement_joins == 2:
                        competition_observed.set()
        return frames

    with stream_boundaries(), monkeypatch.context() as patch:
        patch.setattr(summary_pipeline, "run_in_threadpool", simultaneous_reads)
        patch.setattr(summary_pipeline.openai_service, "summarize_filing", provider)
        tasks = [asyncio.create_task(consume()) for _ in range(3)]
        try:
            await asyncio.wait_for(joined.wait(), 2)
            summary_pipeline._release_inflight(fid, old_leader)  # failed without persisting
            await asyncio.wait_for(provider_started.wait(), 2)
            await asyncio.wait_for(competition_observed.wait(), 2)
            assert calls == 1, "failed leader followers started duplicate provider work"
            assert replacement_joins == 2
            finish.set()
            results = await asyncio.wait_for(asyncio.gather(*tasks), 2)
            completions = [next(frame for frame in frames if frame["type"] == "complete") for frames in results]
            assert len({frame["summary_id"] for frame in completions}) == 1
            assert fid not in summary_pipeline._inflight_generations
        finally:
            finish.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            summary_pipeline._inflight_generations.pop(fid, None)


@pytest.mark.asyncio
async def test_expired_follower_budget_does_not_replace_active_leader(monkeypatch):
    from tests.support.summary_stream_harness import seed_company_filing, stream_boundaries

    fid = seed_company_filing()
    leader = summary_pipeline._claim_inflight(fid)
    with stream_boundaries() as generate:
        # Exhaust only the follower budget, without waiting or changing the global backstop.
        monkeypatch.setattr(summary_pipeline, "INFLIGHT_WAIT_CAP_SECONDS", 0)
        try:
            frames = [frame async for frame in summary_pipeline.stream_filing_summary(
                filing_id=fid, current_user=None, user_id=None, telemetry_distinct_id="offline",
                telemetry_entry_point=None, telemetry_ctx={},
            )]
            assert frames[-1] == {"type": "error", "message": "Summary generation timed out. Please try again."}
            generate.assert_not_called()
            assert summary_pipeline._inflight_generations.get(fid) is leader
            assert not leader.is_set()
        finally:
            summary_pipeline._release_inflight(fid, leader)


@pytest.mark.asyncio
@pytest.mark.parametrize("force_regenerate", [False, True])
async def test_delayed_empty_snapshot_after_replacement_completes_is_reread(monkeypatch, force_regenerate):
    from tests.support.summary_stream_harness import seed_company_filing, stream_boundaries

    fid = seed_company_filing()
    leader = summary_pipeline._claim_inflight(fid)
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
        elif func.__name__ == "get_persisted_summary_fields" and result is None:
            # The replacement cannot persist before the delayed follower has its empty snapshot.
            await delayed_read.wait()
        return result

    async def consume():
        nonlocal joins
        frames = []
        async for frame in summary_pipeline.stream_filing_summary(
            filing_id=fid, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, force_regenerate=force_regenerate,
        ):
            frames.append(frame)
            if frame.get("stage") == "queued":
                joins += 1
                if joins == 2:
                    joined.set()
        return frames

    with stream_boundaries() as generate, monkeypatch.context() as patch:
        patch.setattr(summary_pipeline, "run_in_threadpool", delay_empty_read)
        delayed = asyncio.create_task(consume(), name="delayed-follower")
        replacement = asyncio.create_task(consume(), name="replacement-follower")
        try:
            await asyncio.wait_for(joined.wait(), 2)
            summary_pipeline._release_inflight(fid, leader)
            await asyncio.wait_for(delayed_read.wait(), 2)
            completed = await asyncio.wait_for(replacement, 2)
            assert fid not in summary_pipeline._inflight_generations
            generate.assert_awaited_once()
            return_delayed.set()  # now return the obsolete empty snapshot
            resumed = await asyncio.wait_for(delayed, 2)
            generate.assert_awaited_once()
            assert next(f["summary_id"] for f in completed if f["type"] == "complete") == next(
                f["summary_id"] for f in resumed if f["type"] == "complete")
            assert fid not in summary_pipeline._inflight_generations
        finally:
            return_delayed.set()
            for task in (delayed, replacement):
                task.cancel()
            await asyncio.gather(delayed, replacement, return_exceptions=True)
            summary_pipeline._inflight_generations.pop(fid, None)
