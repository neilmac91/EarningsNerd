"""The exports' rendered words keep the voice (docs/voice-and-style.md; CLAUDE.md rule 12).

The frontend's copy gates (no-em-dash-copy.spec.ts, brandCopyRules.spec.ts) read TypeScript only, and a
walk over Python literals cannot see what a PDF, a CSV or a workbook prints once the fixtures have
flowed through summary_sections and the export builders. This test renders the filing-summary PDF and
CSV, the analysis PDF and the workbook (its cells, comments, sheet names and chart titles) for fixtures
that reach every fixed line the four export modules write, and fails on:

1. an em-dash, unless the cell or text run is the bare null token "—" (the one sanctioned em-dash);
2. an exclamation mark;
3. a heading the export modules own that is not in sentence case: the PDFs' titles, the analysis PDF's
   section headings (its narrative carries none here, so every <h2> is the builder's), the CSV's title
   row, and the workbook's title, sheet names, header rows and fact labels. A proper noun passes (the
   company's name, "Multi-Period Analysis", "EarningsNerd", "YoY") and so does any word with no
   lowercase letter (SEC, EDGAR, UTC, 10-K, FY2024).

Out of reach (review): the summary's section titles and table headings, which summary_sections.py
writes in the schema's casing (the voice guide keeps it); and lines that only other data reaches.
"""
from __future__ import annotations

import csv
import html as html_lib
import io
import re
import zipfile
from html.parser import HTMLParser

from openpyxl import load_workbook

import tests.unit.test_excel_export as workbook_fixtures
import tests.unit.test_export_service as export_fixtures
from app.services.excel_export_service import build_analysis_workbook
from app.services.export_service import ExportService
from app.services.trend_analysis.data_notes import data_notes

EM_DASH = "—"
PROPER = ("BIOGEN INC.", "Test & Co", "Multi-Period Analysis", "EarningsNerd")
MIXED_CASE = frozenset({"YoY", "QoQ"})
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'’-]*")
_VOID = frozenset({"br", "meta", "img", "hr", "link", "input", "wbr"})


