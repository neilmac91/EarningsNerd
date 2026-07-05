#!/usr/bin/env python3
"""Warm the companyfacts-backed multi-period history in ``financial_fact`` (Multi-Period Analysis M1).

One SEC request per company (https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json) ingests the
company's full annual + quarterly history with proper FY/Q1..Q4 labels. Run after deploy to make
the coverage endpoint's first touch a pure DB read for the cohorts users actually hit; the internal
endpoint ``POST /internal/jobs/sync-companyfacts`` is the lighter-weight alternative.

Requirements (runs in prod / CI, NOT the offline sandbox):
  - DATABASE_URL pointing at the production database
  - network access to data.sec.gov (paced by the shared SEC rate limiter)

Usage:
  python scripts/sync_companyfacts.py --watchlist-only        # every company on any watchlist
  python scripts/sync_companyfacts.py --tickers AAPL,MSFT     # explicit cohort
  python scripts/sync_companyfacts.py --limit 500             # first 500 companies by id
  python scripts/sync_companyfacts.py --tickers AAPL --force  # ignore the 24h freshness stamp
"""
import argparse
import asyncio
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see backfill_facts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(
    *, tickers: list[str] | None, watchlist_only: bool, limit: int | None, force: bool
) -> None:
    from app.database import SessionLocal
    from app.services import facts_service

    db = SessionLocal()
    try:
        stats = await facts_service.sync_companyfacts_batch(
            db, tickers=tickers, watchlist_only=watchlist_only, limit=limit, force=force
        )
        logger.info("Companyfacts sync complete: %s", stats)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Ingest SEC companyfacts history into financial_fact."
    )
    parser.add_argument(
        "--tickers", type=str, default=None,
        help="Comma-separated tickers to sync (default: all companies, or --watchlist-only).",
    )
    parser.add_argument(
        "--watchlist-only", action="store_true",
        help="Only companies on at least one user's watchlist.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max companies to sync.")
    parser.add_argument(
        "--force", action="store_true", help="Re-sync even inside the freshness TTL."
    )
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    asyncio.run(
        _main(tickers=tickers, watchlist_only=args.watchlist_only, limit=args.limit, force=args.force)
    )
