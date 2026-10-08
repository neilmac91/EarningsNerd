from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.utils.datetimes import utcnow
import logging

from app.config import settings
from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user, _clear_auth_cookie, _clear_refresh_cookie
# Module imports, not function imports: the service functions stay patchable at their home, and no
# handler below can shadow a service function of the same name.
from app.services import user_account_service, user_data_export_service, user_notification_feed_service
from app.services.audit_service import log_user_deletion, log_data_export
from app.services.entitlements import get_entitlements
from app.services.notification_service import (
    apply_preference_update,
    get_or_create_preferences,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Optional imports for third-party services
try:
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe not available - install stripe package for subscription cancellation")

try:
    from posthog import Posthog
    posthog_client = Posthog(
        project_api_key=settings.POSTHOG_API_KEY,
        host=settings.POSTHOG_HOST
    ) if settings.POSTHOG_API_KEY else None
    POSTHOG_AVAILABLE = posthog_client is not None
except ImportError:
    POSTHOG_AVAILABLE = False
    posthog_client = None
    logger.warning("PostHog not available - install posthog package for analytics deletion")

try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry SDK not available - install sentry-sdk for error tracking cleanup")


class UserDataExport(BaseModel):
    """User data export model"""
    profile: Dict[str, Any]
    searches: List[Dict[str, Any]]
    saved_summaries: List[Dict[str, Any]]
    watchlist: List[Dict[str, Any]]
    usage: List[Dict[str, Any]]
    billing_payments: List[Dict[str, Any]]
    export_timestamp: datetime


@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get user profile"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_pro": current_user.is_pro,
        "created_at": current_user.created_at
    }


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 100:
            raise ValueError("Name must be at most 100 characters.")
        return value or None  # empty string clears the name


@router.patch("/me")
async def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update editable profile fields (currently the display name)."""
    data = payload.model_dump(exclude_unset=True)
    user_account_service.apply_profile_update(db, current_user, data)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_pro": current_user.is_pro,
    }


class NotificationPreferencesResponse(BaseModel):
    notify_10k: bool
    notify_10q: bool
    notify_8k: bool
    # FPI alerts (Phase 5): 20-F/40-F annual (free) and 6-K interim (free, digest-only).
    notify_20f: bool
    notify_6k: bool
    channel: str
    digest: str
    realtime: bool
    # Effective gating so the UI can render Pro-only toggles as locked rather than guessing.
    realtime_available: bool
    eightk_available: bool

    class Config:
        from_attributes = True


class NotificationPreferencesUpdate(BaseModel):
    notify_10k: Optional[bool] = None
    notify_10q: Optional[bool] = None
    notify_8k: Optional[bool] = None
    notify_20f: Optional[bool] = None
    notify_6k: Optional[bool] = None
    channel: Optional[str] = None
    digest: Optional[str] = None
    realtime: Optional[bool] = None


def _prefs_response(prefs, ent) -> NotificationPreferencesResponse:
    return NotificationPreferencesResponse(
        notify_10k=prefs.notify_10k,
        notify_10q=prefs.notify_10q,
        notify_8k=prefs.notify_8k,
        notify_20f=prefs.notify_20f,
        notify_6k=prefs.notify_6k,
        channel=prefs.channel,
        digest=prefs.digest,
        realtime=prefs.realtime,
        realtime_available=ent.realtime_alerts,
        eightk_available=ent.eightk_coverage,
    )


@router.get("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's new-filing alert preferences (creating defaults if none exist)."""
    prefs = get_or_create_preferences(db, current_user.id)
    return _prefs_response(prefs, get_entitlements(current_user))


