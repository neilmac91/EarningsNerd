"""Anchor discrete-quarter labels to the filing's own fiscal focus, never calendar months."""
from datetime import date
from typing import Any


def fiscal_label(end: str, report_end: str, fiscal_year: Any, fiscal_period: Any) -> dict:
    """Derive a point's fiscal label from its distance to a known filing-period anchor.

    DEI fiscal focus describes the filing, not its comparative facts. Translate whole fiscal
    quarters backward from that anchor; allow a 53-week calendar's drift, but leave irregular
    transition periods unknown. This is only used for already-selected discrete-quarter or
    instant facts, never six-/nine-month YTD values.
    """
    if isinstance(fiscal_year, str) and fiscal_year.isdigit():
        fiscal_year = int(fiscal_year)
    if type(fiscal_year) is not int or not 1900 <= fiscal_year <= 2200:
        return {}
    if fiscal_period not in ("Q1", "Q2", "Q3", "Q4"):
        return {}
    try:
        days = (date.fromisoformat(report_end) - date.fromisoformat(end)).days
    except (TypeError, ValueError):
        return {}
    quarters = round(days / 91.3125)
    if days < 0 or abs(days - quarters * 91.3125) > 18:
        return {}
    offset = int(fiscal_period[1]) - 1 - quarters
    return {"fiscal_year": fiscal_year + offset // 4, "fiscal_period": f"Q{offset % 4 + 1}"}
