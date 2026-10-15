"""A reader's review of one filing section's wording changes (the Pro review queue, E27 / PR B).

One row per (user, filing, section). ``labels`` maps a change's content-addressed id
(``section_diff``: stable while the two paragraphs' wording is unchanged) to ``reviewed`` or
``follow_up``; ids that a re-extraction or a diff-engine bump retires are dropped on the next
write and ignored on read. The review is complete when every change of the current comparison
carries a label; ``completed_at`` and the ``receipt`` (the two texts' fingerprints, the engine
and extractor versions, the counts and the follow-ups, frozen at that moment) are set then and
cleared again if a label is removed. ``section_review_service`` is the only writer.

Existing databases get this table from ``migrations/20261013_section_reviews.sql``; fresh ones
from ``create_all``.
"""
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class SectionReview(Base):
    __tablename__ = "section_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "filing_id", "section", name="uq_section_reviews_user_filing_section"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filing_id = Column(Integer, ForeignKey("filings.id", ondelete="CASCADE"), nullable=False, index=True)
    section = Column(String(32), nullable=False)
    # change id -> "reviewed" | "follow_up"; always replaced whole, never mutated in place.
    labels = Column(JSON, nullable=False, default=dict)
    # The diff engine the labels were made against (section_diff.ENGINE_VERSION at the last write).
    engine_version = Column(SmallInteger, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    receipt = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
