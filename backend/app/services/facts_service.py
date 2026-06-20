"""Normalize the standardized XBRL metrics we already extract into queryable `financial_fact` rows.

`normalize_standardized_to_facts` is pure (dict in → list[dict] out, unit-testable). `upsert_facts`
writes them while maintaining the restatement-safe `is_latest` flag.

v1 sources only the current period each filing reports, attributed to that filing's accession —
accurate and dependency-free (it reuses `xbrl_service.extract_standardized_metrics`). A
local-invariant reconciliation gate (`reconcile_facts`, no network) runs on write: it hard-rejects
impossible values and flags implausible ones (`reconciled=False`) so the UI can surface them honestly
("reconciled or visibly flagged" — strategy §3.5/§5). The authoritative cross-check vs `data.sec.gov`
and cross-source backfill (companyfacts / FSDS / Frames) remain later waves.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
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

# Concepts that are physically impossible below zero — a negative value is a parse error,
# not a legitimate datum (a loss lives in net_income/operating_income, never in revenue or
# total_assets). These hard-reject; everything else can legitimately be negative.
NON_NEGATIVE_CONCEPTS: frozenset[str] = frozenset(
    {"revenue", "total_assets", "cash_and_equivalents", "long_term_debt"}
)

# A period-over-period swing beyond this factor (either direction) is treated as a likely
# scale bug (the ABNB "$ in millions" → 1, XOM EPS 0.00 class), flagged not rejected.
_MAGNITUDE_TOLERANCE = 10.0


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
    """Turn standardized metrics into fact dicts — one row per concept *per reported period*.

    A 10-K's XBRL carries the current year plus comparative prior years, so each concept's
    ``series`` (from ``extract_standardized_metrics``) yields several periods. We emit a row for
    every period point, attributed to this filing's accession; the identity key includes
    ``period_end`` so they're distinct, and the restatement-safe ``is_latest`` logic in
    ``upsert_facts`` keeps the newest filing's value current when periods overlap across filings.
    Falls back to the single ``current`` entry when no ``series`` is present. Tolerant of
    missing/malformed entries (skipped, never raised).
    """
    if not accession or not isinstance(standardized, dict):
        return []
    facts: list[dict[str, Any]] = []
    for concept, entry in standardized.items():
        if not isinstance(entry, dict):
            continue
        points = entry.get("series")
        if not isinstance(points, list) or not points:
            current = entry.get("current")
            points = [current] if isinstance(current, dict) else []
        for point in points:
            if not isinstance(point, dict):
                continue
            value = point.get("value")
            # Exclude bool (a subclass of int) and non-numeric values.
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            period_end = _parse_date(point.get("period"))
            if period_end is None:
                continue
            # Each point may carry the form that reported it; fall back to the filing's form.
            point_form = point.get("form") or form
            facts.append(
                {
                    "company_id": company_id,
                    "filing_id": filing_id,
                    "concept": concept,
                    "unit": _CONCEPT_UNITS.get(concept, "USD"),
                    "period_end": period_end,
                    "fiscal_year": period_end.year,
                    "fiscal_period": _fiscal_period(point_form),
                    "value": float(value),
                    "form": point_form,
                    "accession": accession,
                    "source": "edgar_xbrl",
                }
            )
    return facts


def reconcile_facts(
    facts: list[dict[str, Any]],
    *,
    prior_values: Optional[dict[str, float]] = None,
    period_of_report: Optional[date] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Local-invariant reconciliation gate (pure, no network — strategy §3.5).

    Operates on one filing's batch of normalized facts. Returns ``(accepted, rejected)``:

    * **rejected** — physically impossible values (negative on a non-negative concept). Dropped,
      never stored, logged as ``fact_reconciliation_reject``.
    * **accepted** — every other fact, each annotated with a ``reconciled`` bool: ``True`` if it
      passed all soft checks, ``False`` if any flagged it. Flagged facts are still stored so the UI
      can show them with a quality badge ("reconciled or visibly flagged"), never silently trusted.

    Soft checks: zero where the prior period was non-zero; >1 order-of-magnitude swing vs prior
    (scale bug); sign(EPS) != sign(net_income) (the MU class); diluted EPS > basic EPS; and
    ``period_end`` != ``period_of_report`` for the current period (the ADI class).

    **Period-aware.** Facts are grouped by ``period_end`` and processed oldest→newest so that
    cross-concept checks (EPS vs net income) only ever compare like-period values, and each period's
    "prior" is its immediate predecessor — seeded from the DB value before the earliest period
    (``prior_values``) then chained across in-batch periods (so a multi-period backfill compares a
    year against the year before it, even when both arrive in the same batch). A single-filing v1
    batch is one group, so this reduces to the obvious behaviour. The period-correctness check
    applies only to the latest (current) period; comparative prior periods legitimately differ.
    """

    def _num(v: Any) -> Optional[float]:
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    # Group by reporting period, oldest first (None-period facts last — they carry no position).
    groups: dict[Any, list[dict[str, Any]]] = {}
    for fact in facts:
        groups.setdefault(fact.get("period_end"), []).append(fact)
    ordered_periods = sorted(groups, key=lambda pe: (pe is None, pe))
    dated = [pe for pe in ordered_periods if pe is not None]
    latest_period = dated[-1] if dated else None

    running_prior: dict[str, Optional[float]] = dict(prior_values or {})
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for pe in ordered_periods:
        group = groups[pe]
        by_concept = {f["concept"]: _num(f.get("value")) for f in group}
        net_income = by_concept.get("net_income")
        eps_basic = by_concept.get("earnings_per_share")
        eps_diluted = by_concept.get("eps_diluted")
        eps_sign_mismatch = (
            net_income not in (None, 0)
            and eps_basic not in (None, 0)
            and (net_income > 0) != (eps_basic > 0)
        )
        diluted_exceeds_basic = (
            eps_basic is not None and eps_diluted is not None and eps_diluted > eps_basic + 1e-9
        )

        period_values: dict[str, float] = {}
        for fact in group:
            concept = fact["concept"]
            value = _num(fact.get("value"))

            if concept in NON_NEGATIVE_CONCEPTS and value is not None and value < 0:
                rejected.append(fact)
                logger.warning(
                    "fact_reconciliation_reject concept=%s value=%s reason=negative",
                    concept,
                    fact.get("value"),
                )
                continue

            prior = _num(running_prior.get(concept))
            reasons: list[str] = []

            if value == 0 and prior not in (None, 0):
                reasons.append("zero_where_prior_nonzero")
            if value not in (None, 0) and prior not in (None, 0):
                ratio = abs(value) / abs(prior)
                if ratio > _MAGNITUDE_TOLERANCE or ratio < 1.0 / _MAGNITUDE_TOLERANCE:
                    reasons.append("magnitude_vs_prior")
            if concept in ("earnings_per_share", "eps_diluted") and eps_sign_mismatch:
                reasons.append("eps_sign_vs_net_income")
            if concept == "eps_diluted" and diluted_exceeds_basic:
                reasons.append("diluted_gt_basic")
            if (
                period_of_report is not None
                and pe is not None
                and pe == latest_period
                and pe != period_of_report
            ):
                reasons.append("period_mismatch")

            if reasons:
                logger.info(
                    "fact_reconciliation_flag concept=%s value=%s reasons=%s",
                    concept,
                    fact.get("value"),
                    ",".join(reasons),
                )
            accepted.append({**fact, "reconciled": not reasons})
            if value is not None:
                period_values[concept] = value

        # This period's values become the prior for the next (newer) period in the batch.
        running_prior.update(period_values)

    return accepted, rejected


