"""GDPR data export (Art. 20): collect every personal record the account owns.

Read-only: the caller logs the export, writes the ``data_exported`` audit row and builds the
download response, so a failure here leaves nothing behind.

Every timestamp in the payload is one representation (F19): the instant in UTC, ISO 8601 with a ``Z``
suffix and its microseconds when it has any (``2026-07-06T10:52:35.123456Z``), or ``null`` where the
column holds none. ``_utc`` makes it from whatever the database hands back: SQLite reads a value naive,
PostgreSQL reads an aware column in the session's time zone, and a legacy column that a later model
change made aware can still be naive in an older database; a naive value is UTC, as every writer stores it.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import AccountAgreement, BillingPayment, SavedSummary, SectionReview, User, UserSearch, UserUsage, Watchlist
from app.models.feedback import Feedback, FeedbackAttachment
from app.utils.datetimes import ensure_utc, iso_z, utcnow


def _utc(value: Optional[datetime]) -> Optional[str]:
    """The export's one timestamp representation: the same instant in UTC as ``iso_z``, or ``None``."""
    return iso_z(ensure_utc(value).astimezone(timezone.utc)) if value is not None else None


def _feedback_export(db: Session, owner_id: int) -> list[dict[str, Any]]:
    """Retained reports and a private media manifest, never storage keys or image bytes."""
    now = utcnow()
    reports = db.query(Feedback).filter(Feedback.user_id == owner_id).order_by(Feedback.id).all()
    attachments = db.query(FeedbackAttachment).filter(
        FeedbackAttachment.owner_id == owner_id,
        FeedbackAttachment.feedback_id.is_not(None),
    ).order_by(FeedbackAttachment.created_at, FeedbackAttachment.id).all()
    by_report: dict[int, list[dict[str, Any]]] = {}
    for attachment in attachments:
        expired = attachment.expires_at is not None and ensure_utc(attachment.expires_at) <= now
        available = attachment.state == "available" and attachment.deleted_at is None and not expired
        item = {
            "id": attachment.id,
            "content_type": attachment.content_type,
            "width": attachment.width,
            "height": attachment.height,
            "byte_count": attachment.byte_count,
            "sha256": attachment.checksum,
            "created_at": _utc(attachment.created_at),
            "expires_at": _utc(attachment.expires_at),
            "status": "available" if available else "expired" if expired else "unavailable",
            "download_path": f"/api/feedback/attachments/{attachment.id}" if available else None,
        }
        by_report.setdefault(attachment.feedback_id, []).append(item)
    return [{
        "id": report.id,
        "type": report.type,
        "message": report.message,
        "page_url": report.page_url,
        "status": report.status,
        "created_at": _utc(report.created_at),
        "attachments": by_report.get(report.id, []),
    } for report in reports]


def build_user_data_export(db: Session, current_user: User) -> Dict[str, Any]:
    """The export payload, keys in wire order (profile ... export_timestamp)."""
    # Collect profile data
    profile_data = {
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "is_pro": current_user.is_pro,
        "stripe_customer_id": current_user.stripe_customer_id,
        "stripe_subscription_id": current_user.stripe_subscription_id,
        "created_at": _utc(current_user.created_at),
        "updated_at": _utc(current_user.updated_at),
    }

    # Collect search history
    searches = db.query(UserSearch).filter(UserSearch.user_id == current_user.id).all()
    searches_data = [
        {
            "id": search.id,
            "query": search.query,
            "company_id": search.company_id,
            "created_at": _utc(search.created_at),
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
            "created_at": _utc(summary.created_at),
        }
        for summary in saved_summaries
    ]

    # Collect watchlist
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).all()
    watchlist_data = [
        {
            "id": item.id,
            "company_id": item.company_id,
            "created_at": _utc(item.created_at),
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
            "created_at": _utc(usage_item.created_at),
            "updated_at": _utc(usage_item.updated_at),
        }
        for usage_item in usage
    ]

    # Export every retained observation owned by this account, across live/test modes.
    payments = db.query(BillingPayment).filter(BillingPayment.user_id == current_user.id).all()
    payments_data = [
        {
            "stripe_payment_id": payment.stripe_payment_id,
            "livemode": payment.livemode,
            "stripe_invoice_id": payment.stripe_invoice_id,
            "source_event_id": payment.source_event_id,
            "source_api_version": payment.source_api_version,
            "amount_minor": payment.amount_minor,
            "currency": payment.currency,
            "payment_type": payment.payment_type,
            "paid_at": _utc(payment.paid_at),
            "observed_at": _utc(payment.observed_at),
            "subscription_invoice": payment.subscription_invoice,
            "user_id": payment.user_id,
            "attribution": payment.attribution,
            "stripe_customer_id": payment.stripe_customer_id,
            "stripe_subscription_id": payment.stripe_subscription_id,
            "is_beta_observed": payment.is_beta_observed,
            "invite_cohort_observed": payment.invite_cohort_observed,
            "billing_cycle": payment.billing_cycle,
        }
        for payment in payments
    ]

    # The reader's reviews of filings' wording changes (labels per change, the frozen receipts).
    reviews = db.query(SectionReview).filter(SectionReview.user_id == current_user.id).all()
    reviews_data = [
        {
            "filing_id": review.filing_id,
            "section": review.section,
            "labels": review.labels,
            "engine_version": review.engine_version,
            "completed_at": _utc(review.completed_at),
            "receipt": review.receipt,
            "created_at": _utc(review.created_at),
            "updated_at": _utc(review.updated_at),
        }
        for review in reviews
    ]

    # Only recorded signup evidence: an older account with no confirmation exports an empty list.
    agreements = db.query(AccountAgreement).filter(AccountAgreement.user_id == current_user.id).all()
    agreements_data = [
        {
            "adult_eligible": agreement.adult_eligible,
            "terms_accepted": agreement.terms_accepted,
            "terms_version": agreement.terms_version,
            "eligibility_version": agreement.eligibility_version,
            "accepted_at": _utc(agreement.accepted_at),
            "source": agreement.source,
        }
        for agreement in agreements
    ]

    # Compile export
    export_data = {
        "profile": profile_data,
        "searches": searches_data,
        "saved_summaries": saved_summaries_data,
        "watchlist": watchlist_data,
        "usage": usage_data,
        "billing_payments": payments_data,
        "section_reviews": reviews_data,
        "account_agreements": agreements_data,
        "feedback": _feedback_export(db, current_user.id),
        "export_timestamp": _utc(utcnow()),
    }
    return export_data
