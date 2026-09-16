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
from app.services.summary_versioning import SUMMARY_PROMPT_VERSION, SUMMARY_SCHEMA_VERSION

logger = logging.getLogger(__name__)

Generator = Callable[..., Awaitable[Any]]
SessionFactory = Callable[[], Session]


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


def check_schema_threshold(schema_version_lt: Optional[int]) -> None:
    """A threshold above the current schema can never be satisfied by a regeneration (the
    pipeline stamps the current schema), so every refreshed row would be selected and paid for
    again on the next execution. Refuse it up front."""
    if schema_version_lt is not None and schema_version_lt > SUMMARY_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version_lt={schema_version_lt} exceeds the current schema version {SUMMARY_SCHEMA_VERSION}; "
            "a regeneration could never leave that filter"
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
    check_schema_threshold(schema_version_lt)
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


def generation_failed(result: Any) -> bool:
    """The orchestrator converts exceptions into a terminal ``error`` event instead of raising;
    ``generate_summary_background`` returns that event, and a paid attempt that ended there is a
    failure, never a keep-better decision."""
    return isinstance(result, dict) and result.get("type") == "error"


async def drain_stale(
    session_factory: SessionFactory, *, limit: int, max_seconds: float, schema_version_lt: Optional[int] = None,
    filing_type: Optional[str] = None, generate: Optional[Generator] = None,
    clock: Optional[Callable[[], float]] = None,
) -> Dict[str, Any]:
    """Regenerate up to ``limit`` stale rows in place, stopping before a generation that would
    start after ``max_seconds``; honest per-filing outcomes, never a fabricated "updated".

    Candidates are sampled at random so a filing that keep-better-loses every time cannot wedge
    every batch at a deterministic head-of-line. No session or pooled connection is held while a
    generation runs: selection and every stamp re-read use their own short-lived session, and the
    generation runs in the pipeline's own sessions."""
    check_schema_threshold(schema_version_lt)
    if generate is None:
        from app.services.summary_generation_service import generate_summary_background
        generate = generate_summary_background
    clock = clock or time.monotonic
    started = clock()
    with session_factory() as db:
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
            result = await generate(fid, None, force_regenerate=True)
        except Exception:  # noqa: BLE001 - one filing's failure must not abort the batch
            logger.warning("refresh-stale: regeneration failed for filing %s", fid, exc_info=True)
            failed.append(fid)
            continue
        if generation_failed(result):
            logger.warning("refresh-stale: generation ended in a terminal error for filing %s", fid)
            failed.append(fid)
            continue
        with session_factory() as db:  # a fresh transaction sees the pipeline's commit
            still_stale = (
                db.query(Summary.id).filter(Summary.filing_id == fid).filter(stale_filter(schema_version_lt)).first()
                is not None
            )
        (kept if still_stale else updated).append(fid)
    return {
        "stale_total": stale_total,
        "attempted": len(updated) + len(kept) + len(failed),
        "updated": len(updated), "kept_by_gate": len(kept), "failed": len(failed), "deferred": len(deferred),
        "elapsed_seconds": round(clock() - started, 1),
        "updated_filing_ids": updated, "kept_by_gate_filing_ids": kept,
        "failed_filing_ids": failed, "deferred_filing_ids": deferred,
    }