def _prior_values(
    db: Session, company_id: int, concepts: set[str], before: Optional[date]
) -> dict[str, float]:
    """Most-recent ``is_latest`` value per concept strictly before ``before`` (period_end).

    Feeds the gate's zero-vs-prior and magnitude checks. One query for the whole batch.
    """
    if not concepts or before is None:
        return {}
    rows = (
        db.query(FinancialFact.concept, FinancialFact.value)
        .filter(
            FinancialFact.company_id == company_id,
            FinancialFact.concept.in_(list(concepts)),
            FinancialFact.is_latest.is_(True),
            FinancialFact.period_end < before,
        )
        .order_by(FinancialFact.concept.asc(), FinancialFact.period_end.desc())
        .all()
    )
    out: dict[str, float] = {}
    for concept, value in rows:
        if concept not in out and value is not None:  # first row per concept = most recent prior
            out[concept] = float(value)
    return out


def upsert_facts(
    db: Session,
    facts: list[dict[str, Any]],
    *,
    period_of_report: Optional[date] = None,
    reconcile: bool = True,
) -> dict[str, int]:
    """Insert fact rows, maintaining ``is_latest`` and the reconciliation flag.

    Runs the local-invariant gate (``reconcile`` on by default) over the batch first: impossible
    facts are dropped, the rest are written with their computed ``reconciled`` value. Idempotent on
    the full identity key — if a row with the same (company, concept, period_end, fiscal_period,
    unit, accession) already exists it is skipped; otherwise any current ``is_latest`` row for the
    same (company, concept, period_end, fiscal_period, unit) is demoted and this one inserted as
    latest. Callers should upsert in chronological order so the newest reported / restated value wins.
    """
    rejected = 0
    if reconcile and facts:
        company_id = facts[0]["company_id"]
        concepts = {f["concept"] for f in facts}
        period_ends = [f["period_end"] for f in facts if f.get("period_end")]
        # Seed the gate with each concept's value from before the EARLIEST batch period;
        # reconcile_facts groups by period and chains in-batch priors forward from there, so a
        # multi-period batch compares each year against the one before it (DB or in-batch).
        prior = _prior_values(db, company_id, concepts, min(period_ends) if period_ends else None)
        facts, dropped = reconcile_facts(
            facts, prior_values=prior, period_of_report=period_of_report
        )
        rejected = len(dropped)

    inserted = 0
    skipped = 0
    for fact in facts:
        fact = dict(fact)
        reconciled = fact.pop("reconciled", False)
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

        db.add(FinancialFact(**fact, is_latest=True, reconciled=reconciled))
        inserted += 1

    db.commit()
    return {"inserted": inserted, "skipped": skipped, "rejected": rejected}


