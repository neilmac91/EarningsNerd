"""Shared descriptions for analysis PDF and workbook exports.

The dataset owns financial eligibility and calculations. These helpers only present its
provenance; they never recalculate or promote a legacy record to validated status.
"""
from __future__ import annotations

from collections.abc import Iterator
import re
from typing import Any

ANALYSIS_DISCLAIMER = (
    "EarningsNerd provides financial data and AI-assisted commentary for research, not investment "
    "advice or a recommendation to trade securities. Figures may be reported or calculated; "
    "sources and methods accompany this analysis. Data and commentary may contain errors or "
    "omissions. Check material information against original filings before making investment "
    "decisions. Use is subject to the EarningsNerd Terms of Service (earningsnerd.io/terms). "
    "EarningsNerd is not affiliated with or endorsed by the SEC."
)
FCF_DEFINITION = (
    "Standardized free cash flow = operating cash flow minus purchases of property and equipment. "
    "This definition excludes finance-lease principal payments and may differ from the "
    "company's own free cash flow measure."
)
_FORMULA_LABELS = {
    "year_over_year_growth": "(current - same period last year) / abs(same period last year)",
    "quarter_over_quarter_growth": "(current quarter - previous fiscal quarter) / abs(previous fiscal quarter)",
    "compound_annual_growth": "(last / first) ^ (1 / fiscal years between endpoints) - 1",
    "percentage_point_change": "current percentage - comparison percentage",
}


def formula_text(formula: Any) -> str:
    return _FORMULA_LABELS.get(str(formula), str(formula)) if formula else ""


def point_method(point: dict[str, Any]) -> str:
    provenance = point.get("provenance") or {}
    method = provenance.get("method")
    if method in ("reported", "calculated"):
        return str(method)
    # A legacy derived flag records calculation provenance, not validation.
    return "calculated" if point.get("derived") else "unknown"


def point_notes(point: dict[str, Any], note: dict[str, Any] | None = None) -> list[str]:
    """A workbook comment references the canonical note before neutral method details."""
    provenance = point.get("provenance") or {}
    notes = [f"Data note {note['letter']}: {note['message']}"] if note else []
    if point_method(point) == "calculated":
        notes.append(
            "Calculated figure. See Sources & Methods for the available formula and operands."
            if provenance else "Computed Q4 — calculation details are unavailable in this older snapshot."
        )
    if provenance.get("formula"):
        notes.append(formula_text(provenance["formula"]))
    return notes


def period_label(period: Any) -> str:
    """Display-only vocabulary; internal lookup and snapshot keys stay unchanged."""
    return re.sub(r"\b(\d{4})Q([1-4])\b", r"Q\2 \1", str(period or ""))


def raw_value_text(value: Any) -> str:
    """Preserve the supplied numeric representation, including zero and ratio precision."""
    return "Unavailable" if value is None else "n/m" if value == "nm" else str(value)


def note_index(envelope: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Index admitted server memberships without reclassifying financial quality."""
    indexed = {}
    for note in envelope["notes"]:
        for ref in note["values"]:
            indexed[(ref["concept"], ref["period"], "value")] = note
        for ref in note["comparisons"]:
            indexed[(ref["concept"], ref["period"], ref["basis"])] = note
    return indexed


def notes_summary(envelope: dict[str, Any]) -> str:
    totals = envelope["totals"]
    return " · ".join([
        f"{totals['reviewValues']} figures need review",
        f"{totals['reviewComparisons']} comparisons need review",
        f"{totals['unavailable']} unavailable",
        f"{totals['unknown']} with no validation record",
        f"{totals['passed']} passed automated checks",
        f"{totals['calculated']} calculated †",
    ])


def source_urls(provenance: dict[str, Any]) -> list[str]:
    """Links supplied by source provenance, in stable first-seen order."""
    urls = [provenance.get("source_url")]
    urls.extend(item.get("source_url") for _, item in operand_records(provenance))
    return list(dict.fromkeys(str(url) for url in urls if url and str(url).startswith("https://")))


def operand_records(provenance: dict[str, Any], prefix: str = "Input ") -> Iterator[tuple[str, dict[str, Any]]]:
    """Preserve nested calculation lineage, including each intermediate formula's operands."""
    for index, operand in enumerate(provenance.get("inputs", []), start=1):
        label = f"{prefix}{index}"
        yield label, operand
        yield from operand_records(operand.get("provenance") or {}, prefix=label + ".")


def export_points(
    series: dict[str, Any], periods: list[str] | None = None,
    period_key: str = "",
) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Output rows and their derived comparisons share the same provenance presentation."""
    by_period = {point.get("period"): point for point in series.get("points", [])}
    for period in periods if periods is not None else by_period:
        point = by_period.get(period) or {"period": period, "value": None}
        yield "Value", point, "percent" if series.get("percent") else series.get("unit", "")
        for growth in ("yoy", "qoq"):
            provenance = point.get(f"{growth}_provenance")
            if point.get(growth) is not None or provenance:
                yield growth.upper(), {
                    "period": point.get("period"), "value": point.get(growth),
                    "provenance": provenance, "reconciled": point.get(f"{growth}_reconciled"),
                }, "percentage points" if series.get("percent") else "fraction"
    for growth, label, unit in (("cagr", "CAGR", "fraction"), ("window_pp", "Window change", "percentage points")):
        provenance = series.get(f"{growth}_provenance")
        if series.get(growth) is not None or provenance:
            yield label, {
                "period": series.get("cagr_window" if growth == "cagr" else "window_pp_range") or period_key,
                "value": series.get(growth), "provenance": provenance,
                "reconciled": series.get(f"{growth}_reconciled"),
            }, unit
