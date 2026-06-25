"""Admin endpoints for data management and cleanup.

These endpoints require authentication and are intended for administrative use only.
They allow clearing cached summaries and XBRL data to fix issues with stale data.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone
import logging

from app.config import settings
from app.database import get_db
from app.models import Filing, Summary, User, SummaryGenerationProgress, FilingContentCache, InviteCode
from app.models.feedback import Feedback
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackAdminItem, FeedbackStatusUpdate, FeedbackStatus, FeedbackType
# EdgarTools migration: Using new edgar module
from app.services.edgar import clear_xbrl_cache, get_xbrl_cache_stats
from app.services.resend_service import send_email, ResendError
from app.services import invite_service
from app.services import audit_service
from app.services.email_service import send_invite_email

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
