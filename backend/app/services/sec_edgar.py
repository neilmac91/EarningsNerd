import httpx
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.config import settings

logger = logging.getLogger(__name__)


class SECEdgarServiceError(RuntimeError):
    """Raised when SEC EDGAR is unavailable or responds unexpectedly."""

    def __init__(self, message: str, *, cause: Optional[Exception] = None) -> None:
        super().__init__(message)
        self.cause = cause

class SECEdgarService:
    BASE_URL = settings.SEC_EDGAR_BASE_URL
    USER_AGENT = settings.SEC_USER_AGENT  # SEC requires proper User-Agent format
    
    # Cache for company tickers (avoid fetching on every search)
    _tickers_cache: Optional[Dict[str, Dict]] = None
    _tickers_cache_time: Optional[datetime] = None
    _cache_ttl_hours = 24  # Cache for 24 hours
    
    async def get_company_tickers(self, force_refresh: bool = False) -> Dict[str, Dict]:
        """Fetch all company tickers from SEC with caching"""
        # Check cache first
        if not force_refresh and self._tickers_cache is not None and self._tickers_cache_time is not None:
            age = datetime.now() - self._tickers_cache_time
            if age < timedelta(hours=self._cache_ttl_hours):
                return self._tickers_cache
        
        # Fetch fresh data
        url = "https://www.sec.gov/files/company_tickers.json"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=15.0  # Reduced timeout for faster failure
                )
                response.raise_for_status()
                tickers_data = response.json()
                
                # Update cache
                self._tickers_cache = tickers_data
                self._tickers_cache_time = datetime.now()
                
                return tickers_data
        except httpx.TimeoutException as exc:
            # If timeout, try to use stale cache if available
            if self._tickers_cache is not None:
                logger.warning("SEC ticker list timeout, serving stale cache.")
                return self._tickers_cache
            raise SECEdgarServiceError("SEC ticker list request timed out.", cause=exc)
        except Exception as exc:
            # If error, try to use stale cache if available
            if self._tickers_cache is not None:
                logger.warning("SEC ticker list failed, serving stale cache: %s", exc)
                return self._tickers_cache
            raise SECEdgarServiceError("Unable to fetch SEC ticker list.", cause=exc)
    
    async def search_company(self, query: str) -> List[Dict]:
        """Search for companies by name or ticker"""
        try:
            tickers_data = await self.get_company_tickers()
        except Exception as e:
            # If we can't fetch tickers, return empty list
            logger.warning("Error fetching company tickers: %s", e)
            return []
        
        query_lower = query.lower().strip()
        
        if not query_lower:
            return []
        
        # Priority search: exact ticker match first, then name matches
        exact_matches = []
        partial_matches = []
        max_results = 20
        
        # SEC company_tickers.json structure: {"0": {"cik_str": ..., "ticker": ..., "title": ...}, ...}
        for key, company_data in tickers_data.items():
            if not isinstance(company_data, dict):
                continue
                
            ticker = company_data.get("ticker", "").strip()
            name = company_data.get("title", "").strip()
            cik = company_data.get("cik_str", "")
            
            # Exact ticker match (highest priority)
            if query_lower == ticker.lower():
                exact_matches.append({
                    "ticker": ticker,
                    "name": name,
                    "cik": str(cik).zfill(10),
                    "exchange": None
                })
            # Exact CIK match
            elif query_lower == str(cik).zfill(10):
                exact_matches.append({
                    "ticker": ticker,
                    "name": name,
                    "cik": str(cik).zfill(10),
                    "exchange": None
                })
            # Name or ticker contains query
            elif (query_lower in name.lower() or query_lower in ticker.lower()):
                partial_matches.append({
                    "ticker": ticker,
                    "name": name,
                    "cik": str(cik).zfill(10),
                    "exchange": None
                })
            
            # Early exit if we have enough results total
            # We continue collecting exact matches even after we have 20 partial, 
            # but stop once we have enough total results
            total_collected = len(exact_matches) + len(partial_matches)
            if len(exact_matches) >= max_results or (len(exact_matches) > 0 and total_collected >= max_results * 2):
                # If we have enough exact matches, or enough total results, stop
                break
        
        # Combine results: exact matches first, then partial matches
        results = exact_matches[:max_results]
        if len(results) < max_results:
            remaining = max_results - len(results)
            results.extend(partial_matches[:remaining])
        
        return results
    
    async def get_company_submissions(self, cik: str) -> Dict:
        """Get company filing submissions from SEC"""
        url = f"{self.BASE_URL}/submissions/CIK{cik.zfill(10)}.json"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise SECEdgarServiceError("SEC submissions request timed out.", cause=exc)
        except httpx.HTTPError as exc:
            raise SECEdgarServiceError("SEC submissions request failed.", cause=exc)
        except Exception as exc:
            raise SECEdgarServiceError("Unable to fetch SEC submissions.", cause=exc)
    
    async def get_filings(self, cik: str, filing_types: List[str] = ["10-K", "10-Q"], limit: Optional[int] = None) -> List[Dict]:
        """Get all filings for a company (optionally limited to most recent)"""
        submissions = await self.get_company_submissions(cik)
        
        filings = []
        recent_filings = submissions.get("filings", {}).get("recent", {})
        
        if not recent_filings:
            return filings
        
        forms = recent_filings.get("form", [])
        filing_dates = recent_filings.get("filingDate", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        report_dates = recent_filings.get("reportDate", [])
        
        # Collect all filings (not just latest of each type)
        all_filings = []
        
        for i, form in enumerate(forms):
            if form in filing_types:
                filing_date_str = filing_dates[i] if i < len(filing_dates) else None
                accession = accession_numbers[i] if i < len(accession_numbers) else None
                report_date_str = report_dates[i] if i < len(report_dates) else None
                
                if not filing_date_str or not accession:
                    continue
                
                all_filings.append({
                    "filing_type": form,
                    "filing_date": filing_date_str,
                    "report_date": report_date_str,
                    "accession_number": accession
                })
        
        # Sort by filing date (most recent first)
        all_filings.sort(key=lambda x: x["filing_date"], reverse=True)
        
        # Apply limit if specified (e.g., last 5 years of filings)
        if limit:
            all_filings = all_filings[:limit]
        
        # Build URLs for each filing
        cik_numeric = str(int(cik))  # Convert to int then back to string to remove leading zeros
        cik_padded = cik.zfill(10)  # Ensure CIK is 10 digits with leading zeros for viewer URL
        
        for filing in all_filings:
            accession = filing["accession_number"]
            accession_dash = accession.replace("-", "")
            
            # Document URL format: https://www.sec.gov/Archives/edgar/data/{cik_numeric}/{accession_dash}/{accession}.txt
            filing["document_url"] = f"https://www.sec.gov/Archives/edgar/data/{cik_numeric}/{accession_dash}/{accession}.txt"
            # SEC EDGAR Viewer URL - uses standard viewer that works reliably
            # Format: https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={accession}&xbrl_type=v
            # Note: This viewer allows users to switch to inline XBRL view if available
            # CIK must be 10 digits with leading zeros for the viewer
            filing["sec_url"] = f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik_padded}&accession_number={accession}&xbrl_type=v"
            filing["cik"] = cik
            filings.append(filing)
        
        return filings
    
    async def get_filing_document(
        self,
        document_url: str,
        timeout: Optional[float] = None,
        max_retries: int = 3
    ) -> str:
        """Fetch the actual filing document with retry logic.

        Implements exponential backoff retry (1s, 2s, 4s) for transient failures.
        This is critical for reliability since SEC EDGAR can have intermittent issues.
        """
        import asyncio

        request_timeout = timeout if timeout is not None else 30.0
        last_exception: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        document_url,
                        headers={"User-Agent": self.USER_AGENT},
                        timeout=request_timeout
                    )
                    response.raise_for_status()
                    return response.text

            except httpx.TimeoutException as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"SEC filing request timed out (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {document_url}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise SECEdgarServiceError("SEC filing request timed out after retries.", cause=exc)

            except httpx.HTTPStatusError as exc:
                # Retry on 5xx server errors, not on 4xx client errors
                if exc.response.status_code >= 500:
                    last_exception = exc
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"SEC server error {exc.response.status_code} (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s: {document_url}"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                raise SECEdgarServiceError(
                    f"SEC filing request failed with status {exc.response.status_code}.",
                    cause=exc
                )

            except httpx.HTTPError as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"SEC filing request failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {document_url}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                raise SECEdgarServiceError("SEC filing request failed after retries.", cause=exc)

            except Exception as exc:
                # Don't retry on unexpected exceptions
                raise SECEdgarServiceError("Unable to fetch SEC filing.", cause=exc)

        # Should not reach here, but handle edge case
        raise SECEdgarServiceError(
            "SEC filing request failed after all retries.",
            cause=last_exception
        )

sec_edgar_service = SECEdgarService()

