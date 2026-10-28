"""The excerpt cohort SQL names an excerpt's builder by the opening that builder writes (E28).

``ops/excerpts/source_cohort.sql`` reads a stored excerpt's first characters: the regex path's separator glued to
its first section (``extract_critical_sections``), its recovered windows alone, or one of the native assembler's
labels (``assemble_excerpt_from_sections``, ``_SECTION_LAYOUT``) on a row created since that assembler. This gate
holds the CASE's arms, in order, to those builders: it reads each arm's predicate and label out of the SQL,
classifies as the SQL does, and runs both real builders over the three real filings the parity test holds (a
10-Q, a 10-K and a 20-F). It also holds the SQL's marks to the log reader's and to tasks/todo.md's E28 values,
and its output to counts. Nothing runs the SQL in CI; its rehearsal on PostgreSQL is in its PR. Retire it with
the SQL file, whose header names it.
"""
from __future__ import annotations

import gzip
import importlib.util
import inspect
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.ai.extraction import _ExtractionMixin
from app.services.edgar import xbrl_sections
from app.services.edgar.compat import xbrl_service
from app.services.openai_service import openai_service

ROOT = Path(__file__).resolve().parents[3]
SQL = ROOT / "ops" / "excerpts" / "source_cohort.sql"
READER = ROOT / "ops" / "excerpts" / "provenance_count.py"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
FILINGS = [
    ("tax_rate_comparison/figs-20260630.html.gz", "10-Q", "0001628280-26-054342"),
    ("operating_pretax/meli-2025.html.gz", "10-K", "0001099590-26-000006"),
    ("operating_pretax/se-2025.html.gz", "20-F", "0001140361-26-015366"),
]
SEPARATOR = "\n\n" + "=" * 50
NATIVE_SINCE = datetime(2026, 6, 15, tzinfo=timezone.utc)  # 2714c4df, the native assembler
OLD = datetime(2026, 3, 1, tzinfo=timezone.utc)
NEW = datetime(2026, 10, 10, tzinfo=timezone.utc)


def _literal(text: str) -> str:
    return text.replace("''", "'")


def _case() -> str:
    text = SQL.read_text()
    return text[text.index("           CASE\n"):text.index("           END AS builder")]


def arms() -> list[str]:
    """The CASE's labels, in the order its arms are tried."""
    return [then or other for then, other in re.findall(r"THEN '(\w+)'|ELSE '(\w+)'", _case())]


def openings() -> dict[str, list[str]]:
    case = _case()
    recovered = re.findall(r"LIKE '((?:[^']|'')*)' \|\| E'\\n%'\n", case)
    native = re.findall(r"^\s+'((?:[^']|'')*)' \|\| E'\\n%',?$", case, flags=re.MULTILINE)
    return {"regex_recovered": [_literal(text) + "\n" for text in recovered],
            "native": [_literal(text) + "\n" for text in native]}


def classify(excerpt: str | None, created: datetime) -> str:
    """The SQL's CASE, arm by arm, from what the SQL holds."""
    found = openings()
    if excerpt is None or excerpt[:1] == "":
        return "none"
    if excerpt[:52] == SEPARATOR:
        return "regex_targeted"
    head = excerpt[:64]
    if any(head.startswith(opening) for opening in found["regex_recovered"]):
        return "regex_recovered"
    if any(head.startswith(opening) for opening in found["native"]):
        return "native" if created >= NATIVE_SINCE else "label_before_native"
    return "unclassified"


def test_the_case_tries_its_arms_in_this_order_with_these_predicates():
    case = _case()
    assert arms() == ["none", "regex_targeted", "regex_recovered", "native", "label_before_native", "unclassified"]
    assert "WHEN c.critical_excerpt IS NULL OR substr(c.critical_excerpt, 1, 1) = '' THEN 'none'" in case
    assert "WHEN substr(c.critical_excerpt, 1, 52) = E'\\n\\n' || repeat('=', 50) THEN 'regex_targeted'" in case
    assert case.count("substr(c.critical_excerpt, 1, 64) LIKE '") == 2
    assert "substr(c.critical_excerpt, 1, 64) LIKE ANY (ARRAY[" in case
    assert "THEN CASE WHEN c.created_at >= timestamptz '2026-06-15 00:00:00+00' THEN 'native'" in case
    assert len(SEPARATOR) == 52


