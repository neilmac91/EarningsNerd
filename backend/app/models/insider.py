"""Insider activity (SEC Form 4) as stored, per accession, and the scan that fills it (ADR 0009).

Public SEC data about an issuer: none of these rows references a user or the ``filings`` table (a Form 4
accession also appears under its reporting owners, and ``filings`` holds each accession once). Project-specific
table names, as every deploy-owned table has (lessons/ops-deploy-owned-state-needs-a-distinctive-name.md). Fresh
databases get the schema from these models; production gets it from
``migrations/20261114_earningsnerd_insider_tables.sql``.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Index, Integer, String, UniqueConstraint

from app.database import Base


class InsiderFiling(Base):
    """One Form 4 in an issuer's listing: listed by a scan, then fetched and parsed once. A filing is immutable, so
    a row whose status is not ``listed`` is never fetched again. SEC lists a Form 4 under its issuer and under each
    reporting owner, and an owner can be a company with a scan of its own, so an accession has one row per issuer
    that listed it; only the row of the issuer the document names (``ok``) has trades."""

    __tablename__ = "earningsnerd_insider_filings"
    __table_args__ = (
        UniqueConstraint("issuer_cik", "accession", name="uq_earningsnerd_insider_filings_issuer_accession"),
        Index("ix_earningsnerd_insider_filings_issuer_status", "issuer_cik", "status"),
    )

    id = Column(Integer, primary_key=True)
    accession = Column(String(25), nullable=False)
    issuer_cik = Column(String(10), nullable=False)
    filed_date = Column(Date, nullable=True)
    primary_document = Column(String(255), nullable=True)
    # listed (known, not fetched yet) | ok | not_issuer (its document reports another issuer's shares) | no_xml |
    # not_found | failed
    status = Column(String(20), nullable=False)
    error_type = Column(String(60), nullable=True)
    parser_version = Column(Integer, nullable=True)
    attempted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class InsiderTransaction(Base):
    """One open-market trade parsed from a stored Form 4, in the shape the insider endpoint returns."""

    __tablename__ = "earningsnerd_insider_transactions"
    __table_args__ = (
        UniqueConstraint("accession", "ordinal", name="uq_earningsnerd_insider_transactions_accession_ordinal"),
        Index("ix_earningsnerd_insider_transactions_issuer_date", "issuer_cik", "transaction_date"),
    )

    id = Column(Integer, primary_key=True)
    accession = Column(String(25), nullable=False)
    ordinal = Column(Integer, nullable=False)
    issuer_cik = Column(String(10), nullable=False)
    insider_name = Column(String(255), nullable=True)
    insider_title = Column(String(255), nullable=True)
    is_director = Column(Boolean, nullable=True)
    is_officer = Column(Boolean, nullable=True)
    is_ten_pct_owner = Column(Boolean, nullable=True)
    ticker = Column(String(16), nullable=True)
    transaction_date = Column(Date, nullable=True)
    transaction_code = Column(String(4), nullable=True)
    transaction_label = Column(String(60), nullable=True)
    shares = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    value = Column(Float, nullable=True)
    acquired_disposed = Column(String(1), nullable=True)
    is_10b5_1 = Column(Boolean, nullable=True)
    filed_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class InsiderScan(Base):
    """One issuer's scan: what the endpoint reports, and the lease that keeps two steps from running at once."""

    __tablename__ = "earningsnerd_insider_scans"
    __table_args__ = (UniqueConstraint("issuer_cik", name="uq_earningsnerd_insider_scans_issuer_cik"),)

    id = Column(Integer, primary_key=True)
    issuer_cik = Column(String(10), nullable=False)
    # idle (nothing left to fetch) | scanning (filings still listed) | paused (SEC pushed back) | failed
    status = Column(String(20), nullable=False)
    lease_token = Column(String(32), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    last_listed_at = Column(DateTime(timezone=True), nullable=True)
    paused_until = Column(DateTime(timezone=True), nullable=True)
    pauses = Column(Integer, nullable=False, default=0, server_default="0")
    error_code = Column(String(60), nullable=True)
    steps = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
