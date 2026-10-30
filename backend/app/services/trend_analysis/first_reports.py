"""Each fiscal year's own annual report's value, read beside the value a later filing reports (MPA WP5a).

The dataset shows each year's current row, the latest filing's value. Where a later annual report gave a year another
value (a recast, a change of scope, a correction), WP5b (#1682, ``facts/own_reports.py``) keeps the value the year's own
annual report gave as a non-current row at that report's accession; the per-filing writer's rows and a demoted former
winner can hold the same cell, since both writers skip a stored identity. This module reads those rows once per annual
dataset and gives a reported figure whose own report's value differs by more than ``EVIDENCE_TOLERANCE`` the evidence
the page's dialog shows (``first_reported``, frontend ``features/analysis/lib/laterFilings.ts``, which decodes it).
It is evidence, not a data note (D-061): it changes no value, validation, totals or letter.

"Own report" is ingest's rule (``own_reports._own_report``) replayed on stored rows, since nothing on a row marks it
as one. Ingest takes a filing's own period end as the latest fiscal-year duration it reports
(``fiscal_naming.own_period_ends``); the database keeps only some of a filing's items (each period's winner, and an own
value a later filing changed), so here it is the latest fiscal-year row stored at its accession, a year-end balance
included, of an annual form, an item with no form counting where its accession is an annual report's, as ingest reads
it. A stored row never lies past its filing's own end, so this end is ingest's or earlier; a filing row whose period of
report lies beyond it by more than ``DRIFT_DAYS`` says the filing's own year was never stored, and then none of its rows
is its own. A row is a figure's own report where its accession's own end is the figure's period end, for the same
concept, unit and span, at another filing; an original wins over an amendment, then the earliest filed, then the
accession (companyfacts' listing order, ingest's last key, is not stored). ``tests/unit/test_first_reports.py`` holds
the two rules to one answer over WP5b's own-report shapes.

Growth across a change of basis reads n/m (item 3): where the two years of a YoY sit on different bases, the ratio of
the value shown to the value first reported moving by more than ``BASIS_TOLERANCE`` between them, the comparison reads
"nm" and carries the growth their own reports give (``yoy_first_reported``); a calculated figure's growth reads n/m
where one of its inputs changed basis (D4). Nothing else of the comparison changes: its provenance and checks stand.

Annual runs only (D5): WP5b stores fiscal-year rows alone, and the page refuses evidence in a quarterly run, so a
quarterly dataset reads nothing more and carries none. No CAGR or window change reads n/m (D5, deferred).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.models import Company, FinancialFact
from app.services.fact_provenance import (
    METRIC_FORMULAS, METRIC_INPUTS, provenance_for_fact, published_value, source_link,
)
from app.services.facts.fiscal_naming import ANNUAL_FORMS, DRIFT_DAYS
from app.services.trend_analysis.formatting import NOT_MEANINGFUL
from app.services.trend_analysis.source_documents import FilingDates, filing_documents
from app.utils.sec_urls import normalize_accession

# D1 (the founder's, brief WP5a D1): a figure carries its own report's value only where the two differ by more than
# this share of the own value (the restatement census's gap, |shown - own| / |own|). 0.1% keeps the rounding-only
# gaps out (113 of 116 sit at or below it) and shows the small real changes one tap away.
EVIDENCE_TOLERANCE = Decimal("0.001")
# D1: a YoY reads n/m across a change of basis where one year's shown-to-first-reported ratio differs from the other's
# by more than this share (coherence.md section 1.6 item 3). A year without evidence has the ratio 1.
BASIS_TOLERANCE = Decimal("0.01")
# D3: per-share figures keep their evidence but their growth never reads n/m by this rule: after a stock split every
# earlier year is restated at one ratio, so the first year after it would read n/m across no change of what EPS measures.
BASIS_EXEMPT = frozenset({"earnings_per_share", "eps_diluted"})
# D4: a calculated figure's growth reads n/m where one of these inputs changed basis, each read from the figure's
# recorded operand of that concept, else (a calculation stored before operands were recorded) from that concept's own
# figure for the year in the dataset. Empty, calculated growth would keep its number beside its inputs' evidence.
BASIS_INPUTS: Mapping[str, tuple[str, ...]] = METRIC_INPUTS
# Each calculated figure from its inputs in METRIC_INPUTS' order, as facts/derive.py computes it, for the growth its
# inputs' own reports give.
_CALCULATED: Mapping[str, Callable[[float, float], Optional[float]]] = {
    "net_margin": lambda numerator, revenue: numerator / revenue * 100 if revenue else None,
    "operating_margin": lambda numerator, revenue: numerator / revenue * 100 if revenue else None,
    "gross_margin": lambda numerator, revenue: numerator / revenue * 100 if revenue else None,
    "free_cash_flow": lambda cash_flow, capex: cash_flow - abs(capex),
    "working_capital": lambda assets, liabilities: assets - liabilities,
    "current_ratio": lambda assets, liabilities: assets / liabilities if liabilities else None,
}

Cell = tuple[str, str, str, Optional[str]]  # concept, period end, unit, period start (ISO days)


def _key(accession: Any) -> str:
    """An accession as its dashless form where it is one, so two spellings of one filing meet."""
    try:
        return normalize_accession(accession)
    except ValueError:
        return str(accession)


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, date) else (str(value)[:10] if value else None)


def _day(value: Any) -> Optional[str]:
    """A stored filed date as the calendar day the page reads (YYYY-MM-DD), or None: never a timestamp."""
    try:
        return date.fromisoformat(str(value)[:10]).isoformat() if value else None
    except ValueError:
        return None


def _cell(figure: Any) -> Cell:
    get = figure.get if isinstance(figure, Mapping) else lambda name: getattr(figure, name, None)
    return get("concept"), _iso(get("period_end")), get("unit"), _iso(get("period_start"))


def differs(shown: float, own: float) -> bool:
    """D1: whether the two values differ by more than ``EVIDENCE_TOLERANCE`` of the own value, exactly, in Decimal.
    An own value of 0 differs from any other."""
    shown_d, own_d = Decimal(str(shown)), Decimal(str(own))
    if own_d == 0:
        return shown_d != 0
    return abs(shown_d - own_d) / abs(own_d) > EVIDENCE_TOLERANCE


def _year_before(period: str) -> Optional[str]:
    return f"FY{int(period[2:]) - 1}" if period.startswith("FY") and period[2:].isdigit() else None


Figure = Optional[tuple[Any, Optional[dict[str, Any]]]]  # a value and its first_reported, or None where absent


def _ratio(figure: Figure) -> Optional[Decimal]:
    """A value shown over its first-reported value: 1 without evidence, None where the own value is 0 (unbounded)."""
    value, first = figure or (None, None)
    if value is None or not first:
        return Decimal(1)
    own = Decimal(str(first["value"]))
    return Decimal(str(value)) / own if own else None


def basis_changed(now: Optional[Decimal], before: Optional[Decimal]) -> bool:
    """D1: whether two years' ratios (``_ratio``) sit on different bases: unbounded on either side, or apart by more
    than ``BASIS_TOLERANCE``."""
    if now is None or before is None:
        return True
    if before == 0:
        return now != 0
    return abs(now / before - 1) > BASIS_TOLERANCE


def own_period_ends(rows: Iterable[FinancialFact], filings: Mapping[str, FilingDates]) -> dict[str, date]:
    """Each annual filing's own period end, by dashless accession, from the company's stored fiscal-year rows."""
    fiscal = [row for row in rows if row.fiscal_period == "FY"]
    annual = {_key(row.accession) for row in fiscal if row.form in ANNUAL_FORMS}
    annual |= {key for key, filing in filings.items() if filing.form in ANNUAL_FORMS}
    ends: dict[str, date] = {}
    for row in fiscal:
        key = _key(row.accession)
        if row.form in ANNUAL_FORMS or row.form is None and key in annual:
            ends[key] = max(row.period_end, ends.get(key, row.period_end))
    for key, filing in filings.items():
        if key in ends and filing.form in ANNUAL_FORMS and filing.period_end is not None \
                and (filing.period_end - ends[key]).days > DRIFT_DAYS:
            del ends[key]  # The filing's own year is not stored: no stored row of it is its own report.
    return ends


class FirstReports:
    """The own-report rows one annual dataset reads, and the evidence they give its figures."""

    def __init__(self, documents: dict[str, str], dates: Mapping[str, FilingDates], cik: Optional[str],
                 current: Iterable[FinancialFact] = (), history: Iterable[FinancialFact] = ()) -> None:
        self.documents = documents
        self._dates, self._cik = dates, cik
        history = list(history)
        self._own_ends = own_period_ends([*current, *history], dates) if history else {}
        self._cells: dict[Cell, list[FinancialFact]] = {}
        for row in history:
            # A calculated metric's evidence sits on its inputs (item 5); a withheld row is no one's evidence.
            if row.concept not in METRIC_FORMULAS and published_value(row) is not None:
                self._cells.setdefault(_cell(row), []).append(row)

    def _filed(self, accession: Any, stored: Any = None) -> Optional[str]:
        """The day a filing was filed: the value's own record of it, else its filing row's."""
        return _day(stored) or getattr(self._dates.get(_key(accession)), "filed", None)

    def own_report(self, figure: Mapping[str, Any]) -> Optional[FinancialFact]:
        """The stored row of the figure's year's own annual report, at another filing than the figure's, or None."""
        accession = _key(figure.get("accession"))
        owns = [row for row in self._cells.get(_cell(figure), ())
                if _key(row.accession) != accession and self._own_ends.get(_key(row.accession)) == row.period_end]
        return min(owns, key=lambda row: ((row.form or "").endswith("/A"),
                                          self._filed(row.accession, provenance_for_fact(row).get("filed_at")) or "",
                                          row.accession), default=None)

    def evidence(self, figure: Mapping[str, Any], later_filed: Any = None) -> Optional[dict[str, Any]]:
        """The figure's ``first_reported``: its own report's value where that differs from the one shown (D1)."""
        shown = figure.get("value")
        own = self.own_report(figure) if shown is not None else None
        if own is None or not differs(shown, float(own.value)):
            return None
        return {
            "value": float(own.value), "unit": own.unit, "form": own.form, "accession": own.accession,
            "filed_at": self._filed(own.accession, provenance_for_fact(own).get("filed_at")),
            # Under the key the snapshot folds to its accession folder (source_documents.folder_links), so a filing
            # row that lands later moves no snapshot.
            "source_url": source_link(self._cik, own.accession, self.documents),
            "later_filed_at": self._filed(figure.get("accession"), later_filed),
            "disagreement": None,
        }

    def attach(self, points: list[dict[str, Any]]) -> None:
        """Give each reported figure of one series its evidence, before its comparisons copy its provenance."""
        if not self._cells:
            return
        for point in points:
            provenance = point.get("provenance") or {}
            if point.get("value") is not None and provenance.get("method") == "reported":
                first = self.evidence(point, provenance.get("filed_at"))
                if first is not None:
                    point["first_reported"] = first


    def _input(self, operand: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        """A calculated figure's reported input's evidence, as a reported figure's (item 5)."""
        reported = (operand.get("provenance") or {}).get("method") == "reported"
        return self.evidence(operand, operand.get("filed_at")) if reported else None

    def _figures(self, concept: str, point: Mapping[str, Any], points: Mapping[str, Mapping[str, Any]]) -> list[Figure]:
        """What a year's growth rests on: a reported figure itself, a calculated one its inputs (D4)."""
        if concept not in BASIS_INPUTS:
            return [(point.get("value"), point.get("first_reported"))]
        recorded: dict[str, Mapping[str, Any]] = {}
        for operand in (point.get("provenance") or {}).get("inputs") or []:
            recorded.setdefault(operand.get("concept"), operand)
        figures: list[Figure] = []
        for name in BASIS_INPUTS[concept]:
            operand, shown = recorded.get(name), points.get(name, {}).get(point["period"])
            figures.append((operand.get("value"), self._input(operand)) if operand is not None
                           else (shown.get("value"), shown.get("first_reported")) if shown is not None else None)
        return figures

    @staticmethod
    def _as_first_reported(concept: str, point: Mapping[str, Any], figures: list[Figure]) -> Optional[float]:
        """The year's value as its own reports give it: a reported figure's own value, a calculated one recomputed from
        its inputs' own values (the value shown where no input carries evidence)."""
        if concept not in BASIS_INPUTS:
            value, first = figures[0]
            return first["value"] if first else value
        if not any(figure and figure[1] for figure in figures):
            return point.get("value")
        values = [(figure[1]["value"] if figure[1] else figure[0]) if figure else None for figure in figures]
        return None if any(value is None for value in values) else _CALCULATED[concept](*values)

    def basis_rule(self, series_list: list[dict[str, Any]], growth: Callable, pp_delta: Callable) -> list[dict[str, Any]]:
        """Item 3, once every series' growth is attached: a YoY whose two years sit on different bases reads n/m and
        carries the growth their own reports give, computed as the series computes its own (``growth``, or
        ``pp_delta`` for a margin). EPS is exempt (D3); its provenance and checks stand."""
        if not self._cells:
            return series_list
        points = {series["concept"]: {point["period"]: point for point in series["points"]} for series in series_list}
        for series in series_list:
            concept, delta = series["concept"], pp_delta if series.get("percent") else growth
            if concept in BASIS_EXEMPT:
                continue
            for point in series["points"]:
                before = points[concept].get(_year_before(point["period"]) or "")
                if point.get("yoy") is None or before is None:
                    continue
                now_figures, before_figures = self._figures(concept, point, points), self._figures(concept, before, points)
                if any(basis_changed(_ratio(now), _ratio(then)) for now, then in zip(now_figures, before_figures)):
                    point["yoy"] = NOT_MEANINGFUL
                    point["yoy_first_reported"] = delta(self._as_first_reported(concept, point, now_figures),
                                                        self._as_first_reported(concept, before, before_figures))
        return series_list


def read_first_reports(db: Session, company: Company, mode: str, current: list[FinancialFact],
                       shown: Iterable[Optional[FinancialFact]]) -> FirstReports:
    """The dataset's one read of its filing rows (``filing_documents``) and, in an annual run, its one read of the
    company's non-current fiscal-year rows from the earliest period end it shows: an accession's own end is the latest
    year it reports, so a row before that bound is no shown figure's own report and moves no accession's own end
    past one. ``current`` is the dataset's own read of the current rows (``dataset._index_facts``)."""
    shown = [row for row in shown if row is not None]
    history: list[FinancialFact] = []
    if mode == "annual" and shown:
        history = (
            db.query(FinancialFact)
            .filter(
                FinancialFact.company_id == company.id,
                FinancialFact.fiscal_period == "FY",
                FinancialFact.is_latest.is_(False),
                FinancialFact.period_end >= min(row.period_end for row in shown),
            )
            .all()
        )
    documents, dates = filing_documents(db, company.id, [*shown, *history])
    return FirstReports(documents, dates, getattr(company, "cik", None), current, history)
