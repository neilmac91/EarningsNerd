"""Versioned presentation notes; never alter financial values or source validation."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

# Version 2: the reasons' words below and the marked notes lettered first. The envelope's shape is version 1's, so the
# frontend reads both; a saved presentation of version 1 regenerates once (presentation_is_current). A change to the
# words, the record-only list or the letter order takes a new version: test_analysis_data_notes.py's NOTES_DIGESTS
# holds each version's.
DATA_NOTES_VERSION = 2
_MISSING = object()
_KINDS = {"review": 0, "unknown": 1, "unavailable": 2}
_BASES = ("qoq", "yoy", "cagr", "window_pp")
_FALLBACK_MESSAGE = "The source or calculation basis needs review. Check the original filing."
# Each reason's words. A note's message prints for one figure (the evidence dialog, a workbook cell's comment) and once
# for all of a note's figures (the page's detail, the PDF's and the workbook's lists, the chart footnotes), so a sentence
# names no one figure (no "the figure", "the saved calculation" or "this value"), asks for nothing only the page does
# ("select it") and says nothing of how a gap is drawn, which differs by surface: a dash in the table, the PDF's tables
# and the page's and PNG's bar charts, a break in a line chart, an empty cell and an empty chart slot in the workbook,
# "Unavailable" in the PDF's Sources & methods. Nor does a sentence carry a semicolon: a chart's footnote lists a note's
# places with "; " before its words. test_analysis_data_notes.py holds all four.
REASONS = {
    "not_in_dataset": "Not in our data. Never shown as zero.",
    "legacy_calculation": "Calculated before 10 October 2026, when we began keeping each calculation’s inputs. Shown as stored, with its inputs not linked.",
    "source_check_needed": "Not yet matched to the filing by our automated check.",
    "unsupported_eps_calculation": "Calculated quarterly earnings per share is not supported. Use a reported quarterly EPS figure.",
    "legacy_calculation_not_supported": "Could not be reproduced from compatible source inputs, so unavailable.",
    "repair_rolled_back": "Withdrawn during a data correction and unavailable.",
    "incompatible_vintages": "The inputs come from incompatible versions of the company’s filings.",
    "missing_compatible_operand": "No compatible earlier year-to-date figure is available to calculate from.",
    "negative_calculated_value": "Calculated as an invalid negative amount, so withheld.",
    "missing_inputs": "Source inputs needed for calculation are unavailable.",
    "missing_input": "A source input needed for calculation is unavailable.",
    "missing_source": "The original source could not be established.",
    "missing_provenance": "Detailed source information is unavailable.",
    "legacy_unverified": "Needs a source check before use.",
    "legacy_unreconciled": "Needs a source check before use.",
    "legacy_unknown": "Validation details are unavailable. No verification claim is made.",
    "legacy_provenance_unavailable": "Saved without detailed source information.",
    "incompatible_inputs": "The source inputs do not have a compatible reporting basis.",
    "mixed_vintage": "Calculated from figures in different filing versions.",
    "mixed_vintages": "Calculated from figures in different filing versions.",
    "unit_mismatch": "The source inputs use different units or currencies.",
    "period_mismatch": "Period ends on a different date from its filing’s reporting period.",
    "missing_adjacent_period": "The immediately preceding period is unavailable.",
    "eps_not_additive": "Quarterly earnings per share cannot be obtained by subtracting annual and year-to-date EPS.",
    "eps_requires_reported_quarter": "A reported quarterly earnings-per-share figure is unavailable.",
    "rounded_share_count": "Rounded weighted-average share counts do not establish an exact quarterly EPS figure.",
    "calculation_mismatch": "Not confirmed by our calculation from the filed inputs.",
    "missing_calculation_inputs": "Not checked: no compatible inputs in the same filing.",
    "zero_where_prior_nonzero": "Zero where the previous period was not zero.",
    "magnitude_vs_prior": "More than ten times the previous period’s value, or less than a tenth of it.",
    "eps_sign_vs_net_income": "Earnings per share and net income have opposite signs for the period.",
    "diluted_gt_basic": "Diluted earnings per share is higher than basic earnings per share for the period.",
    "legacy_period_label_mismatch": "Saved with the wrong fiscal period and replaced by a corrected figure.",
    "rolling_duration_not_fiscal_year": "Saved as a rolling twelve months, not the company’s fiscal year, so unavailable.",
    "calculation_parent_period_corrected": "Withdrawn and unavailable: an input was corrected or withdrawn.",
    "source_conflict": "The company’s filings report different values. We show the most recent filing’s value.",
}
# Reasons that describe a figure's record, not its value (D-061): their notes put no mark beside the figure. Closed: any
# other reason marks, so a new reason shows until it is classified here. lib/dataNotes.ts holds the same list, and the
# shared notes fixture's record_only_reasons pins both.
RECORD_ONLY_REASONS = frozenset({"legacy_calculation"})
# The fine print's words for a note that marks its figure ("Revenue FY2024: not yet matched to the filing"). The page
# prints them from provenance.ts REASON_SUMMARIES, which the fixture's summaries holds equal to these; the PDF and the
# workbook print them through note_summary, in their summary line (analysis_export_metadata.fine_print_summary). A clause
# has no semicolon of its own, as a sentence has none: the fine print lists a note's places, and joins its clauses,
# with "; ".
SUMMARIES = {
    "source_check_needed": "not yet matched to the filing",
    "source_conflict": "the filings report different values (the most recent shown)",
    "calculation_mismatch": "not confirmed by our calculation from the filed inputs",
    "missing_calculation_inputs": "no compatible inputs in the same filing, so not checked",
}
SUMMARY_FALLBACK = "questioned by an automated check"


def _issue(value: Mapping[str, Any]) -> dict | None:
    provenance = value.get("provenance")
    validation = provenance.get("validation") if provenance is not None else None
    reviewed = validation == "needs_review" if provenance is not None else value.get("reconciled") is False
    if value.get("value", _MISSING) is None:
        kind = "unavailable"
    elif reviewed:
        kind = "review"
    elif validation == "passed":
        return None
    else:
        kind = "unknown"
    fallback = {"unavailable": "not_in_dataset", "unknown": "legacy_unknown", "review": "source_check_needed"}
    supplied = provenance.get("reasons") or [] if provenance is not None else []
    # JavaScript's default string sort compares UTF-16 code units, not Unicode code points.
    reasons = sorted(set(supplied or [fallback[kind]]), key=lambda text: text.encode("utf-16-be", "surrogatepass"))
    return {"kind": kind, "reasons": reasons, "key": json.dumps([kind, reasons], ensure_ascii=True, separators=(",", ":"))}


def quality_key(value: Mapping[str, Any]) -> str | None:
    """Portable ASCII-JSON issue identity; absent validation never means passed."""
    issue = _issue(value)
    return issue["key"] if issue else None


def note_for_quality(value: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict | None:
    """Look up a value/citation's own concern; no inference from a matching financial cell."""
    key = quality_key(value)
    return next((note for note in envelope["notes"] if note["key"] == key), None) if key else None


