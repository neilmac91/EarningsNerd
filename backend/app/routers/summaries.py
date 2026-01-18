from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session, joinedload
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime, timezone
from app.database import get_db, SessionLocal
from app.models import (
    Filing,
    Summary,
    User,
    SummaryGenerationProgress,
    FilingContentCache,
)
from app.services.sec_edgar import sec_edgar_service
from app.services.openai_service import openai_service, _normalize_risk_factors
from app.services.xbrl_service import xbrl_service
from app.schemas import attach_normalized_facts
from app.routers.auth import get_current_user_optional, get_current_user
from app.routers.subscriptions import check_usage_limit, increment_user_usage, get_current_month
from app.services.export_service import export_service
from fastapi.responses import Response, StreamingResponse
import json
from pydantic import BaseModel
import time

router = APIRouter()

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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _record_progress(
    db: Session,
    filing_id: int,
    stage: str,
    *,
    error: Optional[str] = None,
    section_coverage: Optional[Dict[str, Any]] = None,
) -> SummaryGenerationProgress:
    now = _utcnow()
    progress = (
        db.query(SummaryGenerationProgress)
        .filter(SummaryGenerationProgress.filing_id == filing_id)
        .first()
    )

    if not progress:
        progress = SummaryGenerationProgress(
            filing_id=filing_id,
            stage=stage,
            started_at=now,
            updated_at=now,
            elapsed_seconds=0.0,
            error=error,
        )
        db.add(progress)
        if section_coverage is not None:
            progress.section_coverage = section_coverage
    else:
        progress.stage = stage
        if progress.started_at is None:
            progress.started_at = now
        progress.updated_at = now
        # Handle timezone-aware vs timezone-naive datetime comparison
        started_at = progress.started_at
        if started_at.tzinfo is None:
            # Convert timezone-naive to UTC if needed
            started_at = started_at.replace(tzinfo=timezone.utc)
        progress.elapsed_seconds = float((now - started_at).total_seconds())
        progress.error = error
        if section_coverage is not None:
            progress.section_coverage = section_coverage

    db.flush()
    db.commit()
    db.refresh(progress)
    return progress


def _progress_as_dict(progress: SummaryGenerationProgress) -> Dict[str, Any]:
    elapsed = progress.elapsed_seconds
    if elapsed is None and progress.started_at:
        # Handle timezone-aware vs timezone-naive datetime comparison
        started_at = progress.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed = float((_utcnow() - started_at).total_seconds())
    return {
        "stage": progress.stage,
        "elapsedSeconds": int(elapsed or 0),
        "error": progress.error,
        "updated_at": progress.updated_at.isoformat() if progress.updated_at else None,
        "sectionCoverage": progress.section_coverage,
    }


def _get_or_cache_excerpt(
    db: Session,
    filing: Filing,
    filing_text: Optional[str],
) -> Optional[str]:
    if not filing_text:
        return None

    # Get filing_id safely - it should be accessible even if filing is detached
    filing_id = filing.id if hasattr(filing, 'id') and filing.id else None
    if not filing_id:
        # If we can't get the ID, we can't proceed
        return None

    # Always query filing fresh with content_cache loaded to avoid detached session issues
    filing_reattached = db.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
    if not filing_reattached:
        # Filing not found - return None
        return None

    cache = filing_reattached.content_cache
    filing_type = filing_reattached.filing_type
    
    if cache and cache.critical_excerpt:
        return cache.critical_excerpt

    filing_type_key = (filing_type or "10-K").upper()
    excerpt = openai_service.extract_critical_sections(filing_text, filing_type_key)
    if excerpt:
        if cache is None:
            cache = FilingContentCache(filing_id=filing_id, critical_excerpt=excerpt)
            db.add(cache)
        else:
            cache.critical_excerpt = excerpt
        db.flush()
        db.commit()
    return excerpt

