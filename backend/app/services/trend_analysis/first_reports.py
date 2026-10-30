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

A finding that signals a tagging error rather than a change of basis (item 4), an exact sign flip or an exact factor of
1,000ⁿ between the two values (``disagreement``), also marks the figure with the existing ``source_conflict`` reason (D2
option A: no new words, no data notes version), so its comparisons and window figures inherit the note as they inherit
any; the mark rests only on an own row that passed its checks (D6), and growth as first reported across a finding on
either year is "nm", since one of the two readings rests on the slip.

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
# Item 4, D2 option A: a finding marks the figure with the reason the data notes already word ("The company's filings
# report different values. We show the most recent filing's value.").
SOURCE_CONFLICT = "source_conflict"
# D2: a per-share figure is not sign-tested, since a small EPS can change sign in a legitimate recast (GE's FY2022
# diluted EPS, -0.05 in its own report, 0.05 later); its scale still is.
SIGN_TEST_EXEMPT = frozenset({"earnings_per_share", "eps_diluted"})
SCALE_STEPS = (1, 2, 3)  # A factor of 1,000ⁿ for these n, either way.
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


def disagreement(concept: str, shown: float, own: float) -> Optional[str]:
    """What an exact comparison of the two values finds (item 4), in Decimal so a factor that floats round still meets:
    "opposite_sign" where the value shown is the own value negated (not for a per-share figure, D2), "scale" where one
    is the other times 1,000ⁿ (``SCALE_STEPS``), a positive factor, so the two share a sign; else None."""
    shown_d, own_d = Decimal(str(shown)), Decimal(str(own))
    if shown_d == 0 or own_d == 0:
        return None
    if shown_d == -own_d:
        return None if concept in SIGN_TEST_EXEMPT else "opposite_sign"
    if any(shown_d == own_d * 1000 ** n or own_d == shown_d * 1000 ** n for n in SCALE_STEPS):
        return "scale"
    return None


def _has_finding(value: Optional[Mapping[str, Any]]) -> bool:
    """Whether a sign or scale finding sits in a figure's evidence: its own ``first_reported``, or an input's in its
    provenance, at any depth (item 5's evidence)."""
    if not value:
        return False
    if (value.get("first_reported") or {}).get("disagreement"):
        return True
    return any(_has_finding(operand) for operand in (value.get("provenance") or {}).get("inputs") or [])


def grounds_a_mark(own: FinancialFact) -> bool:
    """D6: a finding marks the figure only where the own report's row passed its checks, so a letter never rests on an
    unchecked value; any row the publication policy shows still gives evidence."""
    return provenance_for_fact(own)["validation"] == "passed"


def _marked(provenance: Mapping[str, Any]) -> dict[str, Any]:
    """A copy of a figure's provenance that questions it (item 4): needs review, for ``source_conflict``."""
    return {**provenance, "validation": "needs_review",
            "reasons": list(dict.fromkeys([*provenance.get("reasons", []), SOURCE_CONFLICT]))}


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

    def _first_reported(self, figure: Mapping[str, Any], own: Optional[FinancialFact],
                        later_filed: Any) -> Optional[dict[str, Any]]:
        shown = figure.get("value")
        if own is None or shown is None or not differs(shown, float(own.value)):
            return None
        return {
            "value": float(own.value), "unit": own.unit, "form": own.form, "accession": own.accession,
            "filed_at": self._filed(own.accession, provenance_for_fact(own).get("filed_at")),
            # Under the key the snapshot folds to its accession folder (source_documents.folder_links), so a filing
            # row that lands later moves no snapshot.
            "source_url": source_link(self._cik, own.accession, self.documents),
            "later_filed_at": self._filed(figure.get("accession"), later_filed),
            "disagreement": disagreement(figure.get("concept"), shown, own.value),
        }

    def evidence(self, figure: Mapping[str, Any], later_filed: Any = None) -> Optional[dict[str, Any]]:
        """The figure's ``first_reported``: its own report's value where that differs from the one shown (D1)."""
        return self._first_reported(figure, self.own_report(figure), later_filed)

    def _with_inputs(self, provenance: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        """A copy of a calculation's record whose reported inputs, at any depth, carry their own evidence as a reported
        figure does (item 5), or None where none does. The stored record is never written."""
        inputs, changed = [], False
        for operand in provenance.get("inputs") or []:
            first, nested = self._input(operand), self._with_inputs(operand.get("provenance") or {})
            if first is not None or nested is not None:
                operand = {**operand, **({"first_reported": first} if first is not None else {}),
                           **({"provenance": nested} if nested is not None else {})}
                changed = True
            inputs.append(operand)
        return {**provenance, "inputs": inputs} if changed else None

    def attach(self, points: list[dict[str, Any]]) -> None:
        """Give each figure of one series its evidence, a reported one its own and a calculated one its inputs' (item
        5), and mark a reported one where the two filings disagree in a way that signals a tagging error (item 4, D6),
        before its comparisons copy its provenance."""
        if not self._cells:
            return
        for point in points:
            provenance = point.get("provenance") or {}
            if point.get("value") is None:
                continue
            with_inputs = self._with_inputs(provenance)
            if with_inputs is not None:
                point["provenance"] = provenance = with_inputs
            if provenance.get("method") != "reported":
                continue
            own = self.own_report(point)
            first = self._first_reported(point, own, provenance.get("filed_at"))
            if first is None:
                continue
            point["first_reported"] = first
            if first["disagreement"] and grounds_a_mark(own):
                point["provenance"], point["reconciled"] = _marked(provenance), False


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
            figures.append((operand.get("value"), operand.get("first_reported")) if operand is not None
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
                    # Across a finding in either year's evidence (item 4), one of the two readings rests on the slip:
                    # n/m, never a number or null.
                    found = _has_finding(point) or _has_finding(before) or any(
                        figure and figure[1] and figure[1]["disagreement"] for figure in (*now_figures, *before_figures))
                    point["yoy_first_reported"] = NOT_MEANINGFUL if found else delta(
                        self._as_first_reported(concept, point, now_figures),
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
