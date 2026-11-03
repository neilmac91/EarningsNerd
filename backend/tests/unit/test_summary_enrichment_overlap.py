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
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.database import SessionLocal, engine
from app.models import Base, Filing, Summary
from app.services import facts_service, summary_pipeline
from app.services.request_work import RequestWork
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
STEP_5 = {"type": "progress", "stage": "summarizing", "message": "Step 5: Generating investor-focused summary...",
          "percent": 50}  # the join's last frame: the generation stage begins after it
JOIN_TIMEOUT = 0.2  # seconds; the stand-in excerpt build is held past it, so the join times out
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
    deadline; the overlapped order starts it once the excerpt build has ended, inside the join."""
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
    after the join's last progress frame and before the provider request, with the error frame the
    serial order sent (checked against main), and no summary row."""
    filing_id = _seed_with_period()
    statement = MagicMock(side_effect=RuntimeError("statement parse broke"))
    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "acquire_statement_context", statement):
        events = await _drain(filing_id)

    statement.assert_called_once()
    summarize.assert_not_awaited()
    assert events[-1] == {"type": "error", "message": "We could not generate this summary. Try again shortly."}
    assert events[-2] == STEP_5
    assert [e["type"] for e in events].count("error") == 1
    with SessionLocal() as db:
        assert db.query(Summary).filter_by(filing_id=filing_id).first() is None


