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
  python scripts/filing_scan.py --dry-run    # rejected: safe preview is unavailable

--dry-run is disabled for both modes before application initialization. The former no-email
path still changed notification logs and watchlist watermarks; no safe preview is implemented.
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
    if dry_run:
        raise SystemExit(
            "Safe preview is unavailable: --dry-run is disabled to avoid changing "
            "notification logs and watchlist watermarks."
        )

    from app.database import SessionLocal
    from app.services import filing_scan_service

    from app.services.job_run_service import track_job

    with track_job("filing-digest" if digest else "filing-scan", dry_run=dry_run) as attempt:
        db = SessionLocal()
        try:
            if digest:
                stats = await filing_scan_service.run_daily_digest(
                    db, send_digest=None
                )
                attempt.record(stats)
                logger.info("Daily digest complete: %s", stats)
            else:
                stats = await filing_scan_service.run_filing_scan(
                    db,
                    send_alert=None,
                    cadence_minutes=cadence_minutes,
                )
                attempt.record(stats)
                logger.info("Filing scan complete: %s", stats)
        finally:
            db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Scan watched companies for new SEC filings.")
    parser.add_argument("--digest", action="store_true", help="Run the daily digest pass instead of the real-time scan.")
    parser.add_argument("--dry-run", action="store_true", help="Unavailable: rejects without starting work; safe preview is not implemented.")
    parser.add_argument("--cadence-minutes", type=int, default=60, help="Skip companies checked within this window.")
    args = parser.parse_args()

    asyncio.run(_main(digest=args.digest, dry_run=args.dry_run, cadence_minutes=args.cadence_minutes))
