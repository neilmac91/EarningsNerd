"""Shared descriptions for analysis PDF and workbook exports.

The dataset owns financial eligibility and calculations. These helpers only present its
provenance; they never recalculate or promote a legacy record to validated status.
"""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
import re
from typing import Any, NamedTuple

from app.services.trend_analysis.data_notes import marks_figure, note_summary
from app.utils.datetimes import ensure_utc, utc_from_iso

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
# The fine print's closing line. The page's asks the reader to select a figure, which a file cannot offer, so each
# export names where it keeps a figure's evidence instead; its words hold the surface rules data_notes' reason words
# hold (test_export_note_marks.py), so the page's "confirm that reported figures" drops its "that".
AUTOMATED_CHECKS = ("Automated checks confirm reported figures come from the company’s filed data (XBRL). "
                    "They are not an audit of the company’s accounts.")
PDF_CLOSING = f"Sources & methods gives each figure’s source filing, method and inputs. {AUTOMATED_CHECKS}"
WORKBOOK_CLOSING = ("Sources & methods gives each figure’s source filing, method and inputs, and a figure with a data "
                    f"note or a calculation carries a comment. {AUTOMATED_CHECKS}")
# The quarterly grid's legend for its Q4 header † (MetricsTable.tsx): the dagger marks a period, never a figure.
QUARTER_LEGEND = "Fiscal quarters follow the company’s reporting calendar."
DERIVED_Q4_LEGEND = ("A Q4 header † means some flow figures are calculated from annual totals less the first nine "
                     "months. It does not mark the column’s balance-sheet figures as calculated.")


def display_instant(value: datetime | str | None) -> str | None:
    """An instant as the exports print it, "October 24, 2026, 20:26 UTC": the server cannot know the
    reader's zone, so the zone is named. None when absent or unreadable."""
    if not value:
        return None
    try:
        moment = (ensure_utc(value) if isinstance(value, datetime) else utc_from_iso(str(value))).astimezone(timezone.utc)
    except ValueError:
        return None
    return f"{moment:%B} {moment.day}, {moment.year}, {moment:%H:%M} UTC"


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
    """A workbook comment references the canonical note before neutral method details. Every note stays as a comment,
    the workbook's evidence dialog; it names its letter only when the note marks the figure (D-061), as the page does."""
    provenance = point.get("provenance") or {}
    notes = [f"Data note {note['letter']}: {note['message']}" if marks_figure(note) else f"Data note: {note['message']}"] if note else []
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
    voice guide's range form), a window of one period "FY2021..FY2021" as that period, "FY2021"
    (E177, as the analysis page prints it), and a quarter key "2026Q2" as "Q2 2026".
    """
    text = re.sub(rf"\b({_PERIOD_KEY})\.\.({_PERIOD_KEY})\b",
                  lambda window: window[1] if window[1] == window[2] else f"{window[1]}\u2013{window[2]}",
                  str(period or ""))
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


# A summary names at most this many metrics for a note, then counts the rest (DataNotes.tsx SUMMARY_PLACES).
SUMMARY_PLACES = 3


def _comparison_label(ref: dict[str, Any]) -> str:
    """A growth figure as the page names it: "Revenue YoY", "Net margin window percentage-point change"."""
    basis = ref["basis"]
    name = {"qoq": "QoQ", "yoy": "YoY", "window_pp": "window percentage-point"}.get(basis, "CAGR")
    return f"{ref['label']} {name}{' change' if basis == 'window_pp' else ''}"


def _places(refs: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    """Each metric with its periods, in the note's order (DataNotes.tsx placesOf)."""
    places: dict[str, list[str]] = {}
    for ref in refs:
        periods = places.setdefault(ref["label"], [])
        if (period := period_label(ref["period"])) not in periods:
            periods.append(period)
    return list(places.items())


def _comparison_places(note: dict[str, Any]) -> list[tuple[str, list[str]]]:
    return _places([{**ref, "label": _comparison_label(ref)} for ref in note["comparisons"]])


def summary_places(note: dict[str, Any]) -> str:
    """Where a marked note sits, for the summary line: its figures, or, for a note only on growth figures, those
    ("Revenue FY2018, FY2019; Net margin FY2020"), at most SUMMARY_PLACES metrics, then "and N more"."""
    places = _places(note["values"]) if note["values"] else _comparison_places(note)
    shown = "; ".join(f"{label} {', '.join(periods)}" for label, periods in places[:SUMMARY_PLACES])
    return f"{shown} and {len(places) - SUMMARY_PLACES} more" if len(places) > SUMMARY_PLACES else shown


class SummaryClause(NamedTuple):
    words: str
    note: dict[str, Any] | None = None  # a marked note's clause: each export draws its letter its own way
    gap: bool = False  # the gap count: each export says after it how it draws a missing figure


