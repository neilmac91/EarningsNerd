"""Anchor per-filing fiscal labels to the filing's own fiscal focus, never to calendar months or years; where
no focus is trusted the labellers add no label and the fact normalizer keeps the calendar year of the end."""
from datetime import date
from typing import Any, Optional

from app.services.facts.fiscal_naming import ANNUAL_FORMS, DRIFT_DAYS as _DRIFT_DAYS, focus_years, years_back


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


def annual_fiscal_label(end: str, report_end: Any, fiscal_year: Any, fiscal_period: Any) -> dict:
    """Name an annual report's point by the issuer's fiscal year where its end's calendar year does not.

    A retailer's year ending 1 February 2025 is its fiscal 2024, and a 52-week year ending
    1 January 2023 is fiscal 2022. The DEI focus names the year the filing reports; a comparative
    ends a whole number of fiscal years earlier (``facts/fiscal_naming.years_back``). Like the
    companyfacts writer (``facts/fiscal_naming.reported_fiscal_year``) this trusts only an annual
    report's FY focus that names the anchor's end year or the year before; it narrows the year before
    to a year that mostly lies in it (``facts/fiscal_naming.focus_years``: one ending by early July),
    so a lagging focus on a December year keeps the default. That writer names a year chain that no
    timely report names by its late reports' own focus under the same narrowing, so a late report is
    named alike. Unlike that writer this sees one filing, so it cannot outvote an outlier focus across
    the years. The per-filing writer makes up for that where companyfacts already stores a trusted
    year for one of the report's period ends: it moves the filing's annual labels onto that year chain
    (``facts/fiscal_evidence.adopt_trusted_fiscal_years``). Before the first companyfacts sync it
    cannot, so a year named by its end under a lagging focus (Salesforce's fiscal 2026, ended
    31 January 2026, focus 2025) keeps the year before until the stored-row relabel (#1372) moves the
    filing by the one offset companyfacts names (``lessons/sec-fact-writers-name-a-period-alike.md``).
    Returns {} when the calendar year of the end already names the year (the fact normalizer's
    default, so a calendar-aligned issuer's points keep their exact shape), when the focus is not
    trusted, or when the point is not a whole number of years before the anchor.
    """
    fiscal_year = _focus_year(fiscal_year)
    try:
        point, anchor = date.fromisoformat(end), date.fromisoformat(report_end)
    except (TypeError, ValueError):
        return {}
    if fiscal_period != "FY" or fiscal_year not in focus_years(anchor):
        return {}
    years = years_back(point, anchor)
    if years is None or fiscal_year - years == point.year:
        return {}
    return {"fiscal_year": fiscal_year - years, "fiscal_period": "FY"}


def filing_point_label(form: Any, end: str, report_end: Any, fiscal_year: Any, fiscal_period: Any) -> dict:
    """A 10-Q point's fiscal quarter, or an annual report point's fiscal year, from the filing's focus."""
    form = str(form or "")
    if form.removesuffix("/A") == "10-Q":
        return fiscal_label(end, report_end, fiscal_year, fiscal_period)
    if form in ANNUAL_FORMS:
        return annual_fiscal_label(end, report_end, fiscal_year, fiscal_period)
    return {}
