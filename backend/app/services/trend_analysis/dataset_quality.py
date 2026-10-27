"""Publication and comparison lineage for the multi-period dataset."""
from typing import Any, Callable, Mapping

from app.services.fact_provenance import calculated_provenance, provenance_for_fact, published_value
from app.services.trend_analysis.data_notes import data_notes as data_notes

INCOMPATIBLE_UNITS_MESSAGE = (
    "This company's filed figures for these periods are in more than one currency or unit, so they can't be "
    "compared. Analysis isn't available for this range."
)


class IncompatibleUnitsError(ValueError):
    """A series whose valued points name different units, or a valued point that names none (E102).

    The whole dataset is refused before any comparison, window figure, observation, narrative or export reads it:
    a USD point beside native-currency points, or USD/shares beside CNY/shares, would chart, compare and compound
    as one series. No series is split, no value converted and no point dropped. ``code`` is the stable domain code
    for the analysis routes' error adapter once the shared error vocabulary (E31) lands; until then each route
    sends the message as it sends every dataset refusal, a ValueError."""

    code = "analysis_incompatible_units"

    def __init__(self) -> None:
        super().__init__(INCOMPATIBLE_UNITS_MESSAGE)


def require_one_unit(points: list[dict]) -> None:
    """Refuse a series unless every valued point names the same unit (``IncompatibleUnitsError``). A point with no
    value is absent, never incompatible; a numeric zero is a value. A ratio series names ``pure`` throughout."""
    units = {point.get("unit") for point in points if point.get("value") is not None}
    if len(units) > 1 or not all(isinstance(unit, str) and unit.strip() for unit in units):
        raise IncompatibleUnitsError()


def dataset_point(row: Any, period: str, cik: str | None, documents: Mapping[str, str] | None = None) -> dict[str, Any]:
    provenance = provenance_for_fact(row, cik, documents)
    return {
        "period": period, "value": published_value(row), "concept": row.concept,
        "unit": row.unit,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat(),
        "form": row.form, "accession": row.accession, "raw_tag": row.raw_tag,
        # New lineage owns this marker. The old boolean is only a compatibility hint for
        # rows written before quarter calculations and same-period ratios were distinguished.
        "derived": row.fiscal_period == "Q4" and bool(
            provenance.get("period_calculation") or (
                row.source == "derived" and not row.provenance and not row.reconciled
            )
        ),
        "reconciled": provenance["validation"] == "passed", "provenance": provenance,
        "source_url": provenance.get("source_url"),
        "fiscal_year": row.fiscal_year, "fiscal_period": row.fiscal_period,
    }


def add_comparisons(
    points: list[dict], periods: list[dict], mode: str, is_percent: bool,
    delta: Callable[[float | None, float | None], float | str | None],
) -> None:
    """Require exact fiscal predecessors; gaps never become quarterly comparisons."""
    by_period = {p["period"]: p for p in points}
    for bucket, point in zip(periods, points):
        if point["value"] is None:
            continue
        year, fiscal_period = bucket["fiscal_year"], bucket["fiscal_period"]
        prior_keys = {"yoy": f"FY{year - 1}" if mode == "annual" else f"{year - 1}{fiscal_period}"}
        if mode == "quarterly":
            quarter = int(fiscal_period[1])
            prior_keys["qoq"] = f"{year}Q{quarter - 1}" if quarter > 1 else f"{year - 1}Q4"
        for comparison, key in prior_keys.items():
            previous = by_period.get(key)
            value = delta(point["value"], previous["value"] if previous else None)
            point[comparison] = value
            point[f"{comparison}_reconciled"] = None
            if value is None or previous is None:
                continue
            formula = "percentage_point_change" if is_percent else {
                "yoy": "year_over_year_growth", "qoq": "quarter_over_quarter_growth",
            }[comparison]
            provenance = calculated_provenance(formula, [point, previous])
            point[f"{comparison}_provenance"] = provenance
            point[f"{comparison}_reconciled"] = provenance["validation"] == "passed"