def _letter(index: int) -> str:
    result = ""
    index += 1
    while index:
        index, digit = divmod(index - 1, 26)
        result = chr(97 + digit) + result
    return result


def _add(groups: dict, value: Mapping[str, Any]) -> dict | None:
    issue = _issue(value)
    if issue is None:
        return None
    return groups.setdefault(issue["key"], {
        **issue, "id": "", "letter": "",
        "message": " ".join(REASONS.get(reason, _FALLBACK_MESSAGE) for reason in issue["reasons"]),
        "values": [], "comparisons": [], "counts": dict.fromkeys(_BASES, 0),
    })


def marks_figure(note: Mapping[str, Any]) -> bool:
    """Whether a note puts a mark beside its figure: a review note with a reason that questions the number (D-061).
    It reads the note's reasons in place: test_data_note_reasons_have_words.py reads an assignment to a name `reasons`
    as a write, which would make every export that asks this question a reason emitter."""
    return note["kind"] == "review" and (
        not note["reasons"] or any(reason not in RECORD_ONLY_REASONS for reason in note["reasons"]))


def note_summary(reasons: Iterable[str]) -> str:
    """A marked note's fine-print words, as the page's noteSummary writes them: each questioning reason's clause,
    once, in reason order. The exports' summary line prints it; the fixture's summaries pins it to the page's."""
    clauses = [SUMMARIES.get(reason, SUMMARY_FALLBACK) for reason in reasons if reason not in RECORD_ONLY_REASONS]
    return "; ".join(dict.fromkeys(clauses or [SUMMARY_FALLBACK]))


def _finish(groups: dict) -> list[dict]:
    # Marked notes take the first letters, so a page's first visible letter is "a"; then review, unknown and
    # unavailable notes. Python's stable sort preserves first report appearance within each.
    notes = sorted(groups.values(), key=lambda note: (not marks_figure(note), _KINDS[note["kind"]]))
    for index, note in enumerate(notes):
        note["letter"] = _letter(index)
        note["id"] = f"analysis-data-note-{note['letter']}"
    return notes


