import logging
from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, Boolean, ForeignKey, Float, JSON, event, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.waitlist import WaitlistSignup
from app.models.contact import ContactSubmission
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken
from app.models.subscription import Subscription, StripeEvent, ACTIVE_STATUSES
from app.models.notifications import NotificationPreferences, NotificationLog
from app.models.earnings import EarningsEvent, EarningsAlertLog
from app.models.financial_fact import FinancialFact
from app.models.notable_filing import NotableFiling
from app.models.trend_analysis import TrendAnalysis
from app.models.invite import InviteCode
from app.models.feedback import Feedback

logger = logging.getLogger(__name__)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Nullable: social-only accounts (Google/Apple) have no password
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_pro = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    # Closed-beta cohort flag, set server-side when a user registers with a valid invite. Drives the
    # 100%-off promo at checkout (so eligibility never depends on a client-supplied parameter).
    is_beta = Column(Boolean, default=False, nullable=False)
    # Lifetime "free taste" of the Pro Copilot (roadmap 2.2): a Free user gets a small lifetime
    # allowance of grounded "Ask this Filing" questions before the upsell. Lifetime, so it lives here
    # (one row per user) rather than on user_usage (which is monthly). Pro is unlimited via
    # entitlements and never touches this counter.
    copilot_free_taste_used = Column(Integer, default=0, server_default="0", nullable=False)
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    # Email verification (store SHA-256 hash of token, never the raw token)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String, nullable=True)
    email_verification_expires = Column(DateTime(timezone=True), nullable=True)
    # Password reset (store SHA-256 hash of token, never the raw token)
    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    # When the user last opened the in-app notification bell. Unread = notification_log rows newer
    # than this (or all rows if never opened). Avoids per-row read-state writes.
    notifications_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    searches = relationship("UserSearch", back_populates="user", cascade="all, delete-orphan")
    saved_summaries = relationship("SavedSummary", back_populates="user", cascade="all, delete-orphan")
    usage = relationship("UserUsage", back_populates="user", cascade="all, delete-orphan")
    watchlist = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    # 1:1 billing state. The webhook keeps both this row and the `is_pro` mirror in sync.
    subscription = relationship(
        "Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # New-filing alert preferences (1:1) + send/dedup log. Cascade so GDPR delete removes them.
    notification_preferences = relationship(
        "NotificationPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    notification_logs = relationship(
        "NotificationLog", back_populates="user", cascade="all, delete-orphan"
    )


class OAuthAccount(Base):
    """OAuth provider links for a user. One user may link multiple providers
    (Google, Apple), all pointing at the same integer users.id."""
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        # One provider identity maps to exactly one app account — enforced at the DB level (not just
        # in app logic) so concurrent OAuth callbacks for the same provider `sub` can't dup-link.
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)           # 'google' | 'apple'
    provider_account_id = Column(String, nullable=False)    # provider's 'sub' claim
    # Email from provider — may be a private relay address for Apple
    provider_email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="oauth_accounts")


class OAuthState(Base):
    """Short-lived state+nonce for OAuth flows that can't use SameSite cookies (Apple form_post).

    ``expires_at`` is stored as naive UTC to match the ``datetime.utcnow()`` convention used by
    RefreshToken — a tz-aware column compared against a naive value (or vice versa) raises
    ``TypeError: can't compare offset-naive and offset-aware datetimes`` because Postgres returns
    ``DateTime(timezone=True)`` tz-aware while SQLite returns it naive. Keeping both the column and
    the comparison naive UTC avoids that pitfall on every backend.
    """
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True)
    # unique=True already creates the index; no separate index=True needed.
    state = Column(String(64), unique=True, nullable=False)
    nonce = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class LoginAttempt(Base):
    """Durable failed-login lockout, keyed on a hash of the email — NOT the User row.

    Keying on the email hash means a non-existent address accumulates failures and locks exactly
    like a real one, so there is no 429-vs-401 difference to reveal which emails have accounts (a
    user-row lockout would reintroduce that enumeration oracle). Persisted here so the lockout holds
    across Cloud Run instances and restarts, unlike the in-memory limiter it replaces. The hash is
    peppered with SECRET_KEY (see services/login_lockout), so raw emails are never stored.
    """
    __tablename__ = "login_attempts"

    email_hash = Column(String(64), primary_key=True)
    failed_count = Column(Integer, nullable=False, default=0, server_default="0")
    locked_until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    cik = Column(String, unique=True, index=True, nullable=False)
    ticker = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    exchange = Column(String, nullable=True)
    sic = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    # When the new-filing scanner last checked this company (used to honour the scan cadence).
    last_filings_check_at = Column(DateTime(timezone=True), nullable=True)
    # When this company's SEC companyfacts history was last ingested into financial_fact
    # (multi-period analysis). Null = never; re-sync when older than COMPANYFACTS_SYNC_TTL_HOURS
    # or when a newer Filing row exists. Stamped even for unsupported (IFRS-only) filers so we
    # don't refetch them hourly.
    facts_synced_at = Column(DateTime(timezone=True), nullable=True)
    # When this company's deep filing history (10-K/10-Q since 2001) was backfilled from EFTS
    # (P1-6). Null = never; the on-visit enqueue backfills once and stamps this so it never
    # re-walks the company.
    history_backfilled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    filings = relationship("Filing", back_populates="company")


