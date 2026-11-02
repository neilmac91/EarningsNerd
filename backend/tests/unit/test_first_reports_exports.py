"""The producer's later-filing evidence as the exports print it (MPA WP5a-B through WP5a-X; CLAUDE.md rule 12).

The producer (WP5a-B, trend_analysis/first_reports.py) sends later-filing evidence and the exports (WP5a-X) print it.
Each was held to the page on its own: the producer's datasets by the page's decoders
(frontend/tests/unit/later-filings-producer.spec.ts), the exports by test_export_later_filings.py's shared fixture. Here
they meet. backend/tests/fixtures/analysis_first_reports_produced.json holds what the producer builds
(test_first_reports_wire.py keeps it so): WP5b's REGN sync and three findings on it, an exact sign flip of FY2018 net
income, an FY2018 balance in thousands and FY2018 revenue in thousands on the net margin's input, each over two windows.
Every one runs through the real builders, and the PDF's HTML and the workbook print exactly what its evidence and
later_filing_places say:

1. The line, the closing line's sentence and the n/m sentence where later_filing_places puts them; no letter but the
   data notes' (a finding's source_conflict mark is a note's); and none of it once the two fields are stripped:
   test_export_later_filings.py's tests whose expectations come from a dataset and its places alone, run over these.
   The places name exactly the figures and the growths whose evidence Sources & methods gives (2), and REGN's over
   FY2017..FY2021 are the shared fixture's REGN case.
2. Every figure and input that carries first_reported, at any depth of a figure's, a YoY's, a CAGR's or a window
   change's calculation, gives its year's own annual report at its own place in Sources & methods: in the workbook a
   "First reported" row right under its own row, with that report's value, unit, accession, filed day and link; in
   the PDF inside its row's or its input's item, with the accession and link. Every growth that reads n/m across the
   change gives its cause and its growth as first reported (yoy_first_reported, as the page prints it) on its own row.
   The words are built here from the dataset's values and filings in the page's words (laterFilings.ts, which
   test_export_later_filings.py reads), a finding's from its two values, so a reworded file fails here too.
3. Each comment on Metrics and the sheets with charts is main's with the evidence after its data note: a figure's
   wherever the figure shows, and the top line's growth across the change. No other comment changes.
4. Not inert: with the builders' later-filing seams switched off as main had them (PRE_X), neither file prints any of
   it; switched on, both files differ.
5. Each n/m the workbook prints says why, as the files' n/m sentence does: the two years its inputs give have opposite
   signs, or its note gives the later filing's cause.
6. Reach: between them the datasets print every kind of evidence above (REACH), so a producer that stops sending a
   field or a finding fails here as well as in its own tests. None carries a growth whose own reports give none (a
   null yoy_first_reported); test_export_later_filings.py's own case does.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

import app.services.export_service as export_service
from app.services.analysis_export_metadata import (
    BASIS_CHANGE_CAUSE, exact_figure, growth_text, note_index, period_label,
)
from app.services.trend_analysis.data_notes import marks_figure, resolve_data_notes
from app.services.trend_analysis.formatting import NOT_MEANINGFUL
from app.services.trend_analysis.later_filings import later_filing_places
from tests.unit import test_export_later_filings as exports
from tests.unit.test_export_later_filings import (
    EXPORTED, NEW_WORDS, _figure_cells, _files, _methods, _pdf, _sources, _switched_off, _workbook,
)

PRODUCED = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "analysis_first_reports_produced.json")
                      .read_text())["datasets"]
NAMES = list(PRODUCED)
CASES = [{"name": name, "dataset": dataset, "expected": later_filing_places(dataset)}
         for name, dataset in PRODUCED.items()]
MEASURES = ("Value", "YOY", "QOQ", "CAGR", "Window change")
INPUTS = {"Value": "a calculated figure's input", "YOY": "a YoY's input", "CAGR": "a CAGR's input",
          "Window change": "a window change's input"}
FINDINGS = {"opposite_sign": "a sign finding", "scale": "a scale finding"}


def _point(series: dict, period: str) -> dict:
    return next((point for point in series["points"] if point["period"] == period), {})


def _window(dataset: dict, series: dict) -> list[dict]:
    """The series' points the run shows, in its periods' order."""
    return [point for period in dataset["periods"] if (point := _point(series, period["key"]))]


def _across_the_change(point: dict) -> bool:
    return point.get("yoy") == NOT_MEANINGFUL and "yoy_first_reported" in point


def _scale(own: float, shown: float) -> tuple[int, str]:
    """The factor of 1,000ⁿ (n to 3) that takes the own report's value exactly to the one shown, and its way."""
    own_d, shown_d = Decimal(repr(own)), Decimal(repr(shown))
    return next((1000 ** n, way) for n in (1, 2, 3)
                for way, (big, small) in (("larger", (shown_d, own_d)), ("smaller", (own_d, shown_d)))
                if big == small * 1000 ** n)


