"""Shared series lookup and growth-operand selection."""
from __future__ import annotations

from typing import Any, Optional

from app.services.trend_analysis.periods import parse_period_key


# --- deterministic inflection signals ----------------------------------------------------------


def _series_map(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {series["concept"]: series for series in dataset["series"]}


def _valued_points(series: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not series:
        return []
    return [p for p in series["points"] if p["value"] is not None]


def _growth_operand_points(
    dataset: dict[str, Any], series: dict[str, Any], point: dict[str, Any]
) -> list[dict[str, Any]]:
    """Current/prior points that own a displayed YoY/pp change, in that order."""
    period = point["period"]
    try:
        mode = dataset.get("mode") or ("annual" if period.startswith("FY") else "quarterly")
        year, quarter = parse_period_key(mode, period)
    except ValueError:
        return [point]
    prior_period = f"FY{year - 1}" if quarter is None else f"{year - 1}{quarter}"
    prior = next((candidate for candidate in series["points"] if candidate["period"] == prior_period), None)
    points = [point]
    if prior and prior.get("marker"):
        points.append(prior)
    return points


def _growth_operand_markers(
    dataset: dict[str, Any], series: dict[str, Any], point: dict[str, Any]
) -> list[str]:
    return [operand["marker"] for operand in _growth_operand_points(dataset, series, point)]
