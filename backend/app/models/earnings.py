"""Earnings-calendar models — the owned earnings-events engine (strategy §3.3 / §3.7).

`EarningsEvent` is one row per (ticker, fiscal quarter), mutated in place as knowledge improves
along the status ladder ``estimated → confirmed → reported``. Reported is ground truth from an
EDGAR 8-K Item 2.02; estimated/confirmed come from providers + the company's own reporting pattern.

`EarningsAlertLog` is the send/dedup ledger for the earnings-day email — a unique
``(user_id, earnings_event_id, event_date, channel)`` makes a double-send impossible, and the
``event_date`` in the key means a company *moving* its date re-alerts on the new day while the old
send can't fire twice (the sibling of `NotificationLog`, which keys on ``filing_id`` — a column that
doesn't exist for a not-yet-filed future event).

Kept portable like the rest of the schema: plain ``String`` (not PG enums) and
``DateTime(timezone=True)`` / ``Date`` so the same tables work on Postgres (prod) and SQLite (tests).
"""
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func

from app.database import Base

# Status ladder + confidence + event-time slots kept as validated strings for SQLite portability.
STATUS_ESTIMATED = "estimated"
STATUS_CONFIRMED = "confirmed"
STATUS_REPORTED = "reported"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

TIME_BMO = "bmo"  # before market open
TIME_AMC = "amc"  # after market close
TIME_DMH = "dmh"  # during market hours

SOURCE_ALPHA_VANTAGE = "alpha_vantage"
SOURCE_EDGAR_8K = "edgar_8k"
SOURCE_PATTERN = "pattern"


class EarningsEvent(Base):
    __tablename__ = "earnings_events"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(16), nullable=False, index=True)          # normalised upper-case
    cik = Column(String(10), nullable=True)                          # zero-padded; null until mapped
    company_name = Column(String, nullable=True)
    # The fiscal quarter being reported. NOT NULL is deliberate: Postgres treats NULLs as distinct
    # in unique constraints, so a nullable column here would silently allow duplicate (ticker, NULL)
    # rows and break the one-row-per-company-quarter invariant.
    fiscal_period_end = Column(Date, nullable=False)
    event_date = Column(Date, nullable=False, index=True)            # America/New_York calendar day
    event_time = Column(String(3), nullable=True)                    # bmo | amc | dmh | None
    status = Column(String(10), nullable=False, default=STATUS_ESTIMATED, server_default=STATUS_ESTIMATED)
    confidence = Column(String(10), nullable=False, default=CONFIDENCE_MEDIUM, server_default=CONFIDENCE_MEDIUM)
    eps_estimate = Column(Numeric, nullable=True)
    eps_actual = Column(Numeric, nullable=True)
    anticipation_score = Column(Numeric, nullable=False, default=0, server_default="0")
    source = Column(String(20), nullable=False, default=SOURCE_PATTERN, server_default=SOURCE_PATTERN)
    accession_number = Column(String(25), nullable=True)             # set on reported → deep-link 8-K
    prior_event_date = Column(Date, nullable=True)                   # previous value when date moved
    date_changed_at = Column(DateTime(timezone=True), nullable=True) # when it moved (stability input)
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reported_at = Column(DateTime(timezone=True), nullable=True)     # 8-K acceptanceDateTime

    __table_args__ = (
        UniqueConstraint("ticker", "fiscal_period_end", name="uq_earnings_events_ticker_period"),
        # top-N-per-day query for the anticipated-earnings surfaces (§3.7)
        Index("ix_earnings_events_day_rank", "event_date", "anticipation_score"),
    )


class EarningsAlertLog(Base):
    __tablename__ = "earnings_alert_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    earnings_event_id = Column(
        Integer, ForeignKey("earnings_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Denormalised event_date is part of the dedup key (a date change must re-alert; the old send
    # must not fire twice). Kept on the row so the ledger is self-describing without a join.
    event_date = Column(Date, nullable=False)
    channel = Column(String(20), nullable=False, default="email", server_default="email")
    # sent | failed | pending — pending is a claim placeholder written before the send (the unique
    # constraint acts as the send lock); it becomes sent/failed once the send returns.
    status = Column(String(20), nullable=False, default="sent", server_default="sent")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id", "earnings_event_id", "event_date", "channel",
            name="uq_earnings_alert_log_user_event_date_channel",
        ),
    )
