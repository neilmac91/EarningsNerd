"""Admission reservations: a short PostgreSQL lease that holds one quota unit while work runs.

Completed-use counters (``user_usage``) are incremented atomically after generation (#729), but
admission used to be a plain read, so concurrent requests by one account could all pass the cap.
A reservation is written in the same serialized transaction as the admission decision and is
either converted (deleted together with the counter increment), released (deleted) or, if the
process dies, ignored once ``expires_at`` passes. Project-specific name: never adopt a
conventional table by accident (see lessons/ops-deploy-owned-state-needs-a-distinctive-name.md).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class UsageReservation(Base):
    __tablename__ = "earningsnerd_usage_reservations"
    __table_args__ = (
        Index("ix_earningsnerd_usage_reservations_scope", "user_id", "month", "kind", "expires_at"),
    )

    id = Column(Integer, primary_key=True)
    # Cascade on both layers: the ORM path (DELETE /api/users/me) and any Core/SQL delete of a
    # users row must take live and expired leases with it, never fail an account deletion.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    month = Column(String(7), nullable=False)  # "YYYY-MM", same bucket key as user_usage
    kind = Column(String(20), nullable=False)  # "summary" (Copilot/Analysis reserved for slice 2)
    token = Column(String(36), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="usage_reservations")
