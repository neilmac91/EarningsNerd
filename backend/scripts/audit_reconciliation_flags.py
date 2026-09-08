#!/usr/bin/env python3
"""Audit (and optionally repair) stored ``financial_fact.reconciled`` flags (W3-9).

``upsert_facts`` is idempotent on the fact identity key and never re-evaluates the stored
``reconciled`` flag of a row it skips, so a flag computed by an older local-invariant gate (or a
prior parse of the same filing) is frozen. This job re-runs the normal backfill with
``refresh_flags=True`` and ``flags_only=True``: for every existing identity whose ``source`` AND
``value`` are identical to the freshly computed fact, the stored flag is re-evaluated; rows whose
value or source differ (e.g. a bulk companyfacts row occupying the same identity, or an
authoritative override) are only COUNTED as ``value_mismatch`` and never touched. FLAG COLUMNS
ONLY: an identity that is not stored yet is counted as ``facts_unstored`` and never inserted, no
current ``is_latest`` row is demoted, and ``processed_facts_at`` is not touched (storing those
identities is the full re-pass's job: ``scripts/backfill_facts.py`` without ``--only-new``). The
companyfacts cross-check stays on (one limiter-paced fetch per company), exactly as in the
scheduled backfill.

The first production execution (2026-09-08, before this mode existed) also inserted 78 rows;
``scripts/list_facts_created.py`` lists them for review.

DRY RUN BY DEFAULT: without ``--apply`` every per-filing transaction is rolled back — no rows, no
flag flips, no ``processed_facts_at`` stamps — and the job attempt is recorded as ``dry_run``
under the ad hoc identity ``reconciliation-flag-audit`` (it cannot satisfy the scheduled
``backfill-facts`` heartbeat). The stats are printed as one JSON line.

Founder commands (the DB is only reachable from Cloud Run — see docs/DEPLOYMENT.md):
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/audit_reconciliation_flags.py --wait               # dry run: counts only
  gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1 \\
    --args=scripts/audit_reconciliation_flags.py,--apply --wait       # repair the flags

Local usage:
  python scripts/audit_reconciliation_flags.py                       # dry run
  python scripts/audit_reconciliation_flags.py --apply               # write
  python scripts/audit_reconciliation_flags.py --tickers AAPL,MSFT --limit 50
"""
import argparse
import json
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see retention_purge.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def _main(*, apply: bool, tickers: list[str] | None, limit: int | None) -> None:
    from app.database import SessionLocal
    from app.services import facts_service
    from app.services.job_run_service import track_job

    with track_job("reconciliation-flag-audit", dry_run=not apply) as attempt:
        db = SessionLocal()
        try:
            stats = facts_service.backfill_facts(
                db, refresh_flags=True, flags_only=True, tickers=tickers, limit=limit,
                dry_run=not apply,
            )
            attempt.record(stats)
            print(json.dumps(stats, sort_keys=True))
        finally:
            db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    os.environ.setdefault("EDGAR_IDENTITY", "EarningsNerd support@earningsnerd.io")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(
        description="Audit stored financial_fact.reconciled flags (dry run unless --apply)."
    )
    parser.add_argument("--apply", action="store_true", help="Write the flag repairs (default: dry run).")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated tickers (default: all).")
    parser.add_argument("--limit", type=int, default=None, help="Max filings to process.")
    args = parser.parse_args()
    parsed_tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None
    _main(apply=args.apply, tickers=parsed_tickers, limit=args.limit)
