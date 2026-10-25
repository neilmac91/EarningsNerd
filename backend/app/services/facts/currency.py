"""Reporting currency of a companyfacts series, and the convenience rows it supersedes.

A foreign US-GAAP filer (the Alibaba shape) tags every period in its reporting currency and, in
each filing, its own period again as a USD convenience translation at that period's rate.
Companyfacts therefore holds a CNY list and a USD list for the same line. A history built from
the USD list mixes exchange-rate moves into growth, so a concept whose USD list is such a
translation is read from its reporting currency instead.

The currency ranking (``_reporting_currency``) is defined here, not in the per-filing extractor
that shares it (``edgar/instance/core.py`` re-exports it), so the pure normalizers that import
this module load no Settings, ORM or EDGAR code, at import or at call time. Only
``demote_convenience_rows``, which the session-owning ingest calls, imports the ORM. The
collector's item admission (``admitted_items``) lives here too, so the ranking counts exactly the
periods ``companyfacts`` keeps, and so does the form rule it applies (``is_proxy_form``): a proxy or
information statement's figures are never admitted, so they neither win a period nor rank a unit list.
"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import TYPE_CHECKING, Any, Iterator

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


def admitted_items(items: list, *, instant: bool) -> Iterator[tuple[tuple[date, str], date | None, float, dict]]:
    """Each companyfacts item the collector keeps, as ``((end, klass), start, value, item)``.

    A kept item comes from no proxy or information statement (``is_proxy_form``), and has a finite
    numeric ``val`` and a parseable ``end``. A duration also needs a parseable ``start``, and its
    span sets klass ("FY", "Q", "YTD6" or "YTD9"; any other span is dropped); an instant's klass is
    "I". ``series_unit`` ranks the unit lists on these same keys, so a list never wins on a period
    that the collector then drops.
    """
    # Call time: concepts imports quarterly, which imports this module.
    from app.services.facts.concepts import _classify_duration, _parse_date

    for item in items:
        if not isinstance(item, dict) or is_proxy_form(item.get("form")):
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


def series_unit(usgaap: dict, tags: tuple[str, ...], default_unit: str, *, instant: bool) -> str:
    """The unit list one concept is read from: its reporting currency across its candidate tags.

    ``default_unit`` is the concept's USD unit ("USD" or "USD/shares"); only lists of the same
    shape compete. A foreign list is read only when the USD list is its convenience translation:
    every USD period the collector keeps (``admitted_items``: period end and span class) is also
    kept from the foreign list; an item the collector drops counts on neither side, and with no
    USD list every foreign list qualifies. Among such lists ``_reporting_currency``,
    the per-filing extractor's rule, picks (the most distinct period-ends, then the latest).
    Any other shape keeps ``default_unit``: a stray foreign fact, whatever its date, or a currency
    switch in either direction. There some USD period has no native twin, so a native read
    would leave the USD row an earlier sync stored there current beside the native series.
    """
    suffix = "/shares" if default_unit.endswith("/shares") else ""
    kept: dict[str, set[tuple[date, str]]] = {}
    for tag in tags:
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        for key, items in units.items() if isinstance(units, dict) else ():
            currency = key.removesuffix(suffix)
            if key != currency + suffix or not is_amount_unit(currency) or not isinstance(items, list):
                continue
            kept.setdefault(currency, set()).update(period for period, *_ in admitted_items(items, instant=instant))
    usd = kept.pop("USD", set())
    native = [(end.isoformat(), 0.0, currency, 0.0) for currency, periods in kept.items() if usd <= periods
              for end, _klass in periods]
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
