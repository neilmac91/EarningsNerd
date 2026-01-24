from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session, joinedload
from typing import Optional, Dict, Any, List
import asyncio
import time
import json
import concurrent.futures
from pydantic import BaseModel
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
SUMMARY_LIMITER = RateLimiter(limit=5, window_seconds=60)

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate AI summary with streaming response"""
    enforce_rate_limit(
        request,
        SUMMARY_LIMITER,
        f"summary:{current_user.id}",
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
    
    # Cache company data before streaming to avoid detached session issues
    company_name = filing.company.name if filing.company else "Unknown company"
    company_cik = filing.company.cik if filing.company else None
    
    # Cache all filing attributes we need to avoid detached session issues
    filing_document_url = filing.document_url
    filing_type = filing.filing_type
    filing_accession_number = filing.accession_number

    user_id = current_user.id
    can_generate, current_count, limit = check_usage_limit(current_user, db)
    if not can_generate:
        async def error_response():
            message = (
                "You've reached your monthly limit of "
                f"{limit} summaries. Upgrade to Pro for unlimited summaries."
            )
            payload = {"type": "error", "message": message}
            yield f"data: {json.dumps(payload)}\n\n"
        return StreamingResponse(error_response(), media_type="text/event-stream")
    
    async def stream_summary():
        # Create a new session for the async generator to avoid detached session issues
        from app.database import SessionLocal
        
        # Use a dedicated executor for DB operations to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)

        async def run_sync_db(func, *args, **kwargs):
            """Helper to run DB operations in thread pool"""
            return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

        # We need to manage the session manualy since we can't use 'with' easily across async boundaries with threads
        session = SessionLocal()
        
        pipeline_started_at = time.time()
        stage_started_at = pipeline_started_at
        stage_timings: List[tuple[str, float]] = []

        def mark_stage(stage_name: str):
            nonlocal stage_started_at
            now = time.time()
            duration = now - stage_started_at
            stage_timings.append((stage_name, duration))
            stage_started_at = now

        try:
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'initializing', 'message': 'Initializing...'})}\n\n"

            # Note: We use cached values (company_name, filing_type, etc.) from the outer scope
            # to avoid detached session issues. Only re-query when we need to access relationships
            # or update the filing object.
            
            # DB OP: Query filing
            def get_filing_sync():
                return session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
            
            filing_in_session = await run_sync_db(get_filing_sync)
            
            if not filing_in_session:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Filing not found'})}\n\n"
                return

            # Step 1: File Validation
            # DB OP: Record progress
            await run_sync_db(record_progress, session, filing_id, "fetching")
            
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
                # Wrap the SEC fetch in a task with heartbeat loop
                fetch_task = asyncio.create_task(
                    sec_edgar_service.get_filing_document(filing_document_url, timeout=25.0)
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
                    yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': fetch_message, 'elapsed_seconds': elapsed_secs})}\n\n"
                    fetch_heartbeat_index += 1
                
                # Get the result (or raise exception if task failed)
                filing_text = await fetch_task
                
                if not filing_text:
                    raise ValueError("Filing document is empty or inaccessible")
            except Exception as fetch_error:
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
            
            # Extract excerpt - already offloaded to executor in original code, but we can use our executor
            def extract_excerpt_sync():
                    # Use the main session here since we are in a thread anyway, but create a new one to be safe/clean
                    # or reuse the one we have if it's thread-safe enough (Session is not thread safe).
                    # Safest is to use a fresh session for this read-only op or reuse the managed session if we lock it.
                    # Given the original code created a new session, let's stick to that pattern for the heavy extraction.
                from app.database import SessionLocal
                with SessionLocal() as thread_session:
                    thread_filing = thread_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                    return get_or_cache_excerpt(thread_session, thread_filing, filing_text)
            
            # We can reuse our `run_sync_db` which uses `executor`
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
                                filing_for_update = session.query(Filing).filter(Filing.id == filing_id).first()
                                if filing_for_update:
                                    filing_for_update.xbrl_data = data
                                    session.commit()
                            
                            await run_sync_db(update_xbrl_sync)
                            return metrics
                    except Exception as xbrl_error:
                        print(f"[stream:{filing_id}] Error updating XBRL data: {str(xbrl_error)}")
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
                # Proceed without excerpt/XBRL if they take too long
                excerpt = None
                xbrl_metrics = None
            except Exception as e:
                # If anything fails, proceed without excerpt/XBRL
                print(f"[stream:{filing_id}] Error waiting for excerpt/XBRL: {str(e)}")
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

            # Heartbeat loop - keep connection alive while waiting for AI
            # This prevents HTTP connection timeout during long-running AI operations
            from app.config import settings
            
            # Rotating heartbeat messages for better UX during long AI operations
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
                # Wait for task completion or heartbeat interval
                done, pending = await asyncio.wait(
                    [summary_task], 
                    timeout=settings.STREAM_HEARTBEAT_INTERVAL,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if summary_task in done:
                    # Task completed, exit loop
                    break
                
                # Task still running, send heartbeat with rotating message and timing info
                heartbeat_message = SUMMARIZE_MESSAGES[summarize_heartbeat_index % len(SUMMARIZE_MESSAGES)]
                elapsed_secs = int(time.time() - pipeline_started_at)
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'message': heartbeat_message, 'heartbeat_count': summarize_heartbeat_index, 'elapsed_seconds': elapsed_secs})}\n\n"
                summarize_heartbeat_index += 1
            
            # Get result (or raise exception if task failed)
            summary_payload = await summary_task
            mark_stage("generate_summary")

            # Check if summary has error status - handle early
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
                # DB OP: Record progress
                await run_sync_db(
                    record_progress,
                    session,
                    filing_id,
                    "summarizing",
                    section_coverage=section_coverage,
                )
                print(
                    f"[stream:{filing_id}] coverage snapshot: "
                    f"{section_coverage.get('covered_count', 0)}/"
                    f"{section_coverage.get('total_count', 0)} sections populated"
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
                # Re-query filing to ensure it's attached to session before accessing content_cache
                filing_for_cache = session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()

                # Save to database
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

                # Now filing is attached to session, we can safely access content_cache
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
                # Return summary_id so we have it for the response if needed (though we rely on summary object usually)
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

            # Check summary status and emit appropriate response
            summary_status = summary_payload.get("status", "complete")
            summary_message = summary_payload.get("message")
            
            # Emit final markdown once
            yield f"data: {json.dumps({'type': 'chunk', 'content': markdown})}\n\n"
            
            # Emit status and completion
            if summary_status == "partial":
                yield f"data: {json.dumps({'type': 'partial', 'message': summary_message or 'Some sections may not have loaded fully.', 'summary_id': saved_summary_id})}\n\n"
            elif summary_status == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': summary_message or 'Error generating summary', 'summary_id': saved_summary_id})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'summary_id': saved_summary_id})}\n\n"
        except Exception as e:
            import traceback
            import sys
            error_trace = traceback.format_exc()
            error_msg = str(e)
            print(f"Error in streaming summary: {error_msg}", flush=True)
            print(f"Traceback: {error_trace}", flush=True)
            sys.stderr.write(f"[STREAM ERROR] {error_msg}\n{error_trace}\n")
            sys.stderr.flush()
            try:
                await run_sync_db(record_progress, session, filing_id, "error", error=error_msg[:200])
            except:
                pass
            
            # Return user-friendly error message
            if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
                error_message = error_msg[:200]
            else:
                error_message = "Unable to retrieve this filing at the moment — please try again shortly."
            
            yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
        finally:
            # Clean up executor and session
            try:
                executor.shutdown(wait=False)
            except:
                pass
            try:
                session.close()
            except:
                pass
            
            total_elapsed = time.time() - pipeline_started_at
            breakdown = ", ".join(f"{stage}:{duration:.2f}s" for stage, duration in stage_timings)
            if breakdown:
                print(f"[stream:{filing_id}] pipeline finished in {total_elapsed:.2f}s ({breakdown})")
            else:
                print(f"[stream:{filing_id}] pipeline finished in {total_elapsed:.2f}s (no stage breakdown)")

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
