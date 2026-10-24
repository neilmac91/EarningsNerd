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
``protected_rows`` and ``demote_convenience_rows``, which the session-owning ingest calls with the
payload's own view of itself (``payload_view``), import the ORM. The collector's item admission
(``admitted_items``) and its pick over the companyfacts registries (``companyfacts_currencies``)
live here too, so the per-filing pick counts exactly the periods ``companyfacts`` keeps and the
demotion reads the very pick the collector read.
"""
from __future__ import annotations

import math
from datetime import date
from typing import TYPE_CHECKING, Any, Iterator, Mapping, NamedTuple

from app.services.facts.fiscal_naming import ANNUAL_FORMS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_QUARTERS = ("Q1", "Q2", "Q3", "Q4")  # concepts._QUARTER_PERIODS, which this module cannot import at load


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
    same keys, so an item the collector drops for its value, date or span never votes. The pick
    runs over the whole registries, so the concepts a financial filer's collector skips
    (``_FI_SKIPPED_CONCEPTS``) still vote: a filing tags them in its own currency too.
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
    across the amount lists, instants included; per-share lists do not vote. A tie leaves the
    filing undetermined, and its items are read in whatever currency the series takes.
    ``_reporting_currency``'s rule is not reused here: it counts period-ends and breaks a tie toward
    the non-USD code, so one stray EUR fact at a USD 10-K's own period-end would make that 10-K EUR.
    The series currency is the deciding filing's, the determined filing that ranks highest on
    ``(an annual report, its currency spans two period-ends, its latest period-end, filed)``: the
    annual report presenting comparatives that reports the latest period, so a later 10-K/A or
    20-F/A restating an older year never decides over the newer annual report. With no determined
    filing it is the domestic default, USD. The collector never reads a filing whose own currency
    is another: there its items in the series currency are convenience translations. So a
    switcher's series holds only the periods its filings in the new currency present, and a stray
    item (a one-period amendment, a later quarterly report) never flips it.
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
    own: dict[Any, tuple[str, set[date]]] = {}  # accession -> its currency, and the period-ends it spans
    for accession, by_unit in votes.items():
        ranked = sorted(by_unit.items(), key=lambda pair: len(pair[1]), reverse=True)
        if len(ranked) == 1 or len(ranked[0][1]) > len(ranked[1][1]):
            currency, kept = ranked[0]
            own[accession] = (currency, {end for _tag, end, _klass in kept})
    deciding = max(((stamps[accession][0], len(ends) >= 2, max(ends), stamps[accession][1], currency)
                    for accession, (currency, ends) in own.items()), default=None)
    series = deciding[-1] if deciding else "USD"
    return series, frozenset(accession for accession, (currency, _ends) in own.items() if currency != series)


def companyfacts_currencies(usgaap: dict) -> tuple[str, frozenset[Any]]:
    """``filing_currencies`` over the companyfacts registries: the one pick the collector reads, and
    the sync's demotion reads again through ``payload_view``, so the two never disagree."""
    # Call time: concepts imports quarterly, which imports this module.
    from app.services.facts.concepts import COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS

    return filing_currencies(usgaap, COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS)


class PayloadView(NamedTuple):
    """What one companyfacts payload shows of itself, for ``protected_rows`` and ``demote_convenience_rows``."""

    currency: str  # the series currency (``companyfacts_currencies``), the one the batch's units carry
    foreign: frozenset[Any]  # the filings whose own facts are in another currency
    known: frozenset[Any]  # every accession its items name, in any taxonomy and unit
    newest_filed: str  # its newest ``filed`` date (ISO), "" when no item carries one


def payload_view(companyfacts: Any) -> PayloadView:
    """The raw payload's pick, over its us-gaap items, and the filings it knows: every item of every
    taxonomy (us-gaap, ifrs-full, dei) counts, in any unit, so a filing companyfacts names under
    another taxonomy is never taken for one it does not show yet."""
    facts_root = companyfacts.get("facts") if isinstance(companyfacts, dict) else None
    facts_root = facts_root if isinstance(facts_root, dict) else {}
    items = (item for taxonomy in facts_root.values() if isinstance(taxonomy, dict)
             for node in taxonomy.values() if isinstance(node, dict) and isinstance(node.get("units"), dict)
             for listed in node["units"].values() if isinstance(listed, list)
             for item in listed if isinstance(item, dict))
    known: set[Any] = set()
    newest = ""
    for item in items:
        known.add(item.get("accn"))
        newest = max(newest, str(item.get("filed") or "")[:10])
    usgaap = facts_root.get("us-gaap")
    return PayloadView(*companyfacts_currencies(usgaap if isinstance(usgaap, dict) else {}), frozenset(known), newest)


