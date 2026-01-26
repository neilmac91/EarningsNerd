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
from app.services.xbrl_service import clear_xbrl_cache, get_xbrl_cache_stats

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_admin(user: User) -> None:
    """Verify user has admin privileges.

    For now, any authenticated user can use admin endpoints.
    In production, this should check for admin role.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    # TODO: Add proper admin role check
    # if not user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")


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
