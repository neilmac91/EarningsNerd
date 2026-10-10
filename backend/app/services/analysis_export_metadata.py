"""Shared descriptions for analysis PDF and workbook exports.

The dataset owns financial eligibility and calculations. These helpers only present its
provenance; they never recalculate or promote a legacy record to validated status.
"""
from __future__ import annotations

from collections.abc import Iterator
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
_REASON_LABELS = {
    "unsupported_eps_calculation": "Quarterly EPS is unavailable because a reported figure has not been located; reconstructing annual diluted shares is unsupported.",
    "legacy_calculation": "This calculation predates the current source checks and needs rebuilding.",
    "source_check_needed": "The source figure has not passed the required checks.",
    "incompatible_periods": "The source periods or accounting bases do not match.",
    "missing_comparator": "The required comparison period is unavailable.",
}
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


def point_limitations(point: dict[str, Any]) -> list[str]:
    provenance = point.get("provenance") or {}
    reasons = [_REASON_LABELS.get(str(reason), str(reason).replace("_", " "))
               for reason in provenance.get("reasons", []) if reason]
    if reasons:
        return reasons
    validation = provenance.get("validation")
    if validation == "needs_review":
        return ["Source checks are incomplete; review the original filing."]
    if validation == "unavailable":
        return ["Unavailable in this analysis."]
    if not provenance and point.get("reconciled") is False:
        return ["Unreconciled value: check the source filing before relying on this figure."]
    return []


def point_notes(point: dict[str, Any]) -> list[str]:
    provenance = point.get("provenance") or {}
    notes: list[str] = []
    if point_method(point) == "calculated":
        notes.append(
            "Calculated from reported inputs. See Sources & Methods for the formula and operands."
            if provenance else "Computed Q4 — calculated from reported inputs; calculation details are unavailable in this older snapshot."
        )
    if provenance.get("formula"):
        notes.append(formula_text(provenance["formula"]))
    notes.extend(point_limitations(point))
    return notes


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


def export_points(series: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], str]]:
    """Output rows and their derived comparisons share the same provenance presentation."""
    for point in series.get("points", []):
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
                "period": series.get("cagr_window" if growth == "cagr" else "window_pp_range"),
                "value": series.get(growth), "provenance": provenance,
                "reconciled": series.get(f"{growth}_reconciled"),
            }, unit