def backfill_facts(
    db: Session,
    extract=None,
    limit: Optional[int] = None,
    *,
    only_unprocessed: bool = False,
) -> dict[str, int]:
    """Populate ``financial_fact`` from filings that already carry ``xbrl_data``.

    Reuses the standardized-metrics extractor + the pure normalizer + the writer. Idempotent
    (``upsert_facts`` skips rows that already exist). Filings are processed oldest-first so the
    newest reported value wins ``is_latest``, and each is stamped with ``processed_facts_at`` so we
    can tell which filings have been normalized. ``extract`` is injectable for tests.

    ``only_unprocessed=True`` skips filings already stamped — the incremental mode for the scheduled
    cron (process just the newly-arrived filings). The default reprocesses everything (a full,
    idempotent pass), which is what a manual re-run wants.
    """
    if extract is None:
        from app.services.edgar.compat import xbrl_service

        extract = xbrl_service.extract_standardized_metrics

    query = db.query(Filing).filter(Filing.xbrl_data.isnot(None))
    if only_unprocessed:
        query = query.filter(Filing.processed_facts_at.is_(None))
    query = query.order_by(Filing.filing_date.asc())
    if limit:
        query = query.limit(limit)

    processed = 0
    inserted = 0
    skipped = 0
    rejected = 0
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
        # `period_of_report` isn't a Filing column today; read defensively so the period-correctness
        # check auto-activates if one is added later.
        result = upsert_facts(
            db, facts, period_of_report=getattr(filing, "period_of_report", None)
        )
        # Stamp the filing as normalized (tracking column; also drives `only_unprocessed`).
        filing.processed_facts_at = datetime.now(timezone.utc)
        db.commit()
        inserted += result["inserted"]
        skipped += result["skipped"]
        rejected += result.get("rejected", 0)
        processed += 1

    return {
        "filings_processed": processed,
        "facts_inserted": inserted,
        "facts_skipped": skipped,
        "facts_rejected": rejected,
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
                "reconciled": bool(row.reconciled),
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
