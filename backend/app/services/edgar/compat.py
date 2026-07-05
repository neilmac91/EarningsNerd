"""
Backward Compatibility Layer

This module provides compatibility wrappers that allow existing code
to use the new EdgarTools services through the same interface as the
legacy services.

Usage:
    from app.services.edgar.compat import xbrl_service, sec_edgar_service
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from .client import edgar_client
from .xbrl_service import edgar_xbrl_service, clear_xbrl_cache, get_xbrl_cache_stats
from .exceptions import EdgarError
from .config import FilingType, EDGAR_IDENTITY
from .circuit_breaker import edgar_circuit_breaker, CircuitOpenError
from app.services.sec_rate_limiter import sec_rate_limiter

logger = logging.getLogger(__name__)


class SECEdgarServiceCompat:
    """
    Compatibility wrapper for legacy SECEdgarService interface.

    This allows existing code that imports sec_edgar_service to continue
    working while using the new EdgarTools backend.
    """

    # Cached company tickers for fast local search
    _tickers_cache: Optional[Dict[str, Dict]] = None
    _tickers_cache_time: Optional[datetime] = None
    _cache_ttl = timedelta(hours=24)

    async def _get_cached_tickers(self) -> Dict[str, Dict]:
        """
        Fetch company tickers from SEC with two-tier caching and stale fallback.

        Cache hierarchy:
        - L1: In-memory class-level cache (fastest)
        - L2: Redis cache (persistent, shared across instances)
        - Fallback: Serve stale L1 cache if fetch fails
        """
        # L1: Check in-memory cache first
        if (
            self._tickers_cache is not None
            and self._tickers_cache_time is not None
            and datetime.now() - self._tickers_cache_time < self._cache_ttl
        ):
            return self._tickers_cache

        # L2: Check Redis cache
        redis_key = "sec:company_tickers"
        redis_data = await self._get_tickers_from_redis(redis_key)
        if redis_data is not None:
            logger.debug("SEC tickers L2 cache hit")
            SECEdgarServiceCompat._tickers_cache = redis_data
            SECEdgarServiceCompat._tickers_cache_time = datetime.now()
            return redis_data

        # Fetch from SEC EDGAR
        try:
            async with edgar_circuit_breaker:
                # Route the sec.gov GET through the rate limiter (10 req/s + 429 backoff); it carried
                # the breaker but bypassed the limiter. The client is created ONCE outside the
                # retryable closure so execute_with_backoff reuses the pool across retries.
                async with httpx.AsyncClient() as client:
                    async def _do_request() -> httpx.Response:
                        resp = await client.get(
                            "https://www.sec.gov/files/company_tickers.json",
                            headers={"User-Agent": EDGAR_IDENTITY},
                            timeout=15.0,
                        )
                        resp.raise_for_status()
                        return resp

                    response = await sec_rate_limiter.execute_with_backoff(_do_request)
                    data = response.json()

                    # Update both cache tiers
                    SECEdgarServiceCompat._tickers_cache = data
                    SECEdgarServiceCompat._tickers_cache_time = datetime.now()
                    await self._set_tickers_to_redis(redis_key, data)

                    logger.debug("SEC tickers fetched and cached (L1+L2)")
                    return data
        except CircuitOpenError as e:
            if self._tickers_cache is not None:
                logger.warning("SEC circuit breaker open, serving stale cache: %s", e)
                return self._tickers_cache
            raise EdgarError(f"SEC EDGAR circuit breaker is open: {e}", cause=e)
        except Exception as e:
            if self._tickers_cache is not None:
                logger.warning("SEC ticker fetch failed, serving stale cache: %s", e)
                return self._tickers_cache
            raise EdgarError(f"Unable to fetch SEC ticker list: {e}", cause=e)

    async def _get_tickers_from_redis(self, key: str) -> Optional[Dict[str, Dict]]:
        """Get tickers data from Redis cache (L2)."""
        try:
            from app.services.redis_service import cache_get
            return await cache_get(key)
        except Exception as e:
            logger.debug(f"Redis L2 tickers cache get failed: {e}")
            return None

    async def _set_tickers_to_redis(self, key: str, data: Dict[str, Dict]) -> bool:
        """Set tickers data in Redis cache (L2)."""
        try:
            from app.services.redis_service import cache_set, CacheTTL
            return await cache_set(key, data, CacheTTL.SEC_TICKERS)
        except Exception as e:
            logger.debug(f"Redis L2 tickers cache set failed: {e}")
            return False

    def _local_search(self, tickers_data: Dict[str, Dict], query: str) -> List[Dict[str, Any]]:
        """Fast in-memory search over cached company tickers."""
        query_lower = query.lower().strip()
        if not query_lower:
            return []

        exact_matches: List[Dict[str, Any]] = []
        partial_matches: List[Dict[str, Any]] = []
        max_results = 20

        for company_data in tickers_data.values():
            if not isinstance(company_data, dict):
                continue

            ticker = company_data.get("ticker", "").strip()
            name = company_data.get("title", "").strip()
            cik = company_data.get("cik_str", "")

            entry = {
                "ticker": ticker,
                "name": name,
                "cik": str(cik).zfill(10),
                "exchange": None,
            }

            if query_lower == ticker.lower():
                exact_matches.append(entry)
            elif query_lower in name.lower() or query_lower in ticker.lower():
                partial_matches.append(entry)

            if len(exact_matches) >= max_results:
                break

        results = exact_matches[:max_results]
        remaining = max_results - len(results)
        if remaining > 0:
            results.extend(partial_matches[:remaining])
        return results

    async def search_company(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for companies by ticker or name.

        Uses fast local search on cached SEC ticker data. Falls back to
        EdgarTools fuzzy search only if local search yields no results.

        Returns legacy format:
        [{"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193", "exchange": None}]

        Raises:
            EdgarError: If there's a network or API error
        """
        # Primary: fast local search on cached data (<1ms)
        try:
            tickers_data = await self._get_cached_tickers()
            results = self._local_search(tickers_data, query)
            if results:
                return results
        except EdgarError:
            raise
        except Exception as e:
            logger.warning(f"Local search failed, trying EdgarTools: {e}")

        # Fallback: EdgarTools fuzzy search (for queries local search can't match)
        try:
            companies = await edgar_client.search_company(query)
            return [c.to_dict() for c in companies]
        except EdgarError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching company: {e}")
            raise EdgarError(f"Failed to search companies: {e}", cause=e)

    async def get_company_submissions(self, cik: str) -> Dict[str, Any]:
        """
        Get company submissions (filings).

        Returns legacy format with nested filings structure.

        Raises:
            EdgarError: If there's a network or API error
        """
        try:
            # Get filings for common types
            filings_10k = await edgar_client.get_filings(
                cik, FilingType.FORM_10K, limit=10, include_amended=True
            )
            filings_10q = await edgar_client.get_filings(
                cik, FilingType.FORM_10Q, limit=10, include_amended=True
            )

            all_filings = filings_10k + filings_10q
            # Sort by date descending, handling None filing_date gracefully
            from datetime import date as date_type
            all_filings.sort(
                key=lambda f: f.filing_date if f.filing_date else date_type.min,
                reverse=True
            )

            return {
                "filings": {
                    "recent": {
                        "form": [f.filing_type.value for f in all_filings],
                        "filingDate": [f.filing_date.isoformat() if f.filing_date else None for f in all_filings],
                        "accessionNumber": [f.accession_number for f in all_filings],
                    }
                }
            }
        except EdgarError:
            # Propagate EdgarError (includes network errors) to caller
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting submissions: {e}")
            raise EdgarError(f"Failed to get company submissions: {e}", cause=e)

    async def get_filings(
        self,
        cik: str,
        filing_types: List[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get filings for a company.

        Returns legacy format:
        [{
            "filing_type": "10-K",
            "filing_date": "2024-01-15",
            "report_date": "2023-12-31",
            "accession_number": "...",
            "document_url": "...",
            "sec_url": "...",
            "cik": "..."
        }]
        """
        if filing_types is None:
            filing_types = ["10-K", "10-Q"]

        try:
            all_filings = []

            for form_type in filing_types:
                # Non-strict resolution: known forms (incl. FPI 20-F/6-K/40-F) map to a member;
                # only genuinely unrecognized strings fall through to UNKNOWN and are skipped. This
                # replaces the old strict() + ValueError path that silently dropped 20-F/6-K.
                ft = FilingType.from_string(form_type, strict=False)
                if ft == FilingType.UNKNOWN:
                    logger.warning(f"Unknown filing type: {form_type}")
                    continue
                filings = await edgar_client.get_filings(
                    cik, ft, limit=limit, include_amended=False
                )
                all_filings.extend(filings)

            # Sort by date descending, handling None filing_date gracefully
            from datetime import date as date_type
            all_filings.sort(
                key=lambda f: f.filing_date if f.filing_date else date_type.min,
                reverse=True
            )

            if limit:
                all_filings = all_filings[:limit]

            return [f.to_dict() for f in all_filings]

        except EdgarError:
            # Propagate EdgarError (includes network errors) to caller
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting filings: {e}")
            raise EdgarError(f"Failed to get filings: {e}", cause=e)

    async def get_filing_document(
        self,
        document_url: str,
        timeout: Optional[float] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Get filing document content by URL.

        Note: This method uses direct HTTP as EdgarTools doesn't expose URL-based access.
        """
        timeout = timeout or 60.0
        import asyncio as aio

        try:
            async with edgar_circuit_breaker:
                async with httpx.AsyncClient() as client:
                    # Each attempt acquires a limiter token before hitting sec.gov (the fetch carried
                    # the breaker but bypassed the limiter). The manual exponential backoff below owns
                    # retries, so use execute() (token wait) not execute_with_backoff.
                    async def _do_get() -> httpx.Response:
                        resp = await client.get(
                            document_url,
                            headers={"User-Agent": EDGAR_IDENTITY},
                            timeout=timeout,
                            follow_redirects=True,
                        )
                        resp.raise_for_status()
                        return resp

                    for attempt in range(max_retries):
                        try:
                            response = await sec_rate_limiter.execute(_do_get)
                            return response.text
                        except Exception:
                            if attempt == max_retries - 1:
                                raise
                            await aio.sleep(2 ** attempt)
        except CircuitOpenError as e:
            raise EdgarError(f"SEC EDGAR circuit breaker is open: {e}", cause=e)
        except Exception as e:
            raise EdgarError(f"Failed to fetch document: {e}", cause=e)

    async def get_company_tickers(
        self,
        force_refresh: bool = False,
    ) -> Dict[str, Dict]:
        """
        Get all company tickers from SEC (delegates to cached fetch).
        """
        if force_refresh:
            SECEdgarServiceCompat._tickers_cache_time = None
        return await self._get_cached_tickers()


class XBRLServiceCompat:
    """
    Compatibility wrapper for legacy XBRLService interface.

    This allows existing code that imports xbrl_service to continue
    working while using the new EdgarTools backend.
    """

    async def get_xbrl_data(
        self,
        accession_number: str,
        cik: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get XBRL data for a filing.

        Returns legacy format:
        {
            "revenue": [{"period": "...", "value": ..., "form": "...", "accn": "..."}],
            "net_income": [...],
            ...
        }
        """
        return await edgar_xbrl_service.get_xbrl_data(accession_number, cik)

    def extract_standardized_metrics(self, xbrl_data: Dict) -> Dict[str, Any]:
        """
        Extract standardized metrics from XBRL data.

        Returns legacy format with current, prior, change, and series.
        """
        return edgar_xbrl_service.extract_standardized_metrics(xbrl_data)

    async def get_filing_sections(
        self,
        accession_number: str,
        cik: str,
        filing_type: str,
    ) -> Optional[Dict[str, str]]:
        """
        Extract critical sections (financials / mda / risk) via edgartools' native parser.

        Returns a dict of clean section text, or None when unavailable (callers fall back
        to the legacy regex extractor).
        """
        return await edgar_xbrl_service.get_filing_sections(accession_number, cik, filing_type)


# Singleton instances for drop-in replacement
sec_edgar_service = SECEdgarServiceCompat()
xbrl_service = XBRLServiceCompat()

# Re-export cache functions for admin routes
__all__ = [
    "sec_edgar_service",
    "xbrl_service",
    "clear_xbrl_cache",
    "get_xbrl_cache_stats",
]
