"""Admin bulk summary maintenance: the FK-safe reset-all and the in-place refresh of stale rows.

Called by ``routers/admin.py`` (POST /api/admin/summaries/reset-all and /summaries/refresh-stale).
The router keeps the admin gate, the batch clamp, the reset-all audit row and log, and the response
shape. Generation goes through the ONE orchestrator (``generate_summary_background``); this module
never generates on its own.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Filing, SavedSummary, Summary, SummaryGenerationProgress, User
from app.services import audit_service
from app.services.summary_refresh import generation_failed, stale_filter
from app.services.summary_versioning import is_stale

logger = logging.getLogger(__name__)


def _chunked(seq, size=900):
    """Yield successive `size`-length slices so a bulk IN(...) can't exceed a DB parameter cap
    (SQLite's 999, PostgreSQL's bind-parameter ceiling)."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


@dataclass(frozen=True)
class ResetAllPlan:
    """What a reset-all would delete: the matched summaries minus the bookmarked ones it skips."""

    include_saved: bool
    total_matched: int
    delete_ids: list[int]
    delete_filing_ids: list[int]
    skipped_saved: list[dict]


def select_reset_candidates(db: Session, *, filing_type: Optional[str], include_saved: bool) -> ResetAllPlan:
    """Read-only: the summaries a reset-all matches, split into those to delete and the bookmarked
    (``saved_summaries``) ones that are skipped unless ``include_saved``."""
    # Select only the columns we need (id + filing_id). Summary has large JSON/text columns we
    # never read here, so loading full ORM objects for a bulk op wastes memory + DB I/O.
    query = db.query(Summary.id, Summary.filing_id)
    if filing_type:
        query = query.join(Filing, Filing.id == Summary.filing_id).filter(
            Filing.filing_type == filing_type
        )
    summaries = query.all()

    # Pinned (saved) summaries, scoped to the same filter so we don't load every bookmark in the DB.
    pinned_query = db.query(SavedSummary.summary_id).join(
        Summary, Summary.id == SavedSummary.summary_id
    )
    if filing_type:
        pinned_query = pinned_query.join(Filing, Filing.id == Summary.filing_id).filter(
            Filing.filing_type == filing_type
        )
    pinned_ids = {sid for (sid,) in pinned_query.all()}

    to_delete = [s for s in summaries if include_saved or s.id not in pinned_ids]
    skipped = [s for s in summaries if not include_saved and s.id in pinned_ids]

    delete_ids = [s.id for s in to_delete]
    delete_filing_ids = sorted({s.filing_id for s in to_delete})
    skipped_saved = [{"filing_id": s.filing_id, "summary_id": s.id} for s in skipped]
    return ResetAllPlan(
        include_saved=include_saved,
        total_matched=len(summaries),
        delete_ids=delete_ids,
        delete_filing_ids=delete_filing_ids,
        skipped_saved=skipped_saved,
    )


def delete_summaries(db: Session, plan: ResetAllPlan) -> None:
    """Delete the plan's summaries (and their progress rows; with ``include_saved``, their bookmarks
    first) in FK-safe order, chunked, in one commit."""
    delete_ids = plan.delete_ids
    delete_filing_ids = plan.delete_filing_ids
    # Chunk every IN-list so a large reset can't exceed a DB parameter cap (SQLite's 999, etc.).
    # When including saved summaries, drop their bookmarks first so the FK doesn't block.
    if plan.include_saved:
        for chunk in _chunked(delete_ids):
            db.query(SavedSummary).filter(
                SavedSummary.summary_id.in_(chunk)
            ).delete(synchronize_session=False)
    # Clear progress so regeneration starts clean (XBRL + content cache are intentionally kept).
    for chunk in _chunked(delete_filing_ids):
        db.query(SummaryGenerationProgress).filter(
            SummaryGenerationProgress.filing_id.in_(chunk)
        ).delete(synchronize_session=False)
    for chunk in _chunked(delete_ids):
        db.query(Summary).filter(Summary.id.in_(chunk)).delete(synchronize_session=False)
    db.commit()