async def _generate_summary_background(filing_id: int, user_id: Optional[int]):
    """Background task to generate summary"""
    from app.database import SessionLocal
    
    # Create a new database session for the background task
    with SessionLocal() as db:
        print(f"Starting summary generation for filing {filing_id}")
        # Eagerly load content_cache and company relationship to avoid detached session issues
        filing = db.query(Filing).options(
            joinedload(Filing.content_cache),
            joinedload(Filing.company)
        ).filter(Filing.id == filing_id).first()
        if not filing:
            print(f"Filing {filing_id} not found")
            return
        
        # Cache company data early to avoid detached session issues
        company_name = filing.company.name if filing.company else "Company"
        filing_type = (filing.filing_type or "").upper()
        filing_document_url = filing.document_url
        filing_accession_number = filing.accession_number
        company_cik = filing.company.cik if filing.company else None
        
        # Check if summary already exists
        existing = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        if existing:
            print(f"Summary already exists for filing {filing_id}")
            # If summary already exists, still increment usage if user generated it
            if user_id:
                from app.models import User
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    month = get_current_month()
                    increment_user_usage(user.id, month, db)
            return
        
        # Check if OpenAI API key is configured
        from app.config import settings
        if not settings.OPENAI_API_KEY:
            print(f"Warning: OpenAI API key not configured. Cannot generate summary for filing {filing_id}")
            # Create a placeholder summary indicating API key is missing
            summary = Summary(
                filing_id=filing_id,
                business_overview=(
                    "Summary generation requires OpenAI API key. "
                    "Please configure OPENAI_API_KEY in your .env file."
                ),
                financial_highlights=None,
                risk_factors=None,
                management_discussion=None,
                key_changes=None,
                raw_summary={"error": "OpenAI API key not configured"}
            )
            db.add(summary)
            db.commit()
            return
        
        import time
        start_time = time.time()

        # Increased timeouts to accommodate API retries (3 attempts with exponential backoff)
        global_timeout = 120.0 if filing_type == "10-K" else (100.0 if filing_type == "10-Q" else 60.0)

        async def generate_summary_core() -> None:
                # Step 1: File Validation
                _record_progress(db, filing_id, "fetching")
                print(f"[{filing_id}] Step 1: File Validation - Confirming document is accessible and parsable...")

                processing_profile = {
                    "include_previous": False,
                    "document_timeout": 15.0,
                    "xbrl_timeout": 6.0,
                    "fetch_xbrl": filing_type in {"10-K", "10-Q"},
                }

                if filing_type == "10-K":
                    processing_profile.update(
                        {
                            "include_previous": True,
                            "document_timeout": 15.0,
                            "xbrl_timeout": 6.0,
                        }
                    )
                elif filing_type == "10-Q":
                    processing_profile.update(
                        {
                            "include_previous": False,
                            "document_timeout": 10.0,
                            "xbrl_timeout": 3.0,
                        }
                    )
                elif filing_type == "8-K":
                    processing_profile.update(
                        {
                            "include_previous": False,
                            "fetch_xbrl": False,
                            "document_timeout": 6.0,
                        }
                    )

                previous_filings = []
                if processing_profile["include_previous"]:
                    previous_filings = (
                        db.query(Filing)
                        .filter(
                            Filing.company_id == filing.company_id,
                            Filing.filing_type == "10-K",
                            Filing.id != filing_id,
                            Filing.filing_date < filing.filing_date,
                        )
                        .order_by(Filing.filing_date.desc())
                        .limit(1)
                        .all()
                    )
                    print(f"Found {len(previous_filings)} previous 10-K filings for trend analysis")

                async def fetch_filing_text(url: str) -> Optional[str]:
                    try:
                        return await sec_edgar_service.get_filing_document(
                            url, timeout=processing_profile["document_timeout"]
                        )
                    except Exception as exc:
                        print(f"Error fetching filing from {url}: {str(exc)}")
                        return None

                tasks = [asyncio.create_task(fetch_filing_text(filing_document_url))]
                prev_filing_refs: List[Filing] = []
                for prev_filing in previous_filings:
                    tasks.append(asyncio.create_task(fetch_filing_text(prev_filing.document_url)))
                    prev_filing_refs.append(prev_filing)

                xbrl_task = None
                xbrl_start = None
                if processing_profile["fetch_xbrl"]:
                    print(f"[{filing_id}] Fetching XBRL data in parallel...")

                    async def fetch_xbrl_data() -> Optional[Dict[str, Any]]:
                        try:
                            return await asyncio.wait_for(
                                xbrl_service.get_xbrl_data(
                                    filing_accession_number, company_cik
                                ),
                                timeout=processing_profile["xbrl_timeout"],
                            )
                        except asyncio.TimeoutError:
                            print(
                                f"[{filing_id}] ⚠ XBRL data fetch timed out after {processing_profile['xbrl_timeout']:.0f}s, continuing without it"
                            )
                            return None
                        except Exception as exc:
                            print(f"[{filing_id}] ⚠ Could not extract XBRL data: {str(exc)}")
                            return None

                    xbrl_start = time.time()
                    xbrl_task = asyncio.create_task(fetch_xbrl_data())

                results = await asyncio.gather(*tasks, return_exceptions=True)
                filing_text = results[0] if results and not isinstance(results[0], Exception) else None
                if not filing_text:
                    raise RuntimeError("Unable to retrieve this filing at the moment — please try again shortly.")

                fetch_time = time.time() - start_time
                print(
                    f"[{filing_id}] ✓ File validated and fetched: {len(filing_text):,} characters in {fetch_time:.1f}s"
                )

                # Step 2: Section Parsing
                _record_progress(db, filing_id, "parsing")
                print(f"[{filing_id}] Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...")
                
                excerpt = _get_or_cache_excerpt(db, filing, filing_text)
                print(f"[{filing_id}] ✓ Parsing complete...")

                xbrl_data = None
                if xbrl_task:
                    xbrl_data = await xbrl_task
                    if xbrl_data:
                        # Re-query filing to ensure it's attached to the session before updating
                        filing_for_xbrl = db.query(Filing).filter(Filing.id == filing_id).first()
                        if filing_for_xbrl:
                            filing_for_xbrl.xbrl_data = xbrl_data
                            db.commit()
                        if xbrl_start:
                            xbrl_time = time.time() - xbrl_start
                            print(f"[{filing_id}] ✓ Extracted XBRL data in {xbrl_time:.1f}s")

                previous_filings_text: List[Dict[str, Any]] = []
                for index, result in enumerate(results[1:], 0):
                    if (
                        result
                        and not isinstance(result, Exception)
                        and index < len(prev_filing_refs)
                    ):
                        prev_filing = prev_filing_refs[index]
                        previous_filings_text.append(
                            {
                                "filing_date": prev_filing.filing_date.isoformat()
                                if prev_filing.filing_date
                                else None,
                                "text": result,
                            }
                        )
                        print(
                            f"Fetched previous 10-K from {prev_filing.filing_date}: {len(result):,} characters"
                        )

                xbrl_metrics = None
                if xbrl_data:
                    xbrl_metrics = xbrl_service.extract_standardized_metrics(xbrl_data)

                # Step 3: Content Analysis
                _record_progress(db, filing_id, "analyzing")
                print(f"[{filing_id}] Step 3: Content Analysis - Analyzing risk factors...")

                # Step 4: Summary Generation
                print(f"[{filing_id}] Step 4: Generating financial overview...")
                ai_start = time.time()
                print(f"[{filing_id}] Step 5: Generating investor-focused summary...")
                summary_data = await openai_service.summarize_filing(
                    filing_text,
                    company_name,
                    filing_type,
                    previous_filings=
                    previous_filings_text if previous_filings_text else None,
                    xbrl_metrics=xbrl_metrics,
                    filing_excerpt=excerpt,
                )
                ai_time = time.time() - ai_start
                print(f"[{filing_id}] ✓ AI summary generated in {ai_time:.1f}s")
                
                # Check summary status - handle error, partial, and complete
                summary_status = summary_data.get("status", "complete")
                
                # If status is error, raise exception to trigger error handling
                if summary_status == "error":
                    error_message = summary_data.get("message", "Error generating summary")
                    raise RuntimeError(error_message)
                
                # Log partial status if applicable
                if summary_status == "partial":
                    partial_message = summary_data.get("message", "Some sections may not have loaded fully.")
                    print(f"[{filing_id}] ⚠ Partial summary generated: {partial_message}")

                section_coverage = (
                    (summary_data.get("raw_summary") or {}).get("section_coverage")
                    if isinstance(summary_data, dict)
                    else None
                )
                _record_progress(
                    db,
                    filing_id,
                    "summarizing",
                    section_coverage=section_coverage,
                )
                if section_coverage:
                    print(
                        f"[{filing_id}] coverage snapshot: "
                        f"{section_coverage.get('covered_count', 0)}/"
                        f"{section_coverage.get('total_count', 0)} sections populated"
                    )

                sections_info = (
                    (summary_data.get("raw_summary") or {}).get("sections", {})
                ) or {}

                financial_section = sections_info.get("financial_highlights")
                normalized_financial_section = attach_normalized_facts(
                    financial_section, xbrl_metrics
                )
                if (
                    isinstance(summary_data, dict)
                    and isinstance(sections_info, dict)
                    and normalized_financial_section is not None
                ):
                    sections_info["financial_highlights"] = normalized_financial_section
                    summary_data["sections"] = sections_info

                summary = Summary(
                    filing_id=filing_id,
                    business_overview=summary_data.get("business_overview"),
                    financial_highlights=normalized_financial_section,
                    risk_factors=summary_data.get("risk_factors"),
                    management_discussion=summary_data.get("management_discussion"),
                    key_changes=summary_data.get("key_changes"),
                    raw_summary=summary_data.get("raw_summary"),
                )
                db.add(summary)

                cache = filing.content_cache
                if sections_info:
                    if cache is None:
                        cache = FilingContentCache(
                            filing_id=filing_id,
                            critical_excerpt=excerpt,
                            sections_payload=sections_info,
                        )
                        db.add(cache)
                    else:
                        if excerpt and not cache.critical_excerpt:
                            cache.critical_excerpt = excerpt
                        cache.sections_payload = sections_info
                elif excerpt and cache is None:
                    cache = FilingContentCache(
                        filing_id=filing_id, critical_excerpt=excerpt
                    )
                    db.add(cache)

                db.commit()

                total_time = time.time() - start_time
                print(
                    f"[{filing_id}] ✓ Summary generation completed in {total_time:.1f}s total"
                )

                _record_progress(db, filing_id, "completed")

                if user_id:
                    from app.models import User

                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        month = get_current_month()
                        increment_user_usage(user.id, month, db)

        try:
            await asyncio.wait_for(generate_summary_core(), timeout=global_timeout)
        except asyncio.TimeoutError:
            print(
                f"[{filing_id}] ✗ Summary generation exceeded global timeout of {global_timeout}s"
            )
            _record_progress(db, filing_id, "error", error="timeout")
            error_message = "Unable to complete summary due to parsing timeout. Suggest retrying later."
            error_summary = Summary(
                filing_id=filing_id,
                business_overview=error_message,
                financial_highlights=None,
                risk_factors=None,
                management_discussion=None,
                key_changes=None,
                raw_summary={
                    "status": "error",
                    "message": error_message,
                    "summary_title": f"{company_name} {filing_type} Filing Summary",
                    "sections": [],
                    "insights": {
                        "sentiment": "Neutral",
                        "growth_drivers": [],
                        "risk_signals": []
                    },
                    "error": "Global timeout",
                    "timeout_seconds": global_timeout,
                },
            )
            db.add(error_summary)
            db.commit()
        except Exception as inner_error:
            import traceback

            error_trace = traceback.format_exc()
            error_msg = str(inner_error)
            print(f"Error in timeout wrapper: {error_msg}")
            print(f"Traceback: {error_trace}")
            _record_progress(
                db,
                filing_id,
                "error",
                error=error_msg[:200],
            )
            # Check if error message is already user-friendly
            if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
                error_message = error_msg[:200]
            else:
                error_message = "Unable to retrieve this filing at the moment — please try again shortly."
            error_summary = Summary(
                filing_id=filing_id,
                business_overview=error_message,
                financial_highlights=None,
                risk_factors=None,
                management_discussion=None,
                key_changes=None,
                raw_summary={
                    "status": "error",
                    "message": error_message,
                    "summary_title": f"{company_name} {filing_type} Filing Summary",
                    "sections": [],
                    "insights": {
                        "sentiment": "Neutral",
                        "growth_drivers": [],
                        "risk_signals": []
                    },
                    "error": error_msg,
                    "traceback": error_trace,
                },
            )
            db.add(error_summary)
            db.commit()

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
        return _progress_as_dict(progress)

    return {"stage": "pending", "elapsedSeconds": 0}

