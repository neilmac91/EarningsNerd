"""Code-owned narrative observations and strict model selection."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.services.trend_analysis.dataset import marker_index
from app.services.trend_analysis.formatting import (
    _format_value, _ratio_threshold_value, _pct_str, _ordered_percentage_values, _fmt_growth,
)
from app.services.trend_analysis.series import (
    _series_map, _valued_points, _growth_operand_points, _growth_operand_markers,
)


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
