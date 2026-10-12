"""Pre-refactor characterization anchor for ``stream_filing_summary`` — the finalize group.

These tests PIN the orchestrator's behaviour after the provider returns (the measurement-channel
log lines keyed off the quality verdict and the audit dicts the payload carries, the UNIQUE(filing_id)
concurrent-writer resolution inside ``save_summary_sync``, and the completion-time usage count for a
user id with no account row) exactly as it runs today, so the upcoming decomposition into stage
modules can prove ZERO observable change. Every assertion is on an observable: yielded event dicts,
DB rows, mock call lists, the in-flight registry, the generation semaphore, and the exact log text
the code formats (``record.getMessage()`` for the ``%``-style counters).
"""
import logging
import re
from contextlib import nullcontext
from copy import deepcopy
from typing import Optional
from unittest.mock import ANY, MagicMock, call, patch

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Filing, FilingContentCache, Summary, UserUsage
from app.services import summary_pipeline
from app.services.summary_generation_service import MACHINE_COVERABLE_SECTIONS
from app.services.summary_pipeline import EVENT_GENERATION_FAILED, EVENT_GENERATION_STARTED
from app.services.summary_schema import TRACKED_SECTIONS_V2
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

LOGGER = "app.services.summary_pipeline"
GENERIC_FAILURE = {"type": "error", "message": "Unable to retrieve this filing at the moment — please try again shortly."}
# The seven un-prefixed ``%``-style counters the finalize stage can emit, in source order.
CHANNELS = (
    "figure_trace_untraceable", "summary_quality_partial", "summary_quality_full_machine_only",
    "attribution_unverified", "table_cell_units", "forward_quote_unverified", "evidence_snap",
)
PROSE = "Revenue reached $987.6 million this year."
GROUNDING_EXCERPT = "Total assets were 42 at year end."
MISSING_USER_ID = 999_999_999
STAGE_TIMING = r"\d+\.\d\ds"
BASE_BREAKDOWN = (
    f"fetch_document:{STAGE_TIMING}, context_enrichment:{STAGE_TIMING}, "
    f"generate_summary:{STAGE_TIMING}, persist_summary:{STAGE_TIMING}"
)


@pytest.fixture(autouse=True)
def _tables_and_registry():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


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


def _channel_lines(caplog) -> list[str]:
    """Every rendered measurement-channel line, in emit order (the channels not under test must stay silent)."""
    return [m for level, m in _pipeline_logs(caplog) if level == logging.INFO and m.split(" ", 1)[0] in CHANNELS]


def _stages(record_progress: MagicMock) -> list[str]:
    """``record_progress(session, filing_id, stage, ...)`` — the stage is the third positional."""
    return [c.args[2] for c in record_progress.call_args_list]


def _company_cik(filing_id: int) -> str:
    with SessionLocal() as db:
        return db.get(Filing, filing_id).company.cik


def _summary_rows(filing_id: int) -> list[Summary]:
    with SessionLocal() as db:
        return db.query(Summary).filter(Summary.filing_id == filing_id).order_by(Summary.id).all()


def _content_cache(filing_id: int) -> Optional[FilingContentCache]:
    with SessionLocal() as db:
        return db.get(FilingContentCache, filing_id)


def _complete(events: list[dict]) -> dict:
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    assert [e for e in events if e["type"] in {"complete", "partial", "error"}] == [events[-1]]
    return events[-1]


# ------------------------------------------------- E1: figure-trace channel (untraceable dollar figure)

