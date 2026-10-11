"""GDPR data export (Art. 20): collect every personal record the account owns.

Read-only: the caller logs the export, writes the ``data_exported`` audit row and builds the
download response, so a failure here leaves nothing behind.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import BillingPayment, SavedSummary, User, UserSearch, UserUsage, Watchlist
from app.utils.datetimes import ensure_utc, iso_z, utcnow


def _utc_timestamp(value: datetime | None) -> str | None:
    """Preserve nulls and the instant; SQLite returns naive UTC, PostgreSQL can return offsets."""
    return iso_z(ensure_utc(value).astimezone(timezone.utc)) if value is not None else None


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
        "created_at": _utc_timestamp(current_user.created_at),
        "updated_at": _utc_timestamp(current_user.updated_at),
    }

    # Collect search history
    searches = db.query(UserSearch).filter(UserSearch.user_id == current_user.id).all()
    searches_data = [
        {
            "id": search.id,
            "query": search.query,
            "company_id": search.company_id,
            "created_at": _utc_timestamp(search.created_at),
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
            "created_at": _utc_timestamp(summary.created_at),
        }
        for summary in saved_summaries
    ]

    # Collect watchlist
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).all()
    watchlist_data = [
        {
            "id": item.id,
            "company_id": item.company_id,
            "created_at": _utc_timestamp(item.created_at),
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
            "created_at": _utc_timestamp(usage_item.created_at),
            "updated_at": _utc_timestamp(usage_item.updated_at),
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
            "paid_at": _utc_timestamp(payment.paid_at),
            "observed_at": _utc_timestamp(payment.observed_at),
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
        "export_timestamp": iso_z(utcnow()),
    }
    return export_data
