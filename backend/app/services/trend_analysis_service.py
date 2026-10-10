"""Multi-Period Analysis — the deterministic engine (M2).

Assembles a company's N-period dataset from ``financial_fact`` (one indexed read), computes every
number the product shows or the AI narrates — YoY/QoQ deltas, CAGR, margin/liquidity series, and
deterministic "inflection" signals — and assigns each value a stable ``F#`` citation marker. The
LLM (M3) receives this dataset verbatim and may only cite markers it was given; it NEVER does
arithmetic. That split (server math, model prose) is the same grounding contract Copilot uses.

Readers filter ``fiscal_period == "FY"`` (annual) / ``IN Q1..Q4`` (quarterly), so legacy
NULL-fiscal_period rows can never surface here (D1). Quarterly balance-sheet columns select
instant concepts by ``period_end`` — the fiscal-year-end balance sheet IS the Q4 instant, stored
once under its FY label (D2c).
"""
from __future__ import annotations

import hashlib  # noqa: F401 - retained facade import
import json
import logging  # noqa: F401 - retained facade import
import re  # noqa: F401 - retained facade import
from dataclasses import dataclass  # noqa: F401 - retained facade import
from datetime import date  # noqa: F401 - retained facade import
from decimal import Decimal  # noqa: F401 - retained facade import
from typing import Any, Optional  # noqa: F401 - retained facade import

from sqlalchemy.orm import Session  # noqa: F401 - retained facade import

from app.config import settings
from app.models import Company, FinancialFact  # noqa: F401 - retained facade import
from app.services import citation_markers  # noqa: F401 - retained facade import
from app.services.ai.copilot_chat import merge_chat_usage
from app.services.fact_provenance import (  # noqa: F401 - retained facade import
    CALCULATION_VERSION, calculated_provenance,
)

from app.services.trend_analysis.dataset_quality import add_comparisons, dataset_point  # noqa: F401 - retained facade import
from app.services.trend_analysis.stream_events import analysis_completion
from app.utils.datetimes import ensure_utc, iso_z  # noqa: F401 - retained facade import

# Compatibility facade: keep every original definition available at this module path.
from app.services.trend_analysis.periods import (
    MODES,
    _QUARTERS,
    DATASET_CONCEPT_ORDER,
    _CONCEPT_LABELS,
    concept_label,
    _ANNUAL_KEY_RE,
    _QUARTER_KEY_RE,
    parse_period_key,
    _period_sort_key,
    _CORE_REVENUE_CONCEPTS,
    available_periods,
)
from app.services.trend_analysis.formatting import (
    NOT_MEANINGFUL,
    _format_value,
    _pct_str,
    _fmt_growth,
    _ratio_threshold_value,
    _ordered_percentage_values,
)
from app.services.trend_analysis.series import (
    _series_map,
    _valued_points,
    _growth_operand_points,
    _growth_operand_markers,
)
from app.services.trend_analysis.detectors import (
    detect_growth_deceleration,
    detect_margin_compression,
    detect_fcf_ni_divergence,
    detect_debt_build,
    detect_liquidity_squeeze,
    _DETECTORS,
    detect_inflections,
)
from app.services.trend_analysis.citations import (
    _MARKER_GROUP_RE,
    _MARKER_REF_RE,
    _is_citation_group,
    _point_citation,
    resolve_narrative_citations,
)
from app.services.trend_analysis.fidelity import (
    _FIDELITY_NUM_RE,
    _FIDELITY_SCALES,
    _FIDELITY_WINDOW_CHARS,
    _FIDELITY_MARKER_RE,
    _window_number_tokens,
    _fidelity_candidates,
    _token_matches_any,
    scan_numeric_fidelity,
)
from app.services.trend_analysis.cache import (
    logger,
    PROMPT_VERSION,
    _load_cached_analysis,
    has_cached_analysis,
    _persist_analysis,
)

from app.services.trend_analysis.dataset import (
    INSTANT_CONCEPTS,
    _PERCENT_CONCEPTS,
    _SERIES_TONE,
    _growth,
    _pp_delta,
    _cagr,
    _valued_endpoints,
    build_dataset,
    dataset_fingerprint,
    _has_minimum_analysis_data,
    marker_index,
)
from app.services.trend_analysis.observations import (
    ANALYSIS_SECTIONS,
    _SECTION_KEYS,
    _OPTIONAL_PER_SECTION,
    _SELECTION_TOTAL_LIMIT,
    TrendObservation,
    _observation_id,
    _point_value,
    _same_dimension,
    _growth_comparison_values,
    _marker_chain,
    _derived_qualifier,
    build_observation_catalogue,
    compact_observation_catalogue,
    _strict_json,
    parse_observation_selection,
    render_observation_selection,
)


