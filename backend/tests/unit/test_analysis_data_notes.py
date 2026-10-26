"""Shared presentation contract: exact financial concerns, no new verification claims."""
import hashlib
import json
import re
import uuid
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

import app.services.trend_analysis.data_notes as data_notes_module
from app.services.trend_analysis.data_notes import (
    _FALLBACK_MESSAGE,
    DATA_NOTES_VERSION,
    REASONS,
    RECORD_ONLY_REASONS,
    SUMMARIES,
    SUMMARY_FALLBACK,
    citation_data_notes,
    data_notes,
    marks_figure,
    note_for_quality,
    note_summary,
    quality_key,
    resolve_data_notes,
)
from app.services.trend_analysis.dataset import build_dataset, dataset_fingerprint

GOLDEN = json.loads((Path(__file__).parents[1] / "fixtures" / "analysis_data_notes.json").read_text())
CASES = GOLDEN["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_presentation_golden_preserves_inputs(case):
    before = deepcopy(case["dataset"])
    assert data_notes(case["dataset"]) == case["expected"]
    assert resolve_data_notes(case["dataset"]) == case["expected"]
    assert case["dataset"] == before


@pytest.mark.parametrize("case", [case for case in CASES if "citations" in case], ids=lambda case: case["name"])
def test_citation_supplements_preserve_report_letters_populations_and_inputs(case):
    report = deepcopy(case["expected"])
    citations = deepcopy(case["citations"])
    combined = citation_data_notes(citations, report)
    assert combined == case["expected_citation_notes"]
    assert combined["totals"] == report["totals"]
    assert report == case["expected"]
    assert citations == case["citations"]
    assert citation_data_notes(citations, combined) == combined
    for citation in citations:
        note = note_for_quality(citation, combined)
        assert note is None if quality_key(citation) is None else note["key"] == quality_key(citation)


def test_canonical_keys_preserve_unknown_codes_and_utf16_order():
    note = CASES[2]["expected"]["notes"][0]
    assert note["reasons"] == ['quote"\\\n', "\x7f", "é", "\ud800", "😀", "\ue000"]
    assert note["key"].isascii()
    assert "\\u007f" in note["key"] and "\\ud83d\\ude00" in note["key"]
    # All six unknown codes survive, even though each maps to the same public sentence.
    assert note["message"].count("Check the original filing.") == 6
    assert quality_key(CASES[2]["dataset"]["series"][0]["points"][0]) == note["key"]


def test_every_known_reason_has_a_pinned_message_and_supplements_continue_after_z():
    case = CASES[3]
    assert {note["reasons"][0] for note in case["expected"]["notes"]} == set(REASONS)
    result = citation_data_notes(case["citations"], data_notes(case["dataset"]))
    # 36 reasons: the 35 that mark take a..ai, the record-only legacy_calculation aj, and the supplements follow.
    assert [note["letter"] for note in result["notes"][-4:]] == ["aj", "ak", "al", "am"]
    assert result["notes"][-4]["reasons"] == ["legacy_calculation"]
    assert all(not note["values"] and not note["comparisons"] for note in result["notes"][-3:])


def test_the_marking_rule_and_summary_words_match_the_shared_fixture():
    """The fixture pins the frontend's copies too (data-notes.spec.ts, dataNoteMarking.spec.tsx): one record-only
    list, one rule and one set of summary words on both sides."""
    assert GOLDEN["record_only_reasons"] == sorted(RECORD_ONLY_REASONS)
    assert GOLDEN["summaries"]["clauses"] == SUMMARIES
    assert GOLDEN["summaries"]["fallback"] == SUMMARY_FALLBACK
    for example in GOLDEN["summaries"]["joined"]:
        assert note_summary(example["reasons"]) == example["summary"]
    # A summary clause is for a reason that marks, and every clause has a message.
    assert not set(SUMMARIES) & RECORD_ONLY_REASONS and set(SUMMARIES) <= set(REASONS)
    for case in CASES:
        notes = case.get("expected_citation_notes", case["expected"])["notes"]
        assert [note["letter"] for note in notes if marks_figure(note)] == case["marked_letters"]


# A page action: a gesture verb, base or -ing, aimed at something ("Select it", "Clicking one", "Hover over it", "Scroll
# down"). No export or PNG can honour one. A verb with another object passes, since a filing uses these words otherwise:
# "the earnings press release", "selected financial data", "the company chose", "a drag on margins".
PAGE_ACTIONS = re.compile(
    r"\b(?:select|click|tap|hover|press|choose|scroll|swipe|toggle)(?:ing)?\s+"
    r"(?:it|them|one|any|a|an|the|this|that|these|those|here|on|over|to|through|down|up)\b",
    re.IGNORECASE,
)
# How a missing figure is drawn differs by surface: a dash in the table, the PDF's tables and the page's and PNG's bar
# charts; a break in a line chart; an empty cell and an empty chart slot in the workbook; "Unavailable" in the PDF's
# Sources & methods. So words never say it: not the dash or the em dash, and not "shown as", "drawn as", "printed as",
# "left" or "shown" with a glyph or a blank. "Never shown as zero" and "shown as stored" say what the value is, and pass;
# so do "the filing left the table empty" and a range's en dash.
DRAWING = re.compile(
    r"\bdash(?:es)?\b|—"
    r"|\b(?:shown|drawn|printed|displayed|rendered|left)\s+(?:as\s+)?(?:an?\s+)?(?:hyphen|blank|empty|gap|n/a|space)\b"
    r"|\b(?:shown|drawn|printed|displayed|rendered)\s+as\s+[–-]",
    re.IGNORECASE,
)
# A note's message is read for one figure (the dialog, a workbook comment) and once for all of a note's figures (the
# detail, the PDF's and the workbook's lists, the chart footnotes), so it names no one figure or set: no "this", "that",
# "these", "those" or "the" before figure, value, calculation or number, saved, stored, reported or calculated or not.
# "This year", a relative "that" and a distributive "each figure" pass.
DEICTIC = re.compile(
    r"\b(?:this|that|these|those|the)\s+(?:(?:saved|stored|reported|calculated)\s+)?"
    r"(?:figure|value|calculation|number)s?\b",
    re.IGNORECASE,
)


def _surface_problems(words: str, *, clause: bool = False) -> list[str]:
    problems = [label for label, pattern in (
        ("asks for a page action the PDF, workbook and PNG cannot offer", PAGE_ACTIONS),
        ("says how a figure is drawn, which differs by surface", DRAWING),
        ("names one figure, though a note can group several", DEICTIC),
    ) if pattern.search(words)]
    # The fine print lists a note's places, and joins its clauses, with "; ", so a clause's own would split them.
    if clause and ";" in words:
        problems.append("carries a semicolon, which the fine print reads as its own separator")
    return problems


@pytest.mark.parametrize("words, clause", [
    ("Select it to compare with the filing.", False), ("Selecting it opens the filing.", False),
    ("Clicking it opens the filing.", False), ("Press it to compare.", False), ("Choose one to see both filings.", False),
    ("Tap it for the source.", False), ("Hover over it for its inputs.", False), ("Click on the figure.", False),
    ("Scroll down to the table.", False),
    ("Shown as a dash.", False), ("Shown as —, never as zero.", False),
    ("Not in our data; shown as a blank cell, never as zero.", False), ("Not in our data; left empty, never zero.", False),
    ("Drawn as a gap in the line.", False), ("Shown as a hyphen.", False), ("Left blank, never zero.", False),
    ("Shown empty.", False), ("Shown as n/a.", False), ("Shown as –.", False),
    ("Filings report different values for this figure.", False), ("Different values for that figure.", False),
    ("Those figures differ from the filing.", False), ("The figure’s period ends on a different date.", False),
    ("The saved figure needs a source check.", False), ("Could not confirm the value.", False),
    ("An input to the saved calculation moved.", False), ("This number was restated.", False),
    ("the filings report different values; we show the most recent", True),
])
def test_the_surface_words_check_fails_what_it_names(words, clause):
    assert _surface_problems(words, clause=clause)


@pytest.mark.parametrize("words, clause", [
    ("The filing left the table empty.", False), ("The company reported a blank value.", False),
    ("Covers FY2016–FY2025.", False), ("The opening balance differs from the previous closing balance.", False),
    ("Restated in the following period.", False), ("The expanded share count differs.", False),
    ("Taken from the earnings press release, not the filing.", False),
    ("Taken from the filing’s selected financial data.", False),
    ("The company chose a 53-week fiscal year.", False), ("Currency moves were a drag on margins.", False),
    ("The company changed its fiscal year end this year.", False),
    ("A calculation that could not be reproduced.", False), ("Each figure’s period ends on a different date.", False),
    ("A reported quarterly earnings-per-share figure is unavailable.", False),
    ("We show the most recent filing’s value.", False), ("Not in our data; never shown as zero.", False),
    ("Calculated before 10 October 2026; shown as stored, with its inputs not linked.", False),
    ("the filings report different values (the most recent shown)", True),
])
def test_the_surface_words_check_passes_ordinary_words(words, clause):
    assert _surface_problems(words, clause=clause) == []


def test_reason_words_hold_on_every_surface_that_prints_them():
    """A note's message prints in the page's data notes and evidence dialog, the PDF, the workbook's comments and
    Overview and the chart PNG's footnotes, for one figure and for a note's several, and provenance.ts holds the same
    words (the fixture above). So no sentence asks for what only the page can do ("Select it to compare"), says how a
    figure is drawn, or names one figure ("the figure's period"). The fine print's summary clauses are held alike, since
    WP3 prints them in the exports too, and carry no semicolon of their own."""
    sentences = [(reason, words, False) for reason, words in {**REASONS, "(fallback)": _FALLBACK_MESSAGE}.items()]
    sentences += [(f"(summary) {reason}", clause, True)
                  for reason, clause in {**SUMMARIES, "(fallback)": SUMMARY_FALLBACK}.items()]
    problems = {reason: found for reason, words, clause in sentences if (found := _surface_problems(words, clause=clause))}
    assert problems == {}, f"reason words that do not hold on every surface: {problems}"


def _probe(validation, *reasons):
    return {"version": 1, "method": "reported", "validation": validation, "reasons": list(reasons), "formula": None,
            "inputs": []}


# Every kind of note in an order the letters do not keep: a record-only note, one with no check recorded, a gap, notes
# that question the number on a value and on a growth figure, a mixed note and a code with no words of its own; then
# two citation-only concerns, the unmarked one first.
NOTES_PROBE = {
    "mode": "annual", "period_key": "FY2023..FY2024", "periods": [{"key": "FY2023"}, {"key": "FY2024"}],
    "series": [
        {"concept": "operating_margin", "label": "Operating margin", "percent": True, "cagr": None, "window_pp": None,
         "points": [{"period": "FY2023", "value": 30.0, "provenance": _probe("needs_review", "legacy_calculation")},
                    {"period": "FY2024", "value": 31.0}]},
        {"concept": "revenue", "label": "Revenue", "percent": False, "cagr": None, "window_pp": None,
         "points": [{"period": "FY2023", "value": None},
                    {"period": "FY2024", "value": 120.0, "provenance": _probe("needs_review", "source_conflict"),
                     "yoy": 0.2, "yoy_provenance": _probe("needs_review", "period_mismatch")}]},
        {"concept": "free_cash_flow", "label": "Free cash flow", "percent": False, "cagr": None, "window_pp": None,
         "points": [{"period": "FY2023", "value": 10.0,
                     "provenance": _probe("needs_review", "legacy_calculation", "source_check_needed")},
                    {"period": "FY2024", "value": 12.0, "provenance": _probe("needs_review", "probe_code_without_words")}]},
    ],
}
NOTES_PROBE_CITATIONS = [
    {"value": 1.0, "provenance": _probe("unavailable", "missing_provenance")},
    {"value": 1.0, "provenance": _probe("needs_review", "unit_mismatch")},
]
# Each data notes version's words, record-only list and letter order, as _notes_digest gives them. A saved analysis keeps
# the notes it was built with, and the cache and the PDF admit it by version alone (presentation_is_current), so the
# page would refuse a saved row whose words or letters changed under the same version, and only a metered refresh would
# get past it. A change to any of them takes a new version: raise DATA_NOTES_VERSION and add its digest here, and a
# saved analysis of the old version regenerates once, unmetered. Never edit a released version's digest; a version not
# yet on main has saved nothing, so its digest is replaced instead. Version 1 predates this gate.
NOTES_DIGESTS = {
    2: "c5dde3d9257c9c6e14312aaa22aba8ab5764a14849cb1b92eea8a4fe82984fff",
}


def _notes_digest() -> str:
    """The words, the record-only list and the letters the probe gets, never the version number the digest decides:
    the digest a failure prints for the next version is the one that version computes."""
    def unversioned(envelope: dict) -> dict:
        return {key: value for key, value in envelope.items() if key != "version"}

    report = data_notes(NOTES_PROBE)
    payload = {"reasons": REASONS, "fallback": _FALLBACK_MESSAGE, "record_only": sorted(RECORD_ONLY_REASONS),
               "report": unversioned(report),
               "with_citations": unversioned(citation_data_notes(NOTES_PROBE_CITATIONS, report))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def test_a_change_to_the_notes_words_or_letters_takes_a_new_version(monkeypatch):
    """Rule 12 for DATA_NOTES_VERSION: the words and the letters a saved analysis keeps are pinned per version."""
    letters = [(note["letter"], note["reasons"]) for note in citation_data_notes(
        NOTES_PROBE_CITATIONS, data_notes(NOTES_PROBE))["notes"]]
    # The probe meets the rule it pins: the marked notes first, in report order, then review, unknown and gap notes.
    assert letters == [
        ("a", ["source_conflict"]), ("b", ["legacy_calculation", "source_check_needed"]),
        ("c", ["probe_code_without_words"]), ("d", ["period_mismatch"]), ("e", ["legacy_calculation"]),
        ("f", ["legacy_unknown"]), ("g", ["not_in_dataset"]), ("h", ["unit_mismatch"]), ("i", ["missing_provenance"]),
    ]
    assert max(NOTES_DIGESTS) == DATA_NOTES_VERSION, "a new version adds its digest beside the released ones"
    assert len(set(NOTES_DIGESTS.values())) == len(NOTES_DIGESTS), "a new version changes the words or letters"
    digest = _notes_digest()
    # Following the message below converges: the raised version computes the digest it prints.
    monkeypatch.setattr(data_notes_module, "DATA_NOTES_VERSION", DATA_NOTES_VERSION + 1)
    assert _notes_digest() == digest, "the digest must not depend on the version number it decides"
    monkeypatch.undo()
    assert digest == NOTES_DIGESTS[DATA_NOTES_VERSION], (
        f"the data notes' words, record-only list or letter order changed under version {DATA_NOTES_VERSION}, so a "
        f"saved analysis would keep the old ones and the page would refuse it: raise DATA_NOTES_VERSION to "
        f"{DATA_NOTES_VERSION + 1} and add NOTES_DIGESTS[{DATA_NOTES_VERSION + 1}] = {digest!r} (while version "
        f"{DATA_NOTES_VERSION} is not yet on main, replace its digest instead)"
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_marked_notes_take_the_first_letters(case):
    """Read from each case's marked_letters, not the producer: within the report, and within its supplements,
    every marked note is lettered before every unmarked one."""
    def number(letter):
        return sum((ord(char) - 96) * 26 ** power for power, char in enumerate(reversed(letter)))

    report = case["expected"]["notes"]
    combined = case.get("expected_citation_notes", case["expected"])["notes"]
    for notes in (report, combined[len(report):]):
        marks = [note["letter"] in case["marked_letters"] for note in sorted(notes, key=lambda note: number(note["letter"]))]
        assert marks == sorted(marks, reverse=True)


def test_saved_supported_notes_are_authoritative_and_detached():
    dataset = deepcopy(CASES[0]["dataset"])
    saved = deepcopy(CASES[0]["expected"])
    saved["notes"][0]["message"] = "Server-owned wording for this notes version."
    dataset["data_notes"] = saved
    resolved = resolve_data_notes(dataset)
    assert resolved == saved
    resolved["notes"][0]["message"] = "Local edit"
    resolved["totals"]["total"] = -1
    assert saved["notes"][0]["message"] == "Server-owned wording for this notes version."
    assert saved["totals"]["total"] == 12


@pytest.mark.parametrize("present", [
    None, {}, {"version": True}, {"version": 2}, {"version": 2, "notes": None, "totals": {}},
    # A well-formed envelope of another version: version 1's words and letters are not this server's.
    {"version": 1, "notes": [], "totals": {}}, {"version": 3, "notes": [], "totals": {}},
])
def test_present_unusable_notes_never_silently_fall_back(present):
    dataset = {**CASES[0]["dataset"], "data_notes": present}
    with pytest.raises(ValueError, match="Unsupported or malformed"):
        resolve_data_notes(dataset)


def test_duplicate_legacy_slots_are_counted_once_and_last_point_wins():
    dataset = deepcopy(CASES[4]["dataset"])
    dataset["periods"] *= 2
    dataset["series"] += deepcopy(dataset["series"])
    first = dataset["series"][0]
    first["points"].insert(0, {"period": "2024Q1", "value": None})
    assert data_notes(dataset) == CASES[4]["expected"]


def test_display_metadata_does_not_change_snapshot_but_financial_quality_does():
    dataset = deepcopy(CASES[0]["dataset"])
    original = dataset_fingerprint(dataset)
    dataset["data_notes"] = data_notes(dataset)
    dataset["narrative_presentation"] = {"format_version": "analysis-narrative-v1", "evidence": []}
    dataset["snapshot_id"] = original
    dataset["data_as_of"] = "2026-10-11T00:00:00Z"
    assert dataset_fingerprint(dataset) == original
    dataset["data_notes"]["notes"][0]["message"] = "Updated display copy."
    dataset["narrative_presentation"]["evidence"].append({"observation_id": "signal-1"})
    assert dataset_fingerprint(dataset) == original
    dataset["series"][0]["points"][0]["provenance"]["reasons"] = ["source_conflict"]
    assert dataset_fingerprint(dataset) != original


@pytest.mark.requires_db
def test_built_dataset_carries_notes_for_values_and_inherited_comparisons():
    from app.database import SessionLocal, engine
    from app.models import Base, Company, FinancialFact

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        company = Company(cik=uuid.uuid4().hex[:10], ticker="NOTES", name="Notes example")
        db.add(company)
        db.flush()
        for year in (2023, 2024):
            for concept, amount in (("revenue", 100), ("net_income", 10)):
                reviewed = year == 2024 and concept == "revenue"
                provenance = {
                    "version": 1, "method": "reported", "validation": "needs_review" if reviewed else "passed",
                    "reasons": ["source_conflict"] if reviewed else [], "formula": None, "inputs": [],
                }
                db.add(FinancialFact(
                    company_id=company.id, concept=concept, value=amount + year - 2023,
                    unit="USD", period_start=date(year, 1, 1), period_end=date(year, 12, 31),
                    fiscal_year=year, fiscal_period="FY", form="10-K", accession=f"NOTES-{year}",
                    source="companyfacts", raw_tag=f"us-gaap:{concept}", reconciled=not reviewed,
                    is_latest=True, provenance=provenance,
                ))
        db.flush()
        dataset = build_dataset(db, company, "annual", "FY2023", "FY2024")
        notes = dataset["data_notes"]
        assert notes["version"] == DATA_NOTES_VERSION == 2
        concern = next(note for note in notes["notes"] if note["reasons"] == ["source_conflict"])
        assert {ref["concept"] for ref in concern["values"]} == {"revenue"}
        assert {ref["basis"] for ref in concern["comparisons"]} == {"yoy", "cagr"}
        assert notes["totals"]["reviewValues"] == 1
        assert notes["totals"]["reviewComparisons"] == 2
        assert dataset["snapshot_id"] == dataset_fingerprint(dataset)