def _value_words(record: dict) -> list[str]:
    """What the files say of a figure or an input that carries first_reported, in the page's words
    (laterFilings.ts firstReportedSentence, then disagreementSentence), from the dataset's two values and two filings;
    nothing where it carries none or has no value, as the page's dialog reads it."""
    first, shown = record.get("first_reported"), record.get("value")
    if not first or shown is None:
        return []
    own = ", ".join(filter(None, [first.get("form"), first.get("filed_at") and f"filed {first['filed_at']}"]))
    later = f" (filed {first['later_filed_at']})" if first.get("later_filed_at") else ""
    words = [f"First reported as {exact_figure(first['value'], first['unit'])} in its own annual report"
             f"{f' ({own})' if own else ''}. A later filing{later} reports {exact_figure(shown, first['unit'])}, "
             "shown here."]
    if first.get("disagreement") == "opposite_sign":
        words.append("A later filing reports the opposite sign.")
    elif first.get("disagreement") == "scale":
        factor, way = _scale(first["value"], shown)
        words.append(f"A later filing reports a value {factor:,} times {way} than the year’s own annual report.")
    return words


def _growth_words(point: dict, series: dict) -> list[str]:
    """What the files say of a YoY that reads n/m across the change (SourceValue.tsx): the cause, then its growth as
    first reported as the page prints it (growth_text, held to the page by analysis_growth_text.json), none where the
    own reports give none."""
    growth = point["yoy_first_reported"]
    text = None if growth is None else growth_text(growth, bool(series.get("percent")))
    return [BASIS_CHANGE_CAUSE, *([f"As first reported: {text}"] if text else [])]


def _evidence(dataset: dict) -> list[tuple]:
    """Each place the files give evidence, read from the dataset in Sources & methods' order, as (metric, period,
    measure, entry, words, first): the entry is its measure's own row ("Value", "YOY") or an input under it
    ("Input 2.1"), and first the own report whose value it gives, None for a growth across the change."""
    found = []

    def given(series: dict, period: str, measure: str, entry: str, record: dict) -> None:
        if words := _value_words(record):
            found.append((series["label"], period, measure, entry, words, record["first_reported"]))

    def inputs(series: dict, period: str, measure: str, provenance: dict | None, prefix: str = "Input ") -> None:
        for index, operand in enumerate((provenance or {}).get("inputs") or [], start=1):
            given(series, period, measure, f"{prefix}{index}", operand)
            inputs(series, period, measure, operand.get("provenance"), f"{prefix}{index}.")

    for series in dataset["series"]:
        for point in _window(dataset, series):
            period = period_label(point["period"])
            given(series, period, "Value", "Value", point)
            inputs(series, period, "Value", point.get("provenance"))
            if _across_the_change(point):
                found.append((series["label"], period, "YOY", "YOY", _growth_words(point, series), None))
            inputs(series, period, "YOY", point.get("yoy_provenance"))
        for measure, basis, window in (("CAGR", "cagr", "cagr_window"),
                                       ("Window change", "window_pp", "window_pp_range")):
            inputs(series, period_label(series.get(window) or dataset["period_key"]), measure,
                   series.get(f"{basis}_provenance"))
    return found


def _workbook_evidence(book) -> list[tuple]:
    """Each place the workbook gives evidence, read from Sources & methods in its order: each row whose note speaks of
    a later filing, as (metric, period, measure, entry, note, the own report as the row gives it). A "First reported"
    row speaks for the row right above it, which must be its own; a growth's row speaks for itself, after any note."""
    found, measure, above = [], None, None
    for row in _sources(book):
        entry, note = str(row["Entry"]), str(row["Note"] or "")
        measure = entry if entry in MEASURES else measure
        if entry == "First reported" or entry.endswith(" first reported"):
            own = measure if entry == "First reported" else entry.removesuffix(" first reported")
            assert (above["Metric"], above["Period"], above["Entry"]) == (row["Metric"], row["Period"], own), (
                row, above)
            found.append((row["Metric"], row["Period"], measure, own, note, tuple(row[column] for column in (
                "Value (raw)", "Unit", "Accession", "Filed", "Source URL", "Method"))))
        elif "First reported as " in note or BASIS_CHANGE_CAUSE in note:
            found.append((row["Metric"], row["Period"], measure, entry, note.split(" · ")[-1], None))
        above = row
    return found


_PDF_EVIDENCE = re.compile(r'<ul class="operands"><li>((?:First reported as |Not meaningful: )[^<]*'
                           r'(?:<a href="[^"]*">Source filing 1</a>)?)</li></ul>')


