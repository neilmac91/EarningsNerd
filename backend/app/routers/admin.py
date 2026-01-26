"""Admin endpoints for data management and cleanup.

These endpoints require authentication and are intended for administrative use only.
They allow clearing cached summaries and XBRL data to fix issues with stale data.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.database import get_db
from app.models import Filing, Summary, User, SummaryGenerationProgress, FilingContentCache
from app.routers.auth import get_current_user
# EdgarTools migration: Using new edgar module
from app.services.edgar import clear_xbrl_cache, get_xbrl_cache_stats

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_admin(user: User) -> None:
    """Verify user has admin privileges.

    Only users with is_admin=True can access admin endpoints.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


@router.delete("/filing/{filing_id}/summary")
async def delete_filing_summary(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete the summary for a specific filing.

    This allows re-generation of the summary with fresh data.
    Use this when a summary contains incorrect or stale information.
    """
    _require_admin(current_user)

    # Find the filing
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Delete summary if exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        db.delete(summary)
        logger.info(f"Admin {current_user.id} deleted summary for filing {filing_id}")

    # Delete progress record to allow fresh generation
    progress = db.query(SummaryGenerationProgress).filter(
        SummaryGenerationProgress.filing_id == filing_id
    ).first()
    if progress:
        db.delete(progress)

    db.commit()

    return {
        "message": f"Summary deleted for filing {filing_id}",
        "filing_id": filing_id,
        "summary_deleted": summary is not None
    }


@router.delete("/filing/{filing_id}/xbrl")
async def clear_filing_xbrl(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear XBRL data for a specific filing.

    This removes cached XBRL data from the database, allowing
    fresh data to be fetched from SEC on the next request.
    """
    _require_admin(current_user)

    # Find the filing
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    # Clear XBRL data
    had_xbrl = filing.xbrl_data is not None
    filing.xbrl_data = None

    db.commit()
    logger.info(f"Admin {current_user.id} cleared XBRL data for filing {filing_id}")

    return {
        "message": f"XBRL data cleared for filing {filing_id}",
        "filing_id": filing_id,
        "had_xbrl_data": had_xbrl
    }


@router.delete("/filing/{filing_id}/reset")
async def reset_filing(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Completely reset a filing's generated content.

    This deletes:
    - Summary
    - XBRL data
    - Content cache
    - Generation progress

    Use this to force a complete re-generation from scratch.
    """
    _require_admin(current_user)

    # Find the filing
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")

    deleted = {
        "summary": False,
        "xbrl_data": False,
        "content_cache": False,
        "progress": False
    }

    # Delete summary
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        db.delete(summary)
        deleted["summary"] = True

    # Clear XBRL data
    if filing.xbrl_data is not None:
        filing.xbrl_data = None
        deleted["xbrl_data"] = True

    # Delete content cache
    content_cache = db.query(FilingContentCache).filter(
        FilingContentCache.filing_id == filing_id
    ).first()
    if content_cache:
        db.delete(content_cache)
        deleted["content_cache"] = True

    # Delete progress record
    progress = db.query(SummaryGenerationProgress).filter(
        SummaryGenerationProgress.filing_id == filing_id
    ).first()
    if progress:
        db.delete(progress)
        deleted["progress"] = True

    db.commit()
    logger.info(f"Admin {current_user.id} reset filing {filing_id}: {deleted}")

    return {
        "message": f"Filing {filing_id} has been reset",
        "filing_id": filing_id,
        "deleted": deleted
    }


@router.post("/xbrl/clear-memory-cache")
async def clear_xbrl_memory_cache(
    current_user: User = Depends(get_current_user),
):
    """Clear the in-memory XBRL cache.

    This clears the server's in-memory cache of XBRL data,
    forcing fresh fetches from SEC for all subsequent requests.

    Note: This only affects the current server instance.
    """
    _require_admin(current_user)

    # Get stats before clearing
    stats_before = get_xbrl_cache_stats()

    # Clear the cache
    count = clear_xbrl_cache()

    logger.info(f"Admin {current_user.id} cleared XBRL memory cache ({count} entries)")

    return {
        "message": f"XBRL memory cache cleared",
        "entries_cleared": count,
        "stats_before": stats_before
    }


@router.get("/xbrl/cache-stats")
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
):
    """Get XBRL cache statistics.

    Returns information about the current state of the XBRL cache.
    """
    _require_admin(current_user)

    return get_xbrl_cache_stats()


def _extract_xbrl_years(xbrl_data: dict) -> set:
    """Extract all years from XBRL data periods."""
    years = set()
    if not xbrl_data:
        return years

    # Check common metric keys that have period data
    for key in ["revenue", "net_income", "total_assets", "earnings_per_share"]:
        entries = xbrl_data.get(key, [])
        if isinstance(entries, list):
            for entry in entries:
                period = entry.get("period") if isinstance(entry, dict) else None
                if period and isinstance(period, str) and len(period) >= 4:
                    try:
                        year = int(period[:4])
                        years.add(year)
                    except ValueError:
                        pass
    return years


@router.get("/filings/audit-xbrl")
async def audit_stale_xbrl(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    year_threshold: int = 2
):
    """Audit filings for stale XBRL data.

    Finds filings where the XBRL data years don't match the filing's period.
    This helps identify filings with incorrectly cached data.

    Args:
        year_threshold: Max years difference allowed (default 2).
                        Filings with XBRL data older than this are flagged.

    Returns list of filing IDs with stale data and details about the mismatch.
    """
    _require_admin(current_user)

    # Find all filings with XBRL data
    filings_with_xbrl = db.query(Filing).filter(
        Filing.xbrl_data.isnot(None)
    ).all()

    stale_filings = []
    for filing in filings_with_xbrl:
        # Get the expected year from filing period
        expected_year = None
        if filing.period_end_date:
            expected_year = filing.period_end_date.year
        elif filing.filing_date:
            expected_year = filing.filing_date.year

        if not expected_year:
            continue

        # Extract years from XBRL data
        xbrl_years = _extract_xbrl_years(filing.xbrl_data)

        if not xbrl_years:
            continue

        # Check if any XBRL year is too far from expected
        max_xbrl_year = max(xbrl_years)
        year_diff = expected_year - max_xbrl_year

        if year_diff > year_threshold:
            stale_filings.append({
                "filing_id": filing.id,
                "company_id": filing.company_id,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
                "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
                "expected_year": expected_year,
                "xbrl_years": sorted(xbrl_years, reverse=True),
                "max_xbrl_year": max_xbrl_year,
                "year_difference": year_diff
            })

    return {
        "total_filings_with_xbrl": len(filings_with_xbrl),
        "stale_filings_count": len(stale_filings),
        "year_threshold": year_threshold,
        "stale_filings": stale_filings
    }


@router.post("/filings/bulk-reset-stale")
async def bulk_reset_stale_xbrl(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    year_threshold: int = 2,
    dry_run: bool = True
):
    """Bulk reset filings with stale XBRL data.

    Identifies filings with XBRL data years that don't match the filing period,
    and optionally resets them for regeneration.

    Args:
        year_threshold: Max years difference allowed (default 2).
        dry_run: If True, only report what would be reset. If False, actually reset.

    Returns list of affected filings and reset status.
    """
    _require_admin(current_user)

    # Find all filings with XBRL data
    filings_with_xbrl = db.query(Filing).filter(
        Filing.xbrl_data.isnot(None)
    ).all()

    affected_filings = []
    for filing in filings_with_xbrl:
        # Get the expected year from filing period
        expected_year = None
        if filing.period_end_date:
            expected_year = filing.period_end_date.year
        elif filing.filing_date:
            expected_year = filing.filing_date.year

        if not expected_year:
            continue

        # Extract years from XBRL data
        xbrl_years = _extract_xbrl_years(filing.xbrl_data)

        if not xbrl_years:
            continue

        # Check if any XBRL year is too far from expected
        max_xbrl_year = max(xbrl_years)
        year_diff = expected_year - max_xbrl_year

        if year_diff > year_threshold:
            affected_filings.append({
                "filing_id": filing.id,
                "expected_year": expected_year,
                "max_xbrl_year": max_xbrl_year,
                "year_difference": year_diff
            })

            if not dry_run:
                # Reset the filing
                # Clear XBRL data
                filing.xbrl_data = None

                # Delete summary if exists
                summary = db.query(Summary).filter(Summary.filing_id == filing.id).first()
                if summary:
                    db.delete(summary)

                # Delete progress if exists
                progress = db.query(SummaryGenerationProgress).filter(
                    SummaryGenerationProgress.filing_id == filing.id
                ).first()
                if progress:
                    db.delete(progress)

                logger.info(f"Admin {current_user.id} bulk-reset filing {filing.id} (stale XBRL)")

    if not dry_run:
        db.commit()
        logger.info(f"Admin {current_user.id} bulk-reset {len(affected_filings)} filings with stale XBRL data")

    return {
        "dry_run": dry_run,
        "year_threshold": year_threshold,
        "affected_count": len(affected_filings),
        "affected_filings": affected_filings,
        "message": f"{'Would reset' if dry_run else 'Reset'} {len(affected_filings)} filings with stale XBRL data"
    }
