"""The analysis PDF and workbook mark only the notes that question a figure (D-061; CLAUDE.md rule 12; MPA WP3-B).

frontend/tests/unit/dataNoteMarking.spec.tsx holds the page and its chart PNG to the rule; this is the exports' half,
over the same shared notes fixture (`tests/fixtures/analysis_data_notes.json`) and through the real builders.

1. Marks. Every case renders as an analysis PDF (its citations cited in the narrative) and a workbook. Every letter the
   PDF raises (any `<sup>`, whose text must be a letter), links to, sets alone as a run of text ("c" or "c.", the
   detail's letter column or a `<strong>c.</strong>`) or names ("Data note c", "Note c"), and every letter the workbook
   sets in a number format, names in any cell or comment ("Data note c") or prints in a clause or entry's shape ("c
   Revenue FY2024: …", "c. …") in any cell, is one of the case's `marked_letters`; and each of them shows: the PDF draws
   the citation supplements' too, the workbook, which carries no narrative, the report's. A site that bypasses
   `marks_figure` draws record_only_and_mixed_marking's record-only c, its unknown d or its gap's e. A format or a raised
   mark the reader does not know fails. What it cannot see: a letter in a shape not named here, such as "(c)" in a
   sentence.
2. Every note stays: each keeps its anchored entry in the PDF (the report's under the grid, a supplement's under
   Narrative sources) and its words in the workbook's Overview, and an annual PDF prints no †.
3. The fine print's words are the page's, read from DataNotes.tsx's source: the summary's count clauses (rendered from
   its templates, the gap's words aside: the PDF draws the page's dash, the workbook says "left blank"), the places
   (at most SUMMARY_PLACES metrics, then "and N more", and the comparison labels), the detail's places, counts and
   comparisons, and the checks sentence. "No figures need review" is held back beside a record-only note on a growth
   figure alone, on dataNoteMarking.spec.tsx's own report. A change of the page's code form fails here until re-read.
4. The calculated sentence names the metrics metrics-table.spec.tsx's sentences name, read from that spec, for the same
   runs, and both files print it, the PDF above its grid and the workbook in its Overview, with their closing lines. The
   Q4 legend is MetricsTable.tsx's, read from its source.
5. The workbook's letter: a marked figure's cell stays a number whose format prints the letter, in every unit, a
   window's change and the top line's growth among them, and "n/m" takes it from the text section, while an "n/m"
   whose note marks nothing keeps General; a chart's value axis keeps the figures' own format, unlinked, so no tick
   prints a letter. A quarterly PDF's Q4 header takes the page's † where a fourth quarter's flow figure is calculated,
   with its legend, and no figure takes one.
6. The Metrics header row ends in the key to the letters the grid prints, exactly when it prints one: a note marked only
   on a YoY or QoQ figure, which the grid does not show, stays out of it.
7. Every line of the fine print both files print holds the reason words' surface rules (test_analysis_data_notes.py): no
   page action, no drawing, no single figure, no semicolon. The gap words alone say how each file draws a gap, which is
   their job; the detail's entries list places and counts with "; " and their messages are the reason words, which
   that test holds.
8. The PDF's summary line stays on the grid's last page (WeasyPrint): at the row count where, without the rule, it
   would start the next page, the last row moves with it; the sentence above the grid shares the grid's first page.
"""
from __future__ import annotations

import html as html_lib
import io
import json
import re
import zipfile
from copy import deepcopy
from html import escape
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from app.services.analysis_export_metadata import (
    AUTOMATED_CHECKS, DERIVED_Q4_LEGEND, FCF_DEFINITION, PDF_CLOSING, QUARTER_LEGEND, SUMMARY_PLACES, WORKBOOK_CLOSING,
    _comparison_label, calculated_sentence, detail_entries, fine_print_summary, summary_places,
)
from app.services.excel_export_service import build_analysis_workbook
from app.services.export_service import ANALYSIS_GRID_PRECISION, ANALYSIS_GRID_ROUNDING, ExportService
from app.services.trend_analysis.data_notes import data_notes, marks_figure
from tests.unit.test_analysis_data_notes import DRAWING, _surface_problems
from tests.unit.test_export_voice import read_html

FIXTURE = json.loads((Path(__file__).parents[1] / "fixtures" / "analysis_data_notes.json").read_text())
CASES = FIXTURE["cases"]
COMPANY = SimpleNamespace(name="Test Co", ticker="TST")
FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
ANALYSIS_COMPONENTS = FRONTEND / "features" / "analysis" / "components"

PDF_MARK = re.compile(r'<sup class="data-note"><a href="#analysis-data-note-([a-z]+)">([a-z]+)</a></sup>')
PDF_LINK = re.compile(r'href="#analysis-data-note-([a-z]+)"')
# A letter named in words, in either file: "Data note c", and in the PDF "Note c" too.
NAMED = re.compile(r"\bData note ([a-z]{1,2})\b")
# Every format the workbook sets, with the letter a marked note adds: '#,##0" a"', '0.00"x a"', '0.0" pp a"', '@" a"'.
FORMAT = re.compile(r'(?:#,##0(?:\.00)?|0\.0%|0\.00"x|0\.0" pp|@|General)(?:"? (?P<letter>[a-z]+))?"?')


