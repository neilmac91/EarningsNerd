"""Completed filing enrichment survives independent timeout/write failures offline."""
import asyncio
from copy import deepcopy

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary
from app.services import summary_pipeline as pipeline
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    seed_company_filing,
    stream_boundaries,
)

# Filing-instance series shape: actual normalization runs inside the real pipeline.
XBRL = {
    "revenue": [{"value": 996347000000, "period": "2025-03-31", "period_start": "2024-04-01",
                 "currency": "CNY", "form": "20-F", "raw_tag": "us-gaap:Revenues"}],
    "reporting_currency": "CNY",
}


@pytest.fixture(scope="module", autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)


async def _drive(filing_id, before_join=None):
    frames = []
    async for frame in pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    ):
        frames.append(frame)
        if before_join and frame.get("percent") == 50:
            await before_join()
    return frames


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["excerpt_timeout", "xbrl_timeout", "cancel"])
async def test_completed_enrichment_survives_sibling_timeout_and_cancellation_drains(monkeypatch, mode):
    fid = seed_company_filing(filing_type="20-F")
    ready, pending_started, pending_stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_run = pipeline.run_in_threadpool

    async def pending():
        pending_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            pending_stopped.set()

    async def fetch(*args, **kwargs):
        if mode != "excerpt_timeout":
            return await pending()
        return deepcopy(XBRL)

    async def run_db(func, *args, **kwargs):
        if func.__name__ == "extract_excerpt_sync" and mode == "excerpt_timeout":
            return await pending()
        result = await original_run(func, *args, **kwargs)
        if func.__name__ == ("update_xbrl_sync" if mode == "excerpt_timeout" else "extract_excerpt_sync"):
            ready.set()
        return result

    joined = asyncio.Event()

    async def before_join():
        await ready.wait()
        await pending_started.wait()
        joined.set()

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as generate:
        monkeypatch.setattr(pipeline.xbrl_service, "get_xbrl_data", fetch)
        monkeypatch.setattr(pipeline, "run_in_threadpool", run_db)
        monkeypatch.setattr(pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", 10 if mode == "cancel" else 0)
        task = asyncio.create_task(_drive(fid, before_join))
        try:
            await asyncio.wait_for(joined.wait(), 2)
            if mode == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                generate.assert_not_awaited()
            else:
                frames = await asyncio.wait_for(task, 2)
                generate.assert_awaited_once()
                supplied = generate.await_args.kwargs
                if mode == "excerpt_timeout":
                    assert supplied["xbrl_metrics"]["revenue"]["current"] == XBRL["revenue"][0]
                    assert supplied["xbrl_metrics"]["reporting_currency"] == "CNY"
                    assert supplied["filing_excerpt"] is None
                else:
                    assert supplied["filing_excerpt"] == "EXCERPT"
                    assert supplied["xbrl_metrics"] is None
                assert frames[-1]["type"] == "complete"
            assert pending_stopped.is_set(), "unfinished enrichment escaped the gather cleanup"
            assert fid not in pipeline._inflight_generations
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_extracted_metrics_reach_generation_when_xbrl_commit_fails(monkeypatch):
    fid = seed_company_filing(filing_type="20-F")
    attempted = []

    def fail_xbrl_commit(session):
        if any(isinstance(row, Filing) and row.id == fid and row.xbrl_data for row in session.dirty):
            attempted.append(True)
            raise SQLAlchemyError("controlled XBRL commit failure")

    async def fetch(*args, **kwargs):
        return deepcopy(XBRL)

    event.listen(Session, "before_commit", fail_xbrl_commit)
    try:
        with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as generate:
            monkeypatch.setattr(pipeline.xbrl_service, "get_xbrl_data", fetch)
            frames = await asyncio.wait_for(_drive(fid), 2)
            generate.assert_awaited_once()
            metrics = generate.await_args.kwargs["xbrl_metrics"]
            assert metrics["revenue"]["current"]["value"] == 996347000000
            assert metrics["revenue"]["current"]["currency"] == "CNY"
            assert generate.await_args.kwargs["filing_excerpt"] == "EXCERPT"
            assert frames[-1]["type"] == "complete"
        assert attempted == [True]
        with SessionLocal() as session:
            assert session.get(Filing, fid).xbrl_data is None  # failed cache write rolled back
            assert session.query(Summary).filter_by(filing_id=fid).one().id == frames[-1]["summary_id"]
        assert fid not in pipeline._inflight_generations
    finally:
        event.remove(Session, "before_commit", fail_xbrl_commit)
