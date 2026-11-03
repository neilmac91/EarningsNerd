"""Admin endpoints for data management and cleanup.

These endpoints require authentication and are intended for administrative use only.
They allow clearing cached summaries and XBRL data to fix issues with stale data.
"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import Optional
from datetime import date, datetime, timedelta
import logging
import time

from app.config import settings
from app.database import get_db
from app.models import User
from app.models.invite_mail import PERMISSION_VIA
from app.models.feedback import Feedback
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackAdminItem, FeedbackStatusUpdate, FeedbackStatus, FeedbackType
# EdgarTools migration: Using new edgar module
from app.services.edgar import clear_xbrl_cache, get_xbrl_cache_stats
from app.services.resend_service import send_email, ResendError
from app.services import admin_feedback_service
from app.services import admin_account_service
from app.services import filing_list_service
from app.services import admin_filing_service
from app.services import admin_summary_service
from app.services import invite_delivery_service
from app.services import invite_service
from app.services import legal_readiness_service
from app.services import audit_service
from app.services.summary_pipeline import PIPELINE_TIMEOUT_SECONDS
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION
from app.utils.datetimes import utcnow
from app.utils.text import has_control_characters

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


class CreateFreeAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    full_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if has_control_characters(value):
            raise ValueError("Name must not contain control characters.")
        return value or None


@router.post("/users/free", status_code=status.HTTP_409_CONFLICT)
async def create_free_account(
    payload: CreateFreeAccountRequest,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        return await admin_account_service.create_free_account(
            email=payload.email, full_name=payload.full_name, actor=current_user,
        )
    except admin_account_service.AccountInvitationRequired as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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


MAX_INVITE_HOURS = 24 * 30  # a link lives a month at most; an unbounded value overflowed to a 500
PERMISSION_REQUIRED_DETAIL = "Record how and when the recipient asked for an invitation before emailing it."
INVITED_COHORT_ONLY_DETAIL = (
    "Registration is open to the invited cohort only, so an invitation needs its recipient's address and exactly "
    "that cohort."
)


def _require_invite_admitted(cohort: Optional[str], email: Optional[str]) -> None:
    """Refuse, before anything is written, an invitation no account could be opened with now: 503 while neither
    collection nor the invited-cohort exception admits accounts (as before the exception), 422 for one outside the
    exception's cohort or bound to no address. ``cohort`` and ``email`` are what the invitation stores (a mint strips
    the cohort and lower-cases the address); the cohort is never echoed."""
    if legal_readiness_service.admits_invite(cohort, email):
        return
    if not legal_readiness_service.is_invited_cohort_available():
        raise HTTPException(status_code=503, detail=legal_readiness_service.COLLECTION_UNAVAILABLE_MESSAGE)
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=INVITED_COHORT_ONLY_DETAIL)


class InvitePermission(BaseModel):
    """How and when the recipient asked for an invitation, which an emailed invitation records (EN-BETA PB-01).

    Knowing the person, an admin's checkbox or an account's acceptance of the Terms is not this permission: the record
    names the recipient's own request. It covers the invitation email for that link and its re-sends, nothing else,
    and an unsubscribe ends it."""

    model_config = ConfigDict(extra="forbid")

    requested_via: str
    requested_on: date

    @field_validator("requested_via")
    @classmethod
    def known_channel(cls, value: str) -> str:
        if value not in PERMISSION_VIA:
            raise ValueError(f"requested_via must be one of: {', '.join(PERMISSION_VIA)}.")
        return value

    @field_validator("requested_on")
    @classmethod
    def plausible_day(cls, value: date) -> date:
        today = utcnow().date()
        if value > today + timedelta(days=1):  # a day's grace: the admin's calendar day can be ahead of UTC's
            raise ValueError("The request can't be dated in the future.")
        if value < today - timedelta(days=365):
            raise ValueError("Record a request made within the last year.")
        return value

    def basis(self) -> invite_delivery_service.Permission:
        return invite_delivery_service.Permission(self.requested_via, self.requested_on)


class MintInviteRequest(BaseModel):
    email: Optional[EmailStr] = None        # optional binding; only this address may redeem
    # optional grouping label (launch wave, partner batch); capped to the column width so an
    # over-long value returns a clean 422 instead of a DB driver 500.
    cohort: Optional[str] = Field(default=None, max_length=64)
    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=MAX_INVITE_HOURS)  # default INVITE_EXPIRY_HOURS
    send_email: bool = False                # email the link: needs email, permission and invitation-email readiness
    permission: Optional[InvitePermission] = None


class InviteResponse(BaseModel):
    id: int
    email: Optional[str]
    invite_link: str
    expires_at: datetime
    # The provider accepted the invitation email. Not delivered, not read: delivery_status says what is known.
    emailed: bool
    cohort: Optional[str]
    # The emailed invitation's state (models/invite_mail.py), or None when no email was asked for.
    delivery_status: Optional[str] = None


class ResendInviteRequest(BaseModel):
    expires_in_hours: Optional[int] = Field(default=None, ge=1, le=MAX_INVITE_HOURS)  # default INVITE_EXPIRY_HOURS
    # None reads as the route always has: a bound invite's replacement is emailed, an unbound one's is not.
    # False re-issues a bound invite as a manual link the admin shares.
    send_email: Optional[bool] = None
    # Needed only to email the replacement of a link that was never emailed; otherwise its first request stands.
    permission: Optional[InvitePermission] = None


class ResendInviteResponse(InviteResponse):
    revoked_invite_id: int


def _mail_refusal(exc: Exception) -> HTTPException:
    """The answer to a refusal of the invite delivery service; nothing was written before it."""
    if isinstance(exc, invite_delivery_service.RecipientSuppressed):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This address unsubscribed from invitation emails, or its mail bounced or was reported as spam, "
                "so no invitation was emailed."
            ),
        )
    if isinstance(exc, invite_delivery_service.InvitePendingForAddress):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pending invitation already exists for this address (invite {exc.invite_id}). Re-send or revoke it.",
        )
    if isinstance(exc, invite_delivery_service.InviteNotBound):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This invitation isn't bound to an address, so it can't be emailed.",
        )
    if isinstance(exc, invite_delivery_service.PermissionRequired):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=PERMISSION_REQUIRED_DETAIL)
    if isinstance(exc, invite_delivery_service.InviteNotAdmitted):
        # The invited-cohort exception closed since the route's check, or the invite is outside it: as the route's.
        if not legal_readiness_service.is_invited_cohort_available():
            return HTTPException(status_code=503, detail=legal_readiness_service.COLLECTION_UNAVAILABLE_MESSAGE)
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=INVITED_COHORT_ONLY_DETAIL)
    if isinstance(exc, invite_service.InviteNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if isinstance(exc, invite_service.InviteAlreadyRedeemedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already redeemed")
    raise TypeError(f"not a mail refusal: {type(exc).__name__}")  # _MAIL_REFUSALS lists the classes this answers


_MAIL_REFUSALS = (
    invite_delivery_service.RecipientSuppressed,
    invite_delivery_service.InvitePendingForAddress,
    invite_delivery_service.InviteNotBound,
    invite_delivery_service.PermissionRequired,
    invite_delivery_service.InviteNotAdmitted,
    invite_service.InviteNotFoundError,
    invite_service.InviteAlreadyRedeemedError,
)


def _record_outcome(db: Session, delivery_id: int, outcome: invite_delivery_service.SendOutcome) -> str:
    """The send's outcome on its delivery row: a unit of its own after the mail, released before the route goes on.

    No pooled connection waits on the provider: the link and its "sending" row were committed in the unit before the
    send, and this is a fenced write after it. A failed record leaves the row "sending", which reads unknown later, and
    the admin is told what the call answered."""
    try:
        return invite_delivery_service.record_send_outcome(db, delivery_id, outcome)
    except Exception:  # noqa: BLE001 — the send happened or not; the call's own outcome is what is known
        logger.warning("Could not record invitation delivery %s", delivery_id, exc_info=True)
        return outcome.status
    finally:
        filing_list_service.release_request_session(db)


@router.get("/invites/readiness")
async def invite_readiness(current_user: User = Depends(get_current_user)):
    """Admin-only: what holds new collection, the invited-cohort exception and requested invitation email, as
    conditions, never values.

    The admin page reads it for its banner and to turn off what is unavailable; every invite route checks again, so a
    stale page cannot act on an old answer. An unpublished operator's draft fields, the provider key, the webhook
    secret and the configured cohort stay out of it."""
    _require_admin(current_user)
    return {
        "collection": legal_readiness_service.collection_readiness(),
        "invited_cohort": legal_readiness_service.invited_cohort_readiness(),
        "invitation_email": legal_readiness_service.invitation_email_readiness(),
    }


@router.post("/invites", response_model=InviteResponse)
async def mint_invite(
    payload: MintInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: mint a single-use beta invite and return its magic link (shown once).

    The raw token is embedded in ``invite_link`` and never persisted (only its hash is stored).
    ``send_email`` also emails the link to ``email``: only while requested invitation email is available, with the
    recipient's recorded request (``permission``), never to a suppressed address, and never while another link for
    the address is live. ``emailed`` is true when the provider accepted it, which is not delivery. While only the
    invited-cohort exception admits accounts, the invitation must be bound to an address and carry its cohort.
    """
    _require_admin(current_user)
    # What the invite will store: a mint strips the cohort (invite_service.mint_invite) and lower-cases the address.
    _require_invite_admitted(
        (payload.cohort or "").strip() or None, str(payload.email).strip().lower() if payload.email else None,
    )
    if payload.send_email:
        if not legal_readiness_service.is_invitation_email_available():
            raise HTTPException(status_code=503, detail=legal_readiness_service.INVITATION_EMAIL_UNAVAILABLE_MESSAGE)
        if not payload.email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="An emailed invitation needs the recipient's address.",
            )
        if payload.permission is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=PERMISSION_REQUIRED_DETAIL)
    # A commit expires the admin, and after the release it is detached: read what the units need first.
    admin_id, admin_email = current_user.id, current_user.email

    def mint() -> invite_delivery_service.PreparedInvite:
        try:
            if payload.send_email:
                return invite_delivery_service.prepare_invite_send(
                    db,
                    created_by=admin_id,
                    email=payload.email,
                    expires_in_hours=payload.expires_in_hours,
                    cohort=payload.cohort,
                    permission=payload.permission.basis(),
                )
            invite, _raw, link = invite_service.mint_invite(
                db,
                created_by=admin_id,
                email=payload.email,
                expires_in_hours=payload.expires_in_hours,
                cohort=payload.cohort,
            )
            return invite_delivery_service.PreparedInvite(issued=invite_delivery_service.issued_fields(invite, link))
        finally:
            filing_list_service.release_request_session(db)

    try:
        prepared = await run_in_threadpool(mint)
    except _MAIL_REFUSALS as exc:
        raise _mail_refusal(exc) from None
    issued = prepared.issued
    delivery_status: Optional[str] = None
    if prepared.delivery_id is not None:
        outcome = await invite_delivery_service.deliver(prepared)
        delivery_status = await run_in_threadpool(_record_outcome, db, prepared.delivery_id, outcome)
    emailed = delivery_status in invite_delivery_service.PROVIDER_TOOK

    def audit() -> None:
        # A unit of its own after the mail, so the row records whether it went and no pool slot waits on the mail
        # provider (E171).
        try:
            audit_service.create_audit_log(
                db,
                action="invite_minted",
                user_id=admin_id,
                user_email=admin_email,
                entity_type="invite",
                entity_id=str(issued["id"]),
                details={"cohort": issued["cohort"], "emailed": emailed, "delivery_status": delivery_status},
            )
        except Exception:
            logger.warning("Failed to write audit log for invite_minted", exc_info=True)
        finally:
            filing_list_service.release_request_session(db)

    await run_in_threadpool(audit)
    return InviteResponse(**issued, emailed=emailed, delivery_status=delivery_status)


