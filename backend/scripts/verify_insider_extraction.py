#!/usr/bin/env python3
"""Live verification for the insider (Form 4) extraction pipeline.

Runs the *real* EdgarTools path against live SEC EDGAR and prints (a) the raw
object shapes our extractor depends on and (b) the extractor's output, so we can
confirm the duck-typed contract in ``app/services/ownership_extractor.py`` and
``app/services/insider_service.py`` holds against current edgartools + SEC data.

This is the bridge between the offline unit tests (which mock the EdgarTools
objects) and production: the unit tests prove the *logic*, this proves the
*shapes*. Run it before trusting the feed in prod.

Usage:
    cd backend
    python scripts/verify_insider_extraction.py            # defaults: AAPL, NVDA, JPM
    python scripts/verify_insider_extraction.py TSLA MSFT  # custom tickers
    EDGAR_IDENTITY="you@example.com" python scripts/verify_insider_extraction.py AAPL

Requires: edgartools installed and outbound network access to SEC EDGAR.
Exit code is non-zero if no transactions could be extracted for any ticker
(a strong signal the EdgarTools contract has drifted).
"""

import asyncio
import os
import sys
from itertools import islice

# Make `app` importable when run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_TICKERS = ["AAPL", "NVDA", "JPM"]
FILINGS_PER_TICKER = 5  # keep the live run quick; enough to see real trades


def _hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _short(value, width: int = 80) -> str:
    s = repr(value)
    return s if len(s) <= width else s[: width - 3] + "..."


def _introspect_first_form4(ticker: str):
    """Print the raw shapes of the first Form 4 for a ticker (for humans)."""
    from edgar import Company as EdgarCompany

    company = EdgarCompany(ticker)
    print(f"Company: name={getattr(company, 'name', None)!r} cik={getattr(company, 'cik', None)!r}")

    filings = company.get_filings(form="4", amendments=False)
    first = next(iter(islice(filings, 1)), None)
    if first is None:
        print("  (no Form 4 filings found)")
        return

    accession = getattr(first, "accession_number", None) or getattr(first, "accession_no", None)
    print(f"Filing: accession={accession!r} filed={getattr(first, 'filing_date', None)!r}")

    form4 = first.obj()
    print(f"obj() type: {type(form4).__module__}.{type(form4).__name__}")

    # Surface the attributes the extractor reads.
    for attr in ("insider_name", "position", "reporting_owners", "issuer", "aff10b5_one"):
        print(f"  .{attr}: {_short(getattr(form4, attr, '<missing>'))}")

    summ_getter = getattr(form4, "get_ownership_summary", None)
    if callable(summ_getter):
        try:
            summ = summ_getter()
            print(f"  get_ownership_summary().has_10b5_1_plan: "
                  f"{_short(getattr(summ, 'has_10b5_1_plan', '<missing>'))}")
            print(f"  get_ownership_summary().net_change: "
                  f"{_short(getattr(summ, 'net_change', '<missing>'))}")
        except Exception as exc:  # noqa: BLE001 - diagnostic only
            print(f"  get_ownership_summary() raised: {exc!r}")

    trades = getattr(form4, "market_trades", None)
    cols = getattr(trades, "columns", None)
    if cols is not None:
        print(f"  market_trades columns: {list(cols)}")
    else:
        print(f"  market_trades type: {type(trades).__name__}")


async def _verify_ticker(ticker: str) -> int:
    """Run the production service path and the extractor; return txn count."""
    from app.services import insider_service

    _hr(f"{ticker}: raw EdgarTools shapes")
    try:
        _introspect_first_form4(ticker)
    except Exception as exc:  # noqa: BLE001 - diagnostic only
        print(f"  introspection failed: {exc!r}")

    _hr(f"{ticker}: insider_service.get_insider_activity()")
    # Fresh cache each run so we always exercise the live fetch.
    insider_service.clear_cache()
    result = await insider_service.get_insider_activity(
        ticker, window_days=180, limit_filings=FILINGS_PER_TICKER, recent_limit=10
    )

    print(f"company_name: {result['company_name']!r}  cik: {result['cik']!r}")
    print(f"total_transactions: {result['total_transactions']}")
    s = result["summary"]
    print(
        "summary: "
        f"buys={s['buy_count']} ({s['buy_shares']:,.0f} sh) "
        f"sells={s['sell_count']} ({s['sell_shares']:,.0f} sh) "
        f"net={s['net_shares']:,.0f} sh  "
        f"10b5-1 plan sells={s['plan_10b5_1_sell_shares']:,.0f} sh  "
        f"last={s['last_transaction_date']}"
    )

    print("recent transactions:")
    for t in result["transactions"][:6]:
        val = f"${t['value']:,.0f}" if t.get("value") is not None else "n/a"
        print(
            f"  {t.get('transaction_date')}  {t.get('transaction_code')}"
            f" {t.get('transaction_label')}  "
            f"{t.get('insider_name')} ({t.get('insider_title')})  "
            f"{t.get('shares')} sh @ {t.get('price')}  = {val}  "
            f"10b5-1={t.get('is_10b5_1')}"
        )
    if not result["transactions"]:
        print("  (none — note: companies with only grants/derivatives have no open-market trades)")

    return result["total_transactions"]


async def main(tickers: list[str]) -> int:
    # Mirror the app's EdgarTools identity requirement.
    from edgar import set_identity

    identity = os.environ.get("EDGAR_IDENTITY", "neil@earningsnerd.io")
    set_identity(identity)
    print(f"EdgarTools identity: {identity}")

    total = 0
    for ticker in tickers:
        try:
            total += await _verify_ticker(ticker.upper().strip())
        except Exception as exc:  # noqa: BLE001 - report and continue
            _hr(f"{ticker}: FAILED")
            print(f"  {type(exc).__name__}: {exc}")

    _hr("RESULT")
    if total == 0:
        print("❌ No transactions extracted for any ticker — the EdgarTools "
              "Form 4 contract may have drifted. Inspect the raw shapes above.")
        return 1
    print(f"✅ Extracted {total} open-market insider transactions across "
          f"{len(tickers)} ticker(s). Contract looks healthy.")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] or DEFAULT_TICKERS
    raise SystemExit(asyncio.run(main(args)))
