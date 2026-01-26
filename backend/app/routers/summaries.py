from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional, Dict, Any, List
import asyncio
import time
import datetime
from datetime import timedelta
import json
import concurrent.futures
from pydantic import BaseModel
import logging
from fastapi.responses import Response, StreamingResponse

from app.database import get_db, SessionLocal
from app.models import (
    Filing,
    Summary,
    User,
    SummaryGenerationProgress,
    FilingContentCache,
)
from app.services.sec_edgar import sec_edgar_service
from app.services.openai_service import openai_service
from app.services.xbrl_service import xbrl_service
from app.schemas import attach_normalized_facts
from app.routers.auth import get_current_user, get_current_user_optional
from app.services.subscription_service import check_usage_limit, increment_user_usage, get_current_month
from app.services.export_service import export_service
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.summary_generation_service import (
    generate_summary_background,
    get_generation_progress_snapshot,
    record_progress,
    progress_as_dict,
    get_or_cache_excerpt
)
from app.services.fallback_summary import generate_xbrl_summary

router = APIRouter()
logger = logging.getLogger(__name__)
SUMMARY_LIMITER = RateLimiter(limit=5, window_seconds=60)

# Hard pipeline timeout to guarantee user receives response within this time
PIPELINE_TIMEOUT_SECONDS = 90

# Timeout for XBRL/excerpt enrichment - SEC API for large companies can take 5-10s
CONTEXT_ENRICHMENT_TIMEOUT_SECONDS = 8.0

class SummaryResponse(BaseModel):
    id: int
    filing_id: int
    business_overview: Optional[str]
    financial_highlights: Optional[dict]
    risk_factors: Optional[list]
    management_discussion: Optional[str]
    key_changes: Optional[str]
    raw_summary: Optional[dict]
    
    class Config:
        from_attributes = True

@router.get("/filing/{filing_id}/progress")
async def get_summary_progress(
    filing_id: int,
    db: Session = Depends(get_db)
):
    """Get progress status for summary generation"""
    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        # Summary exists, return completed status
        return {
            "stage": "completed",
            "elapsedSeconds": 0
        }
    
    progress = (
        db.query(SummaryGenerationProgress)
        .filter(SummaryGenerationProgress.filing_id == filing_id)
        .first()
    )
    if progress:
        return progress_as_dict(progress)

    return {"stage": "pending", "elapsedSeconds": 0}

