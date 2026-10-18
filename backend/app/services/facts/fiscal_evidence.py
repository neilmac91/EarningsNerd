"""Trust the fiscal year companyfacts already names a period end by, and name an annual filing's years alike.

The companyfacts writer names an FY period from its whole year chain (``facts/calendar``), so it outvotes
one annual report's lagging DEI focus; the per-filing labeller sees one filing and cannot
(``edgar/fiscal_periods.annual_fiscal_label``). Evidence at a (company, period_end) is every
companyfacts-reported FY row there (source ``companyfacts``, no filing owner, a raw tag, a fiscal year,
not retired by a quarterly repair as ``validation: unavailable``) that the fiscal-year-window writer
stored or a repair corrected (provenance version ``PROVENANCE_VERSION``), current or not. A row stored
before that writer (NULL provenance) names every FY period by the calendar year of its end, so it is no
evidence. The evidence must name one year and include a duration: the writer names an FY balance older
than every year window it knows by one report's ``fy`` or by calendar year, with no chain behind it.
The stored-row relabel (#1372) applies the same rule.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from app.models import FinancialFact
from app.services.fact_provenance import PROVENANCE_VERSION
from app.services.facts.calendar import ANNUAL_FORMS


def evidence_kind(row: Any) -> Optional[str]:
    """``current`` for a companyfacts-reported FY row the fiscal-year-window writer stored (or a
    repair corrected), ``legacy`` for one stored before it, None for any other row."""
    provenance = row.provenance if isinstance(row.provenance, dict) else {}
    if (row.source != "companyfacts" or row.filing_id is not None or row.raw_tag is None
            or row.fiscal_year is None or provenance.get("validation") == "unavailable"):
        return None
    return "current" if provenance.get("version") == PROVENANCE_VERSION else "legacy"


def trusted_year(evidence: list[tuple[int, bool]], legacy: bool) -> tuple[Optional[int], Optional[str]]:
    """The one companyfacts year at a period end, from its (year, is_duration) evidence, or the reason
    none can be trusted."""
    if not evidence:
        return None, "legacy_companyfacts_only" if legacy else "no_companyfacts_fy"
    years = {year for year, _is_duration in evidence}
    if len(years) > 1:
        return None, "companyfacts_disagree"
    if not any(is_duration for _year, is_duration in evidence):
        return None, "untrusted_instant_only"
    return years.pop(), None


def trusted_fiscal_years(db: Session, company_id: int, period_ends: Iterable[date]) -> dict[date, int]:
    """The trusted companyfacts year at each of these FY period ends that has one, in one query."""
    rows = db.query(
        FinancialFact.period_end, FinancialFact.period_start, FinancialFact.fiscal_year, FinancialFact.source,
        FinancialFact.filing_id, FinancialFact.raw_tag, FinancialFact.provenance,
    ).filter(
        FinancialFact.company_id == company_id, FinancialFact.fiscal_period == "FY",
        FinancialFact.source == "companyfacts", FinancialFact.period_end.in_(sorted(set(period_ends))),
    )
    evidence: dict[date, list[tuple[int, bool]]] = defaultdict(list)
    for row in rows:
        if evidence_kind(row) == "current":
            evidence[row.period_end].append((row.fiscal_year, row.period_start is not None))
    years = {end: trusted_year(items, legacy=False)[0] for end, items in evidence.items()}
    return {end: year for end, year in years.items() if year is not None}


def adopt_trusted_fiscal_years(db: Session, form: Optional[str], facts: list[dict[str, Any]]) -> None:
    """Move an annual report's FY facts onto the years companyfacts already names, by one offset.

    Each FY fact's own label (its filing's DEI focus, else the calendar year of its end) is compared
    with the trusted companyfacts year at its end. When every fact that has one gives the same offset,
    every FY fact of the filing moves by it, so the filing's years stay one apart: taking the year end
    by end would give the newest year, which companyfacts does not hold yet, the label of the one
    before it. Disagreeing offsets, or no trusted year at all (companyfacts not synced yet), keep the
    filing's own labels. A calendar-aligned or Target-style filing moves by zero; quarter labels never
    move. Mutates ``facts``; one query for an annual report, none otherwise. The fact writers' company
    lock is taken before that query, so a companyfacts sync cannot commit between the evidence read
    and the write that follows (``upsert_facts`` takes it again in the same transaction).
    """
    annual = [fact for fact in facts if fact["fiscal_period"] == "FY"] if form in ANNUAL_FORMS else []
    if not annual:
        return
    from app.services.facts.upsert import _lock_fact_companies  # upsert imports this module

    _lock_fact_companies(db, annual)
    trusted = trusted_fiscal_years(db, annual[0]["company_id"], {fact["period_end"] for fact in annual})
    offsets = {trusted[fact["period_end"]] - fact["fiscal_year"] for fact in annual if fact["period_end"] in trusted}
    if len(offsets) == 1 and (offset := offsets.pop()):
        for fact in annual:
            fact["fiscal_year"] += offset
