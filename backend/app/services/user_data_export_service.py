"""GDPR data export (Art. 20): collect every personal record the account owns.

Read-only: the caller logs the export, writes the ``data_exported`` audit row and builds the
download response, so a failure here leaves nothing behind.
"""
from datetime import timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import BillingPayment, SavedSummary, User, UserSearch, UserUsage, Watchlist
from app.utils.datetimes import iso_z, utcnow


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
            # SQLite drops timezone metadata; both columns store UTC instants.
            "paid_at": iso_z(payment.paid_at.replace(tzinfo=timezone.utc) if payment.paid_at.tzinfo is None
                             else payment.paid_at.astimezone(timezone.utc)),
            "observed_at": iso_z(payment.observed_at.replace(tzinfo=timezone.utc) if payment.observed_at.tzinfo is None
                                 else payment.observed_at.astimezone(timezone.utc)),
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

    # Compile export
    export_data = {
        "profile": profile_data,
        "searches": searches_data,
        "saved_summaries": saved_summaries_data,
        "watchlist": watchlist_data,
        "usage": usage_data,
        "billing_payments": payments_data,
        "export_timestamp": utcnow().isoformat(),
    }
    return export_data
