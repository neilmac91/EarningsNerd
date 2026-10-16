"""Reporting currency of a companyfacts series, and the convenience rows it supersedes.

A foreign US-GAAP filer (the Alibaba shape) tags every period in its reporting currency and, in
each filing, its own period again as a USD convenience translation at that period's rate.
Companyfacts therefore holds a CNY list and a USD list for the same line. A history built from
the USD list mixes exchange-rate moves into growth, so each concept is read from its reporting
currency, picked by the per-filing extractor's own rule.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def is_amount_unit(unit: Any) -> bool:
    """An ISO-4217 currency amount ("USD", "CNY"): the only additive unit. Per-share
    ("CNY/shares"), share-count and ratio ("pure") units never sum into a quarter."""
    return isinstance(unit, str) and len(unit) == 3 and unit.isalpha() and unit.isupper()


def series_unit(usgaap: dict, tags: tuple[str, ...], default_unit: str) -> str:
    """The unit list one concept is read from: its reporting currency across its candidate tags.

    ``default_unit`` is the concept's USD unit ("USD" or "USD/shares"); only lists of the same
    shape compete. Only a currency present at the latest period-end can win: that is a full
    history's analogue of the filing's own period, so a filer that switched currency is read in
    its current one. Among those, the pick is ``_reporting_currency``'s: the most distinct
    period-ends, then a non-USD code. A domestic filer keeps ``default_unit`` unless a foreign
    list at its latest period-end covers as many period-ends (the per-filing tie rule).
    """
    from app.services.edgar.instance.core import _reporting_currency  # lazy: facts imports stay EDGAR-free

    suffix = "/shares" if default_unit.endswith("/shares") else ""
    candidates: list[tuple[str, float, str, float]] = []
    for tag in tags:
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        for key, items in units.items() if isinstance(units, dict) else ():
            currency = key.removesuffix(suffix)
            if key != currency + suffix or not is_amount_unit(currency) or not isinstance(items, list):
                continue
            candidates.extend((str(item["end"])[:10], 0.0, currency, 0.0)
                              for item in items if isinstance(item, dict) and item.get("end"))
    if not candidates:
        return default_unit
    latest = max(end for end, *_ in candidates)
    current = {currency for end, _value, currency, _decimals in candidates if end == latest}
    return f"{_reporting_currency([c for c in candidates if c[2] in current], latest)}{suffix}"


def demote_convenience_rows(db: Session, facts: list[dict[str, Any]]) -> int:
    """Demote the current USD rows that native-currency facts supersede; never delete one.

    ``is_latest`` is kept per unit, so a CNY row does not demote the USD row already current for
    the same concept, period end and fiscal period, and both currencies would stay current. Any
    such exact USD twin (``USD`` or ``USD/shares``) is demoted, whatever its source or filing:
    ``series_unit`` already chose the series currency, and a current USD row beside the native one
    would put two currencies in one series. Rows at any other key are left alone.
    """
    from app.models import FinancialFact  # lazy: the pure normalizers import this module

    twins: dict[tuple[Any, ...], str] = {}
    for fact in facts:
        currency = fact["unit"].partition("/")[0]
        if is_amount_unit(currency) and currency != "USD":
            twins[(fact["concept"], fact["period_end"], fact["fiscal_period"])] = (
                "USD" + fact["unit"][len(currency):]
            )
    if not twins:
        return 0
    rows = db.query(FinancialFact).filter(
        FinancialFact.company_id == facts[0]["company_id"],
        FinancialFact.concept.in_({concept for concept, _end, _fp in twins}),
        FinancialFact.unit.in_(set(twins.values())),
        FinancialFact.is_latest.is_(True),
    ).all()
    demoted = 0
    for row in rows:
        if twins.get((row.concept, row.period_end, row.fiscal_period)) == row.unit:
            row.is_latest = False
            demoted += 1
    return demoted
