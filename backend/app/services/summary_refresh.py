"""Version-stale summary selection and the bounded in-place drain (admin endpoint and job script).

One SQL encoding of ``summary_versioning.is_stale`` (pinned against it by
``tests/unit/test_admin_refresh_stale.py``), one breakdown for dry runs, and one drain loop that
regenerates stale rows IN PLACE through the ONE orchestrator with ``force_regenerate=True``
(``summaries.id`` and bookmarks survive; the pipeline's keep-better gate refuses downgrades).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Filing, Summary
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION, is_stale

logger = logging.getLogger(__name__)

Generator = Callable[..., Awaitable[Any]]


def stale_filter(schema_version_lt: Optional[int]):
    """Rows to refresh: missing/behind stamp. schema_version_lt bounds by schema; None = stale vs
    the CURRENT schema+prompt version (covers a prompt-only bump that leaves schema_version equal)."""
    if schema_version_lt is not None:
        return or_(Summary.schema_version.is_(None), Summary.schema_version < schema_version_lt)
    return or_(
        Summary.schema_version.is_(None),
        Summary.schema_version != SUMMARY_SCHEMA_VERSION,
        Summary.prompt_version.is_(None),
        Summary.prompt_version != SUMMARY_PROMPT_VERSION,
    )


def stale_query(db: Session, *, schema_version_lt: Optional[int] = None, filing_type: Optional[str] = None):
    query = (
        db.query(Summary.id, Summary.filing_id, Summary.schema_version, Summary.prompt_version, Filing.filing_type)
        .join(Filing, Filing.id == Summary.filing_id)
        .filter(stale_filter(schema_version_lt))
    )
    if filing_type:
        query = query.filter(Filing.filing_type == filing_type)
    return query


def stale_breakdown(db: Session, *, schema_version_lt: Optional[int] = None,
                    filing_type: Optional[str] = None) -> Dict[str, Any]:
    """Counts only (no prose loaded): the staleness population by stamp pair and by form."""
    by_stamp: Dict[str, int] = {}
    by_form: Dict[str, int] = {}
    total = 0
    for _sid, _fid, schema, prompt, form in stale_query(
        db, schema_version_lt=schema_version_lt, filing_type=filing_type,
    ).yield_per(1000):
        total += 1
        stamp = f"{schema if schema is not None else 'null'}/{prompt or 'null'}"
        by_stamp[stamp] = by_stamp.get(stamp, 0) + 1
        by_form[form or "null"] = by_form.get(form or "null", 0) + 1
    summaries_total = db.query(func.count(Summary.id)).scalar() or 0
    return {
        "current_schema_version": SUMMARY_SCHEMA_VERSION,
        "current_prompt_version": SUMMARY_PROMPT_VERSION,
        "summaries_total": int(summaries_total),
        "stale_total": total,
        "by_stamp": dict(sorted(by_stamp.items())),
        "by_form": dict(sorted(by_form.items())),
    }


async def drain_stale(
    db: Session, *, limit: int, max_seconds: float, schema_version_lt: Optional[int] = None,
    filing_type: Optional[str] = None, generate: Optional[Generator] = None,
    clock: Optional[Callable[[], float]] = None,
) -> Dict[str, Any]:
    """Regenerate up to ``limit`` stale rows in place, stopping before a generation that would
    start after ``max_seconds``; honest per-filing outcomes, never a fabricated "updated".

    Candidates are sampled at random so a filing that keep-better-loses every time cannot wedge
    every batch at a deterministic head-of-line. Each generation runs in the pipeline's own
    sessions; ``db`` here only selects candidates and re-reads their stamps."""
    if generate is None:
        from app.services.summary_generation_service import generate_summary_background
        generate = generate_summary_background
    clock = clock or time.monotonic
    started = clock()
    query = stale_query(db, schema_version_lt=schema_version_lt, filing_type=filing_type)
    stale_total = query.count()
    candidates = [row.filing_id for row in query.order_by(func.random()).limit(max(0, limit)).all()]
    updated: List[int] = []
    kept: List[int] = []
    failed: List[int] = []
    deferred: List[int] = []
    for index, fid in enumerate(candidates):
        if clock() - started > max_seconds:
            deferred = candidates[index:]
            logger.info("refresh-stale: time budget reached after %d attempts; %d deferred", index, len(deferred))
            break
        try:
            await generate(fid, None, force_regenerate=True)
        except Exception:  # noqa: BLE001 - one filing's failure must not abort the batch
            logger.warning("refresh-stale: regeneration failed for filing %s", fid, exc_info=True)
            failed.append(fid)
            continue
        db.commit()  # end this session's read transaction so the fresh SELECT sees the pipeline's commit
        stamp = db.query(Summary.schema_version, Summary.prompt_version).filter(Summary.filing_id == fid).first()
        if stamp is not None and not is_stale(stamp[0], stamp[1]):
            updated.append(fid)
        else:
            kept.append(fid)
    return {
        "stale_total": stale_total,
        "attempted": len(updated) + len(kept) + len(failed),
        "updated": len(updated), "kept_by_gate": len(kept), "failed": len(failed), "deferred": len(deferred),
        "elapsed_seconds": round(clock() - started, 1),
        "updated_filing_ids": updated, "kept_by_gate_filing_ids": kept,
        "failed_filing_ids": failed, "deferred_filing_ids": deferred,
    }
