"""Shared presentation contract: exact financial concerns, no new verification claims."""
import json
import re
import uuid
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

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


def test_reason_words_hold_on_every_surface_that_prints_them():
    """A note's message prints in the page's data notes and evidence dialog, the PDF, the workbook's comments and
    Overview and the chart PNG's footnotes, and provenance.ts holds the same words (the fixture above). So no sentence
    asks for what only the page can do ("Select it to compare"), and none says how a figure is drawn: the page, the PDF
    and the charts print a gap as a dash, but the workbook leaves its cell empty. The fine print's summary clauses are
    held alike, since WP3 prints them in the exports too."""
    sentences = {**REASONS, "(fallback)": _FALLBACK_MESSAGE,
                 **{f"(summary) {reason}": clause for reason, clause in SUMMARIES.items()},
                 "(summary fallback)": SUMMARY_FALLBACK}
    asks = sorted(reason for reason, words in sentences.items()
                  if re.search(r"\b(select|click|tap|hover)\b", words, re.IGNORECASE))
    draws = sorted(reason for reason, words in sentences.items()
                   if re.search(r"\b(dash|blank|empty)\b|[\u2013\u2014]", words, re.IGNORECASE))
    assert asks == [], f"words that ask for a page action the PDF, workbook and PNG cannot offer: {asks}"
    assert draws == [], f"words that say how a figure is drawn, which differs by surface: {draws}"


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
