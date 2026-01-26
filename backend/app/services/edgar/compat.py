"""
Backward Compatibility Layer

This module provides compatibility wrappers that allow existing code
to use the new EdgarTools services through the same interface as the
legacy services.

Usage:
    # Replace legacy imports:
    # from app.services.xbrl_service import xbrl_service
    # With:
    from app.services.edgar.compat import xbrl_service

    # Or for sec_edgar_service:
    from app.services.edgar.compat import sec_edgar_service
"""

import logging
from typing import Any, Dict, List, Optional

from .client import edgar_client
from .xbrl_service import edgar_xbrl_service, clear_xbrl_cache, get_xbrl_cache_stats
from .exceptions import CompanyNotFoundError, FilingNotFoundError, EdgarError
from .config import FilingType

logger = logging.getLogger(__name__)


class SECEdgarServiceCompat:
    """
    Compatibility wrapper for legacy SECEdgarService interface.

    This allows existing code that imports sec_edgar_service to continue
    working while using the new EdgarTools backend.
    """

    async def search_company(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for companies by ticker or name.

        Returns legacy format:
        [{"ticker": "AAPL", "name": "Apple Inc.", "cik": "0000320193", "exchange": None}]

        Raises:
            EdgarError: If there's a network or API error
        """
        try:
            companies = await edgar_client.search_company(query)
            return [c.to_dict() for c in companies]
        except EdgarError:
            # Propagate EdgarError (includes network errors) to caller
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
                try:
                    ft = FilingType.from_string(form_type)
                    filings = await edgar_client.get_filings(
                        cik, ft, limit=limit, include_amended=False
                    )
                    all_filings.extend(filings)
                except ValueError:
                    logger.warning(f"Unknown filing type: {form_type}")
                    continue

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
        import httpx
        from .config import EDGAR_IDENTITY

        timeout = timeout or 60.0

        async with httpx.AsyncClient() as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(
                        document_url,
                        headers={"User-Agent": EDGAR_IDENTITY},
                        timeout=timeout,
                        follow_redirects=True,
                    )
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise EdgarError(f"Failed to fetch document: {e}", cause=e)
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

    async def get_company_tickers(
        self,
        force_refresh: bool = False,
    ) -> Dict[str, Dict]:
        """
        Get all company tickers from SEC.

        Returns a dictionary mapping index to company info:
        {
            "0": {"cik_str": "320193", "ticker": "AAPL", "title": "Apple Inc."},
            ...
        }
        """
        import httpx
        from .config import EDGAR_IDENTITY

        # SEC provides a bulk company tickers endpoint
        tickers_url = "https://www.sec.gov/files/company_tickers.json"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    tickers_url,
                    headers={"User-Agent": EDGAR_IDENTITY},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch company tickers from SEC: {e}")
            return {}


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