class _Runs(HTMLParser):
    """A document's text runs (the stylesheet's content strings among them) and its h1/h2 texts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.runs: list[str] = []
        self.headings: list[str] = []
        self._open: list[str] = []
        self._heading: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2"):
            self._heading = []
        if tag not in _VOID:
            self._open.append(tag)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2") and self._heading is not None:
            self.headings.append("".join(self._heading).strip())
            self._heading = None
        while self._open and self._open.pop() != tag:
            pass

    def handle_data(self, data):
        if self._open and self._open[-1] == "style":
            # Margin-box copy, such as the running footer, prints from the stylesheet's content strings.
            self.runs += re.findall(r'"([^"]*)"', " ".join(re.findall(r"content:\s*([^;]+);", data)))
            return
        if data.strip():
            self.runs.append(data)
        if self._heading is not None:
            self._heading.append(data)


def read_html(document: str) -> _Runs:
    parser = _Runs()
    parser.feed(document)
    return parser


def breaks(texts: list[str]) -> list[str]:
    """Texts that carry an em-dash other than the bare null token, or an exclamation mark."""
    return [text for text in texts if (EM_DASH in text and text.strip() != EM_DASH) or "!" in text]


def not_sentence_case(text: str) -> str | None:
    """The first word that breaks sentence case, or None. A proper noun stands in as one capital word."""
    for name in PROPER:
        text = text.replace(name, " NAME ")
    for index, word in enumerate(_WORD.findall(text)):
        if word in MIXED_CASE or not any(c.islower() for c in word):
            continue
        if word[0].isupper() != (index == 0):
            return word
    return None


def _summary():
    sections = export_fixtures._full_sections()
    sections["management_discussion_insights"]["quotes"].append({"quote": "Demand held up in every region."})
    return export_fixtures._make_summary_and_filing(sections)


def _analysis():
    """The PDF fixture with a narrative that carries no heading, a calculated point with its operand's
    source fields, and data notes in every count the summary line prints."""
    analysis = export_fixtures.TestAnalysisPdfHtml()._analysis()
    analysis.narrative_md = "Revenue grew from $1,000 [1] to $1,500 [2]."
    points = analysis.dataset_json["series"][0]["points"]
    points[0]["provenance"] = {"method": "reported", "validation": "needs_review", "reasons": ["source_conflict"]}
    points[1].update(yoy=0.2, yoy_provenance={"method": "calculated", "validation": "needs_review",
                                              "reasons": ["source_conflict"]})
    points[2]["provenance"] = {
        "method": "calculated", "validation": "passed", "reasons": [], "formula": "annual_minus_ytd",
        "inputs": [{"concept": "operating_cash_flow", "value": 2500, "unit": "USD", "period_start": "2024-01-01",
                    "period_end": "2024-12-31", "accession": "0000123456-25-000001", "raw_tag": "us-gaap:Revenues",
                    "filed_at": "2025-02-14", "source_url": "https://www.sec.gov/Archives/edgar/data/1/000012345625000001/"}],
    }
    analysis.dataset_json["data_notes"] = data_notes(analysis.dataset_json)
    return analysis


def _workbook():
    return load_workbook(io.BytesIO(build_analysis_workbook(workbook_fixtures._dataset(),
                                                            exported_at=workbook_fixtures.EXPORTED_AT)))


def _workbook_texts(data: bytes) -> list[str]:
    book = load_workbook(io.BytesIO(data))
    texts = list(book.sheetnames)
    for sheet in book.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    texts.append(cell.value)
                if cell.comment is not None:
                    texts.append(cell.comment.text)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.startswith("xl/charts/"):
                texts += re.findall(r"<a:t>([^<]*)</a:t>", archive.read(name).decode("utf-8"))
    return texts


def test_no_em_dash_or_exclamation_in_what_the_exports_print():
    service = ExportService()
    summary, filing = _summary()
    analysis = _analysis()
    found = {
        "filing PDF": breaks(read_html(service.generate_pdf_html(summary, filing)).runs),
        "analysis PDF": breaks(read_html(service.generate_analysis_pdf_html(
            analysis, export_fixtures.TestAnalysisPdfHtml()._company())).runs),
        "CSV": breaks([cell for row in csv.reader(io.StringIO(service.generate_csv(summary, filing))) for cell in row]),
        "workbook": breaks(_workbook_texts(build_analysis_workbook(
            workbook_fixtures._dataset(), exported_at=workbook_fixtures.EXPORTED_AT))),
    }
    assert found == {name: [] for name in found}


def test_the_headings_the_exports_own_are_in_sentence_case():
    service = ExportService()
    summary, filing = _summary()
    filing_pdf = read_html(service.generate_pdf_html(summary, filing))
    analysis_pdf = read_html(service.generate_analysis_pdf_html(_analysis(), export_fixtures.TestAnalysisPdfHtml()._company()))
    csv_rows = list(csv.reader(io.StringIO(service.generate_csv(summary, filing).removeprefix("﻿"))))
    book = _workbook()
    overview = book["Overview"]
    headings = {
        "filing PDF title": [filing_pdf.headings[0]],
        "analysis PDF headings": analysis_pdf.headings,
        "CSV title row": csv_rows[3],
        "workbook sheet names": book.sheetnames,
        "workbook title": [overview["A7"].value],
        "workbook fact labels": [row[0].value for row in overview.iter_rows(min_row=10) if row[1].value],
        "workbook header rows": [cell.value for sheet in book.worksheets[1:] for cell in sheet[1] if cell.value],
    }
    assert headings["analysis PDF headings"][1:] == [
        "Data notes", "Metrics by period", "Narrative sources", "Sources & methods", "About this document",
    ], "the analysis fixture's narrative must carry no heading, so every <h2> read here is the builder's"
    found = {name: [(text, word) for text in texts if (word := not_sentence_case(html_lib.unescape(str(text))))]
             for name, texts in headings.items()}
    assert found == {name: [] for name in headings}


def test_the_readers_flag_the_forms_this_pr_fixed():
    """Planted forms: the old copy fails each check, and the null token and a sentence-case title pass."""
    assert breaks(["BIOGEN INC. — 10-K Summary", "“We remain focused.” — CEO", "Ready!", EM_DASH, f" {EM_DASH} "]) == [
        "BIOGEN INC. — 10-K Summary", "“We remain focused.” — CEO", "Ready!",
    ]
    assert not_sentence_case("BIOGEN INC. · 10-K Summary") == "Summary"
    assert not_sentence_case("Sources & Methods") == "Methods"
    assert not_sentence_case("BIOGEN INC. · 10-K summary") is None
    assert not_sentence_case("Test & Co · Multi-Period Analysis") is None
    assert not_sentence_case("YoY growth") is None and not_sentence_case("Exported UTC") is None
    runs = read_html("<style>@page { @bottom-left { content: \"A — B\"; } }</style><h1>X · Y summary</h1><td>—</td>")
    assert runs.runs == ["A — B", "X · Y summary", EM_DASH] and runs.headings == ["X · Y summary"]
