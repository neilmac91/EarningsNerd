"""Compatibility facade for Multi-Period Analysis.

The trend_analysis package owns datasets, observations, citations and cached narrative streaming.
Keep the original module exports available to callers while those implementations move.
"""
from __future__ import annotations

import hashlib  # noqa: F401 - retained facade import
import json  # noqa: F401 - retained facade import
import logging  # noqa: F401 - retained facade import
import re  # noqa: F401 - retained facade import
from dataclasses import dataclass  # noqa: F401 - retained facade import
from datetime import date  # noqa: F401 - retained facade import
from decimal import Decimal  # noqa: F401 - retained facade import
from typing import Any, Optional  # noqa: F401 - retained facade import

from sqlalchemy.orm import Session  # noqa: F401 - retained facade import

from app.config import settings  # noqa: F401 - retained facade import
from app.models import Company, FinancialFact  # noqa: F401 - retained facade import
from app.services import citation_markers  # noqa: F401 - retained facade import
from app.services.ai.copilot_chat import merge_chat_usage  # noqa: F401 - retained facade import
from app.services.fact_provenance import (  # noqa: F401 - retained facade import
    CALCULATION_VERSION, calculated_provenance,
)

from app.services.trend_analysis.dataset_quality import add_comparisons, dataset_point  # noqa: F401 - retained facade import
from app.services.trend_analysis.stream_events import analysis_completion  # noqa: F401 - retained facade import
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


from app.services.trend_analysis.narrative import stream_trend_narrative


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
