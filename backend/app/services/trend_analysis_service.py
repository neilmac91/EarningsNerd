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

import hashlib
import json
import logging  # noqa: F401 - retained facade import
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal  # noqa: F401 - retained facade import
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, FinancialFact
from app.services import citation_markers  # noqa: F401 - retained facade import
from app.services.ai.copilot_chat import merge_chat_usage
from app.services.fact_provenance import (
    CALCULATION_VERSION, calculated_provenance,
)

from app.services.trend_analysis.dataset_quality import add_comparisons, dataset_point
from app.services.trend_analysis.stream_events import analysis_completion
from app.utils.datetimes import ensure_utc, iso_z

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

# Balance-sheet (point-in-time) concepts + their derived metrics: matched by period_end in
# quarterly mode; everything else is a flow/duration concept matched by (fiscal_year, fiscal_period).
INSTANT_CONCEPTS: frozenset[str] = frozenset(
    {
        "total_assets", "cash_and_equivalents", "shareholders_equity", "long_term_debt",
        "current_assets", "current_liabilities", "working_capital", "current_ratio",
    }
)

# Margin concepts are stored ×100 (percent); current_ratio is a plain ratio.
_PERCENT_CONCEPTS: frozenset[str] = frozenset({"net_margin", "gross_margin", "operating_margin"})

# Display valence per concept, shipped on each series as `tone` — the same dataset-as-source-of-
# truth pattern as `percent`, so the frontend never re-derives which concepts read inverted or
# neutral. "inverted": an increase is a cost/risk signal (the same judgment detect_debt_build
# encodes); "neutral": the direction is a strategic choice (a capex ramp, an investing/financing
# swing), not inherently good or bad. Everything else defaults to "normal" (up = good).
_SERIES_TONE: dict[str, str] = {
    "long_term_debt": "inverted",
    "current_liabilities": "inverted",
    "capital_expenditures": "neutral",
    "investing_cash_flow": "neutral",
    "financing_cash_flow": "neutral",
}


def _growth(current: Optional[float], prior: Optional[float]) -> Optional[float] | str:
    """Fractional growth with the compute_metric edge discipline: no prior / zero prior → None.
    Opposite-signed current/prior → NOT_MEANINGFUL (a swing through zero, not a real up/down
    move — same-sign moves of any magnitude, even a large one off a small base, stay real growth)."""
    if current is None or prior is None or prior == 0:
        return None
    if current != 0 and (current > 0) != (prior > 0):
        return NOT_MEANINGFUL
    return (current - prior) / abs(prior)


def _pp_delta(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    """Percentage-POINT delta for percent-unit series (margins, stored ×100): current − prior.
    Never divides, so it never "explodes" the way relative growth can — a 47.3% → 38.3% move is
    simply -9.0pp, always sane — and needs no NOT_MEANINGFUL guard."""
    if current is None or prior is None:
        return None
    return current - prior


def _cagr(first: float, last: float, years: int) -> Optional[float]:
    """Compound annual growth rate; only defined for positive endpoints over ≥1 year."""
    if years < 1 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / years) - 1.0


def _valued_endpoints(
    periods: list[dict[str, Any]], points: list[dict[str, Any]]
) -> Optional[tuple[tuple[int, float], tuple[int, float]]]:
    """First/last ``(fiscal_year, value)`` over a series' non-null points — the ONE endpoint-
    selection rule for every annual window figure (CAGR and window_pp), so the two can't drift.
    Returns ``None`` when fewer than two valued points exist (no window to measure)."""
    valued = [
        (bucket["fiscal_year"], point["value"])
        for bucket, point in zip(periods, points)
        if point["value"] is not None
    ]
    if len(valued) < 2:
        return None
    return valued[0], valued[-1]


