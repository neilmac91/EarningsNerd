"""Generation stage: the provider call, metering at provider start, heartbeats and the fallback.

Prepares the provider inputs (preview queue, statement context, 6-K classification), starts the
``summarize_filing`` task under the provider-start signal that converts the admission lease into a
counted unit, streams heartbeats or section previews while it runs, falls back to the deterministic
XBRL summary on the in-stage deadline, and turns an error payload into the terminal error event.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator, Optional

from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


async def generate(run: GenerationRun) -> AsyncIterator[dict]:
    """Run the provider task with heartbeats, metering and the deterministic fallback."""
    filing_id = run.filing_id

    # A5: when STREAM_SECTION_REVEAL is on, stream the extraction and push progressive section
    # previews onto a queue that the heartbeat loop drains below. The callback can't yield from
    # this generator, so the queue decouples them. Off by default → behaviour unchanged.
    preview_queue: Optional[asyncio.Queue] = (
        asyncio.Queue() if pipeline.settings.STREAM_SECTION_REVEAL else None
    )
    summary_stream_cb = None
    if preview_queue is not None:
        async def summary_stream_cb(preview_md: str) -> None:
            preview_queue.put_nowait(preview_md)

    # Now run AI summarization (with excerpt/XBRL if available)
    # Wrap in task to enable heartbeat loop while waiting
    statement_source = None
    report_period = run.filing_fields.get("report_period")
    if run.filing_text and report_period is not None:
        with run.worker_owner.activate():
            statement_source = await pipeline.run_in_threadpool(
                pipeline.acquire_statement_context, run.filing_text, accession=run.filing_accession_number,
                document_url=run.filing_document_url, form=run.filing_type,
                report_period=report_period.date().isoformat(),
            )
    if run.is_six_k:
        # W3-8b: deterministic pre-classification of the final 6-K grounding selects the prompt
        # variant and is recorded on the stored summary for audit. Placed after every grounding
        # branch (fresh exhibit fetch, primary-document fallback, or a valid content cache whose
        # text arrives as the excerpt) so a cached or regenerated 6-K is classified too.
        sixk = pipeline.classify_sixk_text(run.filing_text or run.excerpt)
        run.sixk_class, run.sixk_class_audit = sixk.sixk_class, sixk.as_audit()
    if run.request_evidence is not None:
        run.request_evidence.summary_service_invoked = True

    # Metering point: see ``GenerationRun.begin_charge`` — the held admission lease becomes a
    # counted unit when the dispatcher signals that the provider request is issued.
    run.provider_started = asyncio.Event()

    with pipeline.provider_start_signal(run.on_provider_start), run.worker_owner.activate():
        run.summary_task = asyncio.create_task(pipeline.openai_service.summarize_filing(
            run.filing_text,
            run.company_name,
            run.filing_type,
            xbrl_metrics=run.xbrl_metrics,
            filing_excerpt=run.excerpt,
            stream_cb=summary_stream_cb,
            **({"statement_source": statement_source} if statement_source else {}),
            **({"sixk_class": run.sixk_class, "sixk_class_audit": run.sixk_class_audit} if run.sixk_class else {}),
        ))
    run.provider_started_waiter = asyncio.ensure_future(run.provider_started.wait())

    SUMMARIZE_MESSAGES = [
        "Analyzing financial highlights...",
        "Cross-referencing with XBRL data...",
        "Extracting key metrics from MD&A...",
        "Identifying significant risk factors...",
        "Synthesizing investment insights...",
        "Reviewing guidance and outlook...",
    ]
    summarize_heartbeat_index = 0
    run.summary_payload = None
    provider_fallback = False  # the payload is the deterministic XBRL fallback, not a provider result

    # Build fallback kwargs once to avoid duplication (DRY principle)
    fallback_kwargs = {
        "xbrl_data": run.xbrl_metrics,
        "company_name": run.company_name,
        "filing_date": run.filing_fields["filing_date"].isoformat() if run.filing_fields["filing_date"] else "Unknown",
        "filing_text": run.filing_text,
        "filing_type": run.filing_type,
        "filing_excerpt": run.excerpt,
    }

    while not run.summary_task.done():
        if run.provider_started.is_set():
            await run.charge_lease()  # the provider request is issued: count the unit now
        awaited = [run.summary_task] if run.provider_started_waiter.done() else [run.summary_task, run.provider_started_waiter]
        done, pending = await asyncio.wait(
            awaited,
            timeout=pipeline.settings.STREAM_HEARTBEAT_INTERVAL,
            return_when=asyncio.FIRST_COMPLETED
        )

        if run.summary_task in done:
            break
        if run.provider_started_waiter in done:
            continue  # charge at the top of the loop before the next heartbeat wait

        # Check for AI Timeout (60s)
        current_time = pipeline.time.time()
        time_in_stage = current_time - run.stage_started_at

        if time_in_stage > 75.0:
            logger.warning(f"[stream:{filing_id}] AI summarization timed out after {time_in_stage:.1f}s. Switching to fallback.")
            run.summary_task.cancel()
            await asyncio.gather(run.summary_task, return_exceptions=True)
            # Use fallback with full filing context for meaningful partial results
            run.summary_payload = pipeline.generate_xbrl_summary(**fallback_kwargs)
            provider_fallback = True
            # Break loop manually since task is cancelled/ignored
            break

        heartbeat_message = SUMMARIZE_MESSAGES[summarize_heartbeat_index % len(SUMMARIZE_MESSAGES)]
        elapsed_secs = int(pipeline.time.time() - run.pipeline_started_at)
        # Estimate progress during summarization: start at 50%, increase by 2% per heartbeat, cap at 90%
        current_percent = min(50 + (summarize_heartbeat_index * 2), 90)
        # A5: if progressive previews have arrived, emit the latest full render (coalesced) as a
        # 'preview' event — real content the client can reveal early — instead of a generic
        # heartbeat. Falls through to the heartbeat when no preview is pending (or feature off).
        latest_preview = None
        if preview_queue is not None:
            while not preview_queue.empty():
                latest_preview = preview_queue.get_nowait()
        if latest_preview:
            yield {'type': 'preview', 'stage': 'summarizing', 'markdown': latest_preview, 'heartbeat_count': summarize_heartbeat_index, 'percent': current_percent, 'elapsed_seconds': elapsed_secs}
        else:
            yield {'type': 'progress', 'stage': 'summarizing', 'message': heartbeat_message, 'heartbeat_count': summarize_heartbeat_index, 'percent': current_percent, 'elapsed_seconds': elapsed_secs}
        summarize_heartbeat_index += 1

    if not run.summary_payload:
        try:
            run.summary_payload = await run.summary_task
        except TimeoutError:
            # The service now owns the exact AI deadline, independent of heartbeat timing.
            run.summary_payload = pipeline.generate_xbrl_summary(**fallback_kwargs)
            provider_fallback = True
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                raise
            # Looked like we already handled fallback, but ensure payload is set
            if not run.summary_payload:
                run.summary_payload = pipeline.generate_xbrl_summary(**fallback_kwargs)
                provider_fallback = True
    run.mark_stage("generate_summary")

    run.summary_status = run.summary_payload.get("status", "complete")
    if run.provider_started.is_set() or (run.summary_status != "error" and not provider_fallback):
        # The signal may have fired just before the task finished; a result without the
        # signal (a stand-in service) still ran a provider, so it is counted on completion.
        # A timeout fallback without the signal ran no provider at all (the deadline passed
        # during local parsing or admission), so it is served uncounted.
        await run.charge_lease()
    if run.summary_status == "error":
        error_message = run.summary_payload.get("message", "Error generating summary")
        await run.refund_charge("provider returned an error payload")
        # Persist the error state so the /progress endpoint reports a retryable error
        # immediately, instead of leaving "summarizing" to age out via the stale check.
        try:
            await run.run_sync_db(run.record_progress_sync, filing_id, "error", error=error_message[:200])
        except Exception as db_err:
            logger.error(f"[stream:{filing_id}] Failed to record AI error progress: {db_err}", exc_info=True)
        yield {'type': 'error', 'message': error_message}
        return
