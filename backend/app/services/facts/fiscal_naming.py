"""Name a period's fiscal year from annual reports, by the rules both fact writers share.

The companyfacts writer (``facts/calendar``, ``facts/companyfacts``) and the per-filing labeller
(``edgar/fiscal_periods``) must give a period one fiscal year, since the fact identity leaves it out
(``lessons/sec-fact-writers-name-a-period-alike.md``). Both count whole fiscal years back from a period
whose year is known (``years_back``), and both trust a late or lone annual report's own focus only for
the year its period ends in or mostly lies in (``focus_years``). It also holds the form rules: the annual
reports (``ANNUAL_FORMS``), and what the companyfacts collector, the backfill's cross-check and the per-filing
fallback never take: a proxy's or information statement's figures (``is_proxy_form``), and a quarterly report's
year that holds only part of one (``without_partial_years``).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})
QUARTERLY_FORMS = frozenset({"10-Q", "10-Q/A", "10-QT", "10-QT/A"})
# A 52/53-week calendar drifts a few days from whole quarters and years; transition periods do not.
DRIFT_DAYS = 18

# Schedule 14A and 14C submissions: a letter prefix (PRE, PREM, PRER, PREC, PREN, PRRN, DEF, DEFA,
# DEFM, DEFR, DEFC, DEFN, DFAN, DFRN, PX), an optional space, then 14A or 14C, an optional suffix
# (PX14A6G, PX14A6N) and /A. No periodic report or registration statement is named so: those start
# with a digit (10-K, 20-F, 8-K) or a letter and a hyphen (S-1, F-4, N-14), and SC 14D9 and SC 14N
# are other schedules.
_PROXY_FORM = re.compile(r"[A-Z]+ ?14[AC][0-9A-Z]*(?:/A)?")


def is_proxy_form(form: Any) -> bool:
    """A proxy or information statement (DEF 14A, DEFA14A, PRE 14C, ...), never a financial report.

    Since 2023 a proxy's pay-versus-performance table tags ``NetIncomeLoss`` (and sometimes other
    statement lines) for five fiscal years. Companyfacts lists those items under the proxy's own form,
    filed after the reports it quotes, so a latest-filed rule would take the proxy's figure, which can
    be rounded, on another basis or at the wrong scale (FedEx's is in dollars, not millions). Every
    other form stays admitted: 10-K, 10-Q, 20-F, 40-F, 6-K, an 8-K recast, S-1, S-4, 10-KT and their
    amendments, including a 10-K/A that adds Part III late and carries the same table.
    """
    return isinstance(form, str) and _PROXY_FORM.fullmatch(" ".join(form.split()).upper()) is not None


def without_partial_years(items: list) -> list:
    """One tag's companyfacts items in one unit, less each quarterly report's year that holds part of one (E291).

    A 10-Q can tag a prior-year comparative with a full-year span: CBAN's and FIX's Q1 2026 10-Qs tag Q1 2025's
    figures as 2025-01-01 to 2025-12-31, and HP's tagged a first half so. Filed after the 10-K, such an item would
    win the year wherever the latest filed item wins. So a quarterly report's (``QUARTERLY_FORMS``) item spanning a
    year is dropped where its value, not zero, equals that of a shorter item from the same start (a quarter, or six
    or nine months to date), in any filing, under the same tag: a year whose quarter sits under a sibling tag of its
    concept is kept (OSPN's Q1 2018 10-Q; E292). Equals exactly: a real year can sit near its nine months (Estee
    Lauder's FY2023 operating income, 0.3% below), and where the rest of a year nets to exactly nothing (BMY's
    FY2011 investing cash flow) the annual report's own item still gives the year. A 10-Q's recast of a prior year
    (Macy's FY2021) matches no shorter item and stays, as does every annual report's item and every zero. Another
    filing's item only exposes the mis-tag: a reader still reads each value from the item it read it from before.
    Sized on the collector's duration concepts, where it drops no real year on 696 cached payloads; across every tag
    a rate, a count or a one-off payment can equal its quarter (2,156 of the 2,664 items it drops there), so an
    all-tag reader such as the restatement census's evidence index keeps every item.
    """
    from app.services.facts.concepts import _classify_duration, _parse_date  # call time, as currency's admission

    def span(item: Any) -> tuple[Any, Any, Any]:  # (span class, start, value) of a numeric duration item
        value = item.get("val") if isinstance(item, dict) else None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None, None, None
        start, end = _parse_date(item.get("start")), _parse_date(item.get("end"))
        return (_classify_duration(start, end), start, value) if start and end else (None, None, None)

    spans = [span(item) for item in items]
    parts = {(start, value) for klass, start, value in spans if klass in ("Q", "YTD6", "YTD9")}
    return [item for item, (klass, start, value) in zip(items, spans)
            if not (klass == "FY" and value != 0 and (start, value) in parts
                    and str(item.get("form") or "").upper() in QUARTERLY_FORMS)]


def focus_years(end: date) -> tuple[int, int]:
    """The years an annual report's own focus may name a year ending on ``end`` by: the calendar year it
    ends in, or the one its midpoint falls in (a year ending by early July), so a lagging focus on a
    December year is not trusted."""
    return end.year, (end - timedelta(days=183)).year


def years_back(point: date, anchor: date) -> int | None:
    """Whole fiscal years from ``point`` to ``anchor``, allowing a 52/53-week calendar's drift; None for a
    point after the anchor or one a whole number of years does not reach (a transition period)."""
    days = (anchor - point).days
    years = round(days / 365.25)
    return years if days >= 0 and abs(days - years * 365.25) <= DRIFT_DAYS else None


def year_ending_on(end: date, labels: dict[date, int]) -> int | None:
    """The fiscal year that ends on ``end``, a year-end balance outside every fiscal-year window: whole
    years before the next window's year (``labels``, by window end), as the per-filing writer counts back
    from its report. None when no window follows or ``end`` is not whole years before it."""
    anchor = min((window_end for window_end in labels if window_end > end), default=None)
    years = None if anchor is None else years_back(end, anchor)
    return None if years is None else labels[anchor] - years


def own_period_ends(duration_values: dict) -> dict[str, date]:
    """Each annual report's own period end, by accession: the latest fiscal year it reports."""
    ends: dict[str, date] = {}
    for values in duration_values.values():
        for (end, kind), record in values.items():
            if kind != "FY":
                continue
            for candidate in record.get("candidates") or [record]:
                accession = candidate.get("accession")
                if candidate.get("form") in ANNUAL_FORMS and accession:
                    ends[accession] = max(end, ends.get(accession, end))
    return ends


def reported_fiscal_year(record: dict, end: date, own_ends: dict[str, date] | None = None) -> int | None:
    """Only a timely original annual report establishes its own fiscal-year label. Given each report's own
    period end (``own_ends``), a late report establishes its own period's label too, by a year
    ``focus_years`` trusts, as the per-filing writer names a late report's years from its focus."""
    late = own_ends is not None
    trusted = focus_years(end) if late else (end.year - 1, end.year)
    evidence = []
    for candidate in record.get("candidates") or [record]:
        fy = candidate.get("fy")
        if (candidate.get("form") not in ANNUAL_FORMS or candidate.get("fp") != "FY"
                or not isinstance(fy, int) or isinstance(fy, bool) or fy not in trusted
                or candidate.get("period_end") != end
                or candidate.get("period_start") != record.get("period_start")
                or late and own_ends.get(candidate.get("accession")) != end):
            continue
        try:
            filed = date.fromisoformat(str(candidate.get("filed") or "")[:10])
        except ValueError:
            continue
        days = (filed - end).days
        if 0 <= days and (late or days <= 180):
            evidence.append((filed, fy))
    if not evidence:
        return None
    earliest = min(item[0] for item in evidence)
    years = {fy for filed, fy in evidence if filed == earliest}
    return next(iter(years)) if len(years) == 1 else None
