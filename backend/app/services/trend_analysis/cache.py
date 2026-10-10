"""Trend narrative version and cache persistence."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session


# Preserve the facade logger name when these functions move.
logger = logging.getLogger("app.services.trend_analysis_service")


# Bump on changes to the live selector prompt or observation rendering. Dataset changes also
# invalidate caches through dataset_fingerprint. The active model selects code-owned observations;
# financial values and comparisons are rendered deterministically.
# v2: derived flag narrowed to true computed-Q4 points, CAGR markers, per-marker signal brackets,
# multi-reference resolver, pp-vs-relative guardrail.
# v3: percent-unit series (margins) report YoY/QoQ as percentage-point deltas (not relative %);
# sign-flip growth renders "n/m" instead of a nonsensical percentage.
# v4: a/an-with-numerals voice guard; rule 5 reworded for the YTD9/shares-based Q4 derivations.
PROMPT_VERSION = "trends-v7-observations"


def _load_cached_analysis(db: Session, company_id: int, mode: str, key: str):
    from app.models import TrendAnalysis

    return (
        db.query(TrendAnalysis)
        .filter(
            TrendAnalysis.company_id == company_id,
            TrendAnalysis.mode == mode,
            TrendAnalysis.period_key == key,
        )
        .first()
    )


def has_cached_analysis(
    db: Session, company_id: int, mode: str, start_period: str, end_period: str
) -> bool:
    """Whether a cached row exists for the naive ``start..end`` key — the router's cheap
    pre-flight probe: over-cap requests with a cached row can only resolve FREE (a cache
    re-serve or a system-invalidated regeneration), so they may proceed past the 429 gate.

    Conservative on purpose: ``build_dataset`` canonicalizes the period key from the actual data
    buckets, which can differ from the raw request range (e.g. the requested start year has no
    data) — a miss here just means the gate stays closed, never that quota leaks."""
    return _load_cached_analysis(db, company_id, mode, f"{start_period}..{end_period}") is not None


def _persist_analysis(
    *,
    company_id: int,
    mode: str,
    key: str,
    fingerprint: str,
    dataset: dict[str, Any],
    narrative: str,
    citations: list[dict[str, Any]],
    model: Optional[str],
    grounded: int,
    unverified: int,
    user_id: Optional[int],
) -> Optional[int]:
    """Upsert the cached analysis row on (company, mode, period_key) in a fresh session (the SSE
    generator outlives the request session). Best-effort: a persistence failure must never break
    the stream the user already received — it only costs the next request a regeneration."""
    from sqlalchemy.exc import IntegrityError

    from app.database import SessionLocal
    from app.models import TrendAnalysis

    db = SessionLocal()
    try:
        def _apply(row: "TrendAnalysis") -> None:
            row.prompt_version = PROMPT_VERSION
            row.dataset_fingerprint = fingerprint
            row.dataset_json = dataset
            row.narrative_md = narrative
            row.citations_json = citations
            row.model = model
            row.grounded = grounded
            row.unverified = unverified
            row.created_by_user_id = user_id

        row = _load_cached_analysis(db, company_id, mode, key)
        if row is None:
            row = TrendAnalysis(company_id=company_id, mode=mode, period_key=key)
            _apply(row)
            db.add(row)
            try:
                db.commit()
            except IntegrityError:
                # A concurrent generation won the unique key — update its row instead.
                db.rollback()
                row = _load_cached_analysis(db, company_id, mode, key)
                if row is None:
                    return None
                _apply(row)
                db.commit()
        else:
            _apply(row)
            db.commit()
        return row.id
    except Exception:  # noqa: BLE001 - cache write is best-effort
        logger.exception("failed to persist trend analysis for company %s", company_id)
        return None
    finally:
        db.close()
