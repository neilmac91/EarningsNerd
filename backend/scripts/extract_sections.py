#!/usr/bin/env python3
"""Extract and store Item 1A text for 10-K/10-Q filings (the "what changed" wording diff).

The hourly filing-scan job runs the same batch when ENABLE_SECTION_CHANGES is on; this script is
the operator's hand on it: warm the table for a cohort before the flag flips, widen a batch, or
retry failed rows. One SEC request per filing through the shared limiter, serial; the parse is
local. Runs regardless of the flag.

Requirements (prod / CI, NOT the offline sandbox):
  - SEC EDGAR network access
  - DATABASE_URL pointing at the target database

Usage:
  python scripts/extract_sections.py                      # watched companies + summarized filings, newest first
  python scripts/extract_sections.py --tickers AAPL,MSFT  # those companies only (any cohort)
  python scripts/extract_sections.py --all --limit 200    # every supported filing, bounded
  python scripts/extract_sections.py --retry-failed       # include failed rows without the 24 h wait
  python scripts/extract_sections.py --window-days 400    # only filings filed in the last 400 days (default: three years)
"""
import argparse
import asyncio
import logging
import os
import sys

# Make the backend root importable as `app.*` when run directly (see filing_scan.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)


async def _main(*, tickers: list[str], cohort: str, limit: int | None, retry_failed: bool, window_days: int | None) -> None:
    from app.database import SessionLocal
    from app.services import filing_section_service
    from app.services.job_run_service import track_job

    with track_job("section-extraction") as attempt:
        db = SessionLocal()
        try:
            stats = await filing_section_service.run_section_extraction(
                db, limit=limit, cohort=cohort, tickers=tickers or None, retry_failed=retry_failed,
                window_days=window_days,
            )
            attempt.record(stats)
            logger.info("Section extraction complete: %s", stats)
        finally:
            db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Extract Item 1A text for 10-K/10-Q filings.")
    parser.add_argument("--tickers", default="", help="Comma-separated tickers to restrict the batch to.")
    parser.add_argument("--all", action="store_true", help="Every supported filing, not only the watched/summarized cohort.")
    parser.add_argument("--limit", type=int, default=None, help="Filings per run (default: SECTION_EXTRACTION_BATCH_LIMIT).")
    parser.add_argument("--retry-failed", action="store_true", help="Re-attempt failed rows without the 24 h wait.")
    parser.add_argument("--window-days", type=int, default=None, help="Only filings filed within this many days (default: three years).")
    args = parser.parse_args()

    asyncio.run(_main(
        tickers=[t for t in args.tickers.split(",") if t.strip()],
        cohort="all" if args.all else "watched",
        limit=args.limit,
        retry_failed=args.retry_failed,
        window_days=args.window_days,
    ))