async def stream_trend_narrative(
    *,
    company_id: int,
    mode: str,
    start_period: str,
    end_period: str,
    force: bool = False,
    user_id: Optional[int] = None,
):
    """Transport-agnostic narrative pipeline: yields plain event dicts for the SSE route.

    Event contract (the Copilot shapes, so frontend consumers share plumbing):
      {"type": "progress", "stage", "message", "percent"}
      {"type": "token", "text"}                              (fresh generations only)
      {"type": "complete", "kind": "analysis" | "not_enough_data", "analysis_id", "narrative",
       "citations", "grounded", "cached", "n_periods", "usage"}
      {"type": "error", "message"}

    Cache-first (D4): if a row matches (company, mode, period_key) with the same prompt_version
    AND dataset_fingerprint, its narrative is re-served instantly — no model call, no meter (the
    router meters only non-cached "analysis" completions). ``force`` always regenerates.
    Opens its own sessions: the request's session is gone by the time this generator runs.
    """
    from app.database import SessionLocal
    from app.services.openai_service import STREAM_ERROR_SENTINEL, openai_service
    from app.services.prompt_loader import get_named_prompt

    yield {"type": "progress", "stage": "assembling", "message": "Assembling the numbers…", "percent": 10}

    db = SessionLocal()
    try:
        company = db.get(Company, company_id)
        if company is None:
            yield {"type": "error", "message": "Company not found."}
            return
        ticker = company.ticker
        try:
            dataset = build_dataset(db, company, mode, start_period, end_period)
        except ValueError as exc:
            yield {"type": "error", "message": str(exc)}
            return
        fingerprint = dataset_fingerprint(dataset)
        key = dataset["period_key"]
        cached = _load_cached_analysis(db, company_id, mode, key)
        if (
            not force
            and cached is not None
            and cached.narrative_md
            and cached.prompt_version == PROMPT_VERSION
            and cached.dataset_fingerprint == fingerprint
        ):
            cached_citations = cached.citations_json or []
            cached_mismatched = scan_numeric_fidelity(
                cached.narrative_md,
                cached_citations,
                marker_index(dataset),
            )
            yield analysis_completion(
                dataset, analysis_id=cached.id, narrative=cached.narrative_md,
                citations=cached_citations, grounded=cached.grounded, unverified=cached.unverified,
                mismatched=len(cached_mismatched), cached=True, invalidated=False, usage={},
            )
            return
        # A cached row existed but no longer matches (prompt bump or new facts): this regeneration
        # is system-triggered, not user-triggered — the router exempts it from the fair-use meter.
        # A `force` refresh is user-initiated and stays metered.
        invalidated = cached is not None and not force
    finally:
        # Never hold a DB connection through the model call.
        db.close()

    yield {"type": "progress", "stage": "writing", "message": "Writing the analysis…", "percent": 30}

    if not _has_minimum_analysis_data(dataset):
        yield {
            "type": "complete",
            "kind": "not_enough_data",
            "analysis_id": None,
            "narrative": "",
            "citations": [],
            "grounded": 0,
            "unverified": 0,
            "cached": False,
            "invalidated": invalidated,
            "n_periods": len(dataset["periods"]),
            "usage": {},
        }
        return

    prompt = get_named_prompt("trends-analyst-agent")
    catalogue = build_observation_catalogue(dataset)
    selection_shape = json.dumps({key: [] for key, _ in ANALYSIS_SECTIONS}, separators=(",", ":"))
    base_messages = [
        {"role": "system", "content": prompt.raw},
        {
            "role": "user",
            "content": (
                compact_observation_catalogue(catalogue)
                + "\n\nReturn exactly one JSON object with this shape and no other text:\n"
                + selection_shape
            ),
        },
    ]

    index = marker_index(dataset)
    model_name = openai_service.model
    total_usage: dict[str, Any] = {}
    selection: Optional[dict[str, list[str]]] = None

    # The model may rank only catalogue IDs.  Its raw chunks are never user-visible.  One retry is
    # retained for malformed selection JSON; usage still sums every physical model call.
    for attempt in range(2):
        messages = list(base_messages)
        if attempt:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The prior reply was rejected. Return only the complete JSON object with "
                        "all six required keys. Every value must be a list of at most three IDs "
                        "from that key's section; do not add prose, fields, or replacement text."
                    ),
                }
            )
            yield {
                "type": "progress",
                "stage": "verifying",
                "message": "Re-checking the selection…",
                "percent": 80,
            }

        usage_sink: dict[str, Any] = {}
        parts: list[str] = []
        stream_failed = False
        async for chunk in openai_service.stream_chat(
            messages,
            max_tokens=settings.ANALYSIS_MAX_TOKENS,
            temperature=0.2,
            usage_sink=usage_sink,
        ):
            if chunk.startswith(STREAM_ERROR_SENTINEL):
                detail = chunk[len(STREAM_ERROR_SENTINEL):]
                logger.warning("trend observation selection stream failed for %s: %s", ticker, detail)
                stream_failed = True
                break
            parts.append(chunk)
            if len(parts) % 40 == 0:
                yield {
                    "type": "progress",
                    "stage": "writing" if attempt == 0 else "verifying",
                    "message": "Selecting grounded observations…",
                    "percent": 60 if attempt == 0 else 85,
                }
        merge_chat_usage(total_usage, usage_sink)
        if stream_failed:
            yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
            return

        candidate_text = "".join(parts).strip()
        selection = parse_observation_selection(candidate_text, catalogue)
        if selection is not None:
            break
    if selection is None:
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return

    code_narrative = render_observation_selection(catalogue, selection)
    narrative, citations, grounded, unverified = resolve_narrative_citations(code_narrative, index)
    mismatched = scan_numeric_fidelity(narrative, citations, index)
    if unverified or mismatched:
        logger.error(
            "code-owned trend observations failed citation fidelity for %s (%s %s): "
            "unverified=%d mismatched=%s",
            ticker, mode, key, unverified, mismatched,
        )
        yield {"type": "error", "message": "The analysis could not be generated. Please try again."}
        return

    # The sole token payload is emitted only after strict selection validation and code rendering.
    yield {"type": "token", "text": narrative}
    analysis_id = _persist_analysis(
        company_id=company_id,
        mode=mode,
        key=key,
        fingerprint=fingerprint,
        dataset=dataset,
        narrative=narrative,
        citations=citations,
        model=model_name,
        grounded=grounded,
        unverified=unverified,
        user_id=user_id,
    )
    yield analysis_completion(
        dataset, analysis_id=analysis_id, narrative=narrative, citations=citations,
        grounded=grounded, unverified=unverified, mismatched=len(mismatched),
        cached=False, invalidated=invalidated, usage=total_usage,
    )


