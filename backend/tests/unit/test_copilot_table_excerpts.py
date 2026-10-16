"""Table-text citations on the sources copilot-eval actually prepares: what publishes, what may retry.

Every excerpt below is a citation shape the retained copilot-eval generations produced (the corpus in
``tasks/review-evidence/copilot-table-excerpt-retry-2026-10-16/``), checked against contiguous slices of
the real prepared sources in ``tests/fixtures/copilot_table_sources.json``. A whole row copied as the
filing shows it publishes. A lone figure, a short label, a partial or elided row, a row retyped with
different spacing and a twice-declared number never publish, but may buy the one private regeneration.
A quoted label, an undeclared literal and a source too short to verify anything stay terminal.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.copilot.envelope import _verify_citations
from app.services.copilot.exceptions import _RegenerableEvidenceMismatch, _UnpublishableAnswer
from app.services.provenance_service import normalize_for_match

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "copilot_table_sources.json"
SOURCES = {key: value["text"] for key, value in json.loads(FIXTURE.read_text())["sources"].items()}
FILING = SimpleNamespace(document_url="https://www.sec.gov/Archives/edgar/data/1577552/000095017025090161/baba-20250331.htm")
BABA_INCOME = "baba_fy2025_sections_income_statement"
BABA_SCHEDULE = "baba_fy2025_sections_consolidating_schedule"
BABA_REGEX = "baba_fy2025_regex_consolidating_schedule"
ASML = "asml_fy2025_regex_statement"
ASML_KPI = "asml_fy2025_regex_kpi_panel"
AAPL = "aapl_fy2025_sections_statement"
SECTION = "Item 18 — Consolidated Income Statements"


def cite(n, excerpt, section=SECTION):
    return {"n": n, "excerpt": excerpt, "section": section}


def verdict(source_key, citations, referenced=frozenset({"1"})):
    source = SOURCES.get(source_key, source_key)
    try:
        published = _verify_citations(citations, FILING, normalize_for_match(source), set(referenced))
    except _RegenerableEvidenceMismatch:
        return "regenerable"
    except _UnpublishableAnswer:
        return "terminal"
    assert all(row["verified"] is True for row in published.values())
    return "published"


CASES = {
    # Whole rows, copied as the source shows them (the shapes that verified 342 of 342 times).
    "income row, collapsed spacing": (BABA_INCOME, [cite(1, "Revenue 5, 24 868,687 941,168 996,347 137,300")], "published"),
    "income row, copied with its blank cells": (BABA_INCOME, [cite(1, SOURCES[BABA_INCOME].split("\n\n\n\n\n\n\n")[0])],
                                               "published"),
    "schedule row on sections": (BABA_SCHEDULE, [cite(1, "Revenue from third parties — 833,583 98,433 64,331 — 996,347 137,300")],
                                 "published"),
    "schedule row on regex": (BABA_REGEX, [cite(1, "Revenue from third parties — 833,583 98,433 64,331 — 996,347 137,300")],
                              "published"),
    "row label alone": (BABA_REGEX, [cite(1, "Revenue from third parties")], "published"),
    "ASML statement row": (ASML, [cite(1, "Total net sales 28,262.9 100.0 32,667.3 100.0 15.6", "Item 5")], "published"),
    "AAPL row with its glued label": (AAPL, [cite(1, "Total net sales416,161\xa0391,035\xa0383,285", "Item 8")], "published"),
    # Table-text failures: never published, now each buys the one private regeneration.
    "bare figure (2026-10-15 draws)": (BABA_INCOME, [cite(1, "996,347")], "regenerable"),
    "figure declared twice beside its row": (BABA_INCOME, [cite(1, "996,347"),
                                                          cite(1, "Revenue 5, 24 868,687 941,168 996,347 137,300")],
                                            "regenerable"),
    "partial row under the floor": (BABA_INCOME, [cite(1, "Revenue\n5, 24\n \n \n \n868,687")], "regenerable"),
    "header fragment": (BABA_REGEX, [cite(1, "Consolidated\nTotal")], "regenerable"),
    "elided row": (BABA_REGEX, [cite(1, "Revenue from third parties ... 996,347 ... 137,300")], "regenerable"),
    "ASML KPI cells": (ASML_KPI, [cite(1, "€32.7bn\nTotal net sales", "Highlights")], "regenerable"),
    "AAPL row retyped with a space": (AAPL, [cite(1, "Total net sales 416,161 391,035 383,285", "Item 8")], "regenerable"),
    # Still terminal: no candidate with these defects may buy another generation.
    "quoted section label": (BABA_INCOME, [cite(1, "996,347", 'Item 18 — "Consolidated Income Statements"')], "terminal"),
    "undeclared literal": (BABA_INCOME, [cite(1, "996,347")], "terminal"),
    "source too short to verify": ("Revenue 996,347", [cite(1, "996,347")], "terminal"),
}
REFERENCED = {"undeclared literal": frozenset({"1", "2"})}


@pytest.mark.parametrize("case", list(CASES))
def test_table_citation_publishes_retries_or_stays_terminal(case):
    source_key, citations, expected = CASES[case]
    assert verdict(source_key, citations, REFERENCED.get(case, frozenset({"1"}))) == expected


def test_fixture_slices_keep_their_provenance_and_are_unedited():
    """Each slice names the prepared source and offset it was cut from (the full sources are in the
    copilot-eval artifacts, not the repository) and the hash of its own text, which catches a later edit."""
    sources = json.loads(FIXTURE.read_text())["sources"]
    assert set(sources) == {BABA_INCOME, BABA_SCHEDULE, BABA_REGEX, ASML, ASML_KPI, AAPL}
    for value in sources.values():
        assert len(value["source_sha256"]) == 64 and value["offset"] >= 0 and value["text"]
        assert hashlib.sha256(value["text"].encode("utf-8")).hexdigest() == value["text_sha256"]
    assert {sources[k]["source_sha256"][:12] for k in (BABA_INCOME, BABA_SCHEDULE)} == {"be4499769327"}
    assert sources[BABA_REGEX]["source_sha256"][:12] == "9e4a6a8d7efb"