def _operand_unit(provenance: Any) -> Any:
    """The one unit a calculation's recorded operands share, or None when absent or mixed."""
    inputs = provenance.get("inputs") if isinstance(provenance, dict) else None
    units = {operand.get("unit") for operand in inputs or () if isinstance(operand, dict)}
    return units.pop() if len(units) == 1 else None


def _promotable(row: Any) -> bool:
    """Not a row whose provenance is unavailable: one the journaled repair quarantined (a rolled-back
    insert among them, which only a reviewed reapplication may restore) or one withheld from display."""
    return not (isinstance(row.provenance, dict) and row.provenance.get("validation") == "unavailable")


def _other_derived(row: Any, currency: str) -> bool:
    """A stored ratio computed from operands in another currency than ``currency``. Rows from
    before operands were recorded (2026-10-10) have no provenance; a derived one with no filing
    owner came from companyfacts, which then read only the USD lists."""
    if row.provenance is None:
        return currency != "USD" and row.source == "derived" and row.filing_id is None
    operands = _operand_unit(row.provenance)
    return is_amount_unit(operands) and operands != currency


def protected_rows(db: Session, facts: list[dict[str, Any]], view: PayloadView) -> frozenset[int]:
    """The ids of the stored rows of the batch's concepts that no sync of this payload may demote.

    Such a row is from a filing the payload does not name, filed after the payload's newest: a newer
    filing that SEC's companyfacts does not show yet (a delayed response, or the sync a new filing
    triggers before companyfacts includes it). A row's filing date is its Filing row's, as
    ``upsert_facts_bulk`` reads them, else its provenance's ``filed_at``; a row with neither, or one
    filed on the payload's newest date, is not protected. The read takes the fact writers' company
    lock first, so no writer adds a row between it and the upsert, which stores the batch's row
    behind a protected current one as it does behind a known newer filing.
    """
    from app.models import Filing, FinancialFact  # lazy: the pure normalizers import this module
    from app.services.facts.upsert import _lock_fact_companies

    if not facts:
        return frozenset()
    _lock_fact_companies(db, facts)
    rows = [row for row in db.query(FinancialFact.id, FinancialFact.accession, FinancialFact.provenance).filter(
        FinancialFact.company_id == facts[0]["company_id"],
        FinancialFact.concept.in_({fact["concept"] for fact in facts}),
    ) if row.accession not in view.known]
    dates = dict(db.query(Filing.accession_number, Filing.filing_date).filter(
        Filing.accession_number.in_({row.accession for row in rows})).all()) if rows else {}

    def filed(row: Any) -> str:
        stored = dates.get(row.accession)
        if stored is not None:
            return stored.isoformat()[:10]
        provenance = row.provenance if isinstance(row.provenance, dict) else {}
        return str(provenance.get("filed_at") or "")[:10]

    return frozenset(row.id for row in rows if filed(row) > view.newest_filed)


def _kind(unit: str) -> str | None:
    """What a row competes with for its key here: "amount" for a currency amount or per-share unit, in
    any currency, "pure" for a ratio, None for any other unit (a share count), which the sync leaves."""
    return "amount" if is_amount_unit(unit.partition("/")[0]) else ("pure" if unit == "pure" else None)


