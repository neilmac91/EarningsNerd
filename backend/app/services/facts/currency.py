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
demotion reads the very pick the collector read. Where a newer annual report the payload does not
show yet, reporting a period at least as late as the payload's own deciding report, proves the
series switched currency (``_proven_switch``), the sync writes nothing from the payload and leaves
only that currency current, outside the filings the payload reads in another currency: a wrong
number is worse than a gap, and the payload's own rows, current at the periods only it presents,
would mix the old currency into the new one's series across years.
"""
from __future__ import annotations

import math
from datetime import date
from typing import TYPE_CHECKING, Any, Callable, Iterator, Mapping, NamedTuple

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
    return _filing_pick(usgaap, duration_tags, instant_tags)[:2]


def _filing_pick(
    usgaap: dict, duration_tags: Mapping[str, tuple[str, ...]], instant_tags: Mapping[str, tuple[str, ...]]
) -> tuple[str, frozenset[Any], dict[Any, str], tuple[Any, ...] | None]:
    """``filing_currencies``' series currency and foreign filings, and what ``payload_view`` carries
    besides: each determined filing's own currency, and the deciding filing's rank ``(an annual
    report, its currency spans two period-ends, its latest period-end, filed)``, None when no filing
    is determined."""
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
    currencies = {accession: currency for accession, (currency, _ends) in own.items()}
    return (series, frozenset(accession for accession, currency in currencies.items() if currency != series),
            currencies, deciding[:-1] if deciding else None)


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
    own: Mapping[Any, str]  # each determined filing's own currency (a tie is absent)
    decider: tuple[Any, ...] | None  # the deciding filing's rank (``_filing_pick``), None when none decides


def payload_view(companyfacts: Any) -> PayloadView:
    """The raw payload's pick, over its us-gaap items through the collector's registries, and the
    filings it knows: every item of every taxonomy (us-gaap, ifrs-full, dei) counts, in any unit, so
    a filing companyfacts names under another taxonomy is never taken for one it does not show yet."""
    # Call time: concepts imports quarterly, which imports this module.
    from app.services.facts.concepts import COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS

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
    series, foreign, own, decider = _filing_pick(
        usgaap if isinstance(usgaap, dict) else {}, COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS)
    return PayloadView(series, foreign, frozenset(known), newest, own, decider)


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


class Guard(NamedTuple):
    """What the stored rows of filings newer than a payload decide for its sync (``protected_rows``)."""

    ids: frozenset[int]  # the rows neither of the sync's paths may demote, all in the series currency; none on a switch
    switch: str | None  # the currency a newer annual report proves the series switched to, else None


def protected_rows(db: Session, facts: list[dict[str, Any]], view: PayloadView) -> Guard:
    """The stored rows of the batch's concepts that no sync of this payload may demote, and the switch
    of the reporting currency they prove, if any.

    Such a row is from a filing the payload does not name, filed after the payload's newest: a newer
    filing that SEC's companyfacts does not show yet (a delayed response, or the sync a new filing
    triggers before companyfacts includes it). A row's filing date is its Filing row's, as
    ``upsert_facts_bulk`` reads them, else its provenance's ``filed_at``; a row with neither, or one
    filed on the payload's newest date, is not protected. The read takes the fact writers' company
    lock first, so no writer adds a row between it and the upsert, which stores the batch's row
    behind a protected current one as it does behind a known newer filing.

    Where those rows prove a switch (``_proven_switch``), no row is protected: the sync stores nothing
    and demotes by currency (``demote_convenience_rows``). Otherwise a row keeps its protection only in
    the payload's series currency (``_in_view``): an amount or per-share row in that currency, a ratio
    not computed from another currency's operands, or a row of any other unit (a share count). The sync
    that names its filing would demote a row outside the view, so this one may: a stray, or a quarterly
    report's rows ahead of the annual report that switches.
    """
    from app.models import Filing, FinancialFact  # lazy: the pure normalizers import this module
    from app.services.facts.upsert import _lock_fact_companies

    if not facts:
        return Guard(frozenset(), None)
    _lock_fact_companies(db, facts)
    columns = (FinancialFact.id, FinancialFact.accession, FinancialFact.unit, FinancialFact.is_latest,
               FinancialFact.form, FinancialFact.concept, FinancialFact.period_end, FinancialFact.fiscal_period,
               FinancialFact.provenance, FinancialFact.source, FinancialFact.filing_id)
    rows = [row for row in db.query(*columns).filter(
        FinancialFact.company_id == facts[0]["company_id"],
        FinancialFact.concept.in_({fact["concept"] for fact in facts}),
    ) if row.accession not in view.known]
    filings = {accession: (stamp, form) for accession, stamp, form in db.query(
        Filing.accession_number, Filing.filing_date, Filing.filing_type).filter(
        Filing.accession_number.in_({row.accession for row in rows}))} if rows else {}

    def filed(row: Any) -> str:
        stored = filings.get(row.accession, (None, None))[0]
        if stored is not None:
            return stored.isoformat()[:10]
        provenance = row.provenance if isinstance(row.provenance, dict) else {}
        return str(provenance.get("filed_at") or "")[:10]

    newer = [row for row in rows if filed(row) > view.newest_filed]
    switch = _proven_switch(newer, filed, {accession: form for accession, (_stamp, form) in filings.items()}, view)
    return Guard(frozenset() if switch else frozenset(row.id for row in newer if _in_view(row, view.currency)),
                 switch)


def _proven_switch(newer: list[Any], filed: Callable[[Any], str], forms: Mapping[Any, Any],
                   view: PayloadView) -> str | None:
    """The currency a newer filing proves the series switched to from the payload's, else None.

    ``newer`` holds the stored rows of the batch's concepts from filings newer than the payload
    (``protected_rows``). Each such filing (accession) votes from them as ``filing_currencies`` votes
    from a payload: its own currency is the one more of its amount rows carry than any other (not
    always a majority), each counted once per concept and period; per-share rows do not vote, and a
    tie leaves it undetermined. A filing may decide when it is an annual report (``ANNUAL_FORMS``, by
    a row's form, else its Filing row's type), holds a current row, its own currency spans two
    period-ends, and it outranks the payload's own deciding filing (``view.decider``) on
    ``filing_currencies``' rank, which a filing filed after it does when its latest period-end in that
    currency is at least as late. The one ranking highest on (that period-end, filed) decides, and proves a switch when its
    currency is not the payload's. So a stray (one concept read in another currency), a quarterly
    report, an annual report tagging one period, or a 10-K/A or 20-F/A restating a year before the
    payload's latest annual report never proves one: none would decide ``filing_currencies`` over the
    payload and it. A misjudgement here picks one of two views that each read one currency: a gap,
    never a wrong number. The stored units are the per-filing writer's per-concept picks, so a newer
    10-K most of whose concepts that pick read in another currency proves a switch the payload's own
    items would not (a gap in that currency until the sync that names it).
    """
    votes: dict[Any, dict[str, set[tuple[Any, ...]]]] = {}
    stamps: dict[Any, tuple[bool, bool, str]] = {}  # accession -> (an annual report, a current row, filed)
    for row in newer:
        if is_amount_unit(row.unit):
            votes.setdefault(row.accession, {}).setdefault(row.unit, set()).add(
                (row.concept, row.period_end, row.fiscal_period))
        was = stamps.get(row.accession, (False, False, ""))
        stamps[row.accession] = (was[0] or (row.form or forms.get(row.accession)) in ANNUAL_FORMS,
                                 was[1] or bool(row.is_latest), max(was[2], filed(row)))
    proofs = []
    for accession, by_unit in votes.items():
        ranked = sorted(((len(keys), unit) for unit, keys in by_unit.items()), reverse=True)
        ends = {end for _concept, end, _period in by_unit[ranked[0][1]]}
        annual, current, when = stamps[accession]
        rank = (True, True, max(ends), when)  # filing_currencies' rank of an annual report over two period-ends
        if ((len(ranked) == 1 or ranked[0][0] > ranked[1][0]) and annual and current and len(ends) >= 2
                and (view.decider is None or rank > view.decider)):
            proofs.append((*rank[2:], ranked[0][1]))
    deciding = max(proofs, default=None)
    return deciding[-1] if deciding is not None and deciding[-1] != view.currency else None


def _in_view(row: Any, currency: str) -> bool:
    """Whether a newer filing's row keeps its protection in a view read in ``currency``. The writers
    keep one current ratio per key, and no companyfacts concept carries a share count, so the ratio
    and share-count clauses change an outcome only in a state built by hand."""
    kind = _kind(row.unit)
    if kind == "amount":
        return row.unit.partition("/")[0] == currency
    return kind is None or not _other_derived(row, currency)


def _kind(unit: str) -> str | None:
    """What a row competes with for its key here: "amount" for a currency amount or per-share unit, in
    any currency, "pure" for a ratio, None for any other unit (a share count), which the sync leaves."""
    return "amount" if is_amount_unit(unit.partition("/")[0]) else ("pure" if unit == "pure" else None)


def demote_convenience_rows(db: Session, facts: list[dict[str, Any]], view: PayloadView, guard: Guard) -> int:
    """Demote the current rows a companyfacts batch supersedes, make its own row current where a key it
    presents has none, and return how many rows were demoted; never delete or rewrite one.

    The batch is read in one series currency (``filing_currencies``), which its amount units carry,
    and ``view`` is its payload's own (``payload_view``). ``is_latest`` is kept per unit, so at every
    key with a fiscal period, over the batch's concepts and whatever a row's source or filing, a
    current row is demoted when it is an amount or per-share row in another currency (a convenience
    translation, a period from before a currency switch that the new currency's filings do not
    present, or a newer filing's row outside the view), in both directions; when it is an amount or
    per-share row under a filing whose own currency is another (``view.foreign``): there a figure in
    the series currency is that filing's convenience translation, as earlier syncs stored it; and when
    a protected row (``guard.ids``) of its kind, amount or ratio, is current at its key: a newer filing
    holds its key, so the batch never leaves its own row current beside it. A protected row is in the
    series currency and is never demoted. Then ``_promote_batch_rows`` makes the batch's own row current
    at every key it presents that holds none, whichever sync left it so, and ``_replace_stale_ratios``
    replaces the ratios computed from other-currency operands. Rows with no fiscal period and other
    concepts are left alone. The count is of rows demoted; a promotion is not counted, as the upsert's
    insert is not.

    Where a newer annual report proves the series switched (``guard.switch``), the ingest stores nothing
    from the batch, and this only demotes, at every key with a fiscal period over the batch's concepts,
    each current amount or per-share row in another currency than the switch's, protected or not, and
    each in the switch's currency under a filing whose own currency, as this payload reads it
    (``view.own``), is another: the convenience translations the sync that names that report demotes
    too. Nothing is promoted and no ratio is replaced, so the current amount and per-share rows are
    those a sync whose payload names every stored filing converges to (gaps before the switch), or
    fewer wherever that sync would make current a row not current now: the report's rows the
    per-filing writer stored behind older ones, a quarterly report's rows in the switch's currency
    that an earlier sync demoted, and, on a switch back, the older filings' rows in that currency,
    which no sync reading the other currency stored. They are more in one shape: a row in the
    switch's currency under a newer filing this payload does not name, which that sync reads in
    another currency, stays current until that sync runs.
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
    if guard.switch:
        stale = [row for row in labelled if row.is_latest and _kind(row.unit) == "amount"
                 and (row.unit.partition("/")[0] != guard.switch
                      or view.own.get(row.accession, guard.switch) != guard.switch)]
        for row in stale:
            row.is_latest = False
        return len(stale)
    newer = {(row.concept, row.period_end, row.fiscal_period, _kind(row.unit)) for row in labelled
             if row.is_latest and row.id in guard.ids and _kind(row.unit)}
    demoted = 0
    for row in labelled:
        kind, unit_currency = _kind(row.unit), row.unit.partition("/")[0]
        superseded = (row.concept, row.period_end, row.fiscal_period, kind) in newer or kind == "amount" and (
            unit_currency != currency or row.accession in view.foreign)
        if superseded and row.is_latest and row.id not in guard.ids:
            row.is_latest = False
            demoted += 1
    _promote_batch_rows(facts, rows)
    return demoted + _replace_stale_ratios(facts, labelled, currency)


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


def _replace_stale_ratios(facts: list[dict[str, Any]], rows: list[Any], currency: str) -> int:
    """Replace each current ratio computed from other-currency operands where the batch has its own.

    A ratio (``pure``) keeps its unit across currencies, so the upsert's filing-date rule can keep one
    computed from other-currency operands (``_other_derived``) current and store the batch's
    calculation behind it: where the batch has its own calculation at that key, the stale row is
    demoted and the batch's promoted, unless the batch's calculation is quarantined (``_promotable``),
    when the stale ratio stays current. A protected ratio is never stale here: it is in the view
    (``_in_view``), and the demotion has already demoted any other ratio current at its key. A ratio
    stored under the batch calculation's own identity is skipped by the upsert and left as it is; the
    journaled repair recomputes it. Returns how many rows were demoted.
    """
    ratios = {(f["concept"], f["period_end"], f["fiscal_period"]): f["accession"] for f in facts
              if f["unit"] == "pure" and _operand_unit(f.get("provenance")) == currency}
    groups: dict[tuple[Any, ...], list[Any]] = {}
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        if row.unit == "pure" and key in ratios:
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
