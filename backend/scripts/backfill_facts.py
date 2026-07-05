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

  # One-time remediation of financial-institution revenue (filing 528 / MCB fix): re-extract the
  # as-reported revenue/components and rewrite xbrl_data + financial_fact. Requires network (SEC).
  python scripts/backfill_facts.py --remediate-financials --dry-run     # preview scope
  python scripts/backfill_facts.py --remediate-financials               # all financial SIC filers
  python scripts/backfill_facts.py --remediate-financials --tickers MCB # a specific company
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


def _remediate(*, tickers: list[str] | None, limit: int | None, dry_run: bool) -> None:
    """Re-extract financial-institution revenue from the as-reported income statement and rewrite
    persisted data. Runs the statement-aware extractor (USE_STATEMENT_FINANCIALS forced on for this
    run) per filing, merging the fresh instance metrics over the stored xbrl_data."""
    os.environ["USE_STATEMENT_FINANCIALS"] = "true"  # force the fix on for the re-extraction
    from app.database import SessionLocal
    from app.services import facts_service
    from app.services.edgar.xbrl_service import _extract_from_filing_instance_sync

    def refetch(company, filing):
        cik = str(getattr(company, "cik", "") or "").strip()
        accession = getattr(filing, "accession_number", None)
        if not cik or not accession:
            return None
        fresh = _extract_from_filing_instance_sync(cik.zfill(10), accession)
        if not fresh:
            return None
        # Merge over the stored blob so keys the instance path doesn't carry are preserved; the
        # overlapping keys (incl. a bank's now-empty "revenue" and the new components) are corrected.
        old = filing.xbrl_data if isinstance(filing.xbrl_data, dict) else {}
        return {**old, **fresh}

    db = SessionLocal()
    try:
        stats = facts_service.remediate_industry_facts(
            db, refetch=refetch, tickers=tickers, limit=limit, dry_run=dry_run
        )
        logger.info("Financial-institution remediation complete (dry_run=%s): %s", dry_run, stats)
    finally:
        db.close()


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    os.environ.setdefault("EDGAR_IDENTITY", "EarningsNerd support@earningsnerd.io")
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Backfill financial_fact from filings' XBRL.")
    parser.add_argument(
        "--only-new",
        action="store_true",
        help="Incremental: skip filings already normalized (processed_facts_at set).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max filings to process.")
    parser.add_argument(
        "--remediate-financials",
        action="store_true",
        help="Re-extract financial-institution revenue/components from the as-reported statement and "
             "rewrite xbrl_data + financial_fact (filing 528 / MCB fix). Requires network (SEC).",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers to remediate (default: all financial-SIC filers).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --remediate-financials: report scope without writing.",
    )
    args = parser.parse_args()

    if args.remediate_financials:
        tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
        _remediate(tickers=tickers, limit=args.limit, dry_run=args.dry_run)
    else:
        _main(only_unprocessed=args.only_new, limit=args.limit)
