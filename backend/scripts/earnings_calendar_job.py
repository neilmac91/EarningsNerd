#!/usr/bin/env python3
"""Refresh the earnings calendar and send earnings-day alerts.

Intended to run as a Cloud Run job on a Cloud Scheduler trigger (mirroring
``earningsnerd-filing-scan``), daily before the US pre-market earnings window. This is deliberately
a real Cloud Run **job**, not the fire-and-forget ``/internal/jobs/earnings-calendar-refresh``
endpoint: a FastAPI ``BackgroundTasks`` callback keeps running only as long as the serving Cloud Run
*instance* stays alive after the HTTP response, and the instance can be reclaimed (scale-to-zero)
before the callback finishes — the same reason ``filing_scan.py`` runs as a dedicated job rather than
through its own internal-trigger endpoint. The internal endpoints remain useful for a one-off manual
kick (e.g. seeding the table for the first time) but should not carry the recurring schedule.

Requirements (runs in prod / CI, NOT the offline sandbox):
  - SEC EDGAR network access (8-K Item 2.02 sweep)
  - Alpha Vantage network access (optional — ALPHA_VANTAGE_API_KEY unset just skips that source)
  - RESEND_API_KEY configured (send earnings-day alert emails)
  - DATABASE_URL pointing at the production database

Usage:
  python scripts/earnings_calendar_job.py            # ingest + reconcile + rescore
  python scripts/earnings_calendar_job.py --alerts    # send today's earnings-day alert digest
  # One-shot guarded re-sweep of past days (e.g. after repair_false_reported_earnings.py):
  python scripts/earnings_calendar_job.py --sweep-from 2026-06-28 --sweep-to 2026-07-04
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import date
from typing import Optional

# Make the backend root importable as `app.*` when run directly (see pregenerate_examples.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(*, alerts: bool, sweep_from: Optional[date] = None, sweep_to: Optional[date] = None) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        if alerts:
            from app.services import earnings_alert_service

            stats = await earnings_alert_service.send_earnings_day_alerts(db)
            logger.info("Earnings-day alerts complete: %s", stats)
        else:
            from app.services import earnings_calendar_service

            stats = await earnings_calendar_service.run_refresh(
                db, sweep_from=sweep_from, sweep_to=sweep_to
            )
            logger.info("Earnings-calendar refresh complete: %s", stats.as_dict())
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Refresh the earnings calendar / send earnings-day alerts.")
    parser.add_argument("--alerts", action="store_true", help="Send today's earnings-day alert digest instead of refreshing.")
    parser.add_argument(
        "--sweep-from", type=date.fromisoformat, default=None,
        help="Override the EDGAR 2.02 sweep window start (YYYY-MM-DD) for a one-shot backfill re-sweep.",
    )
    parser.add_argument(
        "--sweep-to", type=date.fromisoformat, default=None,
        help="Override the EDGAR 2.02 sweep window end (YYYY-MM-DD); required with --sweep-from.",
    )
    args = parser.parse_args()

    if (args.sweep_from is None) != (args.sweep_to is None):
        parser.error("--sweep-from and --sweep-to must be given together")
    if args.sweep_from is not None and args.sweep_from > args.sweep_to:
        parser.error("--sweep-from must be on or before --sweep-to")
    if args.alerts and args.sweep_from is not None:
        parser.error("--sweep-from/--sweep-to apply to the refresh, not --alerts")

    asyncio.run(_main(alerts=args.alerts, sweep_from=args.sweep_from, sweep_to=args.sweep_to))
