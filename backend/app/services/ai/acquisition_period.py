"""Withhold one complete relative-period acquisition proposition; never reconstruct a financial claim."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

CONTEXT_KEY = "acquisition_period_context_version"
CONTEXT_VERSION = 1
OWNED_FIELD = "acquisition_period_limitation"
LIMITATION = "This summary could not independently verify the period attribution of the estimated acquisition gain."

# Closed complete shapes, bounded lexical tokens, no issuer/amount/year literal.
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
MONEY = r"\$[0-9]{1,12}(?:\.[0-9]{1,3})? (?:million|billion)"
NAME = r"[A-Z][A-Za-z0-9&'’.-]{0,29}(?: [A-Z][A-Za-z0-9&'’.-]{0,29}){0,7}"
DATE = rf"{MONTH}[ \u00a0][0-9]{{1,2}}, [0-9]{{4}}"
FIRST = (
    rf"The prior year included (?:an|the) estimated bargain purchase gain of (?P<amount>{MONEY}) "
    rf"for the year ended (?P<date>{DATE}) associated with the (?P<subject>{NAME}) acquisition"
)
SECOND = (
    rf"the current year included a (?P<second_amount>{MONEY}) (?P<second_subject>{NAME})-related gain "
    r"recorded in the (?P<quarter>first|second|third|fourth) quarter of (?P<second_year>[0-9]{4})\."
)
WHOLE = re.compile(rf"\A(?P<first>{FIRST});(?P<continuation> {SECOND})\Z")
SOURCE_SHAPE = (
    rf"Included the estimated bargain purchase gain of (?P<amount>{MONEY}) "
    rf"for the year ended (?P<date>{DATE}) associated with the (?P<subject>{NAME}) acquisition\."
)
SOURCE = re.compile(rf"\A{SOURCE_SHAPE}\Z")
SOURCE_FIND = re.compile(SOURCE_SHAPE)


def _norm(text: str) -> str:
    return text.replace("\xa0", " ")


def _frame(metrics: dict | None) -> tuple[date, date] | None:
    if not isinstance(metrics, dict):
        return None
    pairs = set()
    for metric in metrics.values():
        if not isinstance(metric, dict) or not {"current", "prior"} & metric.keys():
            continue
        current, prior = (metric.get("current"), metric.get("prior"))
        if not isinstance(current, dict) or not isinstance(prior, dict):
            return None
        # Source provenance envelopes use period_end; standardized metric points use period.
        if all(("period" not in point and "period_end" in point for point in (current, prior))):
            continue
        try:
            raw = (current.get("period"), prior.get("period"))
            if any(
                (not isinstance(value, str) or not re.fullmatch("[0-9]{4}-[0-9]{2}-[0-9]{2}", value) for value in raw)
            ):
                return None
            current_date, prior_date = map(date.fromisoformat, raw)
        except ValueError:
            return None
        if current_date.year != prior_date.year + 1 or (current_date.month, current_date.day) != (
            prior_date.month,
            prior_date.day,
        ):
            return None
        pairs.add((current_date, prior_date))
    return next(iter(pairs)) if len(pairs) == 1 else None


def _select(note: dict, excerpt: str, metrics: dict | None, *, recovered: bool = False) -> dict | None:
    """Return a capability-only selection record, never affirmative financial prose."""
    if recovered:
        return None
    if not isinstance(note, dict) or not isinstance(note.get("impact"), str):
        return None
    match = WHOLE.fullmatch(note["impact"])
    if match is None:
        return None
    if match["subject"] != match["second_subject"]:
        return None
    try:
        explicit = datetime.strptime(_norm(match["date"]), "%B %d, %Y").date()
        date(int(match["second_year"]), 1, 1)
    except ValueError:
        return None
    for primary, alternate in (
        ("supporting_evidence", "supportingEvidence"),
        ("source_section_ref", "sourceSectionRef"),
    ):
        left, right = (note.get(primary), note.get(alternate))
        if left and right and (left != right):
            return None
    evidence = note.get("supporting_evidence") or note.get("supportingEvidence")
    if (
        not isinstance(evidence, str)
        or not evidence
        or (not isinstance(excerpt, str))
        or (excerpt.count(evidence) != 1)
    ):
        return None
    source = SOURCE.fullmatch(evidence)
    if source is None or any((_norm(source[key]) != _norm(match[key]) for key in ("amount", "date", "subject"))):
        return None
    matching_subjects = [found for found in SOURCE_FIND.finditer(excerpt) if found["subject"] == match["subject"]]
    if len(matching_subjects) != 1:
        return None
    periods = _frame(metrics)
    if periods is None:
        return None
    current, prior = periods
    if explicit.year in {current.year, prior.year}:
        return None
    if int(match["second_year"]) != current.year:
        return None
    return {
        "authored_continuation": match["continuation"],
        "audit": {
            "kind": "unverified_acquisition_period",
            "source_offset": excerpt.index(evidence),
            "source_length": len(evidence),
            "current": current.isoformat(),
            "prior": prior.isoformat(),
        },
    }


def bind_acquisition_period(sections: dict, excerpt: str, metrics: dict | None, *, recovered: bool = False) -> bool:
    """Select only original primary evidence; erase untrusted model-owned metadata on every path."""
    notes = sections.get("notable_footnotes")
    if not isinstance(notes, list):
        return False
    bound = False
    for note in notes:
        if not isinstance(note, dict):
            continue
        note.pop(OWNED_FIELD, None)
        selected = _select(note, excerpt, metrics, recovered=recovered)
        if selected is not None:
            note.pop("impact")
            note[OWNED_FIELD] = selected
            bound = True
    return bound


def project_footnotes(notes: Any, *, owned: bool = False) -> Any:
    """One visible projection for web, exports and the eval; audit/ownership metadata is private."""
    if not isinstance(notes, list):
        return notes
    result = []
    for note in notes:
        if not isinstance(note, dict):
            result.append(note)
            continue
        visible = dict(note)
        record = visible.pop(OWNED_FIELD, None)
        if owned and isinstance(record, dict):
            visible["impact"] = LIMITATION + record["authored_continuation"]
        result.append(visible)
    return result