def _pdf_evidence(html: str) -> list[tuple]:
    """Each place the PDF gives evidence, read from Sources & methods in its order, as (metric, period, measure,
    entry, its HTML): the series and the row it sits under, and the input whose item holds it, else the row itself.
    None of it prints anywhere else in the file."""
    methods, found = _methods(html), []
    for match in _PDF_EVIDENCE.finditer(methods):
        before = methods[:match.start()]
        holder = before[before.rindex("<li>"):]
        assert "</li>" not in holder, holder  # inside the item it speaks for
        metric = re.findall(r"<h3>([^<]*)</h3>", before)[-1]
        period, measure = re.findall(r"<li><strong>([^<]*)</strong>", before)[-1].split(" · ")
        entry = re.match(r"<li>(Input [\d.]+): ", holder)
        found.append((html_lib.unescape(metric), html_lib.unescape(period), measure, entry[1] if entry else measure,
                      match[1]))
    assert html.count("First reported as ") + html.count(BASIS_CHANGE_CAUSE) == len(found)
    return found


def _pdf_text(words: list[str], first: dict | None) -> str:
    """Evidence as the PDF prints it: the words, then the own report's accession and link where it gives them."""
    text = html_lib.escape(" ".join(words))
    if first and first.get("accession"):
        text += f" · Accession: {html_lib.escape(str(first['accession']))}"
    if first and str(first.get("source_url") or "").startswith("https://"):
        text += f' · <a href="{html_lib.escape(first["source_url"], quote=True)}">Source filing 1</a>'
    return text


def _top_line(dataset: dict) -> dict | None:
    """The series the workbook's bar panel charts: revenue, else net interest income."""
    by_concept = {series["concept"]: series for series in dataset["series"]}
    return by_concept.get("revenue") or by_concept.get("net_interest_income")


def _comment_evidence(book, dataset: dict) -> dict[tuple[str, str], list[str]]:
    """The evidence each comment gives, by sheet and cell: a figure's wherever the figure shows (Metrics and the
    sheets with charts, read through their headers), and the top line's YoY where it reads n/m across the change (its
    sheet's column C: Period, the figure, its YoY growth)."""
    words = {(sheet, cell.coordinate): _value_words(_point(series, period))
             for sheet, cell, series, period in _figure_cells(book, dataset)}
    if (top := _top_line(dataset)) is not None:
        sheet = next(sheet for sheet in book.worksheets[3:] if sheet.title.endswith(" & growth"))
        for row, period in enumerate(dataset["periods"], start=2):
            if _across_the_change(point := _point(top, period["key"])):
                words[(sheet.title, f"C{row}")] = _growth_words(point, top)
    return words


def _texts(book) -> list[str]:
    return [text for sheet in book.worksheets for row in sheet.iter_rows() for cell in row
            for text in (cell.value and str(cell.value), cell.comment and cell.comment.text) if text]


# ---- 1. The line, the sentences and the letters ---------------------------------------------------------------------
# test_export_later_filings.py's tests whose expectations come from a case's dataset and its places alone.
XS_TESTS = {
    "the-line": exports.test_both_files_print_the_line_with_the_shared_fixtures_places,
    "first-reported": exports.test_every_figure_and_input_with_evidence_gives_the_dialogs_sentence_in_both_files,
    "closing-and-n-m": exports.test_the_closing_and_n_m_sentences_print_where_the_line_and_the_n_m_do,
    "no-letter": exports.test_evidence_marks_nothing,
    "none-without-the-fields": exports.test_a_dataset_without_the_fields_prints_none_of_it,
}


@pytest.mark.parametrize("case", CASES, ids=NAMES)
@pytest.mark.parametrize("test", list(XS_TESTS.values()), ids=list(XS_TESTS))
def test_the_exports_dataset_tests_hold_on_each_produced_dataset(test, case):
    test(deepcopy(case))


def test_regns_places_are_the_shared_fixtures_at_its_crossing():
    """The backend twin gives the producer's REGN the values the page's shared fixture plants for REGN and its comparisons
    at the crossing alone (D3: FY2019 and FY2020, a run and a leading edge, keep their growth), as the page's
    laterFilingPlaces does in later-filings-producer.spec.ts."""
    shared = next(case for case in exports.CASES if case["name"] == "regn_own_reports_beside_later_comparatives")
    assert later_filing_places(PRODUCED["regn FY2017..FY2021"]) == {
        "values": shared["expected"]["values"],
        "comparisons": [place for place in shared["expected"]["comparisons"] if place["period"] == "FY2018"]}


