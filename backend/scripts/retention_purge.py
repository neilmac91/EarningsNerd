#!/usr/bin/env python3
"""Apply the scheduled retention purge (docs/DATA_RETENTION_POLICY.md) as a Cloud Run job.

Deletes, in bounded batches, the rows the policy promises to delete on a clock: search history
older than a year, stale failed-login state, expired OAuth states, long-expired or long-revoked
refresh tokens, contact-form submissions older than a year. Counts only are recorded through
the job ledger (`earningsnerd_job_runs`); nothing user-facing changes.

Usage:
  python scripts/retention_purge.py              # apply
  python scripts/retention_purge.py --dry-run    # report the counts each target would delete
"""
import argparse
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see filing_scan.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def _main(*, dry_run: bool, batch_size: int) -> None:
    from app.database import SessionLocal
    from app.services.job_run_service import track_job
    from app.services.retention_service import run_retention_purge

    with track_job("retention-purge", dry_run=dry_run) as attempt:
        db = SessionLocal()
        try:
            stats = run_retention_purge(db, dry_run=dry_run, batch_size=batch_size)
            attempt.record(stats)
            logger.info("Retention purge complete: %s", stats)
        finally:
            db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Apply the scheduled retention purge.")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without deleting anything.")
    parser.add_argument("--batch-size", type=int, default=5000, help="Rows deleted per statement (default 5000).")
    args = parser.parse_args()
    _main(dry_run=args.dry_run, batch_size=args.batch_size)
