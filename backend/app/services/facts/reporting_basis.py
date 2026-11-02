"""Which taxonomy a filer reports under now, and what a companyfacts sync does when it is IFRS.

The companyfacts sync reads us-gaap only. An IFRS filer is one whose payload carries ifrs-full data and
either no us-gaap data, or a latest original periodic report (a 10-K, 10-Q, 20-F or 40-F; amendments
aside, as one may carry little more than its cover) that tags more of its items under ifrs-full than
under us-gaap. The second shape is a filer that moved to IFRS: Toyota from the year ended 2021-03-31,
Itau after 2010. Its us-gaap history stops years before its current reports. Read as a series, that
history would present its last US-GAAP year as the company's latest figures (Multi-Period Analysis, the
peers endpoint), where the filer has reported under IFRS since. A 10-Q counts because a filer that moves
from IFRS to US GAAP may file US-GAAP 10-Qs before its first 10-K (Flutter: IFRS 40-Fs, then 10-Qs from
2024-05, then a 10-K in 2025-03), and an IFRS filer files no 10-Q.

So a sync for an IFRS filer stores nothing (``normalize_companyfacts`` returns no facts) and retires
from current use the series earlier companyfacts syncs stored for it (``retire_ifrs_series``): its rows
with no filing owner, reported (``companyfacts``) or calculated from them (``derived``). Nothing is
deleted, and rows another writer stored under a filing stay as they are: a filing's own figures, which
each filing keeps readable by accession (the Copilot's ``_scope`` ignores ``is_latest``). That includes
a row the per-filing writer stores later from one of the filer's earlier US-GAAP reports when a reader
summarizes it (TM's 2019 20-F; the last one's rows are the series' own identities, which it skips): the key
then holds no current row, so that report's own year can read as current again until a stored basis lets
the writer store it behind (E287). A payload with no ifrs-full data (every domestic filer) never reaches
the count, so its sync is unchanged. A filer that moves back to US GAAP reads its new reports' years as
current, as its next sync stores them. The years the retire left behind stay non-current, since a sync
skips an identity it holds, except a non-USD filer's amounts: a sync outside USD re-promotes the batch's
own stored rows (``currency.py``), though not their ratios. Restoring them needs the same stored basis (E287).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # the normalizer imports this module and must load no ORM (see ``retire_ifrs_series``)
    from sqlalchemy.orm import Session

# The original periodic reports whose taxonomy decides the basis. Amendments are left out: a 20-F/A or
# 10-K/A may tag only its cover page or a restated note, which says nothing about how the filer reports now.
BASIS_FORMS = frozenset({"10-K", "10-Q", "20-F", "40-F"})
COMPANYFACTS_SOURCES = ("companyfacts", "derived")


def _items(taxonomy: Any):
    """Every item a taxonomy's concepts carry, in any unit (malformed parts are skipped)."""
    for concept in (taxonomy or {}).values() if isinstance(taxonomy, dict) else ():
        units = concept.get("units") if isinstance(concept, dict) else None
        for items in (units or {}).values() if isinstance(units, dict) else ():
            yield from (item for item in (items if isinstance(items, list) else ()) if isinstance(item, dict))


def latest_periodic_report(facts_root: dict) -> tuple[str, str] | None:
    """``(filed, accession)`` of the latest original periodic report that us-gaap or ifrs-full items name, or ``None``.

    Ties on the filing date break toward the higher accession, as the writers break a same-day tie.
    """
    reports = {
        (item["filed"], item["accn"])
        for taxonomy in ("us-gaap", "ifrs-full")
        for item in _items(facts_root.get(taxonomy))
        if item.get("form") in BASIS_FORMS and isinstance(item.get("filed"), str) and isinstance(item.get("accn"), str)
    }
    return max(reports) if reports else None


def reports_under_ifrs(facts_root: Any) -> bool:
    """Whether a companyfacts payload's ``facts`` object is an IFRS filer's (module docstring)."""
    if not isinstance(facts_root, dict) or not isinstance(facts_root.get("ifrs-full"), dict):
        return False
    usgaap = facts_root.get("us-gaap")
    if not isinstance(usgaap, dict) or not usgaap:
        return True
    latest = latest_periodic_report(facts_root)
    if latest is None:
        return False

    def tagged(taxonomy: str) -> int:
        return sum(1 for item in _items(facts_root.get(taxonomy)) if item.get("accn") == latest[1])

    return tagged("ifrs-full") > tagged("us-gaap")


def retire_ifrs_series(db: Session, company_id: int, meta: dict) -> int:
    """Retire an IFRS filer's companyfacts series from current use (module docstring); return the count.

    A no-op returning 0 unless ``meta`` (``normalize_companyfacts``) names the payload an IFRS filer's.
    Runs in the sync's transaction, which commits it. It takes the company row first, as every fact
    writer does (``_lock_fact_companies``): an IFRS sync reaches no other lock, and updating fact rows
    before the company row would invert the per-filing writer's order. The ORM is imported here, not
    at module level: ``normalize_companyfacts`` imports this module and loads no Settings, ORM or EDGAR code.
    """
    if not meta.get("unsupported_ifrs"):
        return 0
    from app.models import FinancialFact
    from app.services.facts.upsert import _lock_fact_companies

    _lock_fact_companies(db, [{"company_id": company_id}])
    return (
        db.query(FinancialFact)
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.is_latest.is_(True),
            FinancialFact.filing_id.is_(None),
            FinancialFact.source.in_(COMPANYFACTS_SOURCES),
        )
        .update({FinancialFact.is_latest: False})
    )
