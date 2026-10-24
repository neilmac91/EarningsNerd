"""Saved-summary bookmarks: save, notes, delete, status and the library listing.

``app/routers/saved_summaries.py`` is the HTTP layer; the queries, writes and row shaping live
here. A primary lookup that misses returns ``None`` (``False`` for delete) before anything is
written, and the router maps it to its 404. ``SavedSummaryRelatedRowMissing`` carries the detail
of a 404 from ``_format_saved_summary_response``.

The response dict is built here, not in the router, because building it is ORM work: after a
commit the session expires the joined Summary, Filing and Company rows, so reading their
attributes issues reload SELECTs. The writes therefore shape it before their commit, in the
transaction their lock covers (below).
"""
import threading
from typing import Optional

from sqlalchemy import Row, desc
from sqlalchemy.orm import Session

from app.models import Company, Filing, SavedSummary, Summary, User


class SavedSummaryRelatedRowMissing(Exception):
    """A saved summary's Summary, Filing or Company row is missing; ``detail`` is the 404 detail."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


# Saved-row writes check, then write: the duplicate check before a save, the row read before a notes
# update and the lookup before a delete. On the event loop the routes ran them one at a time within
# the process; in the thread pool two requests could both pass a check (two library rows for one
# summary, or a notes update of a row a delete has removed, which matches no row and answers 500), so
# each takes this lock from its check to its commit. A holder takes it after its session's first query
# and makes no new checkout inside it, so it never waits for a pool slot that a waiter holds: a write
# shapes its answer before its commit, since a read after it would check a connection out again. A
# waiter's check then sees the holder's commit because each statement reads the latest commit (READ
# COMMITTED, PostgreSQL's default and production's). This lock reaches one process, and the API runs
# up to two instances, so before it each unit takes the account's users row lock (``lock_saved_rows``),
# which every instance shares, as the watch-row writes do (``watchlist_service.watch_row_lock``).
#
# Inside the lock a write can still wait in PostgreSQL behind an admin tool's delete, which takes no users
# row lock: a save's INSERT on its summary's row (the foreign-key check) while a delete of that summary is
# uncommitted, and an update or a delete on its bookmark's row while the admin reset-all deletes the
# bookmarks of the summaries it resets (``include_saved``). Each is an operator action with no network call
# in its transaction, and every account's library write on the instance waits behind it. The save does not
# take its summary's lock (FOR KEY SHARE) before this lock to avoid that wait: the reset-all deletes the
# bookmarks before their summaries, the reverse order, and a save over a saved row deadlocked with it (40P01,
# five runs of five in each order on PostgreSQL 16, E171's saved-summaries verification lens).
saved_row_lock = threading.Lock()


def lock_saved_rows(db: Session, user_id: int) -> None:
    """Take ``user_id``'s users row lock for the rest of the caller's transaction.

    Every saved-row write takes it before ``saved_row_lock`` and before its check: the save's duplicate
    check, the notes update's row read and the delete's lookup. The process lock serializes them within
    one instance; across the API's instances two saves of one summary could otherwise both pass the
    duplicate check and store it twice. A second writer waits here for the first's commit, and its
    check then reads that commit (READ COMMITTED). Taken before the process lock, its wait holds that
    lock for no other account. FOR NO KEY UPDATE, as ``watchlist_service.lock_watch_rows`` takes it: it
    serializes these writers and the account's other users row writers, but not the foreign-key checks
    of inserts that name the user. SQLite ignores it."""
    db.query(User.id).filter(User.id == user_id).with_for_update(key_share=True).first()


def _saved(db: Session, user_id: int, summary_id: int) -> Optional[SavedSummary]:
    """The user's library row for ``summary_id``: the save's duplicate check."""
    return db.query(SavedSummary).filter(
        SavedSummary.user_id == user_id,
        SavedSummary.summary_id == summary_id
    ).first()


def _owned(db: Session, user_id: int, saved_summary_id: int) -> Optional[SavedSummary]:
    """The user's library row ``saved_summary_id``: the delete's lookup."""
    return db.query(SavedSummary).filter(
        SavedSummary.id == saved_summary_id,
        SavedSummary.user_id == user_id
    ).first()


def _owned_library_row(db: Session, user_id: int, saved_summary_id: int) -> Optional[Row]:
    """The user's library row ``saved_summary_id`` with its Summary, Filing and Company, in one query
    with joins to avoid N+1: the notes update's row read."""
    return (
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


def save_summary(db: Session, *, user_id: int, summary_id: int, notes: Optional[str]) -> Optional[dict]:
    """Save ``summary_id`` for the user, or update the notes of an existing save when given.

    Returns the library row, or ``None`` when the summary does not exist (nothing is written).
    """
    # Check if summary exists and eagerly load related data to avoid N+1 queries. No lock on the summary:
    # see saved_row_lock's comment.
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

    lock_saved_rows(db, user_id)
    with saved_row_lock:
        saved_summary = _saved(db, user_id, summary_id)
        if saved_summary is None:
            saved_summary = SavedSummary(
                user_id=user_id,
                summary_id=summary_id,
                notes=notes
            )
            db.add(saved_summary)
            db.flush()
            # The server-set created_at, read in the transaction the lock covers.
            db.refresh(saved_summary)
        elif notes is not None:
            # Update notes if provided
            saved_summary.notes = notes
        saved = _format_saved_summary_response(
            saved_summary, db, summary=summary, filing=filing, company=company
        )
        db.commit()
    return saved


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
    lock_saved_rows(db, user_id)
    with saved_row_lock:
        saved_summary = _owned(db, user_id, saved_summary_id)
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
    lock_saved_rows(db, user_id)
    with saved_row_lock:
        row = _owned_library_row(db, user_id, saved_summary_id)
        if not row:
            return None
        saved_summary, summary, filing, company = row

        if notes is not None:
            saved_summary.notes = notes
        updated = _format_saved_summary_response(
            saved_summary, db, summary=summary, filing=filing, company=company
        )
        db.commit()
    return updated



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
