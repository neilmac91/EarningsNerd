"""T2 — characterization of ``generate_summary_background`` (the S1 "before photo").

This is the anchor that pins the *current* behavior of the background/cron/precompute generation
path so the Wave-2 S1 unification (routing it through ``stream_filing_summary``) can't silently
change it. It drives the REAL function against a seeded SQLite DB (no MagicMock DB) using the shared
harness (``CANONICAL_PAYLOAD`` / ``background_boundaries`` / ``seed_company_filing`` from
``tests.support.summary_stream_harness``), so the boundary mocks stay in lockstep with the SSE
anchors.

What is pinned here (the full T2 divergence record):

  Early-return branches (reach a decision before the generation core, need no service mocks):
    - filing not found -> no-op (no Summary row);
    - ``OPENAI_API_KEY`` unset -> a placeholder Summary is persisted (NOT a failure);
    - a Summary already exists -> no regeneration (cron idempotence).

  ``previous_filings`` divergence — the core S1 gap. The background path injects the prior 10-K as
  year-over-year context for a 10-K and passes ``None`` for a 10-Q; the SSE path hardcodes
  ``previous_filings=None``. Two tests pin both arms.

  Coverage taxonomy (9-vs-7) — the background path DUAL-WRITES two different coverage taxonomies:
  the 9-section ``openai_service`` ``coverage_snapshot`` (``_TRACKED_STRUCTURED_SECTIONS``) is
  persisted VERBATIM to ``SummaryGenerationProgress.section_coverage`` (passed through from
  ``raw_summary.section_coverage``), while the full/partial VERDICT and the ``sections_unavailable``
  metadata are computed independently by ``calculate_section_coverage`` over the 7
  ``HIDEABLE_SECTIONS``. S1 collapsing these into one taxonomy breaks the taxonomy test.

  Verdict function — the background verdict comes from ``determine_result_type`` (a section-coverage
  gate ONLY; no XBRL-grounding check), NOT ``assess_quality``. A payload that clears the 3/7
  coverage threshold is cached "full" even when its financials don't match the SEC XBRL metrics;
  ``assess_quality`` (the SSE path's verdict) would mark the identical payload "partial". Pinned
  end-to-end so an S1 swap to ``assess_quality`` fails here.

  Usage / quota — ``increment_user_usage`` is called exactly once on a successful full result WITH
  a ``user_id``; it is NOT called on the partial-discard path (a partial consumes no quota, even
  for a signed-in user).

  Partial discard — a low-coverage result verdicts "partial" and writes NO Summary row (the SSE
  path persists partials with a quality tier — S1 must reconcile).

  Zero PostHog on precompute — a precompute run (``user_id=None``) captures ZERO funnel events. The
  funnel seam (``capture_funnel_event``) is not even imported into this module; funnel telemetry
  lives ONLY on the SSE path (``summary_pipeline``). Pinned both statically and end-to-end (via the
  ``summary_pipeline`` seam S1's unification would route through).

What remains (NOT yet characterized here): the global-timeout and generic-exception handlers
(``summary_generation_service.py:852-910``) each record a "partial" progress row and discard — a
future increment could pin those two error arms directly.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models import Summary, SummaryGenerationProgress, User
from app.services import summary_generation_service
from app.services.summary_generation_service import (
    HIDEABLE_SECTIONS,
    assess_quality,
    calculate_section_coverage,
    determine_result_type,
    generate_summary_background,
)
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    background_boundaries,
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
    """With OPENAI_API_KEY unset, the background path persists a placeholder Summary (current
    behavior) rather than failing — S1 must preserve or consciously change this."""
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
    AI boundary or creating a second row (cron idempotence)."""
    filing_id = seed_company_filing()
    with SessionLocal() as db:
        db.add(Summary(filing_id=filing_id, business_overview="EXISTING SUMMARY"))
        db.commit()

    with background_boundaries() as summarize:
        await generate_summary_background(filing_id, None)

    summarize.assert_not_called()  # the generation core is never reached
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).count() == 1


