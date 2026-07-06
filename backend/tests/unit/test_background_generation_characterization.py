"""Characterization of ``generate_summary_background`` — the unified background/cron/precompute path.

Since S1's old-path removal, ``generate_summary_background`` drains the ONE orchestrator
(``stream_filing_summary``) headless: filing-only generation, the 9-section ``assess_quality``
verdict, partial-persistence, and filing_id-conflict handling are all INHERITED from the SSE
pipeline. It drives the REAL function against a seeded SQLite DB (no MagicMock DB) using the shared
harness (``CANONICAL_PAYLOAD`` / ``stream_boundaries`` / ``seed_company_filing`` from
``tests.support.summary_stream_harness``), so the boundary mocks stay in lockstep with the SSE
anchors.

Pinned here:
  * early-return branches (decided before the drain, need no boundary mocks): filing not found ->
    no-op; ``OPENAI_API_KEY`` unset -> a placeholder Summary is persisted (NOT a failure); a Summary
    already exists -> no regeneration (cron idempotence);
  * the drain is FILING-ONLY — a 10-K with a prior filing on record still passes
    ``previous_filings=None`` (the SSE contract, inherited);
  * a precompute run (``user_id=None``) emits ZERO funnel events — the drain suppresses funnel
    telemetry via ``emit_funnel_telemetry=False``, and the funnel seam is not even imported here;
  * partials are PERSISTED (the drained pipeline saves the row with a quality tier).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models import Summary
from app.services import summary_generation_service
from app.services.summary_generation_service import generate_summary_background
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)


@pytest.fixture(scope="module", autouse=True)
def _tables():
    from app.database import engine
    from app.models import Base

    Base.metadata.create_all(bind=engine)
    yield


# --- early-return branches --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_filing_is_a_noop():
    """A filing_id that doesn't exist returns without writing anything."""
    missing_id = 990_500_000  # far above any autoincrement id the suite creates
    await generate_summary_background(missing_id, None)

    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == missing_id).first() is None


@pytest.mark.asyncio
async def test_no_api_key_persists_a_placeholder_summary(monkeypatch):
    """With OPENAI_API_KEY unset, the background path persists a placeholder Summary (rather than
    failing) — this decision predates the drain and is preserved."""
    filing_id = seed_company_filing()
    monkeypatch.setattr(summary_generation_service.settings, "OPENAI_API_KEY", "")

    await generate_summary_background(filing_id, None)

    with SessionLocal() as db:
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        assert summary is not None
        assert "OpenAI API key" in summary.business_overview
        assert summary.raw_summary == {"error": "OpenAI API key not configured"}


@pytest.mark.asyncio
async def test_existing_summary_is_not_regenerated():
    """If a Summary already exists for the filing, the background path returns without reaching the
    drain or creating a second row (cron idempotence)."""
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        db.add(Summary(filing_id=filing_id, business_overview="EXISTING SUMMARY"))
        db.commit()

    reset_inflight()
    with stream_boundaries() as summarize:
        await generate_summary_background(filing_id, None)

    summarize.assert_not_called()  # the drain is never reached
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).count() == 1


# --- the unified drain: filing-only, zero-funnel, partial-persistence --------------------------

@pytest.mark.asyncio
async def test_drain_is_filing_only_and_zero_funnel():
    """generate_summary_background drains stream_filing_summary headless, so a 10-K (even with a
    prior filing on record) is FILING-ONLY — the SSE path passes previous_filings=None — a Summary
    is persisted, and a precompute run (user_id=None) emits ZERO funnel events (the drain suppresses
    funnel telemetry via emit_funnel_telemetry=False)."""
    from app.services import summary_pipeline

    reset_inflight()
    filing_id = seed_company_filing(filing_type="10-K", prior=True)

    funnel_spy = MagicMock()
    with stream_boundaries() as summarize, patch.object(
        summary_pipeline, "capture_funnel_event", funnel_spy
    ):
        await generate_summary_background(filing_id, None)

    assert summarize.call_args.kwargs.get("previous_filings") is None  # filing-only, even for a 10-K
    funnel_spy.assert_not_called()                                     # zero funnel on the drain
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).first() is not None


@pytest.mark.asyncio
async def test_drain_persists_partial():
    """The drained pipeline PERSISTS partials (AI_QUALITY_GATE always saves the row with a quality
    tier). A 2/9 structured snapshot is partial under the 4/9 bar, yet the row is still written."""
    reset_inflight()
    filing_id = seed_company_filing(filing_type="10-Q")

    partial = {
        **CANONICAL_PAYLOAD,
        "raw_summary": {
            "sections": {},
            "section_coverage": {
                "per_section": {"executive_snapshot": True, "financial_highlights": True},
                "covered_count": 2,
                "total_count": 9,
            },
        },
    }
    with stream_boundaries(payload=partial):
        await generate_summary_background(filing_id, None)

    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).first() is not None
