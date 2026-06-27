import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple, Literal
from sqlalchemy.orm import Session, joinedload
from app.models import Filing, Summary, SummaryGenerationProgress, User, FilingContentCache
# EdgarTools migration: Using new edgar module for SEC services
from app.services.edgar.compat import sec_edgar_service, xbrl_service
from app.services.openai_service import openai_service
from app.schemas import attach_normalized_facts
from app.services.subscription_service import increment_user_usage, get_current_month
from app.config import settings
from app.database import SessionLocal
import logging

logger = logging.getLogger(__name__)

# Minimum number of sections required for a "full" result
# Per execution plan: 3/7 sections minimum for full result designation
MINIMUM_SECTIONS_FOR_FULL_RESULT = 3

# All hideable sections (Executive Summary is never hidden)
HIDEABLE_SECTIONS = [
    "business_overview",
    "financial_highlights",
    "risk_factors",
    "management_discussion",
    "key_changes",
    "forward_guidance",
    "additional_disclosures",
]


def calculate_section_coverage(summary_data: Dict[str, Any]) -> Tuple[int, int, List[str], List[str]]:
    """Calculate section coverage for a summary.

    CRITICAL FIX: Properly detect placeholder/failure content that shouldn't count as "covered".
    The AI may return text like "Not Disclosed" which passes basic non-empty checks
    but represents a failure state, not actual content.

    Returns:
        Tuple of (covered_count, total_count, covered_sections, missing_sections)
    """
    # Placeholder patterns that indicate failure, NOT success
    PLACEHOLDER_PATTERNS = [
        "not disclosed", "not available", "unavailable", "n/a",
        "not found", "not provided", "no data", "could not",
        "unable to", "failed to", "missing", "pending",
        "being processed", "retry", "error",
        "not captured", "not extracted", "were not extracted",
    ]

    def _has_substantive_content(data: Any) -> bool:
        """Check if data contains actual substantive content, not placeholders."""
        if data is None:
            return False

        if isinstance(data, str):
            text = data.strip().lower()
            if not text or len(text) < 20:
                return False
            # Check for placeholder patterns
            for pattern in PLACEHOLDER_PATTERNS:
                if pattern in text and len(text) < 200:
                    # Short text containing placeholder = not substantive
                    return False
            return True

        if isinstance(data, list):
            # For lists (like risk_factors), check if any item has real content
            if not data:
                return False
            for item in data:
                if isinstance(item, dict):
                    # Check if dict has substantive string values
                    for val in item.values():
                        if isinstance(val, str) and len(val.strip()) > 20:
                            text_lower = val.strip().lower()
                            has_placeholder = any(p in text_lower for p in PLACEHOLDER_PATTERNS)
                            if not has_placeholder:
                                return True
                elif isinstance(item, str) and len(item.strip()) > 20:
                    return True
            return False

        if isinstance(data, dict):
            # For dicts (like financial_highlights), check for substantive nested data
            if not data:
                return False
            # Check common nested fields
            for key in ["table", "notes", "summary", "content"]:
                if key in data:
                    if _has_substantive_content(data[key]):
                        return True
            # Check all values
            for val in data.values():
                if isinstance(val, str) and len(val.strip()) > 50:
                    text_lower = val.strip().lower()
                    has_placeholder = any(p in text_lower for p in PLACEHOLDER_PATTERNS)
                    if not has_placeholder:
                        return True
                elif isinstance(val, (list, dict)) and val:
                    if _has_substantive_content(val):
                        return True
            return False

        return False

    total_sections = len(HIDEABLE_SECTIONS)
    covered_sections = []
    missing_sections = []

    for section in HIDEABLE_SECTIONS:
        section_data = summary_data.get(section)
        is_covered = _has_substantive_content(section_data)

        if is_covered:
            covered_sections.append(section)
        else:
            missing_sections.append(section)
            logger.debug(f"Section '{section}' not covered: {type(section_data).__name__}, "
                        f"sample: {str(section_data)[:100] if section_data else 'None'}")

    return len(covered_sections), total_sections, covered_sections, missing_sections


