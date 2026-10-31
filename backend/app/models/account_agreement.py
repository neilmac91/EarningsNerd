"""Minimal evidence of the account holder's own signup confirmations; no inferred legacy assent."""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class AccountAgreement(Base):
    __tablename__ = "account_agreements"
    __table_args__ = (
        CheckConstraint("adult_eligible = true AND terms_accepted = true", name="ck_account_agreements_affirmative"),
        CheckConstraint("source IN ('password', 'google', 'apple')", name="ck_account_agreements_source"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    adult_eligible = Column(Boolean, nullable=False)
    terms_accepted = Column(Boolean, nullable=False)
    terms_version = Column(String(32), nullable=False)
    eligibility_version = Column(String(32), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(16), nullable=False)

    user = relationship("User", back_populates="account_agreements")
