#!/usr/bin/env python3
"""Scan EDGAR full-text search for notable filings (homepage discovery surface).

Intended to run as a Cloud Run job on a Cloud Scheduler trigger (mirroring
``earningsnerd-earnings-calendar-refresh``), twice daily after the BMO/AMC filing waves. This is
deliberately a real Cloud Run **job**, not the fire-and-forget ``/internal/jobs/notable-filings-scan``
endpoint: a FastAPI ``BackgroundTasks`` callback keeps running only as long as the serving Cloud Run
*instance* stays alive after the HTTP response, and the instance can be reclaimed (scale-to-zero)
before the callback finishes. The internal endpoint remains useful for a one-off manual kick (e.g.
the first seed run) but should not carry the recurring schedule.

Requirements (runs in prod / CI, NOT the offline sandbox):
  - SEC EDGAR network access (EFTS full-text search sweep; keyless, rate-limited in-process)
  - DATABASE_URL pointing at the production database

Usage:
  python scripts/notable_filings_job.py             # trailing-window scan (NOTABLE_FILINGS_SCAN_DAYS)
  python scripts/notable_filings_job.py --days 7    # wider one-shot window (first seed / backfill)
"""
import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

# Make the backend root importable as `app.*` when run directly (see pregenerate_examples.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(*, days: Optional[int]) -> None:
    from app.database import SessionLocal
    from app.services import notable_filings_service

    db = SessionLocal()
    try:
        stats = await notable_filings_service.run_scan(db, days=days)
        logger.info("Notable-filings scan complete: %s", stats.as_dict())
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Scan EDGAR for notable filings.")
    parser.add_argument(
        "--days", type=int, default=None,
        help="Trailing window in calendar days (default: NOTABLE_FILINGS_SCAN_DAYS). "
             "Use a larger value (e.g. 7) for the first seed run.",
    )
    args = parser.parse_args()

    if args.days is not None and args.days < 0:
        parser.error("--days must be >= 0")

    asyncio.run(_main(days=args.days))