def _analysis(case: dict) -> SimpleNamespace:
    dataset = deepcopy(case["dataset"])
    dataset["data_notes"] = deepcopy(case["expected"])
    citations = [{**citation, "n": index, "excerpt": f"Source {index}"}
                 for index, citation in enumerate(deepcopy(case.get("citations", [])), start=1)]
    if "expected_citation_notes" in case:
        dataset["narrative_presentation"] = {"notes": deepcopy(case["expected_citation_notes"])}
    narrative = " ".join(f"Figure [{citation['n']}]." for citation in citations) or "No figures cited."
    return SimpleNamespace(mode=dataset["mode"], period_key=dataset["period_key"], dataset_json=dataset,
                           narrative_md=narrative, citations_json=citations)


def pdf_letters(html: str) -> set[str]:
    marks = PDF_MARK.findall(html)
    assert all(target == shown for target, shown in marks), "a letter links to another note's entry"
    letters = set(PDF_LINK.findall(html))
    for raised in re.findall(r"<sup\b[^>]*>(.*?)</sup>", html, re.S):
        text = re.sub(r"<[^>]+>", "", raised).strip()
        assert re.fullmatch(r"[a-z]{1,2}", text), f"a raised mark the reader does not know: {raised!r}"
        letters.add(text)
    for run in read_html(html[html.index("<body"):]).runs:  # the body's text, not the page counter's " of "
        if alone := re.fullmatch(r"\s*([a-z]{1,2})\.?\s*", run):
            letters.add(alone[1])
        letters |= set(NAMED.findall(run)) | set(re.findall(r"\bNote ([a-z]{1,2})\b", run))
    return letters


def workbook_letters(data: bytes) -> set[str]:
    book = load_workbook(io.BytesIO(data))
    letters: set[str] = set()
    for sheet in book.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                found = FORMAT.fullmatch(cell.number_format)
                assert found, f"{sheet.title}!{cell.coordinate}: a format the reader does not know, {cell.number_format!r}"
                letters |= {found["letter"]} - {None}
                texts = [cell.value] if isinstance(cell.value, str) else []
                for text in [*texts, *([cell.comment.text] if cell.comment is not None else [])]:
                    # Named ("Data note c"), a summary or key clause ("c Revenue FY2024: …") and a detail entry ("c. …").
                    letters |= set(NAMED.findall(text)) | set(re.findall(r"(?:^| · )([a-z]{1,2}) (?=\S)", text))
                    letters |= set(re.findall(r"^([a-z]{1,2})\. ", text))
    return letters


# A case whose reason codes hold a lone surrogate, which no XML document can carry: the workbook's Sources sheet prints a
# value's reason codes (as before WP3-B), so only its PDF is read.
NO_WORKBOOK = {"portable_reason_identity_utf16_ascii": "its reason codes hold a lone surrogate (U+D800)"}


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_the_exports_draw_exactly_the_letters_of_notes_that_question_a_figure(case):
    analysis = _analysis(case)
    html = ExportService().generate_analysis_pdf_html(analysis, COMPANY)
    assert pdf_letters(html) == set(case["marked_letters"])
    # Every note stays: its anchored entry in the PDF.
    notes = (case.get("expected_citation_notes") or case["expected"])["notes"]
    assert [note["id"] for note in notes if f'<li id="{note["id"]}">' not in html] == []
    if case["dataset"]["mode"] == "annual":
        assert "†" not in html
    if case["name"] in NO_WORKBOOK:
        return
    workbook = build_analysis_workbook(deepcopy(analysis.dataset_json))
    assert workbook_letters(workbook) == {note["letter"] for note in case["expected"]["notes"] if marks_figure(note)}
    # And its words in the workbook's fine print.
    overview = "\n".join(str(row[0]) for row in load_workbook(io.BytesIO(workbook))["Overview"].iter_rows(values_only=True)
                         if row[0])
    assert [note["letter"] for note in case["expected"]["notes"] if note["message"] not in overview] == []


def test_only_the_named_case_skips_the_workbook():
    case = next(case for case in CASES if case["name"] in NO_WORKBOOK)
    with pytest.raises(ValueError):  # lxml refuses the surrogate
        build_analysis_workbook(deepcopy({**case["dataset"], "data_notes": case["expected"]}))


