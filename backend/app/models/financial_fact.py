"""Normalized financial facts — the queryable shape behind cross-company peers + time-series.

`Filing.xbrl_data` is a per-filing JSON blob, which makes cross-company and multi-period queries
structurally impossible. `financial_fact` normalizes the standardized metrics we already extract into
one row per (company, concept, period), so peer comparison (P3/F3) and fundamentals time-series
(P3/F5) become a single indexed read.

Restatement-safe: a restated value arrives under a NEW accession with the SAME
(company, concept, period_end, fiscal_period, unit). Keeping `accession` in the identity lets the
original and restated rows coexist; a single `is_latest=True` row per (company, concept, period)
keeps reads a one-row lookup. Kept portable (plain String/Numeric/Date) for Postgres (prod) + SQLite
(tests), like the rest of the schema.
"""
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.sql import func

from app.database import Base


class FinancialFact(Base):
    __tablename__ = "financial_fact"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    # Nullable: backfill rows (companyfacts/FSDS) may precede a Filing row for that accession.
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=True)
    concept = Column(String, nullable=False)  # standardized concept, e.g. "revenue", "net_income"
    raw_tag = Column(String, nullable=True)  # as-reported us-gaap tag (audit trail)
    unit = Column(String, nullable=False)  # USD | USD/shares | shares | pure
    period_start = Column(Date, nullable=True)  # null for instant facts
    period_end = Column(Date, nullable=False, index=True)
    fiscal_year = Column(Integer, nullable=True)
    fiscal_period = Column(String, nullable=True)  # FY | Q1..Q4
    value = Column(Numeric, nullable=False)
    form = Column(String, nullable=True)  # 10-K | 10-Q
    accession = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="edgar_xbrl")  # edgar_xbrl|companyfacts|frames|fsds
    reconciled = Column(Boolean, nullable=False, default=False)
    is_latest = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "concept",
            "period_end",
            "fiscal_period",
            "unit",
            "accession",
            name="uq_financial_fact_identity",
        ),
        # Current-values-only partial indexes power the two hot read paths (peers + time-series).
        # The `WHERE` is Postgres-only; on SQLite SQLAlchemy emits a plain index, which is fine.
        Index("ix_financial_fact_peer", "concept", "period_end", postgresql_where=text("is_latest")),
        Index(
            "ix_financial_fact_series",
            "company_id",
            "concept",
            "period_end",
            postgresql_where=text("is_latest"),
        ),
    )
