"""Withhold one complete tax-cause interpretation; never reconstruct a cause."""
from __future__ import annotations

from datetime import date
import re
from typing import Any

from app.services.edgar.tax_rate_comparison import RATE_LEXEME
from app.services.provenance_service import normalize_for_match

LIMITATION = "This summary could not independently verify the explanation of the tax-rate change."
AUDIT_KEY = "tax_rate_explanation_audit"
_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December")
_CLAIM = re.compile(
    r"The effective tax rate for the three months ended "
    rf"(?P<month>{'|'.join(_MONTHS)}) (?P<day>[1-9]|[12][0-9]|3[01]), (?P<year>(?:19|20)[0-9]{{2}}) "
    rf"was (?P<current>{RATE_LEXEME})% versus (?P<prior>{RATE_LEXEME})% for the prior year period, "
    r"primarily due to limitations on the deductibility of officer compensation and state taxes\."
)
_SOURCE_CLAIM = re.compile(_CLAIM.pattern, re.I)


def strip_tax_explanation_metadata(value: Any) -> None:
    """The model cannot supply application audit records, at any nesting depth."""
    if isinstance(value, dict):
        value.pop(AUDIT_KEY, None)
        for child in value.values():
            strip_tax_explanation_metadata(child)
    elif isinstance(value, list):
        for child in value:
            strip_tax_explanation_metadata(child)


def _operands(text: str, *, source: bool = False) -> tuple[str, str, str] | None:
    match = _SOURCE_CLAIM.fullmatch(text) if source else _CLAIM.fullmatch(text)
    if match is None:
        return None
    try:
        month = [name.lower() for name in _MONTHS].index(match["month"].lower()) + 1
        end = date(int(match["year"]), month, int(match["day"]))
    except ValueError:
        return None
    return end.isoformat(), match["current"], match["prior"]


def withhold_tax_rate_explanation(sections: dict[str, Any], index: Any) -> list[dict]:
    """Replace only a whole admitted impact. All other authored bytes stay authored.

    Tagged operands select the narrow claim family, not source truth. Even source
    withdrawal outside the chain cannot make this application-capability statement
    an assertion of a financial fact or a finding that the filing lacks disclosure.
    """
    strip_tax_explanation_metadata(sections)
    notes = sections.get("notable_footnotes")
    if not isinstance(notes, list):
        return []
    candidates = []
    for position, note in enumerate(notes):
        if not isinstance(note, dict) or not isinstance(note.get("impact"), str):
            continue
        operands = _operands(note["impact"])
        evidence = note.get("supporting_evidence", note.get("supportingEvidence"))
        if (operands is None or not isinstance(evidence, str) or not evidence.strip()
                or ("supporting_evidence" in note and "supportingEvidence" in note
                    and note["supporting_evidence"] != note["supportingEvidence"])):
            continue
        candidates.append((position, note, operands, evidence))
    selected = index.tax_rate_comparison() if candidates and index is not None else None
    if selected is None:
        return []
    rates = {r["period_end"]: r["percent_lexical"] for r in selected["rates"]}
    end = date.fromisoformat(selected["report_end"])
    expected = (end.isoformat(), rates[end.isoformat()], rates[end.replace(year=end.year - 1).isoformat()])
    # A complete source explanation conservatively excludes withholding; this is
    # not a verification badge. Unknown formulations remain outside this contract.
    if any(_operands(normalize_for_match(p), source=True) == expected for p in selected["paragraphs"]):
        return []
    source_text = normalize_for_match(selected["text"])
    audit = []
    for position, note, operands, evidence in candidates:
        if operands != expected or source_text.count(normalize_for_match(evidence)) != 1:
            continue
        note["impact"] = LIMITATION
        audit.append({"slot": f"notable_footnotes[{position}].impact", "reason": "interpretation_not_verified",
                      "assertion_scope": selected["assertion_scope"], "root_id": selected["root_id"],
                      "chain_ids": selected["chain_ids"], "rates": selected["rates"]})
    return audit
