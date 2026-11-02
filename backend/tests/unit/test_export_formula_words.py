"""The exports print a formula in the page's words (CLAUDE.md rule 12; chief design on #1953, 6582228814).

The page's evidence dialog prints a recorded formula through figureDisplay.ts's formulaWords: FORMULAS' words where it
has them ("Operating income ÷ revenue × 100"), else the stored expression with each underscore a space. The exports
print a formula through one port, analysis_export_metadata.formula_text, whose FORMULA_WORDS holds the page's words:
the PDF's Sources & methods for a figure and for each of its inputs, at any depth, and the workbook's Formula column for
both and its comment on a calculated figure. This gate reads FORMULAS and the fallback from figureDisplay.ts and fails
where the port differs: a word, a key one side lacks, or the fallback. It then renders the PDF and the workbook with a
figure for each formula the page words and one it does not, and holds each formula they print to the page's words and
none to its stored expression.

The reader. This test does not evaluate TypeScript, so it reads one form of figureDisplay.ts and fails on any other
rather than skip it:
- FORMULAS is declared on one line, `const FORMULAS: Record<string, string> = {`, and closed by a line `}` (or `};`),
  and each line between is blank or one entry, `'key': 'words',`, whose strings are single-quoted and hold no quote and
  no backslash, so no escape is left to decode. A comment, a spread, a computed or double-quoted key, two entries on a
  line, an entry without its comma, a key given twice, another declaration and a literal never closed fail.
- Every other mention of FORMULAS in the file reads it, `FORMULAS[formula]`, and neither assigns to it nor deletes it:
  a write after the declaration fails (`FORMULAS[formula] ??= ...`, `Object.assign(FORMULAS, ...)`), and so does a
  comment that names it, since the reader does not lex comments.
- formulaWords is named once in the file, on the line `export const formulaWords = (formula: string) =>
  FORMULAS[formula] ?? formula.replaceAll('_', ' ')`, whose two strings are the fallback. Any other form fails,
  `replace` among them, which in JavaScript replaces the first match alone where str.replace replaces each.
test_the_reader_reads_one_form_and_fails_on_any_other scores the reader on each of those forms, on look-alikes it
must pass and on the gap below that it passes.

Out of reach (review-checked):
- where the page prints a formula: SourceValue.tsx's three calls of formulaWords;
- a place in a file the render does not reach: its figures are all values, so it prints neither the top line's growth
  comment nor a window figure's comment (both take their formula through point_notes, as a value's comment does);
- a write to FORMULAS through a destructuring target (`[FORMULAS[formula]] = ...`), which the reader takes for a read
  (planted in GAPS);
- a key FORMULAS inherits from Object.prototype (`toString`), which formulaWords reads as a function where
  formula_text falls back;
- a formula the producer writes that FORMULAS does not word, which the page and both files print as stored
  ("FY - (Q1 + Q2 + Q3)", a Q4 calculated from the year less its three quarters, facts/quarterly.py).
"""
from __future__ import annotations

import io
import re
from collections.abc import Iterable
from copy import deepcopy
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from openpyxl import load_workbook

from app.services.analysis_export_metadata import FORMULA_WORDS, formula_text
from app.services.excel_export_service import build_analysis_workbook
from app.services.export_service import ExportService
from tests.unit.test_excel_export import EXPORTED_AT

FIGURE_DISPLAY = Path(__file__).resolve().parents[3] / "frontend" / "features" / "analysis" / "lib" / "figureDisplay.ts"
DECLARATION = "const FORMULAS: Record<string, string> = {"
ENTRY = re.compile(r"\s*'([^'\\]+)': '([^'\\]+)',\s*")
CLOSING = re.compile(r"\s*};?\s*")
FALLBACK = re.compile(r"export const formulaWords = \(formula: string\) => FORMULAS\[formula\] \?\? "
                      r"formula\.replaceAll\('([^'\\]*)', '([^'\\]*)'\)\s*")
READ = "FORMULAS[formula]"
# What makes a mention a write: an assignment of any kind after it, or a delete before it.
ASSIGNED = re.compile(r"\s*(?:\?\?|\|\||&&|\*\*|<<|>>>|>>|[-+*/%&|^])?=(?!=)")
DELETED = re.compile(r"\bdelete\s*$")
# A formula the page has no words for, so each export prints the page's fallback: its underscores turn to spaces.
UNWORDED = "total_debt / total_equity"


