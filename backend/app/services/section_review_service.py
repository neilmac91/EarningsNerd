"""The Pro review of a filing's Item 1A wording changes: labels per change, completion, receipt.

The one writer of ``section_reviews`` (``app/models/section_review.py``). A reader works through
the change queue the Change Report's ``section_changes`` block lists and labels each change
``reviewed`` or ``follow_up``. The review is complete when every change of the current comparison
carries a label (the E3 completion measure: reaching the end of the queue, not opens or clicks);
at that moment a receipt is frozen on the row: which two texts were compared (accessions, SHA-256
fingerprints, extractor versions), which diff engine paired them, the counts, and the changes
flagged for follow-up. Removing a label afterwards reopens the review and clears the receipt.

Labels hang on ``section_diff``'s content-addressed change ids, which survive re-extraction while
the two paragraphs' wording is unchanged. Ids the current comparison no longer has are ignored on
read and dropped on write, and a receipt whose fingerprints no longer match the live comparison
reads as not complete, so a review never claims more than the text in front of the reader. The
dashboard reads the same reconciliation through ``review_progress``.

A write locks the reader's row (``SELECT … FOR UPDATE``; a no-op on SQLite) so two labels pressed
within milliseconds (the 1/2 keys) are applied in turn rather than one overwriting the other, and
the first two labels of a review racing on the insert end with the loser labelling the winner's row.

HTTP-free: the router resolves the Pro entitlement and maps the domain errors below to statuses.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import APP_VERSION, settings
from app.models import Filing
from app.models.filing_section_text import FilingSectionText
from app.models.section_review import SectionReview
from app.services import section_diff
from app.services.filing_section_service import (
    FULL_SECTION_ACCESS,
    SECTION_ITEM_1A,
    SECTION_LABELS,
    build_section_changes,
    cached_diff,
    section_row,
)
from app.services.filing_section_service import STATUS_OK as SECTION_STATUS_OK
from app.utils.datetimes import ensure_utc, iso_z, utcnow

LABEL_REVIEWED = "reviewed"
LABEL_FOLLOW_UP = "follow_up"
LABELS = (LABEL_REVIEWED, LABEL_FOLLOW_UP)
RECEIPT_VERSION = 1

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"


class ReviewError(Exception):
    """Base of the domain errors the router maps to HTTP statuses."""


class FilingNotFound(ReviewError):
    pass


class ReviewUnavailable(ReviewError):
    """Nothing to review: the feature is off, or the filing has no ``ok`` comparison yet."""


class UnknownItem(ReviewError):
    """The change id is not one of the current comparison's."""


class InvalidLabel(ReviewError):
    pass


def _comparison(db: Session, filing: Filing) -> Optional[dict[str, Any]]:
    """The full ``section_changes`` block when it is a comparison; None otherwise (or feature off)."""
    if not settings.ENABLE_SECTION_CHANGES:
        return None
    block = build_section_changes(db, filing, FULL_SECTION_ACCESS)
    return block if block is not None and block.get("status") == "ok" else None


