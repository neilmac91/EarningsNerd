from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.waitlist import WaitlistSignup
from app.models.contact import ContactSubmission
from app.models.audit_log import AuditLog


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_pro = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    searches = relationship("UserSearch", back_populates="user", cascade="all, delete-orphan")
    saved_summaries = relationship("SavedSummary", back_populates="user", cascade="all, delete-orphan")
    usage = relationship("UserUsage", back_populates="user", cascade="all, delete-orphan")
    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    cik = Column(String, unique=True, index=True, nullable=False)
    ticker = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    exchange = Column(String, nullable=True)
    sic = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    filings = relationship("Filing", back_populates="company")


class Watchlist(Base):
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="watchlist")
    company = relationship("Company")


class Filing(Base):
    __tablename__ = "filings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    accession_number = Column(String, unique=True, index=True, nullable=False)
    filing_type = Column(String, nullable=False)  # 10-K, 10-Q, etc.
    filing_date = Column(DateTime(timezone=True), nullable=False)
    period_end_date = Column(DateTime(timezone=True), nullable=True)
    document_url = Column(String, nullable=False)
    sec_url = Column(String, nullable=False)
    xbrl_data = Column(JSON, nullable=True)  # Store XBRL extracted data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    company = relationship("Company", back_populates="filings")
    summaries = relationship("Summary", back_populates="filing")
    content_cache = relationship(
        "FilingContentCache",
        back_populates="filing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    summary_progress = relationship(
        "SummaryGenerationProgress",
        back_populates="filing",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Summary(Base):
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=False)
    business_overview = Column(Text, nullable=True)
    financial_highlights = Column(JSON, nullable=True)  # Store structured data
    risk_factors = Column(JSON, nullable=True)  # Array of risk objects
    management_discussion = Column(Text, nullable=True)
    key_changes = Column(Text, nullable=True)
    raw_summary = Column(JSON, nullable=True)  # Full AI response
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    filing = relationship("Filing", back_populates="summaries")


class UserSearch(Base):
    __tablename__ = "user_searches"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="searches")


class SavedSummary(Base):
    __tablename__ = "saved_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    summary_id = Column(Integer, ForeignKey("summaries.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="saved_summaries")


class UserUsage(Base):
    __tablename__ = "user_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    month = Column(String, nullable=False, index=True)  # Format: "YYYY-MM"
    summary_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", back_populates="usage")


class SummaryGenerationProgress(Base):
    __tablename__ = "summary_generation_progress"

    filing_id = Column(Integer, ForeignKey("filings.id"), primary_key=True)
    stage = Column(String, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    elapsed_seconds = Column(Float, nullable=True)
    error = Column(String, nullable=True)
    section_coverage = Column(JSON, nullable=True)

    filing = relationship("Filing", back_populates="summary_progress")


class FilingContentCache(Base):
    __tablename__ = "filing_content_cache"

    filing_id = Column(Integer, ForeignKey("filings.id"), primary_key=True)
    critical_excerpt = Column(Text, nullable=True)
    sections_payload = Column(JSON, nullable=True)
    # Markdown content for AI consumption
    markdown_content = Column(Text, nullable=True)
    markdown_generated_at = Column(DateTime(timezone=True), nullable=True)
    markdown_sections = Column(JSON, nullable=True)  # List of sections extracted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    filing = relationship("Filing", back_populates="content_cache")


__all__ = [
    "Base",
    "Company",
    "ContactSubmission",
    "Filing",
    "FilingContentCache",
    "SavedSummary",
    "Summary",
    "SummaryGenerationProgress",
    "User",
    "UserSearch",
    "UserUsage",
    "Watchlist",
    "WaitlistSignup",
]
