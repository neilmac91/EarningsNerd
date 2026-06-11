#!/usr/bin/env python3
"""Pre-generate example summaries for zero-wait first-visit activation.

For each ticker, this script resolves the company's latest 10-K, ensures a
``Company`` and ``Filing`` row exist in the database, and triggers/awaits AI
summary generation so the ``Summary`` is cached. A first-time visitor can then
deep-link straight to ``/filing/{id}`` with no generation wait (roadmap Q2).

The operator copies a chosen filing id from this script's output into the
frontend env var ``NEXT_PUBLIC_EXAMPLE_FILING_ID`` (see
``frontend/lib/featureFlags.ts``), which rewires the homepage "See an Example"
CTA to that cached summary.

Requirements (runs in prod / CI, NOT in the offline sandbox):
  - SEC EDGAR network access (resolve companies and fetch filings)
  - ``OPENAI_API_KEY`` configured (summary generation calls the AI model)

Usage:
  python scripts/pregenerate_examples.py
  python scripts/pregenerate_examples.py --tickers AAPL,MSFT,NVDA
"""

import argparse
import asyncio
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Default tickers mirror the homepage QuickAccessBar
# (frontend/components/QuickAccessBar.tsx TOP_COMPANIES).
DEFAULT_TICKERS = [
    "AAPL",
    "NVDA",
    "TSLA",
    "MSFT",
    "META",
    "GOOGL",
    "AMZN",
    "BABA",
]


async def pregenerate_for_ticker(ticker: str) -> None:
    """Resolve the latest 10-K for ``ticker``, persist it, and cache its summary."""
    # Imports are deferred so the module parses/imports without app config
    # (and so SKIP_REDIS_INIT is set before app modules initialize).
    from app.database import SessionLocal
    from app.models import Company, Filing
    from app.services.edgar.compat import sec_edgar_service
    from app.services.summary_generation_service import generate_summary_background

    ticker_upper = ticker.upper().strip()

    with SessionLocal() as db:
        # Get-or-create the company (mirrors routers/companies.py get_company).
        company = db.query(Company).filter(Company.ticker == ticker_upper).first()
        if not company:
            sec_results = await sec_edgar_service.search_company(ticker_upper)
            if not sec_results:
                print(f"{ticker_upper}: company not found on SEC EDGAR — skipping")
                return
            sec_data = sec_results[0]
            company = Company(
                cik=sec_data["cik"],
                ticker=sec_data["ticker"],
                name=sec_data["name"],
                exchange=sec_data.get("exchange"),
            )
            db.add(company)
            db.commit()
            db.refresh(company)

        # Resolve the latest 10-K.
        sec_filings = await sec_edgar_service.get_filings(
            company.cik, filing_types=["10-K"], limit=1
        )
        if not sec_filings:
            print(f"{ticker_upper}: no 10-K filings found — skipping")
            return

        sec_filing = sec_filings[0]
        sec_url = sec_filing.get("sec_url")
        document_url = sec_filing.get("document_url")

        # Both URLs are NOT NULL on the Filing model and validated by event
        # listeners in app/models/__init__.py — skip rather than fail the row.
        if not sec_url or not document_url:
            print(
                f"{ticker_upper}: filing {sec_filing.get('accession_number')} "
                f"missing sec_url/document_url — skipping"
            )
            return

        # Get-or-create the Filing row (mirrors routers/filings.py persistence).
        filing = db.query(Filing).filter(
            Filing.accession_number == sec_filing["accession_number"]
        ).first()
        if not filing:
            filing = Filing(
                company_id=company.id,
                accession_number=sec_filing["accession_number"],
                filing_type=sec_filing["filing_type"],
                filing_date=datetime.fromisoformat(sec_filing["filing_date"]),
                period_end_date=(
                    datetime.fromisoformat(sec_filing["report_date"])
                    if sec_filing.get("report_date")
                    else None
                ),
                document_url=document_url,
                sec_url=sec_url,
            )
            db.add(filing)
            db.commit()
            db.refresh(filing)

        filing_id = filing.id

    # Trigger generation (idempotent: returns early if a Summary already
    # exists; manages its own DB session).
    await generate_summary_background(filing_id, user_id=None)

    # Report whether a cached summary now exists.
    from app.models import Summary

    with SessionLocal() as db:
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        status = "summary cached" if summary else "NO summary (check OPENAI_API_KEY/logs)"
        print(f"{ticker_upper}: filing_id={filing_id} accession={filing.accession_number} -> {status}")


async def main(tickers: list[str]) -> None:
    print(f"Pre-generating example summaries for {len(tickers)} ticker(s): {', '.join(tickers)}")
    for ticker in tickers:
        try:
            await pregenerate_for_ticker(ticker)
        except Exception as exc:  # noqa: BLE001 — keep going for remaining tickers
            logger.exception("Failed to pre-generate example for %s", ticker)
            print(f"{ticker.upper()}: ERROR — {exc}")

    print(
        "\nDone. Copy a chosen filing id into NEXT_PUBLIC_EXAMPLE_FILING_ID "
        "(frontend) to enable the zero-wait 'See an Example' CTA."
    )


if __name__ == "__main__":
    # Skip Redis initialization — this is an offline-style batch job.
    os.environ.setdefault("SKIP_REDIS_INIT", "true")

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        description="Pre-generate cached example summaries for first-visit activation."
    )
    parser.add_argument(
        "--tickers",
        type=str,
        default=None,
        help="Comma-separated tickers (default: homepage QuickAccessBar tickers).",
    )
    args = parser.parse_args()

    if args.tickers:
        ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        ticker_list = list(DEFAULT_TICKERS)

    asyncio.run(main(ticker_list))
