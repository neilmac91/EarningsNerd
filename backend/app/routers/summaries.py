from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional, Dict, Any, List
import asyncio
import time
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

router = APIRouter()
logger = logging.getLogger(__name__)
SUMMARY_LIMITER = RateLimiter(limit=5, window_seconds=60)

# Hard pipeline timeout to guarantee user receives response within this time
PIPELINE_TIMEOUT_SECONDS = 90

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
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Generate AI summary with streaming response (guests allowed)"""
    # Use user ID for authenticated users, IP for guests
    client_host = request.client.host if request.client else "unknown"
    user_id_log = current_user.id if current_user else "Guest"
    logger.info(f"Incoming stream request for filing {filing_id} from {user_id_log} (IP: {client_host})")
    
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
    logger.info(f"Starting summary stream for filing {filing_id}, user {user_id}")

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
                logger.info(f"Stream generator started for filing {filing_id} (timeout: {PIPELINE_TIMEOUT_SECONDS}s)")
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'initializing', 'message': 'Initializing...'})}\n\n"

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
                    logger.warning(f"Filing {filing_id} not found during stream generation.")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Filing not found'})}\n\n"
                    return

                if summary_in_session:
                    logger.info(f"Existing summary found for filing {filing_id}. Returning it.")
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

            # Check usage limits for authenticated user
            if current_user:
                can_generate, current_count, limit = await run_sync_db(check_usage_limit, current_user, session)
                if not can_generate:
                    logger.warning(f"User {user_id} exceeded monthly summary limit ({limit}) for filing {filing_id}.")
                    message = (
                        "You've reached your monthly limit of "
                        f"{limit} summaries. Upgrade to Pro for unlimited summaries."
                    )
                    payload = {"type": "error", "message": message}
                    yield f"data: {json.dumps(payload)}\n\n"
                    return
                logger.info(f"Usage limit check passed for user {user_id}. Current count: {current_count}/{limit}")
            else:
                logger.info(f"Guest user accessing filing {filing_id}. Rate limit already enforced.")
            # Note: We use cached values from outer scope, but filling_in_session is already populated.
            
            # Step 1: File Validation
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "fetching")
            
            logger.info(f"Yielding fetching stage for filing {filing_id}")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'Step 1: File Validation - Confirming document is accessible and parsable...', 'elapsed_seconds': int(time.time() - pipeline_started_at)})}\n\n"

            # Fetch filing document with heartbeat to prevent UI stall at 10%
            from app.config import settings
            FETCH_MESSAGES = [
                "Connecting to SEC EDGAR...",
                "Downloading filing document...",
                "Retrieving full document text...",
                "Processing SEC response...",
            ]
            
            try:
                logger.info(f"Starting SEC fetch for URL: {filing_document_url}")
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
                    logger.info(f"SEC fetch heartbeat {fetch_heartbeat_index + 1}: {fetch_message}")
                    yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': fetch_message, 'elapsed_seconds': elapsed_secs})}\n\n"
                    fetch_heartbeat_index += 1
                
                # Get the result (or raise exception if task failed)
                filing_text = await fetch_task
                logger.info(f"SEC fetch completed. Text length: {len(filing_text) if filing_text else 0}")
                
                if not filing_text:
                    raise ValueError("Filing document is empty or inaccessible")
            except Exception as fetch_error:
                logger.error(f"Error fetching SEC document: {fetch_error}", exc_info=True)
                error_msg = "Unable to retrieve this filing at the moment — please try again shortly."
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                return
            
            mark_stage("fetch_document")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'File validated and fetched successfully'})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Starting parsing...'})}\n\n"

            # Step 2: Section Parsing
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "parsing")
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...'})}\n\n"
            
            # Extract excerpt
            def extract_excerpt_sync():
                from app.database import SessionLocal
                with SessionLocal() as thread_session:
                    thread_filing = thread_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                    return get_or_cache_excerpt(thread_session, thread_filing, filing_text)
            
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
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Parsing complete...'})}\n\n"

            # Step 3: Content Analysis
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "analyzing")
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Step 3: Content Analysis - Analyzing risk factors...'})}\n\n"

            # Step 4: Summary Generation
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Step 4: Generating financial overview...'})}\n\n"

            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "summarizing")
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'message': 'Step 5: Generating investor-focused summary...'})}\n\n"
            
            # Wait for excerpt and XBRL with a short timeout (don't block AI for too long)
            excerpt = None
            xbrl_metrics = None
            try:
                # Give excerpt/XBRL 2 seconds max, then proceed with AI
                tasks_to_wait = [excerpt_task]
                if xbrl_task:
                    tasks_to_wait.append(xbrl_task)
                
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks_to_wait, return_exceptions=True),
                    timeout=2.0
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
            
            
            while not summary_task.done():
                done, pending = await asyncio.wait(
                    [summary_task], 
                    timeout=settings.STREAM_HEARTBEAT_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if summary_task in done:
                    break
                
                heartbeat_message = SUMMARIZE_MESSAGES[summarize_heartbeat_index % len(SUMMARIZE_MESSAGES)]
                elapsed_secs = int(time.time() - pipeline_started_at)
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'message': heartbeat_message, 'heartbeat_count': summarize_heartbeat_index, 'elapsed_seconds': elapsed_secs})}\n\n"
                summarize_heartbeat_index += 1
            
            summary_payload = await summary_task
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

            raw_summary["sections"] = sections_info

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
                yield f"data: {json.dumps({'type': 'complete', 'summary_id': saved_summary_id})}\n\n"
        except TimeoutError:
            # Pipeline hard timeout reached
            logger.warning(f"Pipeline timeout after {PIPELINE_TIMEOUT_SECONDS}s for filing {filing_id}")
            try:
                await run_sync_db(record_progress, session, filing_id, "error", error="Pipeline timeout")
            except Exception as e:
                logger.error(f"Failed to record pipeline timeout error for filing {filing_id}: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Summary generation timed out. Please try again.'})}\n\n"
        except Exception as e:
            logger.error(f"Error in streaming summary: {str(e)}", exc_info=True)
            error_msg = str(e)
            try:
                await run_sync_db(record_progress, session, filing_id, "error", error=error_msg[:200])
            except Exception as e:
                logger.error(f"Failed to record streaming error for filing {filing_id}: {e}", exc_info=True)
            
            # Always expose the raw error for debugging purposes in this branch
            error_message = f"DEBUG_ERROR: {str(e)}[:200]"
            
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
        finally:
            try:
                session.close()
            except Exception as e:
                logger.error(f"Failed to close session for filing {filing_id}: {e}", exc_info=True)
            
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
