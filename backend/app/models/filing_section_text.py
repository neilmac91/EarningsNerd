"""Per-filing section text (Item 1A today) for the "what changed" wording diff.

One row per (filing, section). The text is the filing's own, as edgartools' HTML parser returns
it from the primary document the app fetched (CLAUDE.md rules 2 and 5); nothing model-authored
is stored here. ``status`` records what the extractor found (``ok`` with text, ``missing`` when
the document has no such section, ``oversize`` when the text exceeds the configured cap, ``failed``
on a fetch/parse error with its ``error_type``); ``extractor_version`` lets a later extractor
re-run only rows it would change. The ``diff_*`` columns cache the comparison summary against the
prior same-form filing (counts only, never the items) so lists can sort and filter without
recomputing; ``filing_section_service`` refreshes them when either side is (re)extracted.

Existing databases get this table from ``migrations/20261012_filing_section_text.sql``; fresh
ones from ``create_all``. Deliberately not the legacy ``filing_content_cache.markdown_content``
column (no writer, no versioning, no status).
"""
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class FilingSectionText(Base):
    __tablename__ = "filing_section_text"
    __table_args__ = (
        UniqueConstraint("filing_id", "section", name="uq_filing_section_text_filing_section"),
        Index("ix_filing_section_text_status_extracted", "status", "extracted_at"),
    )

    id = Column(Integer, primary_key=True)
    filing_id = Column(Integer, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(32), nullable=False)
    extractor_version = Column(SmallInteger, nullable=False)
    status = Column(String(16), nullable=False)
    text = Column(Text, nullable=True)
    char_count = Column(Integer, nullable=False, default=0, server_default="0")
    paragraph_count = Column(Integer, nullable=False, default=0, server_default="0")
    sha256 = Column(String(64), nullable=True)
    # A 10-Q Item 1A that only points at the 10-K ("no material changes"): compared like any other
    # text, but a client labels it instead of reading "0 changes" as a restated section.
    reference_only = Column(Boolean, nullable=False, default=False, server_default="0")
    detection_method = Column(String(32), nullable=True)
    confidence = Column(Float, nullable=True)
    error_type = Column(String(120), nullable=True)
    # Cached comparison against the prior same-form filing with an ``ok`` row (summary only).
    diff_prior_filing_id = Column(Integer, ForeignKey("filings.id", ondelete="SET NULL"), nullable=True)
    diff_engine_version = Column(SmallInteger, nullable=True)
    diff_summary = Column(JSON, nullable=True)
    diff_computed_at = Column(DateTime(timezone=True), nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    filing = relationship("Filing", foreign_keys=[filing_id])
