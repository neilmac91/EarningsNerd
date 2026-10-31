"""Shared descriptions for analysis PDF and workbook exports.

The dataset owns financial eligibility and calculations. These helpers only present its
provenance; they never recalculate or promote a legacy record to validated status.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Context, Decimal
import math
import re
from typing import Any, NamedTuple

from app.services.trend_analysis.data_notes import marks_figure, note_summary
from app.services.trend_analysis.formatting import NOT_MEANINGFUL
from app.services.trend_analysis.later_filings import later_filing_places
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
# What Sources & methods holds for a figure is what was recorded: a reported figure has no formula, an older calculation
# may have no recorded inputs, and a figure with no provenance may have neither a source link nor a known method.
EVIDENCE = "Sources & methods gives whatever source, method, formula and inputs are recorded for each figure."
PDF_CLOSING = f"{EVIDENCE} {AUTOMATED_CHECKS}"
# The workbook has a cell for a figure in Metrics and on the sheets with charts only (worksheets, each with a chart
# beside its columns): a growth figure off them is in Sources & methods alone.
SHEETS_WITH_CELLS = "In Metrics and the sheets with charts"
WORKBOOK_CLOSING = (f"{EVIDENCE} {SHEETS_WITH_CELLS}, a figure with a data note or a calculation carries a comment. "
                    f"{AUTOMATED_CHECKS}")
# A later filing's different value (MPA WP5a; coherence.md §1.6, D-061) is evidence, never a note: it adds no letter, no
# summary clause and no total (D7). Each file carries what the page's evidence dialog gives (D10, full), and where the
# data notes print the later-filing line, the closing line says where, after EVIDENCE. The line itself ends at its
# counts, so the files point once where the page's "select one to see both filings" pointed (D9).
LATER_FILING_EVIDENCE = ("Where a later filing reports a different value, Sources & methods also gives what the year’s "
                         "own annual report first reported.")
# The files' n/m sentence, where some growth reads n/m across a change of basis (D12), with Sources & methods' lines; the
# page prints none, its chart footnote and dialog saying each cause where it holds. Both its causes are the dataset's
# (trend_analysis/dataset.py _growth): two values of opposite signs (a zero has none: a zero prior year gives no growth,
# never n/m) and a later filing's value.
NOT_MEANINGFUL_CAUSES = ("Growth reads n/m where its two years’ values have opposite signs, or where a later filing "
                         "reports a different value for one or both of its years.")
# A basis n/m's cause in the page dialog's words (SourceValue.tsx), before the growth the two years' own reports give.
BASIS_CHANGE_CAUSE = "Not meaningful: a later filing reports a different value for one or both of the two years."
# The later-filing line (D9, option A): the page's line after the notes (DataNotes.tsx), set as one more detail entry,
# without the page's "select one to see both filings", since nothing in a file can be selected (chief design on #1776,
# as #1659 ruled for the exports). Its n/m clause follows its count, and those growths' places follow as a note's do.
LATER_FILING_MESSAGE = "A later filing reports a different value."
LATER_FILING_GROWTH = "growth across the change reads n/m"
# The quarterly grid's legend for its Q4 header † (MetricsTable.tsx, whose "; it does not" reads ". It does not" here):
# the dagger marks a period, never a figure.
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
    the workbook's evidence dialog; it names its letter only when the note marks the figure (D-061), as the page does.
    A later filing's evidence on the figure follows the note (evidence_lines)."""
    provenance = point.get("provenance") or {}
    notes = [f"Data note {note['letter']}: {note['message']}" if marks_figure(note) else f"Data note: {note['message']}"] if note else []
    notes += evidence_lines(point)
    if point_method(point) == "calculated":
        notes.append(
            "Calculated figure. Sources & methods gives any recorded formula and inputs."
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


def _listed_places(places: list[tuple[str, list[str]]]) -> str:
    """A detail entry's places, as DataNotesList lists them: "Revenue (FY2018, FY2019); Total assets (FY2018)"."""
    return "; ".join(f"{label} ({', '.join(periods)})" for label, periods in places)


def detail_entries(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The data notes' open detail, as the page's DataNotesList reads: every note, those that mark a figure first,
    each with its id, its letter only when it marks (None otherwise), its message, its places, its counts (its
    figures, and apart from them the growth figures built on them) and its comparisons, each "" when it has none."""
    entries = []
    for note in [*filter(marks_figure, notes), *(note for note in notes if not marks_figure(note))]:
        figures, growth = len(note["values"]), len(note["comparisons"])
        counts = [count_label(figures, "figure")] if figures else []
        if growth:
            counts.append(count_label(growth, "growth figure") + (f" built on {'it' if figures == 1 else 'them'}" if figures else ""))
        comparisons = _comparison_places(note)
        entries.append({
            "id": note["id"], "letter": note["letter"] if marks_figure(note) else None, "message": note["message"],
            "places": f"{_listed_places(_places(note['values']))}." if note["values"] else "",
            "counts": f"{'; '.join(counts)}." if counts else "",
            "comparisons": f"Comparisons: {_listed_places(comparisons)}." if comparisons else "",
        })
    return entries


def later_filing_entry(dataset: Mapping[str, Any]) -> dict[str, Any] | None:
    """The later-filing line as one more unlettered entry of the open detail, after the notes (D9, option A): its
    message, its figures' places, their count with the n/m clause where some growth reads n/m across the change, and
    those growths' places; None where no figure of the run carries its own annual report's value, as the page then
    prints no line. Its places are later_filing_places', the twin of the page's laterFilingPlaces (DataNotes.tsx)."""
    places = later_filing_places(dataset)
    if not places["values"]:
        return None
    growth = _places([{**ref, "label": _comparison_label({**ref, "basis": "yoy"})} for ref in places["comparisons"]])
    counts = count_label(len(places["values"]), "figure") + (f"; {LATER_FILING_GROWTH}" if growth else "")
    return {"id": None, "letter": None, "message": LATER_FILING_MESSAGE,
            "places": f"{_listed_places(_places(places['values']))}.", "counts": f"{counts}.",
            "comparisons": f"Comparisons: {_listed_places(growth)}." if growth else ""}


def basis_not_meaningful(dataset: Mapping[str, Any]) -> bool:
    """Whether some growth of the run reads n/m across a change of basis, so Sources & methods names its causes."""
    return bool(later_filing_places(dataset)["comparisons"])


def not_meaningful_lines(dataset: Mapping[str, Any]) -> list[str]:
    """The files' n/m sentence, as the lines each file adds: the one sentence where some growth of the run reads n/m
    across a change of basis (basis_not_meaningful), else none."""
    return [NOT_MEANINGFUL_CAUSES] if basis_not_meaningful(dataset) else []


def pdf_closing(later_filing: bool) -> str:
    """The PDF's closing line: where Sources & methods keeps a figure's evidence, and, where the line prints, that it
    keeps what each year's own annual report first reported."""
    return f"{EVIDENCE} {LATER_FILING_EVIDENCE} {AUTOMATED_CHECKS}" if later_filing else PDF_CLOSING


def workbook_closing(later_filing: bool) -> str:
    """The workbook's closing line, which also says which cells carry a comment: where the line prints, a figure with
    its own annual report's value carries one too."""
    if not later_filing:
        return WORKBOOK_CLOSING
    return (f"{EVIDENCE} {LATER_FILING_EVIDENCE} {SHEETS_WITH_CELLS}, a figure with a data note, a calculation or a "
            f"first-reported value carries a comment. {AUTOMATED_CHECKS}")


def exact_figure(value: Any, unit: Any) -> str:
    """A value as stored, its digits grouped, with its unit: the page's "As filed" form (figureDisplay.ts exactFigure),
    "6,710,800,000 USD", "2.05 USD per share". The exports keep a figure's full precision (the workbook's cells, the
    PDF's Sources & methods), so a later filing's value and the first-reported one never print alike."""
    amount = f"{Decimal(str(value)).normalize():,f}"
    unit = str(unit or "")
    if unit.endswith("/shares"):
        return f"{amount} {unit.removesuffix('/shares')} per share"
    return " ".join(filter(None, (amount, unit)))


def first_reported_sentence(first: Mapping[str, Any], shown: Any) -> str:
    """The evidence sentence (D11; laterFilings.ts firstReportedSentence): the year's own annual report's value, then
    the later filing's, the one shown, each filing named by its form and filed day as stored, a part it lacks left out."""
    unit = first.get("unit")
    own = ", ".join(filter(None, (first.get("form"), first.get("filed_at") and f"filed {first['filed_at']}")))
    later = f" (filed {first['later_filed_at']})" if first.get("later_filed_at") else ""
    return (f"First reported as {exact_figure(first['value'], unit)} in its own annual report{f' ({own})' if own else ''}. "
            f"A later filing{later} reports {exact_figure(shown, unit)}, shown here.")


def disagreement_sentence(first: Mapping[str, Any], shown: Any) -> str | None:
    """What the producer's exact comparison found, in words built from the two values (D2; laterFilings.ts
    disagreementSentence): the opposite sign, or the factor of 1,000ⁿ and which way it runs; None for any other gap."""
    if first.get("disagreement") == "opposite_sign":
        return "A later filing reports the opposite sign."
    if first.get("disagreement") != "scale":
        return None
    steps = math.floor(math.log10(abs(shown / first["value"])) / 3 + 0.5)  # JavaScript's Math.round, as scaleSteps
    return (f"A later filing reports a value {1000 ** abs(steps):,} times {'larger' if steps > 0 else 'smaller'} than "
            "the year’s own annual report.")


def evidence_lines(figure: Mapping[str, Any]) -> list[str]:
    """What the page's evidence dialog says of a figure (D10, full): where a reported figure or a calculation's input
    carries its year's own annual report's value, the two values and filings, then any finding; where a growth reads
    n/m across a change of basis (growth_point), its cause, then the growth as first reported unless the own reports
    give none (the page prints "n/m" across a sign or scale finding). Nothing for any other figure."""
    first, shown = figure.get("first_reported"), figure.get("value")
    if first and shown is not None:
        return [first_reported_sentence(first, shown), *filter(None, [disagreement_sentence(first, shown)])]
    if "first_reported_growth" not in figure:
        return []
    growth = figure["first_reported_growth"]
    # As comparisonLaterFiling: no line where the growth prints nothing (null, or a number that is not finite).
    text = None if growth is None else growth_text(growth, figure["percent"])
    return [BASIS_CHANGE_CAUSE, *([f"As first reported: {text}"] if text else [])]


def growth_text(value: Any, percent: bool) -> str:
    """A growth as the page's dialog prints it (growth.ts formatGrowth, through format.ts fmtPercent and
    fmtPercentPoints): "n/m" for anything but a number; else one decimal, grouped ("+1,234.5%"), rounded half away from
    zero from the value's shortest decimal form as Intl does ("+0.3%" for 0.0025), after the times 100 in binary
    ("+0.4%" for 0.0045, whose product is 0.44999999999999996), a plus only above zero ("0.0%" for zero, "+0.0%" for a
    growth too small to show), and points for a percent series ("-9.5pp"); nothing ("") for a number that is not finite,
    which format.ts parseNumeric refuses, a JSON integer past a double's range included. A JSON integer is read as the
    double the page reads (JSON.parse), so a long one prints the same digits. Not the prompt's
    formatting._fmt_growth, which signs zero, groups nothing and rounds half to even.
    backend/tests/fixtures/analysis_growth_text.json holds the two equal; the wide context lets a value of any finite
    size print every digit Intl prints."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "n/m"
    try:
        number = float(value) if percent else float(value) * 100
    except OverflowError:
        return ""
    if not math.isfinite(number):
        return ""
    rounded = Decimal(repr(number)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP, context=Context(prec=400))
    return f"{'+' if number > 0 else ''}{rounded:,.1f}{'pp' if percent else '%'}"


def growth_point(point: Mapping[str, Any], growth: str, percent: bool) -> dict[str, Any]:
    """A point's YoY or QoQ as a figure of its own, for Sources & methods and its comment: its value, provenance and
    reconciled flag and, where it reads n/m across a change of basis (laterFilings.ts basisChanged: n/m, with the
    first-reported key present, null included), the growth as first reported and its series' percent flag."""
    figure = {"period": point.get("period"), "value": point.get(growth),
              "provenance": point.get(f"{growth}_provenance"), "reconciled": point.get(f"{growth}_reconciled")}
    if point.get(growth) == NOT_MEANINGFUL and f"{growth}_first_reported" in point:
        figure.update(first_reported_growth=point[f"{growth}_first_reported"], percent=percent)
    return figure


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
    listed = _listed(names)
    verb = "are" if len(names) > 1 or names == ["margins"] else "is"
    return f"{listed[:1].upper()}{listed[1:]} {verb} calculated from filed figures."


def _listed(names: list[str]) -> str:
    """"a", "a and b", "a, b and c"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def derived_quarters(dataset: dict[str, Any]) -> list[str]:
    """A quarterly run's Q4 columns with a calculated flow figure, in the run's order, whose header takes the page's †
    (MetricsTable.tsx derivedQuarter): the dagger marks the period, never a figure. An annual run has none."""
    if dataset.get("mode") != "quarterly":
        return []
    return [period.get("key") for period in dataset.get("periods", []) if period.get("fiscal_period") == "Q4" and any(
        point.get("period") == period.get("key") and point.get("value") is not None and point.get("derived")
        and (point.get("provenance") or {}).get("method") != "reported"
        for series in dataset.get("series", []) for point in series.get("points", []))]


def derived_q4_sentence(dataset: dict[str, Any]) -> str:
    """The workbook's words for what the PDF's Q4 header † marks, where it has no header to mark: the columns, named,
    whose flow figures are calculated ("Some flow figures in Q4 2023 and Q4 2024 are calculated from annual totals less
    the first nine months."); "" when the run computes no Q4."""
    quarters = [period_label(key) for key in derived_quarters(dataset)]
    if not quarters:
        return ""
    return f"Some flow figures in {_listed(quarters)} are calculated from annual totals less the first nine months."


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
            if point.get(growth) is not None or point.get(f"{growth}_provenance"):
                yield (growth.upper(), growth_point(point, growth, bool(series.get("percent"))),
                       "percentage points" if series.get("percent") else "fraction")
    for growth, label, unit in (("cagr", "CAGR", "fraction"), ("window_pp", "Window change", "percentage points")):
        provenance = series.get(f"{growth}_provenance")
        if series.get(growth) is not None or provenance:
            yield label, {
                "period": series.get("cagr_window" if growth == "cagr" else "window_pp_range") or period_key,
                "value": series.get(growth), "provenance": provenance,
                "reconciled": series.get(f"{growth}_reconciled"),
            }, unit
