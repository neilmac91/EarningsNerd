"""Append-only audit history for explicitly applied quarterly data repairs."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.sql import func

from app.database import Base


class FinancialFactRevision(Base):
    __tablename__ = "financial_fact_revision"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(64), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    fact_id = Column(Integer, ForeignKey("financial_fact.id"), nullable=False)
    action = Column(String(16), nullable=False)
    calculation_version = Column(String(64), nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=False)
    reverts_revision_id = Column(Integer, ForeignKey("financial_fact_revision.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_financial_fact_revision_run_company", "run_id", "company_id"),
        Index("ix_financial_fact_revision_fact", "fact_id"),
    )
