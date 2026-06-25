#!/usr/bin/env python3
"""Phase 0 spike: live verification that the FPI (foreign private issuer) path works on real SEC data.

EarningsNerd showed "no filings present" for Alibaba ($BABA) because foreign issuers file 20-F
(annual) and 6-K (interim) instead of 10-K/10-Q, and our discovery path was hardwired to the
domestic forms. This script proves — against *live* SEC EDGAR via edgartools — that the assumptions
the FPI roadmap (tasks/fpi-support-roadmap.md) is built on actually hold, before we wire the rest of
the feature. It is the bridge between the offline unit tests (which prove the FilingType logic) and
production (which depends on edgartools/SEC shapes).

For each ticker it checks:
  1. The company resolves to a CIK.
  2. get_filings(form="20-F") and form="6-K" return at least one filing (the discovery fix premise).
  3. get_financials() returns a non-None Financials object (Phase 2/3 premise).
  4. The reporting-currency symbol resolves (Phase 3 premise — e.g. BABA reports in RMB, NOT USD).
  5. The 20-F exposes recognizable sections / items (Phase 2 premise).

Usage:
    cd backend
    python scripts/verify_fpi_extraction.py                 # defaults: BABA, TSM, ASML
    python scripts/verify_fpi_extraction.py BABA NVO TM     # custom FPI tickers
    EDGAR_IDENTITY="you@example.com" python scripts/verify_fpi_extraction.py BABA

Requires: edgartools installed and outbound network access to SEC EDGAR.
Exit code is non-zero if any ticker fails the discovery premise (20-F or 6-K not found) — a strong
signal that the edgartools/SEC contract has drifted and the roadmap needs revisiting.
"""

import os
import sys
from itertools import islice

# Make `app` importable when run from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_TICKERS = ["BABA", "TSM", "ASML"]
PROBE_FORMS = ["20-F", "6-K"]


def _hr(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _short(value, width: int = 100) -> str:
    s = repr(value)
    return s if len(s) <= width else s[: width - 3] + "..."


def _first_filing(company, form: str):
    """Return the most recent filing of `form` (base form only, no amendments), or None."""
    filings = company.get_filings(form=form, amendments=False)
    return next(iter(islice(filings, 1)), None)


def _currency_symbol(financials) -> str:
    """Best-effort reporting-currency symbol from edgartools (varies by version)."""
    for attr in ("get_currency_symbol", "currency_symbol", "currency"):
        getter = getattr(financials, attr, None)
        if getter is None:
            continue
        try:
            return str(getter() if callable(getter) else getter)
        except Exception:  # noqa: BLE001 — diagnostic script, never fatal
            continue
    return "<unknown>"


def _section_names(filing_obj) -> list:
    """Best-effort list of section/item names exposed by the parsed 20-F object."""
    for attr in ("sections", "items"):
        value = getattr(filing_obj, attr, None)
        if value is None:
            continue
        try:
            if isinstance(value, dict):
                return list(value.keys())
            return list(value)
        except Exception:  # noqa: BLE001
            continue
    return []


def verify_ticker(ticker: str) -> bool:
    """Run the FPI premise checks for one ticker. Returns True if the discovery premise holds."""
    from edgar import Company as EdgarCompany
    # Importing the app client configures the SEC User-Agent identity (set_identity) on import,
    # which edgartools requires before any SEC request. Falls back to a direct set_identity if the
    # app package can't be imported (e.g. running this script outside the backend venv).
    try:
        import app.services.edgar.client  # noqa: F401 — side effect: set_identity()
    except Exception:  # noqa: BLE001
        from edgar import set_identity
        set_identity(os.environ.get("EDGAR_IDENTITY", "neil@earningsnerd.io"))

    _hr(f"{ticker}")
    try:
        company = EdgarCompany(ticker)
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ could not resolve company: {exc}")
        return False

    print(f"  company: name={getattr(company, 'name', None)!r} cik={getattr(company, 'cik', None)!r}")

    # (2) Discovery premise — the actual root-cause fix.
    found_forms = {}
    for form in PROBE_FORMS:
        try:
            first = _first_filing(company, form)
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ get_filings(form={form!r}) raised: {exc}")
            first = None
        if first is not None:
            accn = getattr(first, "accession_number", None) or getattr(first, "accession_no", None)
            print(f"  ✓ {form}: latest accession={accn!r} filed={getattr(first, 'filing_date', None)!r}")
            found_forms[form] = first
        else:
            print(f"  – {form}: none found")

    discovery_ok = bool(found_forms)

    # (3)+(4) Financials + currency premise (Phase 2/3) — informational, not gating.
    try:
        financials = company.get_financials()
        if financials is None:
            print("  – get_financials(): None (Phase 3 will need a fallback)")
        else:
            print(f"  ✓ get_financials(): {type(financials).__name__}; currency={_currency_symbol(financials)}")
    except Exception as exc:  # noqa: BLE001
        print(f"  – get_financials() raised: {exc}")

    # (5) 20-F section/item premise (Phase 2) — informational, not gating.
    twentyf = found_forms.get("20-F")
    if twentyf is not None:
        try:
            obj = twentyf.obj()
            names = _section_names(obj)
            print(f"  ✓ 20-F.obj(): {type(obj).__name__}; {len(names)} sections")
            if names:
                print(f"      e.g. {[str(n) for n in names[:6]]}")
        except Exception as exc:  # noqa: BLE001
            print(f"  – 20-F.obj() raised: {exc}")

    if not discovery_ok:
        print(f"  ✗ DISCOVERY FAILED for {ticker}: neither 20-F nor 6-K found")
    return discovery_ok


def main() -> int:
    tickers = sys.argv[1:] or DEFAULT_TICKERS
    _hr("FPI extraction spike — live SEC EDGAR via edgartools")
    print(f"tickers: {tickers}")
    print(f"identity: {os.environ.get('EDGAR_IDENTITY', '(default)')}")

    results = {t: verify_ticker(t) for t in tickers}

    _hr("SUMMARY")
    for ticker, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {ticker}")

    failures = [t for t, ok in results.items() if not ok]
    if failures:
        print(f"\nDiscovery premise FAILED for: {failures}")
        return 1
    print("\nAll tickers passed the discovery premise (20-F or 6-K found).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