@pytest.mark.asyncio
async def test_untraceable_dollar_figure_is_counted_on_the_figure_trace_channel(caplog):
    """A model-prose dollar figure that grounds in neither XBRL nor the excerpt is counted once on
    the ``figure_trace_untraceable`` channel (count first, flag, filing, empty SIC, canonical key);
    with the gate off it stays advisory — the verdict is still ``full`` and the stream completes."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    payload = deepcopy(CANONICAL_PAYLOAD)
    payload["business_overview"] = PROSE
    payload["raw_summary"]["sections"] = {"the_print": {"headline": PROSE}}
    with stream_boundaries(payload=payload), \
            patch.object(summary_pipeline, "get_or_cache_excerpt", lambda *a, **k: GROUNDING_EXCERPT), \
            patch.object(summary_pipeline.settings, "AI_FIGURE_TRACE_GATE", False):
        events = await _drain(filing_id)

    assert _channel_lines(caplog) == [
        f"figure_trace_untraceable count=1 flag=False filing_id={filing_id} sic= figures=987.6m"
    ]
    complete = _complete(events)
    assert events[-2] == {"type": "chunk", "content": PROSE}
    (stored,) = _summary_rows(filing_id)
    assert stored.id == complete["summary_id"]
    assert stored.raw_summary["quality"]["figures_untraceable"] == ["987.6m"]
    assert stored.raw_summary["quality"]["tier"] == "full"
    assert filing_id not in summary_pipeline._inflight_generations


# ---------------------------------------------- E1: machine-only channel (full tier, zero model sections)

@pytest.mark.asyncio
async def test_full_verdict_on_machine_sections_alone_is_counted_on_the_machine_only_channel(caplog):
    """A per-section snapshot covering exactly the four machine-coverable sections (and no model
    section — Risks is recounted from the finalized projection, so the risk list is empty) tiers
    ``full`` at 4/9 and is counted once on ``summary_quality_full_machine_only`` with the CIK."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    payload = deepcopy(CANONICAL_PAYLOAD)
    payload["risk_factors"] = []
    payload["raw_summary"] = {"sections": {}, "section_coverage": {
        "per_section": {section: section in MACHINE_COVERABLE_SECTIONS for section in TRACKED_SECTIONS_V2},
    }}
    with stream_boundaries(payload=payload):
        events = await _drain(filing_id)

    assert _channel_lines(caplog) == [
        f"summary_quality_full_machine_only filing_id={filing_id} cik={_company_cik(filing_id)} sic= covered=4/9"
    ]
    complete = _complete(events)
    (stored,) = _summary_rows(filing_id)
    assert stored.id == complete["summary_id"]
    assert stored.raw_summary["quality"]["machine_sections_only"] is True
    assert stored.raw_summary["quality"]["tier"] == "full"
    assert stored.raw_summary["section_coverage"]["covered"] == [
        "earnings_quality", "value_drivers", "segments", "balance_sheet_liquidity",
    ]
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------------ E1: audit-dict channels carried by raw_summary