def _xbrl_value_appears(value: float, haystack_lower: str) -> bool:
    """Does an XBRL value appear in the summary text, in any common rendering (billions/
    millions/grouped)? Mirrors the eval harness's grounding check without importing it."""
    av = abs(value)
    candidates: set[str] = set()
    if av >= 1e9:
        for d in range(0, 4):  # 0-3 decimals: covers "383", "383.3", "383.29", "383.285"
            candidates.add(f"{av / 1e9:.{d}f}")
    if av >= 1e6:
        for d in range(0, 4):  # 0-3 decimals, grouped and ungrouped (e.g. "120.5", "1,250")
            candidates.add(f"{av / 1e6:.{d}f}")
            candidates.add(f"{av / 1e6:,.{d}f}")
    candidates.add(f"{int(round(av)):,}")
    return any(c.lower() in haystack_lower for c in candidates if len(c.replace(",", "")) >= 2)


def assess_quality(
    summary_data: Dict[str, Any], xbrl_metrics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Deterministic quality verdict for a generated summary (roadmap S4).

    Returns {tier: "full"|"partial", reasons, numeric_grounded, covered_count, total_count}.
    "partial" means thin section coverage OR financials that don't match the SEC-verified XBRL —
    the signal the UI surfaces honestly (quality badge) instead of silently stripping notices."""
    covered, total, _, _ = calculate_section_coverage(summary_data)
    reasons: List[str] = []

    numeric_grounded = True
    if xbrl_metrics:
        import json as _json

        haystack = (
            str(summary_data.get("business_overview") or "")
            + " "
            + _json.dumps(summary_data.get("financial_highlights") or {}, default=str)
        ).lower()
        checks: List[bool] = []
        for key in ("revenue", "net_income"):
            node = xbrl_metrics.get(key)
            current = node.get("current", {}) if isinstance(node, dict) else {}
            value = current.get("value") if isinstance(current, dict) else None
            if value is not None:
                checks.append(_xbrl_value_appears(float(value), haystack))
        if checks:
            numeric_grounded = all(checks)
            if not numeric_grounded:
                reasons.append("financial figures not grounded in SEC XBRL data")

    if covered < MINIMUM_SECTIONS_FOR_FULL_RESULT:
        reasons.append(f"only {covered}/{total} sections populated")

    tier = "full" if (covered >= MINIMUM_SECTIONS_FOR_FULL_RESULT and numeric_grounded) else "partial"
    return {
        "tier": tier,
        "reasons": reasons,
        "numeric_grounded": numeric_grounded,
        "covered_count": covered,
        "total_count": total,
    }


def determine_result_type(
    summary_data: Dict[str, Any],
    had_errors: bool = False,
    had_timeout: bool = False,
) -> Tuple[Literal["full", "partial"], Optional[str]]:
    """Determine if a summary result is 'full' or 'partial'.

    Per execution plan requirements:
    - Full Result: ≥3/7 sections populated, no errors, AI completed
    - Partial Result: <3/7 sections OR timeout OR error during generation

    Goal: 0% partial results - partial should be SUPER RARE.

    Returns:
        Tuple of (result_type, partial_reason)
        partial_reason is None for full results
    """
    covered_count, total_count, _, _ = calculate_section_coverage(summary_data)

    # Check for errors first
    if had_errors:
        return "partial", "api_error"

    if had_timeout:
        return "partial", "timeout"

    # Check coverage threshold
    if covered_count < MINIMUM_SECTIONS_FOR_FULL_RESULT:
        return "partial", f"insufficient_coverage ({covered_count}/{total_count} sections)"

    return "full", None


def generate_unavailable_sections_notes(missing_sections: List[str]) -> List[Dict[str, str]]:
    """Generate user-friendly notes for unavailable sections.

    Per execution plan: Executive Summary must explicitly note unavailable sections.
    """
    notes_mapping = {
        "business_overview": "Business overview information was not available in this filing",
        "financial_highlights": "Financial highlights could not be extracted from this filing",
        "risk_factors": "Risk factors were not itemized in this filing",
        "management_discussion": "Management Discussion & Analysis (MD&A) was not available",
        "key_changes": "Year-over-year comparisons were not available for this filing period",
        "forward_guidance": "No forward guidance was disclosed in this filing",
        "additional_disclosures": "No additional disclosures were identified in this filing",
    }

    return [
        {"section": section, "note": notes_mapping.get(section, f"{section} was not available")}
        for section in missing_sections
    ]

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def record_progress(
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

def progress_as_dict(progress: SummaryGenerationProgress) -> Dict[str, Any]:
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

# An edgartools-parsed excerpt below this many chars is treated as "thin" (e.g. only a stub
# parsed), so we fall back to the legacy regex + dense-window extractor for more depth. Real
# filings parse to tens of thousands of chars, so this only catches near-empty edge cases.
_EDGARTOOLS_EXCERPT_MIN = 8000


def get_or_cache_excerpt(
    db: Session,
    filing: Filing,
    filing_text: Optional[str],
    sections: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    # ``sections`` (when provided) is edgartools-parsed section text; it lets us build a
    # high-precision excerpt even when ``filing_text`` is empty (e.g. a cache-hit path). We
    # still need one of the two inputs to produce anything.
    if not filing_text and not sections:
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

    # Prefer edgartools' native section parser (precise, robust to fragmented HTML); fall back
    # to the legacy regex + dense-window extractor when sections are unavailable or too thin.
    excerpt = None
    if sections and settings.USE_EDGARTOOLS_SECTIONS:
        excerpt = openai_service.assemble_excerpt_from_sections(
            sections, filing_type_key, filing_text=filing_text
        )
        if excerpt and len(excerpt) < _EDGARTOOLS_EXCERPT_MIN:
            excerpt = None
    if not excerpt:
        excerpt = openai_service.extract_critical_sections(filing_text or "", filing_type_key)
    if excerpt:
        if cache is None:
            cache = FilingContentCache(filing_id=filing_id, critical_excerpt=excerpt)
            db.add(cache)
        else:
            cache.critical_excerpt = excerpt
        db.flush()
        db.commit()
    return excerpt

async def generate_summary_background(filing_id: int, user_id: Optional[int]):
    """Background task to generate summary"""
    
    # Create a new database session for the background task
    with SessionLocal() as db:
        logger.info(f"Starting summary generation for filing {filing_id}")
        # Eagerly load content_cache and company relationship to avoid detached session issues
        filing = db.query(Filing).options(
            joinedload(Filing.content_cache),
            joinedload(Filing.company)
        ).filter(Filing.id == filing_id).first()
        if not filing:
            logger.warning(f"Filing {filing_id} not found")
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
            logger.info(f"Summary already exists for filing {filing_id}")
            # If summary already exists, still increment usage if user generated it
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    month = get_current_month()
                    increment_user_usage(user.id, month, db)
            return
        
        # Check if OpenAI API key is configured
        if not settings.OPENAI_API_KEY:
            logger.warning(f"Warning: OpenAI API key not configured. Cannot generate summary for filing {filing_id}")
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
        
        start_time = time.time()

        # Increased timeouts to accommodate API retries (3 attempts with exponential backoff).
        # 20-F (foreign annual report) is as large as a 10-K, so it gets the same generous budget.
        global_timeout = (
            120.0 if filing_type in {"10-K", "20-F"}
            else (100.0 if filing_type == "10-Q" else 60.0)
        )

        async def generate_summary_core() -> None:
                # Step 1: File Validation
                record_progress(db, filing_id, "fetching")
                logger.info(f"[{filing_id}] Step 1: File Validation - Confirming document is accessible and parsable...")

                # XBRL budgets account for the accession-aware primary path
                # (issue #240): a cold filing.xbrl() parse downloads and parses
                # the instance documents (typically 2-10s), unlike the old
                # single companyfacts JSON fetch. Cached filings return in ms.
                processing_profile = {
                    "include_previous": False,
                    "document_timeout": 15.0,
                    "xbrl_timeout": 12.0,
                    # 20-F XBRL is currency-aware (reporting currency captured, not USD convenience),
                    # so foreign annual reports fetch it too. split("/") covers amended forms
                    # (10-K/A, 20-F/A). filing_type is already upper-cased above.
                    "fetch_xbrl": filing_type.split("/")[0] in {"10-K", "10-Q", "20-F"},
                }

                if filing_type == "10-K":
                    processing_profile.update(
                        {
                            "include_previous": True,
                            "document_timeout": 15.0,
                            "xbrl_timeout": 12.0,
                        }
                    )
                elif filing_type == "10-Q":
                    processing_profile.update(
                        {
                            "include_previous": False,
                            "document_timeout": 10.0,
                            "xbrl_timeout": 10.0,
                        }
                    )

                # B3: the section parse gets its OWN (larger) budget rather than sharing
                # document_timeout — it runs concurrent with the fetch, so the headroom is mostly
                # hidden, and big financial filers (BAC/GS ~20-21s, JPM ~26s) were exceeding the 15s
                # document budget and falling back to the lower-precision regex excerpt. This also
                # fixes 20-F (its inner 40s cap was previously defeated by the 15s outer wait_for).
                processing_profile["section_timeout"] = (
                    40.0 if filing_type.split("/")[0] == "20-F" else 30.0
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
                    logger.info(f"Found {len(previous_filings)} previous 10-K filings for trend analysis")

                async def fetch_filing_text(url: str) -> Optional[str]:
                    try:
                        return await sec_edgar_service.get_filing_document(
                            url, timeout=processing_profile["document_timeout"]
                        )
                    except Exception as exc:
                        logger.error(f"Error fetching filing from {url}: {str(exc)}")
                        return None

                tasks = [asyncio.create_task(fetch_filing_text(filing_document_url))]
                prev_filing_refs: List[Filing] = []
                for prev_filing in previous_filings:
                    tasks.append(asyncio.create_task(fetch_filing_text(prev_filing.document_url)))
                    prev_filing_refs.append(prev_filing)

                xbrl_task = None
                xbrl_start = None
                if processing_profile["fetch_xbrl"]:
                    logger.info(f"[{filing_id}] Fetching XBRL data in parallel...")

                    async def fetch_xbrl_data() -> Optional[Dict[str, Any]]:
                        try:
                            return await asyncio.wait_for(
                                xbrl_service.get_xbrl_data(
                                    filing_accession_number, company_cik
                                ),
                                timeout=processing_profile["xbrl_timeout"],
                            )
                        except asyncio.TimeoutError:
                            logger.warning(
                                f"[{filing_id}] ⚠ XBRL data fetch timed out after {processing_profile['xbrl_timeout']:.0f}s, continuing without it"
                            )
                            return None
                        except Exception as exc:
                            logger.warning(f"[{filing_id}] ⚠ Could not extract XBRL data: {str(exc)}")
                            return None

                    xbrl_start = time.time()
                    xbrl_task = asyncio.create_task(fetch_xbrl_data())

                # Fetch edgartools-parsed sections in parallel (needs only accession + CIK, like
                # XBRL). Used as the high-precision excerpt source; the regex extractor is the
                # fallback when this returns nothing.
                sections_task = None
                if (
                    settings.USE_EDGARTOOLS_SECTIONS
                    and company_cik
                    # 20-F gets section extraction too; split("/") covers amended forms (10-K/A,
                    # 20-F/A). See tasks/fpi-support-roadmap.md.
                    and filing_type.split("/")[0] in {"10-K", "10-Q", "20-F"}
                ):
                    async def fetch_sections() -> Optional[Dict[str, str]]:
                        try:
                            return await asyncio.wait_for(
                                xbrl_service.get_filing_sections(
                                    filing_accession_number, company_cik, filing_type
                                ),
                                timeout=processing_profile["section_timeout"],
                            )
                        except asyncio.TimeoutError:
                            logger.warning(f"[{filing_id}] ⚠ Section parse timed out, using regex fallback")
                            return None
                        except Exception as exc:
                            logger.warning(f"[{filing_id}] ⚠ Section parse failed ({exc}), using regex fallback")
                            return None

                    sections_task = asyncio.create_task(fetch_sections())

                results = await asyncio.gather(*tasks, return_exceptions=True)
                filing_text = results[0] if results and not isinstance(results[0], Exception) else None
                if not filing_text:
                    raise RuntimeError("Unable to retrieve this filing at the moment — please try again shortly.")

                fetch_time = time.time() - start_time
                logger.info(
                    f"[{filing_id}] ✓ File validated and fetched: {len(filing_text):,} characters in {fetch_time:.1f}s"
                )

                # Step 2: Section Parsing
                record_progress(db, filing_id, "parsing")
                logger.info(f"[{filing_id}] Step 2: Section Parsing - Extracting major sections (Item 1A: Risk Factors, Item 7: MD&A)...")

                sections = None
                if sections_task is not None:
                    sections = await sections_task

                # Build the excerpt off the event loop. When edgartools sections are unavailable
                # (fallback) or the financials section is thin (backfill), excerpt construction runs
                # BeautifulSoup + regex over a multi-MB document — blocking the loop here would stall
                # the in-flight XBRL fetch. Use a fresh session inside the worker thread (mirrors the
                # SSE path's extract_excerpt_sync).
                def _build_excerpt_sync() -> Optional[str]:
                    with SessionLocal() as excerpt_session:
                        excerpt_filing = (
                            excerpt_session.query(Filing)
                            .options(joinedload(Filing.content_cache))
                            .filter(Filing.id == filing_id)
                            .first()
                        )
                        return get_or_cache_excerpt(
                            excerpt_session, excerpt_filing, filing_text, sections=sections
                        )

                excerpt = await asyncio.to_thread(_build_excerpt_sync)
                logger.info(f"[{filing_id}] ✓ Parsing complete...")

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
                            logger.info(f"[{filing_id}] ✓ Extracted XBRL data in {xbrl_time:.1f}s")

                previous_filings_text: List[Dict[str, Any]] = []
                for index, result in enumerate(results[1:], 0):
                    if (
                        result
                        and not isinstance(result, Exception)
                        and index < len(prev_filing_refs)
                    ):
                        prev_filing = prev_filing_refs[index]

                        # Build the prior 10-K's excerpt with the same edgartools-first path used
                        # for the main filing, so the year-over-year trend context isn't stuck on
                        # the legacy regex/dense-window extractor. Falls back to regex in
                        # summarize_filing when this is None.
                        prev_excerpt = None
                        prev_accession = prev_filing.accession_number
                        if settings.USE_EDGARTOOLS_SECTIONS and company_cik and prev_accession:
                            try:
                                prev_sections = await xbrl_service.get_filing_sections(
                                    prev_accession, company_cik, "10-K"
                                )
                                if prev_sections:
                                    # Off the event loop: the thin-financials backfill parses the
                                    # multi-MB prior filing with BeautifulSoup. (Pure CPU, no DB.)
                                    prev_excerpt = await asyncio.to_thread(
                                        openai_service.assemble_excerpt_from_sections,
                                        prev_sections,
                                        "10-K",
                                        filing_text=result,
                                    ) or None
                            except Exception as exc:  # noqa: BLE001 — never block on prior-filing parse
                                logger.warning(
                                    f"[{filing_id}] ⚠ Prior 10-K section parse failed ({exc}), using regex fallback"
                                )

                        previous_filings_text.append(
                            {
                                "filing_date": prev_filing.filing_date.isoformat()
                                if prev_filing.filing_date
                                else None,
                                "text": result,
                                "excerpt": prev_excerpt,
                            }
                        )
                        logger.info(
                            f"Fetched previous 10-K from {prev_filing.filing_date}: {len(result):,} characters"
                        )

                xbrl_metrics = None
                if xbrl_data:
                    xbrl_metrics = xbrl_service.extract_standardized_metrics(xbrl_data)

                # Step 3: Content Analysis
                record_progress(db, filing_id, "analyzing")
                logger.info(f"[{filing_id}] Step 3: Content Analysis - Analyzing risk factors...")

                # Step 4: Summary Generation
                logger.info(f"[{filing_id}] Step 4: Generating financial overview...")
                ai_start = time.time()
                logger.info(f"[{filing_id}] Step 5: Generating investor-focused summary...")
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
                logger.info(f"[{filing_id}] ✓ AI summary generated in {ai_time:.1f}s")
                
                # Check summary status - handle error, partial, and complete
                summary_status = summary_data.get("status", "complete")
                
                # If status is error, raise exception to trigger error handling
                if summary_status == "error":
                    error_message = summary_data.get("message", "Error generating summary")
                    raise RuntimeError(error_message)
                
                # Log partial status if applicable
                if summary_status == "partial":
                    partial_message = summary_data.get("message", "Some sections may not have loaded fully.")
                    logger.warning(f"[{filing_id}] ⚠ Partial summary generated: {partial_message}")

                section_coverage = (
                    (summary_data.get("raw_summary") or {}).get("section_coverage")
                    if isinstance(summary_data, dict)
                    else None
                )
                record_progress(
                    db,
                    filing_id,
                    "summarizing",
                    section_coverage=section_coverage,
                )
                if section_coverage:
                    logger.info(
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

                # Determine if this is a full or partial result
                # Per execution plan: Only FULL results are cached. Partial results are NEVER cached.
                result_type, partial_reason = determine_result_type(
                    summary_data,
                    had_errors=(summary_status == "error"),
                    had_timeout=False,
                )

                # Calculate section coverage for logging and metadata
                covered_count, total_count, covered_sections, missing_sections = calculate_section_coverage(summary_data)

                logger.info(
                    f"[{filing_id}] Result type: {result_type}, "
                    f"coverage: {covered_count}/{total_count}, "
                    f"reason: {partial_reason or 'N/A'}"
                )

                # Add unavailable sections notes to executive summary
                sections_unavailable = generate_unavailable_sections_notes(missing_sections)

                # Enrich raw_summary with result metadata
                enriched_raw_summary = summary_data.get("raw_summary") or {}
                enriched_raw_summary["result_type"] = result_type
                enriched_raw_summary["partial_reason"] = partial_reason
                enriched_raw_summary["sections_available"] = covered_sections
                enriched_raw_summary["sections_unavailable"] = sections_unavailable

                if result_type == "partial":
                    # PARTIAL RESULT: Do NOT cache to database
                    # Per execution plan: Partial results must NEVER be stored in the Summary table
                    # They are returned to the requesting user ONLY, then discarded
                    logger.warning(
                        f"[{filing_id}] ⚠ PARTIAL RESULT - NOT CACHING. "
                        f"Coverage: {covered_count}/{total_count}, Reason: {partial_reason}"
                    )

                    # Record partial status in progress for the frontend to detect
                    record_progress(
                        db,
                        filing_id,
                        "partial",
                        error=f"Partial result: {partial_reason}. Coverage: {covered_count}/{total_count}",
                        section_coverage={
                            "result_type": "partial",
                            "partial_reason": partial_reason,
                            "covered_count": covered_count,
                            "total_count": total_count,
                            "covered_sections": covered_sections,
                            "sections_unavailable": sections_unavailable,
                            # Include the actual summary data so frontend can display it
                            # Built dynamically from HIDEABLE_SECTIONS to avoid missing sections
                            "partial_data": {
                                section: (
                                    normalized_financial_section if section == "financial_highlights"
                                    else summary_data.get(section)
                                )
                                for section in HIDEABLE_SECTIONS
                            },
                        },
                    )

                    # Do NOT save to Summary table - partial results are discarded
                    # Do NOT increment user usage for partial results
                    return

                # FULL RESULT: Cache to database as normal
                logger.info(
                    f"[{filing_id}] ✓ FULL RESULT - Caching to database. "
                    f"Coverage: {covered_count}/{total_count}"
                )

                summary = Summary(
                    filing_id=filing_id,
                    business_overview=summary_data.get("business_overview"),
                    financial_highlights=normalized_financial_section,
                    risk_factors=summary_data.get("risk_factors"),
                    management_discussion=summary_data.get("management_discussion"),
                    key_changes=summary_data.get("key_changes"),
                    raw_summary=enriched_raw_summary,
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
                logger.info(
                    f"[{filing_id}] ✓ Summary generation completed in {total_time:.1f}s total"
                )

                record_progress(db, filing_id, "completed")

                if user_id:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        month = get_current_month()
                        increment_user_usage(user.id, month, db)

        try:
            await asyncio.wait_for(generate_summary_core(), timeout=global_timeout)
        except asyncio.TimeoutError:
            logger.error(
                f"[{filing_id}] ✗ Summary generation exceeded global timeout of {global_timeout}s"
            )
            # TIMEOUT = PARTIAL RESULT - Do NOT cache to database
            # Per execution plan: Timeouts result in partial designation, never cached
            record_progress(
                db,
                filing_id,
                "partial",
                error="timeout",
                section_coverage={
                    "result_type": "partial",
                    "partial_reason": "timeout",
                    "covered_count": 0,
                    "total_count": len(HIDEABLE_SECTIONS),
                    "covered_sections": [],
                    "sections_unavailable": generate_unavailable_sections_notes(HIDEABLE_SECTIONS),
                    "retry_available": True,
                    "message": "Analysis timed out. Please retry for full analysis.",
                },
            )
            logger.warning(
                f"[{filing_id}] ⚠ PARTIAL RESULT (timeout) - NOT CACHING. "
                f"User should retry with 'Retry Full Analysis' button."
            )
            # Do NOT save to Summary table - timeout results are discarded
            # Do NOT commit any summary to database
        except Exception as inner_error:
            error_msg = str(inner_error)
            logger.error(f"Error in timeout wrapper: {error_msg}", exc_info=True)

            # ERROR = PARTIAL RESULT - Do NOT cache to database
            # Per execution plan: Errors result in partial designation, never cached
            record_progress(
                db,
                filing_id,
                "partial",
                error=f"error: {error_msg[:200]}",
                section_coverage={
                    "result_type": "partial",
                    "partial_reason": "api_error",
                    "covered_count": 0,
                    "total_count": len(HIDEABLE_SECTIONS),
                    "covered_sections": [],
                    "sections_unavailable": generate_unavailable_sections_notes(HIDEABLE_SECTIONS),
                    "retry_available": True,
                    "message": "Unable to complete analysis. Please retry for full analysis.",
                    "error_detail": error_msg[:200],
                },
            )
            logger.warning(
                f"[{filing_id}] ⚠ PARTIAL RESULT (error) - NOT CACHING. "
                f"Error: {error_msg[:100]}. User should retry with 'Retry Full Analysis' button."
            )
            # Do NOT save to Summary table - error results are discarded
            # Do NOT commit any summary to database

# Stages from which generation can no longer make progress on its own.
TERMINAL_STAGES = {"completed", "error", "partial"}

# A non-terminal progress row older than this is considered orphaned (a crashed/abandoned
# background task). The longest legitimate run is the 10-K global_timeout (120s) plus the
# stream pipeline (90s); 180s leaves comfortable headroom before we call it dead.
STALE_PROGRESS_SECONDS = 180


def mark_stale_progress_as_error(progress: SummaryGenerationProgress) -> bool:
    """Detect an orphaned (stuck) progress row and flip it to a retryable error in-place.

    Fire-and-forget background generation can die without recording a terminal state if it
    crashes before its inner guard runs. Rather than leave the UI spinning forever, surface
    a stale non-terminal row as an error the user can retry. Returns True if it mutated the
    row (caller is responsible for committing)."""
    if progress.stage in TERMINAL_STAGES:
        return False

    last_update = progress.updated_at or progress.started_at
    if last_update is None:
        return False
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)

    if (_utcnow() - last_update).total_seconds() <= STALE_PROGRESS_SECONDS:
        return False

    progress.stage = "error"
    progress.error = "Generation stalled and was abandoned. Please retry."
    return True


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
        return progress_as_dict(progress)
