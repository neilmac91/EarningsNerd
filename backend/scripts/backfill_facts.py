#!/usr/bin/env python3
"""Normalize filings' XBRL into the ``financial_fact`` table (peers F3 + fundamentals F5).

Intended to run as a Cloud Run job on a Cloud Scheduler trigger (mirroring
``earningsnerd-filing-scan``), e.g. weekly, after the filing scan has ingested new filings.
The internal endpoint ``POST /internal/jobs/backfill-facts`` is the lighter-weight alternative.

Requirements (runs in prod / CI, NOT the offline sandbox):
  - DATABASE_URL pointing at the production database
  - filings already carrying ``xbrl_data`` (populated by the summary/XBRL path)

Usage:
  python scripts/backfill_facts.py                 # full, idempotent pass over all filings
  python scripts/backfill_facts.py --only-new      # incremental: only un-normalized filings
  python scripts/backfill_facts.py --limit 500     # cap the number of filings processed
"""
import argparse
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see pregenerate_examples.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


def _main(*, only_unprocessed: bool, limit: int | None) -> None:
    from app.database import SessionLocal
    from app.services import facts_service

    db = SessionLocal()
    try:
        stats = facts_service.backfill_facts(db, limit=limit, only_unprocessed=only_unprocessed)
        logger.info("Facts backfill complete: %s", stats)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Backfill financial_fact from filings' XBRL.")
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="Incremental: skip filings already normalized (processed_facts_at set).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max filings to process.")
    args = parser.parse_args()

    _main(only_unprocessed=args.only_new, limit=args.limit)