def fine_print_summary(envelope: dict[str, Any]) -> list[SummaryClause]:
    """The data notes' summary line, clause by clause, as the page's DataNotes summary reads (D-061): each note that
    marks a figure, in letter order, with its places and its summary words (data_notes.note_summary); then the gaps,
    the figures and, apart from them, the growth figures with no check recorded, and the calculated figures, each only
    when not zero; and "No figures need review" when every populated figure passed, never beside a note that needs
    review but marks nothing (a record-only note), one on a growth figure included."""
    totals, notes = envelope["totals"], envelope["notes"]
    clauses = [SummaryClause(f"{summary_places(note)}: {note_summary(note['reasons'])}", note)
               for note in notes if marks_figure(note)]
    unknown_comparisons = sum(len(note["comparisons"]) for note in notes if note["kind"] == "unknown")
    if totals["unavailable"]:
        clauses.append(SummaryClause(f"{totals['unavailable']} not in our data", gap=True))
    if totals["unknown"]:
        clauses.append(SummaryClause(f"{count_label(totals['unknown'], 'figure')} with no check recorded"))
    if unknown_comparisons:
        clauses.append(SummaryClause(f"{count_label(unknown_comparisons, 'growth figure')} with no check recorded"))
    if totals["calculated"]:
        clauses.append(SummaryClause(f"{totals['calculated']} calculated from filed figures"))
    if (totals["reviewValues"] == 0 and totals["unknown"] == 0 and totals["passed"] > 0
            and not any(note["kind"] == "review" and not marks_figure(note) for note in notes)):
        clauses.append(SummaryClause(f"No figures need review · {totals['passed']} checked"))
    return clauses


def detail_entries(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The data notes' open detail, as the page's DataNotesList reads: every note, those that mark a figure first,
    each with its id, its letter only when it marks (None otherwise), its message, its places, its counts (its
    figures, and apart from them the growth figures built on them) and its comparisons, each "" when it has none."""
    def listed(places: list[tuple[str, list[str]]]) -> str:
        return "; ".join(f"{label} ({', '.join(periods)})" for label, periods in places)

    entries = []
    for note in [*filter(marks_figure, notes), *(note for note in notes if not marks_figure(note))]:
        figures, growth = len(note["values"]), len(note["comparisons"])
        counts = [count_label(figures, "figure")] if figures else []
        if growth:
            counts.append(count_label(growth, "growth figure") + (f" built on {'it' if figures == 1 else 'them'}" if figures else ""))
        comparisons = _comparison_places(note)
        entries.append({
            "id": note["id"], "letter": note["letter"] if marks_figure(note) else None, "message": note["message"],
            "places": f"{listed(_places(note['values']))}." if note["values"] else "",
            "counts": f"{'; '.join(counts)}." if counts else "",
            "comparisons": f"Comparisons: {listed(comparisons)}." if comparisons else "",
        })
    return entries


def _is_calculated(point: dict[str, Any]) -> bool:
    """charts/model.ts isCalculated: a valued point whose provenance says calculated, or with none, a derived flag."""
    provenance = point.get("provenance")
    return point.get("value") is not None and bool(
        provenance.get("method") == "calculated" if provenance is not None else point.get("derived"))


def _in_sentence(label: str) -> str:
    """A metric's label inside a sentence: its first letter lowercased unless it opens an abbreviation ("EPS
    (diluted)"); a ratio takes its article ("the current ratio")."""
    name = label if re.match(r".[A-Z]", label) else label[:1].lower() + label[1:]
    return f"the {name}" if name.endswith(" ratio") else name


def calculated_metrics(dataset: dict[str, Any]) -> list[str]:
    """The metrics whose every value in the run is calculated, named as reportPresentation.ts
    calculatedMetricsSentence names them inside a sentence. Two or more margins read as "margins" when every margin of
    the run is calculated, so a run with a reported gross margin names its calculated margins one by one."""
    keys = {period.get("key") for period in dataset.get("periods", [])}
    series_list = dataset.get("series", [])

    def fully_calculated(series: dict[str, Any]) -> bool:
        valued = [point for point in series.get("points", []) if point.get("period") in keys and point.get("value") is not None]
        return bool(valued) and all(map(_is_calculated, valued))

    def among(series: dict[str, Any], group: list[dict[str, Any]]) -> bool:
        return any(series is member for member in group)

    calculated = [series for series in series_list if fully_calculated(series)]
    margins = [series for series in series_list if re.search(r"\bmargin$", str(series.get("label", "")), re.IGNORECASE)]
    grouped = len(margins) > 1 and all(among(margin, calculated) for margin in margins)
    names = []
    for series in calculated:
        if not grouped or not among(series, margins):
            names.append(_in_sentence(str(series.get("label", ""))))
        elif series is margins[0]:  # "margins" stands where the run's first margin would
            names.append("margins")
    return names


def calculated_sentence(dataset: dict[str, Any]) -> str:
    """The calculated metrics as one sentence ("Margins, free cash flow and the current ratio are calculated from filed
    figures."), since the figures carry no dagger (D-061); "" when the run calculates no metric in full."""
    names = calculated_metrics(dataset)
    if not names:
        return ""
    listed = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
    verb = "are" if len(names) > 1 or names == ["margins"] else "is"
    return f"{listed[:1].upper()}{listed[1:]} {verb} calculated from filed figures."


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