def test_the_gate_reads_a_letter_wherever_an_export_can_set_one():
    """Planted: the record-only case's c, unknown d and gap e set where a site that bypasses the rule would set them, in
    the forms the exports use and in others they could."""
    case = next(case for case in CASES if case["name"] == "record_only_and_mixed_marking")
    html = ExportService().generate_analysis_pdf_html(_analysis(case), COMPANY)
    for planted, letter in (('$1<sup class="data-note"><a href="#analysis-data-note-c">c</a></sup>', "c"),
                            ('<span class="note-letter">d.</span>', "d"), ('<a href="#analysis-data-note-e">', "e"),
                            ("<li><strong>c.</strong> Shown as stored.</li>", "c"), ("<td>$1<sup>d</sup></td>", "d"),
                            ("<p>Data note e: Not in our data.</p>", "e"), ("<p>See Note c.</p>", "c")):
        assert pdf_letters(html.replace("</body>", planted + "</body>")) - pdf_letters(html) == {letter}, planted
    with pytest.raises(AssertionError, match="a raised mark the reader does not know"):
        pdf_letters(html.replace("</body>", "<p>$1<sup>†</sup></p></body>"))

    def letters_after(plant) -> set[str]:
        book = load_workbook(io.BytesIO(build_analysis_workbook(deepcopy(case["dataset"]))))
        plant(book)
        buffer = io.BytesIO()
        book.save(buffer)
        return workbook_letters(buffer.getvalue()) - {"a", "b"}

    def formats(book):
        for cell, number_format in (("D2", '#,##0" c"'), ("D3", '0.00"x d"'), ("E2", '0.0" pp e"'), ("E3", '@" e"')):
            book["Metrics"][cell].number_format = number_format

    assert letters_after(formats) == {"c", "d", "e"}
    assert letters_after(lambda book: setattr(book["Metrics"]["D5"].comment, "text", "Data note e: Not in our data.")) == {"e"}
    assert letters_after(lambda book: book["Overview"].append(["c. Shown as stored."])) == {"c"}
    # The Overview's form before WP3-B, a letter named in any sheet's cell, and a clause's shape in any cell.
    assert letters_after(lambda book: book["Overview"].append(["Data note c: Shown as stored."])) == {"c"}
    assert letters_after(lambda book: book["Sources & methods"].cell(2, 5, "Data note d")) == {"d"}
    assert letters_after(lambda book: book["Cash generation"].cell(2, 1, "e Net income FY2023: no check")) == {"e"}
    with pytest.raises(AssertionError, match="a format the reader does not know"):
        letters_after(lambda book: setattr(book["Metrics"]["D2"], "number_format", '#,##0"(c)"'))


# ---- The fine print, as the page's DataNotes.tsx ---------------------------------------------------------------
def _growth_only(yoy: dict) -> dict:
    """dataNoteMarking.spec.tsx's report: every value passed and none lacks its record; the FY2024 YoY carries `yoy`."""
    passed = {"version": 1, "method": "reported", "validation": "passed", "reasons": [], "formula": None, "inputs": []}
    dataset = {"mode": "annual", "period_key": "FY2023..FY2024", "periods": [{"key": "FY2023"}, {"key": "FY2024"}],
               "series": [{"concept": "revenue", "label": "Revenue", "unit": "USD", "points": [
                   {"period": "FY2023", "value": 100, "provenance": passed},
                   {"period": "FY2024", "value": 110, "provenance": passed, "yoy": 0.1, "yoy_provenance": yoy}]}]}
    return data_notes(dataset)


def test_the_summary_never_clears_a_report_beside_a_record_only_note():
    legacy = _growth_only({"method": "calculated", "validation": "needs_review", "reasons": ["legacy_calculation"]})
    # Every value passed and none is unknown: the counts alone would clear the report.
    assert {key: legacy["totals"][key] for key in ("reviewValues", "reviewComparisons", "unknown", "passed")} == {
        "reviewValues": 0, "reviewComparisons": 1, "unknown": 0, "passed": 2}
    assert [clause.words for clause in fine_print_summary(legacy)] == []
    cleared = _growth_only({"method": "calculated", "validation": "passed", "reasons": []})
    assert [clause.words for clause in fine_print_summary(cleared)] == ["No figures need review · 2 checked"]


def test_the_summary_and_detail_read_as_the_page_reads_them():
    case = next(case for case in CASES if case["name"] == "record_only_and_mixed_marking")
    clauses = fine_print_summary(case["expected"])
    # dataNoteMarking.spec.tsx: "a Free cash flow FY2024: not yet matched to the filing", never the record-only
    # sentence the mixed note's message opens with; then the counts.
    assert [(clause.note and clause.note["letter"], clause.words, clause.gap) for clause in clauses] == [
        ("a", "Free cash flow FY2024: not yet matched to the filing", False),
        ("b", "Long-term debt FY2024: the filings report different values (the most recent shown)", False),
        (None, "1 not in our data", True),
        (None, "1 figure with no check recorded", False),
        (None, "4 calculated from filed figures", False),
    ]
    entries = {entry["id"]: entry for entry in detail_entries(case["expected"]["notes"])}
    assert [entry["letter"] for entry in entries.values()] == ["a", "b", None, None, None]
    legacy = entries["analysis-data-note-c"]
    assert (legacy["places"], legacy["counts"]) == ("Operating margin (FY2023, FY2024).", "2 figures; 1 growth figure built on them.")
    # A note on growth figures alone names them, and the summary names at most three metrics, then counts the rest.
    note = {"values": [], "comparisons": [
        {"label": label, "period": period, "basis": basis} for label, period, basis in (
            ("Revenue", "FY2024", "yoy"), ("Revenue", "FY2022..FY2024", "cagr"), ("Net margin", "FY2022..FY2024", "window_pp"),
            ("Free cash flow", "2026Q2", "qoq"), ("Free cash flow", "2026Q3", "qoq"))]}
    assert summary_places(note) == ("Revenue YoY FY2024; Revenue CAGR FY2022–FY2024; "
                                    "Net margin window percentage-point change FY2022–FY2024 and 1 more")
    note["comparisons"] = note["comparisons"][3:]
    assert summary_places(note) == "Free cash flow QoQ Q2 2026, Q3 2026"
    assert detail_entries([{**case["expected"]["notes"][2], "values": [], "comparisons": note["comparisons"]}])[0][
        "counts"] == "2 growth figures."