@router.post("/filing/{filing_id}/generate", response_model=SummaryResponse)
async def generate_summary(
    filing_id: int,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Generate AI summary for a filing"""
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    # Check if summary already exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    
    if summary:
        return summary
    
    # Begin transaction
    db.begin()
    try:
        # Lock the row for the given filing_id to prevent race conditions
        progress = db.query(SummaryGenerationProgress).filter(
            SummaryGenerationProgress.filing_id == filing_id
        ).with_for_update().first()

        # If progress exists and is not in an error state, another task is already running or completed
        if progress and progress.stage not in ['error']:
            # Return a response indicating that generation is already in progress
            return {
                "id": 0,
                "filing_id": filing_id,
                "business_overview": "Summary generation is already in progress.",
                "financial_highlights": None,
                "risk_factors": None,
                "management_discussion": None,
                "key_changes": None,
                "raw_summary": None
            }

        # Check usage limits only if user is authenticated
        user_id = None
        if current_user:
            can_generate, current_count, limit = check_usage_limit(current_user, db)
            if not can_generate:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"You've reached your monthly limit of {limit} summaries. Upgrade to Pro for unlimited summaries."
                )
            user_id = current_user.id
        
        # If no progress or errored progress, (re)start the generation
        _record_progress(db, filing_id, "queued")
        db.commit()

        asyncio.create_task(_generate_summary_background(filing_id, user_id))
    
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
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Generate AI summary with streaming response"""
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

    # Check usage limits only if user is authenticated
    user_id = None
    if current_user:
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
        user_id = current_user.id
    
    async def stream_summary():
        # Create a new session for the async generator to avoid detached session issues
        from app.database import SessionLocal
        with SessionLocal() as session:
            pipeline_started_at = time.time()
            stage_started_at = pipeline_started_at
            stage_timings: List[tuple[str, float]] = []

            def mark_stage(stage_name: str):
                nonlocal stage_started_at
                now = time.time()
                duration = now - stage_started_at
                stage_timings.append((stage_name, duration))
                stage_started_at = now

            executor = None
            try:
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'initializing', 'message': 'Initializing...'})}\n\n"

                # Note: We use cached values (company_name, filing_type, etc.) from the outer scope
                # to avoid detached session issues. Only re-query when we need to access relationships
                # or update the filing object.
                filing_in_session = session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                if not filing_in_session:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Filing not found'})}\n\n"
                    return

                # Step 1: File Validation
                _record_progress(session, filing_id, "fetching")
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'Step 1: File Validation - Confirming document is accessible and parsable...'})}\n\n"

                # Fetch filing document using cached URL
                try:
                    filing_text = await sec_edgar_service.get_filing_document(
                        filing_document_url,
                        timeout=25.0
                    )
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
                _record_progress(session, filing_id, "parsing")
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...'})}\n\n"
                
                # Parallelize excerpt extraction and XBRL fetching
                import concurrent.futures
                
                # Extract excerpt in thread pool (CPU-bound regex operations)
                loop = asyncio.get_event_loop()
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
                
                def extract_excerpt_sync():
                    # Create a new session for the thread
                    from app.database import SessionLocal
                    with SessionLocal() as thread_session:
                        thread_filing = thread_session.query(Filing).options(joinedload(Filing.content_cache)).filter(Filing.id == filing_id).first()
                        return _get_or_cache_excerpt(thread_session, thread_filing, filing_text)
                
                excerpt_task = loop.run_in_executor(executor, extract_excerpt_sync)
                
                # Ensure executor is cleaned up
                def cleanup_executor():
                    executor.shutdown(wait=False)
                
                # Start XBRL fetching in parallel
                xbrl_task = None
                if filing_type and filing_type.upper() in {"10-K", "10-Q"} and company_cik:
                    async def fetch_xbrl():
                        try:
                            data = await xbrl_service.get_xbrl_data(filing_accession_number, company_cik)
                            if data:
                                metrics = xbrl_service.extract_standardized_metrics(data)
                                # Update filing in main session - re-query to ensure it's attached
                                filing_for_update = session.query(Filing).filter(Filing.id == filing_id).first()
                                if filing_for_update:
                                    filing_for_update.xbrl_data = data
                                    session.commit()
                                return metrics
                        except Exception as xbrl_error:
                            print(f"[stream:{filing_id}] Error updating XBRL data: {str(xbrl_error)}")
                            pass
                        return None
                    xbrl_task = asyncio.create_task(fetch_xbrl())
                
                # Wait for parsing to complete
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Parsing complete...'})}\n\n"

                # Step 3: Content Analysis
                _record_progress(session, filing_id, "analyzing")
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Step 3: Content Analysis - Analyzing risk factors...'})}\n\n"

                # Step 4: Summary Generation
                yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Step 4: Generating financial overview...'})}\n\n"

                _record_progress(session, filing_id, "summarizing")
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
                summary_payload = await openai_service.summarize_filing(
                    filing_text,
                    company_name,
                    filing_type,
                    previous_filings=None,
                    xbrl_metrics=xbrl_metrics,
                    filing_excerpt=excerpt,
                )
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
                    _record_progress(
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
                mark_stage("persist_summary")

                if user_id:
                    from app.models import User
                    user = session.query(User).filter(User.id == user_id).first()
                    if user:
                        month = get_current_month()
                        increment_user_usage(user.id, month, session)
                mark_stage("usage_tracking")

                _record_progress(session, filing_id, "completed")

                # Check summary status and emit appropriate response
                summary_status = summary_payload.get("status", "complete")
                summary_message = summary_payload.get("message")
                
                # Emit final markdown once
                yield f"data: {json.dumps({'type': 'chunk', 'content': markdown})}\n\n"
                
                # Emit status and completion
                if summary_status == "partial":
                    yield f"data: {json.dumps({'type': 'partial', 'message': summary_message or 'Some sections may not have loaded fully.', 'summary_id': summary.id})}\n\n"
                elif summary_status == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': summary_message or 'Error generating summary', 'summary_id': summary.id})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'complete', 'summary_id': summary.id})}\n\n"
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
                    _record_progress(session, filing_id, "error", error=error_msg[:200])
                except:
                    pass
                
                # Return user-friendly error message
                if "Unable to retrieve" in error_msg or "Unable to complete" in error_msg:
                    error_message = error_msg[:200]
                else:
                    error_message = "Unable to retrieve this filing at the moment — please try again shortly."
                
                yield f"data: {json.dumps({'type': 'error', 'message': error_message})}\n\n"
            finally:
                # Clean up executor
                try:
                    executor.shutdown(wait=False)
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


def get_generation_progress_snapshot(filing_id: int) -> Optional[Dict[str, Any]]:
    """Return the persisted generation progress for a filing, if available."""
    with SessionLocal() as session:
        progress = (
            session.query(SummaryGenerationProgress)
            .filter(SummaryGenerationProgress.filing_id == filing_id)
            .first()
        )
        if not progress:
            return None
        return _progress_as_dict(progress)

