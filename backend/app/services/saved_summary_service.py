"""Saved-summary bookmarks: save, notes, delete, status and the library listing.

``app/routers/saved_summaries.py`` is the HTTP layer; the queries, writes and row shaping live
here. A primary lookup that misses returns ``None`` (``False`` for delete) before anything is
written, and the router maps it to its 404. ``SavedSummaryRelatedRowMissing`` carries the detail
of a 404 from ``_format_saved_summary_response``.

The response dict is built here, not in the router, because building it is ORM work: after a
commit the session expires the joined Summary, Filing and Company rows, so reading their
attributes issues reload SELECTs. Shaping therefore runs inside the same call as the commit.
"""
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Company, Filing, SavedSummary, Summary


class SavedSummaryRelatedRowMissing(Exception):
    """A saved summary's Summary, Filing or Company row is missing; ``detail`` is the 404 detail."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def save_summary(db: Session, *, user_id: int, summary_id: int, notes: Optional[str]) -> Optional[dict]:
    """Save ``summary_id`` for the user, or update the notes of an existing save when given.

    Returns the library row, or ``None`` when the summary does not exist (nothing is written).
    """
    # Check if summary exists and eagerly load related data to avoid N+1 queries
    row = (
        db.query(Summary, Filing, Company)
        .join(Filing, Summary.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(Summary.id == summary_id)
        .first()
    )
    if not row:
        return None
    summary, filing, company = row

    # Check if already saved
    existing = db.query(SavedSummary).filter(
        SavedSummary.user_id == user_id,
        SavedSummary.summary_id == summary_id
    ).first()

    if existing:
        # Update notes if provided
        if notes is not None:
            existing.notes = notes
            db.commit()
            db.refresh(existing)
        return _format_saved_summary_response(
            existing, db, summary=summary, filing=filing, company=company
        )

    # Create new saved summary
    saved_summary = SavedSummary(
        user_id=user_id,
        summary_id=summary_id,
        notes=notes
    )
    db.add(saved_summary)
    db.commit()
    db.refresh(saved_summary)

    return _format_saved_summary_response(
        saved_summary, db, summary=summary, filing=filing, company=company
    )


def list_saved_summaries(db: Session, user_id: int) -> list[dict]:
    """The user's library rows, newest first."""
    rows = (
        db.query(SavedSummary, Summary, Filing, Company)
        .join(Summary, SavedSummary.summary_id == Summary.id)
        .join(Filing, Summary.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(SavedSummary.user_id == user_id)
        .order_by(desc(SavedSummary.created_at))
        .all()
    )

    return [
        _format_saved_summary_response(
            saved_summary,
            db,
            summary=summary,
            filing=filing,
            company=company,
        )
        for saved_summary, summary, filing, company in rows
    ]


def saved_summary_status(db: Session, *, user_id: int, summary_id: int) -> Optional[bool]:
    """Whether the user saved ``summary_id``; ``None`` when the summary does not exist.

    Column-only queries: no saved-library content and no other user's bookmark is loaded.
    """
    if db.query(Summary.id).filter(Summary.id == summary_id).first() is None:
        return None
    saved = db.query(SavedSummary.id).filter(
        SavedSummary.user_id == user_id,
        SavedSummary.summary_id == summary_id,
    ).first()
    return saved is not None


def delete_saved_summary(db: Session, *, user_id: int, saved_summary_id: int) -> bool:
    """Delete the user's saved summary; ``False`` when the user has no such row (nothing is written)."""
    saved_summary = db.query(SavedSummary).filter(
        SavedSummary.id == saved_summary_id,
        SavedSummary.user_id == user_id
    ).first()

    if not saved_summary:
        return False

    db.delete(saved_summary)
    db.commit()

    return True


def update_saved_summary_notes(
    db: Session, *, user_id: int, saved_summary_id: int, notes: Optional[str]
) -> Optional[dict]:
    """Set the notes of the user's saved summary when given and return the library row.

    Returns ``None`` when the user has no such row (nothing is written).
    """
    # Single query with joins to avoid N+1
    row = (
        db.query(SavedSummary, Summary, Filing, Company)
        .join(Summary, SavedSummary.summary_id == Summary.id)
        .join(Filing, Summary.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(
            SavedSummary.id == saved_summary_id,
            SavedSummary.user_id == user_id
        )
        .first()
    )

    if not row:
        return None
    saved_summary, summary, filing, company = row

    if notes is not None:
        saved_summary.notes = notes
        db.commit()
        db.refresh(saved_summary)

    return _format_saved_summary_response(
        saved_summary, db, summary=summary, filing=filing, company=company
    )


def _format_saved_summary_response(
    saved_summary: SavedSummary,
    db: Session,
    *,
    summary: Optional[Summary] = None,
    filing: Optional[Filing] = None,
    company: Optional[Company] = None,
) -> dict:
    """Format saved summary response with related data"""
    summary = summary or db.query(Summary).filter(Summary.id == saved_summary.summary_id).first()
    if not summary:
        raise SavedSummaryRelatedRowMissing("Summary not found")

    filing = filing or db.query(Filing).filter(Filing.id == summary.filing_id).first()
    if not filing:
        raise SavedSummaryRelatedRowMissing("Filing not found")

    company = company or db.query(Company).filter(Company.id == filing.company_id).first()
    if not company:
        raise SavedSummaryRelatedRowMissing("Company not found")

    return {
        "id": saved_summary.id,
        "summary_id": saved_summary.summary_id,
        "notes": saved_summary.notes,
        "created_at": saved_summary.created_at.isoformat() if saved_summary.created_at else None,
        "summary": {
            "id": summary.id,
            "filing_id": summary.filing_id,
            "business_overview": summary.business_overview,
        },
        "filing": {
            "id": filing.id,
            "filing_type": filing.filing_type,
            "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
            "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
        },
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "name": company.name,
        }
    }