def _page(pattern: str, source: str, what: str) -> re.Match:
    found = re.search(pattern, source)
    assert found, f"DataNotes.tsx's {what} moved: re-read it and the port in analysis_export_metadata.py"
    return found


def _render(template: str, values: dict[str, int]) -> str:
    """One of DataNotes.tsx's summary spans as the page renders it: `{plural(count, 'one', 'many')}` and `{name}`."""
    text = re.sub(r"\{plural\(([\w.]+), '([^']*)', '([^']*)'\)\}",
                  lambda found: f"{values[found[1]]} {found[2] if values[found[1]] == 1 else found[3]}", template)
    return re.sub(r"\{([\w.]+)\}", lambda found: str(values[found[1]]), text)


def test_the_fine_print_reads_the_page_words():
    page = (ANALYSIS_COMPONENTS / "DataNotes.tsx").read_text(encoding="utf-8")
    # The summary's count clauses: each `&& <span> · …</span>}` span but the sample's, rendered from its template.
    spans = [span for span in re.findall(r"&& <span> · (.*?)</span>\}", page) if "sample data" not in span]
    gap = '{totals.unavailable} not in our data, shown as <MissingValue label="a dash" />'
    assert len(spans) == 5 and spans[0] == gap, "DataNotes.tsx's count clauses moved: re-read them"

    def page_tail(envelope: dict, gap_words: str) -> str:
        totals, notes = envelope["totals"], envelope["notes"]
        values = {f"totals.{name}": count for name, count in totals.items()}
        values["unknownComparisons"] = sum(len(note["comparisons"]) for note in notes if note["kind"] == "unknown")
        shown = [spans[0].replace(' shown as <MissingValue label="a dash" />', gap_words)] if totals["unavailable"] else []
        conditions = (totals["unknown"], values["unknownComparisons"], totals["calculated"])
        shown += [span for span, count in zip(spans[1:4], conditions) if count]
        # When "No figures need review" stands is held by test_the_summary_never_clears_…; here, its words.
        cleared = [clause for clause in fine_print_summary(envelope) if clause.words.startswith("No figures need review")]
        return " · ".join(_render(span, values) for span in shown + spans[4:] * bool(cleared))

    def files(case: dict) -> tuple[str, str]:
        html = ExportService().generate_analysis_pdf_html(_analysis(case), COMPANY)
        pdf = html_lib.unescape(re.sub(r"<[^>]+>", "", re.search(
            r'<p class="fine-print data-notes-summary">(.*?)</p>', html, re.S)[1]))
        overview = [str(row[0]) for row in load_workbook(io.BytesIO(build_analysis_workbook(deepcopy(
            {**case["dataset"], "data_notes": case["expected"]}))))["Overview"].iter_rows(values_only=True) if row[0]]
        return pdf, overview[overview.index("Data notes") + 1]

    for name in ("mixed_quarterly_quality_and_gaps", "explicit_passed_and_calculated_are_independent"):
        case = next(case for case in CASES if case["name"] == name)
        pdf, workbook = files(case)
        # The PDF draws the page's dash (its own run); the workbook says how it draws a gap.
        assert pdf.endswith(page_tail(case["expected"], " shown as —")), (name, pdf)
        assert workbook.endswith(page_tail(case["expected"], " left blank")), (name, workbook)

    # The places: at most SUMMARY_PLACES metrics, joined as the page joins them, then "and N more".
    assert int(_page(r"const SUMMARY_PLACES = (\d+)", page, "SUMMARY_PLACES")[1]) == SUMMARY_PLACES
    joined = _page(r"`\$\{label\} \$\{periods\.join\('([^']*)'\)\}`\)\.join\('([^']*)'\)", page, "summary places")
    more = _page(r"`\$\{shown\}( and )\$\{places\.length - SUMMARY_PLACES\}( more)`", page, "and N more")
    labels = _page(r"const comparisonLabel = \(basis: string\) => (.*)", page, "comparison labels")[1]
    words = dict(re.findall(r"basis === '(\w+)' \? '([^']*)'", labels)) | {"cagr": re.search(r": '([^']*)'\s*$", labels)[1]}
    suffixes = set(re.findall(r"\.basis === 'window_pp' \? '([^']*)' : ''", page))
    assert words.keys() == {"qoq", "yoy", "window_pp", "cagr"} and len(suffixes) == 1, (words, suffixes)
    for basis, word in words.items():
        suffix = suffixes.copy().pop() if basis == "window_pp" else ""
        assert _comparison_label({"label": "Revenue", "basis": basis}) == f"Revenue {word}{suffix}", basis
    places = [(f"Metric {index}", ["FY2023", "FY2024"]) for index in range(SUMMARY_PLACES + 1)]
    note = {"values": [{"label": label, "period": period} for label, periods in places for period in periods],
            "comparisons": []}
    shown = joined[2].join(f"{label} {joined[1].join(periods)}" for label, periods in places[:SUMMARY_PLACES])
    assert summary_places(note) == f"{shown}{more[1]}1{more[2]}"

    # The detail: places, counts and comparisons, as DataNotesList writes them.
    listed = _page(r"placesOf\(note\.values\)\.map\(\(\[label, periods\]\) => `\$\{label\} \(\$\{periods\.join\('([^']*)'\)"
                   r"\}\)`\)\.join\('([^']*)'\)\}\.", page, "detail places")
    figure = _page(r"\$\{figures\} \$\{figures === 1 \? '([^']*)' : '([^']*)'\}", page, "figure count")
    growth = _page(r"\$\{growth\} \$\{growth === 1 \? '([^']*)' : '([^']*)'\}\$\{figures \? `( built on )\$\{figures === 1 \? "
                   r"'([^']*)' : '([^']*)'\}` : ''\}", page, "growth count")
    counts_joined = _page(r"\]\.join\('([^']*)'\)\}\.</p>", page, "counts' join")
    compared = _page(r"(Comparisons: )\{comparisonPlaces\.map\(\(\[label, periods\]\) => `\$\{label\} \(\$\{periods\.join\("
                     r"'([^']*)'\)\}\)`\)\.join\('([^']*)'\)\}\.", page, "comparisons")
    probes = {
        (2, 1): f"2 {figure[2]}{counts_joined[1]}1 {growth[1]}{growth[3]}{growth[5]}",
        (1, 2): f"1 {figure[1]}{counts_joined[1]}2 {growth[2]}{growth[3]}{growth[4]}",
        (0, 3): f"3 {growth[2]}",
    }
    for (figures, growths), counts in probes.items():
        note = {"id": "analysis-data-note-a", "letter": "a", "kind": "review", "reasons": ["source_conflict"],
                "message": "M.", "values": [{"label": "Revenue", "period": f"FY{2020 + index}"} for index in range(figures)],
                "comparisons": [{"label": "Net margin", "period": f"FY{2020 + index}", "basis": "yoy"} for index in range(growths)]}
        entry = detail_entries([note])[0]
        assert entry["counts"] == f"{counts}.", (figures, growths)
        if figures:
            periods = listed[1].join(f"FY{2020 + index}" for index in range(figures))
            assert entry["places"] == f"Revenue ({periods}).", entry
        periods = compared[2].join(f"FY{2020 + index}" for index in range(growths))
        assert entry["comparisons"] == f"{compared[1]}Net margin {words['yoy']} ({periods}).", entry

    # The checks sentence: the page's, with "confirm that" and its semicolon read as the surface rules ask.
    checks = _page(r"(Automated checks confirm [^<]*?accounts\.)", page, "checks sentence")[1]
    assert AUTOMATED_CHECKS == checks.replace("confirm that", "confirm").replace("; they", ". They")


