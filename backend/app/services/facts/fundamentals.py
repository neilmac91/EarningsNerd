"""Filing-scoped financial fact read model."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Filing, FinancialFact
from app.services.fact_provenance import provenance_for_fact, published_value


def _fundamentals_payload(ticker: str, company_name: str, rows, cik: str | None = None) -> dict[str, Any]:
    """Group flat ``FinancialFact`` rows into the FundamentalsResponse shape (per-concept series, in
    the order queried — oldest→newest). Shared by the company- and filing-scoped readers."""
    series: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        series.setdefault(row.concept, []).append(
            {
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "value": published_value(row),
                "unit": row.unit,
                "form": row.form,
                "accession": row.accession,
                "reconciled": bool(row.reconciled),
                "provenance": provenance_for_fact(row, cik),
            }
        )
    return {
        "ticker": ticker,
        "company_name": company_name,
        "concepts": [
            {"concept": concept, "unit": points[0]["unit"], "points": points}
            for concept, points in series.items()
        ],
    }


def get_filing_fundamentals(db: Session, filing_id: int) -> Optional[dict[str, Any]]:
    """Annual (FY) facts **as reported in a single filing**, grouped into per-concept time-series.

    Filing-scoped (roadmap B): keyed by ``filing_id`` with **no** ``is_latest`` filter, so the chart
    shows the multi-year figures *this specific filing* disclosed (its comparative years) — an
    immutable snapshot faithful to the document, even if a later filing restated a period. Restricted
    to ``fiscal_period == "FY"`` (the annual-report periods — 10-K / 20-F / 40-F; see
    ``_fiscal_period``): the backfill ingests every XBRL-bearing filing, so a company that has filed
    10-Qs also carries quarterly facts (``fiscal_period`` is ``None``), and without this filter a
    3-month quarterly value would surface alongside the full-year value for the same ``fiscal_year`` —
    a quarterly bar masquerading as an annual one under the chart's "Annual figures" label. Returns
    ``None`` when the filing doesn't exist.
    """
    filing = (
        db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
    )
    if filing is None:
        return None

    rows = (
        db.query(FinancialFact)
        .filter(
            FinancialFact.filing_id == filing_id,
            FinancialFact.fiscal_period == "FY",
        )
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.asc())
        .all()
    )

    company = filing.company
    return _fundamentals_payload(
        (company.ticker if company else "") or "",
        (company.name if company else "") or "",
        rows,
        cik=company.cik if company else None,
    )
