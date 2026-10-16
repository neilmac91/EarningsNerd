#!/usr/bin/env python3
"""Relabel filing-owned FY facts whose fiscal year contradicts companyfacts (bug hunt 2026-10-15 #8).

Before P5 (#1364) the per-filing writer named every annual fact by the calendar year of its period
end (``facts/upsert.normalize_standardized_to_facts``: ``point.get("fiscal_year") or
period_end.year``), while the companyfacts writer names the same period by the issuer's fiscal
year. The two differ for a year ending around 1 February that is named for the year it starts in
(Target, Home Depot) and for a 52-week year ending on 1 January (Johnson & Johnson). The fact
identity leaves ``fiscal_year`` out, so neither writer ever corrects a row the other stored.

This one-off copies the companyfacts year onto each ``edgar_xbrl`` FY row that has a filing owner,
and only a year it can trust. The evidence for a (company, period_end) is every companyfacts-
reported FY row there (source ``companyfacts``, a raw tag, no filing owner, not retired by a
quarterly repair as ``validation: unavailable``), current or not:
  - no such row                         -> skipped ``no_companyfacts_fy``
  - they name more than one year        -> skipped ``companyfacts_disagree`` (never pick one)
  - they are all instants (balances)    -> skipped ``untrusted_instant_only``: the companyfacts
    writer names an instant older than every fiscal year it knows (its oldest opening balance) by
    calendar year (``facts/companyfacts.py``: ``reported_fiscal_year(record, end) or end.year``),
    which for a January year is the next year's label; a duration's year comes from its window
  - otherwise that one year: a row already carrying it counts ``already_agrees``, the rest relabel.
Durations and instants are both relabelled: an FY balance closes the year that ends on its date.
Only ``fiscal_year`` changes, never period_end, value, unit, accession or is_latest; quarter rows
and companyfacts, derived and reported-EPS rows are never touched and nothing is deleted. The
identity (company, concept, period_end, fiscal_period, unit, accession) and every index on
``financial_fact`` leave ``fiscal_year`` out, so a relabel cannot collide. Re-running is safe: a
relabelled row agrees on the next run.

DRY RUN BY DEFAULT: nothing is written and each company's read is rolled back. ``--apply`` relabels
each company in its own transaction under the company lock both fact writers take, and journals
every changed row in ``financial_fact_revision`` (action ``apply``), so
``scripts/repair_quarterly_facts.py --tickers T --rollback-run RUN_ID [--apply]`` reverts one
company's run. Output: one JSON line per company scanned, then one summary line. No network.

Founder commands (the DB is only reachable from Cloud Run; runbook docs/fiscal-year-label-repair.md):
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/relabel_filing_fy_facts.py --wait              # dry run: counts only
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/relabel_filing_fy_facts.py,--apply --wait      # only after sign-off

Local usage:
  python scripts/relabel_filing_fy_facts.py                       # dry run, every company
  python scripts/relabel_filing_fy_facts.py --tickers TGT,JNJ     # dry run, a cohort
  python scripts/relabel_filing_fy_facts.py --apply --limit 10    # write the first 10 companies
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from typing import TYPE_CHECKING, Any, Callable, Iterable
from uuid import uuid4

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import FinancialFact

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RELABEL_VERSION = "fy-relabel-v1"
FILING_SOURCE = "edgar_xbrl"
SKIP_REASONS = ("already_agrees", "companyfacts_disagree", "no_companyfacts_fy", "untrusted_instant_only")


def _is_evidence(row: FinancialFact) -> bool:
    """A companyfacts-reported FY row that a quarterly repair has not retired as wrong."""
    provenance = row.provenance if isinstance(row.provenance, dict) else {}
    return (row.source == "companyfacts" and row.filing_id is None and row.raw_tag is not None
            and row.fiscal_year is not None and provenance.get("validation") != "unavailable")


def _trusted_year(evidence: list[tuple[int, bool]]) -> tuple[int | None, str | None]:
    """The one companyfacts year at a period end, or the reason none can be trusted."""
    if not evidence:
        return None, "no_companyfacts_fy"
    years = {year for year, _is_duration in evidence}
    if len(years) > 1:
        return None, "companyfacts_disagree"
    if not any(is_duration for _year, is_duration in evidence):
        return None, "untrusted_instant_only"
    return years.pop(), None


def plan_company(rows: Iterable[FinancialFact]) -> dict[str, Any]:
    """Split one company's FY rows into relabels and skips; reads attributes only."""
    evidence: dict[date, list[tuple[int, bool]]] = defaultdict(list)
    targets = []
    for row in rows:
        if row.fiscal_period != "FY":
            continue
        if _is_evidence(row):
            evidence[row.period_end].append((row.fiscal_year, row.period_start is not None))
        elif row.source == FILING_SOURCE and row.filing_id is not None:
            targets.append(row)
    relabel: list[tuple[FinancialFact, int]] = []
    skipped = Counter({reason: 0 for reason in SKIP_REASONS})
    held: dict[str, set[str]] = defaultdict(set)
    for row in targets:
        year, reason = _trusted_year(evidence.get(row.period_end, []))
        if reason is not None:
            skipped[reason] += 1
            held[reason].add(row.period_end.isoformat())
        elif year == row.fiscal_year:
            skipped["already_agrees"] += 1
        else:
            relabel.append((row, year))
    return {
        "scanned": len(targets), "relabel": relabel, "skipped": dict(sorted(skipped.items())),
        "held": {reason: sorted(ends) for reason, ends in sorted(held.items())},
    }