def _review_row(db: Session, user_id: int, filing_id: int, *, lock: bool = False) -> Optional[SectionReview]:
    """The reader's row for the filing's section; ``lock`` holds it for the write that follows."""
    query = db.query(SectionReview).filter(
        SectionReview.user_id == user_id,
        SectionReview.filing_id == filing_id,
        SectionReview.section == SECTION_ITEM_1A,
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def _text_fingerprint(row: Optional[FilingSectionText]) -> dict[str, Any]:
    """A stored text as the receipt names it: its hash, extractor version and extraction time."""
    return {
        "sha256": row.sha256 if row is not None else None,
        "extractor_version": row.extractor_version if row is not None else None,
        "extracted_at": iso_z(ensure_utc(row.extracted_at)) if row is not None and row.extracted_at else None,
    }


def _fingerprints(db: Session, filing: Filing, comparison: dict[str, Any]) -> dict[str, Any]:
    """The two stored texts behind the comparison, by their rows' hashes and extractor versions."""
    current = section_row(db, filing.id)
    prior = section_row(db, comparison["prior_filing"]["filing_id"])
    return {"current": _text_fingerprint(current), "prior": _text_fingerprint(prior)}


def _filing_ref(filing: Filing) -> dict[str, Any]:
    return {
        "filing_id": filing.id,
        "accession_number": filing.accession_number,
        "filing_type": filing.filing_type,
        "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
        "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
    }


def _receipt_matches(receipt: Optional[dict[str, Any]], fingerprints: dict[str, Any], comparison: dict[str, Any]) -> bool:
    """A frozen receipt describes the comparison in front of the reader: same two texts, same engine."""
    if not isinstance(receipt, dict):
        return False
    texts = receipt.get("texts") or {}
    return (
        receipt.get("engine_version") == comparison["engine_version"]
        and (texts.get("current") or {}).get("sha256") == fingerprints["current"]["sha256"]
        and (texts.get("prior") or {}).get("sha256") == fingerprints["prior"]["sha256"]
    )


def _live_labels(row: Optional[SectionReview], ids: list[str]) -> dict[str, str]:
    """The stored labels on the current comparison's changes; a retired id's label is left behind."""
    stored = row.labels if row is not None and isinstance(row.labels, dict) else {}
    return {item_id: stored[item_id] for item_id in ids if item_id in stored}


def _state(
    filing: Filing,
    comparison: Optional[dict[str, Any]],
    row: Optional[SectionReview],
    fingerprints: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """The review as the client renders it. Labels are filtered to the current comparison's ids;
    completion is reported only while its receipt still matches the live comparison."""
    base = {"filing_id": filing.id, "section": SECTION_ITEM_1A, "section_label": SECTION_LABELS[SECTION_ITEM_1A]}
    if comparison is None:
        return {**base, "status": STATUS_UNAVAILABLE, "engine_version": section_diff.ENGINE_VERSION,
                "items_total": 0, "labels": {}, "counts": {"reviewed": 0, "follow_up": 0, "unlabeled": 0},
                "completed_at": None, "receipt": None}
    ids = [item["id"] for item in comparison["items"]]
    labels = _live_labels(row, ids)
    reviewed = sum(1 for label in labels.values() if label == LABEL_REVIEWED)
    follow_up = len(labels) - reviewed
    complete = (
        row is not None and row.completed_at is not None and len(labels) == len(ids)
        and fingerprints is not None and _receipt_matches(row.receipt, fingerprints, comparison)
    )
    return {
        **base,
        "status": STATUS_OK,
        "engine_version": comparison["engine_version"],
        "items_total": len(ids),
        "labels": labels,
        "counts": {"reviewed": reviewed, "follow_up": follow_up, "unlabeled": len(ids) - len(labels)},
        "completed_at": iso_z(ensure_utc(row.completed_at)) if complete else None,
        "receipt": row.receipt if complete else None,
    }


def review_state(db: Session, user_id: int, filing_id: int) -> dict[str, Any]:
    """The reader's review of the filing's wording changes. Read-only: ``status`` is ``unavailable``
    (with no items) when there is no comparison to review."""
    filing = db.get(Filing, filing_id)
    if filing is None:
        raise FilingNotFound(filing_id)
    comparison = _comparison(db, filing)
    row = _review_row(db, user_id, filing_id)
    fingerprints = _fingerprints(db, filing, comparison) if comparison is not None else None
    return _state(filing, comparison, row, fingerprints)


def review_progress(db: Session, user_id: int, filings: Sequence[Filing]) -> dict[int, dict[str, Any]]:
    """Per filing the reader has a review row for, what a list shows of it: ``labeled`` (the labels
    on the live comparison's changes) and ``completed_at`` (only while the receipt still describes
    that comparison), reconciled as ``review_state`` reconciles them (the live diff's ids, the
    stored texts' hashes), so a card never says "Reviewed" after a re-extraction reopened the
    review. Filings without a row are absent.

    A list's read, in three statements however many reviews it carries: the reader's rows, then
    their filings' ``ok`` Item 1A rows, then the prior rows those name (``diff_prior_filing_id``,
    the prior the cached comparison was computed against; ``refresh_diff_summaries`` keeps it on
    the prior rule after every extraction, and a row whose comparison is not cached yet has no
    progress to show). The diff itself comes from the per-process memo (``cached_diff``). The
    review endpoint resolves the prior live; the two agree whenever the summary is current."""
    by_id = {filing.id: filing for filing in filings}
    if not by_id:
        return {}
    rows = (
        db.query(SectionReview)
        .filter(
            SectionReview.user_id == user_id,
            SectionReview.filing_id.in_(list(by_id)),
            SectionReview.section == SECTION_ITEM_1A,
        )
        .all()
    )
    current_rows: dict[int, FilingSectionText] = {}
    prior_rows: dict[int, FilingSectionText] = {}
    if rows and settings.ENABLE_SECTION_CHANGES:
        current_rows = {
            section.filing_id: section
            for section in db.query(FilingSectionText).filter(
                FilingSectionText.filing_id.in_([row.filing_id for row in rows]),
                FilingSectionText.section == SECTION_ITEM_1A,
                FilingSectionText.status == SECTION_STATUS_OK,
                FilingSectionText.diff_prior_filing_id.isnot(None),
            )
        }
        prior_ids = {section.diff_prior_filing_id for section in current_rows.values()}
        if prior_ids:
            prior_rows = {
                section.filing_id: section
                for section in db.query(FilingSectionText).filter(
                    FilingSectionText.filing_id.in_(list(prior_ids)),
                    FilingSectionText.section == SECTION_ITEM_1A,
                    FilingSectionText.status == SECTION_STATUS_OK,
                )
            }
    out: dict[int, dict[str, Any]] = {}
    for row in rows:
        current = current_rows.get(row.filing_id)
        prior = prior_rows.get(current.diff_prior_filing_id) if current is not None else None
        comparison = fingerprints = None
        if current is not None and prior is not None:
            comparison = {"engine_version": section_diff.ENGINE_VERSION, "items": cached_diff(prior, current)["items"]}
            fingerprints = {"current": _text_fingerprint(current), "prior": _text_fingerprint(prior)}
        state = _state(by_id[row.filing_id], comparison, row, fingerprints)
        out[row.filing_id] = {"labeled": len(state["labels"]), "completed_at": state["completed_at"]}
    return out


def _build_receipt(
    filing: Filing, comparison: dict[str, Any], fingerprints: dict[str, Any], labels: dict[str, str], now: datetime
) -> dict[str, Any]:
    prior = comparison["prior_filing"]
    follow_ups = [item["id"] for item in comparison["items"] if labels.get(item["id"]) == LABEL_FOLLOW_UP]
    return {
        "version": RECEIPT_VERSION,
        "completed_at": iso_z(now),
        "section": SECTION_ITEM_1A,
        "section_label": SECTION_LABELS[SECTION_ITEM_1A],
        "filing": _filing_ref(filing),
        "prior_filing": dict(prior),
        "texts": fingerprints,
        "engine_version": comparison["engine_version"],
        "app_version": APP_VERSION,
        "paragraphs": dict(comparison["paragraphs"]),
        "counts": dict(comparison["counts"]),
        "words": dict(comparison["words"]),
        "items_total": len(comparison["items"]),
        "labels": {LABEL_REVIEWED: len(labels) - len(follow_ups), LABEL_FOLLOW_UP: len(follow_ups)},
        "follow_up_ids": follow_ups,
    }


def set_label(
    db: Session, user_id: int, filing_id: int, item_id: str, label: Optional[str], *, now: Optional[datetime] = None
) -> dict[str, Any]:
    """Label one change (``reviewed`` / ``follow_up``), or clear it with None; commit; return the
    state plus ``completed_now``: whether this label completed the queue (the client counts the E3
    completion on that transition, so a label changed while the queue stays complete, or answers
    landing out of order, never count it twice). Completing the queue freezes the receipt; reopening
    it clears the receipt."""
    if label is not None and label not in LABELS:
        raise InvalidLabel(label)
    filing = db.get(Filing, filing_id)
    if filing is None:
        raise FilingNotFound(filing_id)
    comparison = _comparison(db, filing)
    if comparison is None:
        raise ReviewUnavailable(filing_id)
    ids = [item["id"] for item in comparison["items"]]
    if item_id not in ids:
        raise UnknownItem(item_id)
    now = now or utcnow()
    fingerprints = _fingerprints(db, filing, comparison)
    try:
        return _write_label(db, user_id, filing, comparison, ids, fingerprints, item_id, label, now)
    except IntegrityError:
        # The review's first two labels raced on the insert (the unique row per reader, filing and
        # section): the loser starts over against the winner's row, which the retry reads locked.
        db.rollback()
        return _write_label(db, user_id, filing, comparison, ids, fingerprints, item_id, label, now)


def _write_label(
    db: Session,
    user_id: int,
    filing: Filing,
    comparison: dict[str, Any],
    ids: list[str],
    fingerprints: dict[str, Any],
    item_id: str,
    label: Optional[str],
    now: datetime,
) -> dict[str, Any]:
    """One locked read-modify-write of the reader's row, committed."""
    row = _review_row(db, user_id, filing.id, lock=True)
    if row is None:
        row = SectionReview(user_id=user_id, filing_id=filing.id, section=SECTION_ITEM_1A, labels={})
        db.add(row)
    labels = _live_labels(row, ids)
    was_complete = (
        len(labels) == len(ids) and row.completed_at is not None
        and _receipt_matches(row.receipt, fingerprints, comparison)
    )
    if label is None:
        labels.pop(item_id, None)
    else:
        labels[item_id] = label
    row.labels = labels  # a new dict: the JSON column sees the change
    row.engine_version = comparison["engine_version"]
    complete = len(labels) == len(ids)
    if complete:
        # The completion of this comparison sets the time (the E3 measure); a label changed while
        # the queue stays complete keeps it and refreshes the receipt's labels.
        if not was_complete:
            row.completed_at = now
        row.receipt = _build_receipt(filing, comparison, fingerprints, labels, ensure_utc(row.completed_at))
    else:
        row.completed_at = None
        row.receipt = None
    db.commit()
    return {**_state(filing, comparison, row, fingerprints), "completed_now": complete and not was_complete}
