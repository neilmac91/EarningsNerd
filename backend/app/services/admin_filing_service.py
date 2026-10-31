"""Admin maintenance of one filing's generated content, and the stale-XBRL audit / bulk reset.

Called by ``routers/admin.py`` (DELETE /api/admin/filing/{id}/summary, /xbrl and /reset, GET
/api/admin/filings/audit-xbrl, POST /api/admin/filings/bulk-reset-stale). Each write path takes the
admin maintenance lock (``lock_maintenance``) first and commits once at the end, as the endpoints always
did; the router keeps the admin gate, the 404 for ``FilingNotFoundError``, the post-commit logs and the
response shape.
"""
from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Filing, FilingContentCache, Summary, SummaryGenerationProgress, User

logger = logging.getLogger(__name__)

# The key of the PostgreSQL advisory lock each admin maintenance write takes first: "MAINTAIN" in ASCII.
MAINTENANCE_LOCK_KEY = 0x4D41494E5441494E


class FilingNotFoundError(Exception):
    """No filing has the requested id (the admin router maps it to 404 "Filing not found")."""


def lock_maintenance(db: Session) -> None:
    """Take the admin maintenance lock for the rest of the caller's transaction (E171).

    The summary delete, the XBRL clear, the filing reset, the stale-XBRL bulk reset and the summaries' reset-all
    each read the rows they then delete or clear, and report what they read. The event loop ran them one at a time
    within an instance; in the thread pool they overlap. Overlapping, a reset-all, which deletes progress rows
    before summaries, deadlocked with a summary delete or filing reset, whose flush deletes the summary first, and
    two of them each reported, and a reset-all audited, rows the other had deleted. Each takes this lock before its
    first read of those rows, so they run one at a time across the API's instances, and each read sees the commit
    of the one before it (READ COMMITTED). The admin router's units take it on the connection the auth lookup
    checked out, with no other checkout before the commit that releases it, so no holder waits for a pool slot a
    waiter holds. It is a transaction-level advisory lock: PostgreSQL releases it at the commit or rollback, so it
    never outlives the unit on a pooled connection. SQLite has no advisory locks, so off PostgreSQL nothing is
    locked."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(MAINTENANCE_LOCK_KEY)))


def delete_filing_summary(db: Session, filing_id: int, *, actor: User) -> bool:
    """Delete the filing's summary and generation progress, commit, and return whether a summary existed."""
    lock_maintenance(db)
    # Find the filing
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise FilingNotFoundError(filing_id)

    # Delete summary if exists
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        db.delete(summary)
        logger.info(f"Admin {actor.id} deleted summary for filing {filing_id}")

    # Delete progress record to allow fresh generation
    progress = db.query(SummaryGenerationProgress).filter(
        SummaryGenerationProgress.filing_id == filing_id
    ).first()
    if progress:
        db.delete(progress)

    db.commit()
    return summary is not None


def clear_filing_xbrl(db: Session, filing_id: int) -> bool:
    """Clear the filing's stored XBRL data, commit, and return whether it had any."""
    lock_maintenance(db)
    # Find the filing
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise FilingNotFoundError(filing_id)

    # Clear XBRL data
    had_xbrl = filing.xbrl_data is not None
    filing.xbrl_data = None

    db.commit()
    return had_xbrl


def reset_filing(db: Session, filing_id: int) -> dict[str, bool]:
    """Delete the summary, XBRL data, content cache and progress in one commit; report what existed."""
    lock_maintenance(db)
    # Find the filing
    filing = db.query(Filing).filter(Filing.id == filing_id).first()
    if not filing:
        raise FilingNotFoundError(filing_id)

    deleted = {
        "summary": False,
        "xbrl_data": False,
        "content_cache": False,
        "progress": False
    }

    # Delete summary
    summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
    if summary:
        db.delete(summary)
        deleted["summary"] = True

    # Clear XBRL data
    if filing.xbrl_data is not None:
        filing.xbrl_data = None
        deleted["xbrl_data"] = True

    # Delete content cache
    content_cache = db.query(FilingContentCache).filter(
        FilingContentCache.filing_id == filing_id
    ).first()
    if content_cache:
        db.delete(content_cache)
        deleted["content_cache"] = True

    # Delete progress record
    progress = db.query(SummaryGenerationProgress).filter(
        SummaryGenerationProgress.filing_id == filing_id
    ).first()
    if progress:
        db.delete(progress)
        deleted["progress"] = True

    db.commit()
    return deleted