def relabel_company(db: Session, company_id: int, *, apply: bool, run_id: str) -> dict[str, Any]:
    """Plan one company's relabels; with ``apply`` also write and journal them. The caller commits."""
    from app.models import Company, FinancialFact
    from app.models.financial_fact_revision import FinancialFactRevision
    from app.services import facts_service
    from app.services.quarterly_fact_repair import snapshot

    if apply:
        facts_service._lock_fact_companies(db, [{"company_id": company_id}])
    query = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id, FinancialFact.fiscal_period == "FY",
        FinancialFact.source.in_([FILING_SOURCE, "companyfacts"]),
    ).order_by(FinancialFact.id)
    plan = plan_company(query.with_for_update().all() if apply else query.all())
    pairs = Counter((row.period_end.isoformat(), row.fiscal_year, year) for row, year in plan["relabel"])
    revisions = 0
    if apply and plan["relabel"]:
        digest = hashlib.sha256(json.dumps(
            [[row.id, row.fiscal_year, year] for row, year in plan["relabel"]], separators=(",", ":"),
        ).encode()).hexdigest()
        for row, year in plan["relabel"]:
            before = snapshot(row)
            row.fiscal_year = year
            db.add(FinancialFactRevision(
                run_id=run_id, company_id=company_id, fact_id=row.id, action="apply",
                calculation_version=RELABEL_VERSION, payload_sha256=digest,
                before_state=before, after_state=snapshot(row),
            ))
            revisions += 1
        db.flush()
    company = db.get(Company, company_id)
    return {
        "company_id": company_id, "ticker": company.ticker if company else None, "run_id": run_id,
        "dry_run": not apply, "scanned": plan["scanned"], "relabel_rows": len(plan["relabel"]),
        "relabels": [
            {"period_end": end, "from": old, "to": new, "rows": count}
            for (end, old, new), count in sorted(pairs.items(), key=lambda item: (item[0][0], str(item[0][1])))
        ],
        "skipped": plan["skipped"], "held": plan["held"], "revisions": revisions,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Relabel filing-owned FY facts from companyfacts (dry run).")
    parser.add_argument("--apply", action="store_true", help="Write and journal the relabels (default: dry run).")
    parser.add_argument("--tickers", help="Comma-separated cohort (default: every company with filing FY rows).")
    parser.add_argument("--limit", type=int, help="Process at most this many companies, in company-id order.")
    return parser


def run(args: argparse.Namespace, emit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Process each selected company in its own session; emit its line, return the summary."""
    from app.database import SessionLocal
    from app.models import Company, FinancialFact

    tickers = sorted({t.strip().upper() for t in (args.tickers or "").split(",") if t.strip()})
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    # This short read session lists the cohort; each company then gets its own transaction.
    with SessionLocal() as db:
        owners = db.query(FinancialFact.company_id).filter(
            FinancialFact.source == FILING_SOURCE, FinancialFact.fiscal_period == "FY",
            FinancialFact.filing_id.isnot(None),
        ).distinct()
        query = db.query(Company.id, Company.ticker).filter(Company.id.in_(owners)).order_by(Company.id)
        if tickers:
            known = {t for (t,) in db.query(Company.ticker).filter(Company.ticker.in_(tickers))}
            if set(tickers) - known:
                raise ValueError(f"Unknown tickers {sorted(set(tickers) - known)}; no company processed")
            query = query.filter(Company.ticker.in_(tickers))
        companies = (query.limit(args.limit) if args.limit else query).all()
    run_id = str(uuid4())
    summary: dict[str, Any] = {
        "summary": True, "run_id": run_id, "dry_run": not args.apply, "companies": len(companies),
        "companies_with_relabels": 0, "scanned": 0, "relabel_rows": 0, "revisions": 0,
        "skipped": dict.fromkeys(SKIP_REASONS, 0), "failed": 0,
    }
    for company_id, ticker in companies:
        try:
            with SessionLocal() as db:
                result = relabel_company(db, company_id, apply=args.apply, run_id=run_id)
                if args.apply:
                    db.commit()
                else:
                    db.rollback()
        except Exception as exc:  # One company's failure rolls back that company alone and fails the exit code.
            summary["failed"] += 1
            emit({"company_id": company_id, "ticker": ticker, "error": str(exc)})
            continue
        summary["companies_with_relabels"] += bool(result["relabel_rows"])
        for key in ("scanned", "relabel_rows", "revisions"):
            summary[key] += result[key]
        for reason, count in result["skipped"].items():
            summary["skipped"][reason] += count
        emit(result)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(line: dict[str, Any]) -> None:
        print(json.dumps(line, sort_keys=True), flush=True)

    try:
        summary = run(args, emit)
    except ValueError as exc:
        emit({"failed": 1, "error": str(exc)})
        return 1
    emit(summary)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    raise SystemExit(main())