@pytest.mark.asyncio
async def test_a_disconnect_during_the_excerpt_build_cancels_the_pending_statement_parse():
    """``release()`` cancels the statement task with the run's other owned tasks. The client goes
    away while the excerpt build still runs, so the parse is still waiting for it, and it must never
    start. Left unowned, it would start once the build's task is cancelled and run on past the
    release of the generation slot and leadership."""
    filing_id = _seed_with_period()
    excerpt_entered = threading.Event()
    excerpt_may_finish = threading.Event()
    statement_called = threading.Event()

    class ReleasingWork(RequestWork):
        async def drain(self):
            # release() reaches the drain after it has cancelled the owned tasks; the build's
            # worker thread may finish only now.
            excerpt_may_finish.set()
            await super().drain()

    def excerpt(session, filing, text, **kwargs):
        excerpt_entered.set()
        excerpt_may_finish.wait(SIGNAL_DEADLINE)  # released by the drain, or by the test's cleanup
        return "EXCERPT"

    def statement(source_html, **kwargs):
        statement_called.set()
        return deepcopy(STATEMENT)

    async def consume(stream):
        async for _ in stream:
            pass

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt), \
            patch.object(summary_pipeline, "acquire_statement_context", statement), \
            patch.object(summary_pipeline, "RequestWork", ReleasingWork):
        stream = summary_pipeline.stream_filing_summary(
            filing_id=filing_id, current_user=None, user_id=None, telemetry_distinct_id="offline",
            telemetry_entry_point=None, telemetry_ctx={}, emit_funnel_telemetry=False,
        )
        consumer = asyncio.create_task(consume(stream))
        try:
            assert await asyncio.to_thread(excerpt_entered.wait, SIGNAL_DEADLINE)
            consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
            assert consumer.cancelled()
            assert not await asyncio.to_thread(statement_called.wait, ORDER_WINDOW)
        finally:
            excerpt_may_finish.set()
            await asyncio.gather(consumer, return_exceptions=True)
        summarize.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_join_timeout_leaves_the_parse_to_the_generation_stage_as_before(caplog):
    """The join times out on an excerpt build that has not returned, and cancels its task. The
    statement task then does not parse; the generation stage parses after the join, where main
    always did, and its result still reaches the provider."""
    import logging

    caplog.set_level(logging.WARNING, logger="app.services.summary_pipeline")
    filing_id = _seed_with_period()
    build_may_finish = threading.Event()
    seen: dict = {}

    def excerpt(session, filing, text, **kwargs):
        build_may_finish.wait(SIGNAL_DEADLINE)  # outlives the join; released by the provider
        return "EXCERPT"

    def statement(source_html, **kwargs):
        seen["calls"] = seen.get("calls", 0) + 1
        seen["build_still_running"] = not build_may_finish.is_set()
        return deepcopy(STATEMENT)

    async def provider(*args, **kwargs):
        build_may_finish.set()
        return deepcopy(CANONICAL_PAYLOAD)

    with stream_boundaries(payload=deepcopy(CANONICAL_PAYLOAD)) as summarize, \
            patch.object(summary_pipeline, "get_or_cache_excerpt", excerpt), \
            patch.object(summary_pipeline, "acquire_statement_context", statement), \
            patch.object(summary_pipeline, "CONTEXT_ENRICHMENT_TIMEOUT_SECONDS", JOIN_TIMEOUT):
        summarize.side_effect = provider
        events = await _drain(filing_id)

    _assert_complete(events)
    assert seen == {"calls": 1, "build_still_running": True}
    assert summarize.await_args.kwargs["statement_source"] == STATEMENT
    assert any("Excerpt not built by the enrichment join" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("build_ends", ["returned", "raised", "cancelled"])
async def test_the_statement_task_parses_after_its_excerpt_task_unless_that_was_cancelled(build_ends):
    """The task waits for the excerpt task, then parses, whether the build returned or raised (the
    join reads that error). A cancelled build means the join timed out or the run is ending: the
    task returns ``STATEMENT_DEFERRED`` without parsing, and the generation stage, if the run
    reaches it, parses there as main did. Deterministic: no stream, no thread scheduling."""
    from app.services.summary_stages import enrichment

    calls: list = []
    build_may_end = asyncio.Event()

    def statement(source_html, **kwargs):
        calls.append(source_html)
        return deepcopy(STATEMENT)

    async def build():
        await build_may_end.wait()
        if build_ends == "raised":
            raise RuntimeError("excerpt build failed")
        return "EXCERPT"

    run = SimpleNamespace(
        filing_text=DOC_TEXT, filing_accession_number="0000000000-26-000001",
        filing_document_url="https://www.sec.gov/Archives/edgar/data/1/000000000026000001/d.htm",
        filing_type="10-K", filing_fields={"report_period": datetime(2025, 12, 31, tzinfo=timezone.utc)},
        worker_owner=RequestWork(enabled=False), excerpt_task=asyncio.create_task(build()), statement_task=None,
    )
    with patch.object(summary_pipeline, "acquire_statement_context", statement):
        enrichment.start_statement_context(run)
        for _ in range(3):
            await asyncio.sleep(0)
        assert calls == [] and not run.statement_task.done()  # waiting for the build
        if build_ends == "cancelled":
            run.excerpt_task.cancel()
        else:
            build_may_end.set()
        result = await run.statement_task
    await asyncio.gather(run.excerpt_task, return_exceptions=True)

    if build_ends == "cancelled":
        assert result is enrichment.STATEMENT_DEFERRED and calls == []
    else:
        assert result == STATEMENT and calls == [DOC_TEXT]


def test_release_cancels_every_task_the_run_owns():
    """Every ``asyncio.Task`` field of ``GenerationRun`` is named in ``release()``, which cancels and
    drains the run's owned tasks (the provider task in its own branch). A task field left out of it,
    as ``statement_task`` would be, outlives its run."""
    import ast
    import inspect

    from app.services.summary_stages import generation_run

    tree = ast.parse(inspect.getsource(generation_run))
    run_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GenerationRun")
    task_fields = {
        n.target.id for n in run_class.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and "Task" in ast.unparse(n.annotation)
    }
    release = next(n for n in run_class.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "release")
    named = {
        n.attr for n in ast.walk(release)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self"
    }
    assert {"statement_task", "excerpt_task", "xbrl_task", "sections_task"} <= task_fields
    assert task_fields <= named, f"owned task fields release() never names: {sorted(task_fields - named)}"
