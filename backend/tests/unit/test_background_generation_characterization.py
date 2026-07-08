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
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models import Summary, User
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


def _seed_user() -> int:
    """Seed a unique User row (email is the only NOT NULL field) and return its id."""
    with SessionLocal() as db:
        user = User(email=f"bg-{uuid.uuid4().hex[:8]}@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


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


# --- quota / billing contract (charged once on full, never on partial) ------------------------
# generate_summary_background passes user_id straight into the drain, which charges via the
# pipeline's own count_usage (once on a full result; skipped on a partial by the quality gate).
# These pin that billing contract for the background/cron caller — the coverage the pre-unification
# usage tests held, re-anchored on the live drain path.

@pytest.mark.asyncio
async def test_drain_charges_usage_once_for_signed_in_full_result():
    """A signed-in full result consumes exactly one quota unit — the drained pipeline calls
    increment_user_usage once, with this user's id (FREE_TIER_SUMMARY_LIMIT contract)."""
    from app.services import summary_pipeline

    user_id = _seed_user()
    reset_inflight()
    filing_id = seed_company_filing(filing_type="10-Q")  # CANONICAL_PAYLOAD -> 4/7 -> full

    spy = MagicMock()
    with stream_boundaries(), patch.object(summary_pipeline, "increment_user_usage", spy):
        await generate_summary_background(filing_id, user_id)

    spy.assert_called_once()
    assert spy.call_args.args[0] == user_id


@pytest.mark.asyncio
async def test_drain_does_not_charge_usage_for_partial():
    """A partial result consumes NO quota, even for a signed-in user — the quality gate skips the
    charge (the no-charge-on-partial half of the billing contract)."""
    from app.services import summary_pipeline

    user_id = _seed_user()
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
    spy = MagicMock()
    with stream_boundaries(payload=partial), patch.object(summary_pipeline, "increment_user_usage", spy):
        await generate_summary_background(filing_id, user_id)

    spy.assert_not_called()


# --- force-refresh (T1.4): in-place UPDATE preserving id/bookmark + keep-better gate -----------
# ADDITIVE to this locked characterization file (sanctioned by the plan's T1.4 row): the existing
# tests above are untouched. These pin the admin refresh-stale mechanics on the ONE orchestrator.

_PARTIAL_PAYLOAD = {
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


@pytest.mark.asyncio
async def test_force_regenerate_updates_in_place_preserving_id_and_bookmark():
    """force_regenerate=True UPDATEs the existing row in place: exactly one row, same summaries.id
    (so the saved_summaries FK/bookmark survives), business_overview refreshed."""
    from app.models import SavedSummary

    reset_inflight()
    user_id = _seed_user()
    filing_id = seed_company_filing(filing_type="10-Q")

    with stream_boundaries():
        await generate_summary_background(filing_id, None)
    with SessionLocal() as db:
        original = db.query(Summary).filter(Summary.filing_id == filing_id).one()
        original_id = original.id
        db.add(SavedSummary(user_id=user_id, summary_id=original_id))
        db.commit()

    updated_payload = {**CANONICAL_PAYLOAD, "business_overview": "# Updated\n\nRefreshed content."}
    reset_inflight()
    with stream_boundaries(payload=updated_payload):
        await generate_summary_background(filing_id, None, force_regenerate=True)

    with SessionLocal() as db:
        rows = db.query(Summary).filter(Summary.filing_id == filing_id).all()
        assert len(rows) == 1                       # UPDATE in place, not delete+insert
        assert rows[0].id == original_id            # id preserved -> bookmark FK intact
        assert rows[0].business_overview == "# Updated\n\nRefreshed content."
        # The bookmark still resolves to the (same-id) refreshed summary.
        bookmark = db.query(SavedSummary).filter(SavedSummary.summary_id == original_id).one()
        assert bookmark.summary_id == rows[0].id


@pytest.mark.asyncio
async def test_keep_better_gate_keeps_stored_full_over_new_partial():
    """A refresh must never downgrade: a stored full is kept when regeneration comes back partial
    (the 75s AI-timeout XBRL fallback), so a bulk refresh can't silently degrade the corpus."""
    reset_inflight()
    filing_id = seed_company_filing(filing_type="10-Q")

    with stream_boundaries():  # CANONICAL -> full
        await generate_summary_background(filing_id, None)
    with SessionLocal() as db:
        stored = db.query(Summary).filter(Summary.filing_id == filing_id).one()
        stored_id, stored_overview = stored.id, stored.business_overview
        assert (stored.raw_summary or {}).get("quality", {}).get("tier") == "full"

    reset_inflight()
    with stream_boundaries(payload=_PARTIAL_PAYLOAD):  # regeneration degrades to partial
        await generate_summary_background(filing_id, None, force_regenerate=True)

    with SessionLocal() as db:
        kept = db.query(Summary).filter(Summary.filing_id == filing_id).one()
        assert kept.id == stored_id
        assert kept.business_overview == stored_overview          # stored full untouched
        assert (kept.raw_summary or {}).get("quality", {}).get("tier") == "full"


@pytest.mark.asyncio
async def test_force_regenerate_inserts_when_no_summary_exists():
    """force_regenerate on a filing with no stored summary falls through to a normal INSERT."""
    reset_inflight()
    filing_id = seed_company_filing(filing_type="10-Q")

    with stream_boundaries():
        await generate_summary_background(filing_id, None, force_regenerate=True)

    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).count() == 1