def build_dataset(
    db: Session,
    company: Company,
    mode: str,
    start_period: str,
    end_period: str,
) -> dict[str, Any]:
    """Assemble the aligned N-period dataset for one company (pure DB read + arithmetic).

    Raises ``ValueError`` for a bad mode/range (the router maps it to 400). Every value point gets
    a stable ``F#`` marker (series order × period order over non-null values) — the only citation
    currency the AI narrative is allowed to spend.
    """
    if mode not in MODES:
        raise ValueError(f"Invalid mode: {mode!r} (expected 'annual' or 'quarterly')")
    start_fy, start_fp = parse_period_key(mode, start_period)
    end_fy, end_fp = parse_period_key(mode, end_period)

    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.company_id == company.id,
            FinancialFact.is_latest.is_(True),
            FinancialFact.fiscal_period.isnot(None),
        )
        .order_by(FinancialFact.period_end.asc())
        .all()
    )

    # Indexes: flows by (fiscal_year, fiscal_period); instants ALSO by period_end (D2c).
    by_fy_fp: dict[tuple[int, str, str], FinancialFact] = {}
    instant_by_end: dict[tuple[str, date], FinancialFact] = {}
    for row in rows:
        if row.fiscal_year is None:
            continue
        by_fy_fp[(row.fiscal_year, row.fiscal_period, row.concept)] = row
        if row.concept in INSTANT_CONCEPTS:
            instant_by_end[(row.concept, row.period_end)] = row

    # Period axis (oldest → newest), range-filtered and capped.
    if mode == "annual":
        buckets = [
            {"key": f"FY{fy}", "fiscal_year": fy, "fiscal_period": "FY", "period_end": end}
            for fy, end in sorted(
                {
                    (row.fiscal_year, row.period_end)
                    for row in rows
                    if row.fiscal_period == "FY" and row.fiscal_year is not None
                    and start_fy <= row.fiscal_year <= end_fy
                },
                key=lambda pair: pair[1],
            )
        ]
        # A fiscal year may appear with several period_ends across concepts; keep the latest.
        deduped: dict[int, dict[str, Any]] = {}
        for bucket in buckets:
            existing = deduped.get(bucket["fiscal_year"])
            if existing is None or bucket["period_end"] > existing["period_end"]:
                deduped[bucket["fiscal_year"]] = bucket
        periods = sorted(deduped.values(), key=lambda b: b["period_end"])
        cap = settings.ANALYSIS_MAX_ANNUAL_PERIODS
    else:
        seen: dict[tuple[int, str], dict[str, Any]] = {}
        for row in rows:
            if row.fiscal_period not in _QUARTERS or row.fiscal_year is None:
                continue
            bucket = seen.setdefault(
                (row.fiscal_year, row.fiscal_period),
                {
                    "key": f"{row.fiscal_year}{row.fiscal_period}",
                    "fiscal_year": row.fiscal_year,
                    "fiscal_period": row.fiscal_period,
                    "period_end": row.period_end,
                },
            )
            bucket["period_end"] = max(bucket["period_end"], row.period_end)
        ordered = sorted(seen.values(), key=_period_sort_key)
        start_key = (start_fy, start_fp)
        end_key = (end_fy, end_fp)
        started = False
        periods = []
        for bucket in ordered:
            if (bucket["fiscal_year"], bucket["fiscal_period"]) == start_key:
                started = True
            if started:
                periods.append(bucket)
            if (bucket["fiscal_year"], bucket["fiscal_period"]) == end_key and started:
                break
        cap = settings.ANALYSIS_MAX_QUARTERLY_PERIODS

    if not periods:
        raise ValueError("No data available for the selected period range.")
    if len(periods) > cap:
        raise ValueError(f"Too many periods selected: {len(periods)} (max {cap} for {mode} mode).")

    def _row_for(concept: str, bucket: dict[str, Any]) -> Optional[FinancialFact]:
        if mode == "quarterly" and concept in INSTANT_CONCEPTS:
            return instant_by_end.get((concept, bucket["period_end"]))
        return by_fy_fp.get((bucket["fiscal_year"], bucket["fiscal_period"], concept))

    series_list: list[dict[str, Any]] = []
    for concept in DATASET_CONCEPT_ORDER:
        points: list[dict[str, Any]] = []
        any_value = False
        for bucket in periods:
            row = _row_for(concept, bucket)
            if row is None:
                points.append({"period": bucket["key"], "value": None})
                continue
            any_value = True
            points.append(dataset_point(row, bucket["key"], getattr(company, "cik", None)))
        if not any_value:
            continue

        unit = next((p["unit"] for p in points if p.get("unit")), "USD")
        is_percent = concept in _PERCENT_CONCEPTS
        # Percent-unit series (margins) report YoY/QoQ as percentage-POINT deltas — the
        # convention finance readers expect for a ratio already expressed as a percentage — never
        # the relative change of the percentage value itself. Everything else keeps relative
        # growth (with the n/m sign-flip guard baked into `_growth`).
        delta_fn = _pp_delta if is_percent else _growth

        add_comparisons(points, periods, mode, is_percent, delta_fn)

        # CAGR over the series' VALUED endpoints (annual mode, monetary/per-share series only).
        # The basis window is recorded because it can be narrower than the selected range (a
        # concept first reported mid-window) — citations must state the window the figure was
        # actually computed over, not the range the user picked.
        cagr = None
        cagr_window = None
        if mode == "annual" and unit != "pure":
            endpoints = _valued_endpoints(periods, points)
            if endpoints:
                (first_fy, first), (last_fy, last) = endpoints
                cagr = _cagr(first, last, last_fy - first_fy)
                if cagr is not None:
                    cagr_window = f"FY{first_fy}..FY{last_fy}"

        # Window pp change over the same valued endpoints — the percent-series counterpart to
        # CAGR (compounding doesn't apply to a percentage), so the annual KPI strip/table has a
        # window figure for margin concepts even though CAGR itself is always null for them
        # (unit == "pure" excludes them from the CAGR block above).
        window_pp = None
        window_pp_range = None
        if mode == "annual" and is_percent:
            endpoints = _valued_endpoints(periods, points)
            if endpoints:
                (first_fy, first_v), (last_fy, last_v) = endpoints
                window_pp = last_v - first_v
                window_pp_range = f"FY{first_fy}..FY{last_fy}"

        valued_points = [p for p in points if p["value"] is not None]
        endpoints_reconciled = bool(valued_points) and all(
            p.get("reconciled") is not False for p in (valued_points[0], valued_points[-1])
        )
        series_list.append(
            {
                "concept": concept,
                "label": concept_label(concept),
                "unit": unit,
                "percent": is_percent,
                "tone": _SERIES_TONE.get(concept, "normal"),
                "cagr": cagr,
                "cagr_window": cagr_window,
                "cagr_reconciled": endpoints_reconciled if cagr is not None else None,
                "cagr_provenance": calculated_provenance(
                    "compound_annual_growth", [valued_points[0], valued_points[-1]]
                ) if cagr is not None else None,
                "window_pp": window_pp,
                "window_pp_range": window_pp_range,
                "window_pp_reconciled": endpoints_reconciled if window_pp is not None else None,
                "window_pp_provenance": calculated_provenance(
                    "percentage_point_change", [valued_points[0], valued_points[-1]]
                ) if window_pp is not None else None,
                "points": points,
            }
        )

    # Stable citation markers over non-null values, in display order.
    marker = 0
    for series in series_list:
        for point in series["points"]:
            if point["value"] is not None:
                marker += 1
                point["marker"] = f"F{marker}"
    # Series-level CAGR gets its own marker (after every point marker, so point numbering is
    # unchanged): it is a server-computed figure the narrative is told to anchor on, and a figure
    # without a marker forces the model to improvise illegal range citations like [F1..F10].
    for series in series_list:
        if series.get("cagr") is not None:
            marker += 1
            series["cagr_marker"] = f"F{marker}"

    dataset: dict[str, Any] = {
        "ticker": company.ticker,
        "company_name": company.name,
        "mode": mode,
        "period_key": f"{periods[0]['key']}..{periods[-1]['key']}",
        "periods": [
            {
                "key": bucket["key"],
                "fiscal_year": bucket["fiscal_year"],
                "fiscal_period": bucket["fiscal_period"],
                "period_end": bucket["period_end"].isoformat(),
            }
            for bucket in periods
        ],
        "series": series_list,
        "dataset_version": CALCULATION_VERSION,
        "data_as_of": (
            iso_z(ensure_utc(company.facts_synced_at)) if getattr(company, "facts_synced_at", None) else None
        ),
    }
    dataset["inflections"] = detect_inflections(dataset)
    dataset["snapshot_id"] = dataset_fingerprint(dataset)
    return dataset


