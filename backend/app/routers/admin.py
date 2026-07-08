"""Admin endpoints for data management and cleanup.

These endpoints require authentication and are intended for administrative use only.
They allow clearing cached summaries and XBRL data to fix issues with stale data.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone
import logging

from app.config import settings
from app.database import get_db
from app.models import Filing, Summary, SavedSummary, User, SummaryGenerationProgress, FilingContentCache, InviteCode
from app.models.feedback import Feedback
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackAdminItem, FeedbackStatusUpdate, FeedbackStatus, FeedbackType
# EdgarTools migration: Using new edgar module
from app.services.edgar import clear_xbrl_cache, get_xbrl_cache_stats
from app.services.resend_service import send_email, ResendError
from app.services import invite_service
from app.services import audit_service
from app.services.email_service import send_invite_email
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION, is_stale

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


def _chunked(seq, size=900):
    """Yield successive `size`-length slices so a bulk IN(...) can't exceed a DB parameter cap
    (SQLite's 999, PostgreSQL's bind-parameter ceiling)."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


class EmailTestRequest(BaseModel):
    to: Optional[EmailStr] = None  # defaults to the requesting admin's own email


@router.post("/email/test")
async def send_test_email(
    payload: Optional[EmailTestRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """Admin-only: send a test email through the real Resend path and return the result.

    Surfaces the exact provider response — including a 4xx/422 error body and the From
    address actually in use — so email misconfiguration can be diagnosed and a fix
    verified without reading logs. Defaults to sending to the admin's own email.
    """
    _require_admin(current_user)
    to_addr = (payload.to if payload and payload.to else current_user.email)

    try:
        await send_email(
            to=[to_addr],
            subject="EarningsNerd email test",
            html=(
                "<p>This is a test email from EarningsNerd. If you received it, outbound "
                "email is working.</p>"
            ),
        )
        return {
            "success": True,
            "to": to_addr,
            "from": settings.RESEND_FROM_EMAIL,
            "message": f"Resend accepted the email for delivery to {to_addr}.",
        }
    except ResendError as e:
        # e carries Resend's status + response body, e.g. "Resend API error (422): {...}"
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"success": False, "to": to_addr, "from": settings.RESEND_FROM_EMAIL, "error": str(e)},
        )
    except Exception as e:  # network/timeout/etc.
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "success": False,
                "to": to_addr,
                "from": settings.RESEND_FROM_EMAIL,
                "error": f"{e.__class__.__name__}: {e}",
            },
        )


class MintInviteRequest(BaseModel):
    email: Optional[EmailStr] = None        # optional binding; only this address may redeem
    # optional grouping label (launch wave, partner batch); capped to the column width so an
    # over-long value returns a clean 422 instead of a DB driver 500.
    cohort: Optional[str] = Field(default=None, max_length=64)
    expires_in_hours: Optional[int] = None  # defaults to settings.INVITE_EXPIRY_HOURS
    send_email: bool = False                # if True and email is set, also email the magic link


class InviteResponse(BaseModel):
    id: int
    email: Optional[str]
    invite_link: str
    expires_at: datetime
    emailed: bool
    cohort: Optional[str]


class ResendInviteRequest(BaseModel):
    expires_in_hours: Optional[int] = None  # defaults to settings.INVITE_EXPIRY_HOURS


class ResendInviteResponse(InviteResponse):
    revoked_invite_id: int


def _invite_status(invite: InviteCode) -> str:
    # "used" outranks "revoked": once an invite has been redeemed, that fact is the truth worth
    # surfacing even if the row also carries a revoke flag (e.g. legacy data), so redemption
    # history is never masked.
    if invite.used_at is not None:
        return "used"
    if invite.is_revoked:
        return "revoked"
    exp = invite.expires_at
    if exp is not None:
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return "expired"
    return "pending"


