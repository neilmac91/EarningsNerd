"""A filing's own annual figures among the stored fact rows: the filing-scoped chart's selection.

The fact identity (company, concept, period end, fiscal period, unit, accession) holds the accession,
and both writers skip an identity already stored (``facts/upsert.py``). A companyfacts sync stores each
period's winner under the accession of the filing that reported it last, with no filing owner; a year's
own-report row, kept beside a restated winner, is stored the same way under that report's accession.
When either is stored before the filing's own facts are written, it holds the filing's cell and the
per-filing writer adds no row there: every cell of the newest annual report, the oldest year and older
balance of an older one, and an older one's own year where a later report gave that year another value.
``filing_id`` therefore says which writer stored a row, never which filing reported it; a filing's
figures are the rows at its company and accession (``lessons/arch-read-a-filings-facts-by-its-accession.md``).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Filing, FinancialFact
from app.services.fact_provenance import operands_within_accession, provenance_for_fact
from app.services.facts.currency import _operand_unit, _reporting_currency, is_amount_unit
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


def _currency(row: FinancialFact) -> str | None:
    """The currency a row's figure is in: its unit's code ("CNY" for "CNY/shares" too), or for a ratio,
    whose unit names none, the code its recorded operands share (``currency._operand_unit``)."""
    unit = _operand_unit(provenance_for_fact(row)) if row.unit == "pure" else row.unit
    code = unit.partition("/")[0] if isinstance(unit, str) else None
    return code if is_amount_unit(code) else None


def _ranked_first(rows: list[FinancialFact]) -> str | None:
    """The currency the per-filing extractor's rule (``currency._reporting_currency``) ranks first over
    these rows: the most period ends, then a non-USD code. Presence at the filing's own year breaks no
    tie: a USD translation of that year, which only this report gave, always sits there, while the
    native row for it sits under a later report's accession once that report re-reported it."""
    return _reporting_currency([(row.period_end.isoformat(), 0.0, _currency(row), 0.0) for row in rows],
                               period_of_report="")


def _counted_stand_ins(own: list[FinancialFact], stand_ins: list[FinancialFact]) -> set[FinancialFact]:
    """The stand-ins that count in the filing's currency. In a line the filing owns rows of, only in
    their units, so a stand-in never adds a second unit to a line. In any other line, only in the
    currency the filing's own rows rank first (``_currency``: a ratio's is its operands'): the
    per-filing extractor chose it for this report, while a sync may hold a line only in USD (an early
    sync read the USD lists alone; a current one reads them for a filer that switched currency,
    ``currency.series_unit``), and that line's own-year translation alone reaches the period end.
    Only when no row of the filing's own carries a currency do the stand-ins rank their own: the
    sync held every annual cell the writer read, in the writer's currency (the newest report synced
    first, at a domestic filer or after a native sync), or the writer stored no annual row (an
    interim report, or a report it read nothing annual from)."""
    own_units: dict[str, set[str]] = {}
    for row in own:
        own_units.setdefault(row.concept, set()).add(row.unit)
    code = _ranked_first(own) or _ranked_first(stand_ins)
    return {row for row in stand_ins
            if (row.unit in own_units[row.concept] if row.concept in own_units else _currency(row) == code)}


def _lines_reaching(rows: list[FinancialFact], period_end: date | datetime | None) -> set[str]:
    """The concepts whose line has a row at the filing's own period end. ``Filing.period_end_date`` is the
    period of report EDGAR's submissions index gives (``reportDate``), not a date read from the XBRL
    contexts the rows came from. The two name the same day in nearly every report; the year-end slack
    ``fiscal_naming.DRIFT_DAYS`` absorbs the odd one a day off and stays well inside the quarter between
    a 10-Q's period end and the prior year-end balance it holds. Counted in days, never calendar years:
    a year ending by September and its first quarter end in one calendar year. A filing with no period
    end on record has no line known to reach it."""
    if period_end is None:
        return set()
    end = period_end.date() if isinstance(period_end, datetime) else period_end
    return {row.concept for row in rows if abs((row.period_end - end).days) <= DRIFT_DAYS}


