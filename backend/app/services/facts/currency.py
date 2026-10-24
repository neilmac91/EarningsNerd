"""Reporting currency of a companyfacts series, and the rows in another currency it supersedes.

A foreign US-GAAP filer (the Alibaba shape) tags every period in its reporting currency and, in
each filing, its own period again as a USD convenience translation at that period's rate.
Companyfacts therefore holds a CNY list and a USD list for the same line. A history built from
the USD list mixes exchange-rate moves into growth. The currency is therefore picked per filing
(``filing_currencies``): each filing is read only in its own currency, and the series takes the
currency of its latest annual report, so a filer that changed its reporting currency is read in
the new one and a stray item never flips the series.

The currency ranking (``_reporting_currency``) is defined here, not in the per-filing extractor
that shares it (``edgar/instance/core.py`` re-exports it), so the pure normalizers that import
this module load no Settings, ORM or EDGAR code, at import or at call time. Only
``demote_convenience_rows``, which the session-owning ingest calls, imports the ORM. The
collector's item admission (``admitted_items``) lives here too, so the per-filing pick counts
exactly the periods ``companyfacts`` keeps.
"""
from __future__ import annotations

import math
from datetime import date
from typing import TYPE_CHECKING, Any, Iterator, Mapping

from app.services.facts.fiscal_naming import ANNUAL_FORMS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def is_amount_unit(unit: Any) -> bool:
    """An ISO-4217 currency amount ("USD", "CNY"): the only additive unit. Per-share
    ("CNY/shares"), share-count and ratio ("pure") units never sum into a quarter."""
    return isinstance(unit, str) and len(unit) == 3 and unit.isalpha() and unit.isupper()


def _reporting_currency(
    candidates: list[tuple[str, float, str | None, float]],
    period_of_report: str,
) -> str | None:
    """Pick the issuer's reporting currency from candidate facts for one concept.

    Foreign filers (e.g. Alibaba) tag the SAME line in BOTH their reporting currency (all periods)
    AND a USD convenience translation (usually only the latest period). The reporting currency is
    the one covering the most distinct period-ends; ties prefer the currency present at the filing's
    own period_of_report, then alphabetical for determinism. Returns None when no fact carries a
    currency (unit tests, per-share concepts), which disables currency filtering.
    """
    ends_by_ccy: dict[str | None, set] = {}
    for cand in candidates:  # candidates carry (end, value, ccy[, decimals]); only end + ccy are used
        ends_by_ccy.setdefault(cand[2], set()).add(cand[0])
    real = {c: ends for c, ends in ends_by_ccy.items() if c}
    if not real:
        return None
    # Rank by: most distinct period-ends (the native currency spans all presented years; a USD
    # convenience translation is usually only the latest year), then presence at the filing's own
    # period, then prefer a NON-USD code (USD is the convenience-translation convention, so on a tie
    # the native currency wins), then alphabetical for determinism.
    return max(
        real.items(),
        key=lambda item: (
            len(item[1]),
            period_of_report in item[1],
            item[0] != "USD",
            item[0],
        ),
    )[0]


def admitted_items(items: list, *, instant: bool) -> Iterator[tuple[tuple[date, str], date | None, float, dict]]:
    """Each companyfacts item the collector keeps, as ``((end, klass), start, value, item)``.

    A kept item has a finite numeric ``val`` and a parseable ``end``. A duration also needs a
    parseable ``start``, and its span sets klass ("FY", "Q", "YTD6" or "YTD9"; any other span is
    dropped); an instant's klass is "I". ``filing_currencies`` counts each filing's items on these
    same keys, so a filing never takes a currency from items that the collector then drops.
    """
    # Call time: concepts imports quarterly, which imports this module.
    from app.services.facts.concepts import _classify_duration, _parse_date

    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("val")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            continue
        end = _parse_date(item.get("end"))
        if end is None:
            continue
        start: date | None = None
        if instant:
            klass = "I"
        else:
            start = _parse_date(item.get("start"))
            if start is None:
                continue
            klass = _classify_duration(start, end)
            if klass is None:
                continue
        yield (end, klass), start, value, item


