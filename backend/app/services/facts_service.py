"""Normalize the standardized XBRL metrics we already extract into queryable `financial_fact` rows.

`normalize_standardized_to_facts` is pure (dict in → list[dict] out, unit-testable). `upsert_facts`
writes them while maintaining the restatement-safe `is_latest` flag.

v1 sources only the current period each filing reports, attributed to that filing's accession —
accurate and dependency-free (it reuses `xbrl_service.extract_standardized_metrics`). Deeper history
+ cross-source backfill (companyfacts / FSDS / Frames) and the reconciliation gate (cross-check vs
`data.sec.gov`) are later P3 waves.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.financial_fact import FinancialFact

logger = logging.getLogger(__name__)

# Standardized concept (from xbrl_service.extract_standardized_metrics) → unit. Anything unmapped
# defaults to USD (the dominant case); margins are ratios ("pure"), per-share metrics are USD/shares.
_CONCEPT_UNITS: dict[str, str] = {
    "revenue": "USD",
    "net_income": "USD",
    "gross_profit": "USD",
    "operating_income": "USD",
    "total_assets": "USD",
    "cash_and_equivalents": "USD",
    "operating_cash_flow": "USD",
    "capital_expenditures": "USD",
    "free_cash_flow": "USD",
    "shareholders_equity": "USD",
    "long_term_debt": "USD",
    "earnings_per_share": "USD/shares",
    "eps_diluted": "USD/shares",
    "net_margin": "pure",
    "gross_margin": "pure",
    "operating_margin": "pure",
}


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _fiscal_period(form: Optional[str]) -> Optional[str]:
    # A 10-K reports the full fiscal year; for a 10-Q the quarter can't be inferred from the period
    # alone, so leave it unset rather than guess.
    return "FY" if (form or "").upper().replace("-", "").startswith("10K") else None


def normalize_standardized_to_facts(
    company_id: int,
    filing_id: Optional[int],
    accession: Optional[str],
    form: Optional[str],
    standardized: Optional[dict],
) -> list[dict[str, Any]]:
    """Turn standardized metrics into fact dicts for the filing's currently-reported period.

    One row per concept (the ``current`` entry), attributed to this filing's accession. Tolerant of
    missing/malformed entries (skipped, never raised).
    """
    if not accession or not isinstance(standardized, dict):
        return []
    fiscal_period = _fiscal_period(form)
    facts: list[dict[str, Any]] = []
    for concept, entry in standardized.items():
        if not isinstance(entry, dict):
            continue
        current = entry.get("current")
        if not isinstance(current, dict):
            continue
        value = current.get("value")
        # Exclude bool (a subclass of int) and non-numeric values.
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        period_end = _parse_date(current.get("period"))
        if period_end is None:
            continue
        facts.append(
            {
                "company_id": company_id,
                "filing_id": filing_id,
                "concept": concept,
                "unit": _CONCEPT_UNITS.get(concept, "USD"),
                "period_end": period_end,
                "fiscal_year": period_end.year,
                "fiscal_period": fiscal_period,
                "value": float(value),
                "form": form,
                "accession": accession,
                "source": "edgar_xbrl",
            }
        )
    return facts


def upsert_facts(db: Session, facts: list[dict[str, Any]]) -> dict[str, int]:
    """Insert fact rows, maintaining ``is_latest``. Idempotent on the full identity key.

    For each fact: if a row with the same (company, concept, period_end, fiscal_period, unit,
    accession) already exists, skip it. Otherwise demote any current ``is_latest`` row for the same
    (company, concept, period_end, fiscal_period, unit) and insert this one as latest. Callers should
    upsert in chronological order so the newest reported / restated value wins ``is_latest``.
    """
    inserted = 0
    skipped = 0
    for fact in facts:
        if (
            db.query(FinancialFact.id)
            .filter_by(
                company_id=fact["company_id"],
                concept=fact["concept"],
                period_end=fact["period_end"],
                fiscal_period=fact["fiscal_period"],
                unit=fact["unit"],
                accession=fact["accession"],
            )
            .first()
        ):
            skipped += 1
            continue

        # Demote the prior current value for this (company, concept, period, fiscal_period, unit).
        db.query(FinancialFact).filter_by(
            company_id=fact["company_id"],
            concept=fact["concept"],
            period_end=fact["period_end"],
            fiscal_period=fact["fiscal_period"],
            unit=fact["unit"],
            is_latest=True,
        ).update({"is_latest": False})

        db.add(FinancialFact(**fact, is_latest=True, reconciled=False))
        inserted += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped}
