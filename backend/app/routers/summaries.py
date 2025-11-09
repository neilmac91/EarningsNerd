from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
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
from app.routers.auth import get_current_user_optional
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
        progress.elapsed_seconds = float((now - progress.started_at).total_seconds())
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
        elapsed = float((_utcnow() - progress.started_at).total_seconds())
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

    cache = filing.content_cache
    if cache and cache.critical_excerpt:
        return cache.critical_excerpt

    filing_type_key = (filing.filing_type or "10-K").upper()
    excerpt = openai_service.extract_critical_sections(filing_text, filing_type_key)
    if excerpt:
        if cache is None:
            cache = FilingContentCache(filing_id=filing.id, critical_excerpt=excerpt)
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
        filing = db.query(Filing).filter(Filing.id == filing_id).first()
        if not filing:
            print(f"Filing {filing_id} not found")
            return
        
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
        
        try:
            import time
            start_time = time.time()

            filing_type = (filing.filing_type or "").upper()
            global_timeout = 60.0 if filing_type == "10-K" else (45.0 if filing_type == "10-Q" else 20.0)

            async def generate_summary_core() -> None:
                _record_progress(db, filing_id, "fetching")
                print(f"[{filing_id}] Step 1: Fetching filing document...")

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

                tasks = [asyncio.create_task(fetch_filing_text(filing.document_url))]
                prev_filing_refs: List[Filing] = []
                for prev_filing in previous_filings:
                    tasks.append(asyncio.create_task(fetch_filing_text(prev_filing.document_url)))
                    prev_filing_refs.append(prev_filing)

                xbrl_task = None
                xbrl_start = None
                if processing_profile["fetch_xbrl"]:
                    print(f"[{filing_id}] Step 2: Fetching XBRL data...")

                    async def fetch_xbrl_data() -> Optional[Dict[str, Any]]:
                        try:
                            return await asyncio.wait_for(
                                xbrl_service.get_xbrl_data(
                                    filing.accession_number, filing.company.cik
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
                    raise RuntimeError("Failed to fetch current filing document")

                fetch_time = time.time() - start_time
                print(
                    f"[{filing_id}] ✓ Fetched filing document: {len(filing_text):,} characters in {fetch_time:.1f}s"
                )

                excerpt = _get_or_cache_excerpt(db, filing, filing_text)
                _record_progress(db, filing_id, "parsing")

                xbrl_data = None
                if xbrl_task:
                    xbrl_data = await xbrl_task
                    if xbrl_data:
                        filing.xbrl_data = xbrl_data
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

                _record_progress(db, filing_id, "analyzing")

                print(f"[{filing_id}] Step 3: Generating AI summary...")
                ai_start = time.time()
                summary_data = await openai_service.summarize_filing(
                    filing_text,
                    filing.company.name,
                    filing.filing_type,
                    previous_filings=
                    previous_filings_text if previous_filings_text else None,
                    xbrl_metrics=xbrl_metrics,
                    filing_excerpt=excerpt,
                )
                ai_time = time.time() - ai_start
                print(f"[{filing_id}] ✓ AI summary generated in {ai_time:.1f}s")

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
                error_summary = Summary(
                    filing_id=filing_id,
                    business_overview=(
                        f"Summary generation timed out after {global_timeout:.0f} seconds. The process took too long to complete. Please try again or refer to the original filing document."
                    ),
                    financial_highlights=None,
                    risk_factors=None,
                    management_discussion=None,
                    key_changes=None,
                    raw_summary={
                        "error": "Global timeout",
                        "timeout_seconds": global_timeout,
                    },
                )
                db.add(error_summary)
                db.commit()
            except Exception as inner_error:
                import traceback

                error_trace = traceback.format_exc()
                print(f"Error in timeout wrapper: {str(inner_error)}")
                print(f"Traceback: {error_trace}")
                _record_progress(
                    db,
                    filing_id,
                    "error",
                    error=str(inner_error)[:200],
                )
                error_summary = Summary(
                    filing_id=filing_id,
                    business_overview=(
                        f"Error generating summary: {str(inner_error)[:200]}. Please try again or contact support if the issue persists."
                    ),
                    financial_highlights=None,
                    risk_factors=None,
                    management_discussion=None,
                    key_changes=None,
                    raw_summary={"error": str(inner_error), "traceback": error_trace},
                )
                db.add(error_summary)
                db.commit()
        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            print(f"Error generating summary: {str(e)}")
            print(f"Traceback: {error_trace}")
            _record_progress(db, filing_id, "error", error=str(e)[:200])
            error_summary = Summary(
                filing_id=filing_id,
                business_overview=(
                    f"Error generating summary: {str(e)[:200]}. Please try again or contact support if the issue persists."
                ),
                financial_highlights=None,
                risk_factors=None,
                management_discussion=None,
                key_changes=None,
                raw_summary={"error": str(e), "traceback": error_trace},
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
    current_user: Optional[User] = Depends(get_current_user_optional),  # Optional for backward compatibility
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
    
    # Check usage limits if user is authenticated
    user_id = None
    if current_user:
        can_generate, current_count, limit = check_usage_limit(current_user, db)
        if not can_generate:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"You've reached your monthly limit of {limit} summaries. Upgrade to Pro for unlimited summaries."
            )
        user_id = current_user.id
    
    _record_progress(db, filing_id, "queued")
    asyncio.create_task(_generate_summary_background(filing_id, user_id))
    
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
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    
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
    company = filing.company
    company_name = company.name if company else "Unknown company"
    company_cik = company.cik if company else None

    # Check usage limits if user is authenticated
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
        pipeline_started_at = time.time()
        stage_started_at = pipeline_started_at
        stage_timings: List[tuple[str, float]] = []

        def mark_stage(stage_name: str):
            nonlocal stage_started_at
            now = time.time()
            duration = now - stage_started_at
            stage_timings.append((stage_name, duration))
            print(f"[stream:{filing_id}] stage '{stage_name}' completed in {duration:.2f}s")
            stage_started_at = now

        try:
            _record_progress(db, filing_id, "fetching")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'fetching', 'message': 'Fetching filing document...'})}\n\n"

            # Fetch filing document
            filing_text = await sec_edgar_service.get_filing_document(
                filing.document_url,
                timeout=25.0
            )
            mark_stage("fetch_document")

            excerpt = _get_or_cache_excerpt(db, filing, filing_text)
            _record_progress(db, filing_id, "parsing")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': 'Parsing document structure...'})}\n\n"

            # Fetch XBRL data if available
            xbrl_data = None
            xbrl_metrics = None
            if filing.filing_type and filing.filing_type.upper() in {"10-K", "10-Q"} and company_cik:
                try:
                    xbrl_data = await xbrl_service.get_xbrl_data(filing.accession_number, company_cik)
                    if xbrl_data:
                        xbrl_metrics = xbrl_service.extract_standardized_metrics(xbrl_data)
                        filing.xbrl_data = xbrl_data
                        db.commit()
                except:
                    pass
            mark_stage("context_enrichment")

            _record_progress(db, filing_id, "analyzing")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'analyzing', 'message': 'Analyzing content with AI...'})}\n\n"

            yield f"data: {json.dumps({'type': 'progress', 'stage': 'structured', 'message': 'Extracting key figures...'})}\n\n"

            _record_progress(db, filing_id, "summarizing")
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'summarizing', 'message': 'Composing investor-ready summary...'})}\n\n"

            summary_payload = await openai_service.summarize_filing(
                filing_text,
                company_name,
                filing.filing_type,
                previous_filings=None,
                xbrl_metrics=xbrl_metrics,
                filing_excerpt=excerpt,
            )
            mark_stage("generate_summary")

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
                    db,
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
                cache = FilingContentCache(filing_id=filing_id, critical_excerpt=excerpt)
                db.add(cache)

            db.commit()
            mark_stage("persist_summary")

            if user_id:
                from app.models import User
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    month = get_current_month()
                    increment_user_usage(user.id, month, db)
            mark_stage("usage_tracking")

            _record_progress(db, filing_id, "completed")

            # Emit final markdown once
            yield f"data: {json.dumps({'type': 'chunk', 'content': markdown})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'summary_id': summary.id})}\n\n"
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"Error in streaming summary: {str(e)}")
            print(f"Traceback: {error_trace}")
            _record_progress(db, filing_id, "error", error=str(e)[:200])
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error generating summary: {str(e)[:200]}'})}\n\n"
        finally:
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

