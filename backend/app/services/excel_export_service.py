"""Branded Excel workbook export for Multi-Period Analysis (owner decision D1).

One workbook replaces the old per-dataset CSV download: an **Overview** sheet (brand mark +
provenance + conventions + disclaimer), the full **Metrics** grid (typed cells, real Excel number
formats, derived-Q4 cell comments), and **one data sheet per chart panel** with a native chart —
a single download carrying everything the four on-page trend panels show.

``build_analysis_workbook`` is a PURE function over the deterministic dataset dict
(``trend_analysis_service.build_dataset``) — no DB, no I/O beyond the committed brand PNG — so
tests read the produced bytes straight back with openpyxl.

Conventions (also stated on the Overview sheet, where users see them):

- Monetary values are RAW dollars at full precision, formatted ``#,##0`` — the compact "$24.9B"
  rendering belongs to the PDF and on-page table; the workbook is the machine-usable surface.
- Percent series (margins, YoY growth) are written as TRUE Excel percentages: the cell stores
  the fraction (0.558) and formats as ``0.0%``. Dataset margin values arrive ×100 and are divided
  back down on write; growth ratios arrive as fractions and are written as-is.
- Calculated figures carry a cell Comment, never a fill (a fill reads as data emphasis).
- Sources & methods carries the output values, calculation operands and source links, plus
  explicit reasons for missing or limited figures. Missing values remain blank numeric cells.
- Header rows rest in the ink on a neutral fill and the Overview's labels in the ink: sage colours
  no text here (D-041, applying D-030); the sage tab colour marks the workbook as EarningsNerd's.
- The file names itself (title, subject, EarningsNerd as creator, the export instant as created, English)
  and every sheet prints with the brand footer and a page count: the Overview portrait, the grids and panels
  landscape. Each prints one page wide but Sources, whose 17 audit columns printed at 2.9pt on one page: it
  prints four pages wide (about 8pt in LibreOffice), across then down, repeating its header row and its Metric and
  Period columns. Metrics repeats its header row and label column.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.comments import Comment
from openpyxl.drawing.image import Image as XlsxImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.worksheet import Worksheet

from app.services.pdf_branding import PALETTE
from app.services.analysis_export_metadata import (
    ANALYSIS_DISCLAIMER, FCF_DEFINITION, count_label, display_instant, export_points, formula_text, note_index,
    notes_summary, operand_records, period_label, point_method, point_notes,
)
from app.services.trend_analysis.data_notes import resolve_data_notes
from app.utils.company_names import display_company_name
from app.utils.datetimes import ensure_utc, utcnow

# 256px-wide sage mark on transparent, rasterized by frontend/scripts/generate-brand-assets.mjs
# (openpyxl can't rasterize SVG; the PNG is committed so the backend needs no SVG toolchain).
_MARK_PNG = Path(__file__).resolve().parent.parent / "assets" / "brand" / "earningsnerd-mark.png"

# frontend/components/ui/Chart.tsx CHART_SERIES — positional 1→N, never re-sorted, so workbook
# charts pair series→color exactly like the on-page panels (openpyxl hex carries no '#').
CHART_SERIES: tuple[str, ...] = ("3E8E84", "B8812F", "5B7CC0", "CF7159", "6E7E9C", "8B7BC0")

_TAB_COLOR = PALETTE["brand"].lstrip("#")
_HEADER_FILL = PatternFill("solid", start_color=PALETTE["background"].lstrip("#"))
_HEADER_FONT = Font(bold=True, color=PALETTE["ink"].lstrip("#"), size=10)
_INK_FONT = Font(color=PALETTE["ink"].lstrip("#"))
_LABEL_FONT = Font(bold=True, color=PALETTE["ink"].lstrip("#"))
_FOOTNOTE_FONT = Font(color=PALETTE["ink_tertiary"].lstrip("#"), size=9)
_HAIRLINE = Side(style="thin", color=PALETTE["border"].lstrip("#"))
_CELL_BORDER = Border(left=_HAIRLINE, right=_HAIRLINE, top=_HAIRLINE, bottom=_HAIRLINE)

# The page's Margins, Cash generation and Balance sheet charts (frontend/features/analysis/lib/charts/
# model.ts), each one line chart here: the page draws the balance sheet's equity as a bar panel beside
# its debt and cash lines. The top-line bar chart is built separately, its concept being dataset-
# dependent. A panel whose concepts are all absent gets no sheet (a bank has no gross margin), where
# the page keeps that chart's card and says why it does not apply (E195).
_LINE_PANELS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Margins",
        (("gross_margin", "Gross"), ("operating_margin", "Operating"), ("net_margin", "Net")),
    ),
    (
        "Cash generation",
        (
            ("operating_cash_flow", "Operating CF"),
            ("free_cash_flow", "Free cash flow"),
            ("net_income", "Net income"),
        ),
    ),
    (
        "Balance sheet",
        (
            ("long_term_debt", "Long-term debt"),
            ("shareholders_equity", "Equity"),
            ("cash_and_equivalents", "Cash"),
        ),
    ),
)

_INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")


def _sheet_title(title: str) -> str:
    """Excel sheet names: 31 chars max, no []:*?/\\ characters."""
    return _INVALID_SHEET_CHARS.sub("-", title)[:31]


def _write_text(ws: Worksheet, row: int, column: int, value: Any) -> Cell:
    """Untrusted text → an INERT string cell (boundary rule 9: the dataset carries SEC-sourced
    text — company names, XBRL units). openpyxl auto-types any string starting with "=" as a
    LIVE FORMULA (data_type 'f'); forcing the cell back to 's' pins the xlsx type attribute
    Excel actually trusts, so the value displays verbatim — no evaluation, and no visible
    apostrophe mutation (the alternative guard). Other CSV-injection triggers (+ - @) never
    activate in native xlsx string cells, so this single override covers the class."""
    cell = ws.cell(row=row, column=column, value="" if value is None else str(value))
    cell.data_type = "s"
    return cell


def _number_format(unit: Any, percent: bool) -> str:
    if percent:
        return "0.0%"
    if unit == "pure":
        return '0.00"x"'
    if isinstance(unit, str) and unit.endswith("/shares"):
        return "#,##0.00"
    return "#,##0"


def _write_point(
    ws: Worksheet, row: int, col: int, point: dict[str, Any], unit: Any, percent: bool,
    note: dict[str, Any] | None = None,
) -> None:
    """One dataset point → one typed, formatted, bordered cell (comment for derived Q4)."""
    cell = ws.cell(row=row, column=col)
    cell.border = _CELL_BORDER
    value = point.get("value")
    if value is not None:
        cell.value = value / 100 if percent else value
    cell.number_format = _number_format(unit, percent)
    notes = point_notes(point, note)
    if notes:
        cell.comment = Comment("\n".join(notes), "EarningsNerd")


def _print_setup(
    ws: Worksheet, *, landscape: bool, pages_wide: int = 1, title_rows: str | None = None, title_cols: str | None = None,
) -> None:
    """``pages_wide`` pages wide (as many pages tall as it takes), the brand footer and a page count, and a
    grid's header row and label columns repeated on every page it prints across. A sheet more than a page wide prints
    across, then down, so each run of rows prints its pages side by side."""
    ws.page_setup.orientation = "landscape" if landscape else "portrait"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = pages_wide, 0
    if pages_wide > 1:
        ws.page_setup.pageOrder = "overThenDown"
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.print_title_rows, ws.print_title_cols = title_rows, title_cols
    ws.oddFooter.left.text, ws.oddFooter.right.text = "EarningsNerd · earningsnerd.io", "Page &P of &N"


def _write_header_row(ws: Worksheet, headers: list[str]) -> None:
    for col, text in enumerate(headers, start=1):
        cell = _write_text(ws, 1, col, text)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.border = _CELL_BORDER
        cell.alignment = Alignment(horizontal="left" if col == 1 else "right")


def _display_name(dataset: dict[str, Any]) -> str:
    """The company as the page prints it, never EDGAR's capitals (display only: the dataset's company_name
    feeds its fingerprint and stays as served)."""
    return display_company_name(dataset.get("company_name")) or str(dataset.get("ticker", ""))


def _document_title(dataset: dict[str, Any]) -> str:
    return f"{_display_name(dataset)} · Multi-Period Analysis"


def _has_derived(dataset: dict[str, Any]) -> bool:
    return any(
        point_method(point) == "calculated"
        for series in dataset.get("series", [])
        for point in series.get("points", [])
    )


def _build_overview(ws: Worksheet, dataset: dict[str, Any], exported_at: datetime, envelope: dict) -> None:
    ws.sheet_properties.tabColor = _TAB_COLOR
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 100

    if _MARK_PNG.exists():
        image = XlsxImage(str(_MARK_PNG))
        # Explicit display size (the PNG is 2× for crispness; openpyxl anchors at 96dpi pixels).
        image.width, image.height = 128, 99
        ws.add_image(image, "A1")

    mode_label = "Annual" if dataset.get("mode") == "annual" else "Quarterly"
    periods = dataset.get("periods", [])

    title = _write_text(ws, 7, 1, _document_title(dataset))
    title.font = Font(bold=True, size=15, color=PALETTE["ink"].lstrip("#"))
    subtitle = ws.cell(row=8, column=1, value="Chart & metrics data export · EarningsNerd · AI summaries of SEC filings")
    subtitle.font = _FOOTNOTE_FONT

    facts: list[tuple[str, str]] = [
        ("Ticker", str(dataset.get("ticker", ""))),
        ("Mode", mode_label),
        ("Periods", f"{period_label(dataset.get('period_key', ''))} · {count_label(len(periods), 'period')}"),
        # Instants read as words with their zone named; a data-as-of value that is not an instant prints as stored.
        ("Exported", display_instant(exported_at) or "Not recorded"),
        ("Source data as of", display_instant(dataset.get("data_as_of")) or str(dataset.get("data_as_of") or "Not recorded")),
        ("Dataset version", str(dataset.get("dataset_version") or "Legacy snapshot")),
        ("Snapshot", str(dataset.get("snapshot_id") or "Not recorded")),
        ("Source", "SEC filings and calculations via EarningsNerd · earningsnerd.io"),
    ]
    row = 10
    for label, value in facts:
        ws.cell(row=row, column=1, value=label).font = _LABEL_FONT
        _write_text(ws, row, 2, value).font = _INK_FONT
        row += 1

    notes = [
        "Percent series (margins, growth) are true Excel percentages: a cell showing 55.8% stores 0.558.",
        "Monetary values retain the supplied numeric precision and reporting currencies shown in Metrics and Sources & methods; no currency conversion is applied.",
        "Sources & methods lists reported inputs, formulas, source links and any limitations for each figure.",
        "Sources & methods preserves raw dataset values: a margin of 55.8% is recorded there as 55.8 with unit percent.",
        FCF_DEFINITION,
    ]
    if _has_derived(dataset):
        notes.append(
            "Calculated figures (including computed Q4) carry cell comments; calculation method "
            "is separate from whether the source checks passed."
        )
    notes.append("Data notes")
    if summary := notes_summary(envelope):
        notes.append(summary)
    notes.extend(f"Data note {note['letter']}: {note['message']}" for note in envelope["notes"])
    row += 1
    for note in notes:
        cell = _write_text(ws, row, 1, note)
        cell.font = _FOOTNOTE_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.row_dimensions[row].height = max(30, 15 * (len(note) // 110 + 1))
        row += 1

    row += 1
    disclaimer = ws.cell(
        row=row,
        column=1,
        value=ANALYSIS_DISCLAIMER,
    )
    disclaimer.font = _FOOTNOTE_FONT
    disclaimer.alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ws.row_dimensions[row].height = 78


def _build_metrics(ws: Worksheet, dataset: dict[str, Any], indexed: dict) -> None:
    """The full grid: one row per series, one typed column per period (+ annual window figures)."""
    ws.sheet_properties.tabColor = _TAB_COLOR
    periods = [p.get("key", "") for p in dataset.get("periods", [])]
    series_list = dataset.get("series", [])
    # Window figures exist only in annual mode (CAGR / window pp) — omit the columns otherwise.
    has_window = any(
        s.get("cagr") is not None or s.get("window_pp") is not None for s in series_list
    )

    headers = ["Metric", "Concept", "Unit", *(period_label(period) for period in periods)]
    if has_window:
        headers += ["Window growth", "Window"]
    _write_header_row(ws, headers)

    for row_index, series in enumerate(series_list, start=2):
        unit = series.get("unit", "USD")
        percent = bool(series.get("percent"))
        label_cell = _write_text(ws, row_index, 1, series.get("label", ""))
        label_cell.font = _INK_FONT
        label_cell.border = _CELL_BORDER
        _write_text(ws, row_index, 2, series.get("concept", "")).border = _CELL_BORDER
        unit_cell = _write_text(ws, row_index, 3, "percent" if percent else unit)
        unit_cell.border = _CELL_BORDER

        by_period = {p.get("period"): p for p in series.get("points", [])}
        for offset, period in enumerate(periods):
            note = indexed.get((series["concept"], period, "value"))
            _write_point(ws, row_index, 4 + offset, by_period.get(period) or {}, unit, percent, note)

        if has_window:
            growth_cell = ws.cell(row=row_index, column=4 + len(periods))
            growth_cell.border = _CELL_BORDER
            window_cell = ws.cell(row=row_index, column=5 + len(periods))
            window_cell.border = _CELL_BORDER
            basis = None
            if percent and series.get("window_pp") is not None:
                basis = "window_pp"
                growth_cell.value = series["window_pp"]
                growth_cell.number_format = '0.0" pp"'
                _write_text(ws, row_index, 5 + len(periods), period_label(series.get("window_pp_range")))
            elif series.get("cagr") is not None:
                basis = "cagr"
                growth_cell.value = series["cagr"]
                growth_cell.number_format = "0.0%"
                _write_text(ws, row_index, 5 + len(periods), period_label(series.get("cagr_window")))
            quality = series.get(f"{basis}_reconciled")
            provenance = series.get(f"{basis}_provenance")
            period = series.get("window_pp_range" if basis == "window_pp" else "cagr_window") or dataset.get("period_key", "")
            notes = point_notes({"provenance": provenance, "reconciled": quality},
                                indexed.get((series["concept"], period, basis))) if basis else []
            if notes:
                growth_cell.comment = Comment("\n".join(notes), "EarningsNerd")

    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 11
    for offset in range(len(periods)):
        ws.column_dimensions[get_column_letter(4 + offset)].width = 14
    if has_window:
        ws.column_dimensions[get_column_letter(4 + len(periods))].width = 14
        ws.column_dimensions[get_column_letter(5 + len(periods))].width = 17


def _build_sources(ws: Worksheet, dataset: dict[str, Any], indexed: dict) -> None:
    """A visible audit table, independent of cell-comment support in the viewer."""
    ws.sheet_properties.tabColor = _TAB_COLOR
    headers = [
        "Metric", "Period", "Entry", "Concept", "Value (raw)", "Unit", "Method", "Validation",
        "Reason codes", "Formula", "Period start", "Period end", "Accession", "Filed", "Source tag", "Source URL", "Note",
    ]
    _write_header_row(ws, headers)
    row = 2
    periods = [p.get("key", "") for p in dataset.get("periods", [])]
    bases = {"Value": "value", "YOY": "yoy", "QOQ": "qoq", "CAGR": "cagr", "Window change": "window_pp"}
    for series in dataset.get("series", []):
        for measure, point, unit in export_points(series, periods, dataset.get("period_key", "")):
            provenance = point.get("provenance") or {}
            records = [(measure, {
                **point, "concept": series.get("concept"),
                "unit": unit,
                "provenance": provenance,
                "source_url": point.get("source_url") or provenance.get("source_url"),
            }), *operand_records(provenance)]
            for label, record in records:
                record_provenance = record.get("provenance") or {}
                note = indexed.get((series["concept"], point.get("period"), bases[measure])) if label == measure else None
                values = [
                    series.get("label", series.get("concept")), period_label(point.get("period")), label,
                    record.get("concept"), record.get("value"), record.get("unit"),
                    point_method(record), record_provenance.get("validation", "unknown"),
                    "; ".join(record_provenance.get("reasons") or []), formula_text(record_provenance.get("formula")),
                    record.get("period_start"), record.get("period_end"), record.get("accession"),
                    record.get("filed_at") or record_provenance.get("filed_at"), record.get("raw_tag"),
                    record.get("source_url"),
                    f"Data note {note['letter']}" if note else "",
                ]
                for column, value in enumerate(values, start=1):
                    # Only the numeric data column is typed as a number. Every source/formula
                    # string is inert, including strings beginning with spreadsheet operators.
                    cell = (ws.cell(row=row, column=column, value=value)
                            if column == 5 and (value is None or isinstance(value, (int, float, Decimal)))
                            else _write_text(ws, row, column, value))
                    cell.border = _CELL_BORDER
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    if column == 16 and value and str(value).startswith("https://"):
                        cell.hyperlink = str(value)
                row += 1
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = ws.dimensions
    for column in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(column)].width = {
            1: 25, 4: 25, 5: 21, 9: 40, 10: 50, 15: 45, 16: 60, 17: 16,
        }.get(column, 19)


def _style_line_series(chart: LineChart) -> None:
    for index, chart_series in enumerate(chart.series):
        color = CHART_SERIES[index % len(CHART_SERIES)]
        chart_series.graphicalProperties.line.solidFill = color
        chart_series.graphicalProperties.line.width = 22000  # EMU ≈ 1.75pt, the on-page stroke
        chart_series.smooth = False


def _anchor_for(ws: Worksheet, header_count: int) -> str:
    return f"{get_column_letter(header_count + 2)}2"


def _add_top_line_sheet(wb: Workbook, dataset: dict[str, Any], indexed: dict) -> None:
    """The bar panel: top line (revenue, else net interest income) + YoY growth as a column."""
    by_concept = {s.get("concept"): s for s in dataset.get("series", [])}
    top = by_concept.get("revenue") or by_concept.get("net_interest_income")
    if top is None:
        return
    ws = wb.create_sheet(_sheet_title(f"{top.get('label', 'Top line')} & growth"))
    ws.sheet_properties.tabColor = _TAB_COLOR

    unit = top.get("unit", "USD")
    headers = ["Period", str(top.get("label", "Top line")), "YoY growth"]
    _write_header_row(ws, headers)
    by_period = {p.get("period"): p for p in top.get("points", [])}
    periods = [p.get("key", "") for p in dataset.get("periods", [])]
    for row_index, period in enumerate(periods, start=2):
        _write_text(ws, row_index, 1, period_label(period)).border = _CELL_BORDER
        point = by_period.get(period) or {}
        _write_point(ws, row_index, 2, point, unit, percent=False,
                     note=indexed.get((top["concept"], period, "value")))
        growth_cell = ws.cell(row=row_index, column=3)
        growth_cell.border = _CELL_BORDER
        yoy = point.get("yoy")
        notes = point_notes({"provenance": point.get("yoy_provenance"), "reconciled": point.get("yoy_reconciled")},
                            indexed.get((top["concept"], period, "yoy")))
        if notes:
            growth_cell.comment = Comment("\n".join(notes), "EarningsNerd")
        if isinstance(yoy, (int, float)):
            growth_cell.value = yoy
            growth_cell.number_format = "0.0%"
        elif yoy is not None:
            growth_cell.value = "n/m"  # sign-flip sentinel — not a meaningful percentage

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 12

    chart = BarChart()
    chart.type = "col"
    chart.title = str(top.get("label", "Top line"))
    chart.legend = None
    data = Reference(ws, min_col=2, min_row=1, max_row=1 + len(periods))
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=1 + len(periods)))
    chart.series[0].graphicalProperties.solidFill = CHART_SERIES[0]
    chart.width, chart.height = 20, 10
    ws.add_chart(chart, _anchor_for(ws, len(headers)))


def _add_line_panel_sheets(wb: Workbook, dataset: dict[str, Any], indexed: dict) -> None:
    by_concept = {s.get("concept"): s for s in dataset.get("series", [])}
    periods = [p.get("key", "") for p in dataset.get("periods", [])]

    for title, concepts in _LINE_PANELS:
        present = [(concept, label) for concept, label in concepts if concept in by_concept]
        if not present:
            continue
        ws = wb.create_sheet(_sheet_title(title))
        ws.sheet_properties.tabColor = _TAB_COLOR

        headers = ["Period", *(label for _, label in present)]
        _write_header_row(ws, headers)
        maps = [
            (
                {p.get("period"): p for p in by_concept[concept].get("points", [])},
                by_concept[concept].get("unit", "USD"),
                bool(by_concept[concept].get("percent")),
            )
            for concept, _ in present
        ]
        for row_index, period in enumerate(periods, start=2):
            _write_text(ws, row_index, 1, period_label(period)).border = _CELL_BORDER
            for col_offset, (by_period, unit, percent) in enumerate(maps):
                note = indexed.get((present[col_offset][0], period, "value"))
                _write_point(ws, row_index, 2 + col_offset, by_period.get(period) or {}, unit, percent, note)

        ws.column_dimensions["A"].width = 12
        for col_offset in range(len(present)):
            ws.column_dimensions[get_column_letter(2 + col_offset)].width = 16

        chart = LineChart()
        chart.title = title
        data = Reference(ws, min_col=2, max_col=1 + len(present), min_row=1, max_row=1 + len(periods))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(Reference(ws, min_col=1, min_row=2, max_row=1 + len(periods)))
        _style_line_series(chart)
        chart.width, chart.height = 20, 10
        ws.add_chart(chart, _anchor_for(ws, len(headers)))


def build_analysis_workbook(
    dataset: dict[str, Any], exported_at: Optional[datetime] = None
) -> bytes:
    """The branded analysis workbook as xlsx bytes (pure — tests read them straight back).

    ``exported_at`` is injectable for deterministic tests; the route leaves it defaulted.
    """
    exported = exported_at or utcnow()
    envelope = resolve_data_notes(dataset)
    indexed = note_index(envelope)
    workbook = Workbook()
    # The file's own metadata, which openpyxl otherwise leaves as creator "openpyxl" and no title. openpyxl
    # sets the modified time when it saves, so only the created time is the export's.
    properties = workbook.properties
    properties.creator = properties.lastModifiedBy = "EarningsNerd"
    properties.title = _document_title(dataset)
    mode_label = "Annual" if dataset.get("mode") == "annual" else "Quarterly"
    properties.subject = f"{dataset.get('ticker', '')} · {mode_label} · {period_label(dataset.get('period_key', ''))}"
    properties.created = ensure_utc(exported).astimezone(timezone.utc)
    properties.language = "en"
    overview = workbook.active
    overview.title = "Overview"
    _build_overview(overview, dataset, exported, envelope)
    _print_setup(overview, landscape=False)
    metrics = workbook.create_sheet("Metrics")
    _build_metrics(metrics, dataset, indexed)
    # The raw concept keys stay in column B: it is the machine column.
    _print_setup(metrics, landscape=True, title_rows="1:1", title_cols="A:A")
    sources = workbook.create_sheet("Sources & methods")
    _build_sources(sources, dataset, indexed)
    # Its 17 audit columns printed at 2.9pt on one landscape page (LibreOffice); four pages wide, each repeating
    # Metric and Period, print at about 8pt (REGN's ten years and twelve quarters 8.1pt, META's twelve quarters
    # with 1,542 rows 7.9pt; three wide was 6.8pt).
    # Metric and Period name no single row (REGN's 1,006 rows share 216 pairs), so a run of rows prints its four
    # pages in a row, not 47 pages apart.
    _print_setup(sources, landscape=True, pages_wide=4, title_rows="1:1", title_cols="A:B")
    _add_top_line_sheet(workbook, dataset, indexed)
    _add_line_panel_sheets(workbook, dataset, indexed)
    for panel in workbook.worksheets[3:]:
        _print_setup(panel, landscape=True)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
