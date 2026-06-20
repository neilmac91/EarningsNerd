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

    # Peer set: same SIC. Falls back to just the subject when SIC is unknown.
    if company.sic:
        peers = db.query(Company).filter(Company.sic == company.sic).all()
    else:
        peers = [company]
    company_by_id = {c.id: c for c in peers}

    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.company_id.in_(list(company_by_id.keys())),
            FinancialFact.concept == concept,
            FinancialFact.is_latest.is_(True),
        )
        .order_by(FinancialFact.company_id.asc(), FinancialFact.period_end.desc())
        .all()
    )

    # Most recent fact per company (rows are period_end-desc within each company).
    latest: dict[int, FinancialFact] = {}
    for row in rows:
        latest.setdefault(row.company_id, row)

    unit: Optional[str] = None
    entries: list[dict[str, Any]] = []
    for cid, fact in latest.items():
        unit = unit or fact.unit
        entries.append(_entry(company_by_id[cid], fact, is_subject=cid == company.id))

    # Rank by value descending (companies without a value sort last).
    ranked = sorted(
        entries,
        key=lambda e: (e["value"] is not None, e["value"] if e["value"] is not None else 0.0),
        reverse=True,
    )
    n = len(ranked)
    subject: Optional[dict[str, Any]] = None
    for i, entry in enumerate(ranked):
        entry["rank"] = i + 1
        entry["percentile"] = round((n - (i + 1)) / (n - 1) * 100, 1) if n > 1 else 100.0
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
