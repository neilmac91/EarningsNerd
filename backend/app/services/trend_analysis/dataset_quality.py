"""Publication and comparison lineage for the multi-period dataset."""
from typing import Any, Callable

from app.services.fact_provenance import calculated_provenance, provenance_for_fact, published_value


def dataset_point(row: Any, period: str, cik: str | None) -> dict[str, Any]:
    provenance = provenance_for_fact(row, cik)
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
