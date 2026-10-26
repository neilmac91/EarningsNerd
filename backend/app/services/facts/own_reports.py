"""Each fiscal year's own-report value, kept beside the companyfacts winner as a non-current row.

Companyfacts ingest stores one winner per period: the latest-filed item of the first tag with data
(``companyfacts._collect_companyfacts_values``). When a later annual report gives a year another value
(a recast, a change of scope, a correction), the value the year's own report gave lived only among the
collector's in-memory candidates and was never stored (REGN revenue: FY2018 6,710.8M in its own 10-K,
5,145.6M in the FY2020 10-K's comparatives). ``own_report_history`` finds that report's value beside each
FY winner, and ``insert_history_rows`` stores it as a history row.

A history row is never current and never an operand of the sync's derivations; the restatement note
will read it. The 2026-10 census found most such differences are legitimate recasts, so the winner
stays the value shown. The normalizer returns history facts apart from its ``facts``
(``meta["history"]``), because the same-period and quarter derivations read ``facts`` and a history
fact there would replace the winner as an operand; and the bulk writer stores them apart from its
``is_latest`` bookkeeping, so a history row never demotes, promotes or replaces a row. It is the own
report's figure at that report's accession, so a reader of one filing's rows, current or not (the
annual chart, ``facts/filing_scope.py``; the Copilot), reads it as that filing's own, like any row
stored there.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, Iterable, Optional

from app.services.facts.concepts import NON_NEGATIVE_CONCEPTS
from app.services.facts.fiscal_naming import own_period_ends
from app.services.facts.quarterly import reported_fact

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

Records = dict[str, dict[tuple[date, str], dict[str, Any]]]


def own_report_history(facts: list[dict[str, Any]], duration_values: Records,
                       instant_values: Records) -> list[dict[str, Any]]:
    """The year's own-report value beside each FY winner that another filing supplied.

    Reads the normalizer's kept ``facts`` for their reported FY rows (``source`` companyfacts): FY
    durations, and instants labelled FY (a fiscal-year-end balance). A winner the hard reject dropped is
    not among them, so it gets no history row. The own report is found by ``_own_report`` among the
    winner's candidates. A history fact is that report's item, labelled with the winner's fiscal year,
    when its accession is not the winner's and its value differs from the winner's. Values compare
    exactly: both are floats parsed from companyfacts' JSON numbers, so the same reported figure is the
    same float, and any difference, a last-digit rounding included, is one the two filings report; what a
    reader treats as a material difference is the reader's tolerance, not ingest's. A negative value of
    a ``NON_NEGATIVE_CONCEPTS`` concept is dropped: neither fact writer stores one, as winner or not.
    """
    own_ends = own_period_ends(duration_values)
    history: list[dict[str, Any]] = []
    for fact in facts:
        if fact.get("source") != "companyfacts" or fact["fiscal_period"] != "FY":
            continue
        concept, end = fact["concept"], fact["period_end"]
        record = (duration_values.get(concept) or {}).get((end, "FY")) or (
            instant_values.get(concept) or {}).get((end, "I"))
        own = _own_report(record, end, own_ends) if record else None
        if own is None or own.get("accession") == fact["accession"] or own["value"] == fact["value"]:
            continue
        if concept in NON_NEGATIVE_CONCEPTS and own["value"] < 0:
            continue
        history.append({**reported_fact(fact["company_id"], concept, own["unit"], own),
                        "fiscal_year": fact["fiscal_year"], "fiscal_period": "FY"})
    return history


def _own_report(record: dict[str, Any], end: date, own_ends: dict[str, date]) -> Optional[dict[str, Any]]:
    """The year's own annual report among a winner's candidates, or None.

    Candidates are the winning tag's items for the winner's period (``_collect_companyfacts_values``),
    and only items ``currency.admitted_items`` keeps reach them, so a proxy or information statement's
    item is never one; nor is another tag's item, even where the own report used another tag for the
    line (a gap the restatement census measured). An own report is an annual report whose own period
    ends on ``end`` (``own_period_ends``, which maps each annual report's accession, and no other
    form's, to the latest fiscal year it reports), for the winner's period start. An original wins over
    an amendment, then the earliest filed; companyfacts' filing order breaks a tie.
    """
    owns = [candidate for candidate in record.get("candidates") or [record]
            if own_ends.get(candidate.get("accession")) == end
            and candidate.get("period_start") == record.get("period_start")]
    return min(owns, key=lambda c: (c["form"].endswith("/A"), c.get("filed") or ""), default=None)


def insert_history_rows(db: Session, history: Iterable[dict[str, Any]], stored: set[tuple]) -> int:
    """Store each history fact as a non-current row where its identity is absent; returns how many.

    ``stored`` is the bulk writer's identity set, (concept, period_end, fiscal_period, unit,
    accession) for the company: its prefetched rows and the batch it has just written. It gains each
    identity inserted. An identity already stored, current or not, by either fact writer, is left as it
    is, so a re-sync inserts nothing. A history row never enters the writer's ``is_latest`` bookkeeping:
    it demotes no row, and a winner arriving later at its key never promotes it.
    """
    from app.models import FinancialFact  # lazy: the pure normalizer imports this module

    inserted = 0
    for fact in history:
        identity = (fact["concept"], fact["period_end"], fact["fiscal_period"], fact["unit"], fact["accession"])
        if identity in stored:
            continue
        stored.add(identity)
        row = dict(fact)
        reconciled = bool(row.pop("reconciled", False))
        db.add(FinancialFact(**row, is_latest=False, reconciled=reconciled))
        inserted += 1
    return inserted
