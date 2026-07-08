#!/usr/bin/env python3
"""Backfill deep 10-K/10-Q filing history (since 2001) from EFTS into the ``filings`` table (P1-6).

A few EFTS full-text-search requests per company (paced by the shared SEC rate limiter) list the
company's historical annual/quarterly reports; rows are written NOT-NULL-safe + accession-deduped,
and each company is stamped ``companies.history_backfilled_at`` so re-runs skip it. The internal
endpoint ``POST /internal/jobs/backfill-filing-history`` is the lighter-weight alternative.

Requirements (runs in prod / CI, NOT the offline sandbox):
  - DATABASE_URL pointing at the production database
  - network access to efts.sec.gov (paced by the shared SEC rate limiter)

Usage:
  python scripts/backfill_filing_history.py --tickers JPM,BAC   # explicit seed cohort
  python scripts/backfill_filing_history.py --watchlist-only    # every watchlisted company
  python scripts/backfill_filing_history.py --limit 50          # first 50 un-backfilled companies
"""
import argparse
import asyncio
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see sync_companyfacts.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(*, tickers: list[str] | None, watchlist_only: bool, limit: int | None) -> None:
    from app.database import SessionLocal
    from app.services import filing_history_service

    db = SessionLocal()
    try:
        stats = await filing_history_service.batch_backfill(
            db, tickers=tickers, watchlist_only=watchlist_only, limit=limit
        )
        logger.info("Filing-history backfill complete: %s", stats)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Backfill deep 10-K/10-Q history from EFTS.")
    parser.add_argument(
        "--tickers", type=str, default=None,
        help="Comma-separated tickers to backfill (default: all un-backfilled, or --watchlist-only).",
    )
    parser.add_argument(
        "--watchlist-only", action="store_true",
        help="Only companies on at least one user's watchlist.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max companies to backfill.")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    asyncio.run(_main(tickers=tickers, watchlist_only=args.watchlist_only, limit=args.limit))
