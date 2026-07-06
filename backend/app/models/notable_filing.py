"""Notable-filings model — the homepage market-wide discovery surface.

One row per SEC filing the EDGAR scan (``notable_filings_service.run_scan``) judged notable:
high-signal form types (10-K/10-Q/S-1/SC 13D) and 8-Ks with material item codes. Rows are
upserted on ``accession_number`` by the twice-daily scan and pruned after 14 days; the serve
path re-ranks them with a recency decay at read time, so the stored ``score`` is deliberately
decay-free (base signal + demand) and never goes stale over a weekend.

Deliberately NOT a ``Filing`` row: ``Filing`` requires a ``company_id`` FK (and ingestion), while
this table is a lightweight market-wide candidate list keyed by ticker/accession — a card links to
``/company/{ticker}``, and the filing is only ingested if the user goes on to request a summary.

Kept portable like the rest of the schema: plain ``String`` (not PG enums), ``JSON``,
``DateTime(timezone=True)`` / ``Date`` so the same table works on Postgres (prod) and SQLite (tests).
"""
from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base


class NotableFiling(Base):
    __tablename__ = "notable_filings"

    id = Column(Integer, primary_key=True, index=True)
    # With-dashes accession number as EFTS reports it — the scan's dedupe key (exhibits of one
    # filing arrive as separate EFTS hits; the unique constraint is the second line of defence
    # behind the scan's in-memory seen-set).
    accession_number = Column(String(25), nullable=False)
    ticker = Column(String(16), nullable=False)  # normalised upper-case; hits without one are dropped
    cik = Column(String(10), nullable=True)
    company_name = Column(String, nullable=True)
    form = Column(String(12), nullable=False)  # 8-K | 10-K | 10-Q | S-1 | SC 13D
    items = Column(JSON, nullable=True)  # 8-K item codes, e.g. ["2.02", "9.01"]; NULL otherwise
    reason = Column(String(32), nullable=False)  # slug, e.g. earnings_results — see service weights
    filed_date = Column(Date, nullable=False)
    # Base signal + demand boost, WITHOUT recency decay (applied at serve time).
    score = Column(Numeric, nullable=False, default=0, server_default="0")
    sec_url = Column(Text, nullable=False)  # filing index page, rule-10 URL format
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("accession_number", name="uq_notable_filings_accession"),
        # Serve path: filed_date window scan + score ordering.
        Index("ix_notable_filings_rank", "filed_date", "score"),
        Index("ix_notable_filings_ticker", "ticker"),
    )
