"""Insider-activity orchestration (P4, SEC Form 4).

Resolves a ticker, pulls its most recent Form 4 filings from SEC EDGAR via
EdgarTools, extracts the open-market trades (``ownership_extractor``), and
aggregates them into a buy/sell signal with a Rule 10b5-1 split.

Design notes
------------
* **Live SEC read, no DB.** Form 4 data isn't in our ``financial_fact`` table;
  this reads EDGAR on demand and caches the result in-process (TTL).
* **EdgarTools is the only heavy dependency** and it's synchronous, so every
  call goes through ``run_with_circuit_breaker`` (dedicated thread pool +
  timeout + circuit breaker), exactly like the rest of the EDGAR integration.
* **Lazy import of ``edgar``.** The top of this module imports nothing from
  EdgarTools, so it stays importable (and unit-testable via an injected
  ``fetcher``) in environments where edgartools/cryptography aren't installed.
* **Fetch once, window many.** Transactions are cached per ``(ticker,
  limit_filings)``; the trailing-window aggregation is pure and done in-memory,
  so changing ``window_days`` never re-hits SEC.
"""

from __future__ import annotations

import logging
import time
from itertools import islice
from threading import Lock
from typing import Any, Awaitable, Callable, Optional

from app.services.ownership_extractor import (
    _iso_date,
    _safe_getattr,
    extract_form4_transactions,
    summarize_insider_activity,
    transactions_in_window,
)

logger = logging.getLogger(__name__)

# How many of the most-recent Form 4 filings to pull per company. Enough to
# cover a quarter or two of activity for an active issuer without a huge fan-out.
DEFAULT_LIMIT_FILINGS = 60
# How many individual transactions to return in the response (most recent first).
DEFAULT_RECENT_LIMIT = 30
# Each filing is a separate fetch+parse inside the thread pool. Kept in line with
# the /api/filings/ budget (60s) and below the endpoint's request-timeout ceiling
# (see REQUEST_TIMEOUT_SUFFIXES in main.py) so this inner timeout wins, surfacing
# a clean 502 rather than a generic 504.
INSIDER_FETCH_TIMEOUT_SECONDS = 60.0
# In-process cache TTL. Insider feeds change at most a few times a day.
CACHE_TTL_SECONDS = 30 * 60

# A "bundle" is the raw, un-windowed result of a SEC fetch:
#   {"ticker", "company_name", "cik", "transactions": list[dict]}
# Injectable so tests can supply a fake without touching EdgarTools.
Fetcher = Callable[[str, int], Awaitable[dict]]

_cache: dict[tuple[str, int], tuple[float, dict]] = {}
_cache_lock = Lock()


def _cache_get(key: tuple[str, int]) -> Optional[dict]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        ts, bundle = entry
        if time.monotonic() - ts > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return bundle


def _cache_set(key: tuple[str, int], bundle: dict) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic(), bundle)


def clear_cache() -> None:
    """Drop the in-process insider cache (used by tests/admin)."""
    with _cache_lock:
        _cache.clear()


def _safe_attr(obj: Any, *names: str) -> Any:
    """First non-None attribute among ``names``, tolerant of edgartools
    method-vs-property drift (delegates to ``_safe_getattr``)."""
    for name in names:
        val = _safe_getattr(obj, name)
        if val is not None:
            return val
    return None