__all__ = [
    "logger",
    "PROMPT_VERSION",
    "MODES",
    "_QUARTERS",
    "INSTANT_CONCEPTS",
    "_PERCENT_CONCEPTS",
    "_SERIES_TONE",
    "DATASET_CONCEPT_ORDER",
    "_CONCEPT_LABELS",
    "concept_label",
    "_ANNUAL_KEY_RE",
    "_QUARTER_KEY_RE",
    "parse_period_key",
    "_period_sort_key",
    "_CORE_REVENUE_CONCEPTS",
    "available_periods",
    "NOT_MEANINGFUL",
    "_growth",
    "_pp_delta",
    "_cagr",
    "_valued_endpoints",
    "build_dataset",
    "_series_map",
    "_valued_points",
    "detect_growth_deceleration",
    "detect_margin_compression",
    "detect_fcf_ni_divergence",
    "detect_debt_build",
    "detect_liquidity_squeeze",
    "_DETECTORS",
    "detect_inflections",
    "dataset_fingerprint",
    "_format_value",
    "_pct_str",
    "_fmt_growth",
    "ANALYSIS_SECTIONS",
    "_SECTION_KEYS",
    "_OPTIONAL_PER_SECTION",
    "_SELECTION_TOTAL_LIMIT",
    "TrendObservation",
    "_observation_id",
    "_ratio_threshold_value",
    "_point_value",
    "_same_dimension",
    "_ordered_percentage_values",
    "_growth_comparison_values",
    "_growth_operand_points",
    "_growth_operand_markers",
    "_marker_chain",
    "_derived_qualifier",
    "build_observation_catalogue",
    "compact_observation_catalogue",
    "_strict_json",
    "parse_observation_selection",
    "render_observation_selection",
    "_has_minimum_analysis_data",
    "marker_index",
    "_MARKER_GROUP_RE",
    "_MARKER_REF_RE",
    "_is_citation_group",
    "_point_citation",
    "resolve_narrative_citations",
    "_FIDELITY_NUM_RE",
    "_FIDELITY_SCALES",
    "_FIDELITY_WINDOW_CHARS",
    "_FIDELITY_MARKER_RE",
    "_window_number_tokens",
    "_fidelity_candidates",
    "_token_matches_any",
    "scan_numeric_fidelity",
    "_load_cached_analysis",
    "has_cached_analysis",
    "_persist_analysis",
    "stream_trend_narrative",
]