def demote_convenience_rows(
    db: Session, facts: list[dict[str, Any]], view: PayloadView, protected: frozenset[int],
) -> int:
    """Demote the current rows a companyfacts batch supersedes, make its own row current where a key it
    presents has none, and return how many rows were demoted; never delete or rewrite one.

    The batch is read in one series currency (``filing_currencies``), which its amount units carry,
    and ``view`` is its payload's own (``payload_view``). ``is_latest`` is kept per unit, so at every
    key with a fiscal period, over the batch's concepts and whatever a row's source or filing, a
    current row is demoted when it is an amount or per-share row in another currency (a convenience
    translation, or a period from before a currency switch that the new currency's filings do not
    present), in both directions; when it is an amount or per-share row under a filing whose own
    currency is another (``view.foreign``): there a figure in the series currency is that filing's
    convenience translation, as earlier syncs stored it; and when a ``protected`` row
    (``protected_rows``) of its kind, amount or ratio, is current at its key: a newer filing holds
    its key, so the batch never leaves its own row current beside it. A protected row is never
    demoted. Then ``_promote_batch_rows`` makes the batch's own row current at every key it presents
    that holds none, whichever sync left it so, and ``_replace_stale_ratios`` replaces the ratios
    computed from other-currency operands. Rows with no fiscal period and other concepts are left
    alone. The count is of rows demoted; a promotion is not counted, as the upsert's insert is not.
    """
    from app.models import FinancialFact  # lazy: the pure normalizers import this module

    currencies = (fact["unit"].partition("/")[0] for fact in facts)
    currency = next((unit for unit in currencies if is_amount_unit(unit)), None)
    if currency is None:
        return 0
    company_id = facts[0]["company_id"]
    concepts = {fact["concept"] for fact in facts}
    rows = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id, FinancialFact.concept.in_(concepts)).all()
    # The upsert's own rows are still pending (no autoflush): the batch's ratio may be one.
    rows += [obj for obj in db.new if isinstance(obj, FinancialFact) and obj.company_id == company_id
             and obj.concept in concepts]
    labelled = [row for row in rows if row.fiscal_period is not None]
    newer = {(row.concept, row.period_end, row.fiscal_period, _kind(row.unit)) for row in labelled
             if row.is_latest and row.id in protected and _kind(row.unit)}
    demoted = 0
    for row in labelled:
        kind, unit_currency = _kind(row.unit), row.unit.partition("/")[0]
        superseded = (row.concept, row.period_end, row.fiscal_period, kind) in newer or kind == "amount" and (
            unit_currency != currency or row.accession in view.foreign)
        if superseded and row.is_latest and row.id not in protected:
            row.is_latest = False
            demoted += 1
    _promote_batch_rows(facts, rows)
    return demoted + _replace_stale_ratios(facts, labelled, currency, newer)


def _promote_batch_rows(facts: list[dict[str, Any]], rows: list[Any]) -> None:
    """Make the batch's own amount or per-share row (same concept, key, unit and accession) current at
    every key it presents that holds no current amount or per-share row, in any currency, so a fresh
    sync leaves each such key one current row whatever earlier syncs left (a stale payload's demotion,
    a switch and back): the upsert skips a stored identity and never touches its ``is_latest``. A key
    a protected or known-newer row holds is held, and so is a quarter whose unlabelled twin in the
    row's unit is current (the upsert's D1 rule). Never a quarantined row (``_promotable``)."""
    own = {(f["concept"], f["period_end"], f["fiscal_period"]): (f["unit"], f["accession"])
           for f in facts if _kind(f["unit"]) == "amount"}
    current = [row for row in rows if row.is_latest and _kind(row.unit) == "amount"]
    held = {(row.concept, row.period_end, row.fiscal_period) for row in current}
    twins = {(row.concept, row.period_end, row.unit) for row in current if row.fiscal_period is None}
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        if key in held or (row.unit, row.accession) != own.get(key) or not _promotable(row):
            continue
        if row.fiscal_period not in _QUARTERS or (row.concept, row.period_end, row.unit) not in twins:
            row.is_latest = True
            held.add(key)


def _replace_stale_ratios(facts: list[dict[str, Any]], rows: list[Any], currency: str, newer: set) -> int:
    """Replace each current ratio computed from other-currency operands where the batch has its own.

    A ratio (``pure``) keeps its unit across currencies, so the upsert's filing-date rule can keep one
    computed from other-currency operands (``_other_derived``) current and store the batch's
    calculation behind it: where the batch has its own calculation at that key, the stale row is
    demoted and the batch's promoted, unless a protected ratio holds the key (``newer``) or the
    batch's calculation is quarantined (``_promotable``), when the stale ratio stays current. A ratio
    stored under the batch calculation's own identity is skipped by the upsert and left as it is; the
    journaled repair recomputes it. Returns how many rows were demoted.
    """
    ratios = {(f["concept"], f["period_end"], f["fiscal_period"]): f["accession"] for f in facts
              if f["unit"] == "pure" and _operand_unit(f.get("provenance")) == currency}
    groups: dict[tuple[Any, ...], list[Any]] = {}
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        if row.unit == "pure" and key in ratios and (*key, "pure") not in newer:
            groups.setdefault(key, []).append(row)
    demoted = 0
    for key, group in groups.items():
        batch_ratio = next((row for row in group if _promotable(row) and row.accession == ratios[key]
                            and _operand_unit(row.provenance) == currency), None)
        stale = [row for row in group if row.is_latest and _other_derived(row, currency)]
        if batch_ratio is None or not stale:
            continue
        for row in stale:
            row.is_latest = False
        batch_ratio.is_latest = True
        demoted += len(stale)
    return demoted
