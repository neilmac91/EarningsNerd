"""Deterministic inflection signals over the selected dataset."""
from __future__ import annotations

from typing import Any

from app.services.trend_analysis.cache import logger
from app.services.trend_analysis.formatting import _ordered_percentage_values, _pct_str, _ratio_threshold_value
from app.services.trend_analysis.periods import concept_label
from app.services.trend_analysis.series import _growth_operand_markers, _series_map, _valued_points


def detect_growth_deceleration(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Top-line YoY growth strictly declining across the three most recent measurable periods."""
    flags = []
    series_by = _series_map(dataset)
    for concept in ("revenue", "net_interest_income"):
        # Exclude NOT_MEANINGFUL ("nm") explicitly — it's a string sentinel, not a float, and
        # `yoys[0] > yoys[1]` below would raise TypeError if one slipped through.
        points = [
            p for p in _valued_points(series_by.get(concept)) if isinstance(p.get("yoy"), float)
        ]
        if len(points) < 3:
            continue
        last3 = points[-3:]
        yoys = [p["yoy"] for p in last3]
        if yoys[0] > yoys[1] > yoys[2]:
            displays, display_is_distinct = _ordered_percentage_values(yoys)
            sequence = (" → " if display_is_distinct else ", ").join(displays)
            display_qualifier = (
                ""
                if display_is_distinct
                else " (effectively equal where values match at four-decimal precision)"
            )
            markers = [
                marker
                for point in last3
                for marker in _growth_operand_markers(dataset, series_by[concept], point)
            ]
            flags.append(
                {
                    "kind": "growth_deceleration",
                    "concepts": [concept],
                    "periods": [p["period"] for p in last3],
                    "detail": (
                        f"{concept_label(concept)} YoY growth decelerated across its three most "
                        f"recent measurable observations: {sequence}{display_qualifier}."
                    ),
                    "markers": list(dict.fromkeys(markers)),
                }
            )
        # Only flag the primary top line the company actually has.
        if points:
            break
    return flags


def detect_margin_compression(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """A margin strictly declining over the three most recent periods by ≥2 percentage points."""
    flags = []
    series_by = _series_map(dataset)
    for concept in ("operating_margin", "net_margin"):
        points = _valued_points(series_by.get(concept))
        if len(points) < 3:
            continue
        last3 = points[-3:]
        values = [p["value"] for p in last3]  # stored ×100 (percent)
        if values[0] > values[1] > values[2] and (values[0] - values[2]) >= 2.0:
            displays, display_is_distinct = _ordered_percentage_values(
                values, already_percent=True, signed=False
            )
            sequence = (" → " if display_is_distinct else ", ").join(displays)
            display_qualifier = (
                ""
                if display_is_distinct
                else " (effectively equal where values match at four-decimal precision)"
            )
            flags.append(
                {
                    "kind": "margin_compression",
                    "concepts": [concept],
                    "periods": [p["period"] for p in last3],
                    "detail": (
                        f"{concept_label(concept)} compressed {values[0] - values[2]:.1f}pp over "
                        f"three periods: {sequence}{display_qualifier}."
                    ),
                    "markers": [p["marker"] for p in last3],
                }
            )
    return flags


def detect_fcf_ni_divergence(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Free cash flow conversion collapsing vs its own history (earnings-quality signal)."""
    series_by = _series_map(dataset)
    fcf_by_period = {p["period"]: p for p in _valued_points(series_by.get("free_cash_flow"))}
    ratios: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for ni_point in _valued_points(series_by.get("net_income")):
        fcf_point = fcf_by_period.get(ni_point["period"])
        if fcf_point is not None and ni_point["value"] > 0:
            ratios.append((fcf_point, ni_point, fcf_point["value"] / ni_point["value"]))
    if len(ratios) < 3:
        return []
    *prior, (last_fcf, last_ni, last_ratio) = ratios
    prior_avg = sum(r for _, _, r in prior) / len(prior)
    if last_ratio < 0.6 and prior_avg >= 0.9:
        # The historical-average claim depends on every prior FCF/NI pair, so its observation
        # must carry those operands as well as the latest pair.  A marker for only the latest
        # period would make the displayed average look source-bound when its constituents were
        # invisible.
        operand_markers = [
            marker
            for fcf_point, ni_point, _ in ratios
            for marker in (fcf_point["marker"], ni_point["marker"])
        ]
        return [
            {
                "kind": "fcf_ni_divergence",
                "concepts": ["free_cash_flow", "net_income"],
                "periods": [last_fcf["period"]],
                "detail": (
                    f"Free-cash-flow conversion fell to {last_ratio:.2f}× net income in "
                    f"{last_fcf['period']} vs a {prior_avg:.2f}× historical average — earnings and "
                    f"cash are diverging."
                ),
                "markers": list(dict.fromkeys(operand_markers)),
            }
        ]
    return []


def detect_debt_build(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Long-term debt grew ≥50% across the selected window."""
    points = _valued_points(_series_map(dataset).get("long_term_debt"))
    if len(points) < 2:
        return []
    first, last = points[0], points[-1]
    if first["value"] > 0 and last["value"] >= 1.5 * first["value"]:
        growth = (last["value"] - first["value"]) / first["value"]
        return [
            {
                "kind": "debt_build",
                "concepts": ["long_term_debt"],
                "periods": [first["period"], last["period"]],
                "detail": (
                    f"Long-term debt grew {_pct_str(growth)} from {first['period']} to "
                    f"{last['period']}."
                ),
                "markers": [first["marker"], last["marker"]],
            }
        ]
    return []


def detect_liquidity_squeeze(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    """Current ratio below 1.0, or down ≥0.5 across the window to below 1.5."""
    points = _valued_points(_series_map(dataset).get("current_ratio"))
    if not points:
        return []
    first, last = points[0], points[-1]
    if last["value"] < 1.0:
        detail = (
            f"Current ratio is below 1.0 "
            f"({_ratio_threshold_value(last['value'])} in {last['period']})."
        )
    elif len(points) >= 2 and (first["value"] - last["value"]) >= 0.5 and last["value"] < 1.5:
        detail = (
            f"Current ratio declined from {first['value']:.2f}× ({first['period']}) to "
            f"{last['value']:.2f}× ({last['period']})."
        )
    else:
        return []
    return [
        {
            "kind": "liquidity_squeeze",
            "concepts": ["current_ratio"],
            "periods": [first["period"], last["period"]],
            "detail": detail,
            "markers": sorted({first["marker"], last["marker"]}),
        }
    ]


_DETECTORS = (
    detect_growth_deceleration,
    detect_margin_compression,
    detect_fcf_ni_divergence,
    detect_debt_build,
    detect_liquidity_squeeze,
)


def detect_inflections(dataset: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for detector in _DETECTORS:
        try:
            flags.extend(detector(dataset))
        except Exception:  # noqa: BLE001 - a detector bug must never break dataset assembly
            logger.exception("inflection detector %s failed", detector.__name__)
    return flags