@router.get("/invites")
async def list_invites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: list recent invites with derived status (pending/used/revoked/expired), each emailed invite's
    delivery state, and whether its address is suppressed."""
    _require_admin(current_user)

    def invites() -> dict:
        try:
            rows = invite_service.list_recent_invites(db)
            deliveries = invite_delivery_service.deliveries_for_invites(db, [r.id for r in rows])
            suppressed = invite_delivery_service.suppression_for_addresses(db, [r.email for r in rows if r.email])
            return {
                "invites": [
                    {
                        "id": r.id,
                        "email": r.email,
                        "status": invite_service.invite_status(r),
                        "cohort": r.cohort,
                        "expires_at": r.expires_at,
                        "used_at": r.used_at,
                        "user_id": r.user_id,
                        "created_at": r.created_at,
                        "delivery": deliveries.get(r.id),
                        "email_suppression": suppressed.get(r.email) if r.email else None,
                    }
                    for r in rows
                ]
            }
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(invites)


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: revoke an unused invite so its link can no longer be redeemed."""
    _require_admin(current_user)
    admin_id, admin_email = current_user.id, current_user.email

    def revoke() -> str:
        try:
            invite_status = invite_service.invite_status(invite_service.revoke_invite(db, invite_id))
            logger.info("Admin %s revoked invite %s", admin_id, invite_id)
            try:
                audit_service.create_audit_log(
                    db,
                    action="invite_revoked",
                    user_id=admin_id,
                    user_email=admin_email,
                    entity_type="invite",
                    entity_id=str(invite_id),
                )
            except Exception:
                logger.warning("Failed to write audit log for invite_revoked", exc_info=True)
            return invite_status
        finally:
            filing_list_service.release_request_session(db)

    try:
        invite_status = await run_in_threadpool(revoke)
    except invite_service.InviteNotFoundError:
        raise HTTPException(status_code=404, detail="Invite not found")
    except invite_service.InviteAlreadyRedeemedError:
        raise HTTPException(status_code=409, detail="Invite already redeemed")
    return {"message": "Invite revoked", "invite_id": invite_id, "status": invite_status}


