"""Cached Multi-Period Analysis runs — dataset + AI narrative, keyed by company/mode/period range.

One row per (company, mode, period_key): the deterministic dataset snapshot it was generated from
(``dataset_json`` + its sha256 ``dataset_fingerprint``), the streamed narrative, and the resolved
citations. The stream endpoint re-serves a row instantly (no AI call, no meter) while the
fingerprint and ``prompt_version`` still match; new facts change the fingerprint and a prompt bump
invalidates fleet-wide, so no TTL is needed. Regeneration overwrites in place (the unique key), so
the row also gives PDF export and any future share-link a stable id.
"""
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class TrendAnalysis(Base):
    __tablename__ = "trend_analysis"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    mode = Column(String, nullable=False)  # "annual" | "quarterly"
    period_key = Column(String, nullable=False)  # canonical range, e.g. "FY2016..FY2025"
    prompt_version = Column(String, nullable=False)  # trend_analysis_service.PROMPT_VERSION
    dataset_fingerprint = Column(String, nullable=False)  # sha256 of the canonical dataset JSON
    dataset_json = Column(JSON, nullable=False)
    narrative_md = Column(Text, nullable=True)
    citations_json = Column(JSON, nullable=True)
    model = Column(String, nullable=True)  # AI model that wrote the narrative
    grounded = Column(Integer, nullable=False, default=0)  # resolved F# citation count
    # Who triggered the last (re)generation — analytics only, never an access gate (any Pro user
    # may re-serve any cached row).
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "mode", "period_key", name="uq_trend_analysis_key"),
    )
