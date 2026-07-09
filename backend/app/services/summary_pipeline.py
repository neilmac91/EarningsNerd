"""Transport-agnostic summary-generation pipeline.

This module owns the end-to-end summary pipeline that was previously inlined as the
``stream_summary()`` generator inside ``app/routers/summaries.py``. It yields plain
``dict`` events (``{"type": "progress"|"chunk"|"partial"|"complete"|"error", ...}``) so
the SSE endpoint can format them for the wire while the business logic lives here.

Phase 1 (M7) goal: extract the logic with **zero behaviour change** to the SSE contract.
The yielded dicts are exactly the payloads the router used to ``json.dumps`` inline, so the
on-the-wire output is unchanged. A future phase can route the batch/cron path through the
same generator to retire the duplicate in ``summary_generation_service.py``.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import time
from datetime import timedelta
from typing import AsyncIterator, List, Optional

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app import database
from app.config import settings
from app.models import Filing, Summary, User
from app.schemas import attach_normalized_facts
from app.services.content_cache import upsert_content_cache
from app.services.edgar.compat import sec_edgar_service, xbrl_service
from app.services.edgar.sixk_extractor import get_sixk_text
from app.services.fallback_summary import generate_xbrl_summary
from app.services.openai_service import openai_service
from app.services.posthog_client import (
    EVENT_GENERATION_STARTED,
    EVENT_GENERATION_SUCCEEDED,
    EVENT_GENERATION_FAILED,
    EVENT_GENERATION_TIMED_OUT,
    EVENT_PAYWALL_HIT,
    capture_funnel_event,
)
from app.services.subscription_service import (
    check_usage_limit,
    increment_user_usage,
    get_current_month,
)
from app.services.entitlements import get_entitlements
from app.services.summary_generation_service import (
    assess_quality,
    quality_tier_rank,
    record_progress,
    get_or_cache_excerpt,
)
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION

logger = logging.getLogger(__name__)

# A3: process-local registry of in-flight summary generations, keyed by filing_id. When a request
# would generate a filing another request is already generating, it waits for that one and serves the
# persisted result — collapsing a concurrent "thundering herd" on a newly-filed popular report into a
# single generation. Process-local is the right scope: prod is a single Cloud Run instance with Redis
# off, and even when scaled it bounds redundant work per instance.
_inflight_generations: dict[int, asyncio.Event] = {}
INFLIGHT_WAIT_CAP_SECONDS = 110.0  # just under PIPELINE_TIMEOUT_SECONDS (120s)


def _claim_inflight(filing_id: int) -> asyncio.Event:
    """Register this request as the leader generating ``filing_id``; returns the event to release."""
    event = asyncio.Event()
    _inflight_generations[filing_id] = event
    return event


def _release_inflight(filing_id: int, event: asyncio.Event) -> None:
    """Release leadership (only if we still own the slot) and wake any waiters."""
    if _inflight_generations.get(filing_id) is event:
        _inflight_generations.pop(filing_id, None)
    event.set()


# Bounds concurrent full generations per process to protect the single vCPU (see
# settings.MAX_CONCURRENT_GENERATIONS). Lazily constructed so it binds to the running event loop
# rather than import-time. Acquired ONLY on the generation (leader) path — dedup waiters return
# before claiming a slot — so it can never deadlock a leader against its own waiters.
_generation_semaphore: Optional[asyncio.Semaphore] = None


def _get_generation_semaphore() -> asyncio.Semaphore:
    global _generation_semaphore
    if _generation_semaphore is None:
        # <= 0 disables the ceiling (unbounded), mirroring PRO_SUMMARY_MONTHLY_CAP=0. Using a large
        # count rather than skipping acquire keeps the acquire/release bookkeeping uniform.
        limit = settings.MAX_CONCURRENT_GENERATIONS
        _generation_semaphore = asyncio.Semaphore(limit if limit > 0 else 2**31)
    return _generation_semaphore


# Strong references to fire-and-forget background tasks (e.g. the cached-content refresh),
# so the event loop doesn't garbage-collect them mid-execution. Each task removes itself on
# completion. See https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task.
_background_tasks: set[asyncio.Task] = set()


def _spawn_background(coro) -> None:
    """Schedule a fire-and-forget coroutine, keeping a strong reference until it finishes."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# Pipeline-level hard timeout. This is a *backstop* against a genuine hang/runaway — it sits
# deliberately above the sum of the per-step budgets (≈15s fetch + 18s enrichment + 75s AI
# fallback ≈ 108s) so the per-step timeouts remain the primary controls and the AI fallback
# always gets to produce a (partial) result rather than being pre-empted into a timeout error.
# The whole pipeline body runs inside `asyncio.timeout(PIPELINE_TIMEOUT_SECONDS)`.
PIPELINE_TIMEOUT_SECONDS = 120

# Timeout for XBRL/excerpt enrichment. XBRL fetch starts concurrently with the filing
# document fetch, so this is the *additional* budget we wait at the join point. The XBRL
# service's own internal timeout is 15s (EDGAR_DEFAULT_TIMEOUT_SECONDS); an 8s ceiling here
# silently truncated it on large issuers, producing hollow financials.
CONTEXT_ENRICHMENT_TIMEOUT_SECONDS = 18.0


