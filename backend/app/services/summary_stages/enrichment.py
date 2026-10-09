"""Context enrichment: the XBRL and edgartools section tasks, the excerpt, and their bounded join.

``start_enrichment_tasks`` is called by the fetch stage before the document fetch starts, because
XBRL and the section parse only need the accession number and CIK and run concurrently with the
(slow) document fetch. ``parse_and_enrich`` is the stage that emits the parsing/analyzing/summarizing
progress, builds the excerpt and joins the enrichment tasks under
``CONTEXT_ENRICHMENT_TIMEOUT_SECONDS``.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

from sqlalchemy.orm import joinedload

from app import database
from app.models import Filing
from app.services import summary_pipeline as pipeline

if TYPE_CHECKING:  # pragma: no cover - annotations only; see the package docstring on import order
    from app.services.summary_stages.generation_run import GenerationRun

logger = logging.getLogger(pipeline.__name__)


def start_enrichment_tasks(run: GenerationRun) -> None:
    """Start the XBRL fetch and the edgartools section parse as request-owned tasks."""
    filing_id = run.filing_id

    # Start XBRL fetching NOW, concurrently with the (slow) filing-document fetch below.
    # XBRL only needs the accession number + CIK (already cached above), not the document
    # text, so serializing it after the fetch wasted the entire fetch window and left it
    # racing an 8s budget. Running it in parallel gives it the realistic time it needs.
    # A 6-K (FPI interim/furnished report) has no Item/XBRL structure — its content lives in
    # EX-99.x exhibits. It takes a separate grounding path below (the SixK exhibit extractor),
    # NOT the XBRL fetch or edgartools section parse, both of which are 10-K/10-Q/20-F only.
    run.is_six_k = bool(run.filing_type and run.filing_type.upper().split("/")[0] == "6-K")
    run.sixk_class, run.sixk_class_audit = None, None
    run.xbrl_task = None
    # 20-F XBRL is now currency-aware end-to-end (the extractor captures the issuer's
    # reporting currency, e.g. CNY, instead of the USD convenience translation), so it is
    # safe to fetch it for foreign annual reports. See tasks/fpi-support-roadmap.md (Phase 3).
    if run.filing_type and run.filing_type.upper().split("/")[0] in {"10-K", "10-Q", "20-F"} and run.company_cik:
        async def fetch_xbrl():
            try:
                data = await pipeline.xbrl_service.get_xbrl_data(run.filing_accession_number, run.company_cik)
                if data:
                    metrics = pipeline.xbrl_service.extract_standardized_metrics(data)

                    # DB OP: Update filing xbrl_data
                    def update_xbrl_sync():
                        # Use a new session for this thread operation to ensure thread safety
                        with database.SessionLocal() as xbrl_session:
                            filing_for_update = xbrl_session.query(Filing).filter(Filing.id == filing_id).first()
                            if filing_for_update:
                                filing_for_update.xbrl_data = data
                                xbrl_session.commit()
                                # Populate this filing's normalized facts now (roadmap B: the
                                # filing-scoped trend chart reads them). Best-effort and
                                # network-free — reuse the metrics just extracted; a failure
                                # must never break the summary stream. We're already off the
                                # event loop (run_sync_db threadpool) with our own session.
                                try:
                                    from app.services import facts_service

                                    facts_service.process_filing_facts(
                                        xbrl_session, filing_for_update, standardized=metrics
                                    )
                                except Exception:
                                    logger.warning(
                                        f"[stream:{filing_id}] facts upsert failed (non-fatal)",
                                        exc_info=True,
                                    )

                    try:
                        await run.run_sync_db(update_xbrl_sync)
                    except Exception as persistence_error:
                        # Fresh metrics are useful to this generation even when their
                        # best-effort cache/facts write fails. Cancellation still propagates.
                        logger.warning(
                            f"[stream:{filing_id}] XBRL persistence failed (non-fatal): {persistence_error}"
                        )
                    return metrics
            except Exception as xbrl_error:
                logger.warning(f"[stream:{filing_id}] Error updating XBRL data: {str(xbrl_error)}")
                pass
            return None
        with run.worker_owner.activate():
            run.xbrl_task = asyncio.create_task(fetch_xbrl())

    # Fetch edgartools-parsed sections in parallel with the document fetch (needs only
    # accession + CIK). High-precision excerpt source; the regex extractor is the fallback.
    # Skipped on a cache hit (the cached excerpt is reused, no re-extraction needed).
    run.sections_task = None
    if (
        not run.cache_is_valid
        and pipeline.settings.USE_EDGARTOOLS_SECTIONS
        and run.company_cik
        and run.filing_type
        # 20-F (foreign annual report) gets edgartools section extraction too. split("/")
        # so amended forms (10-K/A, 20-F/A) are covered — the lower layers normalize_form
        # anyway. See tasks/fpi-support-roadmap.md.
        and run.filing_type.upper().split("/")[0] in {"10-K", "10-Q", "20-F"}
    ):
        async def fetch_sections():
            try:
                return await pipeline.xbrl_service.get_filing_sections(
                    run.filing_accession_number, run.company_cik, run.filing_type
                )
            except Exception as sections_error:  # noqa: BLE001
                logger.warning(f"[stream:{filing_id}] Section parse failed: {sections_error}")
                return None
        with run.worker_owner.activate():
            run.sections_task = asyncio.create_task(fetch_sections())


async def parse_and_enrich(run: GenerationRun) -> AsyncIterator[dict]:
    """Parsing/analyzing/summarizing progress, the excerpt task and the bounded enrichment join."""
    filing_id = run.filing_id

    yield {'type': 'progress', 'stage': 'parsing', 'message': 'Starting parsing...', 'percent': 15}

    # Step 2: Section Parsing
    # DB OP: Record progress
    await run.run_sync_db(run.record_progress_sync, filing_id, "parsing")

    yield {'type': 'progress', 'stage': 'parsing', 'message': 'Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...', 'percent': 20}

    # Resolve the parallel section parse (if any) before building the excerpt.
    sections = None
    if run.sections_task is not None:
        sections = await run.sections_task

    # Extract excerpt
    def extract_excerpt_sync():
        with database.SessionLocal() as thread_session:
            thread_filing = thread_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
            return pipeline.get_or_cache_excerpt(thread_session, thread_filing, run.filing_text, sections=sections)

    if run.cache_is_valid:
        # Use the cached excerpt directly
        async def return_cached_excerpt():
            return run.excerpt_from_cache
        run.excerpt_task = asyncio.create_task(return_cached_excerpt())
    else:
        run.excerpt_task = asyncio.create_task(run.run_sync_db(extract_excerpt_sync))

    # XBRL fetch was already started concurrently with the document fetch above.

    # Wait for parsing to complete
    yield {'type': 'progress', 'stage': 'parsing', 'message': 'Parsing complete...', 'percent': 25}

    # Step 3: Content Analysis
    # DB OP: Record progress
    await run.run_sync_db(run.record_progress_sync, filing_id, "analyzing")

    yield {'type': 'progress', 'stage': 'analyzing', 'message': 'Step 3: Content Analysis - Analyzing risk factors...', 'percent': 35}

    # Step 4: Summary Generation
    yield {'type': 'progress', 'stage': 'analyzing', 'message': 'Step 4: Generating financial overview...', 'percent': 45}

    # DB OP: Record progress
    await run.run_sync_db(run.record_progress_sync, filing_id, "summarizing")

    yield {'type': 'progress', 'stage': 'summarizing', 'message': 'Step 5: Generating investor-focused summary...', 'percent': 50}

    # Wait for excerpt and XBRL with reasonable timeout
    # CRITICAL: 2s was too aggressive - SEC API for large companies can take 5-10s
    run.excerpt = None
    run.xbrl_metrics = None
    tasks_to_wait = [run.excerpt_task]
    if run.xbrl_task:
        tasks_to_wait.append(run.xbrl_task)
    try:
        # Give excerpt/XBRL time to complete - critical for financial data accuracy
        await asyncio.wait_for(
            asyncio.gather(*tasks_to_wait, return_exceptions=True),
            timeout=pipeline.CONTEXT_ENRICHMENT_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        pass  # wait_for has cancelled/drained pending siblings; retain completed results.
    except Exception as e:
        logger.warning(f"[stream:{filing_id}] Error waiting for excerpt/XBRL: {str(e)}")

    # A slow/failed sibling cannot erase enrichment that already completed successfully.
    # External cancellation bypasses this block; it is never converted to partial success.
    results = [
        task.result() if task.done() and not task.cancelled() and task.exception() is None else None
        for task in tasks_to_wait
    ]
    run.excerpt = results[0]
    if len(results) > 1:
        run.xbrl_metrics = results[1]

    run.mark_stage("context_enrichment")