# --- previous_filings divergence (the core S1 "before photo") ---------------------------------
# The background path injects the prior 10-K as year-over-year context for a 10-K, and passes None
# for other forms. The SSE path hardcodes previous_filings=None. S1 unification must not silently
# resolve this difference — these two tests pin both arms.

@pytest.mark.asyncio
async def test_10k_injects_prior_10k_as_previous_filings():
    """A 10-K with a prior 10-K passes that prior to summarize_filing as previous_filings context."""
    current_id = seed_company_filing(filing_type="10-K", prior=True)

    with background_boundaries() as summarize:
        await generate_summary_background(current_id, None)

    summarize.assert_called_once()
    previous = summarize.call_args.kwargs["previous_filings"]
    assert previous is not None
    assert len(previous) == 1  # the one prior 10-K, injected as YoY trend context


@pytest.mark.asyncio
async def test_10q_passes_no_previous_filings():
    """A 10-Q does not fetch prior filings — summarize_filing receives previous_filings=None."""
    filing_id = seed_company_filing(filing_type="10-Q")

    with background_boundaries() as summarize:
        await generate_summary_background(filing_id, None)

    summarize.assert_called_once()
    assert summarize.call_args.kwargs["previous_filings"] is None


# --- coverage taxonomy (9-vs-7) ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_progress_persists_9_section_snapshot_while_verdict_uses_7_section_hideable():
    """The background path DUAL-WRITES two coverage taxonomies:

      * the 9-section ``openai_service`` snapshot (``raw_summary.section_coverage``) is persisted
        VERBATIM to ``SummaryGenerationProgress.section_coverage`` — passed through, not recomputed;
      * the full/partial verdict and the ``sections_unavailable`` metadata are computed
        independently by ``calculate_section_coverage`` over the 7 ``HIDEABLE_SECTIONS``.

    S1 collapsing these into a single taxonomy (persisting the 7-count to progress, or gating the
    verdict on the persisted 9-snapshot) would break one of the assertions below.
    """
    filing_id = seed_company_filing(filing_type="10-Q")

    # A distinctive 9-section snapshot (openai_service._TRACKED_STRUCTURED_SECTIONS shape):
    # total_count=9, and "missing" names that never appear in the 7 HIDEABLE_SECTIONS.
    nine_snapshot = {
        "per_section": {"segment_performance": True, "three_year_trend": False},
        "covered": [
            "executive_snapshot", "financial_highlights", "risk_factors",
            "management_discussion_insights", "segment_performance",
            "liquidity_capital_structure", "guidance_outlook", "notable_footnotes",
        ],
        "missing": ["three_year_trend"],
        "covered_count": 8,
        "total_count": 9,
        "coverage_ratio": 8 / 9,
    }
    payload = {
        **CANONICAL_PAYLOAD,
        "raw_summary": {
            "sections": CANONICAL_PAYLOAD["raw_summary"]["sections"],
            "section_coverage": nine_snapshot,
        },
    }

    with background_boundaries(payload=payload):
        await generate_summary_background(filing_id, None)

    with SessionLocal() as db:
        # (1) The taxonomy PERSISTED to progress is the 9-section snapshot, passed through unchanged.
        progress = (
            db.query(SummaryGenerationProgress)
            .filter(SummaryGenerationProgress.filing_id == filing_id)
            .first()
        )
        assert progress is not None
        assert progress.stage == "completed"
        assert progress.section_coverage == nine_snapshot
        assert progress.section_coverage["total_count"] == 9  # NOT the 7-section HIDEABLE count

        # (2) The verdict + its metadata use the 7-section HIDEABLE taxonomy.
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        assert summary is not None  # 4/7 HIDEABLE sections clears the "full" threshold
        raw = summary.raw_summary
        assert raw["result_type"] == "full"
        assert raw["section_coverage"]["total_count"] == 9  # 9-snapshot preserved in the cache too
        unavailable = {note["section"] for note in raw["sections_unavailable"]}
        assert unavailable == {"risk_factors", "forward_guidance", "additional_disclosures"}
        assert unavailable <= set(HIDEABLE_SECTIONS)
        assert "three_year_trend" not in unavailable  # a 9-taxonomy-only name never leaks in

    # (3) The two taxonomies really are different counts on the same input (7 for the gate, 9 for
    #     the persisted snapshot) — not one shared number.
    covered7, total7, _, _ = calculate_section_coverage(CANONICAL_PAYLOAD)
    assert (covered7, total7) == (4, 7)
    assert nine_snapshot["total_count"] == 9


