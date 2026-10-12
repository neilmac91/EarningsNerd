"""Aligned financial datasets, growth calculations and stable citation markers."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, FinancialFact
from app.services.fact_provenance import CALCULATION_VERSION, calculated_provenance
from app.services.trend_analysis.dataset_quality import add_comparisons, data_notes, dataset_point
from app.services.trend_analysis.detectors import detect_inflections
from app.services.trend_analysis.formatting import NOT_MEANINGFUL
from app.services.trend_analysis.periods import (
    MODES, DATASET_CONCEPT_ORDER, _QUARTERS, _period_sort_key, concept_label, parse_period_key,
)
from app.services.trend_analysis.series import _series_map, _valued_points
from app.utils.datetimes import ensure_utc, iso_z

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


def _index_facts(
    db: Session, company: Company,
) -> tuple[
    list[FinancialFact], dict[tuple[int, str, str], FinancialFact],
    dict[tuple[str, date], FinancialFact],
]:
    """Read the company facts once and index flows and balance-sheet instants."""
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
    return rows, by_fy_fp, instant_by_end


def _annual_period_axis(
    rows: list[FinancialFact], start_fy: int, end_fy: int,
) -> tuple[list[dict[str, Any]], int]:
    """Select annual buckets and keep the latest end date for each fiscal year."""
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
    return periods, cap


def _quarterly_period_axis(
    rows: list[FinancialFact], start_fy: int, start_fp: str, end_fy: int, end_fp: str,
) -> tuple[list[dict[str, Any]], int]:
    """Walk ordered quarterly buckets from the selected start through the end."""
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
    return periods, cap


def _period_axis(
    rows: list[FinancialFact], mode: str,
    start_fy: int, start_fp: str, end_fy: int, end_fp: str,
) -> list[dict[str, Any]]:
    # Period axis (oldest → newest), range-filtered and capped.
    if mode == "annual":
        periods, cap = _annual_period_axis(rows, start_fy, end_fy)
    else:
        periods, cap = _quarterly_period_axis(rows, start_fy, start_fp, end_fy, end_fp)

    if not periods:
        raise ValueError("No data available for the selected period range.")
    if len(periods) > cap:
        raise ValueError(f"Too many periods selected: {len(periods)} (max {cap} for {mode} mode).")
    return periods


def _attach_growth(
    points: list[dict[str, Any]], periods: list[dict[str, Any]], mode: str, concept: str,
) -> tuple[str, bool]:
    """Attach the existing comparisons with the concept's percentage convention."""
    unit = next((p["unit"] for p in points if p.get("unit")), "USD")
    is_percent = concept in _PERCENT_CONCEPTS
    # Percent-unit series (margins) report YoY/QoQ as percentage-POINT deltas — the
    # convention finance readers expect for a ratio already expressed as a percentage — never
    # the relative change of the percentage value itself. Everything else keeps relative
    # growth (with the n/m sign-flip guard baked into `_growth`).
    delta_fn = _pp_delta if is_percent else _growth

    add_comparisons(points, periods, mode, is_percent, delta_fn)
    return unit, is_percent


def _series_window_figures(
    mode: str, unit: str, is_percent: bool,
    periods: list[dict[str, Any]], points: list[dict[str, Any]],
) -> tuple[Optional[float], Optional[str], Optional[float], Optional[str]]:
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
    return cagr, cagr_window, window_pp, window_pp_range


def _append_series(
    series_list: list[dict[str, Any]], concept: str, unit: str, is_percent: bool,
    cagr: Optional[float], cagr_window: Optional[str],
    window_pp: Optional[float], window_pp_range: Optional[str], points: list[dict[str, Any]],
) -> None:
    """Append the series with the existing endpoint quality and calculation lineage."""
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


def _series_points(
    company: Company, mode: str, periods: list[dict[str, Any]],
    by_fy_fp: dict[tuple[int, str, str], FinancialFact],
    instant_by_end: dict[tuple[str, date], FinancialFact],
) -> list[dict[str, Any]]:
    """Align each concept's points and attach comparisons and window figures."""
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

        unit, is_percent = _attach_growth(points, periods, mode, concept)
        cagr, cagr_window, window_pp, window_pp_range = _series_window_figures(
            mode, unit, is_percent, periods, points,
        )
        _append_series(
            series_list, concept, unit, is_percent,
            cagr, cagr_window, window_pp, window_pp_range, points,
        )
    return series_list


def _assign_markers(series_list: list[dict[str, Any]]) -> None:
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

    rows, by_fy_fp, instant_by_end = _index_facts(db, company)
    periods = _period_axis(rows, mode, start_fy, start_fp, end_fy, end_fp)
    series_list = _series_points(company, mode, periods, by_fy_fp, instant_by_end)
    _assign_markers(series_list)

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
    dataset["data_notes"] = data_notes(dataset)
    dataset["snapshot_id"] = dataset_fingerprint(dataset)
    return dataset


# --- fingerprint + prompt rendering ------------------------------------------------------------


def dataset_fingerprint(dataset: dict[str, Any]) -> str:
    """sha256 of the canonical dataset JSON — new facts (or a changed range) change it, which
    invalidates the cached narrative for that key (D4)."""
    # A refresh that confirms the same source facts must not consume a new AI generation. The
    # Display metadata is excluded; underlying source/quality/formula changes are not.
    content = {key: value for key, value in dataset.items() if key not in {"snapshot_id", "data_as_of", "data_notes", "narrative_presentation"}}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
