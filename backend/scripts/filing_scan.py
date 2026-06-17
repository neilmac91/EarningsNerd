#!/usr/bin/env python3
"""Scan watched companies for new SEC filings and deliver alerts.

Intended to run as a Cloud Run job on a Cloud Scheduler trigger (mirroring the
``earningsnerd-pregenerate`` job), e.g. hourly for the real-time scan and once daily for the digest.

Requirements (runs in prod / CI, NOT the offline sandbox):
  - SEC EDGAR network access (fetch latest filings)
  - RESEND_API_KEY configured (send alert emails)
  - DATABASE_URL pointing at the production database

Usage:
  python scripts/filing_scan.py              # real-time scan pass
  python scripts/filing_scan.py --digest     # daily digest pass
  python scripts/filing_scan.py --dry-run    # scan + log, no emails sent
"""
import argparse
import asyncio
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see pregenerate_examples.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(*, digest: bool, dry_run: bool, cadence_minutes: int) -> None:
    from app.database import SessionLocal
    from app.services import filing_scan_service

    async def _noop_send(**_kwargs):  # used in --dry-run
        return None

    db = SessionLocal()
    try:
        if digest:
            stats = await filing_scan_service.run_daily_digest(
                db, send_digest=_noop_send if dry_run else None
            )
            logger.info("Daily digest complete: %s", stats)
        else:
            stats = await filing_scan_service.run_filing_scan(
                db,
                send_alert=_noop_send if dry_run else None,
                cadence_minutes=cadence_minutes,
            )
            logger.info("Filing scan complete: %s", stats)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Scan watched companies for new SEC filings.")
    parser.add_argument("--digest", action="store_true", help="Run the daily digest pass instead of the real-time scan.")
    parser.add_argument("--dry-run", action="store_true", help="Detect + log but do not send emails.")
    parser.add_argument("--cadence-minutes", type=int, default=60, help="Skip companies checked within this window.")
    args = parser.parse_args()

    asyncio.run(_main(digest=args.digest, dry_run=args.dry_run, cadence_minutes=args.cadence_minutes))
