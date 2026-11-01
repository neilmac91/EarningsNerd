"""Cross-company peer comparison from the normalized financial_fact table (P3/F3).

For a given company + concept, ranks the company against same-SIC peers using each
company's most recent ``is_latest`` value for that concept. This is the cross-company
read the ``financial_fact`` table was built for (see ``ix_financial_fact_peer`` on
``(concept, period_end)``) — a single indexed query, no live SEC calls.

Coverage is only as broad as the facts corpus: peers are limited to same-SIC companies
already present in our DB with facts for the concept, so results are sparse early and
grow as the backfill covers more companies. Peers may report on slightly different
fiscal calendars; we compare each company's most recent annual value.

Two rules keep a ranking comparable (F69, D-072). An industry ranks on one figure: a request
for the default concept ranks a commercial bank or savings institution on net interest income
and every other company on revenue, whatever the company itself stores. And a figure whose
period ended more than ``MAX_FIGURE_LAG`` before the newest figure in its group leaves the
ranking, the subject's included, so a company that stopped filing a concept is not ranked on
its last figure beside current ones.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Company
from app.models.financial_fact import FinancialFact
from app.services.facts_service import _unit_for
from app.services.fact_provenance import provenance_for_fact, published_value

DEFAULT_CONCEPT = "revenue"

# The SIC codes whose companies rank on net interest income by default: commercial banks (6021 national,
# 6022 state, 6029 not elsewhere classified) and savings institutions (6035 federally chartered, 6036 not).
# Net interest income is a bank's top line on /analysis too, and the facts layer keeps it current for every
# bank; every other code, broker-dealers (6211) included, ranks on revenue (F69, D-072).
NET_INTEREST_INCOME_SICS = frozenset({"6021", "6022", "6029", "6035", "6036"})

# How far a figure's period end may trail the newest in its group and still rank (F69, D-072). Fiscal
# calendars and filing deadlines put current annual figures up to about fifteen months apart (a 20-F filer's
# year beside a fast 10-K filer's); a company that stopped filing a concept trails by years.
MAX_FIGURE_LAG = timedelta(days=548)


def default_concept_for(sic: Optional[str]) -> str:
    """The concept a request for the default ranks on: net interest income for a commercial bank or savings
    institution, revenue for every other company."""
    return "net_interest_income" if (sic or "").strip() in NET_INTEREST_INCOME_SICS else DEFAULT_CONCEPT


def _entry(company: Company, fact: FinancialFact, *, is_subject: bool) -> dict[str, Any]:
    return {
        "ticker": company.ticker,
        "company_name": company.name,
        "value": published_value(fact),
        "period_end": fact.period_end.isoformat() if fact.period_end else None,
        "fiscal_year": fact.fiscal_year,
        "is_subject": is_subject,
        "rank": None,
        "percentile": None,
        "reconciled": provenance_for_fact(fact)["validation"] == "passed",
        "provenance": provenance_for_fact(fact, getattr(company, "cik", None)),
    }


def get_peers(
    db: Session, ticker: str, concept: str = DEFAULT_CONCEPT
) -> Optional[dict[str, Any]]:
    """Rank a company against same-SIC peers on one concept.

    Returns ``None`` when the ticker isn't a known company. The subject is always
    included in the response (with null value/rank if it has no fact for the concept,
    or if its figure trails the group's newest by more than ``MAX_FIGURE_LAG``).
    """

    company = db.query(Company).filter(Company.ticker == (ticker or "").upper()).first()
    if company is None:
        return None

    concept = (concept or DEFAULT_CONCEPT).strip() or DEFAULT_CONCEPT

    # One figure per industry (F69, D-072): the default ranks a commercial bank or savings institution on
    # net interest income and every other company on revenue, decided by the subject's SIC code alone, so
    # every page of one industry answers the same ranking. A company that stores no figure on its
    # industry's concept shows none; it never switches the page to another figure.
    if concept == DEFAULT_CONCEPT:
        concept = default_concept_for(company.sic)

    # Currency guard: a ranking is only meaningful within ONE currency — a CNY revenue is
    # ~7x a USD one, so a foreign private issuer (which now stores native-currency facts,
    # e.g. unit="CNY") must never be ranked head-to-head against USD filers in the same SIC.
    # We constrain the cohort to the subject's own reporting currency for this concept:
    #   • monetary concepts (unit "USD"/"CNY"/…) → like-for-like (a USD subject excludes FPIs;
    #     a CNY subject ranks only against other CNY filers, usually itself → panel hides),
    #   • per-share ("USD/shares"/"CNY/shares") → same,
    #   • dimensionless margins ("pure", currency-blind) → all filers share unit "pure", so
    #     a margin cohort naturally spans every currency, which is correct for a ratio.
    # `_unit_for(concept, None)` gives the concept's default unit (USD/USD-shares/pure) for a
    # subject that has no fact yet, so a domestic subject still ranks against its USD peers.
    subject_unit_row = (
        db.query(FinancialFact.unit)
        .filter(
            FinancialFact.company_id == company.id,
            FinancialFact.concept == concept,
            FinancialFact.fiscal_period == "FY",
            FinancialFact.is_latest.is_(True),
        )
        .order_by(FinancialFact.period_end.desc())
        .first()
    )
    # `unit` is NOT NULL on the model, but guard a NULL-valued row defensively so a bad datum
    # can never make the whole cohort fall through to an empty unit filter.
    subject_unit = (subject_unit_row[0] if subject_unit_row else None) or _unit_for(concept, None)

    # Same-SIC companies that have a fact for this concept, in one JOIN — avoids a
    # large IN list and never loads companies without facts. A subject with no fact
    # is still surfaced by the fallback below, since `company` is already fetched.
    # (When SIC is unknown, scope to the subject alone — `sic == NULL` matches nothing.)
    sic_filter = Company.sic == company.sic if company.sic else Company.id == company.id
    results = (
        db.query(Company, FinancialFact)
        .join(FinancialFact, FinancialFact.company_id == Company.id)
        .filter(
            sic_filter,
            FinancialFact.concept == concept,
            # Annual only. A 10-Q value (fiscal_period NULL) must never be ranked against a
            # peer's 10-K annual value. `is_latest` is keyed per period_end, so a filer can
            # hold both an annual and a *later* quarterly is_latest row — without this filter
            # the period_end-desc pick below would surface the quarterly figure for filers
            # that have one and the annual for those that don't (apples-to-oranges).
            FinancialFact.fiscal_period == "FY",
            FinancialFact.is_latest.is_(True),
            # One currency per ranking (see comment above).
            FinancialFact.unit == subject_unit,
        )
        .order_by(FinancialFact.company_id.asc(), FinancialFact.period_end.desc())
        .all()
    )

    # Most recent fact per company (rows are period_end-desc within each company).
    latest: dict[int, tuple[Company, FinancialFact]] = {}
    for peer, fact in results:
        latest.setdefault(peer.id, (peer, fact))

    # Recency (F69, D-072): a company whose most recent figure ended more than MAX_FIGURE_LAG before the
    # group's newest leaves the ranking before anything is counted, the subject's figure included (the
    # subject is then surfaced without a value below). Measured from the group's own newest figure, so
    # the answer needs no clock and a group whose filers all lag keeps its ranking.
    if latest:
        floor = max(fact.period_end for _, fact in latest.values()) - MAX_FIGURE_LAG
        latest = {cid: pair for cid, pair in latest.items() if pair[1].period_end >= floor}

    # The cohort is now single-currency by construction, so the response unit is the
    # subject's unit (not "whichever fact iterated first" — which could differ once the
    # corpus mixes currencies). The frontend formats values with this currency.
    unit: Optional[str] = subject_unit
    entries: list[dict[str, Any]] = []
    for peer, fact in latest.values():
        entries.append(_entry(peer, fact, is_subject=peer.id == company.id))

    # Deterministic order: companies with a value first, value descending, then ticker as a
    # stable tie-break so dict-iteration order can never leak into the ranking.
    ranked = sorted(
        entries,
        key=lambda e: (
            e["value"] is None,
            -e["value"] if e["value"] is not None else 0.0,
            e["ticker"] or "",
        ),
    )
    n = len(ranked)
    # Competition ranking: tied values share a rank and percentile, so equal companies are
    # treated identically instead of being split into adjacent ranks by their arbitrary index.
    # `values` is already value-descending, so a value's first index == the count strictly
    # above it (its rank-1) and #strictly-below == m - first_index - frequency. Precomputing
    # both in one pass keeps this O(n) rather than rescanning `values` per entry.
    values = [e["value"] for e in ranked if e["value"] is not None]
    m = len(values)
    first_index: dict[float, int] = {}
    frequency: dict[float, int] = {}
    for idx, val in enumerate(values):
        first_index.setdefault(val, idx)
        frequency[val] = frequency.get(val, 0) + 1
    subject: Optional[dict[str, Any]] = None
    for entry in ranked:
        v = entry["value"]
        if v is not None:
            entry["rank"] = first_index[v] + 1
            below = m - first_index[v] - frequency[v]
            entry["percentile"] = round(below / (m - 1) * 100, 1) if m > 1 else 100.0
        if entry["is_subject"]:
            subject = entry

    # The subject may not have a fact for this concept yet — surface it explicitly.
    if subject is None:
        subject = {
            "ticker": company.ticker,
            "company_name": company.name,
            "value": None,
            "period_end": None,
            "fiscal_year": None,
            "is_subject": True,
            "rank": None,
            "percentile": None,
            "reconciled": True,  # no value to flag
        }

    return {
        "ticker": company.ticker,
        "company_name": company.name,
        "sic": company.sic,
        "concept": concept,
        "unit": unit,
        "peer_count": n,
        "subject": subject,
        "peers": ranked,
    }