@router.put("/me/notification-preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    update: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update alert preferences.

    Pro-gated toggles (``realtime``, ``notify_8k``) are accepted but **coerced off** for non-Pro
    users (rather than erroring), so the frontend can show them as locked Pro upsells.
    """
    prefs = get_or_create_preferences(db, current_user.id, commit=False)

    VALID_CHANNELS = {"email", "in_app"}
    VALID_DIGESTS = {"immediate", "daily", "weekly"}
    data = update.model_dump(exclude_unset=True)
    if "channel" in data and data["channel"] not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"channel must be one of {sorted(VALID_CHANNELS)}")
    if "digest" in data and data["digest"] not in VALID_DIGESTS:
        raise HTTPException(status_code=400, detail=f"digest must be one of {sorted(VALID_DIGESTS)}")

    ent = apply_preference_update(db, prefs, data, current_user)
    return _prefs_response(prefs, ent)


# --------------------------------------------------------------------------- in-app notifications

class NotificationItem(BaseModel):
    """One filing alert the user received, for the in-app bell. Sourced from notification_log."""
    id: int                     # notification_log row id
    filing_id: int
    ticker: str
    company_name: str
    filing_type: str
    filing_date: Optional[datetime] = None
    created_at: Optional[datetime] = None   # when the alert was logged
    read: bool                  # logged at/before the user last opened the bell

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    unread_count: int


def _notifications_payload(db: Session, user: User, limit: int) -> NotificationListResponse:
    """Recent filing alerts (newest first) + unread count for the in-app bell.

    The list is read and shaped before the count is taken, as one response.
    """
    entries = user_notification_feed_service.recent_notifications(db, user, limit)
    items = [
        NotificationItem(
            id=entry.id,
            filing_id=entry.filing_id,
            ticker=entry.ticker,
            company_name=entry.company_name,
            filing_type=entry.filing_type,
            filing_date=entry.filing_date,
            created_at=entry.created_at,
            read=entry.read,
        )
        for entry in entries
    ]
    return NotificationListResponse(
        items=items, unread_count=user_notification_feed_service.unread_count(db, user)
    )


@router.get("/me/notifications", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent filing alerts for the in-app bell, newest first, plus the unread count."""
    return _notifications_payload(db, current_user, limit)


@router.post("/me/notifications/seen", response_model=NotificationListResponse)
async def mark_notifications_seen(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the bell as opened (resets the unread count). Returns the now-read recent list.

    Fetch the real row via ``db.get`` and mutate it directly (rather than a bulk UPDATE) so the
    response is built from a fresh, in-session user — robust regardless of ``expire_on_commit`` — and
    so it works for the test stand-in (a non-session user) too.
    """
    user = user_notification_feed_service.mark_seen(db, current_user)
    return _notifications_payload(db, user, 20)


@router.get("/export")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export all user data for GDPR compliance (Right to Data Portability - Article 20)

    Returns all personal data associated with the user account in JSON format.
    """
    try:
        export_data = user_data_export_service.build_user_data_export(db, current_user)

        logger.info(f"User data export completed for user {current_user.id}")

        # Create audit log entry
        log_data_export(db, current_user.id, current_user.email)

        return JSONResponse(
            content=export_data,
            headers={
                "Content-Disposition": f'attachment; filename="earningsnerd_data_export_{current_user.id}_{utcnow().strftime("%Y%m%d_%H%M%S")}.json"'
            }
        )

    except Exception as e:
        logger.error(f"Error exporting user data for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data"
        )


@router.delete("/me")
async def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = None
):
    """
    Delete user account and all associated data (GDPR Right to Erasure - Article 17)

    This endpoint:
    1. Deletes all user data from the database (cascade delete)
    2. Logs the deletion for audit purposes
    3. Clears authentication cookie
    4. Returns success confirmation

    Note: Stripe customer data will be retained for 7 years per tax requirements.
    Users will receive a confirmation email before this endpoint should be called.
    """
    try:
        user_id = current_user.id
        user_email = current_user.email
        stripe_customer_id = current_user.stripe_customer_id

        # Log deletion for audit trail (before deleting user)
        logger.warning(
            f"USER DELETION: User {user_id} ({user_email}) account deletion initiated. "
            f"Stripe customer: {stripe_customer_id}"
        )

        # Delete from third-party services BEFORE deleting from database
        deletion_results = {
            "stripe": "skipped",
            "posthog": "skipped",
            "sentry": "skipped"
        }

        # 1. Cancel Stripe subscription if active
        if STRIPE_AVAILABLE and stripe_customer_id:
            try:
                # List all active subscriptions for this customer
                subscriptions = stripe.Subscription.list(customer=stripe_customer_id, status='active')
                for subscription in subscriptions.data:
                    stripe.Subscription.delete(subscription.id)
                    logger.info(f"Cancelled Stripe subscription {subscription.id} for user {user_id}")

                # Note: We do NOT delete the Stripe customer record (7-year tax retention requirement)
                # stripe.Customer.delete(stripe_customer_id)  # DO NOT DO THIS
                deletion_results["stripe"] = "subscriptions_cancelled"
                logger.info(f"Stripe subscriptions cancelled for user {user_id}, customer retained for tax compliance")
            except Exception as e:
                logger.error(f"Failed to cancel Stripe subscription for user {user_id}: {str(e)}")
                deletion_results["stripe"] = f"error: {str(e)}"

        # 2. Send deletion request to PostHog
        if POSTHOG_AVAILABLE and posthog_client:
            try:
                # PostHog GDPR deletion — keyed by distinct_id (user id). Do not echo the
                # email back as a property; the $delete event already targets this person.
                posthog_client.capture(
                    distinct_id=str(user_id),
                    event='$delete',
                    properties={
                        'deletion_timestamp': utcnow().isoformat()
                    }
                )
                posthog_client.flush()  # Ensure the event is sent immediately
                deletion_results["posthog"] = "deletion_requested"
                logger.info(f"PostHog deletion event sent for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send PostHog deletion for user {user_id}: {str(e)}")
                deletion_results["posthog"] = f"error: {str(e)}"

        # 3. Anonymize user in Sentry (Sentry doesn't support full deletion)
        if SENTRY_AVAILABLE:
            try:
                # Set user context to None to anonymize future events
                sentry_sdk.set_user(None)
                deletion_results["sentry"] = "anonymized"
                logger.info(f"Sentry user context cleared for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to anonymize Sentry user {user_id}: {str(e)}")
                deletion_results["sentry"] = f"error: {str(e)}"

        # Create audit log BEFORE deleting user (so we can still reference user_id)
        log_user_deletion(
            db=db,
            user_id=user_id,
            user_email=user_email,
            third_party_results=deletion_results
        )

        # Delete user from database (cascade delete will handle related records)
        user_account_service.delete_user(db, current_user)

        # Clear all session cookies (access + session-presence + refresh) using the same helpers
        # as logout. The previous code cleared a non-existent "auth_token" cookie, leaving the real
        # access and 30-day refresh cookies in place — a lingering refresh cookie could silently
        # restore the session of a just-deleted account.
        if response:
            _clear_auth_cookie(response)
            _clear_refresh_cookie(response)

        logger.info(
            f"USER DELETION COMPLETED: User {user_id} successfully deleted. "
            f"Third-party deletion results: {deletion_results}"
        )
        # Future: Send final confirmation email to user_email (requires email service integration)

        return {
            "status": "success",
            "message": "Your account and all associated data have been permanently deleted.",
            "deleted_at": utcnow().isoformat(),
            "third_party_deletions": deletion_results
        }

    except Exception as e:
        user_account_service.rollback_account_deletion(db)
        logger.error(f"Error deleting user account {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please contact support."
        )

