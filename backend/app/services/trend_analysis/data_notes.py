"""Versioned presentation notes; never alter financial values or source validation."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

DATA_NOTES_VERSION = 1
_MISSING = object()
_KINDS = {"review": 0, "unknown": 1, "unavailable": 2}
_BASES = ("qoq", "yoy", "cagr", "window_pp")
_FALLBACK_MESSAGE = "The source or calculation basis needs review. Check the original filing."
REASONS = {
    "not_in_dataset": "Not available in this dataset.",
    "legacy_calculation": "This saved calculation predates the current source checks. Its inputs need review.",
    "source_check_needed": "A source check remains unresolved. Review the original filing before use.",
    "unsupported_eps_calculation": "This quarterly earnings-per-share calculation is not supported. Use a reported quarterly EPS figure.",
    "legacy_calculation_not_supported": "This saved calculation could not be reproduced from compatible source inputs and is unavailable.",
    "repair_rolled_back": "This figure was withdrawn during a data correction and is unavailable.",
    "incompatible_vintages": "The inputs come from incompatible versions of the company’s filings.",
    "missing_compatible_operand": "A compatible earlier year-to-date figure is unavailable for this calculation.",
    "negative_calculated_value": "The calculation produced an invalid negative amount and was withheld.",
    "missing_inputs": "The source inputs needed for this calculation are unavailable.",
    "missing_input": "A source input needed for this calculation is unavailable.",
    "missing_source": "The original source could not be established.",
    "missing_provenance": "Detailed source information is unavailable for this figure.",
    "legacy_unverified": "This saved figure needs a source check before use.",
    "legacy_unreconciled": "This saved figure needs a source check before use.",
    "legacy_unknown": "Validation details are unavailable for this saved figure. No verification claim is made.",
    "legacy_provenance_unavailable": "Detailed source information is unavailable for this saved figure.",
    "incompatible_inputs": "The source inputs do not have a compatible reporting basis.",
    "mixed_vintage": "The calculation combines figures from different filing versions.",
    "mixed_vintages": "The calculation combines figures from different filing versions.",
    "unit_mismatch": "The source inputs use different units or currencies.",
    "period_mismatch": "The source inputs cover incompatible reporting periods.",
    "missing_adjacent_period": "The immediately preceding period is unavailable.",
    "eps_not_additive": "Quarterly earnings per share cannot be obtained by subtracting annual and year-to-date EPS.",
    "eps_requires_reported_quarter": "A reported quarterly earnings-per-share figure is unavailable.",
    "rounded_share_count": "Rounded weighted-average share counts do not establish an exact quarterly EPS figure.",
    "source_conflict": "Available sources disagree on this figure.",
}


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


def _finish(groups: dict) -> list[dict]:
    # Python's stable sort preserves first report appearance within each kind.
    notes = sorted(groups.values(), key=lambda note: _KINDS[note["kind"]])
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