def read_formulas(source: str) -> tuple[dict[str, str], tuple[str, str]]:
    """FORMULAS, key for key, and formulaWords' fallback (the two strings its replaceAll takes), read from the source of
    figureDisplay.ts in the one form the module docstring states; an AssertionError for any other."""
    lines = source.split("\n")
    declared = [index for index, line in enumerate(lines) if line == DECLARATION]
    assert len(declared) == 1, f"FORMULAS is declared as {DECLARATION!r} {len(declared)} times: re-read it and the port"
    words: dict[str, str] = {}
    for line in lines[declared[0] + 1:]:
        if CLOSING.fullmatch(line):
            break
        if line.strip():
            entry = ENTRY.fullmatch(line)
            assert entry, f"FORMULAS holds a line the gate cannot read: {line!r}"
            assert entry[1] not in words, f"FORMULAS gives {entry[1]!r} twice"
            words[entry[1]] = entry[2]
    else:
        raise AssertionError("FORMULAS is never closed by a line '}'")
    declaration = sum(len(line) + 1 for line in lines[:declared[0]]) + len("const ")
    for mention in re.finditer(r"\bFORMULAS\b", source):
        at = mention.start()
        read = (source.startswith(READ, at) and not ASSIGNED.match(source, at + len(READ))
                and not DELETED.search(source, 0, at))
        context = source[max(at - 20, 0):at + 40]
        assert at == declaration or read, f"a mention of FORMULAS the gate cannot read: {context!r}"
    definitions = [FALLBACK.fullmatch(line) for line in lines if "formulaWords" in line]
    assert len(re.findall(r"\bformulaWords\b", source)) == 1 and len(definitions) == 1 and definitions[0], (
        "formulaWords moved or changed its form: re-read its fallback and the port")
    return words, definitions[0].groups()


def page_formulas() -> tuple[dict[str, str], tuple[str, str]]:
    """The page's formula words and fallback, read from figureDisplay.ts."""
    return read_formulas(FIGURE_DISPLAY.read_text(encoding="utf-8"))


def formula_series(formulas: Iterable[str]) -> list[dict[str, Any]]:
    """A series for each formula, in order, labelled "Formula 1", "Formula 2" and on: its FY2024 figure is calculated by
    the formula from one input calculated by it too, so the formula prints where Sources & methods gives a figure's
    formula and where it gives an input's, in both files, and in the figure's comment in the workbook. A growth formula
    sits on a value too: every measure's line prints its formula through formula_text alike."""

    def calculated(formula: str, inputs: list[dict[str, Any]]) -> dict[str, Any]:
        return {"method": "calculated", "validation": "passed", "reasons": [], "formula": formula, "inputs": inputs}

    return [{"concept": f"formula_{index}", "label": f"Formula {index}", "unit": "USD", "percent": False,
             "points": [{"period": "FY2024", "value": float(index), "provenance": calculated(formula, [
                 {"concept": "input", "value": 1.0, "unit": "USD", "period_start": "2024-01-01",
                  "period_end": "2024-12-31", "provenance": calculated(formula, [])}])}]}
            for index, formula in enumerate(formulas, start=1)]


def test_the_port_holds_the_page_s_words_and_its_fallback():
    words, fallback = page_formulas()
    differ = {key: (FORMULA_WORDS.get(key), words.get(key)) for key in {*words, *FORMULA_WORDS}
              if FORMULA_WORDS.get(key) != words.get(key)}
    assert differ == {}, "FORMULA_WORDS (the exports', then the page's) differs: re-read figureDisplay.ts's FORMULAS"
    assert {key: formula_text(key) for key in words} == words
    # The fallback, read from the page: a formula with no words reads as stored, each underscore a space.
    assert formula_text(UNWORDED) == UNWORDED.replace(*fallback) != UNWORDED
    assert formula_text(None) == formula_text("") == ""


# A figure's line in Sources & methods with its formula after the last middot, then its one input's line, its formula
# last too: no link, accession, source tag or filed day follows either in the fixture.
PRINTED = re.compile(r"<h3>([^<]*)</h3><ul><li><strong>FY2024 · Value</strong>: [^<]* · ([^<·]*)"
                     r'<ul class="operands"><li>Input 1: [^<]* · ([^<·]*)</li></ul></li></ul>')