# --- fingerprint + prompt rendering ------------------------------------------------------------


def dataset_fingerprint(dataset: dict[str, Any]) -> str:
    """sha256 of the canonical dataset JSON — new facts (or a changed range) change it, which
    invalidates the cached narrative for that key (D4)."""
    # A refresh that confirms the same source facts must not consume a new AI generation. The
    # self-identifying hash and fetch time are metadata; source/quality/formula changes are not.
    content = {key: value for key, value in dataset.items() if key not in {"snapshot_id", "data_as_of"}}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- code-owned narrative observations ---------------------------------------------------------

ANALYSIS_SECTIONS: tuple[tuple[str, str], ...] = (
    ("trajectory", "The trajectory"),
    ("growth_quality", "Growth quality"),
    ("margins", "Margins"),
    ("cash_balance_sheet", "Cash & balance sheet"),
    ("red_flags", "Red flags"),
    ("watch_next", "What to watch next"),
)
_SECTION_KEYS = frozenset(key for key, _ in ANALYSIS_SECTIONS)
_OPTIONAL_PER_SECTION = 3
_SELECTION_TOTAL_LIMIT = len(ANALYSIS_SECTIONS) * _OPTIONAL_PER_SECTION


@dataclass(frozen=True)
class TrendObservation:
    """One immutable, request-local sentence the model may select only by ID."""

    id: str
    section: str
    markdown: str
    required: bool = False


