"""Weekly data-quality report (P1-9): the recurrence umbrella over the remediation's detections.

Four sections, each an ORM reimplementation of a committed ``ops/detection/*.sql`` probe (the SQL
stays the read-only ops-console spec; app code is ORM-only per CLAUDE.md):

  (a) ticker integrity   — every ``companies.ticker`` diffed against the SEC primary-per-CIK ticker
                           (mismatch = P0-1 corruption; not-in-file = delisted, informational)
  (b) coverage gaps      — a company whose last fiscal year for a concept lags its last total_assets
                           year by ≥2 (the P0-3 cash-gap generalized to four core concepts)
  (c) filing anomalies   — deep fact history (≥5 fiscal years) but ≤2 stored 10-K rows (P1-6 signal)
  (d) partial reasons    — tier="partial" summary quality reasons, bucketed by SIC prefix (P0-2)

``build_report`` returns a plain dict (JSON-friendly, unit-testable without email); ``run_and_email``
renders it and sends to ``settings.DATA_QUALITY_REPORT_EMAIL``.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, Filing, FinancialFact, Summary

logger = logging.getLogger(__name__)

# Core concepts whose coverage should track total_assets (the always-present balance-sheet anchor).
_COVERAGE_CONCEPTS = ("cash_and_equivalents", "shareholders_equity", "operating_cash_flow")
_ANCHOR_CONCEPT = "total_assets"
_COVERAGE_LAG_YEARS = 2  # flag when a concept's last FY lags total_assets by this many years
_ANOMALY_MIN_SPAN = 5    # ≥ this many fiscal years of facts …
_ANOMALY_MAX_10K = 2     # … but ≤ this many stored 10-K rows


async def ticker_integrity(db: Session) -> dict[str, list[dict]]:
    """Section (a): diff each company's stored ticker against the SEC primary-per-CIK ticker."""
    from app.services.edgar.compat import sec_edgar_service

    mismatches: list[dict] = []
    not_in_file: list[dict] = []
    for ticker, cik in db.query(Company.ticker, Company.cik).order_by(Company.ticker).all():
        primary = await sec_edgar_service.primary_ticker_for_cik(cik)
        if primary is None:
            not_in_file.append({"ticker": ticker, "cik": cik})
        elif ticker != primary:
            mismatches.append({"ticker": ticker, "primary": primary, "cik": cik})
    return {"mismatches": mismatches, "not_in_file": not_in_file}


def coverage_gaps(db: Session) -> list[dict]:
    """Section (b): companies whose last FY for a core concept lags their last total_assets FY."""
    concepts = (*_COVERAGE_CONCEPTS, _ANCHOR_CONCEPT)
    rows = (
        db.query(Company.id, Company.ticker, FinancialFact.concept, func.max(FinancialFact.fiscal_year))
        .join(FinancialFact, FinancialFact.company_id == Company.id)
        .filter(
            FinancialFact.is_latest,
            FinancialFact.fiscal_period == "FY",
            FinancialFact.concept.in_(concepts),
        )
        .group_by(Company.id, Company.ticker, FinancialFact.concept)
        .all()
    )
    # Keyed by company id (not ticker) so a stray duplicate ticker can't merge two companies' facts.
    by_company: dict[int, dict[str, Any]] = {}
    for company_id, ticker, concept, last_fy in rows:
        if last_fy is not None:
            entry = by_company.setdefault(company_id, {"ticker": ticker, "concepts": {}})
            entry["concepts"][concept] = int(last_fy)

    gaps: list[dict] = []
    for entry in by_company.values():
        anchor_fy = entry["concepts"].get(_ANCHOR_CONCEPT)
        if anchor_fy is None:
            continue  # no total_assets anchor → nothing to measure against
        for concept in _COVERAGE_CONCEPTS:
            last_fy = entry["concepts"].get(concept, 0)  # absent concept → year 0 → always flagged
            if anchor_fy - last_fy >= _COVERAGE_LAG_YEARS:
                gaps.append({
                    "ticker": entry["ticker"], "concept": concept,
                    "last_fy": last_fy or None, "last_total_assets_fy": anchor_fy,
                })
    gaps.sort(key=lambda g: (g["concept"], g["ticker"]))
    return gaps


