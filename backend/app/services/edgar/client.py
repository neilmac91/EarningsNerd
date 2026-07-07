"""
EdgarTools Client

High-level client providing a clean, async interface to SEC EDGAR data.
This is the main entry point for all Edgar operations.

Usage:
    from app.services.edgar import EdgarClient, FilingType

    client = EdgarClient()

    # Get company info
    company = await client.get_company("AAPL")

    # Get latest 10-K filing
    filing = await client.get_latest_filing("AAPL", FilingType.FORM_10K)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from itertools import islice
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from edgar import Company as EdgarCompany, set_identity, find as edgar_find

from app.utils.datetimes import utcnow

from .async_executor import run_with_circuit_breaker
from .config import EDGAR_IDENTITY, FilingType, EDGAR_DEFAULT_TIMEOUT_SECONDS, EDGAR_THREAD_POOL_SIZE
from .exceptions import (
    CompanyNotFoundError,
    FilingNotFoundError,
    EdgarError,
    EdgarNetworkError,
    EdgarTimeoutError,
    EdgarRateLimitError,
    translate_edgartools_exception,
)
from .models import Company, Filing

logger = logging.getLogger(__name__)

# Initialize EdgarTools identity on module load
set_identity(EDGAR_IDENTITY)
logger.info(f"EdgarTools initialized with identity: {EDGAR_IDENTITY}")

# Semaphore for search concurrency control
# Python 3.10+ allows creating Semaphore at module level without active event loop
_edgar_search_semaphore = asyncio.Semaphore(EDGAR_THREAD_POOL_SIZE)

# Default cap on filings materialized from the recent submissions window when no explicit limit is
# given (the company filings-list path). The recent window is already SEC-bounded (~1 year or ~1000
# filings); this caps memory for very high-volume filers while leaving a generous multi-year slice
# for the year-grouped UI. Reports (10-K/10-Q/20-F/6-K/40-F) are a few per year, so 50 spans ~10y.
RECENT_FILINGS_MATERIALIZE_CAP = 50

# Negative cache for the bounded-fallback path: (ticker/cik, base_forms) that returned NOTHING even
# after a full-history load — i.e. a company that doesn't file these forms (e.g. precompute a 10-K for
# a 20-F-only FPI). Without it, every bounded call re-pays the full-history load (43 sequential shard
# GETs for a mega-filer, through the shared limiter, inside the 15s budget → circuit-breaker pressure
# on a cron sweep), since EdgarCompany is rebuilt per call. Bounded + TTL'd (per-process, mirrors
# filings.py's _filings_synced_at) so a company that later starts filing the form is re-checked.
_EMPTY_FALLBACK_TTL = timedelta(hours=6)
_EMPTY_FALLBACK_MAX = 1024
_empty_fallback_cache: Dict[Tuple[str, Tuple[str, ...]], datetime] = {}


def _empty_fallback_fresh(ticker: str, base_forms: List[str]) -> bool:
    """True when (ticker, base_forms) recently full-loaded to nothing (skip the repeat full-load).

    The key sorts base_forms so a differently-ordered same-set request is a hit, not a miss.
    """
    ts = _empty_fallback_cache.get((ticker, tuple(sorted(base_forms))))
    return ts is not None and (utcnow() - ts) < _EMPTY_FALLBACK_TTL


def _mark_empty_fallback(ticker: str, base_forms: List[str]) -> None:
    """Record that (ticker, base_forms) has no filings, evicting the oldest key past the cap."""
    key = (ticker, tuple(sorted(base_forms)))
    _empty_fallback_cache.pop(key, None)  # refresh insertion order if already present (true LRU)
    if len(_empty_fallback_cache) >= _EMPTY_FALLBACK_MAX:
        _empty_fallback_cache.pop(next(iter(_empty_fallback_cache)), None)  # insertion-ordered → oldest
    _empty_fallback_cache[key] = utcnow()


def get_filing_by_accession(company, accession_number: str) -> list:
    """Resolve a single filing by accession from an edgartools Company — RECENT window first, the full
    history only if the accession isn't recent.

    Avoids edgartools' default ``trigger_full_load=True`` (43 sequential shard downloads for a
    mega-filer) on the common summary-generation case, where the filing being summarized is recent.
    Behavior-preserving: returns the same filing object either way. Synchronous — call inside the
    edgar thread pool.
    """
    filings = list(
        company.get_filings(accession_number=accession_number, trigger_full_load=False)
    )
    if not filings:
        filings = list(
            company.get_filings(accession_number=accession_number, trigger_full_load=True)
        )
    return filings


class EdgarClient:
    """
    Async client for SEC EDGAR operations using EdgarTools.

    This client provides:
    - Company lookup and search
    - Filing retrieval by type
    - XBRL financial data extraction
    - Clean, typed return values

    All operations are async-safe, running EdgarTools in a dedicated thread pool.
    """

    def __init__(self, timeout: float = EDGAR_DEFAULT_TIMEOUT_SECONDS):
        """
        Initialize the EdgarClient.

        Args:
            timeout: Default timeout for operations in seconds
        """
        self.timeout = timeout

    async def get_company(self, ticker: str) -> Company:
        """
        Get company information by ticker symbol.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")

        Returns:
            Company object with CIK, name, and other metadata

        Raises:
            CompanyNotFoundError: If the ticker is not found
            EdgarError: For other errors
        """
        ticker = ticker.upper().strip()
        logger.debug(f"Getting company info for {ticker}")

        try:
            edgar_company = await run_with_circuit_breaker(
                lambda: EdgarCompany(ticker),
                timeout=self.timeout,
            )

            return self._transform_company(edgar_company, ticker)

        except Exception as exc:
            if "not found" in str(exc).lower():
                raise CompanyNotFoundError(ticker, cause=exc)
            raise translate_edgartools_exception(exc) from exc

    async def search_company(self, query: str, limit: int = 10) -> List[Company]:
        """
        Search for companies by name or ticker.

        Uses EdgarTools' find() function for fuzzy company name search,
        which matches against company names and tickers in the SEC database.

        Args:
            query: Search query (ticker, partial name, etc.)
            limit: Maximum number of results to return (default 10)

        Returns:
            List of matching Company objects
        """
        query = query.strip()
        if not query:
            return []

        logger.debug(f"Searching companies for query: {query}")

        # Try exact ticker lookup first (faster for exact matches)
        try:
            company = await self.get_company(query)
            logger.debug(f"Found exact ticker match: {query}")
            return [company]
        except CompanyNotFoundError:
            pass  # Fall through to fuzzy search
        except EdgarRateLimitError:
            raise  # Don't fallback for rate limits - propagate to caller
        except (EdgarTimeoutError, EdgarNetworkError) as e:
            logger.warning(f"Exact ticker lookup failed for '{query}': {e}, trying fuzzy search")
            pass  # Fall through to fuzzy search

        # Use EdgarTools find() for fuzzy company name search
        try:
            search_results = await run_with_circuit_breaker(
                lambda: edgar_find(query),
                timeout=self.timeout,
            )

            if not search_results or len(search_results) == 0:
                logger.debug(f"No companies found for query: {query}")
                return []

            # Get tickers from search results and fetch company details in parallel
            tickers = search_results.tickers if hasattr(search_results, 'tickers') else []
            logger.debug(f"Found {len(tickers)} matches for '{query}': {tickers[:5]}")

            async def fetch_company_details(ticker: str) -> Optional[Company]:
                """Fetch company details, returning None on error."""
                async with _edgar_search_semaphore:
                    try:
                        return await self.get_company(ticker)
                    except (CompanyNotFoundError, EdgarError) as e:
                        logger.warning(f"Could not fetch details for ticker {ticker}: {e}")
                        return None

            # Fetch all companies in parallel using asyncio.gather
            tasks = [fetch_company_details(ticker) for ticker in tickers[:limit]]
            company_results = await asyncio.gather(*tasks)

            # Filter out None results (failed fetches)
            companies = [company for company in company_results if company is not None]
            return companies

        except EdgarError:
            raise  # Already translated, don't double-wrap
        except Exception as exc:
            logger.error(f"Error searching companies for '{query}': {exc}")
            raise translate_edgartools_exception(exc) from exc

    async def get_filings(
        self,
        ticker: str,
        filing_type: FilingType,
        limit: Optional[int] = 10,
        include_amended: bool = True,
    ) -> List[Filing]:
        """
        Get filings for a company of a single form type.

        Thin wrapper over :meth:`get_filings_multi` (one form) so single-form callers
        (``get_latest_filing`` etc.) inherit the bounded, single-download behavior.

        Args:
            ticker: Stock ticker symbol
            filing_type: Type of filing to retrieve
            limit: Maximum number of filings to return
            include_amended: Whether to include amended filings (/A)

        Returns:
            List of Filing objects, most recent first

        Raises:
            CompanyNotFoundError: If the ticker is not found
            EdgarError: For other errors
        """
        return await self.get_filings_multi(
            ticker, [filing_type], limit=limit, include_amended=include_amended
        )

    async def get_filings_multi(
        self,
        ticker: str,
        filing_types: List[FilingType],
        limit: Optional[int] = 10,
        include_amended: bool = True,
    ) -> List[Filing]:
        """
        Get filings for a company across several form types in ONE bounded SEC round-trip.

        This is the hot path behind the company filings list. It constructs a SINGLE
        ``EdgarCompany`` and issues ONE ``get_filings(form=[...], trigger_full_load=False)`` call,
        so it downloads only the company's *recent* submissions window (one JSON) and never the
        full paginated lifetime history. A mega-filer like Morgan Stanley (105k+ lifetime filings
        across 44 submissions files) previously fanned out to a fresh ``EdgarCompany`` + full-history
        download *per form type* — the cause of the request timeout. The recent window (SEC's
        "greater of ~1000 filings or ~1 year") always contains the newest 10-K/10-Q/20-F for an
        active filer; older history accrues in our DB across loads (see the DB-first serving in
        app/routers/filings.py). ``islice`` bounds materialization to keep memory flat.

        Args:
            ticker: Stock ticker OR CIK (callers on this path pass the CIK).
            filing_types: Form types to retrieve (base forms; ``/A`` handled by ``include_amended``).
            limit: Maximum number of filings to return (None → a bounded recent default).
            include_amended: Whether to include amended filings (/A).

        Returns:
            List of Filing objects, most recent first.

        Raises:
            CompanyNotFoundError: If the ticker/CIK is not found
            EdgarError: For other errors
        """
        ticker = ticker.upper().strip()

        # Base form strings (strip any /A), de-duplicated but order-stable. edgartools' `amendments`
        # flag EXPANDS base forms to include their /A variants when True, and STRIPS /A when False —
        # so we always pass BASE forms + the boolean, never explicit "/A" strings (passing "/A" with
        # amendments=False would silently drop them). See edgar.filtering.filter_by_form.
        base_forms: List[str] = []
        wants_amended = include_amended
        for ft in filing_types:
            base = ft.value.replace("/A", "")
            if base and base not in base_forms:
                base_forms.append(base)
            # If a caller explicitly asks for an amended form (e.g. ?filing_types=10-K/A), force
            # amendments on so the requested /A filings are actually returned (correctly labeled),
            # rather than silently collapsing to the base form and returning non-amended rows. The
            # result is then a superset (base + /A); no real caller requests amended-only forms —
            # the frontend and defaults use base forms — so this only affects that explicit query.
            if ft.is_amended:
                wants_amended = True
        if not base_forms:
            return []

        # The exact form strings the caller wants back. When amendments were forced on above for an
        # explicit "/A" request, the fetch returns a superset (base + /A); trim to this set BEFORE the
        # limit is applied so unrequested base rows never consume limit slots or leak to the response
        # (the cold-company sync path would otherwise return base+/A while the cached path returns only
        # /A — inconsistent). For plain base-form requests this is a no-op.
        allowed_forms = {ft.value for ft in filing_types}
        if include_amended:
            allowed_forms |= {f"{b}/A" for b in base_forms}

        logger.debug(f"Getting {base_forms} filings for {ticker} (recent window)")

        # Bound materialization. The recent-window filter already bounds the row count for normal
        # filers; this cap protects memory for high-volume filers and keeps a generous multi-year
        # slice for the year-grouped UI.
        materialize_cap = limit if limit is not None else RECENT_FILINGS_MATERIALIZE_CAP

        try:
            edgar_company = await run_with_circuit_breaker(
                lambda: EdgarCompany(ticker),
                timeout=self.timeout,
            )

            # ONE recent-window fetch across all requested forms. trigger_full_load=False skips
            # edgartools' paginated older-filings download (the scaling cost). islice caps the
            # materialized EntityFiling objects.
            filings = await run_with_circuit_breaker(
                lambda: list(
                    islice(
                        edgar_company.get_filings(
                            form=base_forms,
                            amendments=wants_amended,
                            trigger_full_load=False,
                        ),
                        materialize_cap,
                    )
                ),
                timeout=self.timeout,
            )

            # Bounded single-latest fallback (precompute, get_latest_filing): only when the recent
            # window returns NOTHING for the requested forms does the target report sit older than
            # the window — retry once with the full history to find it. Mirrors edgartools' own
            # EntityData.latest() intent. The trigger is `== 0`, NOT `< limit`: a bounded caller's
            # default limit is 10 while an annual form yields ~1 filing/year, so `< limit` would
            # full-load on nearly every call and defeat the recent-window optimization. GATED on
            # `limit is not None`, so the unbounded filings-LIST path (limit=None) NEVER pays the
            # full-history cost — that is the whole point of QW2; those callers rely on DB-first
            # serving for deep history instead.
            if limit is not None and len(filings) == 0 and not _empty_fallback_fresh(ticker, base_forms):
                # Log so a "some company full-loads on every cron run" pattern (a company that never
                # files the requested form) is greppable in prod, where its only other trace is latency.
                logger.info(
                    "Recent window empty for %s on %s; falling back to full history", base_forms, ticker
                )
                # sort_by descending so edgartools sorts the Arrow table BEFORE materialization: the
                # full-load concats shards in `files` order (not guaranteed globally sorted), so an
                # unsorted islice(limit) could take an arbitrary old row and miss the latest. With
                # sort_by, islice(limit) is exact.
                filings = await run_with_circuit_breaker(
                    lambda: list(
                        islice(
                            edgar_company.get_filings(
                                form=base_forms,
                                amendments=wants_amended,
                                trigger_full_load=True,
                                sort_by=[("filing_date", "descending")],
                            ),
                            limit,
                        )
                    ),
                    timeout=self.timeout,
                )
                # Full history also empty → this company doesn't file these forms. Remember it so the
                # next bounded call skips the repeat full-load (until the TTL re-checks).
                if len(filings) == 0:
                    _mark_empty_fallback(ticker, base_forms)

            # Trim the fetched rows to exactly the requested forms (see allowed_forms above) BEFORE
            # the limit slice. No-op for plain base-form requests.
            filings = [f for f in filings if getattr(f, "form", None) in allowed_forms]

            # Sort by filing date descending, handling None dates gracefully
            from datetime import date as date_type_sort
            filings.sort(
                key=lambda f: f.filing_date if f.filing_date else date_type_sort.min,
                reverse=True
            )

            if limit:
                filings = filings[:limit]

            # Transform to our Filing model
            return [
                self._transform_filing(f, ticker, edgar_company.cik)
                for f in filings
            ]

        except Exception as exc:
            if "not found" in str(exc).lower():
                raise CompanyNotFoundError(ticker, cause=exc)
            raise translate_edgartools_exception(exc) from exc

    async def get_latest_filing(
        self,
        ticker: str,
        filing_type: FilingType,
    ) -> Filing:
        """
        Get the most recent filing of a specific type.

        Args:
            ticker: Stock ticker symbol
            filing_type: Type of filing to retrieve

        Returns:
            The most recent Filing object

        Raises:
            FilingNotFoundError: If no filing of this type exists
            CompanyNotFoundError: If the ticker is not found
        """
        filings = await self.get_filings(ticker, filing_type, limit=1)

        if not filings:
            raise FilingNotFoundError(ticker, filing_type.value)

        return filings[0]

    # Private transformation methods

    def _transform_company(self, edgar_company: EdgarCompany, ticker: str) -> Company:
        """Transform EdgarTools Company to our Company model."""
        return Company(
            cik=edgar_company.cik,
            ticker=ticker,
            name=edgar_company.name,
            # NOTE: the model columns are `sic`/`industry`. The previous `sic_code`/`sic_description`
            # kwargs were not valid columns, so this raised and SIC was never populated — which broke
            # the Peers cohort and the financial-remediation SIC selection. Write the real columns.
            sic=str(edgar_company.sic) if getattr(edgar_company, 'sic', None) else None,
            industry=edgar_company.industry if getattr(edgar_company, 'industry', None) else None,
            exchange=None,  # EdgarTools doesn't provide this directly
        )

    def _transform_filing(self, edgar_filing, ticker: str, cik: str) -> Filing:
        """Transform EdgarTools Filing to our Filing model."""
        from datetime import date as date_type

        # EdgarTools exposes Company.cik as an int; normalize so string ops (lstrip) work
        cik = str(cik)

        # Parse filing date with error handling
        filing_date = edgar_filing.filing_date
        if isinstance(filing_date, str):
            try:
                filing_date = date_type.fromisoformat(filing_date)
            except (ValueError, TypeError):
                logger.warning(f"Invalid filing date format: {filing_date}")
                filing_date = None

        # Parse period end date with error handling. Read the CHEAP `report_date` attribute that
        # EntityFiling populates directly from the submissions JSON `reportDate` — NOT
        # `period_of_report`, which is a property that lazily downloads the filing SGML
        # (a blocking per-filing sec.gov fetch; even `hasattr` triggers it). On a listing of N
        # filings that reintroduced N network calls and undercut the single-download win. The value
        # is the same period-end date.
        period_end = None
        report_date = getattr(edgar_filing, 'report_date', None)
        if report_date:
            if isinstance(report_date, str):
                try:
                    period_end = date_type.fromisoformat(report_date)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid report_date format: {report_date}")
                    period_end = None
            else:
                period_end = report_date

        # Determine filing type enum - use non-strict mode to get UNKNOWN for unrecognized forms
        filing_type = FilingType.from_string(edgar_filing.form, strict=False)

        # Generate SEC filing URL
        # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/
        accession_clean = edgar_filing.accession_number.replace("-", "")
        cik_clean = cik.lstrip("0") or "0"  # Remove leading zeros, but keep at least "0"
        sec_url = f"https://www.sec.gov/Archives/edgar/data/{cik_clean}/{accession_clean}/"

        # Resolve the absolute document URL from listing metadata only. EntityFiling
        # carries `primary_document` as a plain attribute; do NOT touch `filing_url`,
        # which lazily downloads the filing SGML (a blocking SEC fetch per filing that
        # would turn every metadata listing into N network calls and can raise mid-list).
        document_url = None
        primary_document = getattr(edgar_filing, 'primary_document', None)
        if primary_document:
            document_url = urljoin(sec_url, primary_document)

        return Filing(
            accession_number=edgar_filing.accession_number,
            filing_type=filing_type,
            filing_date=filing_date,
            period_end_date=period_end,
            ticker=ticker,
            cik=cik,
            company_name=edgar_filing.company if hasattr(edgar_filing, 'company') else None,
            document_url=document_url,
            sec_url=sec_url,
        )


# Singleton instance for convenience
edgar_client = EdgarClient()
