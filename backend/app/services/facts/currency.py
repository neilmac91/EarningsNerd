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

A sync that involves no currency but USD (``_another_currency``: neither the payload's pick nor a
stored row of the batch's concepts names another) is main's: nothing is protected and the currency
step returns before touching a row (``Guard.usd_only``). Only where another currency is involved
does the rest run. Where a newer annual report the payload does not show yet, reporting a period at
least as late as the payload's own deciding report, proves the series switched currency
(``_proven_switch``), the sync writes nothing from the payload and leaves only that currency
current, outside the filings whose own currency is another (as the payload reads them, or, for a
filing it does not name, as that filing's stored rows vote): a wrong number is worse than a gap, and
the payload's own rows, current at the periods only it presents, would mix the old currency into
the new one's series across years. Otherwise (``_promote_batch_rows``) a key where a protected row
of a newer filing sits, current or not, holds the newest protected row there, and every other key
the batch presents holds the batch's own row, except a key where a row of a filing filed strictly
after the batch row's own filing was current (a newer-filing rule by date alone: companyfacts' first
tag with data, not the latest filing, picks the batch's winner), and one whose row to make current
is quarantined or whose quarter has a current unlabelled twin in that unit: those are left as found.
So the sync that names every stored filing leaves each key it presents to its batch's row or to a
newer filing's current row there, whatever earlier syncs left, outside those it leaves as found.
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
    filed: Mapping[Any, str]  # each named filing's own ``filed`` date (ISO), the latest its items carry


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
    filed: dict[Any, str] = {}
    for item in items:
        filed[item.get("accn")] = max(filed.get(item.get("accn"), ""), str(item.get("filed") or "")[:10])
    usgaap = facts_root.get("us-gaap")
    series, foreign, own, decider = _filing_pick(
        usgaap if isinstance(usgaap, dict) else {}, COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INSTANT_TAGS)
    return PayloadView(series, foreign, frozenset(filed), max(filed.values(), default=""), own, decider, filed)


def _operand_unit(provenance: Any) -> Any:
    """The one unit a calculation's recorded operands share, or None when absent or mixed."""
    inputs = provenance.get("inputs") if isinstance(provenance, dict) else None
    units = {operand.get("unit") for operand in inputs or () if isinstance(operand, dict)}
    return units.pop() if len(units) == 1 else None


def _filed(accession: Any, provenance: Any, dates: Mapping[Any, str], view: PayloadView) -> str:
    """A row's filing date (ISO) as the sync reads it: its Filing row's (``dates``), else its filing's ``filed``
    in the payload (``view.filed``), else the row's provenance ``filed_at``, else "" (not known). So a calculation
    is dated by its own filing wherever either dates it; only the fallback, ``filed_at``, is its latest operand's."""
    if accession in dates:
        return dates[accession]
    named = view.filed.get(accession)
    return named or str((provenance if isinstance(provenance, dict) else {}).get("filed_at") or "")[:10]


def _filing_dates(db: Session, accessions: set[Any]) -> dict[Any, str]:
    """Each accession's Filing row date (ISO), as ``upsert_facts_bulk`` reads them."""
    from app.models import Filing  # lazy: the pure normalizers import this module

    return {accession: stamp.isoformat()[:10] for accession, stamp in db.query(
        Filing.accession_number, Filing.filing_date).filter(Filing.accession_number.in_(accessions)) if stamp is not None}


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
    """What the stored rows decide for a payload's sync (``protected_rows``)."""

    ids: frozenset[int]  # the rows neither of the sync's paths may demote, all in the series currency; none on a switch
    switch: str | None  # the currency a newer annual report proves the series switched to, else None
    own: Mapping[Any, str]  # each unnamed filing's own currency, newer or not, as its stored rows vote; a tie is absent
    later: frozenset[int] = frozenset()  # current rows (ratios too) of a filing filed strictly after the batch row's
    usd_only: bool = False  # no currency but USD is involved (``_another_currency``): the currency step is main's

    @property
    def kept(self) -> frozenset[int]:
        """The rows the upsert keeps current over a batch row (its ``protected``): ``ids`` and ``later``."""
        return self.ids | self.later


def _another_currency(db: Session, facts: list[dict[str, Any]], view: PayloadView) -> bool:
    """Whether a sync involves a currency other than USD: the payload's series currency, or the own currency
    it reads for a filing (``view.own``, which holds the deciding filing and every ``view.foreign`` one), or
    the unit of a stored amount or per-share row of the batch's concepts, current or not. Otherwise the
    currency step is main's (``Guard.usd_only``). Rows that are not current count too: the vote reads
    them (``_proven_switch``), and a later sync still converges the keys a demotion left. Rows are never
    deleted, so once a company stores such a row, demoted or not, the step runs on every sync whose batch
    carries its concept: it never switches off."""
    from app.models import FinancialFact  # lazy: the pure normalizers import this module

    if view.currency != "USD" or any(currency != "USD" for currency in view.own.values()):
        return True
    units = db.query(FinancialFact.unit).filter(  # one read over the identity index's (company, concept) prefix
        FinancialFact.company_id == facts[0]["company_id"],
        FinancialFact.concept.in_({fact["concept"] for fact in facts})).distinct()
    return any(_kind(unit) == "amount" and unit.partition("/")[0] != "USD" for (unit,) in units)


def protected_rows(db: Session, facts: list[dict[str, Any]], view: PayloadView) -> Guard:
    """The stored rows of the batch's concepts that no sync of this payload may demote, the switch of
    the reporting currency they prove, if any, each unnamed filing's own currency as its stored rows
    vote (``_proven_switch``), and the rows the upsert keeps current (``Guard.kept``). A sync in USD
    alone (``_another_currency``) gets none of these: main's upsert and a currency step that returns.

    A protected row is from a filing the payload does not name, filed after the payload's newest (by
    ``_filed``; undated, or filed that day, is not): a newer filing that SEC's companyfacts does not
    show yet (a delayed response, or the sync a new filing triggers before companyfacts includes it).
    The read takes the fact writers' company lock first, so no writer adds a row between it and the
    upsert, which stores the batch's row behind a protected current one as behind a known newer filing,
    and behind each current row in its unit of a filing filed strictly after the batch row's own
    (``Guard.later``: the upsert's own rule reads Filing rows only). Where those rows prove a switch,
    none is protected: the sync stores nothing and demotes by currency. Otherwise a row keeps its
    protection only in the payload's view (``_in_view``): an amount or per-share row in the series
    currency under a filing whose own currency, as its stored rows vote (``Guard.own``), is not
    another, a ratio not computed from another currency's operands, or a row of any other unit. Outside
    it are a stray, a quarterly report's rows ahead of the annual report that switches, and a
    convenience translation (``_foreign``), each demoted by the sync that names the filing where the
    vote reads it as its payload items do.
    """
    from app.models import Filing, FinancialFact  # lazy: the pure normalizers import this module
    from app.services.facts.upsert import _lock_fact_companies

    if not facts:
        return Guard(frozenset(), None, {})
    _lock_fact_companies(db, facts)
    if not _another_currency(db, facts, view):
        return Guard(frozenset(), None, {}, usd_only=True)
    columns = (FinancialFact.id, FinancialFact.accession, FinancialFact.unit, FinancialFact.is_latest,
               FinancialFact.form, FinancialFact.concept, FinancialFact.period_end, FinancialFact.fiscal_period,
               FinancialFact.provenance, FinancialFact.source, FinancialFact.filing_id)
    stored = db.query(*columns).filter(FinancialFact.company_id == facts[0]["company_id"],
                                       FinancialFact.concept.in_({fact["concept"] for fact in facts})).all()
    rows = [row for row in stored if row.accession not in view.known]
    batch = {(f["concept"], f["period_end"], f["fiscal_period"], f["unit"]): f["accession"] for f in facts
             if f["fiscal_period"] is not None and _kind(f["unit"])}  # amounts, per-share rows and ratios
    others = [row for row in stored if row.is_latest and batch.get(
        (row.concept, row.period_end, row.fiscal_period, row.unit), row.accession) != row.accession]
    filings = {accession: (stamp, form) for accession, stamp, form in db.query(
        Filing.accession_number, Filing.filing_date, Filing.filing_type).filter(Filing.accession_number.in_(
            {row.accession for row in (*rows, *others)} | set(batch.values())))}
    dates = {accession: stamp.isoformat()[:10] for accession, (stamp, _form) in filings.items() if stamp is not None}

    def filed(row: Any) -> str:
        return _filed(row.accession, row.provenance, dates, view)

    newer = [row for row in rows if filed(row) > view.newest_filed]
    switch, own = _proven_switch(rows, filed, {accession: form for accession, (_stamp, form) in filings.items()}, view)
    if switch:
        return Guard(frozenset(), switch, own)
    later = frozenset(row.id for row in others if filed(row) > _filed(
        batch[(row.concept, row.period_end, row.fiscal_period, row.unit)], None, dates, view))
    return Guard(frozenset(row.id for row in newer if _in_view(row, view, own)), None, own, later)


def _proven_switch(unnamed: list[Any], filed: Callable[[Any], str], forms: Mapping[Any, Any],
                   view: PayloadView) -> tuple[str | None, dict[Any, str]]:
    """The currency a newer filing proves the series switched to from the payload's, else None, and
    each filing's own currency as its stored rows vote (a tie is absent), which both of the sync's
    paths read for a filing the payload does not name (``_foreign``).

    ``unnamed`` holds the stored rows of the batch's concepts from filings the payload does not name
    (``protected_rows``). Each such filing (accession), newer than the payload or not, votes from them
    as ``filing_currencies`` votes from a payload: its own currency is the one more of its amount rows
    carry than any other (not always a majority), each counted once per concept and period, current or
    not; per-share rows do not vote, and a tie leaves it undetermined. A filing may decide when it is
    filed after the payload's newest, is an annual report (``ANNUAL_FORMS``, by a row's form, else its
    Filing row's type), holds a current row, its own currency spans two period-ends, and it outranks
    the payload's own deciding filing (``view.decider``) on ``filing_currencies``' rank, which it does
    when its latest period-end in that currency is at least as late. The one ranking highest on (that
    period-end, filed) decides, and proves a switch when its currency is not the payload's. So a stray
    (one concept read in another currency), a quarterly report, an annual report tagging one period, or
    a 10-K/A or 20-F/A restating a year before the payload's latest annual report never proves one:
    none would decide ``filing_currencies`` over the payload and it. A misjudged proof only picks
    between two views that each read one currency: a gap, never a wrong number (the stored units are
    the per-filing writer's per-concept picks, so a newer 10-K can prove a switch its payload items
    would not); for the vote's misjudgements outside a switch, see ``_foreign``.
    """
    votes: dict[Any, dict[str, set[tuple[Any, ...]]]] = {}
    stamps: dict[Any, tuple[bool, bool, str]] = {}  # accession -> (an annual report, a current row, filed)
    for row in unnamed:
        if is_amount_unit(row.unit):
            votes.setdefault(row.accession, {}).setdefault(row.unit, set()).add(
                (row.concept, row.period_end, row.fiscal_period))
        was = stamps.get(row.accession, (False, False, ""))
        stamps[row.accession] = (was[0] or (row.form or forms.get(row.accession)) in ANNUAL_FORMS,
                                 was[1] or bool(row.is_latest), max(was[2], filed(row)))
    proofs, own = [], {}
    for accession, by_unit in votes.items():
        ranked = sorted(((len(keys), unit) for unit, keys in by_unit.items()), reverse=True)
        if len(ranked) == 1 or ranked[0][0] > ranked[1][0]:
            own[accession] = ranked[0][1]
        ends = {end for _concept, end, _period in by_unit[ranked[0][1]]}
        annual, current, when = stamps[accession]
        rank = (True, True, max(ends), when)  # filing_currencies' rank of an annual report over two period-ends
        if (accession in own and when > view.newest_filed and annual and current and len(ends) >= 2
                and (view.decider is None or rank > view.decider)):
            proofs.append((*rank[2:], ranked[0][1]))
    deciding = max(proofs, default=None)
    return (deciding[-1] if deciding is not None and deciding[-1] != view.currency else None), own


def _foreign(accession: Any, currency: str, view: PayloadView, own: Mapping[Any, str]) -> bool:
    """Whether a filing's own currency is another than ``currency``, as the payload reads it
    (``view.own``), else, for a filing it does not name, newer than it or not, as that filing's stored
    rows vote (``Guard.own``). Then its amount and per-share rows in ``currency`` are convenience
    translations on both of the sync's paths, as the sync that names the filing reads them: none keeps
    protection, and each is demoted. A tie is not.

    Reading the stored rows leaves two windows, each closed by the sync that names the filing, which
    reads it from its payload items and converges each key its batch presents (``_promote_batch_rows``).
    A row in ``currency`` under the filing that the payload items read in another currency stays current
    (a wrong number) where the vote names no other currency: its amount rows, each counted once per
    concept and period, current or not (per-share rows do not vote), tie for the most, or more are in
    ``currency`` (all, where an earlier sync stored only its convenience items), or it holds none; where
    it is protected and the newest protected row at its key, the sync makes it current there. And the
    vote reads the per-filing writer's per-concept picks, which break a tie toward a non-USD code, so
    where it names a currency the payload items do not read the filing in, its rows in ``currency`` are
    demoted: a gap at a key the batch does not present, and at one it presents from an older filing,
    that older figure (a wrong number).
    """
    return view.own.get(accession, own.get(accession, currency)) != currency


def _in_view(row: Any, view: PayloadView, own: Mapping[Any, str]) -> bool:
    """Whether a newer filing's row keeps its protection in the payload's view: an amount or per-share
    row in its currency under a filing not ``_foreign`` to it, a ratio not computed from another
    currency's operands, or a row of any other unit. The writers keep one current ratio per key, and no
    companyfacts concept carries a share count, so those two clauses change an outcome only in a state
    built by hand."""
    kind, currency = _kind(row.unit), view.currency
    if kind == "amount":
        return row.unit.partition("/")[0] == currency and not _foreign(row.accession, currency, view, own)
    return kind is None or not _other_derived(row, currency)


def _kind(unit: str) -> str | None:
    """What a row competes with for its key here: "amount" for a currency amount or per-share unit, in
    any currency, "pure" for a ratio, None for any other unit (a share count), which the sync leaves."""
    return "amount" if is_amount_unit(unit.partition("/")[0]) else ("pure" if unit == "pure" else None)


def demote_convenience_rows(db: Session, facts: list[dict[str, Any]], view: PayloadView, guard: Guard) -> int:
    """Demote the current rows a companyfacts batch supersedes, make its own row current at the keys it
    presents, and return how many rows were demoted; never delete or rewrite one. A sync in USD alone
    (``guard.usd_only``) returns 0 here before touching a row, as main's step does for a batch in USD.

    The batch is read in one series currency (``filing_currencies``), which its amount units carry,
    and ``view`` is its payload's own (``payload_view``). ``is_latest`` is kept per unit, so at every
    key with a fiscal period, over the batch's concepts and whatever a row's source or filing, a
    current row is demoted when it is an amount or per-share row in another currency (a convenience
    translation, a period from before a currency switch that the new currency's filings do not
    present, or a newer filing's row outside the view), in both directions; when it is an amount or
    per-share row under a filing whose own currency is another (``_foreign``, as this payload reads it,
    else, for a filing it does not name, as that filing's stored rows vote): there a figure in the
    series currency is that filing's convenience translation, as earlier syncs or the per-filing pick
    stored it; and when a protected row (``guard.ids``) of its kind, amount or ratio, is current at its
    key, which is demoted only for a newer protected row there. Then ``_promote_batch_rows`` converges
    each key a protected row holds or the batch presents, and ``_replace_stale_ratios`` replaces the
    ratios computed from other-currency operands. Rows with no fiscal period and other concepts are
    left alone. The count is of rows demoted; a promotion is not counted, as the upsert's insert is
    not, nor is the demotion of this sync's own insert.

    Where a newer annual report proves the series switched (``guard.switch``), the ingest stores nothing
    from the batch, and this only demotes, at every key with a fiscal period over the batch's concepts,
    each current amount or per-share row in another currency than the switch's, protected or not, and
    each in the switch's currency under a filing ``_foreign`` to it: the convenience translations the
    sync that names every stored filing demotes too. Nothing is promoted and no ratio is replaced, so the
    current amount and per-share rows are those that sync converges to (gaps before the switch), or more
    in ``_foreign``'s first window, or fewer wherever that sync would make current a row not current now
    (rows no writer stored yet, stored behind older ones, or demoted by an earlier sync or a later row).
    """
    if guard.usd_only:
        return 0
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
        stale = [row for row in labelled if row.is_latest and _kind(row.unit) == "amount" and (
            row.unit.partition("/")[0] != guard.switch or _foreign(row.accession, guard.switch, view, guard.own))]
        for row in stale:
            row.is_latest = False
        return len(stale)
    newer = {(row.concept, row.period_end, row.fiscal_period, _kind(row.unit)) for row in labelled
             if row.is_latest and row.id in guard.ids and _kind(row.unit)}
    demoted = 0
    for row in labelled:
        kind, unit_currency = _kind(row.unit), row.unit.partition("/")[0]
        superseded = (row.concept, row.period_end, row.fiscal_period, kind) in newer or kind == "amount" and (
            unit_currency != currency or _foreign(row.accession, currency, view, guard.own))
        if superseded and row.is_latest and row.id not in guard.ids:
            row.is_latest = False
            demoted += 1
    dates = _filing_dates(db, {row.accession for row in rows} | {fact["accession"] for fact in facts})
    held: dict[tuple[Any, ...], Any] = {}  # each key a protected row sits at: the newest (filed, accession, id)
    for row in sorted((row for row in labelled if row.id in guard.ids and _kind(row.unit)),
                      key=lambda row: (_filed(row.accession, row.provenance, dates, view), row.accession, row.id)):
        held[(row.concept, row.period_end, row.fiscal_period)] = row
    return (demoted + _promote_batch_rows(facts, rows, held, dates, view)
            + _replace_stale_ratios(facts, labelled, currency, held))


def _promote_batch_rows(facts: list[dict[str, Any]], rows: list[Any], held: Mapping[tuple[Any, ...], Any],
                        dates: Mapping[Any, str], view: PayloadView) -> int:
    """Make one row the one current row of its kind (an amount or per-share row in any currency, or a
    ratio) at each key it decides, demoting every other current row of that kind there whichever sync or
    writer left it, and return how many were demoted (not counting this sync's own insert, as the
    upsert's count never holds one). The upsert skips a stored identity and never touches its
    ``is_latest``, so without this an earlier state decided the key for good: a stale payload's
    demotion, a switch and back, an amendment the per-filing writer stored behind its original's row.

    At a key ``held`` by a protected row of the sync's view (``guard.ids``), current or not, presented
    or not, the row is the newest protected row there (latest filed, then the higher accession, as the
    writers break a same-day tie, then by id): the newest filing's own figure. At every other key with
    a fiscal period the batch presents in an amount or per-share unit, it is the batch's own row (same
    concept, key, unit and accession), unless a current row there is of a filing filed strictly after
    the batch row's own filing (each dated by ``_filed``: a Filing row, else its filing's date in the
    payload, else a provenance's ``filed_at``): that key is left as found, a newer-filing rule by
    date alone, since companyfacts' first tag with data, not the latest filing, picks the batch's winner
    across tags. The upsert stored the batch's row behind such a row in its unit (``Guard.later``, a
    ratio's too), so the rule holds on its insert path too. A quarantined row (``_promotable``), or a
    quarter whose unlabelled twin in its unit is current (the upsert's D1 rule), is never made current and its key is
    left as found, except that this sync's own insert there is demoted: a lagging sync never makes the
    batch's older figure current at a key a newer filing's row holds, and a row current there before
    stays (a gap only where none was). A proven switch, or a sync in USD alone, never calls this."""
    own = {(f["concept"], f["period_end"], f["fiscal_period"]): (f["unit"], f["accession"], _filed(
        f["accession"], None, dates, view)) for f in facts
        if f["fiscal_period"] is not None and _kind(f["unit"]) == "amount"}
    current: dict[tuple[Any, ...], list[Any]] = {}
    for row in rows:
        if row.is_latest and _kind(row.unit):
            current.setdefault((row.concept, row.period_end, row.fiscal_period), []).append(row)
    twins = {(row.concept, row.period_end, row.unit) for key, group in current.items() if key[2] is None for row in group}
    picks = dict(held)
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        if key not in held and (row.unit, row.accession) == own.get(key, ())[:2] and not any(
                other.is_latest and _filed(other.accession, other.provenance, dates, view) > own[key][2]
                for other in current.get(key, ())):
            picks[key] = row
    demoted = 0
    for key, row in picks.items():
        as_found = not _promotable(row) or row.fiscal_period in _QUARTERS and (
            row.concept, row.period_end, row.unit) in twins
        for other in current.get(key, ()):
            if other is not row and other.is_latest and (not as_found or other.id is None):
                other.is_latest = False  # with as_found, only this sync's own insert (no id before the flush)
                demoted += other.id is not None
        row.is_latest = row.is_latest or not as_found
    return demoted


def _replace_stale_ratios(facts: list[dict[str, Any]], rows: list[Any], currency: str,
                          held: Mapping[tuple[Any, ...], Any]) -> int:
    """Replace each current ratio computed from other-currency operands where the batch has its own.

    A ratio (``pure``) keeps its unit across currencies, so the upsert's filing-date rule (or ``Guard.later``)
    can keep one computed from other-currency operands (``_other_derived``) current and store the batch's
    calculation behind it: where the batch has its own calculation at that key, the stale row is
    demoted and the batch's promoted, unless the batch's calculation is quarantined (``_promotable``),
    when the stale ratio stays current. A protected ratio is never stale here: it is in the view
    (``_in_view``), and a key it holds (``held``) is left to ``_promote_batch_rows``. A ratio stored
    under the batch calculation's own identity is skipped by the upsert and left as it is; the
    journaled repair recomputes it. Returns how many rows were demoted.
    """
    ratios = {(f["concept"], f["period_end"], f["fiscal_period"]): f["accession"] for f in facts
              if f["unit"] == "pure" and _operand_unit(f.get("provenance")) == currency}
    groups: dict[tuple[Any, ...], list[Any]] = {}
    for row in rows:
        key = (row.concept, row.period_end, row.fiscal_period)
        if row.unit == "pure" and key in ratios and key not in held:
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
