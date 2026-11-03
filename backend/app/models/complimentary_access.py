"""The complimentary Pro grant ledger (PB-02, the private beta): which accounts' Pro an operator granted.

The plan never comes from this table. ``entitlements.get_plan`` resolves an account with no usable
``Subscription`` row as Pro while ``User.is_pro`` is True, and a grant sets that flag for an account no
billing state owns. This row records that the grant set it, so a revoke clears only a Pro the grant set
(never a paid account's), Billing can say the access is complimentary, and the operator command can
hold the cohort to its cap and stay idempotent. ``review_on`` is the operator's review or end date:
nothing expires on it (``docs/ops/complimentary-access.md``, "End date").

One row per account: re-granting a revoked account reopens its row. ``audit_logs`` keeps every grant
and revoke, with the account's state before and after, and survives the account's deletion; this row is
deleted with the account.
"""
from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class ComplimentaryAccessGrant(Base):
    __tablename__ = "earningsnerd_complimentary_access_grants"
    __table_args__ = (
        # A revocation records when, by whom and why together, or not at all.
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by IS NULL AND revoke_reason IS NULL)"
            " OR (revoked_at IS NOT NULL AND revoked_by IS NOT NULL AND revoke_reason IS NOT NULL)",
            name="ck_earningsnerd_complimentary_access_grants_revocation",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    cohort = Column(String(64), nullable=False)
    reason = Column(String(200), nullable=False)
    review_on = Column(Date, nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=False)
    # The operator's account as "account:<id>", kept as text so the record outlives that account.
    granted_by = Column(String(64), nullable=False)
    # SHA-256 of the private manifest the grant was applied from (its canonical JSON).
    manifest_sha256 = Column(String(64), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(64), nullable=True)
    revoke_reason = Column(String(200), nullable=True)

    user = relationship("User", back_populates="complimentary_access_grant")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