# --- verdict function (determine_result_type, NOT assess_quality) -----------------------------

@pytest.mark.asyncio
async def test_verdict_uses_determine_result_type_ignoring_xbrl_grounding():
    """The background verdict comes from ``determine_result_type`` — a section-coverage gate that
    never runs an XBRL-grounding check. A payload clearing the 3/7 threshold is cached FULL even
    when its financial figures appear nowhere in the SEC XBRL metrics. ``assess_quality`` (the SSE
    path's verdict) would mark the identical (payload, xbrl) pair "partial". Pinned end-to-end: if
    S1 swaps ``determine_result_type`` for ``assess_quality`` here, the summary would be discarded
    and ``assert summary is not None`` would fail.
    """
    filing_id = seed_company_filing(filing_type="10-Q")

    # XBRL values that appear NOWHERE in CANONICAL_PAYLOAD's business_overview / financial_highlights.
    ungrounded = {
        "revenue": {"current": {"value": 987654321.0}},
        "net_income": {"current": {"value": 123456789.0}},
    }
    from app.services import facts_service

    with background_boundaries():  # summarize -> CANONICAL_PAYLOAD (4/7 -> clears full threshold)
        with patch.object(
            summary_generation_service.xbrl_service,
            "get_xbrl_data",
            AsyncMock(return_value={"facts": "present"}),
        ), patch.object(
            summary_generation_service.xbrl_service,
            "extract_standardized_metrics",
            lambda data: ungrounded,
        ), patch.object(facts_service, "process_filing_facts", MagicMock()):
            await generate_summary_background(filing_id, None)

    with SessionLocal() as db:
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        assert summary is not None  # FULL result cached despite ungrounded financials
        assert summary.raw_summary["result_type"] == "full"

    # Divergence proof: on the identical (payload, xbrl) pair the two verdict functions disagree,
    # which is exactly what makes the end-to-end assertion above sensitive to an S1 swap.
    assert determine_result_type(CANONICAL_PAYLOAD)[0] == "full"
    grounded_verdict = assess_quality(CANONICAL_PAYLOAD, ungrounded)
    assert grounded_verdict["tier"] == "partial"
    assert grounded_verdict["numeric_grounded"] is False


# --- usage / quota semantics ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_usage_incremented_once_on_full_success_with_user_id():
    """A successful full result for a signed-in user consumes quota exactly once:
    ``increment_user_usage`` is called a single time with ``(user.id, current_month, session)``."""
    user_id = _seed_user()
    filing_id = seed_company_filing(filing_type="10-Q")

    spy = MagicMock()
    with background_boundaries(), patch.object(
        summary_generation_service, "increment_user_usage", spy
    ):
        await generate_summary_background(filing_id, user_id)

    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).first() is not None
    spy.assert_called_once()
    called_user_id, called_month, _session = spy.call_args.args
    assert called_user_id == user_id
    assert called_month == summary_generation_service.get_current_month()