# ---- The calculated sentence, as reportPresentation.ts ---------------------------------------------------------
def _run(*rows: tuple[str, str, bool, bool]) -> dict:
    """metrics-table.spec.tsx's runs: each row (concept, label, calculated, percent) with a value in both years."""
    def provenance(calculated: bool) -> dict:
        return {"version": 1, "method": "calculated" if calculated else "reported", "validation": "passed",
                "reasons": [], "formula": None, "inputs": []}
    return {"mode": "annual", "period_key": "FY2023..FY2024", "periods": [{"key": "FY2023"}, {"key": "FY2024"}],
            "series": [{"concept": concept, "label": label, "percent": percent, "points": [
                {"period": period, "value": 10 + index, "provenance": provenance(calculated)}
                for index, period in enumerate(("FY2023", "FY2024"))]} for concept, label, calculated, percent in rows]}


def test_the_calculated_sentence_names_what_the_page_names():
    revenue, fcf = ("revenue", "Revenue", False, False), ("free_cash_flow", "Free cash flow", True, False)
    operating, net = ("operating_margin", "Operating margin", True, True), ("net_margin", "Net margin", True, True)
    regn = [revenue, operating, net, fcf, ("working_capital", "Working capital", True, False),
            ("current_ratio", "Current ratio", True, False)]
    partly = _run(revenue, fcf, operating)
    partly["series"][2]["points"][1]["provenance"]["method"] = "reported"
    runs = [
        _run(revenue, operating, fcf, ("eps_diluted", "EPS (diluted)", True, False)),
        partly,
        _run(*regn),
        _run(regn[0], ("gross_margin", "Gross margin", False, True), *regn[1:]),
        _run(*regn[:3]),
    ]
    spec = (FRONTEND / "tests" / "unit" / "metrics-table.spec.tsx").read_text(encoding="utf-8")
    page = re.findall(r"'Figures are rounded for display; (.+?) calculated from filed figures\. Select any value", spec)
    assert len(page) == len(runs), "metrics-table.spec.tsx's calculated sentences moved: re-read them"
    assert [calculated_sentence(run) for run in runs] == [f"{words[:1].upper()}{words[1:]} calculated from filed figures."
                                                          for words in page]
    assert calculated_sentence(_run(revenue)) == ""


