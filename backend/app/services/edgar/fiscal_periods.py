"""Anchor per-filing fiscal labels to the filing's own fiscal focus, never calendar months or years."""
from datetime import date
from typing import Any, Optional

ANNUAL_FORMS = ("10-K", "20-F", "40-F")
# A 52/53-week calendar drifts a few days from whole quarters and years; transition periods do not.
_DRIFT_DAYS = 18


def _focus_year(fiscal_year: Any) -> Optional[int]:
    """The DEI fiscal-year focus as an int, or None when it is missing or implausible."""
    if isinstance(fiscal_year, str) and fiscal_year.isdigit():
        fiscal_year = int(fiscal_year)
    return fiscal_year if type(fiscal_year) is int and 1900 <= fiscal_year <= 2200 else None


def fiscal_label(end: str, report_end: str, fiscal_year: Any, fiscal_period: Any) -> dict:
    """Derive a point's fiscal label from its distance to a known filing-period anchor.

    DEI fiscal focus describes the filing, not its comparative facts. Translate whole fiscal
    quarters backward from that anchor; allow a 53-week calendar's drift, but leave irregular
    transition periods unknown. This is only used for already-selected discrete-quarter or
    instant facts, never six-/nine-month YTD values.
    """
    fiscal_year = _focus_year(fiscal_year)
    if fiscal_year is None:
        return {}
    if fiscal_period not in ("Q1", "Q2", "Q3", "Q4"):
        return {}
    try:
        days = (date.fromisoformat(report_end) - date.fromisoformat(end)).days
    except (TypeError, ValueError):
        return {}
    quarters = round(days / 91.3125)
    if days < 0 or abs(days - quarters * 91.3125) > _DRIFT_DAYS:
        return {}
    offset = int(fiscal_period[1]) - 1 - quarters
    return {"fiscal_year": fiscal_year + offset // 4, "fiscal_period": f"Q{offset % 4 + 1}"}


def annual_fiscal_label(end: str, report_end: Any, fiscal_year: Any) -> dict:
    """Name an annual report's point by the issuer's fiscal year where its end's calendar year does not.

    A retailer's year ending 1 February 2025 is its fiscal 2024, and a 52-week year ending
    1 January 2023 is fiscal 2022. The DEI focus names the year the filing reports; a comparative
    ends a whole number of fiscal years earlier. The focus must be the anchor's end year or the year
    before, the bound the companyfacts writer applies (``facts/calendar.reported_fiscal_year``), so
    both fact writers name a period alike. Returns {} when the calendar year of the end already
    names the year (the fact normalizer's default, so a calendar-aligned issuer's points keep their
    exact shape) or when the point is not a whole number of years before the anchor.
    """
    fiscal_year = _focus_year(fiscal_year)
    try:
        point, anchor = date.fromisoformat(end), date.fromisoformat(report_end)
    except (TypeError, ValueError):
        return {}
    if fiscal_year not in (anchor.year - 1, anchor.year):
        return {}
    days = (anchor - point).days
    years = round(days / 365.25)
    if days < 0 or abs(days - years * 365.25) > _DRIFT_DAYS or fiscal_year - years == point.year:
        return {}
    return {"fiscal_year": fiscal_year - years, "fiscal_period": "FY"}


def filing_point_label(form: Any, end: str, report_end: Any, fiscal_year: Any, fiscal_period: Any) -> dict:
    """A 10-Q point's fiscal quarter, or an annual report point's fiscal year, from the filing's focus."""
    form = str(form or "").removesuffix("/A")
    if form == "10-Q":
        return fiscal_label(end, report_end, fiscal_year, fiscal_period)
    if form in ANNUAL_FORMS:
        return annual_fiscal_label(end, report_end, fiscal_year)
    return {}