def _observation_id(section: str, kind: str, *parts: str) -> str:
    clean = [re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") for value in parts]
    return ".".join((section, kind, *filter(None, clean)))


def _point_value(series: dict[str, Any], point: dict[str, Any], *, ratio_precision: bool = False) -> str:
    value = point["value"]
    if ratio_precision:
        # The ordinary two-decimal grid display remains untouched.  The same helper also renders
        # the current-ratio Sources excerpt so the cited evidence and threshold cue agree.
        return _ratio_threshold_value(value)
    rendered = _format_value(value, series["unit"], series["percent"])
    if series["percent"] or series["unit"] == "pure":
        return rendered
    if series["unit"].endswith("/shares"):
        currency = series["unit"].removesuffix("/shares")
        return f"{currency} {rendered} per share"
    return f"{series['unit']} {rendered}"


def _same_dimension(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return first.get("unit") == second.get("unit") and bool(first.get("percent")) == bool(
        second.get("percent")
    )


def _growth_comparison_values(first: float, second: float) -> tuple[str, str, str]:
    """Return the raw-value ordering with displays that make a non-equal ordering visible."""
    if first == second:
        rendered = _pct_str(first)
        return "equal to", rendered, rendered
    relation = "above" if first > second else "below"
    (first_text, second_text), display_is_distinct = _ordered_percentage_values([first, second])
    if display_is_distinct:
        return relation, first_text, second_text
    # Beyond four percentage decimals the values are immaterially different for this product
    # surface. Avoid asserting a direction that the intentionally bounded display cannot show.
    return "effectively equal to", _pct_str(first), _pct_str(second)


def _marker_chain(markers: list[str]) -> str:
    return " ".join(f"[{marker}]" for marker in dict.fromkeys(markers))


def _derived_qualifier(*points: dict[str, Any]) -> str:
    """Label an observation whose stated value or comparison uses a computed Q4 point."""
    return " (derived Q4)" if any(point.get("derived") for point in points) else ""


def build_observation_catalogue(dataset: dict[str, Any]) -> list[TrendObservation]:
    """Build a bounded catalogue of code-rendered claims from the trusted dataset shape.

    The model never supplies text, numbers, periods, markers or a replacement catalogue.  Every
    comparison here binds same-period operands with compatible dimensions.  Missingness is only
    emitted for a null point in the selected latest period.
    """
    by = _series_map(dataset)
    observations: list[TrendObservation] = []
    seen: set[str] = set()

    def add(
        section: str,
        kind: str,
        markdown: str,
        *parts: str,
        required: bool = False,
    ) -> None:
        obs_id = _observation_id(section, kind, *parts)
        if obs_id in seen:
            return
        seen.add(obs_id)
        observations.append(TrendObservation(obs_id, section, markdown, required))

    top = next((by.get(name) for name in ("revenue", "net_interest_income") if by.get(name)), None)
    top_points = _valued_points(top)
    if top and top_points:
        first, latest = top_points[0], top_points[-1]
        add(
            "trajectory", "latest", (
                f"{top['label']} was {_point_value(top, latest)} in {latest['period']} "
                f"[{latest['marker']}]{_derived_qualifier(latest)}."
            ), top["concept"], latest["period"], required=True,
        )
        if first is not latest:
            add(
                "trajectory", "first", (
                    f"The earliest available {top['label'].lower()} observation was "
                    f"{_point_value(top, first)} in {first['period']} [{first['marker']}]"
                    f"{_derived_qualifier(first)}."
                ), top["concept"], first["period"],
            )
        if top.get("cagr") is not None and top.get("cagr_marker"):
            add(
                "trajectory", "cagr", (
                    f"{top['label']} CAGR was {_pct_str(top['cagr'])} over "
                    f"{top.get('cagr_window') or dataset['period_key']} [{top['cagr_marker']}]"
                    f"{_derived_qualifier(first, latest)}."
                ), top["concept"], top.get("cagr_window") or dataset["period_key"], required=True,
            )

        growth_points = [p for p in top_points if isinstance(p.get("yoy"), float)][-3:]
        for point in growth_points:
            add(
                "growth_quality", "growth", (
                    f"{top['label']} growth in {point['period']} was "
                    f"{_fmt_growth(point['yoy'], top['percent'])} "
                    f"{_marker_chain(_growth_operand_markers(dataset, top, point))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, top, point))}."
                ), top["concept"], point["period"], required=point is growth_points[-1],
            )

    net_income = by.get("net_income")
    ni_points = _valued_points(net_income)
    if net_income and ni_points:
        latest_ni = ni_points[-1]
        add(
            "trajectory", "latest", (
                f"Net income was {_point_value(net_income, latest_ni)} in {latest_ni['period']} "
                f"[{latest_ni['marker']}]{_derived_qualifier(latest_ni)}."
            ), "net_income", latest_ni["period"], required=True,
        )
        ni_growth = [p for p in ni_points if isinstance(p.get("yoy"), float)][-3:]
        for point in ni_growth:
            add(
                "growth_quality", "growth", (
                    f"Net income growth in {point['period']} was "
                    f"{_fmt_growth(point['yoy'], net_income['percent'])} "
                    f"{_marker_chain(_growth_operand_markers(dataset, net_income, point))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, net_income, point))}."
                ), "net_income", point["period"], required=point is ni_growth[-1],
            )

    growth_pairs = [
        ("net_income", comparison)
        for comparison in ("revenue", "net_interest_income", "noninterest_income")
    ] + [("operating_cash_flow", "net_income")]
    for first_concept, second_concept in growth_pairs:
        first_series, second_series = by.get(first_concept), by.get(second_concept)
        if not first_series or not second_series or not _same_dimension(first_series, second_series):
            continue
        second_by_period = {p["period"]: p for p in _valued_points(second_series)}
        first_growth = [
            p for p in _valued_points(first_series) if isinstance(p.get("yoy"), float)
        ][-3:]
        for first_point in first_growth:
            second_point = second_by_period.get(first_point["period"])
            if second_point is None or not isinstance(second_point.get("yoy"), float):
                continue
            relation, first_growth_text, second_growth_text = _growth_comparison_values(
                first_point["yoy"], second_point["yoy"]
            )
            comparison_operands = (
                _growth_operand_points(dataset, first_series, first_point)
                + _growth_operand_points(dataset, second_series, second_point)
            )
            add(
                "growth_quality", "comparison", (
                    f"In {first_point['period']}, {first_series['label'].lower()} growth of "
                    f"{first_growth_text} "
                    f"{_marker_chain(_growth_operand_markers(dataset, first_series, first_point))} "
                    f"was {relation} "
                    f"{second_series['label'].lower()} growth of "
                    f"{second_growth_text} "
                    f"{_marker_chain(_growth_operand_markers(dataset, second_series, second_point))}"
                    f"{_derived_qualifier(*comparison_operands)}."
                ), first_concept, second_concept, first_point["period"],
            )

    for concept in ("gross_margin", "operating_margin", "net_margin"):
        series = by.get(concept)
        points = _valued_points(series)
        if not series or not points:
            continue
        latest = points[-1]
        add(
            "margins", "latest", (
                f"{series['label']} was {_point_value(series, latest)} in {latest['period']} "
                f"[{latest['marker']}]{_derived_qualifier(latest)}."
            ), concept, latest["period"], required=not any(
                item.section == "margins" and item.required for item in observations
            ),
        )
        for point in [p for p in points if isinstance(p.get("yoy"), float)][-3:]:
            add(
                "margins", "change", (
                    f"{series['label']} changed {_fmt_growth(point['yoy'], True)} in "
                    f"{point['period']} "
                    f"{_marker_chain(_growth_operand_markers(dataset, series, point))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, series, point))}."
                ), concept, point["period"],
            )

    # Same-period cash/earnings level comparisons.  No conversion rate or causal conclusion is
    # synthesized: the code states only the two supplied levels and their ordering.
    for cash_concept in ("free_cash_flow", "operating_cash_flow"):
        cash = by.get(cash_concept)
        if not cash or not net_income or not _same_dimension(cash, net_income):
            continue
        cash_by_period = {p["period"]: p for p in _valued_points(cash)}
        ni_by_period = {p["period"]: p for p in ni_points}
        shared = [period for period in cash_by_period if period in ni_by_period]
        if not shared:
            continue
        period = shared[-1]
        cash_point, ni_point = cash_by_period[period], ni_by_period[period]
        cash_value = _point_value(cash, cash_point)
        income_value = _point_value(net_income, ni_point)
        if cash_value == income_value:
            relation = (
                "equal to"
                if cash_point["value"] == ni_point["value"]
                else "effectively equal to"
            )
        else:
            relation = "above" if cash_point["value"] > ni_point["value"] else "below"
        add(
            "cash_balance_sheet", "level-comparison", (
                f"In {period}, {cash['label'].lower()} of {cash_value} "
                f"[{cash_point['marker']}] was {relation} net income of "
                f"{income_value} [{ni_point['marker']}]"
                f"{_derived_qualifier(cash_point, ni_point)}."
            ), cash_concept, "net-income", period, required=cash_concept == "free_cash_flow",
        )

    for concept in (
        "cash_and_equivalents", "working_capital", "long_term_debt", "shareholders_equity",
    ):
        series = by.get(concept)
        points = _valued_points(series)
        if series and points:
            point = points[-1]
            add(
                "cash_balance_sheet", "latest", (
                    f"{series['label']} was {_point_value(series, point)} in {point['period']} "
                    f"[{point['marker']}]{_derived_qualifier(point)}."
                ), concept, point["period"],
            )

    current_ratio = by.get("current_ratio")
    ratio_points = _valued_points(current_ratio)
    if current_ratio and ratio_points:
        point = ratio_points[-1]
        raw = point["value"]
        if raw > 1.0:
            relation = "above"
        elif raw < 1.0:
            relation = "below"
        else:
            relation = "equal to"
        add(
            "cash_balance_sheet", "ratio-threshold", (
                f"The current ratio was {_point_value(current_ratio, point, ratio_precision=True)} "
                f"in {point['period']} [{point['marker']}]{_derived_qualifier(point)}, "
                f"{relation} 1.00x."
            ), "current-ratio", point["period"], required=True,
        )

    eps = next((by.get(name) for name in ("earnings_per_share", "eps_diluted") if by.get(name)), None)
    eps_points = _valued_points(eps)
    if eps and eps_points:
        point = eps_points[-1]
        add(
            "growth_quality", "latest-eps", (
                f"{eps['label']} was {_point_value(eps, point)} in {point['period']} "
                f"[{point['marker']}]{_derived_qualifier(point)}."
            ), eps["concept"], point["period"], required=not any(
                item.section == "growth_quality" and item.required for item in observations
            ),
        )

    latest_period = dataset["periods"][-1]["key"] if dataset.get("periods") else None
    if latest_period:
        missing_sections = {
            "gross_margin": "margins", "operating_margin": "margins", "net_margin": "margins",
            "free_cash_flow": "cash_balance_sheet", "operating_cash_flow": "cash_balance_sheet",
            "earnings_per_share": "growth_quality", "eps_diluted": "growth_quality",
        }
        for concept, section in missing_sections.items():
            series = by.get(concept)
            point = next((p for p in (series or {}).get("points", []) if p["period"] == latest_period), None)
            if series and point is not None and point.get("value") is None:
                add(
                    section, "selected-gap", (
                        f"{series['label']} is not available in this selected dataset for "
                        f"{latest_period}."
                    ), concept, latest_period,
                )

    signals = dataset.get("inflections") or []
    if signals:
        point_index = marker_index(dataset)
        for position, signal in enumerate(signals, start=1):
            operand_bits = []
            for marker in signal.get("markers") or []:
                point = point_index.get(marker)
                if not point or point.get("kind") == "cagr":
                    continue
                ratio_precision = (
                    point.get("concept") == "current_ratio" and point.get("unit") == "pure"
                )
                operand_bits.append(
                    f"{point['label']} "
                    f"{_point_value(point, point, ratio_precision=ratio_precision)} "
                    f"in {point['period']} [{marker}]"
                    f"{_derived_qualifier(point)}"
                )
            detail = signal["detail"].strip()
            operands = "; ".join(operand_bits)
            add(
                "red_flags", "signal", detail + (f" Source operands: {operands}." if operands else ""),
                signal.get("kind", "signal"), str(position), required=True,
            )
    else:
        add(
            "red_flags", "no-signals", "No trend flags detected in the selected data.",
            "none", required=True,
        )

    if top and top_points:
        latest = top_points[-1]
        if isinstance(latest.get("yoy"), float):
            add(
                "watch_next", "growth", (
                    f"Watch whether {top['label'].lower()} growth in the next reporting update "
                    f"improves from {_fmt_growth(latest['yoy'], top['percent'])} in "
                    f"{latest['period']} "
                    f"{_marker_chain(_growth_operand_markers(dataset, top, latest))}"
                    f"{_derived_qualifier(*_growth_operand_points(dataset, top, latest))}."
                ), top["concept"], latest["period"], required=True,
            )
        else:
            add(
                "watch_next", "level", (
                    f"Watch how {top['label'].lower()} in the next reporting update compares with "
                    f"{_point_value(top, latest)} in {latest['period']} [{latest['marker']}]"
                    f"{_derived_qualifier(latest)}."
                ), top["concept"], latest["period"], required=True,
            )
    for series in (net_income, by.get("operating_margin"), by.get("free_cash_flow")):
        points = _valued_points(series)
        if not series or not points:
            continue
        point = points[-1]
        add(
            "watch_next", "metric", (
                f"Watch how {series['label'].lower()} in the next reporting update compares with "
                f"{_point_value(series, point)} in {point['period']} [{point['marker']}]"
                f"{_derived_qualifier(point)}."
            ), series["concept"], point["period"],
        )

    return observations


def compact_observation_catalogue(catalogue: list[TrendObservation]) -> str:
    lines = ["Allowed observations (select IDs only; text is immutable):"]
    lines.extend(f"- {item.id} | {item.section} | {item.markdown}" for item in catalogue)
    return "\n".join(lines)


def _strict_json(raw: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> Any:
        raise ValueError("non-JSON number")

    try:
        return json.loads(raw.strip(), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (TypeError, ValueError):
        return None


def parse_observation_selection(
    raw: str, catalogue: list[TrendObservation]
) -> Optional[dict[str, list[str]]]:
    """Validate the complete model reply once, at the external boundary."""
    payload = _strict_json(raw)
    if not isinstance(payload, dict) or set(payload) != _SECTION_KEYS:
        return None
    by_id = {item.id: item for item in catalogue}
    total = 0
    selection: dict[str, list[str]] = {}
    for section, _ in ANALYSIS_SECTIONS:
        ids = payload.get(section)
        if not isinstance(ids, list) or len(ids) > _OPTIONAL_PER_SECTION:
            return None
        if any(not isinstance(item_id, str) for item_id in ids) or len(set(ids)) != len(ids):
            return None
        if any(item_id not in by_id or by_id[item_id].section != section for item_id in ids):
            return None
        total += len(ids)
        selection[section] = ids
    return selection if total <= _SELECTION_TOTAL_LIMIT else None


def render_observation_selection(
    catalogue: list[TrendObservation], selection: dict[str, list[str]]
) -> str:
    by_id = {item.id: item for item in catalogue}
    required = {
        section: [item for item in catalogue if item.section == section and item.required]
        for section, _ in ANALYSIS_SECTIONS
    }
    rendered: list[str] = []
    for section, title in ANALYSIS_SECTIONS:
        rendered.append(f"## {title}")
        section_items = [item for item in catalogue if item.section == section]
        chosen: list[TrendObservation] = list(required[section])
        chosen_ids = {item.id for item in chosen}
        chosen.extend(by_id[item_id] for item_id in selection[section] if item_id not in chosen_ids)
        if not chosen and section_items:
            # An empty valid selection cannot make available evidence look absent.  The catalogue
            # order is deterministic and starts with the section's most useful observation.
            chosen.append(section_items[0])
        if chosen:
            rendered.extend(item.markdown for item in chosen)
        else:
            rendered.append("Not enough data is available for this section in the selected periods.")
        rendered.append("")
    return "\n".join(rendered).rstrip()


def _has_minimum_analysis_data(dataset: dict[str, Any]) -> bool:
    by = _series_map(dataset)
    top = next((by.get(name) for name in ("revenue", "net_interest_income") if by.get(name)), None)
    top_periods = {point["period"] for point in _valued_points(top)}
    income_periods = {point["period"] for point in _valued_points(by.get("net_income"))}
    return len(top_periods & income_periods) >= 2


def marker_index(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """F# marker -> its dataset point (augmented with concept/label context) for citation
    resolution in the narrative pipeline. Series-level CAGR markers resolve too (kind="cagr")."""
    index: dict[str, dict[str, Any]] = {}
    for series in dataset["series"]:
        for point in series["points"]:
            marker = point.get("marker")
            if marker:
                index[marker] = {
                    **point,
                    "concept": series["concept"],
                    "label": series["label"],
                    "unit": series["unit"],
                    "percent": series["percent"],
                }
        if series.get("cagr_marker"):
            index[series["cagr_marker"]] = {
                "kind": "cagr",
                "value": series["cagr"],
                # The window the CAGR was actually computed over (valued endpoints), which can
                # be narrower than the selected range — never claim the wider one.
                "period": series.get("cagr_window") or dataset["period_key"],
                "concept": series["concept"],
                "label": series["label"],
                "unit": series["unit"],
                "percent": series["percent"],
                "derived": False,
                "reconciled": series.get("cagr_reconciled"),
                "provenance": series.get("cagr_provenance"),
            }
    return index


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
