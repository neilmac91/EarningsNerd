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
import sys

# Make the backend root importable as `app.*` even when this file is run directly as
# `python scripts/pregenerate_examples.py` (which puts scripts/ on sys.path, not the backend root).
# Without this the Cloud Run pregenerate job fails with `ModuleNotFoundError: No module named 'app'`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


async def pregenerate_for_ticker(ticker: str, force: bool = False) -> None:
    """Resolve the latest 10-K for ``ticker``, persist it, and cache its summary.

    Thin wrapper over ``precompute_service.precompute_one`` — the shared, idempotent core also used
    by the token-gated ``POST /internal/jobs/precompute`` trigger. When ``force`` is True the
    existing summary + cached excerpt are cleared first, so generation re-runs on the current
    code/prompts (otherwise generation is idempotent and skips filings that already have a summary).
    """
    # Deferred import so the module parses without app config (and SKIP_REDIS_INIT is set first).
    from app.services.precompute_service import precompute_one

    r = await precompute_one(ticker, "10-K", force=force)
    cached = r["status"] in ("generated", "already_cached")
    detail = "summary cached" if cached else r["status"].replace("_", " ")
    if r.get("filing_id"):
        print(f"{r['ticker']}: filing_id={r['filing_id']} accession={r['accession']} -> {detail}")
    else:
        print(f"{r['ticker']}: {detail}")


async def main(tickers: list[str], force: bool = False) -> None:
    mode = " (force refresh)" if force else ""
    print(f"Pre-generating example summaries for {len(tickers)} ticker(s){mode}: {', '.join(tickers)}")
    for ticker in tickers:
        try:
            await pregenerate_for_ticker(ticker, force=force)
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reset each filing's existing summary + cached excerpt before regenerating, so the "
             "refresh picks up the current extraction/prompts instead of skipping cached filings.",
    )
    args = parser.parse_args()

    if args.tickers:
        ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        ticker_list = list(DEFAULT_TICKERS)

    asyncio.run(main(ticker_list, force=args.force))