def test_the_separator_and_the_window_headers_are_the_regex_paths_own():
    source = inspect.getsource(_ExtractionMixin.extract_critical_sections)
    assert '("\\n\\n" + "=" * 50 + "\\n\\n".join(critical_sections))' in source
    headers = re.findall(r'"([A-Z&\- ]+ CONTEXT \(recovered from filing\)):\\n"', source)
    assert sorted(openings()["regex_recovered"]) == sorted(header + ":\n" for header in headers)
    assert len(headers) == 2 and all(len(opening) < 64 for opening in openings()["regex_recovered"])


def test_the_native_openings_are_every_layout_label_and_nothing_else():
    labels = {f"{label}:\n" for layout in _ExtractionMixin._SECTION_LAYOUT.values() for _key, label, _cap in layout}
    native = openings()["native"]
    assert len(native) == len(set(native)) and set(native) == labels
    assert all(len(opening) < 64 for opening in native)


def test_a_label_on_a_row_older_than_the_native_assembler_is_unverified():
    # The regex path wrote these very labels first, with no separator, until cdea7751 (2026-01-25).
    opening = "ITEM 1A - RISK FACTORS:\nThe company faces risks."
    assert classify(opening, OLD) == "label_before_native"
    assert classify(opening, NEW) == "native"
    assert classify(None, NEW) == classify("", NEW) == "none"
    assert classify("UNITED STATES SECURITIES AND EXCHANGE COMMISSION\nWashington", NEW) == "unclassified"
    assert classify("ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA\n(no colon)", NEW) == "unclassified"
    assert classify("FINANCIAL STATEMENTS CONTEXT (recovered from filing):\nx", NEW) == "unclassified"


def test_the_marks_are_the_readers_and_e28s():
    spec = importlib.util.spec_from_file_location("ops_excerpt_provenance_count", READER)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    sql = re.findall(r"timestamptz '(\d{4}-\d{2}-\d{2} \d{2}:\d{2}):00\+00' AS (\w+)", SQL.read_text())
    assert sql == [("2026-10-04 09:29", "last_native_report"), ("2026-10-07 19:06", "first_regex_report"),
                   ("2026-10-16 04:10", "fix_deployed")]
    assert [mark for _name, mark in reader.MARKS[1:]] == [f"{day.replace(' ', 'T')}:00Z" for day, _ in sql]
    # The reader's size cap is the parse's own.
    assert reader.SIZE_CAP == xbrl_sections._MAX_SECTION_HTML_CHARS


def test_the_output_is_counts_by_group():
    text = SQL.read_text()
    final = text[text.rindex("SELECT COALESCE(form"):text.index("FROM bucketed")]
    columns = re.findall(r"AS (\w+)", final)
    assert columns == ["form", "created", "last_written", "excerpts", "accessions", "with_summary",
                       "latest_of_form", "with_summary_and_latest"]
    assert "builder," in final and "accession_number" not in final.replace("count(DISTINCT accession_number)", "")
    assert "READ ONLY" in text and "SET LOCAL statement_timeout = '120s';" in text


@pytest.mark.asyncio
@pytest.mark.parametrize(("fixture", "form", "accession"), FILINGS, ids=[filing[1] for filing in FILINGS])
async def test_each_real_builder_reads_as_itself(fixture, form, accession):
    html = gzip.decompress((FIXTURES / fixture).read_bytes()).decode("utf-8")

    sections = await xbrl_service.get_filing_sections(accession, form, html=html)
    native = openai_service.assemble_excerpt_from_sections(sections, form, filing_text=html)
    regex = openai_service.extract_critical_sections(html, form)

    assert native and classify(native, NEW) == "native"
    # The 10-K and the 10-Q have regex sections; the 20-F has none, so its windows open it.
    assert classify(regex, NEW) == ("regex_recovered" if form == "20-F" else "regex_targeted")
