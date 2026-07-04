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
"""
import argparse
import asyncio
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see pregenerate_examples.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(*, alerts: bool) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        if alerts:
            from app.services import earnings_alert_service

            stats = await earnings_alert_service.send_earnings_day_alerts(db)
            logger.info("Earnings-day alerts complete: %s", stats)
        else:
            from app.services import earnings_calendar_service

            stats = await earnings_calendar_service.run_refresh(db)
            logger.info("Earnings-calendar refresh complete: %s", stats.as_dict())
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Refresh the earnings calendar / send earnings-day alerts.")
    parser.add_argument("--alerts", action="store_true", help="Send today's earnings-day alert digest instead of refreshing.")
    args = parser.parse_args()

    asyncio.run(_main(alerts=args.alerts))
