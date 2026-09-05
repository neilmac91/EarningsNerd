"""Weekly data-quality report (P1-9): the recurrence umbrella over the remediation's detections.

The original four sections are ORM reimplementations of a committed ``ops/detection/*.sql`` probe (the SQL
stays the read-only ops-console spec; app code is ORM-only per CLAUDE.md):

  (a) ticker integrity   — every ``companies.ticker`` diffed against the SEC primary-per-CIK ticker
                           (mismatch = P0-1 corruption; not-in-file = delisted, informational)
  (b) coverage gaps      — a company whose last fiscal year for a concept lags its last total_assets
                           year by ≥2 (the P0-3 cash-gap generalized to four core concepts)
  (c) filing anomalies   — deep fact history (≥5 fiscal years) but ≤2 stored 10-K rows (P1-6 signal)
  (d) partial reasons    — tier="partial" summary quality reasons, bucketed by SIC prefix (P0-2)

Universe coverage, summary-less filing ratio, source-list age and durable job health complete the
report.

``build_report`` returns a plain dict (JSON-friendly, unit-testable without email); ``run_and_email``
renders it and sends to ``settings.DATA_QUALITY_REPORT_EMAIL``.
"""
from __future__ import annotations

import logging
import html
import math
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Company, Filing, FinancialFact, Summary
from app.services import index_membership_service
from app.services.job_run_service import job_health
from app.utils.datetimes import utcnow

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

    Project only the reasons JSON after filtering tier in the DB; explode/deduplicate per
    snapshot in Python (portable across Postgres/SQLite; no raw SQL)."""
    # Filter to partial-tier summaries IN THE DB (portable JSON path — verified on Postgres +
    # SQLite) so we never load every full AI response into memory. The reasons array is still
    # exploded in Python (jsonb_array_elements has no clean cross-dialect ORM form).
    rows = (
        db.query(Company.sic, Summary.raw_summary["quality"]["reasons"])
        .join(Filing, Filing.id == Summary.filing_id)
        .join(Company, Company.id == Filing.company_id)
        .filter(Summary.raw_summary["quality"]["tier"].as_string() == "partial")
        .all()
    )
    counter: Counter = Counter()
    for sic, reasons in rows:
        if not _string_list(reasons):
            continue
        bucket = (str(sic)[:2] if sic else "") or "null"
        for reason in set(reasons):
            counter[(bucket, reason)] += 1
    return [
        {"sic_prefix": bucket, "reason": reason, "count": n}
        for (bucket, reason), n in counter.most_common()
    ]


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _counter(value: Any) -> bool:
    return type(value) is int and value >= 0


def _record_list(value: Any, *, strings: tuple[str, ...], score: bool = False) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, dict) and all(isinstance(item.get(key), str) for key in strings)
        and (not score or (type(item.get("score")) in (int, float)
                           and math.isfinite(item["score"]) and 0 <= item["score"] <= 100))
        for item in value
    )


def _forward_counts(audit: Any) -> dict[str, int] | None:
    if not isinstance(audit, dict) or not all(
        _counter(audit.get(key)) for key in ("checked", "verified", "near_miss")
    ) or type(audit.get("armed")) is not bool:
        return None
    if not (_record_list(audit.get("unverified"), strings=("speaker",), score=True)
            and _record_list(audit.get("dropped"), strings=("speaker", "quote"))):
        return None
    checked, verified, near = (audit[k] for k in ("checked", "verified", "near_miss"))
    unverified, dropped = len(audit["unverified"]), len(audit["dropped"])
    if (verified + unverified != checked or near > unverified or dropped > unverified
            or dropped != (unverified if audit["armed"] else 0)):
        return None
    return {"checked": checked, "verified": verified, "unverified": unverified,
            "near_miss": near, "other_unverified": unverified - near, "dropped": dropped}


def _snap_counts(audit: Any) -> dict[str, int] | None:
    if not isinstance(audit, dict) or not all(
        _counter(audit.get(key)) for key in ("checked", "exact")
    ) or type(audit.get("armed")) is not bool:
        return None
    if not (all(_record_list(audit.get(key), strings=("surface", "label", "original", "candidate"), score=True)
                for key in ("would_snap", "snapped"))
            and _record_list(audit.get("left"), strings=("surface",), score=True)):
        return None
    candidates, actions, left = (len(audit[k]) for k in ("would_snap", "snapped", "left"))
    if (audit["exact"] + candidates + actions + left != audit["checked"]
            or (audit["armed"] and candidates) or (not audit["armed"] and actions)):
        return None
    return {"checked": audit["checked"], "exact": audit["exact"],
            "would_snap": candidates, "snapped": actions, "left": left}


def summary_audit_counts(db: Session) -> dict[str, Any]:
    """Count retained snapshot metadata, not generation attempts or a weekly event window.

    Each family has its own denominator. None can mean old data, unavailable grounding or
    no eligible content; it never supplies a measured zero. Project audit JSON only, without
    loading generated prose/filing excerpts or ORM Summary objects.
    """
    names = ("figure_trace", "forward_quotes", "evidence_snap", "machine_sections_only", "quality")
    families = {name: {"recorded": 0, "missing": 0, "malformed": 0,
                       "flagged": 0, "counts": Counter()} for name in names}
    reasons: Counter = Counter()
    population = 0
    rows = db.query(
        Summary.id, Company.sic, Summary.raw_summary["quality"],
        Summary.raw_summary["forward_quote_audit"], Summary.raw_summary["evidence_snap_audit"],
    ).join(Filing, Filing.id == Summary.filing_id).join(
        Company, Company.id == Filing.company_id,
    ).yield_per(1000)
    for _, sic, quality, forward, snap in rows:
        population += 1
        q = quality if isinstance(quality, dict) else {}
        figures, machine = q.get("figures_untraceable"), q.get("machine_sections_only")
        tier, why = q.get("tier"), q.get("reasons")
        quality_valid = tier in ("full", "partial") and _string_list(why)
        values = {
            "figure_trace": ({"unique_figures": len(set(figures))} if _string_list(figures) else None),
            "machine_sections_only": ({"machine_only": int(machine)} if type(machine) is bool else None),
            "quality": ({"partial": int(tier == "partial")} if quality_valid else None),
            "forward_quotes": _forward_counts(forward), "evidence_snap": _snap_counts(snap),
        }
        missing = {
            "figure_trace": quality is None or (isinstance(quality, dict) and figures is None),
            "machine_sections_only": quality is None or (isinstance(quality, dict) and machine is None),
            "quality": quality is None or (isinstance(quality, dict) and (tier is None or why is None)),
            "forward_quotes": forward is None, "evidence_snap": snap is None,
        }
        flagged = {"figure_trace": "unique_figures", "machine_sections_only": "machine_only",
                   "quality": "partial", "forward_quotes": "unverified", "evidence_snap": "left"}
        for name, counts in values.items():
            family = families[name]
            if counts is None:
                family["missing" if missing[name] else "malformed"] += 1
                continue
            family["recorded"] += 1
            family["counts"].update(counts)
            family["flagged"] += int(counts[flagged[name]] > 0)
        if quality_valid and tier == "partial":
            bucket = (str(sic)[:2] if sic else "") or "null"
            for reason in set(why):
                reasons[(bucket, reason)] += 1
    for family in families.values():
        family["unavailable"] = family["missing"] + family["malformed"]
        family["flagged_pct"] = round(100 * family["flagged"] / family["recorded"], 2) if family["recorded"] else None
        family["counts"] = dict(family["counts"])
    return {"snapshot_population": population, "families": families,
            "partial_reasons_by_sic": [{"sic_prefix": bucket, "reason": reason, "count": count}
                                       for (bucket, reason), count in sorted(reasons.items())]}


def universe_coverage(db: Session, *, today: date | None = None) -> dict:
    """Stored summary coverage of committed tickers; a stub is a filing without a Summary.

    This measures any stored summary, not latest-quarter or full-quality coverage. Distinct
    normalized tickers keep class-share spelling differences from inflating the denominator.
    Partial-tier summaries count as summaries; their reasons remain in the existing section.
    """
    members = index_membership_service.member_tickers()
    companies: set[str] = set()
    summarized: set[str] = set()
    filing_count = summary_count = 0
    rows = db.query(
        Company.ticker, func.count(distinct(Filing.id)), func.count(distinct(Summary.id)),
    ).outerjoin(Filing, Filing.company_id == Company.id).outerjoin(
        Summary, Summary.filing_id == Filing.id,
    ).group_by(Company.id, Company.ticker).all()
    for ticker, filings, summaries in rows:
        ticker = index_membership_service.normalize_ticker(ticker)
        if ticker not in members:
            continue
        companies.add(ticker)
        if summaries:
            summarized.add(ticker)
        filing_count += filings
        summary_count += summaries
    generated_on = index_membership_service.universe_generated_on()
    age = ((today or utcnow().date()) - date.fromisoformat(generated_on)).days if generated_on else None
    if age is not None and age < 0:
        age = None
    return {
        "universe_members": len(members),
        "companies_present": len(companies),
        "companies_with_summary": len(summarized),
        "company_coverage_pct": round(100 * len(companies) / len(members), 2) if members else None,
        "summary_coverage_pct": round(100 * len(summarized) / len(members), 2) if members else None,
        "stored_filings": filing_count,
        "summaryless_filings": filing_count - summary_count,
        "stub_ratio_pct": round(100 * (filing_count - summary_count) / filing_count, 2) if filing_count else None,
        "generated_on": generated_on,
        "universe_age_days": age,
    }


async def build_report(db: Session, *, weekly_readout: dict | None = None) -> dict[str, Any]:
    """Assemble detection, universe coverage and durable job-health sections."""
    tickers = await ticker_integrity(db)
    from app.services.ai_readout import decode_readout
    return {
        "ticker_mismatches": tickers["mismatches"],
        "ticker_not_in_file": tickers["not_in_file"],
        "coverage_gaps": coverage_gaps(db),
        "filing_anomalies": filing_anomalies(db),
        "partial_reasons": partial_reason_counts(db),
        "universe_coverage": universe_coverage(db),
        "job_health": job_health(db),
        "summary_audits": summary_audit_counts(db),
        "weekly_readout": weekly_readout if weekly_readout is not None else decode_readout(None),
    }


async def run_and_email(db: Session, *, weekly_readout: dict | None = None) -> dict[str, Any]:
    """Build the report and email it to the founder. Returns the report dict (also useful for a
    dry run / the workflow step summary)."""
    from app.services import email_service, resend_service

    report = await build_report(db, weekly_readout=weekly_readout)
    html_body, text = email_service.render_data_quality_report(report)
    to = settings.DATA_QUALITY_REPORT_EMAIL
    await resend_service.send_email(
        to=[to],
        subject="EarningsNerd data-quality report",
        html=f'{html_body}<pre style="display:none">{html.escape(text)}</pre>',
    )
    logger.info(
        "Data-quality report emailed to %s: %d ticker mismatches, %d coverage gaps, %d filing "
        "anomalies, %d partial-reason rows",
        to, len(report["ticker_mismatches"]), len(report["coverage_gaps"]),
        len(report["filing_anomalies"]), len(report["partial_reasons"]),
    )
    return report
