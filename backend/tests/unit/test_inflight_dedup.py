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
