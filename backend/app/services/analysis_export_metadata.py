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
            "Calculated figure. See Sources & methods for the available formula and operands."
            if provenance else "Computed Q4. Calculation details are unavailable in this older snapshot."
        )
    if provenance.get("formula"):
        notes.append(formula_text(provenance["formula"]))
    return notes


def count_label(count: int, singular: str, plural: str | None = None) -> str:
    """The count with its noun, singular at one: "1 figure", "3 figures"."""
    return f"{count} {singular if count == 1 else plural or singular + 's'}"


_PERIOD_KEY = r"(?:FY)?\d{4}(?:Q[1-4])?"


def period_label(period: Any) -> str:
    """Display-only vocabulary; internal lookup and snapshot keys stay unchanged.

    A window key "FY2022..FY2024" reads as the range "FY2022–FY2024" (an unspaced en-dash, the
    voice guide's range form), and a quarter key "2026Q2" as "Q2 2026".
    """
    text = re.sub(rf"\b({_PERIOD_KEY})\.\.({_PERIOD_KEY})\b", "\\1\u2013\\2", str(period or ""))
    return re.sub(r"\b(\d{4})Q([1-4])\b", r"Q\2 \1", text)


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
    """The data-notes count line, read as the web's DataNotes summary reads: one clause per count
    that is not zero, singular at one, and the passed count only when no figure needs review or
    lacks a validation record. Empty when every count is zero."""
    totals = envelope["totals"]
    unknown_comparisons = sum(
        len(note["comparisons"]) for note in envelope["notes"] if note["kind"] == "unknown"
    )
    all_passed = totals["reviewValues"] == 0 and totals["unknown"] == 0
    clauses = (
        (totals["reviewValues"], "figure needs review", "figures need review"),
        (totals["reviewComparisons"], "comparison needs review", "comparisons need review"),
        (totals["unavailable"], "unavailable", "unavailable"),
        (totals["unknown"], "figure with no validation record", "figures with no validation record"),
        (unknown_comparisons, "comparison with no validation record", "comparisons with no validation record"),
        (totals["passed"] if all_passed else 0, "passed automated checks", "passed automated checks"),
        (totals["calculated"], "calculated †", "calculated †"),
    )
    return " · ".join(count_label(count, singular, plural) for count, singular, plural in clauses if count)


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
