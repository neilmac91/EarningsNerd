"""Durable ownership and usage receipt for one filing's shared summary work.

There is one row per filing, not one row per prompt version: a new version cannot
race an old version's result promotion. Generation and lease tokens fence stale tasks.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class SummaryJob(Base):
    __tablename__ = "earningsnerd_summary_jobs"

    id = Column(String(32), primary_key=True)
    filing_id = Column(Integer, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, unique=True)
    generation = Column(Integer, nullable=False, default=1)
    prompt_version = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    system_funded = Column(Boolean, nullable=False, default=False)
    force = Column(Boolean, nullable=False, default=False)
    lease_token = Column(String(32), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False)
    last_dispatched_at = Column(DateTime(timezone=True), nullable=True)
    dispatch_token = Column(String(32), nullable=False)
    stage = Column(String(30), nullable=False, default="queued")
    error_code = Column(String(60), nullable=True)
    summary_id = Column(Integer, nullable=True)
    reservation_token = Column(String(36), nullable=True)
    charge_state = Column(String(20), nullable=False, default="unreserved")
    charge_month = Column(String(7), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