def to_sse(event: dict) -> str:
    """Format a pipeline event dict as an SSE ``data:`` frame."""
    return f"data: {json.dumps(event)}\n\n"


async def stream_filing_summary(
    *,
    filing_id: int,
    current_user: Optional[User],
    user_id: Optional[int],
    telemetry_distinct_id: str,
    telemetry_entry_point: Optional[str],
    telemetry_ctx: dict,
    emit_funnel_telemetry: bool = True,
    force_regenerate: bool = False,
) -> AsyncIterator[dict]:
    """Run the summary pipeline for ``filing_id``, yielding event dicts.

    Caller is responsible for HTTP concerns (rate limiting, guest quota, the cached/existing
    summary short-circuit) and for capturing the telemetry context before invoking this — the
    generator runs after the request's DB session is gone, so it manages its own session.
    """
    pipeline_started_at = time.time()
    stage_started_at = pipeline_started_at
    stage_timings: List[tuple[str, float]] = []

    def emit_funnel(*args, **kwargs):
        # Suppressed when the background/cron path drains this generator headless — a precompute
        # run must emit ZERO funnel events (S1, T2 pin). The user-facing SSE path leaves it on.
        if emit_funnel_telemetry:
            capture_funnel_event(*args, **kwargs)

    emit_funnel(
        telemetry_distinct_id,
        EVENT_GENERATION_STARTED,
        entry_point=telemetry_entry_point,
        **telemetry_ctx,
    )

    def elapsed_ms() -> int:
        return int((time.time() - pipeline_started_at) * 1000)

    def mark_stage(stage_name: str):
        nonlocal stage_started_at
        now = time.time()
        duration = now - stage_started_at
        stage_timings.append((stage_name, duration))
        stage_started_at = now

    session = database.SessionLocal()
    # A3: set when this request becomes the generation leader; released in `finally`.
    inflight_event: Optional[asyncio.Event] = None
    generation_semaphore: Optional[asyncio.Semaphore] = None
    generation_slot_held = False

    async def run_sync_db(func, *args, **kwargs):
        """Helper to run DB operations in default thread pool"""
        return await run_in_threadpool(func, *args, **kwargs)

    try:
        async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
            logger.info(f"[stream:{filing_id}] Stream generator started (timeout: {PIPELINE_TIMEOUT_SECONDS}s)")
            yield {'type': 'progress', 'stage': 'initializing', 'message': 'Initializing...', 'percent': 0}

            # DB OP: Query filing and check for existing summary
            def get_filing_and_summary_sync():
                filing_in_session = session.query(Filing).options(
                    joinedload(Filing.content_cache),
                    joinedload(Filing.company)
                ).filter(Filing.id == filing_id).first()
                summary_in_session = session.query(Summary).filter(Summary.filing_id == filing_id).first()
                return filing_in_session, summary_in_session

            filing_in_session, summary_in_session = await run_sync_db(get_filing_and_summary_sync)

            if not filing_in_session:
                logger.warning(f"[stream:{filing_id}] Filing not found during stream generation.")
                yield {'type': 'error', 'message': 'Filing not found'}
                return

            if summary_in_session and not force_regenerate:
                logger.info(f"[stream:{filing_id}] Existing summary found. Returning it.")
                yield {
                    'type': 'complete',
                    'summary': summary_in_session.business_overview,
                    'summary_id': summary_in_session.id,
                }
                return

            # A3: in-flight dedup. If another request is already generating this filing, wait for it
            # (emitting heartbeats) and serve the persisted result instead of running a second full
            # generation; otherwise claim leadership (released in `finally`).
            existing_generation = _inflight_generations.get(filing_id)
            if existing_generation is not None:
                logger.info(f"[stream:{filing_id}] Joining in-flight generation (dedup).")
                yield {'type': 'progress', 'stage': 'queued', 'message': 'Another request is already generating this analysis — joining it...', 'percent': 3, 'elapsed_seconds': int(time.time() - pipeline_started_at)}
                waited = 0.0
                while not existing_generation.is_set() and waited < INFLIGHT_WAIT_CAP_SECONDS:
                    try:
                        await asyncio.wait_for(existing_generation.wait(), timeout=settings.STREAM_HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError:
                        waited += settings.STREAM_HEARTBEAT_INTERVAL
                        yield {'type': 'progress', 'stage': 'summarizing', 'message': 'Finishing the shared analysis...', 'percent': min(50 + int(waited), 90), 'elapsed_seconds': int(time.time() - pipeline_started_at)}

                # Re-read on a fresh session (the leader committed on its own) and serve it.
                def get_persisted_summary_fields():
                    with database.SessionLocal() as s:
                        summ = s.query(Summary).filter(Summary.filing_id == filing_id).first()
                        return {"business_overview": summ.business_overview, "id": summ.id} if summ else None

                summary_fields = await run_sync_db(get_persisted_summary_fields)
                if summary_fields:
                    logger.info(f"[stream:{filing_id}] Served result from in-flight leader (dedup hit).")
                    yield {'type': 'complete', 'summary': summary_fields["business_overview"], 'summary_id': summary_fields["id"]}
                    return
                # Leader finished without a persisted summary (error/timeout) — generate directly.
                logger.info(f"[stream:{filing_id}] In-flight leader produced no summary; generating directly.")

            # Claim leadership for this filing_id (atomic: no await between the get above and this set).
            inflight_event = _claim_inflight(filing_id)

            # Cache company data and filing attributes from the fetched filing
            company_name = filing_in_session.company.name if filing_in_session.company else "Unknown company"
            company_cik = filing_in_session.company.cik if filing_in_session.company else None
            company_sic = filing_in_session.company.sic if filing_in_session.company else None
            filing_document_url = filing_in_session.document_url
            filing_type = filing_in_session.filing_type
            filing_accession_number = filing_in_session.accession_number

            # Check for cached content
            cached_content = filing_in_session.content_cache
            cache_is_valid = False
            excerpt_from_cache = None

            if cached_content and cached_content.critical_excerpt:
                # Check age (valid if < 24 hours)
                last_updated = cached_content.updated_at or cached_content.created_at
                if not last_updated:
                    # Should not happen given database constraints, but safe fallback
                    last_updated = datetime.datetime.now(datetime.timezone.utc)
                elif last_updated.tzinfo is None:
                    # SQLite (and some drivers) return naive datetimes; assume UTC so the
                    # subtraction below doesn't raise "can't subtract offset-naive and
                    # offset-aware datetimes" and crash the cached-content path.
                    last_updated = last_updated.replace(tzinfo=datetime.timezone.utc)

                age = datetime.datetime.now(datetime.timezone.utc) - last_updated
                if age < timedelta(hours=24):
                    cache_is_valid = True
                    excerpt_from_cache = cached_content.critical_excerpt
                    logger.info(f"[stream:{filing_id}] Using cached content (age: {age})")

            # Check usage limits for authenticated user
            if current_user:
                can_generate, current_count, limit = await run_sync_db(check_usage_limit, current_user, session)
                if not can_generate:
                    # A Pro user is billing-unlimited, so a block here means the INVISIBLE fair-use
                    # ceiling (PRO_SUMMARY_MONTHLY_CAP) tripped — degrade with a generic message,
                    # never an upsell, and skip the paywall funnel event (a Pro user isn't paywalled).
                    is_pro = await run_sync_db(
                        lambda u: get_entitlements(u).has_unlimited_summaries, current_user
                    )
                    if is_pro:
                        logger.warning(
                            f"[stream:{filing_id}] Pro user {user_id} hit summary fair-use ceiling ({limit})."
                        )
                        yield {
                            "type": "error",
                            "message": (
                                "We've temporarily paused new summary generation on your account due "
                                "to unusually high recent volume. Please try again later or contact support."
                            ),
                        }
                        return
                    logger.warning(f"[stream:{filing_id}] User {user_id} exceeded monthly summary limit ({limit}).")
                    # Demand/pricing signal: record when a free user hits the wall.
                    emit_funnel(
                        telemetry_distinct_id,
                        EVENT_PAYWALL_HIT,
                        entry_point=telemetry_entry_point,
                        limit=limit,
                        summaries_used=current_count,
                    )
                    message = (
                        "You've reached your monthly limit of "
                        f"{limit} summaries. Upgrade to Pro for unlimited summaries."
                    )
                    yield {"type": "error", "message": message}
                    return
                logger.info(f"[stream:{filing_id}] Usage limit check passed for user {user_id}. Current count: {current_count}/{limit}")
            else:
                logger.info(f"[stream:{filing_id}] Guest user access. Rate limit already enforced.")
            # Note: We use cached values from outer scope, but filling_in_session is already populated.

            # Bound concurrent generations per process (protects the single vCPU). Acquired here —
            # AFTER the usage/fair-use gate so rejected/abusive requests never occupy a slot, and only
            # on the leader path (dedup waiters returned above) so it can't deadlock a leader against
            # its waiters. Released in the `finally`. A long queue wait counts against the pipeline
            # timeout, which is the intended back-pressure. (A waiter that times out at
            # INFLIGHT_WAIT_CAP_SECONDS may fall through and become a fresh leader for the same
            # filing; that only softens the same-filing dedup under extreme saturation — it never
            # exceeds MAX_CONCURRENT_GENERATIONS total, and no waiter holds a slot while waiting.)
            generation_semaphore = _get_generation_semaphore()
            await generation_semaphore.acquire()
            generation_slot_held = True

            # Start XBRL fetching NOW, concurrently with the (slow) filing-document fetch below.
            # XBRL only needs the accession number + CIK (already cached above), not the document
            # text, so serializing it after the fetch wasted the entire fetch window and left it
            # racing an 8s budget. Running it in parallel gives it the realistic time it needs.
            # A 6-K (FPI interim/furnished report) has no Item/XBRL structure — its content lives in
            # EX-99.x exhibits. It takes a separate grounding path below (the SixK exhibit extractor),
            # NOT the XBRL fetch or edgartools section parse, both of which are 10-K/10-Q/20-F only.
            is_six_k = bool(filing_type and filing_type.upper().split("/")[0] == "6-K")
            xbrl_task = None
            # 20-F XBRL is now currency-aware end-to-end (the extractor captures the issuer's
            # reporting currency, e.g. CNY, instead of the USD convenience translation), so it is
            # safe to fetch it for foreign annual reports. See tasks/fpi-support-roadmap.md (Phase 3).
            if filing_type and filing_type.upper().split("/")[0] in {"10-K", "10-Q", "20-F"} and company_cik:
                async def fetch_xbrl():
                    try:
                        data = await xbrl_service.get_xbrl_data(filing_accession_number, company_cik)
                        if data:
                            metrics = xbrl_service.extract_standardized_metrics(data)

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

                            await run_sync_db(update_xbrl_sync)
                            return metrics
                    except Exception as xbrl_error:
                        logger.warning(f"[stream:{filing_id}] Error updating XBRL data: {str(xbrl_error)}")
                        pass
                    return None
                xbrl_task = asyncio.create_task(fetch_xbrl())

            # Fetch edgartools-parsed sections in parallel with the document fetch (needs only
            # accession + CIK). High-precision excerpt source; the regex extractor is the fallback.
            # Skipped on a cache hit (the cached excerpt is reused, no re-extraction needed).
            sections_task = None
            if (
                not cache_is_valid
                and settings.USE_EDGARTOOLS_SECTIONS
                and company_cik
                and filing_type
                # 20-F (foreign annual report) gets edgartools section extraction too. split("/")
                # so amended forms (10-K/A, 20-F/A) are covered — the lower layers normalize_form
                # anyway. See tasks/fpi-support-roadmap.md.
                and filing_type.upper().split("/")[0] in {"10-K", "10-Q", "20-F"}
            ):
                async def fetch_sections():
                    try:
                        return await xbrl_service.get_filing_sections(
                            filing_accession_number, company_cik, filing_type
                        )
                    except Exception as sections_error:  # noqa: BLE001
                        logger.warning(f"[stream:{filing_id}] Section parse failed: {sections_error}")
                        return None
                sections_task = asyncio.create_task(fetch_sections())

            # Step 1: File Validation
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "fetching")

            logger.info(f"[stream:{filing_id}] Yielding fetching stage")
            yield {'type': 'progress', 'stage': 'fetching', 'message': 'Step 1: File Validation - Confirming document is accessible and parsable...', 'percent': 5, 'elapsed_seconds': int(time.time() - pipeline_started_at)}

            # Background refresh task definition
            async def background_fetch_and_update():
                try:
                    logger.info(f"[stream:{filing_id}] Background refresh: fetching doc")
                    text = await sec_edgar_service.get_filing_document(filing_document_url, timeout=30.0)
                    if not text:
                        return

                    def update_cache_sync():
                        with database.SessionLocal() as bg_session:
                            bg_filing = bg_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                            if bg_filing:
                                # Update cache using service logic to re-extract
                                get_or_cache_excerpt(bg_session, bg_filing, text)
                                bg_session.commit()

                    await run_sync_db(update_cache_sync)
                    logger.info(f"[stream:{filing_id}] Background refresh completed")
                except Exception as e:
                    logger.warning(f"[stream:{filing_id}] Background refresh failed: {e}", exc_info=True)

            filing_text = ""

            if cache_is_valid:
                # Skip SEC fetch, use cache
                filing_text = ""  # Empty text signals usage of excerpt to downstream services if robustness is handled
                logger.info(f"[stream:{filing_id}] Skipping main thread SEC fetch, using cache.")

                # Spawn background refresh (strong-referenced so it isn't GC'd mid-flight)
                _spawn_background(background_fetch_and_update())

                # Yield immediate progress
                yield {'type': 'progress', 'stage': 'fetching', 'message': 'Cached content found. Loading immediately...', 'percent': 15}
            elif is_six_k and company_cik:
                # 6-K grounding: the primary document is just the cover page, so pull the EX-99.x
                # exhibit / press-release text via the SixK extractor (separate from the Item/XBRL
                # pipeline). Falls back to the cover-page doc so a content-light 6-K still yields text.
                yield {'type': 'progress', 'stage': 'fetching', 'message': 'Retrieving 6-K exhibits from EDGAR...', 'percent': 10}
                try:
                    filing_text = await get_sixk_text(filing_accession_number, company_cik) or ""
                except Exception as sixk_error:  # noqa: BLE001 — extractor is defensive, but never break the stream
                    logger.warning(f"[stream:{filing_id}] 6-K exhibit extraction failed: {sixk_error}")
                    filing_text = ""
                if not filing_text:
                    try:
                        filing_text = await sec_edgar_service.get_filing_document(filing_document_url, timeout=15.0) or ""
                    except Exception:  # noqa: BLE001
                        filing_text = ""
                if not filing_text:
                    yield {'type': 'error', 'message': 'Unable to retrieve this 6-K at the moment — please try again shortly.'}
                    return
                mark_stage("fetch_document")
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
                    logger.info(f"[stream:{filing_id}] Starting SEC fetch for URL: {filing_document_url}")
                    # Wrap the SEC fetch in a task with heartbeat loop
                    fetch_task = asyncio.create_task(
                        sec_edgar_service.get_filing_document(filing_document_url, timeout=15.0)
                    )

                    fetch_heartbeat_index = 0
                    while not fetch_task.done():
                        done, _ = await asyncio.wait(
                            [fetch_task],
                            timeout=settings.STREAM_HEARTBEAT_INTERVAL,
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        if fetch_task in done:
                            break
                        # Send heartbeat during fetch
                        fetch_message = FETCH_MESSAGES[fetch_heartbeat_index % len(FETCH_MESSAGES)]
                        elapsed_secs = int(time.time() - pipeline_started_at)
                        logger.info(f"[stream:{filing_id}] SEC fetch heartbeat {fetch_heartbeat_index + 1}: {fetch_message}")
                        # Estimate progress during fetch: start at 5%, cap at 15%
                        current_percent = min(5 + (fetch_heartbeat_index * 1), 15)
                        yield {'type': 'progress', 'stage': 'fetching', 'message': fetch_message, 'percent': current_percent, 'elapsed_seconds': elapsed_secs}
                        fetch_heartbeat_index += 1

                    # Get the result (or raise exception if task failed)
                    filing_text = await fetch_task
                    logger.info(f"[stream:{filing_id}] SEC fetch completed. Text length: {len(filing_text) if filing_text else 0}")

                    if not filing_text:
                        raise ValueError("Filing document is empty or inaccessible")

                    mark_stage("fetch_document")
                    yield {'type': 'progress', 'stage': 'fetching', 'message': 'File validated and fetched successfully', 'percent': 15}

                except Exception as fetch_error:
                    logger.error(f"[stream:{filing_id}] Error fetching SEC document: {fetch_error}", exc_info=True)
                    error_msg = "Unable to retrieve this filing at the moment — please try again shortly."
                    yield {'type': 'error', 'message': error_msg}
                    return

            yield {'type': 'progress', 'stage': 'parsing', 'message': 'Starting parsing...', 'percent': 15}

            # Step 2: Section Parsing
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "parsing")

            yield {'type': 'progress', 'stage': 'parsing', 'message': 'Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...', 'percent': 20}

            # Resolve the parallel section parse (if any) before building the excerpt.
            sections = None
            if sections_task is not None:
                sections = await sections_task

            # Extract excerpt
            def extract_excerpt_sync():
                with database.SessionLocal() as thread_session:
                    thread_filing = thread_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                    return get_or_cache_excerpt(thread_session, thread_filing, filing_text, sections=sections)

            if cache_is_valid:
                # Use the cached excerpt directly
                async def return_cached_excerpt():
                    return excerpt_from_cache
                excerpt_task = asyncio.create_task(return_cached_excerpt())
            else:
                excerpt_task = asyncio.create_task(run_sync_db(extract_excerpt_sync))

            # XBRL fetch was already started concurrently with the document fetch above.

            # Wait for parsing to complete
            yield {'type': 'progress', 'stage': 'parsing', 'message': 'Parsing complete...', 'percent': 25}

            # Step 3: Content Analysis
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "analyzing")

            yield {'type': 'progress', 'stage': 'analyzing', 'message': 'Step 3: Content Analysis - Analyzing risk factors...', 'percent': 35}

            # Step 4: Summary Generation
            yield {'type': 'progress', 'stage': 'analyzing', 'message': 'Step 4: Generating financial overview...', 'percent': 45}

            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "summarizing")

            yield {'type': 'progress', 'stage': 'summarizing', 'message': 'Step 5: Generating investor-focused summary...', 'percent': 50}

            # Wait for excerpt and XBRL with reasonable timeout
            # CRITICAL: 2s was too aggressive - SEC API for large companies can take 5-10s
            excerpt = None
            xbrl_metrics = None
            try:
                # Give excerpt/XBRL time to complete - critical for financial data accuracy
                tasks_to_wait = [excerpt_task]
                if xbrl_task:
                    tasks_to_wait.append(xbrl_task)

                results = await asyncio.wait_for(
                    asyncio.gather(*tasks_to_wait, return_exceptions=True),
                    timeout=CONTEXT_ENRICHMENT_TIMEOUT_SECONDS
                )

                excerpt = results[0] if not isinstance(results[0], Exception) else None
                if len(results) > 1:
                    xbrl_result = results[1]
                    xbrl_metrics = xbrl_result if not isinstance(xbrl_result, Exception) and xbrl_result is not None else None
            except asyncio.TimeoutError:
                excerpt = None
                xbrl_metrics = None
            except Exception as e:
                logger.warning(f"[stream:{filing_id}] Error waiting for excerpt/XBRL: {str(e)}")
                excerpt = None
                xbrl_metrics = None

            mark_stage("context_enrichment")

            # A5: when STREAM_SECTION_REVEAL is on, stream the extraction and push progressive section
            # previews onto a queue that the heartbeat loop drains below. The callback can't yield from
            # this generator, so the queue decouples them. Off by default → behaviour unchanged.
            preview_queue: Optional[asyncio.Queue] = (
                asyncio.Queue() if settings.STREAM_SECTION_REVEAL else None
            )
            summary_stream_cb = None
            if preview_queue is not None:
                async def summary_stream_cb(preview_md: str) -> None:
                    preview_queue.put_nowait(preview_md)

            # Now run AI summarization (with excerpt/XBRL if available)
            # Wrap in task to enable heartbeat loop while waiting
            summary_task = asyncio.create_task(openai_service.summarize_filing(
                filing_text,
                company_name,
                filing_type,
                previous_filings=None,
                xbrl_metrics=xbrl_metrics,
                filing_excerpt=excerpt,
                stream_cb=summary_stream_cb,
            ))

            SUMMARIZE_MESSAGES = [
                "Analyzing financial highlights...",
                "Cross-referencing with XBRL data...",
                "Extracting key metrics from MD&A...",
                "Identifying significant risk factors...",
                "Synthesizing investment insights...",
                "Reviewing guidance and outlook...",
            ]
            summarize_heartbeat_index = 0
            summary_payload = None

            # Build fallback kwargs once to avoid duplication (DRY principle)
            fallback_kwargs = {
                "xbrl_data": xbrl_metrics,
                "company_name": company_name,
                "filing_date": filing_in_session.filing_date.isoformat() if filing_in_session.filing_date else "Unknown",
                "filing_text": filing_text,
                "filing_type": filing_type,
                "filing_excerpt": excerpt,
            }

            while not summary_task.done():
                done, pending = await asyncio.wait(
                    [summary_task],
                    timeout=settings.STREAM_HEARTBEAT_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED
                )

                if summary_task in done:
                    break

                # Check for AI Timeout (60s)
                current_time = time.time()
                time_in_stage = current_time - stage_started_at

                if time_in_stage > 75.0:
                    logger.warning(f"[stream:{filing_id}] AI summarization timed out after {time_in_stage:.1f}s. Switching to fallback.")
                    summary_task.cancel()
                    # Use fallback with full filing context for meaningful partial results
                    summary_payload = generate_xbrl_summary(**fallback_kwargs)
                    # Break loop manually since task is cancelled/ignored
                    break

                heartbeat_message = SUMMARIZE_MESSAGES[summarize_heartbeat_index % len(SUMMARIZE_MESSAGES)]
                elapsed_secs = int(time.time() - pipeline_started_at)
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

            if not summary_payload:
                try:
                    summary_payload = await summary_task
                except asyncio.CancelledError:
                    # Looked like we already handled fallback, but ensure payload is set
                    if not summary_payload:
                        summary_payload = generate_xbrl_summary(**fallback_kwargs)
            mark_stage("generate_summary")

            summary_status = summary_payload.get("status", "complete")
            if summary_status == "error":
                error_message = summary_payload.get("message", "Error generating summary")
                # Persist the error state so the /progress endpoint reports a retryable error
                # immediately, instead of leaving "summarizing" to age out via the stale check.
                try:
                    await run_sync_db(record_progress, session, filing_id, "error", error=error_message[:200])
                except Exception as db_err:
                    logger.error(f"[stream:{filing_id}] Failed to record AI error progress: {db_err}", exc_info=True)
                yield {'type': 'error', 'message': error_message}
                return

            markdown = summary_payload.get("business_overview") or ""
            raw_summary = summary_payload.get("raw_summary") or {}
            sections_info = (raw_summary.get("sections") or {}) or {}

            section_coverage = (
                raw_summary.get("section_coverage")
                if isinstance(raw_summary, dict)
                else None
            )
            if section_coverage:
                await run_sync_db(
                    record_progress,
                    session,
                    filing_id,
                    "summarizing",
                    section_coverage=section_coverage,
                )

            # v2 (Tier-3.1): enrich the P&L table (results_that_matter) with normalized XBRL facts for
            # the metrics block's provenance chips, and surface risks under the v2 key.
            financial_section = sections_info.get("results_that_matter")
            normalized_financial_section = attach_normalized_facts(financial_section, xbrl_metrics)
            if normalized_financial_section is not None:
                sections_info["results_that_matter"] = normalized_financial_section

            risk_section = summary_payload.get("risk_factors") or []
            sections_info["risks"] = risk_section
            # Legacy compat columns on the Summary row (management_discussion / key_changes) still get
            # the v2-mapped prose (earnings_quality / forward_signals, re-pointed in summarize_filing).
            management_section = summary_payload.get("management_discussion")
            guidance_section = summary_payload.get("key_changes")

            # The legacy MD&A/guidance wrapper injection is retired under v2: the v2 taxonomy already
            # carries earnings_quality + forward_signals, and the web reads the render_sections output
            # (rendered_sections), not these keys. Injecting management_discussion_insights /
            # guidance_outlook here would only decorate every v2 row with phantom v1 nodes.

            raw_summary["sections"] = sections_info
            raw_summary["status"] = summary_status
            # Embed the schema version so the render projection (summary_sections) can version-
            # dispatch on raw_summary["schema_version"]; the Summary columns below carry the same
            # stamps for querying/refreshing stale rows.
            raw_summary["schema_version"] = SUMMARY_SCHEMA_VERSION

            # S4: deterministic quality verdict (always attached as metadata for the UI badge).
            # sic feeds the bank-aware revenue-grounding rule (P0-2) as the flag-independent
            # FI signal alongside component presence.
            # ``excerpt or filing_text``: when excerpt extraction failed (cache miss + section-parse
            # timeout), ``summarize_filing`` still generated from ``filing_text``'s parsed sample — so the
            # gate must ground against the same text, else every filing-copied figure false-flags on
            # exactly the degraded population. The two are complementary (filing_text is emptied only when
            # the excerpt is in use), and ``untraceable_figures`` returns [] if BOTH are empty.
            quality = assess_quality(
                summary_payload, xbrl_metrics, sic=company_sic, excerpt=excerpt or filing_text
            )
            raw_summary["quality"] = quality
            untraceable = quality.get("figures_untraceable") or []
            if untraceable:
                # T3.2 advisory-phase measurement channel. The gate ships flag-off, so untraceable dollar
                # figures do NOT tier the summary "partial" — this greppable counter (count first, for a
                # log-based metric threshold) is the only push signal for the flag-flip decision and,
                # post-T5, the regression alarm for derived-aggregate reintroduction.
                logger.info(
                    "figure_trace_untraceable count=%d flag=%s filing_id=%s sic=%s figures=%s",
                    len(untraceable),
                    settings.AI_FIGURE_TRACE_GATE,
                    filing_id,
                    company_sic or "",
                    "|".join(untraceable),
                )
            if quality.get("tier") == "partial":
                # P0-2 detection: greppable counter of partial verdicts by reason + SIC. A
                # bank-heavy spike after any prompt change is the recurrence signal for the
                # bank-blind-grounding incident class.
                logger.info(
                    "summary_quality_partial filing_id=%s cik=%s sic=%s reasons=%s",
                    filing_id,
                    company_cik,
                    company_sic or "",
                    "|".join(quality.get("reasons") or []),
                )

            # S4 quality gate (flagged, default off): the summary is ALWAYS persisted, so the
            # streamed result doesn't vanish when the client refetches and isn't regenerated from
            # scratch on revisit. When a result is assessed "partial", the gate instead skips
            # charging the user's monthly quota (they weren't served a full result); the UI
            # surfaces it honestly via the quality badge + one-click Regenerate.
            count_usage = not (settings.AI_QUALITY_GATE and quality["tier"] == "partial")
            if not count_usage:
                logger.info(
                    f"[stream:{filing_id}] Quality gate: tier=partial, not charging usage "
                    f"(reasons: {quality['reasons']})"
                )

            # DB OP: Persist summary
            def save_summary_sync():
                filing_for_cache = session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()

                if force_regenerate:
                    # Admin refresh-stale: UPDATE the existing row IN PLACE (preserve summaries.id so
                    # the saved_summaries FK/bookmark survives and UNIQUE(filing_id) holds) instead of
                    # delete+insert, guarded by a keep-better gate.
                    existing = session.query(Summary).filter(Summary.filing_id == filing_id).first()
                    if existing is not None:
                        stored_tier = ((existing.raw_summary or {}).get("quality") or {}).get("tier")
                        new_tier = (quality or {}).get("tier")
                        if quality_tier_rank(new_tier) < quality_tier_rank(stored_tier):
                            # Never let a refresh downgrade a stored higher tier (a 75s AI-timeout
                            # XBRL fallback comes back "partial"; keep the stored "full").
                            logger.info(
                                "[stream:%s] refresh keep-better: keeping stored tier=%s over new tier=%s",
                                filing_id, stored_tier, new_tier,
                            )
                            return existing.id
                        existing.business_overview = markdown
                        existing.financial_highlights = normalized_financial_section
                        existing.risk_factors = risk_section
                        existing.management_discussion = management_section
                        existing.key_changes = guidance_section
                        # Reassign a NEW dict so SQLAlchemy marks the JSON column dirty and emits UPDATE.
                        existing.raw_summary = raw_summary
                        existing.schema_version = SUMMARY_SCHEMA_VERSION
                        existing.prompt_version = SUMMARY_PROMPT_VERSION
                        if filing_for_cache:
                            upsert_content_cache(
                                session, filing_id, filing_for_cache.content_cache,
                                excerpt=excerpt, sections_payload=sections_info,
                            )
                        session.commit()
                        return existing.id
                    # force on a filing with no stored summary yet: fall through to a normal INSERT.

                summary = Summary(
                    filing_id=filing_id,
                    business_overview=markdown,
                    financial_highlights=normalized_financial_section,
                    risk_factors=risk_section,
                    management_discussion=management_section,
                    key_changes=guidance_section,
                    raw_summary=raw_summary,
                    schema_version=SUMMARY_SCHEMA_VERSION,
                    prompt_version=SUMMARY_PROMPT_VERSION,
                )
                session.add(summary)

                if filing_for_cache:
                    upsert_content_cache(
                        session,
                        filing_id,
                        filing_for_cache.content_cache,
                        excerpt=excerpt,
                        sections_payload=sections_info,
                    )

                try:
                    session.commit()
                    return summary.id
                except IntegrityError:
                    # A concurrent writer (cron / another instance) persisted this filing's summary
                    # first — filing_id is UNIQUE. Serve the winner's row instead of erroring the
                    # user's stream (S1 decision #3).
                    session.rollback()
                    existing = session.query(Summary).filter(Summary.filing_id == filing_id).first()
                    if existing is None:
                        raise
                    return existing.id

            saved_summary_id = await run_sync_db(save_summary_sync)

            mark_stage("persist_summary")

            if user_id and count_usage:
                def track_usage_sync():
                    user = session.query(User).filter(User.id == user_id).first()
                    if user:
                        month = get_current_month()
                        increment_user_usage(user.id, month, session)

                await run_sync_db(track_usage_sync)

            mark_stage("usage_tracking")

            # DB OP: Record complete
            await run_sync_db(record_progress, session, filing_id, "completed")

            summary_status = summary_payload.get("status", "complete")
            summary_message = summary_payload.get("message")

            # A persisted result with status "error" means only fallback content was
            # produced — count it as a failure in the funnel, not a success.
            emit_funnel(
                telemetry_distinct_id,
                EVENT_GENERATION_SUCCEEDED if summary_status != "error" else EVENT_GENERATION_FAILED,
                duration_ms=elapsed_ms(),
                result_type=summary_status,
                quality_verdict=quality.get("tier"),
                figures_untraceable_count=len(quality.get("figures_untraceable") or []),
                entry_point=telemetry_entry_point,
                **telemetry_ctx,
            )

            yield {'type': 'chunk', 'content': markdown}

            if summary_status == "partial":
                yield {'type': 'partial', 'message': summary_message or 'Some sections may not have loaded fully.', 'summary_id': saved_summary_id}
            elif summary_status == "error":
                yield {'type': 'error', 'message': summary_message or 'Error generating summary', 'summary_id': saved_summary_id}
            else:
                yield {'type': 'complete', 'summary_id': saved_summary_id, 'percent': 100}
    except TimeoutError:
        # Pipeline hard timeout reached
        logger.warning(f"[stream:{filing_id}] Pipeline timeout after {PIPELINE_TIMEOUT_SECONDS}s")
        emit_funnel(
            telemetry_distinct_id,
            EVENT_GENERATION_TIMED_OUT,
            duration_ms=elapsed_ms(),
            result_type="timeout",
            entry_point=telemetry_entry_point,
            **telemetry_ctx,
        )
        # Record on a FRESH session. asyncio.timeout cancels the pending await, but the
        # threadpool worker behind it may still be using `session` (threads aren't
        # cancellable) and SQLAlchemy Sessions aren't thread-safe — touching the shared one
        # here would race. The shared session is cleaned up in `finally`.
        def record_timeout_progress():
            with database.SessionLocal() as err_session:
                record_progress(err_session, filing_id, "error", error="Pipeline timeout")
        try:
            await run_sync_db(record_timeout_progress)
        except Exception as e:
            logger.error(f"[stream:{filing_id}] Failed to record pipeline timeout error: {e}", exc_info=True)
        yield {'type': 'error', 'message': 'Summary generation timed out. Please try again.'}
    except Exception as e:
        logger.error(f"[stream:{filing_id}] Error in streaming summary: {str(e)}", exc_info=True)
        error_msg = str(e)
        emit_funnel(
            telemetry_distinct_id,
            EVENT_GENERATION_FAILED,
            duration_ms=elapsed_ms(),
            result_type="error",
            entry_point=telemetry_entry_point,
            error=error_msg[:200],
            **telemetry_ctx,
        )
        # Record on a fresh session: the shared session may carry a poisoned transaction from
        # the failed op (and could still be in use by its threadpool worker). The shared
        # session is rolled back/closed in `finally`.
        def record_stream_error_progress():
            with database.SessionLocal() as err_session:
                record_progress(err_session, filing_id, "error", error=error_msg[:200])
        try:
            await run_sync_db(record_stream_error_progress)
        except Exception as e:
            logger.error(f"[stream:{filing_id}] Failed to record streaming error: {e}", exc_info=True)

        if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
            error_message = error_msg[:200]
        else:
            error_message = "Unable to retrieve this filing at the moment — please try again shortly."

        yield {'type': 'error', 'message': error_message}
    finally:
        # Release the generation slot first (only if actually acquired), then in-flight leadership,
        # so a queued generation can start as soon as this one is done.
        if generation_slot_held and generation_semaphore is not None:
            generation_semaphore.release()
        # A3: release in-flight leadership so any waiters proceed and serve the persisted result.
        # Runs on completion, error, timeout, AND GeneratorExit (client disconnect) — never leaks a slot.
        if inflight_event is not None:
            _release_inflight(filing_id, inflight_event)
        try:
            session.close()
        except Exception as e:
            logger.error(f"[stream:{filing_id}] Failed to close session: {e}", exc_info=True)

        total_elapsed = time.time() - pipeline_started_at
        breakdown = ", ".join(f"{stage}:{duration:.2f}s" for stage, duration in stage_timings)
        if breakdown:
            logger.info(f"[stream:{filing_id}] pipeline finished in {total_elapsed:.2f}s ({breakdown})")
        else:
            logger.info(f"[stream:{filing_id}] pipeline finished in {total_elapsed:.2f}s")