@router.post("/filing/{filing_id}/generate", response_model=SummaryResponse)
async def generate_summary(
    filing_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate AI summary for a filing"""
    enforce_rate_limit(
        request,
        SUMMARY_LIMITER,
        f"summary:{current_user.id}",
        error_detail="Too many summary requests. Please try again shortly.",
    )
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    
    if summary:
        return summary
    
    try:
        # Lock the row for the given filing_id to prevent race conditions
        progress = (
            db.query(SummaryGenerationProgress)
            .filter(SummaryGenerationProgress.filing_id == filing_id)
            .with_for_update()
            .first()
        )

        # If progress exists and is not in an error state, another task is already running or completed
        if progress and progress.stage not in ["error"]:
            # Return a response indicating that generation is already in progress
            return {
                "id": 0,
                "filing_id": filing_id,
                "business_overview": "Summary generation is already in progress.",
                "financial_highlights": None,
                "risk_factors": None,
                "management_discussion": None,
                "key_changes": None,
                "raw_summary": None,
            }

        # Check usage limits for authenticated user
        user_id = current_user.id
        can_generate, current_count, limit = check_usage_limit(current_user, db)
        if not can_generate:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"You've reached your monthly limit of {limit} summaries. "
                    "Upgrade to Pro for unlimited summaries."
                ),
            )

        # If no progress or errored progress, (re)start the generation
        record_progress(db, filing_id, "queued")
        db.commit()

        asyncio.create_task(generate_summary_background(filing_id, user_id))
    except Exception as e:
        db.rollback()
        raise e
    finally:
        # The rollback is handled by the exception block, and commit by the happy path.
        # The session is closed by the dependency injection system.
        pass
    
    # Return placeholder response with accurate timing
    return {
        "id": 0,
        "filing_id": filing_id,
        "business_overview": "Generating summary... This typically takes 15-30 seconds.",
        "financial_highlights": None,
        "risk_factors": None,
        "management_discussion": None,
        "key_changes": None,
        "raw_summary": None
    }

@router.post("/filing/{filing_id}/generate-stream")
async def generate_summary_stream(
    filing_id: int,
    request: Request,
    force: bool = False,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Generate AI summary with streaming response (guests allowed).

    Args:
        force: If True, delete existing summary and regenerate from scratch.
               Use this for "Regenerate Analysis" functionality.
    """
    # Use user ID for authenticated users, IP for guests
    client_host = request.client.host if request.client else "unknown"
    user_id_log = current_user.id if current_user else "Guest"
    logger.info(f"[stream:{filing_id}] Incoming stream request from {user_id_log} (IP: {client_host}, force={force})")

    rate_limit_key = f"summary:{current_user.id}" if current_user else f"summary:guest:{client_host}"

    enforce_rate_limit(
        request,
        SUMMARY_LIMITER,
        rate_limit_key,
        error_detail="Too many summary requests. Please try again shortly.",
    )
    # Eagerly load content_cache and company relationship to avoid detached session issues
    filing = db.query(Filing).options(
        joinedload(Filing.content_cache),
        joinedload(Filing.company)
    ).filter(Filing.id == filing_id).first()

    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        if force:
            # Force regeneration: delete existing summary and related data
            logger.info(f"[stream:{filing_id}] Force regeneration requested - deleting existing summary")
            db.delete(summary)

            # Also clear XBRL data to get fresh data
            if filing.xbrl_data is not None:
                filing.xbrl_data = None
                logger.info(f"[stream:{filing_id}] Cleared XBRL data for regeneration")

            # Clear progress record
            progress = db.query(SummaryGenerationProgress).filter(
                SummaryGenerationProgress.filing_id == filing_id
            ).first()
            if progress:
                db.delete(progress)

            db.commit()
        else:
            # Return existing summary as JSON
            async def existing_summary():
                payload = {
                    'type': 'complete',
                    'summary': summary.business_overview,
                    'summary_id': summary.id,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            return StreamingResponse(existing_summary(), media_type="text/event-stream")

    # Removed blocking synchronous DB query here. Filing existence is checked inside stream_summary.
    # Removed caching of company data and filing attributes here. These will be fetched inside stream_summary.

    user_id = current_user.id if current_user else None
    logger.info(f"[stream:{filing_id}] Starting summary stream for user {user_id}")

    async def stream_summary():
        # Create a new session for the async generator to avoid detached session issues
        from app.database import SessionLocal
        from fastapi.concurrency import run_in_threadpool
        
        # Hard pipeline timeout to guarantee user receives response within this time
        PIPELINE_TIMEOUT_SECONDS = 90
        
        pipeline_started_at = time.time()
        stage_started_at = pipeline_started_at
        stage_timings: List[tuple[str, float]] = []

        def mark_stage(stage_name: str):
            nonlocal stage_started_at
            now = time.time()
            duration = now - stage_started_at
            stage_timings.append((stage_name, duration))
            stage_started_at = now

        # We need to manage the session manually since we can't use 'with' easily across async boundaries with threads
        # but since we are refactoring to use run_in_threadpool with scoped logic, we can improve this.
        # However, for now, let's keep the manual session management to minimize diff churn, but optimize the execution.
        session = SessionLocal()

        async def run_sync_db(func, *args, **kwargs):
            """Helper to run DB operations in default thread pool"""
            return await run_in_threadpool(func, *args, **kwargs)

        try:
            async with asyncio.timeout(PIPELINE_TIMEOUT_SECONDS):
                logger.info(f"[stream:{filing_id}] Stream generator started (timeout: {PIPELINE_TIMEOUT_SECONDS}s)")
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'initializing', 'message': 'Initializing...', 'percent': 0})}\n\n"

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
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Filing not found'})}\n\n"
                    return

                if summary_in_session:
                    logger.info(f"[stream:{filing_id}] Existing summary found. Returning it.")
                    payload = {
                        'type': 'complete',
                        'summary': summary_in_session.business_overview,
                        'summary_id': summary_in_session.id,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    return

            # Cache company data and filing attributes from the fetched filing
            company_name = filing_in_session.company.name if filing_in_session.company else "Unknown company"
            company_cik = filing_in_session.company.cik if filing_in_session.company else None
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
                
                age = datetime.datetime.now(datetime.timezone.utc) - last_updated
                if age < timedelta(hours=24):
                    cache_is_valid = True
                    excerpt_from_cache = cached_content.critical_excerpt
                    logger.info(f"[stream:{filing_id}] Using cached content (age: {age})")

            # Check usage limits for authenticated user
            if current_user:
                can_generate, current_count, limit = await run_sync_db(check_usage_limit, current_user, session)
                if not can_generate:
                    logger.warning(f"[stream:{filing_id}] User {user_id} exceeded monthly summary limit ({limit}).")
                    message = (
                        "You've reached your monthly limit of "
                        f"{limit} summaries. Upgrade to Pro for unlimited summaries."
                    )
                    payload = {"type": "error", "message": message}
                    yield f"data: {json.dumps(payload)}\n\n"
                    return
                logger.info(f"[stream:{filing_id}] Usage limit check passed for user {user_id}. Current count: {current_count}/{limit}")
            else:
                logger.info(f"[stream:{filing_id}] Guest user access. Rate limit already enforced.")
            # Note: We use cached values from outer scope, but filling_in_session is already populated.
            
            # Step 1: File Validation
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "fetching")
            
            logger.info(f"[stream:{filing_id}] Yielding fetching stage")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'Step 1: File Validation - Confirming document is accessible and parsable...', 'percent': 5, 'elapsed_seconds': int(time.time() - pipeline_started_at)})}\n\n"

            # Background refresh task definition
            async def background_fetch_and_update():
                try:
                    logger.info(f"[stream:{filing_id}] Background refresh: fetching doc")
                    text = await sec_edgar_service.get_filing_document(filing_document_url, timeout=30.0)
                    if not text:
                        return
                    
                    def update_cache_sync():
                        from app.database import SessionLocal
                        with SessionLocal() as bg_session:
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
                filing_text = "" # Empty text signals usage of excerpt to downstream services if robustness is handled
                logger.info(f"[stream:{filing_id}] Skipping main thread SEC fetch, using cache.")
                
                # Spawn background refresh
                asyncio.create_task(background_fetch_and_update())
                
                # Yield immediate progress
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'Cached content found. Loading immediately...', 'percent': 15})}\n\n"
            else:
                # Fetch filing document with heartbeat to prevent UI stall at 10%
                from app.config import settings
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
                        yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': fetch_message, 'percent': current_percent, 'elapsed_seconds': elapsed_secs})}\n\n"
                        fetch_heartbeat_index += 1
                    
                    # Get the result (or raise exception if task failed)
                    filing_text = await fetch_task
                    logger.info(f"[stream:{filing_id}] SEC fetch completed. Text length: {len(filing_text) if filing_text else 0}")
                    
                    if not filing_text:
                        raise ValueError("Filing document is empty or inaccessible")
                    
                    mark_stage("fetch_document")
                    yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'File validated and fetched successfully', 'percent': 15})}\n\n"

                except Exception as fetch_error:
                    logger.error(f"[stream:{filing_id}] Error fetching SEC document: {fetch_error}", exc_info=True)
                    error_msg = "Unable to retrieve this filing at the moment — please try again shortly."
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                    return
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Starting parsing...', 'percent': 15})}\n\n"

            # Step 2: Section Parsing
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "parsing")
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...', 'percent': 20})}\n\n"
            
            # Extract excerpt
            def extract_excerpt_sync():
                from app.database import SessionLocal
                with SessionLocal() as thread_session:
                    thread_filing = thread_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                    return get_or_cache_excerpt(thread_session, thread_filing, filing_text)
            
            if cache_is_valid:
                # Use the cached excerpt directly
                async def return_cached_excerpt():
                    return excerpt_from_cache
                excerpt_task = asyncio.create_task(return_cached_excerpt())
            else:
                excerpt_task = asyncio.create_task(run_sync_db(extract_excerpt_sync))
            
            # Start XBRL fetching in parallel
            xbrl_task = None
            if filing_type and filing_type.upper() in {"10-K", "10-Q"} and company_cik:
                async def fetch_xbrl():
                    try:
                        data = await xbrl_service.get_xbrl_data(filing_accession_number, company_cik)
                        if data:
                            metrics = xbrl_service.extract_standardized_metrics(data)
                            
                            # DB OP: Update filing xbrl_data
                            def update_xbrl_sync():
                                # Use a new session for this thread operation to ensure thread safety
                                from app.database import SessionLocal
                                with SessionLocal() as xbrl_session:
                                    filing_for_update = xbrl_session.query(Filing).filter(Filing.id == filing_id).first()
                                    if filing_for_update:
                                        filing_for_update.xbrl_data = data
                                        xbrl_session.commit()
                            
                            await run_sync_db(update_xbrl_sync)
                            return metrics
                    except Exception as xbrl_error:
                        logger.warning(f"[stream:{filing_id}] Error updating XBRL data: {str(xbrl_error)}")
                        pass
                    return None
                xbrl_task = asyncio.create_task(fetch_xbrl())
            
            # Wait for parsing to complete
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Parsing complete...', 'percent': 25})}\n\n"

            # Step 3: Content Analysis
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "analyzing")
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Step 3: Content Analysis - Analyzing risk factors...', 'percent': 35})}\n\n"

            # Step 4: Summary Generation
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Step 4: Generating financial overview...', 'percent': 45})}\n\n"

            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "summarizing")
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'message': 'Step 5: Generating investor-focused summary...', 'percent': 50})}\n\n"
            
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

            # Now run AI summarization (with excerpt/XBRL if available)
            # Wrap in task to enable heartbeat loop while waiting
            summary_task = asyncio.create_task(openai_service.summarize_filing(
                filing_text,
                company_name,
                filing_type,
                previous_filings=None,
                xbrl_metrics=xbrl_metrics,
                filing_excerpt=excerpt,
            ))

            from app.config import settings
            
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
                ai_duration = current_time - (pipeline_started_at + 30) # rough estimate, or track start of AI stage
                # Better: track stage_started_at for AI
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
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'message': heartbeat_message, 'heartbeat_count': summarize_heartbeat_index, 'percent': current_percent, 'elapsed_seconds': elapsed_secs})}\n\n"
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
                yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
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

            financial_section = sections_info.get("financial_highlights")
            normalized_financial_section = attach_normalized_facts(financial_section, xbrl_metrics)
            if normalized_financial_section is not None:
                sections_info["financial_highlights"] = normalized_financial_section

            risk_section = summary_payload.get("risk_factors") or []
            sections_info["risk_factors"] = risk_section
            management_section = summary_payload.get("management_discussion")
            guidance_section = summary_payload.get("key_changes")

            # CRITICAL: Add MD&A and guidance to sections_info for frontend tabs
            # Frontend reads from raw_summary.sections, not top-level fields
            if management_section and "management_discussion_insights" not in sections_info:
                # Wrap in expected structure if not already present from AI
                sections_info["management_discussion_insights"] = {
                    "themes": [management_section] if isinstance(management_section, str) else management_section,
                    "quotes": [],
                    "capital_allocation": []
                }

            if guidance_section and "guidance_outlook" not in sections_info:
                # Wrap in expected structure if not already present from AI
                sections_info["guidance_outlook"] = {
                    "outlook": guidance_section if isinstance(guidance_section, str) else str(guidance_section),
                    "targets": [],
                    "assumptions": []
                }

            raw_summary["sections"] = sections_info
            raw_summary["status"] = summary_status

            # DB OP: Persist summary
            def save_summary_sync():
                filing_for_cache = session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()

                summary = Summary(
                    filing_id=filing_id,
                    business_overview=markdown,
                    financial_highlights=normalized_financial_section,
                    risk_factors=risk_section,
                    management_discussion=management_section,
                    key_changes=guidance_section,
                    raw_summary=raw_summary
                )
                session.add(summary)

                if filing_for_cache:
                    cache = filing_for_cache.content_cache
                    if sections_info:
                        if cache is None:
                            cache = FilingContentCache(
                                filing_id=filing_id,
                                critical_excerpt=excerpt,
                                sections_payload=sections_info,
                            )
                            session.add(cache)
                        else:
                            if excerpt and not cache.critical_excerpt:
                                cache.critical_excerpt = excerpt
                            cache.sections_payload = sections_info
                    elif excerpt and cache is None:
                        cache = FilingContentCache(filing_id=filing_id, critical_excerpt=excerpt)
                        session.add(cache)

                session.commit()
                return summary.id

            saved_summary_id = await run_sync_db(save_summary_sync)
            
            mark_stage("persist_summary")

            if user_id:
                def track_usage_sync():
                    from app.models import User
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
            
            yield f"data: {json.dumps({'type': 'chunk', 'content': markdown})}\n\n"
            
            if summary_status == "partial":
                yield f"data: {json.dumps({'type': 'partial', 'message': summary_message or 'Some sections may not have loaded fully.', 'summary_id': saved_summary_id})}\n\n"
            elif summary_status == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': summary_message or 'Error generating summary', 'summary_id': saved_summary_id})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'summary_id': saved_summary_id, 'percent': 100})}\n\n"
        except TimeoutError:
            # Pipeline hard timeout reached
            logger.warning(f"[stream:{filing_id}] Pipeline timeout after {PIPELINE_TIMEOUT_SECONDS}s")
            try:
                await run_sync_db(record_progress, session, filing_id, "error", error="Pipeline timeout")
            except Exception as e:
                logger.error(f"[stream:{filing_id}] Failed to record pipeline timeout error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Summary generation timed out. Please try again.'})}\n\n"
        except Exception as e:
            logger.error(f"[stream:{filing_id}] Error in streaming summary: {str(e)}", exc_info=True)
            error_msg = str(e)
            try:
                await run_sync_db(record_progress, session, filing_id, "error", error=error_msg[:200])
            except Exception as e:
                logger.error(f"[stream:{filing_id}] Failed to record streaming error: {e}", exc_info=True)
            
            if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
                error_message = error_msg[:200]
            else:
                error_message = "Unable to retrieve this filing at the moment — please try again shortly."
            
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
        finally:
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

    return StreamingResponse(stream_summary(), media_type="text/event-stream")

@router.get("/filing/{filing_id}", response_model=SummaryResponse)
async def get_summary(filing_id: int, db: Session = Depends(get_db)):
    """Get summary for a filing"""
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    
    if not summary:
        # Return empty summary instead of 404 to allow frontend to trigger generation
        return {
            "id": 0,
            "filing_id": filing_id,
            "business_overview": None,
            "financial_highlights": None,
            "risk_factors": None,
            "management_discussion": None,
            "key_changes": None,
            "raw_summary": None
        }
    
    return summary

@router.get("/filing/{filing_id}/export/pdf")
async def export_summary_pdf(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export summary as PDF (Pro feature)"""
    from app.routers.auth import get_current_user
    
    # Require authentication for exports
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if user is Pro
    if not current_user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PDF export is a Pro feature. Upgrade to Pro to access this feature."
        )
    
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    try:
        pdf_bytes = await export_service.export_pdf(summary, filing)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filing.company.name}_{filing.filing_type}_{filing.filing_date.strftime("%Y%m%d") if filing.filing_date else "summary"}.pdf"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )

@router.get("/filing/{filing_id}/export/csv")
async def export_summary_csv(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Export summary financial metrics as CSV (Pro feature)"""
    from app.routers.auth import get_current_user
    
    # Require authentication for exports
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if user is Pro
    if not current_user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSV export is a Pro feature. Upgrade to Pro to access this feature."
        )
    
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    try:
        csv_content = export_service.generate_csv(summary, filing)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filing.company.name}_{filing.filing_type}_{filing.filing_date.strftime("%Y%m%d") if filing.filing_date else "summary"}.csv"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate CSV: {str(e)}"
        )