@router.post("/invites/{invite_id}/resend", response_model=ResendInviteResponse)
async def resend_invite(
    invite_id: int,
    payload: Optional[ResendInviteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Admin-only: re-issue an invite by minting a fresh link (same email + cohort) and revoking the old.

    Used invites can't be re-sent (409). The old invite is revoked so its link can no longer be
    redeemed; the new magic link is returned (shown once). It is emailed when ``send_email`` says so, or, when it says
    nothing, when the invite is bound to an address, as before the field: only while requested invitation email is
    available, to an unsuppressed address, on the request the link was first emailed under (or ``permission``), and
    refused before anything is revoked when it cannot be. A bound invite is not re-issued while another live link is
    bound to its address, so a repeated re-send makes one replacement. The raw token is never persisted nor written to
    the audit log.
    """
    _require_admin(current_user)
    # The invite's own cohort and address are checked in the unit, before anything is revoked (prepare_reissue).
    if not (legal_readiness_service.is_collection_available() or legal_readiness_service.is_invited_cohort_available()):
        raise HTTPException(status_code=503, detail=legal_readiness_service.COLLECTION_UNAVAILABLE_MESSAGE)
    expires_in_hours = payload.expires_in_hours if payload else None
    requested = payload.send_email if payload else None
    permission = payload.permission.basis() if payload and payload.permission else None
    admin_id, admin_email = current_user.id, current_user.email

    def reissue() -> invite_delivery_service.PreparedInvite:
        try:
            # Inspect the existing binding before reissue can revoke the old link: with no answer in the request, a
            # bound invite's replacement is emailed, so it needs email readiness before anything is revoked.
            emailed = requested if requested is not None else invite_service.invite_has_delivery_recipient(db, invite_id)
            if emailed and not legal_readiness_service.is_invitation_email_available():
                raise HTTPException(status_code=503, detail=legal_readiness_service.INVITATION_EMAIL_UNAVAILABLE_MESSAGE)
            return invite_delivery_service.prepare_reissue(
                db,
                invite_id,
                created_by=admin_id,
                expires_in_hours=expires_in_hours,
                send_email=emailed,
                permission=permission,
            )
        finally:
            filing_list_service.release_request_session(db)

    try:
        prepared = await run_in_threadpool(reissue)
    except _MAIL_REFUSALS as exc:
        raise _mail_refusal(exc) from None
    issued = prepared.issued
    delivery_status: Optional[str] = None
    if prepared.delivery_id is not None:
        outcome = await invite_delivery_service.deliver(prepared)
        delivery_status = await run_in_threadpool(_record_outcome, db, prepared.delivery_id, outcome)
    emailed = delivery_status in invite_delivery_service.PROVIDER_TOOK

    logger.info("Admin %s resent invite %s as %s", admin_id, invite_id, issued["id"])

    def audit() -> None:
        # As the mint's: a unit of its own after the mail (E171).
        try:
            audit_service.create_audit_log(
                db,
                action="invite_resent",
                user_id=admin_id,
                user_email=admin_email,
                entity_type="invite",
                entity_id=str(issued["id"]),
                details={
                    "revoked_invite_id": invite_id,
                    "cohort": issued["cohort"],
                    "emailed": emailed,
                    "delivery_status": delivery_status,
                },
            )
        except Exception:
            logger.warning("Failed to write audit log for invite_resent", exc_info=True)
        finally:
            filing_list_service.release_request_session(db)

    await run_in_threadpool(audit)
    return ResendInviteResponse(**issued, emailed=emailed, delivery_status=delivery_status, revoked_invite_id=invite_id)


def _feedback_item(row: Feedback, user_email: Optional[str], attachments: list | None = None) -> dict:
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
        "attachment_count": len(attachments or []),
        "attachments": attachments or [],
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

    def feedback_list() -> dict:
        try:
            rows = admin_feedback_service.list_feedback(db, feedback_status=status, feedback_type=type)
            attachments = admin_feedback_service.attachment_metadata(db, [row.id for row, _ in rows])
            return {"feedback": [_feedback_item(row, email, attachments[row.id]) for row, email in rows]}
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(feedback_list)


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
    new_status = payload.status
    admin_id, admin_email = current_user.id, current_user.email

    def set_status() -> dict:
        try:
            feedback = admin_feedback_service.set_feedback_status(db, feedback_id, new_status)
            if not feedback:
                raise HTTPException(status_code=404, detail="Feedback not found")

            logger.info("Admin %s set feedback %s status to %s", admin_id, feedback_id, new_status)

            try:
                audit_service.create_audit_log(
                    db,
                    action="feedback_status_changed",
                    user_id=admin_id,
                    user_email=admin_email,
                    entity_type="feedback",
                    entity_id=str(feedback_id),
                    details={"status": new_status},
                )
            except Exception:
                logger.warning("Failed to write audit log for feedback_status_changed", exc_info=True)

            user_email = admin_feedback_service.submitter_email(db, feedback)
            attachments = admin_feedback_service.attachment_metadata(db, [feedback.id])
            return _feedback_item(feedback, user_email, attachments[feedback.id])
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(set_status)


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

    def delete_summary() -> bool:
        try:
            return admin_filing_service.delete_filing_summary(db, filing_id, actor=current_user)
        except admin_filing_service.FilingNotFoundError:
            raise HTTPException(status_code=404, detail="Filing not found")
        finally:
            filing_list_service.release_request_session(db)

    summary_deleted = await run_in_threadpool(delete_summary)

    return {
        "message": f"Summary deleted for filing {filing_id}",
        "filing_id": filing_id,
        "summary_deleted": summary_deleted
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
    admin_id = current_user.id

    def clear_xbrl() -> bool:
        try:
            return admin_filing_service.clear_filing_xbrl(db, filing_id)
        except admin_filing_service.FilingNotFoundError:
            raise HTTPException(status_code=404, detail="Filing not found")
        finally:
            filing_list_service.release_request_session(db)

    had_xbrl = await run_in_threadpool(clear_xbrl)
    logger.info(f"Admin {admin_id} cleared XBRL data for filing {filing_id}")

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
    admin_id = current_user.id

    def reset() -> dict[str, bool]:
        try:
            return admin_filing_service.reset_filing(db, filing_id)
        except admin_filing_service.FilingNotFoundError:
            raise HTTPException(status_code=404, detail="Filing not found")
        finally:
            filing_list_service.release_request_session(db)

    deleted = await run_in_threadpool(reset)
    logger.info(f"Admin {admin_id} reset filing {filing_id}: {deleted}")

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

    def audit() -> tuple[int, list[dict]]:
        try:
            return admin_filing_service.audit_stale_xbrl(db, year_threshold=year_threshold)
        finally:
            filing_list_service.release_request_session(db)

    total_filings_with_xbrl, stale_filings = await run_in_threadpool(audit)

    return {
        "total_filings_with_xbrl": total_filings_with_xbrl,
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
    admin_id = current_user.id

    def bulk_reset() -> list[dict]:
        try:
            return admin_filing_service.bulk_reset_stale_xbrl(
                db, year_threshold=year_threshold, dry_run=dry_run, actor=current_user
            )
        finally:
            filing_list_service.release_request_session(db)

    affected_filings = await run_in_threadpool(bulk_reset)

    if not dry_run:
        logger.info(f"Admin {admin_id} bulk-reset {len(affected_filings)} filings with stale XBRL data")

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
    admin_id, admin_email = current_user.id, getattr(current_user, "email", None)

    def reset_summaries() -> admin_summary_service.ResetAllPlan:
        try:
            plan = admin_summary_service.select_reset_candidates(
                db, filing_type=filing_type, include_saved=include_saved, for_delete=not dry_run
            )
            if not dry_run and plan.delete_ids:
                admin_summary_service.delete_summaries(db, plan)
                audit_service.create_audit_log(
                    db=db,
                    action="summaries_bulk_reset",
                    user_id=admin_id,
                    user_email=admin_email,
                    entity_type="summaries",
                    details={
                        "filing_type": filing_type,
                        "include_saved": include_saved,
                        "deleted_count": len(plan.delete_ids),
                        "skipped_saved_count": len(plan.skipped_saved),
                    },
                    status="success",
                )
            return plan
        finally:
            filing_list_service.release_request_session(db)

    plan = await run_in_threadpool(reset_summaries)
    delete_ids = plan.delete_ids
    skipped_saved = plan.skipped_saved

    if not dry_run and delete_ids:
        logger.info(
            "Admin %s bulk-reset %d summaries (filing_type=%s, include_saved=%s); skipped %d saved",
            admin_id, len(delete_ids), filing_type, include_saved, len(skipped_saved),
        )

    return {
        "dry_run": dry_run,
        "filing_type": filing_type,
        "include_saved": include_saved,
        "total_matched": plan.total_matched,
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


# Hard ceiling on rows regenerated per refresh-stale call. Large backlogs = repeated calls / a job.
_REFRESH_STALE_MAX_BATCH = 10
# The path's request timeout in main.py's table, in place of its 30 s default: a real run generates its batch in its
# request, so it needs minutes. It stays inside the service's Cloud Run request timeout (the deploy's --timeout=600), so
# the middleware's 504, with its CORS headers, comes before Cloud Run ends the request.
REFRESH_STALE_TIMEOUT_SECONDS = 570.0
# What one generation is allowed: the pipeline's 120 s backstop (PIPELINE_TIMEOUT_SECONDS), and a minute for its setup
# before it and its cleanup after it. An allowance, not a bound: while durable tasks are on, the cleanup waits for its
# worker threads with no timeout of its own (request_work.RequestWork.drain), so a generation can outlast it.
_REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS = PIPELINE_TIMEOUT_SECONDS + 60.0
# A run starts no generation later than this after its route begins, so the last one it starts has its allowance, and
# 40 s are left for the work outside it: the auth lookup before the route, and the last stamp re-read and the audit row
# after the batch, three checkouts that each wait at most DB_POOL_TIMEOUT's 10 s, and ten seconds for their queries. An
# estimate, as the allowance is: a checkout that must also connect (DB_CONNECT_TIMEOUT) can take longer. What it does
# not start, it reports deferred. A generation started near this bound that outlasts its allowance can take the run
# past the timeout: it answers 504, and that generation's tail, its re-read and the audit row finish after the
# response; the budget has passed, so no other generation starts.
_REFRESH_STALE_START_BY_SECONDS = REFRESH_STALE_TIMEOUT_SECONDS - _REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS - 40.0


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

    **Bounded, synchronous small batch.** A real run is hard-capped at ``_REFRESH_STALE_MAX_BATCH``
    rows and generates sequentially in the request, which keeps the Cloud Run request's CPU allocated
    (FastAPI ``BackgroundTasks`` would run under post-response CPU throttling, which the deploy sets
    with ``--cpu-throttling`` while durable tasks are on, and could be cut short). ``main.py``'s
    request-timeout table gives this path ``REFRESH_STALE_TIMEOUT_SECONDS`` (570 s, inside the
    service's 600 s), and a run starts no generation more than ``_REFRESH_STALE_START_BY_SECONDS``
    (350 s) after the route begins. That leaves the last one it starts its allowance (the pipeline's
    120 s backstop, and a minute for its setup and cleanup) and 40 s for the work around the batch.
    The candidates it does not start are reported ``deferred``: still stale, and a later call may
    select them. The allowance is not a bound, since while durable tasks are on a generation's
    cleanup waits for its worker threads: one started near the bound that outlasts it can take the
    run past the timeout, which then answers 504, and that generation's tail, its stamp re-read and
    the audit row finish after the response, under that throttling, with only the audit row's counts
    kept. It is NOT a whole-corpus backfill. Drain a large backlog by calling repeatedly (the op is
    idempotent + keep-better-gated) or with the job-side drain (``scripts/refresh_stale_summaries.py``).

    ``dry_run`` (default) reports the full ``stale_total`` without regenerating — the admin staleness
    count — while ``batch_limit`` reflects the clamped per-call ceiling. Candidates are sampled at
    random (``admin_summary_service.select_stale_candidates``).

    No pooled connection is held while a generation runs (E171): the candidates are read and the
    request's session released in one thread-pool unit, and the service re-reads each stamp and writes
    the audit row in short sessions of its own.

    Args:
        schema_version_lt: Refresh rows whose ``schema_version`` is NULL or below this. Omit to
            refresh everything stale vs the current schema+prompt version.
        filing_type: Optional form filter (e.g. "10-K", "10-Q").
        limit: Rows to regenerate this call, clamped to [1, _REFRESH_STALE_MAX_BATCH].
        dry_run: If True (default), only report the stale candidates — regenerate nothing.
    """
    _require_admin(current_user)
    # The run's time budget starts with the route, so the candidate read is inside it.
    start_by = time.monotonic() + _REFRESH_STALE_START_BY_SECONDS
    limit = max(1, min(limit, _REFRESH_STALE_MAX_BATCH))
    # After the release the admin is detached: read what the later work needs first.
    admin_id, admin_email = current_user.id, getattr(current_user, "email", None)

    def candidates() -> tuple[int, list[int]]:
        try:
            return admin_summary_service.select_stale_candidates(
                db, schema_version_lt=schema_version_lt, filing_type=filing_type, limit=limit
            )
        finally:
            filing_list_service.release_request_session(db)

    stale_total, candidate_filing_ids = await run_in_threadpool(candidates)

    # Per-filing outcomes (see admin_summary_service.regenerate_in_place); a dry run regenerates nothing.
    updated: list[int] = []
    kept_by_gate: list[int] = []
    failed: list[int] = []
    deferred: list[int] = []
    if not dry_run and candidate_filing_ids:
        updated, kept_by_gate, failed, deferred = await admin_summary_service.regenerate_in_place(
            candidate_filing_ids,
            actor_id=admin_id,
            actor_email=admin_email,
            filing_type=filing_type,
            schema_version_lt=schema_version_lt,
            stale_total=stale_total,
            start_by=start_by,
            clock=time.monotonic,  # the clock its deadline was set on
        )
        logger.info(
            "Admin %s refresh-stale: updated %d, kept-by-gate %d, failed %d, deferred %d of %d stale (filing_type=%s)",
            admin_id, len(updated), len(kept_by_gate), len(failed), len(deferred), stale_total, filing_type,
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
        # Not started: the run's time budget had passed. They remain stale for a later call.
        "deferred_count": len(deferred),
        "deferred_filing_ids": deferred,
        "message": (
            f"{stale_total} stale summaries"
            f"{f' of type {filing_type}' if filing_type else ''}; "
            + (
                f"would refresh up to {len(candidate_filing_ids)} in place (bookmarks preserved)."
                if dry_run
                else f"updated {len(updated)} in place, {len(kept_by_gate)} kept by the "
                f"keep-better gate (still stale), {len(failed)} failed, {len(deferred)} deferred "
                "to a later call (time budget)."
            )
        ),
    }