class Watchlist(Base):
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    # Per-(user, company) alert high-water mark: the newest filing we've notified this user about.
    # Prevents re-alerting and bounds the "what's new since you started watching" window.
    last_alerted_accession = Column(String, nullable=True)
    last_alerted_at = Column(DateTime(timezone=True), nullable=True)
    # Per-company earnings-day alert opt-in (strategy §3.7). Distinct from the filing-alert prefs:
    # watchlists stay unlimited, but the per-plan cap on how many companies may have this ON is
    # enforced at toggle time (entitlements.earnings_alert_limit — Free 3 / Pro 100).
    earnings_alert = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="watchlist")
    company = relationship("Company")


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (
        # Covers the hot filings-list read (get_cached_filings / DB-first serving):
        #   WHERE company_id = ? AND filing_type IN (...) ORDER BY filing_date DESC
        # and the trending join's company_id filter. filings.company_id was previously unindexed.
        # Declared here so create_all builds it on fresh DBs; existing prod DBs get the identically
        # named index from migrations/20260710_filings_company_type_date_index.sql (IF NOT EXISTS →
        # the two paths never collide).
        Index("ix_filings_company_type_date", "company_id", "filing_type", "filing_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    accession_number = Column(String, unique=True, index=True, nullable=False)
    filing_type = Column(String, nullable=False)  # 10-K, 10-Q, etc.
    filing_date = Column(DateTime(timezone=True), nullable=False)
    period_end_date = Column(DateTime(timezone=True), nullable=True)
    document_url = Column(String, nullable=False)
    sec_url = Column(String, nullable=False)
    xbrl_data = Column(JSON, nullable=True)  # Store XBRL extracted data
    # When this filing's XBRL was last normalized into financial_fact (null = never). Lets the
    # scheduled backfill run incrementally over just the newly-arrived filings.
    processed_facts_at = Column(DateTime(timezone=True), nullable=True)
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
    __table_args__ = (
        # One summary per filing (S1 decision #3). Fresh DBs get it here via create_all; existing
        # DBs via migrations/20260705_summary_filing_id_unique.sql. Concurrent writers catch the
        # IntegrityError and return the existing row rather than erroring the user.
        UniqueConstraint("filing_id", name="uq_summaries_filing_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=False)
    business_overview = Column(Text, nullable=True)
    financial_highlights = Column(JSON, nullable=True)  # Store structured data
    risk_factors = Column(JSON, nullable=True)  # Array of risk objects
    management_discussion = Column(Text, nullable=True)
    key_changes = Column(Text, nullable=True)
    raw_summary = Column(JSON, nullable=True)  # Full AI response
    # Version stamps (summary_versioning): the sections-taxonomy and prompt versions this row was
    # generated under. NULL = legacy/pre-stamp = stale. Existing DBs self-heal these at startup via
    # database.ensure_additive_columns; a serializer/prompt bump can then refresh stale rows in place.
    schema_version = Column(SmallInteger, nullable=True)
    prompt_version = Column(String, nullable=True)
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
    # "Ask this Filing" Copilot (A2) monthly question count, metered separately from summaries.
    qa_count = Column(Integer, default=0, nullable=False)
    # Multi-Period Analysis monthly generation count (fresh AI narratives only — cached re-serves
    # are free). Fair-use cap: settings.ANALYSIS_MONTHLY_CAP.
    analysis_count = Column(Integer, default=0, nullable=False)
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
    "InviteCode",
    "LoginAttempt",
    "NotificationLog",
    "NotificationPreferences",
    "OAuthAccount",
    "OAuthState",
    "SavedSummary",
    "StripeEvent",
    "Subscription",
    "Summary",
    "SummaryGenerationProgress",
    "TrendAnalysis",
    "User",
    "UserSearch",
    "UserUsage",
    "Watchlist",
    "WaitlistSignup",
]


# SQLAlchemy event listeners for data validation
# These catch issues at the Python level before they hit the database

@event.listens_for(Filing, "before_insert")
def validate_filing_before_insert(mapper, connection, target):
    """Validate Filing required fields before INSERT."""
    if target.sec_url is None:
        # Generate sec_url if missing (defensive fallback)
        if target.accession_number:
            accession_clean = target.accession_number.replace("-", "")
            # Try to get CIK from company relationship or use placeholder
            cik = "0"
            if hasattr(target, 'company') and target.company and target.company.cik:
                cik = target.company.cik.lstrip("0") or "0"
            target.sec_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/"
            logger.warning(
                f"Filing {target.accession_number}: sec_url was None, "
                f"auto-generated: {target.sec_url}"
            )
        else:
            raise ValueError(
                "Filing sec_url cannot be None and accession_number is required to generate it"
            )

    if target.document_url is None:
        raise ValueError(
            f"Filing {target.accession_number}: document_url cannot be None "
            f"(NOT NULL constraint)"
        )


@event.listens_for(Filing, "before_update")
def validate_filing_before_update(mapper, connection, target):
    """Validate Filing required fields before UPDATE."""
    if target.sec_url is None:
        raise ValueError(
            f"Filing {target.accession_number}: Cannot set sec_url to None "
            f"(NOT NULL constraint)"
        )