def test_both_files_print_the_calculated_sentence_and_their_closing_lines():
    """The sentence replaces the dagger (D-061): a run that calculates a metric in full names it above the PDF's grid
    and in the workbook's Overview; a run that calculates none names nothing. Each file ends its fine print in its
    closing line."""
    calculated = _run(("revenue", "Revenue", False, False), ("operating_margin", "Operating margin", True, True),
                      ("net_margin", "Net margin", True, True), ("free_cash_flow", "Free cash flow", True, False))
    sentence = calculated_sentence(calculated)
    assert sentence == "Margins and free cash flow are calculated from filed figures."
    for dataset, named in ((calculated, sentence), (_run(("revenue", "Revenue", False, False)), "")):
        dataset["data_notes"] = data_notes(dataset)
        analysis = SimpleNamespace(mode="annual", period_key=dataset["period_key"], dataset_json=dataset, narrative_md="",
                                   citations_json=[])
        html = ExportService().generate_analysis_pdf_html(analysis, COMPANY)
        lead = " ".join(filter(None, (ANALYSIS_GRID_ROUNDING, named, ANALYSIS_GRID_PRECISION)))
        assert f'<h2>Metrics by period</h2>\n                <p class="fine-print">{escape(lead)}</p>' in html, named
        assert f'<p class="fine-print">{escape(PDF_CLOSING)}</p>' in html
        overview = [row[0] for row in load_workbook(io.BytesIO(build_analysis_workbook(dataset)))["Overview"].iter_rows(
            values_only=True) if row[0]]
        assert (named in overview) is bool(named) and overview.count(WORKBOOK_CLOSING) == 1
        if named:  # among the conventions, after the definitions
            assert overview.index(FCF_DEFINITION) + 1 == overview.index(named)


def test_the_q4_legend_is_the_pages():
    """MetricsTable.tsx's legend, its "; it does not" read ". It does not" (the surface rules' semicolon)."""
    table = (ANALYSIS_COMPONENTS / "MetricsTable.tsx").read_text(encoding="utf-8")
    legend = re.search(r"\? ' (Fiscal quarters follow [^']*?calculated\.)'", table)
    assert legend, "MetricsTable.tsx's quarterly legend moved: re-read it"
    assert f"{QUARTER_LEGEND} {DERIVED_Q4_LEGEND}" == legend[1].replace("; it does not", ". It does not")


# ---- The workbook's letter ---------------------------------------------------------------------------------------
def test_a_marked_figure_stays_a_number_whose_format_prints_its_letter():
    from tests.unit.test_excel_export import _dataset

    dataset = _dataset()
    conflict = {"method": "reported", "validation": "needs_review", "reasons": ["source_conflict"]}
    revenue, margin, eps, ratio = dataset["series"][:4]
    revenue["points"][0]["provenance"] = conflict
    revenue["points"][1]["yoy_provenance"] = revenue["points"][2]["yoy_provenance"] = conflict
    revenue["cagr_provenance"] = margin["points"][0]["provenance"] = margin["window_pp_provenance"] = conflict
    eps["points"][0]["provenance"] = ratio["points"][0]["provenance"] = conflict
    data = build_analysis_workbook(dataset)
    book = load_workbook(io.BytesIO(data))
    metrics, top = book["Metrics"], book["Revenue & growth"]
    expected = {
        (metrics, "D2"): '#,##0" a"', (metrics, "D3"): '0.0%" a"', (metrics, "D4"): '#,##0.00" a"',
        (metrics, "D5"): '0.00"x a"', (metrics, "G2"): '0.0%" a"', (metrics, "G3"): '0.0" pp a"',
        (top, "B2"): '#,##0" a"', (top, "C3"): '0.0%" a"', (book["Margins"], "B2"): '0.0%" a"',
    }
    for (sheet, cell), number_format in expected.items():
        assert (sheet[cell].data_type, sheet[cell].number_format) == ("n", number_format), f"{sheet.title}!{cell}"
    # "n/m" is text: its letter comes from the format's text section.
    assert (top["C4"].value, top["C4"].data_type, top["C4"].number_format) == ("n/m", "s", '@" a"')
    # An unmarked figure keeps its format; a gap marks nothing.
    assert (metrics["E2"].number_format, metrics["E3"].number_format, metrics["D6"].number_format) == ("#,##0", "0.0%", "#,##0")
    # A chart's value axis keeps the figures' own format, unlinked, so no tick prints the letter (LibreOffice set
    # "1,600 a" on every tick of a linked axis).
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        axes = [re.findall(r'<numFmt formatCode="([^"]*)" sourceLinked="0"/>', archive.read(name).decode())
                for name in sorted(archive.namelist()) if name.startswith("xl/charts/chart")]
    assert axes == [["#,##0"], ["0.0%"], ["#,##0"], ["#,##0"]]


def test_an_n_m_whose_note_marks_nothing_keeps_general():
    """The top line's "n/m" YoY takes a letter from its text section only where its note questions the number: a
    record-only note and a missing check record leave it as written, General, with its comment."""
    from tests.unit.test_excel_export import _dataset

    for provenance in ({"method": "calculated", "validation": "needs_review", "reasons": ["legacy_calculation"]},
                       {"method": "calculated", "validation": "unknown", "reasons": []}):
        dataset = _dataset()
        dataset["series"][0]["points"][2]["yoy_provenance"] = provenance
        top = load_workbook(io.BytesIO(build_analysis_workbook(dataset)))["Revenue & growth"]
        assert (top["C4"].value, top["C4"].number_format) == ("n/m", "General"), provenance
        assert top["C4"].comment.text.startswith("Data note: "), provenance