def test_the_pdf_and_the_workbook_print_each_formula_in_the_page_s_words():
    words, fallback = page_formulas()
    formulas = [*words, UNWORDED]
    expected = {f"Formula {index}": words.get(formula, formula.replace(*fallback))
                for index, formula in enumerate(formulas, start=1)}
    dataset = {"ticker": "TST", "company_name": "Test & Co", "mode": "annual", "period_key": "FY2024..FY2024",
               "periods": [{"key": "FY2024", "fiscal_year": 2024, "fiscal_period": "FY", "period_end": "2024-12-31"}],
               "series": formula_series(formulas)}
    analysis = SimpleNamespace(mode="annual", period_key=dataset["period_key"], narrative_md="", citations_json=[],
                               dataset_json=deepcopy(dataset))
    html = ExportService().generate_analysis_pdf_html(analysis, SimpleNamespace(name="Test & Co", ticker="TST"))
    book = load_workbook(io.BytesIO(build_analysis_workbook(deepcopy(dataset), exported_at=EXPORTED_AT)))

    # The PDF: each figure's formula and its input's.
    methods = html.split('<section class="methods">', 1)[1]
    printed = {label: (unescape(figure), unescape(operand)) for label, figure, operand in PRINTED.findall(methods)}
    assert printed == {label: (text, text) for label, text in expected.items()}

    # The workbook: Sources & methods' Formula column, for each figure's row and its input's, and the figure's comment
    # in Metrics, whose last line is its formula.
    sheet = book["Sources & methods"]
    header = [cell.value for cell in sheet[1]]
    rows = [dict(zip(header, (cell.value for cell in row))) for row in sheet.iter_rows(min_row=2)]
    assert {(row["Metric"], row["Entry"]): row["Formula"] for row in rows} == {
        (label, entry): text for label, text in expected.items() for entry in ("Value", "Input 1")}
    metrics = book["Metrics"]
    assert metrics.cell(1, 4).value == "FY2024"
    assert {metrics.cell(row, 1).value: metrics.cell(row, 4).comment.text.split("\n")[-1]
            for row in range(2, 2 + len(formulas))} == expected

    # And neither file prints a stored expression anywhere.
    texts = [html, *(text for sheet in book.worksheets for row in sheet.iter_rows() for cell in row
                     for text in (cell.value, cell.comment and cell.comment.text) if isinstance(text, str))]
    assert [formula for formula in formulas if any(formula in text for text in texts)] == []


