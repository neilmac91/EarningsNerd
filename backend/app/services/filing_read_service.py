"""Single-filing and recent-filing reads behind ``app/routers/filings.py``.

Moved verbatim from the router (specific filing, its cached content, its fundamentals, recent
filings) so it stays HTTP only. Each function is one synchronous unit on the request's session,
run where the router used to run it (on the event loop): it reads, builds the response payload with
the caller's converter, and closes the session in the same unit, so the pooled connection is back
before the async route yields to the sync dependency's thread-pool finalizer
(``lessons/ops-release-cached-filing-reads-before-yield.md``;
``tests/unit/test_cached_filings_pool_lifetime.py``). The converters stay with the router's
response models. A missing filing is a ``None`` return; the router raises its unchanged 404.
"""
from typing import Any, Callable, List, Optional, TypeVar

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.models import Filing

T = TypeVar("T")


def filing_by_id(db: Session, filing_id: int, convert: Callable[[Filing], T]) -> Optional[T]:
    """The converted filing (company eagerly loaded), or None; releases the session either way."""
    try:
        filing = db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
        if not filing:
            return None
        return convert(filing)
    finally:
        db.close()


def filing_content(db: Session, filing_id: int, build: Callable[[Optional[str]], T]) -> Optional[T]:
    """``build(markdown)`` for the filing's cached markdown (None when it has none yet), or None when
    the filing does not exist; releases the session either way."""
    try:
        filing = (
            db.query(Filing)
            .options(joinedload(Filing.content_cache))
            .filter(Filing.id == filing_id)
            .first()
        )
        if not filing:
            return None

        cache = filing.content_cache
        markdown = getattr(cache, "markdown_content", None) if cache else None
        return build(markdown)
    finally:
        db.close()


def filing_fundamentals(db: Session, filing_id: int) -> Optional[dict[str, Any]]:
    """The filing's as-reported fundamentals payload, or None; releases the session either way."""
    from app.services import facts_service

    try:
        return facts_service.get_filing_fundamentals(db, filing_id)
    finally:
        db.close()


def recent_filings(db: Session, limit: int, convert: Callable[[Filing], T]) -> List[T]:
    """The newest ``limit`` filings across all companies, converted; releases the session."""
    # Use joinedload to eagerly load company relationship, avoiding N+1 queries
    try:
        filings = db.query(Filing).options(joinedload(Filing.company)).order_by(desc(Filing.filing_date)).limit(limit).all()
        return [convert(filing) for filing in filings]
    finally:
        db.close()
