"""The statement-context parse runs inside the enrichment join's wait on XBRL, not after the join.

It reads nothing the join produces, and the generation stage used to start it only after the join
had waited out XBRL, serial work between the end of the XBRL fetch and the provider request. The
overlap and the orderings are proved by signal, never by elapsed time
(``lessons/ops-one-test-process-per-worktree.md``): a mock waits for a signal that only the intended
order can send (or that only the wrong order sends, within a window), under a deadline far above the
moment the signal takes. The join budget is raised past that deadline so the join cannot time out
first. The XBRL write stays inside the join, pinned here too: moved out, it doubled pool waits.
"""
import asyncio
import threading
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary
from app.services import facts_service, summary_pipeline
from tests.support.summary_stream_harness import (
    CANONICAL_PAYLOAD,
    reset_inflight,
    seed_company_filing,
    stream_boundaries,
)

DOC_TEXT = "FILING DOCUMENT TEXT " * 40  # what stream_boundaries' document fetch returns
XBRL = {
    "revenue": [{"value": 996347000000, "period": "2025-12-31", "period_start": "2025-01-01",
                 "currency": "USD", "form": "10-K", "raw_tag": "us-gaap:Revenues"}],
    "reporting_currency": "USD",
}
STATEMENT = {"table_path": "/html/body/table[3]", "disclosure_status": "complete"}
SIGNAL_DEADLINE = 10.0  # seconds; the concurrent order sends each signal within milliseconds
JOIN_BUDGET = 60.0  # above SIGNAL_DEADLINE, so a serial order fails at the mock, not at the join
ORDER_WINDOW = 2.0  # seconds a stand-in step gives the wrong order to show itself


@pytest.fixture(autouse=True)
def _tables_and_registry():
    Base.metadata.create_all(bind=engine)
    reset_inflight()
    yield
    reset_inflight()


def _seed_with_period() -> int:
    filing_id = seed_company_filing(filing_type="10-K")
    with SessionLocal() as db:
        db.get(Filing, filing_id).period_end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)
        db.commit()
    return filing_id


def _filing_fields(filing_id: int) -> tuple[str, str]:
    with SessionLocal() as db:
        filing = db.get(Filing, filing_id)
        return filing.accession_number, filing.document_url


async def _drain(filing_id: int) -> list[dict]:
    """Headless drain shape (the background/cron path)."""
    return [event async for event in summary_pipeline.stream_filing_summary(
        filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
        telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
    )]


def _assert_complete(events: list[dict]) -> int:
    assert events[-1] == {"type": "complete", "summary_id": events[-1]["summary_id"], "percent": 100}
    return events[-1]["summary_id"]


@pytest.mark.asyncio
async def test_statement_context_runs_while_the_join_waits_on_xbrl():
    """The XBRL fetch does not return until the statement parse has started. The serial order
    started the parse only after the join had the XBRL result, so the fetch would wait out its
    deadline; the overlapped order starts it beside the excerpt, inside the join."""
    filing_id = _seed_with_period()
    accession, document_url = _filing_fields(filing_id)
    loop = asyncio.get_running_loop()
    statement_started = asyncio.Event()
    seen: dict = {}

    def statement(source_html, *, accession, document_url, form, report_period):
        seen["args"] = (source_html, accession, document_url, form, report_period)
        loop.call_soon_threadsafe(statement_started.set)
        return deepcopy(STATEMENT)

    async def xbrl(accession_number, cik, refresh=False):
        try:
            async with asyncio.timeout(SIGNAL_DEADLINE):
                await statement_started.wait()
            seen["statement_began_inside_the_join"] = True
        except TimeoutError:
            seen["statement_began_inside_the_join"] = False
        return deepcopy(XBRL)

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "acquire_statement_context", statement), \
            patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", xbrl), \
            patch.object(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", JOIN_BUDGET):
        events = await _drain(filing_id)

    _assert_complete(events)
    assert seen["statement_began_inside_the_join"] is True
    assert seen["args"] == (DOC_TEXT, accession, document_url, "10-K", "2025-12-31")
    summarize.assert_awaited_once()
    assert summarize.await_args.kwargs["statement_source"] == STATEMENT
    assert summarize.await_args.kwargs["xbrl_metrics"] == summary_pipeline.xbrl_service.extract_standardized_metrics(
        deepcopy(XBRL))


@pytest.mark.asyncio
async def test_the_statement_parse_waits_for_its_own_excerpt_build():
    """The excerpt build holds a pooled connection through its CPU work, so on one vCPU a parse
    beside it stretches that hold (the harness saw pool waits rise under load). The build here
    gives a parse that starts beside it a window (ORDER_WINDOW) to show itself; the parse must
    instead start after the build has returned."""
    filing_id = _seed_with_period()
    statement_started = threading.Event()
    excerpt_returned = threading.Event()
    seen: dict = {}

    def excerpt(session, filing, text, **kwargs):
        seen["parse_ran_during_build"] = statement_started.wait(ORDER_WINDOW)
        excerpt_returned.set()
        return "EXCERPT"

    def statement(source_html, *, accession, document_url, form, report_period):
        statement_started.set()
        seen["build_had_returned"] = excerpt_returned.is_set()
        return deepcopy(STATEMENT)

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt), \
            patch.object(summary_pipeline, "acquire_statement_context", statement):
        events = await _drain(filing_id)

    _assert_complete(events)
    assert seen == {"parse_ran_during_build": False, "build_had_returned": True}
    assert summarize.await_args.kwargs["statement_source"] == STATEMENT


@pytest.mark.asyncio
async def test_the_xbrl_write_finishes_before_the_provider_request():
    """The XBRL write (xbrl_data and its facts) stays inside the join. Moved beside the generation it
    lands on the provider start's charge write, two pooled connections at once per run, and the
    harness's load run doubled its pool-wait time on the four-slot pool. The write here gives a
    provider request that starts during it a window (ORDER_WINDOW) to show itself."""
    filing_id = seed_company_filing(filing_type="10-K")
    provider_started = threading.Event()
    seen: dict = {}

    def facts(session, filing, *, standardized):
        seen["provider_started_during_write"] = provider_started.wait(ORDER_WINDOW)

    async def provider(*args, **kwargs):
        provider_started.set()
        return deepcopy(CANONICAL_PAYLOAD)

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", AsyncMock(return_value=deepcopy(XBRL))), \
            patch.object(facts_service, "process_filing_facts", facts):
        summarize.side_effect = provider
        events = await _drain(filing_id)

    _assert_complete(events)
    assert seen == {"provider_started_during_write": False}
    with SessionLocal() as db:
        assert db.get(Filing, filing_id).xbrl_data == XBRL


@pytest.mark.asyncio
async def test_a_statement_context_error_still_ends_the_run_before_the_provider_request():
    """Started early, awaited where the call used to be: the error ends the run at the same point,
    with the same error frame and no provider request, summary row or provider charge."""
    filing_id = _seed_with_period()
    statement = MagicMock(side_effect=RuntimeError("statement parse broke"))
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "acquire_statement_context", statement):
        events = await _drain(filing_id)

    statement.assert_called_once()
    summarize.assert_not_awaited()
    assert events[-1]["type"] == "error"
    assert [e["type"] for e in events].count("error") == 1
    with SessionLocal() as db:
        assert db.query(Summary).filter_by(filing_id=filing_id).first() is None