def test_the_metrics_header_row_keys_the_letters_its_grid_prints():
    from tests.unit.test_excel_export import _dataset

    plain = load_workbook(io.BytesIO(build_analysis_workbook(_dataset())))["Metrics"]
    assert [cell.value for cell in plain[1]][-1] == "Window"  # no marked note: no key
    dataset = _dataset()
    dataset["series"][0]["points"][0]["provenance"] = {"method": "reported", "validation": "needs_review",
                                                       "reasons": ["source_check_needed"]}
    metrics = load_workbook(io.BytesIO(build_analysis_workbook(dataset)))["Metrics"]
    headers = [cell.value for cell in metrics[1]]
    key = metrics.cell(1, headers.index("Window") + 2)
    assert key.value == "Data notes · a Revenue FY2022: not yet matched to the filing"
    assert key.fill.fill_type is None and key.border.bottom.style is None and key.alignment.wrap_text
    assert str(key.font.color.rgb).endswith("636A77") and key.font.size == 9  # the footnote font
    assert metrics.freeze_panes == "B2" and metrics["A1"].value == "Metric"
    # A note marked only on a growth figure the grid does not show (a YoY) stays out of the key, and alone prints none;
    # the Overview's summary names it.
    margin = dataset["series"][1]
    margin["points"][2].update(yoy=4.3, yoy_provenance={"method": "calculated", "validation": "needs_review",
                                                        "reasons": ["calculation_mismatch"]})
    book = load_workbook(io.BytesIO(build_analysis_workbook(dataset)))
    assert book["Metrics"].cell(1, headers.index("Window") + 2).value == key.value
    assert any("b Net margin YoY FY2024: not confirmed" in str(row[0]) for row in book["Overview"].iter_rows(values_only=True))
    dataset["series"][0]["points"][0].pop("provenance")
    alone = load_workbook(io.BytesIO(build_analysis_workbook(dataset)))["Metrics"]
    assert [cell.value for cell in alone[1]][-1] == "Window"


# ---- The exports' own words ----------------------------------------------------------------------------------------
def _quarterly_q4(derived: bool) -> SimpleNamespace:
    dataset = {"mode": "quarterly", "period_key": "2024Q3..2025Q1", "periods": [
        {"key": "2024Q3", "fiscal_period": "Q3"}, {"key": "2024Q4", "fiscal_period": "Q4"},
        {"key": "2025Q1", "fiscal_period": "Q1"}], "series": [
        {"concept": "revenue", "label": "Revenue", "unit": "USD", "points": [
            {"period": "2024Q3", "value": 300.0}, {"period": "2024Q4", "value": 400.0, "derived": derived},
            {"period": "2025Q1", "value": 350.0}]},
        {"concept": "cash_and_equivalents", "label": "Cash", "unit": "USD", "points": [{"period": "2024Q4", "value": 9.0}]}]}
    dataset["data_notes"] = data_notes(dataset)
    return SimpleNamespace(mode="quarterly", period_key=dataset["period_key"], dataset_json=dataset, narrative_md="",
                           citations_json=[])


def _held(text: str, gap_words: str) -> dict[str, list[str]]:
    """The surface problems of one printed line of fine print. A summary line is read clause by clause: a marked note's
    clause is its places and the reason words (that test holds them), and the gap's clause says how this file draws a
    gap, so it must draw (DRAWING) and nothing else."""
    if " · " not in text:
        return {text: problems} if (problems := _surface_problems(text)) else {}
    found = {}
    for clause in re.split(r" · (?!\d+ checked)", text.removeprefix("Data notes · ")):
        if re.match(r"[a-z]{1,2} ", clause):
            continue
        if clause.endswith(gap_words):
            assert DRAWING.search(gap_words) and _surface_problems(clause.removesuffix(gap_words)) == [], clause
        elif problems := _surface_problems(clause):
            found[clause] = problems
    return found


def test_every_line_of_the_fine_print_holds_the_reason_words_surface_rules():
    """Every line each file prints in its fine print, read from the files: the PDF's paragraphs from the sentence above
    its grid to its closing line, the supplements' lead among them, and the workbook's Overview lines from the
    calculated sentence to its closing line. A detail entry is its note's message, which test_analysis_data_notes.py
    holds, then its places and counts, which list with "; " as the page's do, so the entries are not read."""
    case = next(case for case in CASES if case["name"] == "record_only_and_mixed_marking")
    pdfs = [ExportService().generate_analysis_pdf_html(_analysis(case), COMPANY),
            ExportService().generate_analysis_pdf_html(_quarterly_q4(True), COMPANY)]
    lines = [html_lib.unescape(re.sub(r"<[^>]+>", "", paragraph)).strip() for html in pdfs
             for paragraph in re.findall(r'<p class="fine-print[^"]*">(.*?)</p>', html, re.S)]
    # Each PDF's lead, summary and closing, the annual's supplements' lead and the quarterly's legend.
    assert len(lines) == 8 and "Data notes for narrative sources" in lines, lines
    assert any(line.endswith(DERIVED_Q4_LEGEND) for line in lines), lines
    assert {line: found for line in lines if (found := _held(line, " shown as —"))} == {}
    overview = [str(row[0]) for row in load_workbook(io.BytesIO(build_analysis_workbook(deepcopy(
        {**case["dataset"], "data_notes": case["expected"]}))))["Overview"].iter_rows(values_only=True) if row[0]]
    printed = overview[overview.index(FCF_DEFINITION) + 1:overview.index(WORKBOOK_CLOSING) + 1]
    entries = [line for line in printed if re.match(r"(?:[a-z]{1,2}\. )?[A-Z][^·]*\. .*\d+ (?:growth )?figures?", line)]
    read = [line for line in printed if line not in entries]
    assert len(read) == 5 and calculated_sentence(case["dataset"]) in read and len(entries) == 5, (read, entries)
    assert {line: found for line in read if (found := _held(line, " left blank"))} == {}
    # Planted: the page's own closing line and sentence ending, and the line this replaced, fail here.
    assert _held("Select any figure to see its source filing, method and inputs.", "")
    assert _held("Select any value for its source and full precision.", "")
    assert _held("Calculated figures (including computed Q4) carry cell comments; calculation method is separate.", "")
    assert _held("Data notes · 2 not in our data, shown as a blank cell", " left blank")


