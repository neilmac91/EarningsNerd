"""Filing-scoped financial fact read model."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models import Filing
from app.services.fact_provenance import provenance_for_fact, published_value
from app.services.facts.filing_scope import annual_filing_rows, filing_years


def _fundamentals_payload(
    ticker: str, company_name: str, rows, cik: str | None = None, years: dict[int, int | None] | None = None,
) -> dict[str, Any]:
    """Group flat ``FinancialFact`` rows into the FundamentalsResponse shape (per-concept series, in
    the order queried — oldest→newest), each point under ``years``' fiscal year for its row, if given."""
    series: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        series.setdefault(row.concept, []).append(
            {
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "fiscal_year": years[row.id] if years is not None else row.fiscal_year,
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

    Filing-scoped (roadmap B): the rows at the filing's company and accession, with **no** ``is_latest``
    filter (``filing_scope.annual_filing_rows``), so the chart shows the multi-year figures *this
    specific filing* disclosed (its comparative years) — an immutable snapshot faithful to the
    document, even if a later filing restated a period. Never keyed by ``filing_id`` alone: a
    companyfacts row stored first at the filing's identity holds that cell with no filing owner.
    Restricted to ``fiscal_period == "FY"`` (the annual-report periods — 10-K / 20-F / 40-F; see
    ``_fiscal_period``): a quarter under the same accession never shows as an annual bar, nor does a
    10-Q's FY-labelled prior year-end balance (``annual_filing_rows``). ``None`` when no such filing.
    """
    filing = (
        db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
    )
    if filing is None:
        return None

    company = filing.company
    rows = annual_filing_rows(db, filing)
    return _fundamentals_payload(
        (company.ticker if company else "") or "",
        (company.name if company else "") or "",
        rows,
        cik=company.cik if company else None,
        years=filing_years(rows),
    )