def _collect_insider_data_sync(ticker: str, limit_filings: int) -> dict:
    """Synchronous EdgarTools work — runs inside the EDGAR thread pool.

    Resolves the company, walks its most recent Form 4 filings, and extracts the
    open-market trades from each. Raises ``CompanyNotFoundError`` for an unknown
    ticker so the router can return a clean 404; other EDGAR failures are
    translated to the standard ``EdgarError`` hierarchy (so the circuit breaker
    sees real network errors).
    """
    from edgar import Company as EdgarCompany  # lazy: heavy dependency

    from app.services.edgar.exceptions import (
        CompanyNotFoundError,
        translate_edgartools_exception,
    )

    try:
        company = EdgarCompany(ticker)
    except Exception as exc:
        if "not found" in str(exc).lower():
            raise CompanyNotFoundError(ticker, cause=exc)
        raise translate_edgartools_exception(exc) from exc

    # An unknown ticker can yield a hollow Company rather than raising.
    cik = _safe_attr(company, "cik")
    if not cik:
        raise CompanyNotFoundError(ticker)

    company_name = _safe_attr(company, "name", "company_name")
    resolved_ticker = _safe_attr(company, "ticker") or ticker

    transactions: list[dict] = []
    try:
        # trigger_full_load=False: the panel shows RECENT insider activity, and Form 4s are dense
        # (insiders file frequently), so the recent submissions window suffices. The default
        # (trigger_full_load=True) would download the company's entire lifetime history first — the
        # same mega-filer cost the filing-load fix removed from listings — before islice bounds it.
        filings = company.get_filings(form="4", amendments=False, trigger_full_load=False)
    except Exception as exc:
        raise translate_edgartools_exception(exc) from exc

    for filing in islice(filings, limit_filings):
        accession = str(_safe_attr(filing, "accession_number", "accession_no") or "")
        filed_date = _iso_date(_safe_attr(filing, "filing_date", "filed_date"))
        try:
            form4 = filing.obj()
        except Exception as exc:  # one bad filing must not sink the feed
            logger.warning("Form 4 obj() failed for %s: %s", accession, exc)
            continue
        transactions.extend(
            extract_form4_transactions(form4, accession=accession, filed_date=filed_date)
        )

    return {
        "ticker": str(resolved_ticker).upper(),
        "company_name": company_name,
        "cik": str(cik) if cik else None,
        "transactions": transactions,
    }


async def _default_fetch(ticker: str, limit_filings: int) -> dict:
    """Production fetcher: EdgarTools in the thread pool, circuit-breaker guarded."""
    # Lazy import: the app.services.edgar package pulls in edgartools at import
    # time, so keep it out of module scope to stay importable (and unit-testable
    # via an injected fetcher) where edgartools isn't installed.
    from app.services.edgar.async_executor import run_with_circuit_breaker

    return await run_with_circuit_breaker(
        lambda: _collect_insider_data_sync(ticker, limit_filings),
        timeout=INSIDER_FETCH_TIMEOUT_SECONDS,
    )


def _sort_recent(transactions: list[dict]) -> list[dict]:
    """Most-recent first, by transaction date (falling back to filed date)."""

    def key(t: dict) -> str:
        return _iso_date(t.get("transaction_date")) or _iso_date(t.get("filed_date")) or ""

    return sorted(transactions, key=key, reverse=True)


async def get_insider_activity(
    ticker: str,
    *,
    window_days: int = 90,
    limit_filings: int = DEFAULT_LIMIT_FILINGS,
    recent_limit: int = DEFAULT_RECENT_LIMIT,
    fetcher: Optional[Fetcher] = None,
) -> dict:
    """Return the insider-activity summary + recent trades for a ticker.

    Raises ``CompanyNotFoundError`` for an unknown ticker and the usual
    ``EdgarError`` subclasses for SEC/network failures; the router maps these to
    404 / 502.
    """
    ticker_norm = ticker.upper().strip()
    fetch = fetcher or _default_fetch
    cache_key = (ticker_norm, limit_filings)

    bundle = _cache_get(cache_key)
    if bundle is None:
        bundle = await fetch(ticker_norm, limit_filings)
        _cache_set(cache_key, bundle)

    all_txns = bundle.get("transactions") or []
    # Window the returned list + count to match the (windowed) summary, so a response for
    # window_days=30 never lists trades from outside that window or reports a total that
    # disagrees with the signal. `summary` windows internally; reuse the same slice here.
    windowed = transactions_in_window(all_txns, window_days)
    summary = summarize_insider_activity(all_txns, window_days=window_days)
    recent = _sort_recent(windowed)[:recent_limit]

    return {
        "ticker": bundle.get("ticker") or ticker_norm,
        "company_name": bundle.get("company_name"),
        "cik": bundle.get("cik"),
        "window_days": window_days,
        "summary": summary,
        "transactions": recent,
        "total_transactions": len(windowed),
    }