def filing_anomalies(db: Session) -> list[dict]:
    """Section (c): deep fact history (≥ _ANOMALY_MIN_SPAN fiscal years) but ≤ _ANOMALY_MAX_10K
    stored 10-K rows — the recent-window-ingestion signature."""
    spans = (
        db.query(
            Company.id, Company.ticker,
            func.min(FinancialFact.fiscal_year), func.max(FinancialFact.fiscal_year),
        )
        .join(FinancialFact, FinancialFact.company_id == Company.id)
        .filter(FinancialFact.is_latest, FinancialFact.fiscal_period == "FY")
        .group_by(Company.id, Company.ticker)
        .all()
    )
    tenk_counts = dict(
        db.query(Filing.company_id, func.count(distinct(Filing.id)))
        .filter(Filing.filing_type == "10-K")
        .group_by(Filing.company_id)
        .all()
    )
    anomalies: list[dict] = []
    for company_id, ticker, first_fy, last_fy in spans:
        if first_fy is None or last_fy is None:
            continue
        span = int(last_fy) - int(first_fy)
        stored_10k = int(tenk_counts.get(company_id, 0))
        if span >= _ANOMALY_MIN_SPAN and stored_10k <= _ANOMALY_MAX_10K:
            anomalies.append({
                "ticker": ticker, "first_fact_fy": int(first_fy),
                "last_fact_fy": int(last_fy), "stored_10k_rows": stored_10k,
            })
    anomalies.sort(key=lambda a: (-(a["last_fact_fy"] - a["first_fact_fy"]), a["ticker"]))
    return anomalies


def partial_reason_counts(db: Session) -> list[dict]:
    """Section (d): tier="partial" summary quality reasons, counted by SIC-prefix bucket.

    ``raw_summary`` is a JSON column → a dict in Python, so the tier filter + reason explode happen
    in Python (portable across Postgres/SQLite; no jsonb operators in app code)."""
    # Filter to partial-tier summaries IN THE DB (portable JSON path — verified on Postgres +
    # SQLite) so we never load every full AI response into memory. The reasons array is still
    # exploded in Python (jsonb_array_elements has no clean cross-dialect ORM form).
    rows = (
        db.query(Company.sic, Summary.raw_summary)
        .join(Filing, Filing.id == Summary.filing_id)
        .join(Company, Company.id == Filing.company_id)
        .filter(Summary.raw_summary["quality"]["tier"].as_string() == "partial")
        .all()
    )
    counter: Counter = Counter()
    for sic, raw in rows:
        quality = (raw or {}).get("quality") if isinstance(raw, dict) else None
        if not isinstance(quality, dict):
            continue  # defensive: the DB filter already enforced tier == "partial"
        bucket = (str(sic)[:2] if sic else "") or "null"
        for reason in quality.get("reasons") or []:
            counter[(bucket, str(reason))] += 1
    return [
        {"sic_prefix": bucket, "reason": reason, "count": n}
        for (bucket, reason), n in counter.most_common()
    ]


async def build_report(db: Session) -> dict[str, Any]:
    """Assemble all four sections into a JSON-friendly dict."""
    tickers = await ticker_integrity(db)
    return {
        "ticker_mismatches": tickers["mismatches"],
        "ticker_not_in_file": tickers["not_in_file"],
        "coverage_gaps": coverage_gaps(db),
        "filing_anomalies": filing_anomalies(db),
        "partial_reasons": partial_reason_counts(db),
    }


async def run_and_email(db: Session) -> dict[str, Any]:
    """Build the report and email it to the founder. Returns the report dict (also useful for a
    dry run / the workflow step summary)."""
    from app.services import email_service, resend_service

    report = await build_report(db)
    html, text = email_service.render_data_quality_report(report)
    to = settings.DATA_QUALITY_REPORT_EMAIL
    await resend_service.send_email(
        to=[to],
        subject="EarningsNerd data-quality report",
        html=f'{html}<pre style="display:none">{text}</pre>',
    )
    logger.info(
        "Data-quality report emailed to %s: %d ticker mismatches, %d coverage gaps, %d filing "
        "anomalies, %d partial-reason rows",
        to, len(report["ticker_mismatches"]), len(report["coverage_gaps"]),
        len(report["filing_anomalies"]), len(report["partial_reasons"]),
    )
    return report
