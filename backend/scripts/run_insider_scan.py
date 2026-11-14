#!/usr/bin/env python3
"""Run a company's insider (Form 4) scan in this process, step by step, into the configured database (ADR 0009).

In production the task worker runs the scan: a beta reader's visit queues the first step and each step queues
the next. Where durable tasks are off (development) nothing queues, so this fills the store for the company
page's insider panel. It is the same step the worker runs (``insider_scan_service.run_scan_step``): one listing,
then at most 8 filings a step, stopping at the first pushback from SEC.

Usage:
    cd backend
    python scripts/run_insider_scan.py AAPL            # until nothing is left to read, or SEC pushes back
    python scripts/run_insider_scan.py AAPL --steps 1  # one step

Requests to SEC, paced by the process's own limits: one listing and one per filing (two when a filing's XML is
not at the listing's name), so about 61 for a company with 60 recent Form 4s. Requires the company to be stored
(open its page once), outbound access to SEC EDGAR and ``EDGAR_IDENTITY`` set as the app requires it.

Exit code: 0 when the scan finished or ran its steps, 1 when the company is not stored or the scan stopped.
"""

import argparse
import asyncio
import os
import sys

# Make `app` importable when run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main(ticker: str, steps: int) -> int:
    from app.database import SessionLocal
    from app.models import Company
    from app.services.insider_scan_service import OUTCOME_RAN, run_scan_step

    with SessionLocal() as db:
        company = db.query(Company).filter(Company.ticker == ticker.upper().strip()).first()
        if company is None:
            print(f"No stored company has the ticker {ticker!r}.")
            return 1
        cik = company.cik
        for number in range(1, steps + 1):
            stats = await run_scan_step(db, cik)
            print(f"step {number}: {stats.as_dict()}")
            if stats.outcome != OUTCOME_RAN or stats.stopped:
                print("The scan stopped; its row says why and when it may run again.")
                return 1
            if not stats.remaining:
                print("Nothing is left to read.")
                return 0
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ticker")
    parser.add_argument("--steps", type=int, default=20, help="the most steps to run (8 filings each)")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.ticker, max(1, min(args.steps, 50)))))
