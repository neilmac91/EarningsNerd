#!/usr/bin/env python3
"""Give filing-owned legacy calculations their lineage record (Multi-Period Analysis WP0).

A filing-owned margin, free cash flow, working capital or current ratio stored before #1191 carries
no versioned provenance, so every reader shows it as ``legacy_calculation``. Ingestion skips an
identity already stored and the quarterly repair leaves filing-owned rows alone, so nothing else
ever records its lineage. This one-off recomputes each such row from the operands its own accession
stores, through the per-filing writer's calculator, and writes the record that writer would write
today, less its local-gate audit, which cannot be recovered. The rule is
``app/services/filing_lineage_repair.py``; the runbook is docs/filing-lineage-repair.md.

Only ``provenance`` and ``reconciled`` change, never a value, label or ``is_latest``, and only on a
pass (``reconciled`` true) or on a concern with positive evidence (``reconciled`` false): a
recomputed value that disagrees with the figure (``calculation_mismatch``), or a review state an
operand carries. These are held, unchanged and counted:
  - ``legacy_flagged``             the row's ``reconciled`` is false: the old gate's reason is lost
  - ``operand_withheld``           an operand is ``unavailable``, so the record would withhold the figure
  - ``inputs_not_found``           the calculator finds no operands (each row's ``diagnostic`` says why,
                                   for example a flow operand stored before #831 with no start date)
  - ``operand_legacy_calculation`` an operand is itself a legacy calculation
Re-running is safe: a written row has a version-1 record and is no longer a target.

DRY RUN BY DEFAULT: nothing is written and each company's transaction is rolled back. ``--apply``
re-plans each company from live data, in its own transaction under the company lock both fact
writers take, and journals every changed row in ``financial_fact_revision`` (action ``apply``,
version ``lineage-backfill-v1``), so ``scripts/repair_quarterly_facts.py --tickers T --rollback-run
RUN_ID [--apply]`` reverts one company's run. Output: a start line naming the run, flushed before
the first company, then one JSON line per company and one summary line. No network: no SEC read.

Founder commands (the DB is only reachable from Cloud Run; runbook docs/filing-lineage-repair.md):
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/repair_filing_lineage.py --wait              # dry run: counts only
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/repair_filing_lineage.py,--apply --wait      # only after sign-off

Local usage:
  python scripts/repair_filing_lineage.py                       # dry run, every company
  python scripts/repair_filing_lineage.py --tickers REGN        # dry run, a cohort
  python scripts/repair_filing_lineage.py --apply --limit 10    # write the first 10 companies
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable
from uuid import uuid4

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Give filing-owned legacy calculations their lineage (dry run).")
    parser.add_argument("--apply", action="store_true", help="Write and journal the records (default: dry run).")
    parser.add_argument("--tickers", help="Comma-separated cohort, each reported (default: every company with "
                                          "a filing-owned formula row).")
    parser.add_argument("--limit", type=int, help="Process at most this many companies, in company-id order.")
    return parser


def run(args: argparse.Namespace, emit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Process each selected company in its own session; emit its line, return the summary."""
    from app.database import SessionLocal
    from app.models import Company, FinancialFact
    from app.services import filing_lineage_repair as repair
    from app.services.fact_provenance import METRIC_FORMULAS

    tickers = sorted({t.strip().upper() for t in (args.tickers or "").split(",") if t.strip()})
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")
    # This short read session lists the cohort and closes; each company then gets its own transaction.
    with SessionLocal() as db:
        query = db.query(Company.id, Company.ticker).order_by(Company.id)
        if tickers:
            known = {t for (t,) in db.query(Company.ticker).filter(Company.ticker.in_(tickers))}
            if set(tickers) - known:
                raise ValueError(f"Unknown tickers {sorted(set(tickers) - known)}; no company processed")
            query = query.filter(Company.ticker.in_(tickers))  # each named company gets a line
        else:
            owners = db.query(FinancialFact.company_id).filter(
                FinancialFact.filing_id.isnot(None), FinancialFact.concept.in_(sorted(METRIC_FORMULAS)),
            ).distinct()
            query = query.filter(Company.id.in_(owners))
        companies = (query.limit(args.limit) if args.limit else query).all()
    run_id = str(uuid4())
    # Each company commits as it goes: this line keeps the run_id in the log of a run cut short.
    emit({"started": True, "run_id": run_id, "dry_run": not args.apply, "tickers": tickers or None})
    summary: dict[str, Any] = {
        "summary": True, "run_id": run_id, "dry_run": not args.apply, "companies": len(companies),
        "companies_with_writes": 0, "scanned": 0, "writes": 0, "revisions": 0,
        "outcomes": {"passed": 0, "needs_review": 0}, "reasons": {},
        "held": dict.fromkeys(repair.HOLD_REASONS, 0), "diagnostics": dict.fromkeys(repair.DIAGNOSTICS, 0),
        "latest_fy": {"cleared": 0, "marked": 0, "held": 0}, "failed": 0,
    }
    for company_id, ticker in companies:
        try:
            with SessionLocal() as db:
                result = repair.backfill_company(db, company_id, apply=args.apply, run_id=run_id)
                if args.apply:
                    db.commit()
                else:
                    db.rollback()
        except Exception as exc:  # One company's failure rolls back that company alone and fails the exit code.
            summary["failed"] += 1
            emit({"company_id": company_id, "ticker": ticker, "error": str(exc)})
            continue
        summary["companies_with_writes"] += bool(result["writes"])
        for key in ("scanned", "writes", "revisions"):
            summary[key] += result[key]
        for key in ("outcomes", "reasons", "held", "diagnostics", "latest_fy"):
            for name, count in result[key].items():
                summary[key][name] = summary[key].get(name, 0) + count
        emit(result)
    summary["reasons"] = dict(sorted(summary["reasons"].items()))
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
