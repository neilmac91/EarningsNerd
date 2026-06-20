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

from app.models import Company, Filing, FinancialFact

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


def backfill_facts(db: Session, extract=None, limit: Optional[int] = None) -> dict[str, int]:
    """Populate ``financial_fact`` from filings that already carry ``xbrl_data``.

    Reuses the standardized-metrics extractor + the pure normalizer + the writer. Idempotent
    (``upsert_facts`` skips rows that already exist). Filings are processed oldest-first so the
    newest reported value wins ``is_latest``. ``extract`` is injectable for tests.
    """
    if extract is None:
        from app.services.edgar.compat import xbrl_service

        extract = xbrl_service.extract_standardized_metrics

    query = (
        db.query(Filing)
        .filter(Filing.xbrl_data.isnot(None))
        .order_by(Filing.filing_date.asc())
    )
    if limit:
        query = query.limit(limit)

    processed = 0
    inserted = 0
    skipped = 0
    errors = 0
    for filing in query.all():
        try:
            standardized = extract(filing.xbrl_data)
        except Exception:
            logger.exception("facts backfill: extract failed for filing %s", filing.id)
            errors += 1
            continue
        facts = normalize_standardized_to_facts(
            filing.company_id, filing.id, filing.accession_number, filing.filing_type, standardized
        )
        result = upsert_facts(db, facts)
        inserted += result["inserted"]
        skipped += result["skipped"]
        processed += 1

    return {
        "filings_processed": processed,
        "facts_inserted": inserted,
        "facts_skipped": skipped,
        "extract_errors": errors,
    }


def get_fundamentals(db: Session, ticker: str) -> Optional[dict[str, Any]]:
    """Current (``is_latest``) facts for a ticker, grouped into per-concept time-series.

    Returns ``None`` when the ticker isn't a known company. Each concept's points are ordered oldest
    → newest so a chart can render the trend directly.
    """
    company = db.query(Company).filter(Company.ticker == (ticker or "").upper()).first()
    if company is None:
        return None

    rows = (
        db.query(FinancialFact)
        .filter(FinancialFact.company_id == company.id, FinancialFact.is_latest.is_(True))
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.asc())
        .all()
    )

    series: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        series.setdefault(row.concept, []).append(
            {
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period,
                "value": float(row.value) if row.value is not None else None,
                "unit": row.unit,
                "form": row.form,
                "accession": row.accession,
            }
        )

    return {
        "ticker": company.ticker,
        "company_name": company.name,
        "concepts": [
            {"concept": concept, "unit": points[0]["unit"], "points": points}
            for concept, points in series.items()
        ],
    }