def filing_currencies(
    usgaap: dict, duration_tags: Mapping[str, tuple[str, ...]], instant_tags: Mapping[str, tuple[str, ...]]
) -> tuple[str, frozenset[Any]]:
    """The series currency, and the accessions whose own facts are in another currency.

    ``duration_tags`` and ``instant_tags`` map each concept to its candidate tags (the companyfacts
    registries). A filing's (accession's) own currency is the one that tags more of its kept amount
    items than any other, each item counted once per tag, period end and span (``admitted_items``)
    across the amount lists; per-share lists do not vote. A tie leaves the filing undetermined,
    and its items are read in whatever currency the series takes. ``_reporting_currency``'s rule
    is not reused here: it counts period-ends and breaks a tie toward the non-USD code, so one
    stray EUR fact at a USD 10-K's own period-end would make that 10-K EUR. The series currency is
    the deciding filing's: the latest annual report whose currency spans two period-ends (it
    presents comparatives), else the latest annual report, else the latest other filing likewise;
    with no determined filing it is the domestic default, USD. The collector never reads a filing
    whose own currency is another: there its items in the series currency are convenience
    translations. So a switcher's series holds only the periods its filings in the new currency
    present, and a stray item (a one-period amendment, a later quarterly report) never flips it.
    """
    votes: dict[Any, dict[str, set[tuple[str, date, str]]]] = {}
    stamps: dict[Any, tuple[bool, str]] = {}  # accession -> (an annual report, filed)
    tagged = [*((tag, False) for tags in duration_tags.values() for tag in tags),
              *((tag, True) for tags in instant_tags.values() for tag in tags)]
    for tag, instant in tagged:
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        for unit, items in units.items() if isinstance(units, dict) else ():
            if not is_amount_unit(unit) or not isinstance(items, list):
                continue
            for (end, klass), _start, _value, item in admitted_items(items, instant=instant):
                accession = item.get("accn")
                votes.setdefault(accession, {}).setdefault(unit, set()).add((tag, end, klass))
                stamp = (item.get("form") in ANNUAL_FORMS, str(item.get("filed") or ""))
                stamps[accession] = max(stamps.get(accession, stamp), stamp)
    own: dict[Any, tuple[str, int]] = {}  # accession -> its currency, and the period-ends it spans
    for accession, by_unit in votes.items():
        ranked = sorted(by_unit.items(), key=lambda pair: len(pair[1]), reverse=True)
        if len(ranked) == 1 or len(ranked[0][1]) > len(ranked[1][1]):
            currency, kept = ranked[0]
            own[accession] = (currency, len({end for _tag, end, _klass in kept}))
    deciding = max(((stamps[accession][0], ends >= 2, stamps[accession][1], currency)
                    for accession, (currency, ends) in own.items()), default=None)
    series = deciding[-1] if deciding else "USD"
    return series, frozenset(accession for accession, (currency, _ends) in own.items() if currency != series)


def _operand_unit(provenance: Any) -> Any:
    """The one unit a calculation's recorded operands share, or None when absent or mixed."""
    inputs = provenance.get("inputs") if isinstance(provenance, dict) else None
    units = {operand.get("unit") for operand in inputs or () if isinstance(operand, dict)}
    return units.pop() if len(units) == 1 else None


def _other_derived(row: Any, currency: str) -> bool:
    """A stored ratio computed from operands in another currency than ``currency``. Rows from
    before operands were recorded (2026-10-10) have no provenance; a derived one with no filing
    owner came from companyfacts, which then read only the USD lists."""
    if row.provenance is None:
        return currency != "USD" and row.source == "derived" and row.filing_id is None
    operands = _operand_unit(row.provenance)
    return is_amount_unit(operands) and operands != currency


def demote_convenience_rows(db: Session, facts: list[dict[str, Any]]) -> int:
    """Demote the current rows in another currency that a companyfacts batch supersedes; never
    delete or rewrite one.

    The batch is read in one series currency (``filing_currencies``), which its amount units
    carry. ``is_latest`` is kept per unit, so the batch's rows leave a current row in another
    currency current beside them, and the series would hold two currencies. Every current row of
    a batch concept whose unit is another currency amount or per-share unit is therefore demoted,
    at any key with a fiscal period, whatever its source or filing: a convenience translation, or
    a period from before a currency switch that the new currency's filings do not present. This
    runs in both directions, so a USD series demotes a current row in another currency too. Rows
    with no fiscal period (legacy NULL-period twins) and other concepts are left alone. A ratio
    (``pure``) keeps its unit across currencies, so the upsert's filing-date rule can keep one
    computed from other-currency operands (``_other_derived``) current and store the batch's
    calculation behind it: where the batch has its own calculation at that key, the stale row is
    demoted and the batch's promoted. A ratio stored under the batch calculation's own identity is
    skipped by the upsert and left as it is; the journaled repair recomputes it.
    """
    from app.models import FinancialFact  # lazy: the pure normalizers import this module

    currencies = (fact["unit"].partition("/")[0] for fact in facts)
    currency = next((unit for unit in currencies if is_amount_unit(unit)), None)
    if currency is None:
        return 0
    ratios: dict[tuple[Any, ...], tuple[str, str]] = {}  # key -> the batch's accession and operand unit
    for fact in facts:
        if fact["unit"] == "pure" and _operand_unit(fact.get("provenance")) == currency:
            key = (fact["concept"], fact["period_end"], fact["fiscal_period"])
            ratios[key] = (fact["accession"], currency)
    company_id = facts[0]["company_id"]
    concepts = {fact["concept"] for fact in facts}
    rows = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id,
        FinancialFact.concept.in_(concepts),
        FinancialFact.fiscal_period.isnot(None),
    ).all()
    # The upsert's own rows are still pending (no autoflush): the batch's ratio may be one.
    rows += [obj for obj in db.new if isinstance(obj, FinancialFact) and obj.company_id == company_id
             and obj.concept in concepts and obj.fiscal_period is not None]
    demoted = 0
    ratio_rows: dict[tuple[Any, ...], list[Any]] = {}
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        unit_currency = row.unit.partition("/")[0]
        if is_amount_unit(unit_currency) and unit_currency != currency:
            if row.is_latest:
                row.is_latest = False
                demoted += 1
        elif row.unit == "pure" and key in ratios:
            ratio_rows.setdefault(key, []).append(row)
    for key, group in ratio_rows.items():
        batch_ratio = next((row for row in group
                            if (row.accession, _operand_unit(row.provenance)) == ratios[key]), None)
        stale = [row for row in group if row.is_latest and _other_derived(row, currency)]
        if batch_ratio is None or not stale:
            continue
        for row in stale:
            row.is_latest = False
        batch_ratio.is_latest = True
        demoted += len(stale)
    return demoted
