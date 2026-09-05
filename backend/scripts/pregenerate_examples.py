#!/usr/bin/env python3
"""Pre-generate example summaries for zero-wait first-visit activation.

For each domestic ticker, this script resolves the latest 10-K and 10-Q (BABA: annual 20-F), ensures a
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


# Foreign private issuers file 20-F (annual) instead of 10-K — pick the right annual form per
# ticker so a foreign name in DEFAULT_TICKERS (e.g. BABA) resolves its actual filing rather than a
# 10-K it never files. (Requires ENABLE_FPI_FILINGS for precompute_one to accept 20-F.)
_ANNUAL_FORM_BY_TICKER = {"BABA": "20-F"}


async def pregenerate_for_ticker(ticker: str, force: bool = False, *, form: str | None = None) -> dict:
    """Resolve the latest annual filing (10-K, or 20-F for foreign issuers) for ``ticker``,
    persist it, and cache its summary.

    Thin wrapper over ``precompute_service.precompute_one`` — the shared, idempotent core also used
    by the token-gated ``POST /internal/jobs/precompute`` trigger. When ``force`` is True the
    existing summary + cached excerpt are cleared first, so generation re-runs on the current
    code/prompts (otherwise generation is idempotent and skips filings that already have a summary).
    """
    # Deferred import so the module parses without app config (and SKIP_REDIS_INIT is set first).
    from app.services.precompute_service import precompute_one

    form = form or _ANNUAL_FORM_BY_TICKER.get(ticker.upper().strip(), "10-K")
    r = await precompute_one(ticker, form, force=force)
    cached = r["status"] in ("generated", "already_cached")
    detail = "summary cached" if cached else r["status"].replace("_", " ")
    if r.get("filing_id"):
        print(f"{r['ticker']}: filing_id={r['filing_id']} accession={r['accession']} -> {detail}")
    else:
        print(f"{r['ticker']}: {detail}")
    return r


async def main(tickers: list[str], force: bool = False, *, annual_only: bool = False) -> None:
    mode = " (force refresh)" if force else ""
    print(f"Pre-generating example summaries for {len(tickers)} ticker(s){mode}: {', '.join(tickers)}")
    from app.services.job_run_service import track_job

    with track_job("pregenerate") as attempt:
        stats: dict[str, int] = {}
        for ticker in tickers:
            annual = _ANNUAL_FORM_BY_TICKER.get(ticker.upper().strip(), "10-K")
            forms = [annual] if annual_only or annual != "10-K" else [annual, "10-Q"]
            for form in forms:
                try:
                    result = await pregenerate_for_ticker(ticker, force=force, form=form)
                    status = result["status"]
                except Exception:  # keep going, then fail the job with the observed counts
                    logger.exception("Failed to pre-generate example for %s %s", ticker, form)
                    status = "errors"
                stats[status] = stats.get(status, 0) + 1
        attempt.record(stats)
        print("Pre-generation complete; per-ticker outcomes:", stats)


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
    parser.add_argument("--annual-only", action="store_true", help="Resolve annual reports only.")
    args = parser.parse_args()

    if args.tickers:
        ticker_list = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        ticker_list = list(DEFAULT_TICKERS)

    asyncio.run(main(ticker_list, force=args.force, annual_only=args.annual_only))
