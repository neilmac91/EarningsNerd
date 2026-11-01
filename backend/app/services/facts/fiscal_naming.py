"""Name a period's fiscal year from annual reports, by the rules both fact writers share.

The companyfacts writer (``facts/calendar``, ``facts/companyfacts``) and the per-filing labeller
(``edgar/fiscal_periods``) must give a period one fiscal year, since the fact identity leaves it out
(``lessons/sec-fact-writers-name-a-period-alike.md``). Both count whole fiscal years back from a period
whose year is known (``years_back``), and both trust a late or lone annual report's own focus only for
the year its period ends in or mostly lies in (``focus_years``). It also holds the form rules: the annual
reports (``ANNUAL_FORMS``), and the proxy and information statements (``is_proxy_form``) whose figures the
companyfacts collector and the backfill's cross-check never take.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})
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
