"""Reporting currency of a companyfacts series, and the convenience rows it supersedes.

A foreign US-GAAP filer (the Alibaba shape) tags every period in its reporting currency and, in
each filing, its own period again as a USD convenience translation at that period's rate.
Companyfacts therefore holds a CNY list and a USD list for the same line. A history built from
the USD list mixes exchange-rate moves into growth, so a concept whose USD list is such a
translation is read from its reporting currency instead.
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
    shape compete. A foreign list is read only when the USD list is its convenience translation:
    every USD period-end is also one of its period-ends. Among such lists the per-filing
    extractor's ``_reporting_currency`` picks (the most distinct period-ends, then the latest).
    Any other shape keeps ``default_unit``: a stray foreign fact, whatever its date, or a currency
    switch in either direction. There some USD period-end has no native twin, so a native read
    would leave the USD row an earlier sync stored there current beside the native series.
    """
    from app.services.edgar.instance.core import _reporting_currency  # lazy: facts imports stay EDGAR-free

    suffix = "/shares" if default_unit.endswith("/shares") else ""
    ends: dict[str, set[str]] = {}
    for tag in tags:
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        for key, items in units.items() if isinstance(units, dict) else ():
            currency = key.removesuffix(suffix)
            if key != currency + suffix or not is_amount_unit(currency) or not isinstance(items, list):
                continue
            ends.setdefault(currency, set()).update(
                str(item["end"])[:10] for item in items if isinstance(item, dict) and item.get("end"))
    usd = ends.pop("USD", set())
    native = [(end, 0.0, currency, 0.0) for currency, periods in ends.items() if usd <= periods
              for end in periods]
    if not native:
        return default_unit
    return f"{_reporting_currency(native, max(native)[0])}{suffix}"


def _operand_unit(provenance: Any) -> Any:
    """The one unit a calculation's recorded operands share, or None when absent or mixed."""
    inputs = provenance.get("inputs") if isinstance(provenance, dict) else None
    units = {operand.get("unit") for operand in inputs or () if isinstance(operand, dict)}
    return units.pop() if len(units) == 1 else None


def _usd_derived(row: Any) -> bool:
    """A stored ratio computed from USD operands. Rows from before operands were recorded
    (2026-10-10) have no provenance; a derived one with no filing owner came from companyfacts,
    which then read only the USD lists."""
    if row.provenance is None:
        return row.source == "derived" and row.filing_id is None
    return _operand_unit(row.provenance) == "USD"


def demote_convenience_rows(db: Session, facts: list[dict[str, Any]]) -> int:
    """Demote the current rows that native-currency facts supersede; never delete or rewrite one.

    ``is_latest`` is kept per unit, so a CNY row does not demote the USD row already current for
    the same concept, period end and fiscal period, and both currencies would stay current. Any
    such exact USD twin (``USD`` or ``USD/shares``) is demoted, whatever its source or filing:
    ``series_unit`` already chose the series currency, and a current USD row beside the native one
    would put two currencies in one series. A ratio (``pure``) keeps its unit across currencies, so
    the upsert's filing-date rule can keep one computed from USD operands (``_usd_derived``) current
    and store the native calculation behind it: that row is demoted and the batch's own native
    calculation promoted. A ratio stored under the native calculation's own identity is skipped by
    the upsert and left as it is; the journaled repair recomputes it. Rows at any other key are
    left alone.
    """
    from app.models import FinancialFact  # lazy: the pure normalizers import this module

    twins: dict[tuple[Any, ...], str] = {}
    ratios: dict[tuple[Any, ...], tuple[str, str]] = {}  # key -> native accession and operand unit
    for fact in facts:
        key = (fact["concept"], fact["period_end"], fact["fiscal_period"])
        currency = fact["unit"].partition("/")[0]
        if is_amount_unit(currency) and currency != "USD":
            twins[key] = "USD" + fact["unit"][len(currency):]
        operands = _operand_unit(fact.get("provenance"))
        if fact["unit"] == "pure" and is_amount_unit(operands) and operands != "USD":
            ratios[key] = (fact["accession"], operands)
    if not twins and not ratios:
        return 0
    company_id = facts[0]["company_id"]
    rows = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id,
        FinancialFact.concept.in_({concept for concept, _end, _fp in (*twins, *ratios)}),
        FinancialFact.unit.in_({*twins.values(), "pure"}),
    ).all()
    # The upsert's own rows are still pending (no autoflush): a native ratio it stored may be one.
    rows += [obj for obj in db.new if isinstance(obj, FinancialFact) and obj.company_id == company_id]
    demoted = 0
    ratio_rows: dict[tuple[Any, ...], list[Any]] = {}
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        if row.is_latest and twins.get(key) == row.unit:
            row.is_latest = False
            demoted += 1
        elif row.unit == "pure" and key in ratios:
            ratio_rows.setdefault(key, []).append(row)
    for key, group in ratio_rows.items():
        native = next((row for row in group
                       if (row.accession, _operand_unit(row.provenance)) == ratios[key]), None)
        stale = [row for row in group if row.is_latest and _usd_derived(row)]
        if native is None or not stale:
            continue
        for row in stale:
            row.is_latest = False
        native.is_latest = True
        demoted += len(stale)
    return demoted
