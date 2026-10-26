"""A filing's own annual figures among the stored fact rows: the filing-scoped chart's selection.

The fact identity (company, concept, period end, fiscal period, unit, accession) holds the accession,
and both writers skip an identity already stored (``facts/upsert.py``). A companyfacts sync stores each
period's winner under the accession of the filing that reported it last, with no filing owner; a year's
own-report row, kept beside a restated winner, is stored the same way under that report's accession.
When either is stored before the filing's own facts are written, it holds the filing's cell and the
per-filing writer adds no row there: every cell of the newest annual report, the oldest year and older
balance of an older one. ``filing_id`` therefore says which writer stored a row, never which filing
reported it; a filing's figures are the rows at its company and accession
(``lessons/arch-read-a-filings-facts-by-its-accession.md``).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Filing, FinancialFact
from app.services.fact_provenance import operands_within_accession, provenance_for_fact
from app.services.facts.currency import _reporting_currency
from app.services.facts.fiscal_naming import DRIFT_DAYS, years_back


def _stands_in(row: FinancialFact, accession: str) -> bool:
    """Whether a row another writer stored at the filing's accession shows as the filing's own figure:
    an item the filing reported, or a calculation over operands it reported, every one on record. A
    companyfacts calculation takes its first operand's accession (revenue's, for a margin), so its
    other operand may be a later filing's. A row the audited repair retired, or the publication policy
    withholds, stands in for nothing."""
    provenance = provenance_for_fact(row)
    if provenance["validation"] == "unavailable":
        return False
    if provenance["method"] != "calculated":
        return True
    return bool(provenance["inputs"]) and operands_within_accession(provenance, accession)


def _series_units(rows: list[FinancialFact]) -> dict[str, set[str]]:
    """Each concept's units: those of the filing's own rows, else the one the per-filing extractor's
    reporting-currency rule picks among the stand-ins (``currency._reporting_currency``: the most
    period ends, then a non-USD code), so a stand-in never adds a second currency to a line (a USD
    convenience row an early sync stored beside the native history)."""
    units: dict[str, set[str]] = {}
    for concept in dict.fromkeys(row.concept for row in rows):
        series = [row for row in rows if row.concept == concept]
        units[concept] = {row.unit for row in series if row.filing_id is not None}
        if not units[concept]:
            ends = [(row.period_end.isoformat(), 0.0, row.unit.partition("/")[0], 0.0) for row in series]
            code = _reporting_currency(ends, max(ends)[0])
            units[concept] = {row.unit for row in series if row.unit.partition("/")[0] == code}
    return units


def _lines_reaching(rows: list[FinancialFact], period_end: date | datetime | None) -> set[str]:
    """The concepts whose line has a row at the filing's own period end, within a 52/53-week calendar's
    drift (``fiscal_naming.DRIFT_DAYS``): ``Filing.period_end_date`` is the period of report EDGAR's
    submissions index gives (``reportDate``), not a date read from the XBRL contexts the rows came from.
    A filing with no period end on record has no line known to reach it."""
    if period_end is None:
        return set()
    end = period_end.date() if isinstance(period_end, datetime) else period_end
    return {row.concept for row in rows if abs((row.period_end - end).days) <= DRIFT_DAYS}


def annual_filing_rows(db: Session, filing: Filing) -> list[FinancialFact]:
    """The filing's own FY rows, by concept then period end, current or not.

    Read at the filing's company and accession (another company's rows under a combined report's
    accession stay out). The rows the per-filing writer stored count always. A row another writer
    stored there stands in for the filing's (``_stands_in``) only once that writer has run
    (``processed_facts_at``), so the chart never lacks the lines and years it adds, and only in a line
    that reaches the filing's own period end (``_lines_reaching``): short of it, the rows stored there
    are only the cells this filing reported last (an older report's oldest year and older balance; an
    interim report's prior year-end balance, which the sync labels FY although the per-filing writer
    stores no FY row for an interim report), and a line of those alone would read as all it
    disclosed. No ``is_latest`` filter: a later restatement demotes the rows, never removes them from
    their filing's chart.
    """
    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.company_id == filing.company_id,
            FinancialFact.accession == filing.accession_number,
            FinancialFact.fiscal_period == "FY",
        )
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.asc())
        .all()
    )
    processed = filing.processed_facts_at is not None
    chosen = [row for row in rows if row.filing_id is not None
              or processed and _stands_in(row, filing.accession_number)]
    units = _series_units(chosen)
    chosen = [row for row in chosen if row.unit in units[row.concept]]
    reaching = _lines_reaching(chosen, filing.period_end_date)
    return [row for row in chosen if row.filing_id is not None or row.concept in reaching]


def filing_years(rows: list[FinancialFact]) -> dict[int, int | None]:
    """The fiscal year each of a filing's rows shows under, by row id. The filing's own rows keep theirs.
    A stand-in is named as the per-filing writer would have named its cell: whole years counted back or
    forward from the latest period end the filing's own rows name, never a stand-in's
    (``fiscal_naming.years_back``), else by its own label. A companyfacts row stored before the
    fiscal-year-window writer names its year by the calendar year of its end, so for an issuer that
    names a year by its start (Target) or a 52-week year ending on 1 January, its own label would
    repeat the next bar's."""
    own = {row.period_end: row.fiscal_year for row in rows if row.filing_id is not None and row.fiscal_year}
    anchor = max(own, default=None)
    years: dict[int, int | None] = {}
    for row in rows:
        back = None if row.filing_id is not None or anchor is None else years_back(*sorted((row.period_end, anchor)))
        years[row.id] = row.fiscal_year if back is None else own[anchor] + (back if row.period_end > anchor else -back)
    return years
