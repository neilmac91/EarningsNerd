from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import os

from app.database import get_db
from app.models import User, UserSearch, SavedSummary, UserUsage, Watchlist
from app.routers.auth import get_current_user
from app.services.audit_service import log_user_deletion, log_data_export

router = APIRouter()
logger = logging.getLogger(__name__)

# Optional imports for third-party services
try:
    import stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe not available - install stripe package for subscription cancellation")

try:
    from posthog import Posthog
    posthog_client = Posthog(
        project_api_key=os.getenv("POSTHOG_API_KEY"),
        host=os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
    ) if os.getenv("POSTHOG_API_KEY") else None
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
        # Collect profile data
        profile_data = {
            "user_id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "is_active": current_user.is_active,
            "is_pro": current_user.is_pro,
            "stripe_customer_id": current_user.stripe_customer_id,
            "stripe_subscription_id": current_user.stripe_subscription_id,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
        }

        # Collect search history
        searches = db.query(UserSearch).filter(UserSearch.user_id == current_user.id).all()
        searches_data = [
            {
                "id": search.id,
                "query": search.query,
                "company_id": search.company_id,
                "created_at": search.created_at.isoformat() if search.created_at else None,
            }
            for search in searches
        ]

        # Collect saved summaries
        saved_summaries = db.query(SavedSummary).filter(SavedSummary.user_id == current_user.id).all()
        saved_summaries_data = [
            {
                "id": summary.id,
                "summary_id": summary.summary_id,
                "notes": summary.notes,
                "created_at": summary.created_at.isoformat() if summary.created_at else None,
            }
            for summary in saved_summaries
        ]

        # Collect watchlist
        watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).all()
        watchlist_data = [
            {
                "id": item.id,
                "company_id": item.company_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in watchlist
        ]

        # Collect usage data
        usage = db.query(UserUsage).filter(UserUsage.user_id == current_user.id).all()
        usage_data = [
            {
                "id": usage_item.id,
                "month": usage_item.month,
                "summary_count": usage_item.summary_count,
                "created_at": usage_item.created_at.isoformat() if usage_item.created_at else None,
                "updated_at": usage_item.updated_at.isoformat() if usage_item.updated_at else None,
            }
            for usage_item in usage
        ]

        # Compile export
        export_data = {
            "profile": profile_data,
            "searches": searches_data,
            "saved_summaries": saved_summaries_data,
            "watchlist": watchlist_data,
            "usage": usage_data,
            "export_timestamp": datetime.utcnow().isoformat(),
        }

        logger.info(f"User data export completed for user {current_user.id}")

        # Create audit log entry
        log_data_export(db, current_user.id, current_user.email)

        return JSONResponse(
            content=export_data,
            headers={
                "Content-Disposition": f'attachment; filename="earningsnerd_data_export_{current_user.id}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json"'
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
                # PostHog GDPR deletion - sends delete event
                posthog_client.capture(
                    distinct_id=str(user_id),
                    event='$delete',
                    properties={
                        'email': user_email,
                        'deletion_timestamp': datetime.utcnow().isoformat()
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
        db.delete(current_user)
        db.commit()

        # Clear authentication cookie
        if response:
            response.delete_cookie(
                key="auth_token",  # Match your cookie name from settings
                path="/",
            )

        logger.info(
            f"USER DELETION COMPLETED: User {user_id} successfully deleted. "
            f"Third-party deletion results: {deletion_results}"
        )

        # TODO: Send final confirmation email to user_email
        # (email service implementation needed)

        return {
            "status": "success",
            "message": "Your account and all associated data have been permanently deleted.",
            "deleted_at": datetime.utcnow().isoformat(),
            "third_party_deletions": deletion_results
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user account {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please contact support."
        )

