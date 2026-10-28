"""The detection SQL names an excerpt's builder by the opening that builder writes (E28).

``ops/detection/excerpt_source_cohort.sql`` reads a stored excerpt's first characters: the regex path's
separator glued to its first section (``extract_critical_sections``), its recovered windows alone, or one of
the native assembler's labels (``assemble_excerpt_from_sections``, ``_SECTION_LAYOUT``). This gate reads those
openings out of the SQL, classifies as the SQL does, and runs both real builders over the three real filings
the parity test already holds (a 10-Q, a 10-K and a 20-F), so the openings and the builders change together.
Retire it with the SQL file, whose header names it.
"""
from __future__ import annotations

import gzip
import inspect
import re
from pathlib import Path

import pytest

from app.services.ai.extraction import _ExtractionMixin
from app.services.edgar.compat import xbrl_service
from app.services.openai_service import openai_service

SQL = Path(__file__).resolve().parents[3] / "ops" / "detection" / "excerpt_source_cohort.sql"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILINGS = [
    ("tax_rate_comparison/figs-20260630.html.gz", "10-Q", "0001628280-26-054342"),
    ("operating_pretax/meli-2025.html.gz", "10-K", "0001099590-26-000006"),
    ("operating_pretax/se-2025.html.gz", "20-F", "0001140361-26-015366"),
]
SEPARATOR = "\n\n" + "=" * 50
WINDOW = 64  # the SQL reads substr(critical_excerpt, 1, 64)


def _literal(text: str) -> str:
    return text.replace("''", "'")


def sql_openings() -> dict[str, list[str]]:
    """The openings the SQL's CASE reads, by builder, as Python strings."""
    case = SQL.read_text()
    recovered = re.findall(r"LIKE '((?:[^']|'')*)' \|\| E'\\n%'\n", case)
    native = re.findall(r"^\s+'((?:[^']|'')*)' \|\| E'\\n%',?$", case, flags=re.MULTILINE)
    return {
        "regex_recovered": [_literal(text) + "\n" for text in recovered],
        "native": [_literal(text) + "\n" for text in native],
    }


def classify(excerpt: str | None) -> str:
    """The SQL's CASE, read from its openings."""
    openings = sql_openings()
    head = (excerpt or "")[:WINDOW]
    if not excerpt:
        return "none"
    if excerpt[:len(SEPARATOR)] == SEPARATOR:
        return "regex_targeted"
    for builder in ("regex_recovered", "native"):
        if any(head.startswith(opening) for opening in openings[builder]):
            return builder
    return "unclassified"


def test_the_sql_reads_the_separator_the_regex_path_glues_to_its_first_section():
    text = SQL.read_text()
    assert text.count("substr(c.critical_excerpt, 1, 52) = E'\\n\\n' || repeat('=', 50)") == 1
    assert len(SEPARATOR) == 52
    source = inspect.getsource(_ExtractionMixin.extract_critical_sections)
    assert '("\\n\\n" + "=" * 50 + "\\n\\n".join(critical_sections))' in source


def test_the_native_openings_are_every_layout_label_and_nothing_else():
    labels = {f"{label}:\n" for layout in _ExtractionMixin._SECTION_LAYOUT.values() for _key, label, _cap in layout}
    native = sql_openings()["native"]
    assert len(native) == len(set(native)) and set(native) == labels
    assert all(len(opening) < WINDOW for opening in native)


def test_the_recovered_openings_are_the_regex_paths_window_headers():
    source = inspect.getsource(_ExtractionMixin.extract_critical_sections)
    recovered = sql_openings()["regex_recovered"]
    assert sorted(recovered) == sorted(
        header + ":\n" for header in re.findall(r'"([A-Z&\- ]+ CONTEXT \(recovered from filing\)):\\n"', source)
    )
    assert len(recovered) == 2 and all(len(opening) < WINDOW for opening in recovered)
    # The native assembler's own windows read differently, and never open an excerpt (a section always does).
    assert not any(classify(opening) == "regex_recovered" for opening in (
        "FINANCIAL STATEMENTS CONTEXT (recovered from filing):\n", "MD&A CONTEXT (recovered from filing):\n"))


def test_nothing_reads_as_a_builder_it_is_not():
    assert classify(None) == classify("") == "none"
    assert classify("UNITED STATES SECURITIES AND EXCHANGE COMMISSION\nWashington, D.C.") == "unclassified"
    assert classify("ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA\n(no colon)") == "unclassified"


@pytest.mark.asyncio
@pytest.mark.parametrize(("fixture", "form", "accession"), FILINGS, ids=[filing[1] for filing in FILINGS])
async def test_each_real_builder_reads_as_itself(fixture, form, accession):
    html = gzip.decompress((FIXTURES / fixture).read_bytes()).decode("utf-8")

    sections = await xbrl_service.get_filing_sections(accession, form, html=html)
    native = openai_service.assemble_excerpt_from_sections(sections, form, filing_text=html)
    regex = openai_service.extract_critical_sections(html, form)

    assert native and classify(native) == "native"
    # The 10-K and the 10-Q have regex sections; the 20-F has none, so its windows open it.
    assert classify(regex) == ("regex_recovered" if form == "20-F" else "regex_targeted")