def test_a_quarterly_grid_marks_its_derived_fourth_quarters_never_a_figure():
    """MetricsTable.tsx's Q4 header † and its legend (coherence §2.5: they mark a period, not a figure): a calculated
    Q4 flow figure puts the † on its column's header, which the legend explains; no figure carries one."""
    html = ExportService().generate_analysis_pdf_html(_quarterly_q4(True), COMPANY)
    assert '<th class="num">Q4 2024 †</th>' in html and '<th class="num">Q3 2024</th>' in html
    assert f"{QUARTER_LEGEND} {DERIVED_Q4_LEGEND}" in html
    assert html.count("†") == 2, "the header and its legend, never a figure"
    plain = ExportService().generate_analysis_pdf_html(_quarterly_q4(False), COMPANY)
    assert "†" not in plain and QUARTER_LEGEND in plain


# ---- The PDF's layout ---------------------------------------------------------------------------------------------
def _rows(count: int) -> SimpleNamespace:
    conflict = {"method": "reported", "validation": "needs_review", "reasons": ["source_conflict"]}
    passed = {"method": "reported", "validation": "passed", "reasons": []}
    dataset = {"mode": "annual", "period_key": "FY2022..FY2024", "periods": [{"key": key} for key in ("FY2022", "FY2023", "FY2024")],
               "series": [{"concept": f"metric_{index}", "label": f"Metric {index}", "unit": "USD", "points": [
                   {"period": period, "value": 1000.0 + index, "provenance": conflict if (index, period) == (0, "FY2023") else passed}
                   for period in ("FY2022", "FY2023", "FY2024")]} for index in range(count)]}
    dataset["data_notes"] = data_notes(dataset)
    return SimpleNamespace(mode="annual", period_key=dataset["period_key"], dataset_json=dataset, narrative_md="",
                           citations_json=[])


def _render_pdf(weasyprint, html: str):
    try:
        return weasyprint.HTML(string=html).render()
    except Exception as exc:  # missing system libs in odd envs: not what this test reads
        pytest.skip(f"WeasyPrint runtime unavailable: {exc}")


def _pages(document, last_row: str) -> dict[str, int]:
    """The page each block starts on: the sentence above the grid, the grid's first and last rows and the summary."""
    found: dict[str, int] = {}
    for number, page in enumerate(document.pages):
        for box in page._page_box.descendants():
            element = box.element
            if element is None:
                continue
            text, classes = "".join(element.itertext()), element.get("class") or ""
            if element.tag == "tr" and text.startswith("Metric 0"):
                found.setdefault("first row", number)
            if element.tag == "tr" and text.startswith(last_row):
                found.setdefault("last row", number)
            if element.tag == "p" and classes == "fine-print" and text.startswith(ANALYSIS_GRID_ROUNDING):
                found.setdefault("sentence", number)
            if "data-notes-summary" in classes:
                found.setdefault("summary", number)
    return found


def test_the_summary_line_stays_on_the_grids_last_page():
    weasyprint = pytest.importorskip("weasyprint")
    rule = ".data-notes-summary { break-before: avoid; } "
    for count in range(8, 60):
        html = ExportService().generate_analysis_pdf_html(_rows(count), COMPANY)
        # The metrics section alone: the layout under test, without laying out the rest of the report.
        html = re.sub(r'(<section class="metrics-landscape">.*?</section>).*(</body>)', r"\1\2", html, count=1, flags=re.S)
        # Without the rule as written here, the summary never parts from the grid (the rule spelt another way keeps
        # it there, and the loop fails), or the rule is gone, and the layout below fails at the boundary.
        without = _pages(_render_pdf(weasyprint, html.replace(rule, "")), f"Metric {count - 1}")
        if without["summary"] != without["last row"]:
            break
    else:
        pytest.fail("no row count from 8 to 59 puts the summary on the page after the grid without the rule")
    pages = _pages(_render_pdf(weasyprint, html), f"Metric {count - 1}")
    assert pages["summary"] == pages["last row"], (count, pages)
    assert pages["sentence"] == pages["first row"], (count, pages)