# The reader's fixture: the form figureDisplay.ts takes, two entries long, then the forms the rule can take and the
# look-alikes the reader must pass.
FORM = """const FORMULAS: Record<string, string> = {
  'FY - YTD9': 'Full year − first nine months',
  '100 * net_income / revenue': 'Net income ÷ revenue × 100',
}

export const formulaWords = (formula: string) => FORMULAS[formula] ?? formula.replaceAll('_', ' ')

export function substitutedFormula(formula: string): string | null {
  if (!FORMULAS[formula]) return null
  return formula
}
"""
FORM_WORDS = {"FY - YTD9": "Full year − first nine months", "100 * net_income / revenue": "Net income ÷ revenue × 100"}
LAST_ENTRY = "  '100 * net_income / revenue': 'Net income ÷ revenue × 100',\n"
FALLBACK_LINE = "export const formulaWords = (formula: string) => FORMULAS[formula] ?? formula.replaceAll('_', ' ')"
GUARD = "  if (!FORMULAS[formula]) return null\n"
# Each form the reader must refuse, as an edit of FORM (old, new) and the words its refusal names.
REFUSED = {
    "a comment inside the literal": (LAST_ENTRY, LAST_ENTRY + "  // the growth keys\n", "holds a line"),
    "a double-quoted entry": (LAST_ENTRY, LAST_ENTRY + '  "YTD6 - Q1": "First six months",\n', "holds a line"),
    "a spread": (LAST_ENTRY, LAST_ENTRY + "  ...GROWTH,\n", "holds a line"),
    "a computed key": (LAST_ENTRY, LAST_ENTRY + "  [GROWTH_KEY]: 'Growth',\n", "holds a line"),
    "two entries on a line": (LAST_ENTRY, LAST_ENTRY.rstrip("\n") + " 'YTD6 - Q1': 'First six months',\n",
                              "holds a line"),
    "an escape in the words": (LAST_ENTRY, LAST_ENTRY + "  'YTD6 - Q1': 'First six months \\u2212 first quarter',\n",
                               "holds a line"),
    "an entry without its comma": (LAST_ENTRY, LAST_ENTRY.replace("100',", "100'"), "holds a line"),
    "a comment after an entry": (LAST_ENTRY, LAST_ENTRY.replace("100',", "100', // a margin"), "holds a line"),
    "a key given twice": (LAST_ENTRY, LAST_ENTRY + "  'FY - YTD9': 'Full year less nine months',\n", "twice"),
    "a closing that ends the statement otherwise": ("}\n\nexport", "} as const\n\nexport", "holds a line"),
    "a literal never closed": (FORM[FORM.index("}\n\nexport"):], "", "never closed"),
    "an exported declaration": ("const FORMULAS:", "export const FORMULAS:", "declared"),
    "an untyped declaration": ("const FORMULAS: Record<string, string> = {", "const FORMULAS = {", "declared"),
    "a second declaration in a block comment": (
        "const FORMULAS", "/*\nconst FORMULAS: Record<string, string> = {\n}\n*/\nconst FORMULAS", "declared"),
    "a comment that names it": (GUARD, "  // FORMULAS words only these\n" + GUARD, "a mention of"),
    "an assignment": (GUARD, GUARD + "  FORMULAS[formula] = formula\n", "a mention of"),
    "an assignment to another key": (GUARD, GUARD + "  FORMULAS['YTD6 - Q1'] = formula\n", "a mention of"),
    "a compound assignment": (GUARD, GUARD + "  FORMULAS[formula] ??= formula\n", "a mention of"),
    "an augmented assignment": (GUARD, GUARD + "  FORMULAS[formula] += ' (stored)'\n", "a mention of"),
    "a delete": (GUARD, GUARD + "  delete FORMULAS[formula]\n", "a mention of"),
    "an Object.assign": (GUARD, GUARD + "  Object.assign(FORMULAS, GROWTH)\n", "a mention of"),
    "an export of it": ("export function", "export { FORMULAS }\n\nexport function", "a mention of"),
    "a fallback that replaces the first underscore alone": (
        "formula.replaceAll('_', ' ')", "formula.replace('_', ' ')", "formulaWords moved"),
    "a fallback that keeps the stored expression": (
        "?? formula.replaceAll('_', ' ')", "?? formula", "formulaWords moved"),
    "a fallback by a regular expression": ("replaceAll('_', ' ')", "replaceAll(/_/g, ' ')", "formulaWords moved"),
    "a fallback with more after it": ("replaceAll('_', ' ')", "replaceAll('_', ' ').trim()", "formulaWords moved"),
    "a fallback switched off for another": (
        FALLBACK_LINE,
        f"// {FALLBACK_LINE}\nexport const formulaWords = (formula: string) => FORMULAS[formula] ?? formula",
        "formulaWords moved"),
    "a fallback in a function": (FALLBACK_LINE, "export function formulaWords(formula: string) {\n"
                                                "  return FORMULAS[formula] ?? formula.replaceAll('_', ' ')\n}",
                                 "formulaWords moved"),
}
# Each look-alike the reader must pass, as an edit of FORM, and what it reads.
PASSED = {
    "a blank line inside the literal": (LAST_ENTRY, "\n" + LAST_ENTRY, FORM_WORDS),
    "a closing with its semicolon": ("}\n\nexport", "};\n\nexport", FORM_WORDS),
    "another indent and trailing space": (LAST_ENTRY, LAST_ENTRY.replace("  '100", "    '100").replace(",\n", ",  \n"),
                                          FORM_WORDS),
    "operators, parentheses and the minus sign in a key and its words": (
        LAST_ENTRY,
        LAST_ENTRY + "  '(last / first) ^ (1 / years) - 1': '(Last ÷ first) to the power of (1 ÷ years) − 1',\n",
        {**FORM_WORDS, "(last / first) ^ (1 / years) - 1": "(Last ÷ first) to the power of (1 ÷ years) − 1"}),
    "a read that compares": (
        GUARD, GUARD + "  if (FORMULAS[formula] === undefined || FORMULAS[formula] == null) return null\n", FORM_WORDS),
    "another name that holds it": (GUARD, GUARD + "  const METRIC_FORMULAS = formula\n", FORM_WORDS),
}
# Each form the rule forbids that the reader passes, a gap the module docstring names, as an edit of FORM, and what the
# reader reads from it.
GAPS = {
    "a write through a destructuring target": (GUARD, GUARD + "  ;[FORMULAS[formula]] = [formula]\n", FORM_WORDS),
}


def test_the_reader_reads_one_form_and_fails_on_any_other():
    assert read_formulas(FORM) == (FORM_WORDS, ("_", " "))
    for name, (old, new, refusal) in REFUSED.items():
        planted = FORM.replace(old, new, 1)
        assert planted != FORM, name
        with pytest.raises(AssertionError, match=refusal):
            read_formulas(planted)
    for name, (old, new, words) in PASSED.items():
        planted = FORM.replace(old, new, 1)
        assert planted != FORM, name
        assert read_formulas(planted) == (words, ("_", " ")), name
    for name, (old, new, words) in GAPS.items():
        planted = FORM.replace(old, new, 1)
        assert planted != FORM, name
        assert read_formulas(planted) == (words, ("_", " ")), f"{name} is no longer a gap: refuse it and say so"
    # figureDisplay.ts itself takes the form.
    assert page_formulas()[1] == ("_", " ")