@pytest.mark.asyncio
async def test_partial_result_is_discarded_and_consumes_no_usage():
    """A low-coverage result verdicts "partial" and is DISCARDED: no Summary row is written, and —
    even for a signed-in user — ``increment_user_usage`` is NOT called (the partial ``return`` at
    summary_generation_service.py:799 preempts the increment at :846-850, so a partial consumes no
    quota). The SSE path persists partials with a quality tier; S1 unification must reconcile this.
    """
    user_id = _seed_user()
    filing_id = seed_company_filing(filing_type="10-Q")

    # Empty sections => 0/7 coverage => determine_result_type returns "partial".
    partial_payload = {
        "status": "complete",
        "business_overview": "",
        "financial_highlights": None,
        "risk_factors": [],
        "management_discussion": "",
        "key_changes": "",
        "raw_summary": {"sections": {}, "section_coverage": {"covered_count": 0, "total_count": 7}},
    }
    spy = MagicMock()
    with background_boundaries(payload=partial_payload), patch.object(
        summary_generation_service, "increment_user_usage", spy
    ):
        await generate_summary_background(filing_id, user_id)

    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).first() is None
    spy.assert_not_called()


# --- zero PostHog funnel events on precompute -------------------------------------------------

@pytest.mark.asyncio
async def test_precompute_emits_zero_posthog_funnel_events():
    """A precompute run (``user_id=None``) captures ZERO PostHog funnel events. Funnel telemetry
    lives ONLY on the SSE path (``summary_pipeline.capture_funnel_event``, 4 call sites); the
    background path does not import or call the seam at all. Two guards pin this:
      (1) static — ``capture_funnel_event`` is not even a name in this module;
      (2) end-to-end — no funnel event fires during the run, including via the ``summary_pipeline``
          seam that S1's unification would route precompute through.
    If S1 routes precompute through ``stream_filing_summary``, funnel events would fire for an
    anonymous precompute and both guards would trip.
    """
    # (1) Static guard: the funnel seam is not imported into the background module.
    assert not hasattr(summary_generation_service, "capture_funnel_event")

    from app.services import posthog_client, summary_pipeline

    filing_id = seed_company_filing(filing_type="10-Q")
    spy = MagicMock()
    with background_boundaries(), patch.object(
        summary_pipeline, "capture_funnel_event", spy
    ), patch.object(posthog_client, "capture_funnel_event", spy):
        await generate_summary_background(filing_id, None)

    # (2) End-to-end guard: no funnel event fired for the anonymous precompute.
    spy.assert_not_called()
    with SessionLocal() as db:
        assert db.query(Summary).filter(Summary.filing_id == filing_id).first() is not None


# --- S1 decision A: flag-ON, generate_summary_background DRAINS stream_filing_summary -----------
# The pins above characterize the UNCHANGED legacy body (flag off = today's prod). These pin the
# NEW drained path — the reconciliation semantics (filing-only, zero-funnel, partial-persistence)
# are INHERITED from the SSE orchestrator and only apply when the flag is on. The legacy body's
# YoY/verdict/discard code is untouched here; its deletion rides the post-soak old-path removal.

@pytest.mark.asyncio
async def test_flag_on_drains_pipeline_filing_only_and_zero_funnel(monkeypatch):
    """Flag ON: generate_summary_background drains stream_filing_summary headless, so a 10-K (even
    with a prior filing on record) is FILING-ONLY — the SSE path passes previous_filings=None — a
    Summary is persisted, and a precompute run (user_id=None) emits ZERO funnel events (the drain
    suppresses funnel telemetry via emit_funnel_telemetry=False)."""
    from app.services import summary_pipeline

    monkeypatch.setattr(summary_generation_service.settings, "USE_PIPELINE_FOR_BACKGROUND", True)
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
async def test_flag_on_persists_partial(monkeypatch):
    """Flag ON: the drained pipeline PERSISTS partials (AI_QUALITY_GATE always saves the row with a
    quality tier), reconciling the legacy body's discard-on-partial (pinned above under flag-off).
    A 2/9 structured snapshot is partial under the flag-on 4/9 bar, yet the row is still written."""
    monkeypatch.setattr(summary_generation_service.settings, "USE_PIPELINE_FOR_BACKGROUND", True)
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
