"""Observed invoice allocations, not a balance, entitlement source, or accounting ledger."""
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.datetimes import utcnow


class BillingPayment(Base):
    __tablename__ = "earningsnerd_billing_payments"
    __table_args__ = (
        Index("ix_billing_payments_user_paid", "user_id", "paid_at"),
        Index("ix_billing_payments_mode_paid", "livemode", "paid_at"),
    )

    stripe_payment_id = Column(String(255), primary_key=True)
    livemode = Column(Boolean, primary_key=True)
    stripe_invoice_id = Column(String(255), nullable=False)
    source_event_id = Column(String(255), nullable=False)
    source_api_version = Column(String(80))
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    payment_type = Column(String(80), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    subscription_invoice = Column(Boolean, nullable=False)
    # Follow the existing Subscription erasure policy; do not retain a detached user history.
    user_id = Column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    attribution = Column(String(40), nullable=False)
    # These identifiers are retained only for an unambiguously attributed account.
    stripe_customer_id = Column(String(255))
    stripe_subscription_id = Column(String(255))
    is_beta_observed = Column(Boolean)
    invite_cohort_observed = Column(String(64))
    billing_cycle = Column(String(20))

    user = relationship("User", back_populates="billing_payments")