AUDIT_CHANNELS = [
    pytest.param(
        "attribution_audit",
        {"unverified": [{"slot": "revenue_driver"}, {"slot": None}], "checked": 3, "dropped": [],
         "decider": "rules", "verification": {"decided": 2, "error": None}},
        "AI_ATTRIBUTION_GATE",
        "attribution_unverified count=2 checked=3 dropped=0 decider=rules decided=2 verify_error= "
        "flag=False filing_id={filing_id} sic= slots=revenue_driver|?",
        id="attribution_unverified",
    ),
    pytest.param(
        "table_cell_unit_audit",
        {"restored_count": 2, "unresolved_count": 1, "unresolved": [{"reason": "ambiguous_scale"}]},
        None,
        "table_cell_units restored=2 unresolved=1 filing_id={filing_id} sic= reasons=ambiguous_scale",
        id="table_cell_units",
    ),
    pytest.param(
        "forward_quote_audit",
        {"unverified": [{"speaker": "CEO"}, {}], "near_miss": 1, "dropped": []},
        "AI_FORWARD_QUOTE_GATE",
        "forward_quote_unverified count=2 near_miss=1 dropped=0 flag=False filing_id={filing_id} sic= speakers=CEO|?",
        id="forward_quote_unverified",
    ),
    pytest.param(
        "evidence_snap_audit",
        {"checked": 4, "exact": 2, "would_snap": [1], "snapped": [], "left": [1]},
        "AI_EVIDENCE_SNAP",
        "evidence_snap checked=4 exact=2 would_snap=1 snapped=0 left=1 flag=False filing_id={filing_id}",
        id="evidence_snap",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("audit_key, audit, flag_name, template", AUDIT_CHANNELS)
async def test_audit_dict_survives_finalization_and_emits_its_measurement_line(
    caplog, audit_key: str, audit: dict, flag_name: Optional[str], template: str,
):
    """An audit dict on ``raw_summary`` passes through the finalizer untouched, is rendered once on
    its own channel (counts first, ``?`` for a missing slot/speaker, the gate flag as configured, the
    empty SIC) while every other channel stays silent, and is persisted verbatim on the Summary row."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    payload = deepcopy(CANONICAL_PAYLOAD)
    payload["raw_summary"][audit_key] = deepcopy(audit)
    flag_off = patch.object(summary_pipeline.settings, flag_name, False) if flag_name else nullcontext()
    with stream_boundaries(payload=payload), flag_off:
        events = await _drain(filing_id)

    assert _channel_lines(caplog) == [template.format(filing_id=filing_id)]
    complete = _complete(events)
    (stored,) = _summary_rows(filing_id)
    assert stored.id == complete["summary_id"]
    assert stored.raw_summary[audit_key] == audit
    assert filing_id not in summary_pipeline._inflight_generations


# ------------------------------------------------- E2: concurrent writer wins on UNIQUE(filing_id)

@pytest.mark.asyncio
async def test_concurrent_writer_that_commits_first_is_served_instead_of_erroring(caplog):
    """When another writer commits this filing's Summary between the pipeline's add and its commit,
    the UNIQUE(filing_id) IntegrityError is swallowed: the pipeline rolls its own insert (and the
    content-cache upsert riding in the same transaction) back, serves the winner's row id in the
    complete event, records ``completed`` and never logs an error."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    rival: dict = {"fired": False, "winner_id": None}

    def commit_a_rival_summary(session: Session, flush_context, instances) -> None:
        if rival["fired"] or not any(isinstance(o, Summary) and o.filing_id == filing_id for o in session.new):
            return
        rival["fired"] = True  # before the rival flush re-enters this listener
        with SessionLocal() as other:
            winner = Summary(filing_id=filing_id, business_overview="WINNER")
            other.add(winner)
            other.commit()
            rival["winner_id"] = winner.id

    record_progress = MagicMock(wraps=summary_pipeline.record_progress)
    event.listen(Session, "before_flush", commit_a_rival_summary)
    try:
        with stream_boundaries(), patch.object(summary_pipeline, "record_progress", record_progress):
            events = await _drain(filing_id)
    finally:
        event.remove(Session, "before_flush", commit_a_rival_summary)

    assert rival["fired"] is True
    assert _complete(events) == {"type": "complete", "summary_id": rival["winner_id"], "percent": 100}
    assert [(row.id, row.business_overview) for row in _summary_rows(filing_id)] == [(rival["winner_id"], "WINNER")]
    assert _content_cache(filing_id) is None
    assert _stages(record_progress) == ["fetching", "parsing", "analyzing", "summarizing", "summarizing", "completed"]
    assert [m for level, m in _pipeline_logs(caplog) if level >= logging.WARNING] == []
    assert filing_id not in summary_pipeline._inflight_generations


@pytest.mark.asyncio
async def test_integrity_error_without_a_winner_row_fails_the_stream_generically(caplog):
    """An IntegrityError on the Summary insert with NO competing row to serve is re-raised into the
    generic failure path: the ERROR log carries the exception text with a traceback, progress is
    recorded as ``error`` with the first 200 characters, the failed funnel event carries the same
    text, nothing is persisted, and the only terminal is the generic retrieval error."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    duplicate = IntegrityError("stmt", {}, Exception("dup"))

    def reject_the_summary_insert(session: Session, flush_context, instances) -> None:
        if any(isinstance(o, Summary) and o.filing_id == filing_id for o in session.new):
            raise duplicate

    record_progress = MagicMock(wraps=summary_pipeline.record_progress)
    funnel = MagicMock()
    semaphore = summary_pipeline._get_generation_semaphore()
    slots_before = semaphore._value
    event.listen(Session, "before_flush", reject_the_summary_insert)
    try:
        with stream_boundaries(), \
                patch.object(summary_pipeline, "record_progress", record_progress), \
                patch.object(summary_pipeline, "capture_funnel_event", funnel):
            events = await _drain(filing_id, emit_funnel_telemetry=True)
    finally:
        event.remove(Session, "before_flush", reject_the_summary_insert)

    assert events[-1] == GENERIC_FAILURE
    assert [e["type"] for e in events if e["type"] != "progress"] == ["error"]
    error_records = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.ERROR]
    assert [r.getMessage() for r in error_records] == [f"[stream:{filing_id}] Error in streaming summary: {duplicate}"]
    assert error_records[0].exc_info is not None and error_records[0].exc_info[1] is duplicate
    assert _stages(record_progress) == ["fetching", "parsing", "analyzing", "summarizing", "summarizing", "error"]
    assert record_progress.call_args_list[-1] == call(ANY, filing_id, "error", error=str(duplicate)[:200])
    assert funnel.call_args_list == [
        call("offline", EVENT_GENERATION_STARTED, entry_point=None),
        call("offline", EVENT_GENERATION_FAILED, duration_ms=ANY, result_type="error", entry_point=None,
             error=str(duplicate)[:200]),
    ]
    assert _summary_rows(filing_id) == []
    assert _content_cache(filing_id) is None
    assert semaphore._value == slots_before
    assert filing_id not in summary_pipeline._inflight_generations


# --------------------------------------------- E3: completion-time usage count without an account row

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_id, breakdown",
    [(MISSING_USER_ID, f"{BASE_BREAKDOWN}, usage_tracking:{STAGE_TIMING}"), (None, BASE_BREAKDOWN)],
    ids=["missing_user_times_the_stage", "no_user_skips_the_stage"],
)
async def test_headless_completion_count_without_an_account_row(caplog, user_id: Optional[int], breakdown: str):
    """A headless drain with a ``user_id`` that has no User row runs the completion-time count stage
    (it appears in the timing log) but increments nothing and writes no UserUsage row; with no
    ``user_id`` the stage is skipped and the timing log ends at ``persist_summary``. Both complete and
    persist the normal content-cache row (the control for the rolled-back upsert above)."""
    caplog.set_level(logging.INFO, logger=LOGGER)
    filing_id = seed_company_filing()
    increment = MagicMock()
    with stream_boundaries(), patch.object(summary_pipeline, "increment_user_usage", increment):
        events = await _drain(filing_id, user_id=user_id)

    complete = _complete(events)
    increment.assert_not_called()
    with SessionLocal() as db:
        assert db.query(UserUsage).filter_by(user_id=MISSING_USER_ID).count() == 0
    assert (logging.INFO, f"[stream:{filing_id}] Internal caller (no user) — per-user quota not applicable.") in _pipeline_logs(caplog)
    finished = [m for level, m in _pipeline_logs(caplog) if level == logging.INFO and "pipeline finished in" in m]
    assert len(finished) == 1
    assert re.fullmatch(rf"\[stream:{filing_id}\] pipeline finished in {STAGE_TIMING} \({breakdown}\)", finished[0]), finished[0]
    (stored,) = _summary_rows(filing_id)
    assert stored.id == complete["summary_id"]
    assert _content_cache(filing_id).critical_excerpt == "EXCERPT"
    assert filing_id not in summary_pipeline._inflight_generations