@router.post("/invites", response_model=InviteResponse)
async def mint_invite(
    payload: MintInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: mint a single-use beta invite and return its magic link (shown once).

    The raw token is embedded in ``invite_link`` and never persisted (only its hash is stored).
    When ``send_email`` is set and an ``email`` is given, the link is also emailed best-effort.
    """
    _require_admin(current_user)
    invite, _raw, link = invite_service.mint_invite(
        db,
        created_by=current_user.id,
        email=payload.email,
        expires_in_hours=payload.expires_in_hours,
        cohort=payload.cohort,
    )
    emailed = False
    if payload.send_email and payload.email:
        try:
            await send_invite_email(to_email=payload.email, magic_link=link)
            emailed = True
        except Exception:
            logger.warning("Failed to send invite email to %s", payload.email, exc_info=True)
    try:
        audit_service.create_audit_log(
            db,
            action="invite_minted",
            user_id=current_user.id,
            user_email=current_user.email,
            entity_type="invite",
            entity_id=str(invite.id),
            details={"cohort": invite.cohort, "emailed": emailed},
        )
    except Exception:
        logger.warning("Failed to write audit log for invite_minted", exc_info=True)
    return InviteResponse(
        id=invite.id,
        email=invite.email,
        invite_link=link,
        expires_at=invite.expires_at,
        emailed=emailed,
        cohort=invite.cohort,
    )


@router.get("/invites")
async def list_invites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: list recent invites with derived status (pending/used/revoked/expired)."""
    _require_admin(current_user)
    rows = db.query(InviteCode).order_by(InviteCode.created_at.desc()).limit(200).all()
    return {
        "invites": [
            {
                "id": r.id,
                "email": r.email,
                "status": _invite_status(r),
                "cohort": r.cohort,
                "expires_at": r.expires_at,
                "used_at": r.used_at,
                "user_id": r.user_id,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: revoke an unused invite so its link can no longer be redeemed."""
    _require_admin(current_user)
    invite = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.used_at is not None:
        # A redeemed invite can't be "un-redeemed"; revoking it would only corrupt its status.
        raise HTTPException(status_code=409, detail="Invite already redeemed")
    invite.is_revoked = True
    db.commit()
    logger.info("Admin %s revoked invite %s", current_user.id, invite_id)
    try:
        audit_service.create_audit_log(
            db,
            action="invite_revoked",
            user_id=current_user.id,
            user_email=current_user.email,
            entity_type="invite",
            entity_id=str(invite_id),
        )
    except Exception:
        logger.warning("Failed to write audit log for invite_revoked", exc_info=True)
    return {"message": "Invite revoked", "invite_id": invite_id, "status": _invite_status(invite)}


@router.post("/invites/{invite_id}/resend", response_model=ResendInviteResponse)
async def resend_invite(
    invite_id: int,
    payload: Optional[ResendInviteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: re-issue an invite by minting a fresh link (same email + cohort) and revoking the old.

    Used invites can't be re-sent (409). The old invite is revoked so its link can no longer be
    redeemed; the new magic link is returned (shown once) and, when an email is bound, also emailed
    best-effort. The raw token is never persisted nor written to the audit log.
    """
    _require_admin(current_user)
    old = db.query(InviteCode).filter(InviteCode.id == invite_id).first()
    if not old:
        raise HTTPException(status_code=404, detail="Invite not found")
    if old.used_at is not None:
        raise HTTPException(status_code=409, detail="Invite already redeemed")

    expires_in_hours = payload.expires_in_hours if payload else None
    # Revoke the old invite BEFORE minting the replacement so there is never a window in which two
    # links for the same invitee are simultaneously redeemable. mint_invite's commit persists the
    # revoke (on the already-tracked ``old`` row) and the new row in a single transaction.
    old.is_revoked = True
    invite, _raw, link = invite_service.mint_invite(
        db,
        created_by=current_user.id,
        email=old.email,
        expires_in_hours=expires_in_hours,
        cohort=old.cohort,
    )

    emailed = False
    if invite.email:
        try:
            await send_invite_email(to_email=invite.email, magic_link=link)
            emailed = True
        except Exception:
            logger.warning("Failed to send invite email to %s", invite.email, exc_info=True)

    logger.info("Admin %s resent invite %s as %s", current_user.id, invite_id, invite.id)
    try:
        audit_service.create_audit_log(
            db,
            action="invite_resent",
            user_id=current_user.id,
            user_email=current_user.email,
            entity_type="invite",
            entity_id=str(invite.id),
            details={"revoked_invite_id": invite_id, "cohort": invite.cohort, "emailed": emailed},
        )
    except Exception:
        logger.warning("Failed to write audit log for invite_resent", exc_info=True)

    return ResendInviteResponse(
        id=invite.id,
        email=invite.email,
        invite_link=link,
        expires_at=invite.expires_at,
        emailed=emailed,
        cohort=invite.cohort,
        revoked_invite_id=invite_id,
    )


def _feedback_item(row: Feedback, user_email: Optional[str]) -> dict:
    """Shape a Feedback row (+ joined user email) into the admin API item."""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_email": user_email,
        "type": row.type,
        "message": row.message,
        "page_url": row.page_url,
        "status": row.status,
        "created_at": row.created_at,
    }


@router.get("/feedback")
async def list_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[FeedbackStatus] = None,
    type: Optional[FeedbackType] = None,
):
    """Admin-only: list recent beta feedback (newest first, capped at 200).

    Joins ``users`` so the submitter's email resolves; the LEFT OUTER JOIN keeps rows whose
    ``user_id`` is null or whose user was deleted (FK is ON DELETE SET NULL). Optional ``status``
    and ``type`` query params narrow the result when provided.
    """
    _require_admin(current_user)
    query = (
        db.query(Feedback, User.email)
        .outerjoin(User, Feedback.user_id == User.id)
    )
    if status is not None:
        query = query.filter(Feedback.status == status)
    if type is not None:
        query = query.filter(Feedback.type == type)
    rows = query.order_by(Feedback.created_at.desc()).limit(200).all()
    return {"feedback": [_feedback_item(row, email) for row, email in rows]}


@router.patch("/feedback/{feedback_id}", response_model=FeedbackAdminItem)
async def update_feedback_status(
    feedback_id: int,
    payload: FeedbackStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: transition a feedback row's triage status (new/triaged/resolved).

    Returns the updated row in the same shape as a list item (with the submitter's email
    re-resolved). An invalid status is rejected with 422 by the schema before this runs.
    """
    _require_admin(current_user)
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    new_status = payload.status
    feedback.status = new_status
    db.commit()
    db.refresh(feedback)
    logger.info("Admin %s set feedback %s status to %s", current_user.id, feedback_id, new_status)

    try:
        audit_service.create_audit_log(
            db,
            action="feedback_status_changed",
            user_id=current_user.id,
            user_email=current_user.email,
            entity_type="feedback",
            entity_id=str(feedback_id),
            details={"status": new_status},
        )
    except Exception:
        logger.warning("Failed to write audit log for feedback_status_changed", exc_info=True)

    # Re-resolve the submitter's email (null-safe when user_id is null/deleted).
    user_email = None
    if feedback.user_id is not None:
        submitter = db.query(User).filter(User.id == feedback.user_id).first()
        user_email = submitter.email if submitter else None
    return _feedback_item(feedback, user_email)


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
        "message": "XBRL memory cache cleared",
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


@router.post("/summaries/reset-all")
async def reset_all_summaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    dry_run: bool = True,
    filing_type: Optional[str] = None,
    include_saved: bool = False,
):
    """Bulk-clear generated summaries so they regenerate with the CURRENT prompts.

    Use after a prompt change to refresh the site (or one form) without raw SQL. Deletes Summary
    rows (and their SummaryGenerationProgress) so the lazy regeneration path rebuilds them on next
    view. **Keeps** XBRL data and the filing content cache — those are the source figures/text
    (unchanged by a prompt edit), so regeneration stays fast and avoids re-fetching from SEC.

    FK-safe: a Summary pinned by a `saved_summaries` bookmark is SKIPPED by default — deleting it
    would violate the foreign key in Postgres (and orphan the bookmark). Pass ``include_saved=true``
    to also drop those bookmarks and refresh them too.

    Args:
        dry_run: If True (default), only report what would be reset — delete nothing.
        filing_type: Optional form filter (e.g. "10-K", "10-Q", "20-F"). None = all forms.
        include_saved: If True, also delete the saved_summaries bookmarks for matched summaries
            (so saved filings refresh too). The bookmark is lost; the user can re-save afterward.

    Returns counts plus the skipped (saved) filings so an operator can act on them deliberately.
    """
    _require_admin(current_user)

    # Select only the columns we need (id + filing_id). Summary has large JSON/text columns we
    # never read here, so loading full ORM objects for a bulk op wastes memory + DB I/O.
    query = db.query(Summary.id, Summary.filing_id)
    if filing_type:
        query = query.join(Filing, Filing.id == Summary.filing_id).filter(
            Filing.filing_type == filing_type
        )
    summaries = query.all()

    # Pinned (saved) summaries, scoped to the same filter so we don't load every bookmark in the DB.
    pinned_query = db.query(SavedSummary.summary_id).join(
        Summary, Summary.id == SavedSummary.summary_id
    )
    if filing_type:
        pinned_query = pinned_query.join(Filing, Filing.id == Summary.filing_id).filter(
            Filing.filing_type == filing_type
        )
    pinned_ids = {sid for (sid,) in pinned_query.all()}

    to_delete = [s for s in summaries if include_saved or s.id not in pinned_ids]
    skipped = [s for s in summaries if not include_saved and s.id in pinned_ids]

    delete_ids = [s.id for s in to_delete]
    delete_filing_ids = sorted({s.filing_id for s in to_delete})
    skipped_saved = [{"filing_id": s.filing_id, "summary_id": s.id} for s in skipped]

    if not dry_run and delete_ids:
        # Chunk every IN-list so a large reset can't exceed a DB parameter cap (SQLite's 999, etc.).
        # When including saved summaries, drop their bookmarks first so the FK doesn't block.
        if include_saved:
            for chunk in _chunked(delete_ids):
                db.query(SavedSummary).filter(
                    SavedSummary.summary_id.in_(chunk)
                ).delete(synchronize_session=False)
        # Clear progress so regeneration starts clean (XBRL + content cache are intentionally kept).
        for chunk in _chunked(delete_filing_ids):
            db.query(SummaryGenerationProgress).filter(
                SummaryGenerationProgress.filing_id.in_(chunk)
            ).delete(synchronize_session=False)
        for chunk in _chunked(delete_ids):
            db.query(Summary).filter(Summary.id.in_(chunk)).delete(synchronize_session=False)
        db.commit()
        audit_service.create_audit_log(
            db=db,
            action="summaries_bulk_reset",
            user_id=current_user.id,
            user_email=getattr(current_user, "email", None),
            entity_type="summaries",
            details={
                "filing_type": filing_type,
                "include_saved": include_saved,
                "deleted_count": len(delete_ids),
                "skipped_saved_count": len(skipped_saved),
            },
            status="success",
        )
        logger.info(
            "Admin %s bulk-reset %d summaries (filing_type=%s, include_saved=%s); skipped %d saved",
            current_user.id, len(delete_ids), filing_type, include_saved, len(skipped_saved),
        )

    return {
        "dry_run": dry_run,
        "filing_type": filing_type,
        "include_saved": include_saved,
        "total_matched": len(summaries),
        "deleted_count": len(delete_ids),
        "skipped_saved_count": len(skipped_saved),
        "skipped_saved": skipped_saved,
        "retained": "xbrl_data + filing_content_cache (regeneration is lazy, on next view)",
        "message": (
            f"{'Would delete' if dry_run else 'Deleted'} {len(delete_ids)} summaries"
            f"{f' of type {filing_type}' if filing_type else ''}; "
            f"{'would skip' if dry_run else 'skipped'} {len(skipped_saved)} saved"
            f"{' (bookmarks included)' if include_saved else ''}."
        ),
    }


# Hard ceiling on rows regenerated per refresh-stale call. Each generation can take up to ~120s and
# runs synchronously in the request, so the batch is capped to stay well within the Cloud Run request
# timeout and avoid holding a DB connection for a long op. Large backlogs = repeated calls / a job.
_REFRESH_STALE_MAX_BATCH = 10


def _stale_summary_filter(schema_version_lt: Optional[int]):
    """Rows to refresh: missing/behind stamp. schema_version_lt bounds by schema; None = stale vs
    the CURRENT schema+prompt version (covers a prompt-only bump that leaves schema_version equal)."""
    if schema_version_lt is not None:
        return or_(Summary.schema_version.is_(None), Summary.schema_version < schema_version_lt)
    return or_(
        Summary.schema_version.is_(None),
        Summary.schema_version != SUMMARY_SCHEMA_VERSION,
        Summary.prompt_version.is_(None),
        Summary.prompt_version != SUMMARY_PROMPT_VERSION,
    )


@router.post("/summaries/refresh-stale")
async def refresh_stale_summaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    schema_version_lt: Optional[int] = None,
    filing_type: Optional[str] = None,
    limit: int = 5,
    dry_run: bool = True,
):
    """Admin-only: regenerate version-stale summaries IN PLACE (bookmarks survive).

    Unlike ``reset-all`` (which DELETEs rows and, with ``include_saved``, destroys the
    ``saved_summaries`` bookmark), this drains the ONE orchestrator with ``force_regenerate=True``:
    each stale row is UPDATEd in place, preserving ``summaries.id`` so the FK/bookmark survives, and
    a keep-better quality gate prevents a 75s AI-timeout fallback from downgrading a stored ``full``.

    **Bounded, synchronous small batch.** Each generation can take up to ~120s, so a real run is
    hard-capped at ``_REFRESH_STALE_MAX_BATCH`` rows and generates sequentially while the request is
    in flight (keeping the Cloud Run request's CPU allocated — FastAPI ``BackgroundTasks`` would run
    under post-response CPU throttling and could be cut short). This deliberately keeps one call well
    within the request timeout; it is NOT a whole-corpus backfill. Drain a large backlog by calling
    repeatedly (the op is idempotent + keep-better-gated) or via a precompute-style Cloud Run job.

    ``dry_run`` (default) reports the full ``stale_total`` without regenerating — the admin staleness
    count — while ``batch_limit`` reflects the clamped per-call ceiling. Candidates are ordered
    most-recent-filing first (a traffic proxy — the DB has no per-summary hit count).

    Args:
        schema_version_lt: Refresh rows whose ``schema_version`` is NULL or below this. Omit to
            refresh everything stale vs the current schema+prompt version.
        filing_type: Optional form filter (e.g. "10-K", "10-Q").
        limit: Rows to regenerate this call, clamped to [1, _REFRESH_STALE_MAX_BATCH].
        dry_run: If True (default), only report the stale candidates — regenerate nothing.
    """
    _require_admin(current_user)
    limit = max(1, min(limit, _REFRESH_STALE_MAX_BATCH))

    query = (
        db.query(Summary.id, Summary.filing_id, Summary.schema_version, Summary.prompt_version)
        .join(Filing, Filing.id == Summary.filing_id)
        .filter(_stale_summary_filter(schema_version_lt))
    )
    if filing_type:
        query = query.filter(Filing.filing_type == filing_type)
    stale_total = query.count()
    # Randomized order (not filing_date DESC): a filing that keep-better-loses every time would
    # otherwise park itself at a deterministic head-of-line and wedge every subsequent batch. Random
    # sampling turns a permanent wedge into a diminishing nuisance.
    candidates = query.order_by(func.random()).limit(limit).all()
    candidate_filing_ids = [c.filing_id for c in candidates]

    # Honest per-filing outcomes: a keep-better gate-keep regenerates nothing (the stored better
    # version stays), so counting every non-raising call as "regenerated" would report progress the
    # batch didn't make while the stale_total never moves. Classify by re-reading the row's stamps.
    updated: list[int] = []
    kept_by_gate: list[int] = []
    failed: list[int] = []
    if not dry_run and candidate_filing_ids:
        from app.services.summary_generation_service import generate_summary_background

        # Guard the admin session against N+1 re-expiry across the loop's own commits; generation
        # runs in the pipeline's OWN sessions, so this only protects rows/audit held here.
        prev_expire = db.expire_on_commit
        db.expire_on_commit = False
        try:
            for fid in candidate_filing_ids:
                try:
                    await generate_summary_background(fid, None, force_regenerate=True)
                except Exception:  # noqa: BLE001 — one filing's failure must not abort the batch
                    logger.warning("refresh-stale: regeneration failed for filing %s", fid, exc_info=True)
                    failed.append(fid)
                    continue
                # Re-read the (separately-committed) row's stamps: current => actually updated;
                # still stale => the keep-better gate kept the stored version (not regenerated).
                # Commit first to end this session's read transaction so the fresh SELECT sees the
                # generation session's commit (no writes pending here, so it's a transaction reset).
                db.commit()
                stamp = (
                    db.query(Summary.schema_version, Summary.prompt_version)
                    .filter(Summary.filing_id == fid)
                    .first()
                )
                if stamp is not None and not is_stale(stamp[0], stamp[1]):
                    updated.append(fid)
                else:
                    kept_by_gate.append(fid)
            audit_service.create_audit_log(
                db=db,
                action="summaries_refresh_stale",
                user_id=current_user.id,
                user_email=getattr(current_user, "email", None),
                entity_type="summaries",
                details={
                    "filing_type": filing_type,
                    "schema_version_lt": schema_version_lt,
                    "stale_total": stale_total,
                    "updated_count": len(updated),
                    "kept_by_gate_count": len(kept_by_gate),
                    "failed_count": len(failed),
                },
                status="success",
            )
        finally:
            db.expire_on_commit = prev_expire
        logger.info(
            "Admin %s refresh-stale: updated %d, kept-by-gate %d, failed %d of %d stale (filing_type=%s)",
            current_user.id, len(updated), len(kept_by_gate), len(failed), stale_total, filing_type,
        )

    return {
        "dry_run": dry_run,
        "filing_type": filing_type,
        "schema_version_lt": schema_version_lt,
        "current_schema_version": SUMMARY_SCHEMA_VERSION,
        "current_prompt_version": SUMMARY_PROMPT_VERSION,
        "stale_total": stale_total,
        "batch_limit": limit,
        "candidate_filing_ids": candidate_filing_ids,
        # Honest outcomes: only `updated` rows were actually regenerated; `kept_by_gate` rows lost to
        # the keep-better gate and remain stale (they may be re-selected on a later call).
        "updated_count": len(updated),
        "updated_filing_ids": updated,
        "kept_by_gate_count": len(kept_by_gate),
        "kept_by_gate_filing_ids": kept_by_gate,
        "failed_count": len(failed),
        "failed_filing_ids": failed,
        "message": (
            f"{stale_total} stale summaries"
            f"{f' of type {filing_type}' if filing_type else ''}; "
            + (
                f"would refresh up to {len(candidate_filing_ids)} in place (bookmarks preserved)."
                if dry_run
                else f"updated {len(updated)} in place, {len(kept_by_gate)} kept by the "
                f"keep-better gate (still stale), {len(failed)} failed."
            )
        ),
    }
