"""Append-only verified source manifests; source bodies remain in private object storage."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class FilingSourceBundle(Base):
    __tablename__ = "earningsnerd_filing_source_bundles"
    __table_args__ = (
        CheckConstraint("member_count BETWEEN 1 AND 4", name="ck_filing_source_member_count"),
        CheckConstraint("byte_length BETWEEN 1 AND 33554432", name="ck_filing_source_bundle_bytes"),
    )

    id = Column(String(64), primary_key=True)
    identity_sha256 = Column(String(64), nullable=False, unique=True)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=False, index=True)
    cik = Column(String(20), nullable=False)
    accession = Column(String(18), nullable=False)
    filing_type = Column(String(10), nullable=False)
    primary_filename = Column(String(255), nullable=False)
    schema_version = Column(Integer, nullable=False)
    selection_version = Column(String(60), nullable=False)
    member_count = Column(Integer, nullable=False)
    byte_length = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class FilingSourceMember(Base):
    __tablename__ = "earningsnerd_filing_source_members"
    __table_args__ = (
        UniqueConstraint("bundle_id", "filename", name="uq_filing_source_member_filename"),
        CheckConstraint("ordinal BETWEEN 0 AND 3", name="ck_filing_source_member_ordinal"),
        CheckConstraint("byte_length BETWEEN 1 AND 33554432", name="ck_filing_source_member_bytes"),
        CheckConstraint("role IN ('primary', 'exhibit')", name="ck_filing_source_member_role"),
    )

    bundle_id = Column(String(64), ForeignKey("earningsnerd_filing_source_bundles.id"), primary_key=True)
    ordinal = Column(Integer, primary_key=True)
    role = Column(String(10), nullable=False)
    filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False)
    byte_length = Column(Integer, nullable=False)
    representation = Column(String(60), nullable=False)
    content_type = Column(String(160), nullable=False)
    content_encoding = Column(String(20), nullable=False)
    storage_generation = Column(String(20), nullable=False)


class FilingSourceExtraction(Base):
    __tablename__ = "earningsnerd_filing_source_extractions"
    __table_args__ = (
        UniqueConstraint("bundle_id", "decoder_version", "extractor_version", name="uq_filing_source_extraction_version"),
        CheckConstraint("text_bytes BETWEEN 1 AND 134217728", name="ck_filing_source_extraction_bytes"),
    )

    id = Column(String(64), primary_key=True)
    bundle_id = Column(String(64), ForeignKey("earningsnerd_filing_source_bundles.id"), nullable=False)
    decoder_version = Column(String(60), nullable=False)
    extractor_version = Column(String(60), nullable=False)
    text_sha256 = Column(String(64), nullable=False)
    text_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