def _value_notes(dataset: Mapping[str, Any], periods: list[str], groups: dict, totals: dict) -> None:
    seen = set()
    for series in dataset["series"]:
        points = {point["period"]: point for point in series["points"]}
        for period in periods:
            identity = (series["concept"], period)
            if identity in seen:
                continue
            seen.add(identity)
            point = points.get(period, {"value": None})
            note = _add(groups, point)
            totals["total"] += 1
            if point.get("value", _MISSING) is None:
                totals["unavailable"] += 1
            else:
                bucket = {"review": "reviewValues", "unknown": "unknown"}.get(note["kind"] if note else None, "passed")
                totals[bucket] += 1
                provenance = point.get("provenance")
                calculated = provenance.get("method") == "calculated" if provenance is not None else point.get("derived")
                totals["calculated"] += bool(calculated)
            if note:
                note["values"].append({"concept": series["concept"], "label": series["label"], "period": period})


def _comparison_quality(value: Mapping[str, Any], basis: str) -> dict:
    return {"value": value.get(basis), "provenance": value.get(f"{basis}_provenance"), "reconciled": value.get(f"{basis}_reconciled")}


def _comparison_notes(dataset: Mapping[str, Any], periods: list[str], groups: dict, totals: dict) -> None:
    seen = set()

    def add(series: dict, period: str, basis: str, value: dict) -> None:
        identity = (series["concept"], period, basis)
        if value["value"] is None or identity in seen:
            return
        seen.add(identity)
        note = _add(groups, value)
        if note is None:
            return
        note["comparisons"].append({"concept": series["concept"], "label": series["label"], "period": period, "basis": basis})
        note["counts"][basis] += 1
        totals["reviewComparisons"] += note["kind"] == "review"

    for series in dataset["series"]:
        points = {point["period"]: point for point in series["points"]}
        for period in periods:
            point = points.get(period)
            if point is None:
                continue
            if dataset["mode"] == "quarterly":
                add(series, period, "qoq", _comparison_quality(point, "qoq"))
            add(series, period, "yoy", _comparison_quality(point, "yoy"))
        if dataset["mode"] == "annual":
            for basis, range_key in (("cagr", "cagr_window"), ("window_pp", "window_pp_range")):
                period = series.get(range_key)
                add(series, dataset["period_key"] if period is None else period, basis, _comparison_quality(series, basis))


def data_notes(dataset: Mapping[str, Any]) -> dict:
    """Classify presentation concerns once, preserving every existing quality field."""
    groups: dict[str, dict] = {}
    totals = dict.fromkeys(("reviewValues", "reviewComparisons", "unavailable", "passed", "unknown", "calculated", "total"), 0)
    periods = list(dict.fromkeys(period["key"] for period in dataset["periods"]))
    _value_notes(dataset, periods, groups, totals)
    _comparison_notes(dataset, periods, groups, totals)
    return {"version": DATA_NOTES_VERSION, "notes": _finish(groups), "totals": totals}


def resolve_data_notes(dataset: Mapping[str, Any]) -> dict:
    """Return saved notes or legacy presentation, detached from the caller/ORM JSON.

    Present but unusable metadata is an error; only absence activates the legacy fallback.
    The application owns saved envelopes. API ingress performs complete wire validation.
    """
    if "data_notes" not in dataset:
        return data_notes(dataset)
    envelope = dataset["data_notes"]
    if (not isinstance(envelope, dict) or type(envelope.get("version")) is not int
            or envelope["version"] != DATA_NOTES_VERSION or not isinstance(envelope.get("notes"), list)
            or not isinstance(envelope.get("totals"), dict)):
        raise ValueError("Unsupported or malformed analysis data notes")
    return deepcopy(envelope)


def citation_data_notes(citations: Iterable[Mapping[str, Any]], report_notes: Mapping[str, Any]) -> dict:
    """Append citation-only issues after report letters without changing report populations."""
    result = deepcopy(report_notes)
    groups: dict[str, dict] = {}
    for citation in citations:
        _add(groups, citation)
    existing = {note["key"] for note in result["notes"]}
    next_index = 0
    for note in result["notes"]:
        number = 0
        for char in note["letter"]:
            number = number * 26 + ord(char) - 96
        next_index = max(next_index, number)
    for note in _finish(groups):
        if note["key"] in existing:
            continue
        note["letter"] = _letter(next_index)
        note["id"] = f"analysis-data-note-{note['letter']}"
        next_index += 1
        result["notes"].append(note)
        existing.add(note["key"])
    return result
