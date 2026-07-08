#!/usr/bin/env python3
"""Weekly data-quality report (P1-9): scan the remediation's detections and email the founder.

Reuses the ORM detections in ``app.services.data_quality_service`` (ticker integrity, per-concept
coverage gaps, filing-count anomalies, partial-summary reasons). Runs on the RESEND-carrying Cloud
Run job (``earningsnerd-filing-digest``) via the jobs channel, or on any host with ``DATABASE_URL``
+ ``RESEND_API_KEY`` set.

Usage:
  python scripts/data_quality_report.py            # build the report + email the founder
  python scripts/data_quality_report.py --dry-run  # build + print JSON, don't email
"""
import argparse
import asyncio
import json
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see sync_companyfacts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(dry_run: bool) -> None:
    from app.database import SessionLocal
    from app.services import data_quality_service

    db = SessionLocal()
    try:
        if dry_run:
            report = await data_quality_service.build_report(db)
            print(json.dumps(report, indent=2, default=str))
        else:
            await data_quality_service.run_and_email(db)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Weekly data-quality report → founder email.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Build and print the report as JSON; do not email."
    )
    args = parser.parse_args()
    asyncio.run(_main(args.dry_run))
