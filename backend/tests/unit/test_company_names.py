"""The backend's company display name is the page's (CLAUDE.md rule 12).

``app/utils/company_names.py`` ports ``frontend/lib/formatCompanyName.ts`` so the analysis PDF and workbook
print "Regeneron Pharmaceuticals, Inc." where the page, the chart PNG and the browser tab do, never EDGAR's
capitals. Two copies of one rule drift unless something holds them together:

1. one case table, ``tests/fixtures/company_display_names.json``, which this test and
   ``frontend/tests/unit/formatCompanyName.spec.ts`` both run, so a case added for either copy runs on both;
2. the four word lists (OVERRIDES, KEEP_UPPER, LEGAL_SUFFIX, LOWER_MIDWORD), read from the TypeScript source
   and held equal to the Python module's, so a word added on one side fails here until the other has it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.utils import company_names
from app.utils.company_names import display_company_name

REPO = Path(__file__).resolve().parents[3]
TABLE = json.loads((REPO / "backend" / "tests" / "fixtures" / "company_display_names.json").read_text(encoding="utf-8"))
TS_SOURCE = (REPO / "frontend" / "lib" / "formatCompanyName.ts").read_text(encoding="utf-8")
CASES = [(group["rule"], served, shown) for group in TABLE["groups"] for served, shown in group["cases"]]


@pytest.mark.parametrize(("rule", "served", "shown"), CASES, ids=[f"{rule}: {served!r}" for rule, served, _ in CASES])
def test_the_shared_table_reads_as_the_page_reads_it(rule, served, shown):
    assert display_company_name(served) == shown


def test_the_table_reaches_every_part_of_the_rule():
    assert all(group["cases"] for group in TABLE["groups"]) and len(TABLE["groups"]) >= 12
    assert display_company_name(None) == "" and display_company_name("   ") == ""
    # The analysis exports' inspected issuer (docs/mpa-improvements export inspection).
    assert display_company_name("REGENERON PHARMACEUTICALS, INC.") == "Regeneron Pharmaceuticals, Inc."


def _ts_block(name: str, source: str) -> str:
    """The body of ``const NAME ... = new Set([...])`` or ``= {...}`` in TypeScript source, line comments
    removed (no list entry holds "//")."""
    match = re.search(rf"^const {name}\b[^=]*=\s*(?:new Set\(\[(.*?)\]\)|\{{(.*?)\n\}})", source, re.M | re.S)
    assert match, f"formatCompanyName.ts declares no {name} in a form this test reads"
    return re.sub(r"//[^\n]*", "", match[1] if match[1] is not None else match[2])


_STRING = r"'([^'\\]*)'|\"([^\"\\]*)\""


def _ts_set(name: str, source: str = TS_SOURCE) -> set[str]:
    return {single if single else double for single, double in re.findall(_STRING, _ts_block(name, source))}


def _ts_record(name: str, source: str = TS_SOURCE) -> dict[str, str]:
    entries = re.findall(rf"(?:([A-Za-z_$][\w$]*)|{_STRING})\s*:\s*(?:{_STRING})", _ts_block(name, source))
    return {bare or single or double: value_single or value_double
            for bare, single, double, value_single, value_double in entries}


def test_the_word_lists_are_the_typescript_modules():
    assert _ts_record("OVERRIDES") == company_names.OVERRIDES
    assert _ts_set("KEEP_UPPER") == company_names.KEEP_UPPER
    assert _ts_set("LEGAL_SUFFIX") == company_names.LEGAL_SUFFIX
    assert _ts_set("LOWER_MIDWORD") == company_names.LOWER_MIDWORD


def test_the_list_reader_reads_what_it_claims():
    """Planted forms: the reader takes bare and quoted keys and both quote styles, and skips a line comment."""
    planted = (
        "const OVERRIDES: Record<string, string> = {\n  ABC: 'Abc',\n  \"D'E\": \"D'e\", // a note: 'X'\n}\n"
        "const KEEP_UPPER = new Set([\n  // legal forms 'LP'\n  'LLC', \"N.V.\",\n])\n"
    )
    assert _ts_record("OVERRIDES", planted) == {"ABC": "Abc", "D'E": "D'e"}
    assert _ts_set("KEEP_UPPER", planted) == {"LLC", "N.V."}
    with pytest.raises(AssertionError, match="declares no LEGAL_SUFFIX"):
        _ts_set("LEGAL_SUFFIX", planted)