def _first_years_after_a_missing_one(db: Session, company_id: int, rows: list[FinancialFact]) -> dict[str, date]:
    """Each line's first period end after the latest year it misses: two of its rows, next by period end
    (``rows`` in concept, then period-end order), between which the company holds an FY row of the concept
    a whole number of years after the earlier one (``fiscal_naming.years_back``) and more than
    ``DRIFT_DAYS`` before the later one. The filing reported that year, as the company's other filings
    show, but its row sits under another accession, so on the chart's categorical axis the two would
    stand side by side as consecutive years. An older report's line the per-filing writer read nothing
    of has one when a later report restated its own year: the sync holds the oldest year, which the
    report filed last, and the own year, the own-report row (``facts/own_reports.py``), while the year
    between sits under the next report's accession. A gap no FY row fills is the company's own: a
    fiscal-year change's transition period, a fresh-start split year, a year no filing reported. It is
    no missing year, and the line shows as it stands. A withheld row (``validation`` unavailable) fills
    no gap. One read, and only when some line has two rows more than a year and ``DRIFT_DAYS`` apart."""
    pairs = [(row, after) for row, after in zip(rows, rows[1:])
             if row.concept == after.concept and (after.period_end - row.period_end).days > 365 + DRIFT_DAYS]
    if not pairs:
        return {}
    held: dict[str, set[date]] = {}
    for row in db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id,
        FinancialFact.fiscal_period == "FY",
        FinancialFact.concept.in_({row.concept for row, _after in pairs}),
        FinancialFact.period_end > min(row.period_end for row, _after in pairs),
        FinancialFact.period_end < max(after.period_end for _row, after in pairs),
    ):
        if provenance_for_fact(row)["validation"] != "unavailable":
            held.setdefault(row.concept, set()).add(row.period_end)
    first: dict[str, date] = {}
    for row, after in pairs:
        if any((years_back(row.period_end, end) or 0) >= 1 and (after.period_end - end).days > DRIFT_DAYS
               for end in held.get(row.concept, ())):
            first[row.concept] = after.period_end  # pairs run in period-end order: the latest gap wins
    return first


def annual_filing_rows(db: Session, filing: Filing) -> list[FinancialFact]:
    """The filing's own FY rows, by concept then period end, current or not.

    Read at the filing's company and accession (another company's rows under a combined report's
    accession stay out). The rows the per-filing writer stored count, but for a missing year (below). A
    row another writer stored there stands in for the filing's (``_stands_in``) only once that writer
    has run (``processed_facts_at``), so the chart never lacks the lines and years it adds, only in the
    filing's currency (``_counted_stand_ins``), and only in a line that reaches the filing's own period
    end (``_lines_reaching``, over the rows that count): short of it, the rows stored there are only
    the cells this filing reported last (an older report's oldest year and older balance; an interim
    report's prior year-end balance, which the sync labels FY although the per-filing writer stores no
    FY row for an interim report), and a line of those alone would read as all it disclosed. A line
    that misses a year another of the company's rows holds shows only its years after the latest one it
    misses (``_first_years_after_a_missing_one``), the filing's own rows among them, so which writer
    holds a cell before the gap, which the order the writers ran decides, does not decide the line. No
    ``is_latest`` filter: a later restatement demotes the rows, never removes them from their filing's
    chart.
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
    own = [row for row in rows if row.filing_id is not None]
    counted = _counted_stand_ins(own, [row for row in rows if row.filing_id is None
                                       and processed and _stands_in(row, filing.accession_number)])
    chosen = [row for row in rows if row.filing_id is not None or row in counted]
    reaching = _lines_reaching(chosen, filing.period_end_date)
    kept = [row for row in chosen if row.filing_id is not None or row.concept in reaching]
    first = _first_years_after_a_missing_one(db, filing.company_id, kept)
    return [row for row in kept if row.period_end >= first.get(row.concept, row.period_end)]


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
