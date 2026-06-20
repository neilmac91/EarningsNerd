"""Cross-company peer comparison from the normalized financial_fact table (P3/F3).

For a given company + concept, ranks the company against same-SIC peers using each
company's most recent ``is_latest`` value for that concept. This is the cross-company
read the ``financial_fact`` table was built for (see ``ix_financial_fact_peer`` on
``(concept, period_end)``) — a single indexed query, no live SEC calls.

Coverage is only as broad as the facts corpus: peers are limited to same-SIC companies
already present in our DB with facts for the concept, so results are sparse early and
grow as the backfill covers more companies. Peers may report on slightly different
fiscal calendars; we compare each company's most recent annual value.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Company
from app.models.financial_fact import FinancialFact

DEFAULT_CONCEPT = "revenue"


def _entry(company: Company, fact: FinancialFact, *, is_subject: bool) -> dict[str, Any]:
    return {
        "ticker": company.ticker,
        "company_name": company.name,
        "value": float(fact.value) if fact.value is not None else None,
        "period_end": fact.period_end.isoformat() if fact.period_end else None,
        "fiscal_year": fact.fiscal_year,
        "is_subject": is_subject,
        "rank": None,
        "percentile": None,
        "reconciled": bool(fact.reconciled),
    }


def get_peers(
    db: Session, ticker: str, concept: str = DEFAULT_CONCEPT
) -> Optional[dict[str, Any]]:
    """Rank a company against same-SIC peers on one concept.

    Returns ``None`` when the ticker isn't a known company. The subject is always
    included in the response (with null value/rank if it has no fact for the concept).
    """

    company = db.query(Company).filter(Company.ticker == (ticker or "").upper()).first()
    if company is None:
        return None

    concept = (concept or DEFAULT_CONCEPT).strip() or DEFAULT_CONCEPT

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
        )
        .order_by(FinancialFact.company_id.asc(), FinancialFact.period_end.desc())
        .all()
    )

    # Most recent fact per company (rows are period_end-desc within each company).
    latest: dict[int, tuple[Company, FinancialFact]] = {}
    for peer, fact in results:
        latest.setdefault(peer.id, (peer, fact))

    unit: Optional[str] = None
    entries: list[dict[str, Any]] = []
    for peer, fact in latest.values():
        unit = unit or fact.unit
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
    # Competition ranking: tied values share a rank (1 + #strictly-greater) and percentile
    # (#strictly-below / (m-1)), so equal companies are treated identically instead of being
    # split into adjacent ranks by their arbitrary index.
    values = [e["value"] for e in ranked if e["value"] is not None]
    m = len(values)
    subject: Optional[dict[str, Any]] = None
    for entry in ranked:
        v = entry["value"]
        if v is not None:
            entry["rank"] = sum(1 for o in values if o > v) + 1
            entry["percentile"] = (
                round(sum(1 for o in values if o < v) / (m - 1) * 100, 1) if m > 1 else 100.0
            )
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
