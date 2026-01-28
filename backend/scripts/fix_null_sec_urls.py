#!/usr/bin/env python3
"""
Fix NULL sec_url Records

This script fixes filings that have NULL sec_url values, which violates
the database NOT NULL constraint and can cause PendingRollbackError.

The issue was caused by the EdgarTools client not generating sec_url
in the _transform_filing method.

Usage:
    # Dry run (default) - shows what would be fixed
    python scripts/fix_null_sec_urls.py

    # Actually fix the records
    python scripts/fix_null_sec_urls.py --execute

    # Fix specific ticker only
    python scripts/fix_null_sec_urls.py --ticker BMRN --execute
"""

import argparse
import logging
import sys
from pathlib import Path

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_sec_url(cik: str, accession_number: str) -> str:
    """Generate SEC filing URL from CIK and accession number."""
    accession_clean = accession_number.replace("-", "")
    cik_clean = cik.lstrip("0") or "0"
    return f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/"


def find_null_sec_url_filings(session, ticker: str = None):
    """Find filings with NULL sec_url."""
    query = """
        SELECT f.id, f.accession_number, f.document_url, f.sec_url,
               c.cik, c.ticker, c.name
        FROM filings f
        JOIN companies c ON f.company_id = c.id
        WHERE f.sec_url IS NULL
    """
    if ticker:
        query += " AND UPPER(c.ticker) = :ticker"
    query += " ORDER BY c.ticker, f.filing_date DESC"

    params = {"ticker": ticker.upper()} if ticker else {}
    result = session.execute(text(query), params)
    return result.fetchall()


def fix_null_sec_urls(session, dry_run: bool = True, ticker: str = None):
    """Fix filings with NULL sec_url values."""
    filings = find_null_sec_url_filings(session, ticker)

    if not filings:
        logger.info("No filings with NULL sec_url found.")
        return 0

    logger.info(f"Found {len(filings)} filings with NULL sec_url")

    fixed_count = 0
    for filing in filings:
        filing_id = filing[0]
        accession_number = filing[1]
        document_url = filing[2]
        current_sec_url = filing[3]
        cik = filing[4]
        company_ticker = filing[5]
        company_name = filing[6]

        new_sec_url = generate_sec_url(cik, accession_number)

        logger.info(
            f"  {company_ticker} ({company_name}): "
            f"Filing {accession_number}"
        )
        logger.info(f"    Current sec_url: {current_sec_url}")
        logger.info(f"    New sec_url: {new_sec_url}")

        if not dry_run:
            update_query = text("""
                UPDATE filings
                SET sec_url = :sec_url
                WHERE id = :filing_id
            """)
            session.execute(update_query, {
                "sec_url": new_sec_url,
                "filing_id": filing_id
            })
            fixed_count += 1
            logger.info(f"    FIXED")
        else:
            logger.info(f"    [DRY RUN - no changes made]")

    if not dry_run:
        session.commit()
        logger.info(f"Fixed {fixed_count} filings")
    else:
        logger.info(f"Dry run complete. Would fix {len(filings)} filings.")
        logger.info("Run with --execute to apply changes.")

    return len(filings)


def main():
    parser = argparse.ArgumentParser(
        description="Fix filings with NULL sec_url values"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the fix (default is dry run)"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="Only fix filings for a specific ticker"
    )
    args = parser.parse_args()

    dry_run = not args.execute

    if dry_run:
        logger.info("Running in DRY RUN mode (no changes will be made)")
    else:
        logger.info("Running in EXECUTE mode (changes will be applied)")

    session = SessionLocal()
    try:
        count = fix_null_sec_urls(session, dry_run=dry_run, ticker=args.ticker)
        return 0 if count >= 0 else 1
    except Exception as e:
        logger.exception(f"Error fixing NULL sec_urls: {e}")
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
