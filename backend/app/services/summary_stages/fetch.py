"""Fetch stage: start the enrichment tasks, then obtain the filing text.

Three sources, in priority order: a valid 24-hour content cache (no fetch at all), the 6-K exhibit
extractor (EX-99.x press-release text, falling back to the cover-page document), or the SEC EDGAR
document fetch with heartbeat progress while it runs.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

from app.services import summary_pipeline as pipeline
from app.services.summary_stages import enrichment

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


async def fetch_document(run: GenerationRun) -> AsyncIterator[dict]:
    """Start XBRL/section tasks, record the fetching stage and obtain the filing text."""
    filing_id = run.filing_id

    enrichment.start_enrichment_tasks(run)

    # Step 1: File Validation
    # DB OP: Record progress
    await run.run_sync_db(run.record_progress_sync, filing_id, "fetching")

    logger.info(f"[stream:{filing_id}] Yielding fetching stage")
    yield {'type': 'progress', 'stage': 'fetching', 'message': 'Step 1: File Validation - Confirming document is accessible and parsable...', 'percent': 5, 'elapsed_seconds': int(pipeline.time.time() - run.pipeline_started_at)}

    run.filing_text = ""

    if run.cache_is_valid:
        # Skip SEC fetch, use cache
        run.filing_text = ""  # Empty text signals usage of excerpt to downstream services if robustness is handled
        logger.info(f"[stream:{filing_id}] Skipping main thread SEC fetch, using cache.")

        # get_or_cache_excerpt returns an existing excerpt without updating its timestamp.
        # Fetching this accession again cannot refresh the valid cache, so reuse it until
        # the existing 24-hour TTL sends generation through the awaited document path.

        # Yield immediate progress
        yield {'type': 'progress', 'stage': 'fetching', 'message': 'Cached content found. Loading immediately...', 'percent': 15}
    elif run.is_six_k and run.company_cik:
        # 6-K grounding: the primary document is just the cover page, so pull the EX-99.x
        # exhibit / press-release text via the SixK extractor (separate from the Item/XBRL
        # pipeline). Falls back to the cover-page doc so a content-light 6-K still yields text.
        yield {'type': 'progress', 'stage': 'fetching', 'message': 'Retrieving 6-K exhibits from EDGAR...', 'percent': 10}
        try:
            with run.worker_owner.activate():
                run.filing_text = await pipeline.get_sixk_text(run.filing_accession_number, run.company_cik) or ""
        except Exception as sixk_error:  # noqa: BLE001 — extractor is defensive, but never break the stream
            logger.warning(f"[stream:{filing_id}] 6-K exhibit extraction failed: {sixk_error}")
            run.filing_text = ""
        if not run.filing_text:
            try:
                run.filing_text = await pipeline.sec_edgar_service.get_filing_document(run.filing_document_url, timeout=15.0) or ""
            except Exception:  # noqa: BLE001
                run.filing_text = ""
        if not run.filing_text:
            yield {'type': 'error', 'message': 'Unable to retrieve this 6-K at the moment — please try again shortly.'}
            return
        run.mark_stage("fetch_document")
        yield {'type': 'progress', 'stage': 'fetching', 'message': '6-K exhibits fetched', 'percent': 15}
    else:
        # Fetch filing document with heartbeat to prevent UI stall at 10%
        FETCH_MESSAGES = [
            "Connecting to SEC EDGAR...",
            "Downloading filing document...",
            "Retrieving full document text...",
            "Processing SEC response...",
        ]

        try:
            logger.info(f"[stream:{filing_id}] Starting SEC fetch for URL: {run.filing_document_url}")
            # Wrap the SEC fetch in a task with heartbeat loop
            run.fetch_task = asyncio.create_task(
                pipeline.sec_edgar_service.get_filing_document(run.filing_document_url, timeout=15.0)
            )

            fetch_heartbeat_index = 0
            while not run.fetch_task.done():
                done, _ = await asyncio.wait(
                    [run.fetch_task],
                    timeout=pipeline.settings.STREAM_HEARTBEAT_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED
                )
                if run.fetch_task in done:
                    break
                # Send heartbeat during fetch
                fetch_message = FETCH_MESSAGES[fetch_heartbeat_index % len(FETCH_MESSAGES)]
                elapsed_secs = int(pipeline.time.time() - run.pipeline_started_at)
                logger.info(f"[stream:{filing_id}] SEC fetch heartbeat {fetch_heartbeat_index + 1}: {fetch_message}")
                # Estimate progress during fetch: start at 5%, cap at 15%
                current_percent = min(5 + (fetch_heartbeat_index * 1), 15)
                yield {'type': 'progress', 'stage': 'fetching', 'message': fetch_message, 'percent': current_percent, 'elapsed_seconds': elapsed_secs}
                fetch_heartbeat_index += 1

            # Get the result (or raise exception if task failed)
            run.filing_text = await run.fetch_task
            logger.info(f"[stream:{filing_id}] SEC fetch completed. Text length: {len(run.filing_text) if run.filing_text else 0}")

            if not run.filing_text:
                raise ValueError("Filing document is empty or inaccessible")

            run.mark_stage("fetch_document")
            yield {'type': 'progress', 'stage': 'fetching', 'message': 'File validated and fetched successfully', 'percent': 15}

        except Exception as fetch_error:
            logger.error(f"[stream:{filing_id}] Error fetching SEC document: {fetch_error}", exc_info=True)
            error_msg = "Unable to retrieve this filing at the moment — please try again shortly."
            yield {'type': 'error', 'message': error_msg}
            return