def _extract_xbrl_years(xbrl_data: dict) -> set:
    """Extract all years from XBRL data periods."""
    years = set()
    if not xbrl_data:
        return years

    # Check common metric keys that have period data
    for key in ["revenue", "net_income", "total_assets", "earnings_per_share"]:
        entries = xbrl_data.get(key, [])
        if isinstance(entries, list):
            for entry in entries:
                period = entry.get("period") if isinstance(entry, dict) else None
                if period and isinstance(period, str) and len(period) >= 4:
                    try:
                        year = int(period[:4])
                        years.add(year)
                    except ValueError:
                        pass
    return years


def audit_stale_xbrl(db: Session, *, year_threshold: int) -> tuple[int, list[dict]]:
    """Read-only: (filings with XBRL data, the ones whose newest XBRL year trails the filing period
    by more than ``year_threshold``)."""
    # Find all filings with XBRL data
    filings_with_xbrl = db.query(Filing).filter(
        Filing.xbrl_data.isnot(None)
    ).all()

    stale_filings = []
    for filing in filings_with_xbrl:
        # Get the expected year from filing period
        expected_year = None
        if filing.period_end_date:
            expected_year = filing.period_end_date.year
        elif filing.filing_date:
            expected_year = filing.filing_date.year

        if not expected_year:
            continue

        # Extract years from XBRL data
        xbrl_years = _extract_xbrl_years(filing.xbrl_data)

        if not xbrl_years:
            continue

        # Check if any XBRL year is too far from expected
        max_xbrl_year = max(xbrl_years)
        year_diff = expected_year - max_xbrl_year

        if year_diff > year_threshold:
            stale_filings.append({
                "filing_id": filing.id,
                "company_id": filing.company_id,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
                "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
                "expected_year": expected_year,
                "xbrl_years": sorted(xbrl_years, reverse=True),
                "max_xbrl_year": max_xbrl_year,
                "year_difference": year_diff
            })

    return len(filings_with_xbrl), stale_filings


def bulk_reset_stale_xbrl(db: Session, *, year_threshold: int, dry_run: bool, actor: User) -> list[dict]:
    """Find the stale-XBRL filings; unless ``dry_run``, clear their XBRL data, summary and progress
    and commit once, under the admin maintenance lock. Returns the affected filings either way."""
    if not dry_run:
        lock_maintenance(db)
    # Find all filings with XBRL data
    filings_with_xbrl = db.query(Filing).filter(
        Filing.xbrl_data.isnot(None)
    ).all()

    affected_filings = []
    for filing in filings_with_xbrl:
        # Get the expected year from filing period
        expected_year = None
        if filing.period_end_date:
            expected_year = filing.period_end_date.year
        elif filing.filing_date:
            expected_year = filing.filing_date.year

        if not expected_year:
            continue

        # Extract years from XBRL data
        xbrl_years = _extract_xbrl_years(filing.xbrl_data)

        if not xbrl_years:
            continue

        # Check if any XBRL year is too far from expected
        max_xbrl_year = max(xbrl_years)
        year_diff = expected_year - max_xbrl_year

        if year_diff > year_threshold:
            affected_filings.append({
                "filing_id": filing.id,
                "expected_year": expected_year,
                "max_xbrl_year": max_xbrl_year,
                "year_difference": year_diff
            })

            if not dry_run:
                # Reset the filing
                # Clear XBRL data
                filing.xbrl_data = None

                # Delete summary if exists
                summary = db.query(Summary).filter(Summary.filing_id == filing.id).first()
                if summary:
                    db.delete(summary)

                # Delete progress if exists
                progress = db.query(SummaryGenerationProgress).filter(
                    SummaryGenerationProgress.filing_id == filing.id
                ).first()
                if progress:
                    db.delete(progress)

                logger.info(f"Admin {actor.id} bulk-reset filing {filing.id} (stale XBRL)")

    if not dry_run:
        db.commit()
    return affected_filings
