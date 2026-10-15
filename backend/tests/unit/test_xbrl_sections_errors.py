"""Section extraction keeps its fallback but no longer hides why it fell back.

From about 2026-10-06 every 10-K/10-Q/20-F section read raised (SEC's 403 on the short filing-index
URL, see app/services/edgar/edgartools_compat.py), and nothing was logged: the 10-K reads swallowed
the error per label, and ``getattr(obj, "sections", None)`` swallowed the AttributeError raised
inside the property. These tests pin the parse results and the warning, offline.
"""
import logging
from types import SimpleNamespace

import pytest

from app.services.edgar import xbrl_sections

ACCESSION = "0000000001-26-000001"
LONG = "x" * 300


class _Section:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class _RaisingSections:
    @property
    def sections(self):
        raise AttributeError("'NoneType' object has no attribute 'download'")


class _RaisingItems:
    def __getitem__(self, label):
        raise AttributeError(f"{label}: 'NoneType' object has no attribute 'download'")


def _resolve_to(monkeypatch, obj):
    filing = SimpleNamespace(obj=lambda: obj)
    monkeypatch.setattr(xbrl_sections, "resolve_filing_by_accession", lambda cik, acc: (None, [filing]))


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_a_10k_whose_item_reads_raise_logs_the_error(monkeypatch, caplog):
    _resolve_to(monkeypatch, _RaisingItems())
    with caplog.at_level(logging.WARNING):
        assert xbrl_sections._extract_sections_sync("0000000001", ACCESSION, "10-K") is None
    [message] = _warnings(caplog)
    assert ACCESSION in message and "AttributeError" in message and "(10-K)" in message
    assert "Item 1A" in message and "Item 7" not in message  # the first error, not the last


@pytest.mark.parametrize("form", ["10-Q", "20-F"])
def test_a_sections_property_that_raises_is_logged_not_hidden(monkeypatch, caplog, form):
    _resolve_to(monkeypatch, _RaisingSections())
    with caplog.at_level(logging.WARNING):
        assert xbrl_sections._extract_sections_sync("0000000001", ACCESSION, form) is None
    [message] = _warnings(caplog)
    assert ACCESSION in message and "AttributeError" in message and f"({form})" in message


def test_a_10q_reads_its_part_keyed_sections(monkeypatch, caplog):
    sections = {
        "part_i_item_1": _Section(" fin " + LONG),
        "part_i_item_2": _Section("m" * 200),  # exactly the minimum, kept
        "part_ii_item_1a": _Section("risk " + LONG),
        "part_ii_item_2": _Section("unregistered sales " + LONG),  # Part II Item 2 is not MD&A
    }
    _resolve_to(monkeypatch, SimpleNamespace(sections=sections))
    with caplog.at_level(logging.WARNING):
        out = xbrl_sections._extract_sections_sync("0000000001", ACCESSION, "10-Q")
    assert out == {"financials": "fin " + LONG, "mda": "m" * 200, "risk": "risk " + LONG}
    assert _warnings(caplog) == []


def test_a_section_one_character_short_of_the_minimum_is_dropped(monkeypatch):
    _resolve_to(monkeypatch, SimpleNamespace(sections={"part_i_item_1": _Section("f" * 199 + "   ")}))
    assert xbrl_sections._extract_sections_sync("0000000001", ACCESSION, "10-Q") is None


@pytest.mark.parametrize(("present", "expected"), [
    ({"part_iii_item_18": "eighteen", "part_iii_item_17": "seventeen", "part_i_item_8": "eight"}, "eighteen"),
    ({"part_iii_item_18": "", "part_iii_item_17": "seventeen", "part_i_item_8": "eight"}, "seventeen"),
    ({"part_i_item_8": "eight"}, "eight"),
])
def test_a_20f_takes_the_first_financials_candidate_with_content(monkeypatch, present, expected):
    sections = {"part_i_item_3": _Section("risk " + LONG), "part_i_item_5": _Section("mda " + LONG)}
    sections.update({key: _Section(f"{text} {LONG}" if text else "") for key, text in present.items()})
    _resolve_to(monkeypatch, SimpleNamespace(sections=sections))
    assert xbrl_sections._extract_sections_sync("0000000001", ACCESSION, "20-F") == {
        "risk": "risk " + LONG, "mda": "mda " + LONG, "financials": f"{expected} {LONG}",
    }


def test_a_10k_parses_its_items_and_skips_a_missing_one_quietly(monkeypatch, caplog):
    class _TenK:
        def __getitem__(self, label):
            if label == "Item 8":
                raise KeyError(label)
            return f"  {label} {LONG}  "

    _resolve_to(monkeypatch, _TenK())
    with caplog.at_level(logging.WARNING):
        out = xbrl_sections._extract_sections_sync("0000000001", ACCESSION, "10-K")
    assert out == {"risk": f"Item 1A {LONG}", "mda": f"Item 7 {LONG}"}
    assert _warnings(caplog) == []


def test_an_empty_parse_without_an_error_stays_quiet(monkeypatch, caplog):
    _resolve_to(monkeypatch, SimpleNamespace(sections={}))
    with caplog.at_level(logging.WARNING):
        assert xbrl_sections._extract_sections_sync("0000000001", ACCESSION, "10-Q") is None
    assert _warnings(caplog) == []