# One SQL encoding of staleness, shared with the job-side drain (scripts/refresh_stale_summaries.py).
_stale_summary_filter = stale_filter


def select_stale_candidates(
    db: Session,
    *,
    schema_version_lt: Optional[int],
    filing_type: Optional[str],
    limit: int,
) -> tuple[int, list[int]]:
    """Read-only: (every stale summary's count, up to ``limit`` randomly sampled candidate filing ids)."""
    query = (
        db.query(Summary.id, Summary.filing_id, Summary.schema_version, Summary.prompt_version)
        .join(Filing, Filing.id == Summary.filing_id)
        .filter(_stale_summary_filter(schema_version_lt))
    )
    if filing_type:
        query = query.filter(Filing.filing_type == filing_type)
    stale_total = query.count()
    # Randomized order (not filing_date DESC): a filing that keep-better-loses every time would
    # otherwise park itself at a deterministic head-of-line and wedge every subsequent batch. Random
    # sampling turns a permanent wedge into a diminishing nuisance.
    candidates = query.order_by(func.random()).limit(limit).all()
    candidate_filing_ids = [c.filing_id for c in candidates]
    return stale_total, candidate_filing_ids


async def regenerate_in_place(
    db: Session,
    candidate_filing_ids: list[int],
    *,
    actor: User,
    filing_type: Optional[str],
    schema_version_lt: Optional[int],
    stale_total: int,
) -> tuple[list[int], list[int], list[int]]:
    """Regenerate each candidate in place, sequentially, through the ONE orchestrator, then write the
    audit row. Returns (updated, kept_by_gate, failed) filing ids."""
    from app.services.summary_generation_service import generate_summary_background

    # Honest per-filing outcomes: a keep-better gate-keep regenerates nothing (the stored better
    # version stays), so counting every non-raising call as "regenerated" would report progress the
    # batch didn't make while the stale_total never moves. Classify by re-reading the row's stamps.
    updated: list[int] = []
    kept_by_gate: list[int] = []
    failed: list[int] = []

    # Guard the admin session against N+1 re-expiry across the loop's own commits; generation
    # runs in the pipeline's OWN sessions, so this only protects rows/audit held here.
    prev_expire = db.expire_on_commit
    db.expire_on_commit = False
    try:
        for fid in candidate_filing_ids:
            try:
                outcome = await generate_summary_background(fid, None, force_regenerate=True)
            except Exception:  # noqa: BLE001 — one filing's failure must not abort the batch
                logger.warning("refresh-stale: regeneration failed for filing %s", fid, exc_info=True)
                failed.append(fid)
                continue
            if generation_failed(outcome):  # a terminal error event is a failed paid attempt, not a gate keep
                logger.warning("refresh-stale: generation ended in a terminal error for filing %s", fid)
                failed.append(fid)
                continue
            # Re-read the (separately-committed) row's stamps: current => actually updated;
            # still stale => the keep-better gate kept the stored version (not regenerated).
            # Commit first to end this session's read transaction so the fresh SELECT sees the
            # generation session's commit (no writes pending here, so it's a transaction reset).
            db.commit()
            stamp = (
                db.query(Summary.schema_version, Summary.prompt_version)
                .filter(Summary.filing_id == fid)
                .first()
            )
            if stamp is not None and not is_stale(stamp[0], stamp[1]):
                updated.append(fid)
            else:
                kept_by_gate.append(fid)
        audit_service.create_audit_log(
            db=db,
            action="summaries_refresh_stale",
            user_id=actor.id,
            user_email=getattr(actor, "email", None),
            entity_type="summaries",
            details={
                "filing_type": filing_type,
                "schema_version_lt": schema_version_lt,
                "stale_total": stale_total,
                "updated_count": len(updated),
                "kept_by_gate_count": len(kept_by_gate),
                "failed_count": len(failed),
            },
            status="success",
        )
    finally:
        db.expire_on_commit = prev_expire
    return updated, kept_by_gate, failed
