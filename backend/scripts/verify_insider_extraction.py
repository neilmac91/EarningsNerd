#!/usr/bin/env python3
"""Check the stored insider scan's offline Form 4 parse against real filings on SEC EDGAR (ADR 0009).

The unit tests parse Form 4 documents written to SEC's schema, with the network closed. This is the other half:
for each ticker it lists the company's most recent Form 4s, fetches each one's document the way the scan does
(``insider_scan_service``: the XML at the listing's file name, the submission's text file on a 404), parses it
offline (``insider_form4.parse_form4``), and compares the rows with the ones edgartools' own parse gives for
the same filing (``filing.obj()``, the path the endpoint used before the scan). A row that differs is printed.

Run it before the insider panel is shown to anyone, and after any edgartools upgrade.

Usage:
    cd backend
    python scripts/verify_insider_extraction.py                # defaults: AAPL, NVDA, JPM
    python scripts/verify_insider_extraction.py TSLA MSFT      # custom tickers
    python scripts/verify_insider_extraction.py --filings 10 AAPL

Requests to SEC, paced by the process's own limits: per ticker one listing, then per filing one document (two
when its XML is not at the listing's name) and edgartools' own two or so for the comparison. With the defaults
(3 tickers, 5 filings each) that is about 50. Requires edgartools, outbound access to SEC EDGAR and
``EDGAR_IDENTITY`` set as the app requires it.

Exit code: 0 when every filing read gave the same rows both ways, 1 when any differed or none could be read.
"""

import argparse
import asyncio
import os
import sys
from itertools import islice
from types import SimpleNamespace

# Make `app` importable when run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_TICKERS = ["AAPL", "NVDA", "JPM"]
DEFAULT_FILINGS = 5


def _hr(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _listing(ticker: str, filings: int):
    """The company's CIK and its most recent Form 4s, as edgartools lists them (one or two requests)."""
    from edgar import Company as EdgarCompany

    company = EdgarCompany(ticker)
    listed = company.get_filings(form="4", amendments=False, trigger_full_load=False)
    return str(company.cik), list(islice(listed, filings))


async def _verify_ticker(ticker: str, filings: int) -> tuple[int, int]:
    """(filings whose rows agree, filings that differ or could not be read) for one ticker."""
    from app.services import insider_scan_service as scan
    from app.services.insider_form4 import Form4ParseError, parse_form4
    from app.services.ownership_extractor import _iso_date, extract_form4_transactions
    from app.utils.sec_urls import normalize_cik

    _hr(ticker)
    raw_cik, listed = await asyncio.to_thread(_listing, ticker, filings)
    cik = normalize_cik(raw_cik)
    print(f"CIK {cik}: {len(listed)} Form 4 filing(s) listed")
    agree = differ = 0
    for filing in listed:
        accession = str(filing.accession_no)
        filed = _iso_date(filing.filing_date)
        stats = scan.StepStats()
        row = SimpleNamespace(accession=accession, primary_document=str(filing.primary_document or ""))
        try:
            document = await scan._fetch_document(cik, row, scan._default_fetch, stats)
            if document is None:
                print(f"  {accession}: no ownership document in the filing (the scan stores no_xml)")
                continue
            parsed = parse_form4(document, accession=accession, filed_date=filed)
            live = extract_form4_transactions(await asyncio.to_thread(filing.obj), accession=accession, filed_date=filed)
        except Form4ParseError as exc:
            differ += 1
            print(f"  {accession}: the offline parse refused it: {exc}")
            continue
        except Exception as exc:  # noqa: BLE001 - report and carry on with the next filing
            differ += 1
            print(f"  {accession}: {type(exc).__name__}: {exc}")
            continue
        issuer = "this issuer" if parsed.issuer_cik == cik else f"another issuer (CIK {parsed.issuer_cik}): stores no trades"
        if parsed.transactions == live:
            agree += 1
            print(f"  {accession}: {len(live)} trade(s), the same both ways; {stats.requests} request(s); reports {issuer}")
            continue
        differ += 1
        print(f"  {accession}: DIFFERS ({len(parsed.transactions)} offline, {len(live)} from edgartools); reports {issuer}")
        for offline_row, live_row in zip(parsed.transactions, live):
            for key in sorted(set(offline_row) | set(live_row)):
                if offline_row.get(key) != live_row.get(key):
                    print(f"      {key}: offline {offline_row.get(key)!r}, edgartools {live_row.get(key)!r}")
    return agree, differ


async def main(tickers: list[str], filings: int) -> int:
    from edgar import set_identity

    from app.services.edgar.config import EDGAR_IDENTITY

    set_identity(EDGAR_IDENTITY)   # as the app sets it; its value is not printed
    agree = differ = 0
    for ticker in tickers:
        try:
            same, different = await _verify_ticker(ticker.upper().strip(), filings)
        except Exception as exc:  # noqa: BLE001 - report and carry on with the next ticker
            _hr(f"{ticker}: FAILED")
            print(f"  {type(exc).__name__}: {exc}")
            differ += 1
            continue
        agree, differ = agree + same, differ + different
    _hr("RESULT")
    print(f"{agree} filing(s) gave the same rows offline and from edgartools; {differ} differed or could not be read.")
    return 0 if agree and not differ else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS)
    parser.add_argument("--filings", type=int, default=DEFAULT_FILINGS, help="Form 4s to read per ticker")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.tickers, max(1, min(args.filings, 20)))))