# ---- 2. Sources & methods -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", NAMES)
def test_each_figure_input_and_growth_gives_its_evidence_at_its_own_place_in_both_files(name):
    dataset = PRODUCED[name]
    evidence = _evidence(dataset)
    assert _workbook_evidence(_workbook(dataset)) == [
        (metric, period, measure, entry, " ".join(words), None if first is None else (
            first["value"], first["unit"], first["accession"], first["filed_at"], first["source_url"], "reported"))
        for metric, period, measure, entry, words, first in evidence]
    assert _pdf_evidence(_pdf(dataset)) == [(metric, period, measure, entry, _pdf_text(words, first))
                                            for metric, period, measure, entry, words, first in evidence]
    # The line names exactly the figures, and the growths, whose evidence Sources & methods gives.
    places = later_filing_places(dataset)
    for kind, entry in (("values", "Value"), ("comparisons", "YOY")):
        assert [(ref["label"], period_label(ref["period"])) for ref in places[kind]] == [
            (metric, period) for metric, period, _, own, *_ in evidence if own == entry], kind


# ---- 3. Comments and 4. not inert -----------------------------------------------------------------------------------
@pytest.mark.parametrize("name", NAMES)
def test_comments_give_the_evidence_after_the_note_and_the_seams_hold_all_of_it(name, monkeypatch):
    dataset = PRODUCED[name]
    monkeypatch.setattr(export_service, "utcnow", lambda: EXPORTED)
    printed, book = _files(dataset), _workbook(dataset)
    _switched_off(monkeypatch)
    main, main_book = _files(dataset), _workbook(dataset)
    # The seams hold all of it: switched off, neither file prints any; switched on, both files differ.
    assert main[0] != printed[0] and main[1] != printed[1]
    texts = [html_lib.unescape(main[0]), *_texts(main_book)]
    assert [words for words in (*NEW_WORDS, "As first reported") if any(words in text for text in texts)] == []
    evidence = _comment_evidence(book, dataset)
    for sheet in (book["Metrics"], *book.worksheets[3:]):
        for row in sheet.iter_rows():
            for cell in row:
                before = main_book[sheet.title][cell.coordinate].comment
                lines = before.text.split("\n") if before else []
                note = 1 if lines and lines[0].startswith("Data note") else 0
                assert (cell.comment.text.split("\n") if cell.comment else []) == [
                    *lines[:note], *evidence.get((sheet.title, cell.coordinate), []), *lines[note:]], (sheet, cell)


# ---- 5. Every n/m says why ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", NAMES)
def test_every_n_m_the_workbook_prints_says_why(name):
    groups = []  # each measure's row of Sources & methods, with the values of the rows under it by entry
    for row in _sources(_workbook(PRODUCED[name])):
        if row["Entry"] in MEASURES:
            groups.append((row, {}))
        else:
            groups[-1][1][row["Entry"]] = row["Value (raw)"]
    for row, under in groups:
        if row["Value (raw)"] == NOT_MEANINGFUL:
            now, before = under["Input 1"], under["Input 2"]  # the two years it compares
            assert BASIS_CHANGE_CAUSE in str(row["Note"]) or (now != 0 and (now > 0) != (before > 0)), (row, under)


# ---- 6. Reach -------------------------------------------------------------------------------------------------------
REACH = {"a figure", *INPUTS.values(), "an input two levels down", "a growth as first reported",
         "a growth as first reported, n/m across a finding", "the top line's growth across the change",
         "a finding beside its data note's letter",
         *(f"{finding} on {holder}" for finding in FINDINGS.values() for holder in ("a figure", "an input"))}


def _reach(dataset: dict) -> set[str]:
    """The kinds of evidence a dataset's files give, read from the places held above, and whether a figure with a
    finding also carries its data note's letter (D2's source_conflict), so its comment gives the evidence after it."""
    top = (_top_line(dataset) or {}).get("label")
    reach = set()
    for metric, _, measure, entry, words, first in _evidence(dataset):
        if first is None:  # a growth across the change
            reach.add("a growth whose own reports give none" if len(words) == 1 else
                      "a growth as first reported, n/m across a finding" if words[-1].endswith(": n/m") else
                      "a growth as first reported")
            if metric == top:
                reach.add("the top line's growth across the change")
            continue
        reach.add("a figure" if entry == measure else INPUTS[measure])
        if "." in entry:
            reach.add("an input two levels down")
        if first.get("disagreement"):
            reach.add(f"{FINDINGS[first['disagreement']]} on {'a figure' if entry == measure else 'an input'}")
    indexed = note_index(resolve_data_notes(dataset))
    if any((point.get("first_reported") or {}).get("disagreement") and marks_figure(note)
           for series in dataset["series"] for point in _window(dataset, series)
           if (note := indexed.get((series["concept"], point["period"], "value")))):
        reach.add("a finding beside its data note's letter")
    return reach


def test_the_produced_datasets_reach_every_kind_of_evidence():
    # Each kind is held at its places above; a dataset the producer pins that reaches a new kind fails here until
    # REACH names it.
    assert set().union(*map(_reach, PRODUCED.values())) == REACH
