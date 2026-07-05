"""T1 — the full ordered SSE event contract of ``stream_filing_summary`` (the user-facing path).

Drives the REAL generator offline (the ``test_inflight_dedup`` pattern) with the SEC/XBRL/AI/excerpt
boundaries mocked in ``summary_pipeline``'s namespace, and pins the ordered contract the frontend
consumes: progress stages in order → a ``chunk`` carrying the summary markdown → exactly one terminal
``complete`` event with ``{summary_id, percent: 100}``; no ``error``. Also pins the ``to_sse`` wire
framing, and emits a recorded frame sequence to ``tests/fixtures/summary_stream_frames.json`` that
the frontend parser test (T10) consumes — so producer and consumer share ONE artifact.

Determinism: instant fakes ⇒ the summarize step returns immediately ⇒ no heartbeat frames ⇒ a fully
ordered sequence.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services import summary_pipeline
from app.services.summary_pipeline import stream_filing_summary, to_sse

FRAMES_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "summary_stream_frames.json"


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _reset_inflight():
    """A leaked ``_inflight_generations`` slot silently reroutes the next generation down the dedup
    (join) path — reset it around every test so each drives the primary path."""
    summary_pipeline._inflight_generations.clear()
    yield
    summary_pipeline._inflight_generations.clear()


_PAYLOAD = {
    "status": "complete",
    "business_overview": "# Summary\n\nAcme Corp designs and sells widgets worldwide.",
    "financial_highlights": {"revenue": "1B", "notes": "Revenue increased 12% year over year."},
    "risk_factors": [{"summary": "Supply-chain risk.", "supporting_evidence": "Item 1A."}],
    "management_discussion": "MD&A covers results of operations and financial condition.",
    "key_changes": "Higher R&D investment.",
    "raw_summary": {
        "sections": {"business_overview": "Acme Corp designs and sells widgets."},
        "section_coverage": {"covered_count": 5, "total_count": 7},
    },
}


def _seed_10k() -> int:
    from app.database import SessionLocal
    from app.models import Company, Filing

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        company = Company(cik=f"cik{suffix}", ticker=f"ST{suffix[:4].upper()}", name="Stream Co")
        db.add(company)
        db.commit()
        db.refresh(company)
        filing = Filing(
            company_id=company.id, accession_number=f"acc-{suffix}", filing_type="10-K",
            filing_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            document_url=f"https://sec.example/{suffix}/d.htm", sec_url=f"https://sec.example/{suffix}/",
        )
        db.add(filing)
        db.commit()
        db.refresh(filing)
        return filing.id


def _mock_boundaries(monkeypatch):
    monkeypatch.setattr(summary_pipeline.sec_edgar_service, "get_filing_document",
                        AsyncMock(return_value="FILING DOCUMENT TEXT " * 40))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", AsyncMock(return_value=None))
    monkeypatch.setattr(summary_pipeline, "get_or_cache_excerpt", lambda *a, **k: "EXCERPT")
    monkeypatch.setattr(summary_pipeline, "check_usage_limit", lambda user, session: (True, 0, None))
    monkeypatch.setattr(summary_pipeline.openai_service, "summarize_filing", AsyncMock(return_value=_PAYLOAD))
    # instant fake ⇒ no heartbeat frames ⇒ fully ordered
    monkeypatch.setattr(summary_pipeline.settings, "STREAM_HEARTBEAT_INTERVAL", 999)


async def _drive(filing_id: int) -> list:
    return [
        ev
        async for ev in stream_filing_summary(
            filing_id=filing_id,
            current_user=None,
            user_id=None,
            telemetry_distinct_id="t",
            telemetry_entry_point=None,
            telemetry_ctx={},
        )
    ]


@pytest.mark.asyncio
async def test_sse_ordered_contract(monkeypatch):
    _mock_boundaries(monkeypatch)
    filing_id = _seed_10k()

    events = await _drive(filing_id)

    # 1. progress stages appear as an ordered subsequence (initializing → … → summarizing)
    stages = [e["stage"] for e in events if e.get("type") == "progress" and "stage" in e]
    expected = ["initializing", "fetching", "parsing", "analyzing", "summarizing"]
    for stage in expected:
        assert stage in stages, f"missing progress stage {stage!r}; got {stages}"
    positions = [stages.index(s) for s in expected]
    assert positions == sorted(positions), f"stages out of order: {stages}"

    # 2. a chunk carries the summary markdown (business_overview)
    chunks = [e for e in events if e.get("type") == "chunk"]
    assert chunks, "no chunk event"
    assert chunks[-1]["content"] == _PAYLOAD["business_overview"]

    # 3. exactly one terminal event, and it's `complete` with percent 100 + an int summary_id
    terminals = [e for e in events if e.get("type") in {"complete", "partial", "error"}]
    assert len(terminals) == 1, f"expected one terminal event, got {[t['type'] for t in terminals]}"
    complete = terminals[0]
    assert complete["type"] == "complete"
    assert complete["percent"] == 100
    assert isinstance(complete["summary_id"], int)

    # 4. every frame is JSON-serializable (it must survive to_sse)
    for ev in events:
        to_sse(ev)


def test_to_sse_framing():
    """The wire framing the frontend parses: ``data: <json>\\n\\n``."""
    frame = to_sse({"type": "complete", "summary_id": 7, "percent": 100})
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    assert json.loads(frame[len("data: "):].strip()) == {"type": "complete", "summary_id": 7, "percent": 100}


@pytest.mark.asyncio
async def test_recorded_frames_fixture_matches_live_contract(monkeypatch):
    """The checked-in frames fixture (shared with the frontend parser test T10) must stay in step
    with what the producer actually emits: same ordered event `type`s, terminating in `complete`."""
    assert FRAMES_FIXTURE.exists(), (
        f"missing {FRAMES_FIXTURE}; regenerate with scripts/gen_summary_stream_frames.py"
    )
    recorded = json.loads(FRAMES_FIXTURE.read_text())
    recorded_types = [f["type"] for f in recorded]

    _mock_boundaries(monkeypatch)
    live_types = [e["type"] for e in await _drive(_seed_10k())]

    assert recorded_types == live_types, (
        "recorded frames drifted from the producer; regenerate the fixture"
    )
    assert recorded_types[-1] == "complete"
