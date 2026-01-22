"""
SEC Client Facade

High-level client for SEC filing operations that combines:
- SECEdgarService for data fetching
- SECRateLimiter for rate limiting
- FilingParser for semantic parsing
- MarkdownSerializer for clean output

This is the primary interface for the 10-Q and 10-K markdown endpoints.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from app.services.sec_edgar import sec_edgar_service, SECEdgarServiceError
from app.services.sec_rate_limiter import sec_rate_limiter, SECRateLimitError
from app.services.filing_parser import filing_parser, ParsedFiling
from app.services.markdown_serializer import markdown_serializer

logger = logging.getLogger(__name__)


class CompanyNotFoundError(Exception):
    """Raised when a company cannot be found by ticker"""
    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(f"Company not found for ticker: {ticker}")


class FilingNotFoundError(Exception):
    """Raised when a filing cannot be found"""
    def __init__(self, ticker: str, filing_type: str):
        self.ticker = ticker
        self.filing_type = filing_type
        super().__init__(f"No {filing_type} filing found for ticker: {ticker}")


class FilingParseError(Exception):
    """Raised when a filing cannot be parsed"""
    def __init__(self, accession_number: str, reason: str):
        self.accession_number = accession_number
        self.reason = reason
        super().__init__(f"Failed to parse filing {accession_number}: {reason}")


@dataclass
class FilingMarkdownResult:
    """Result of parsing a filing to markdown"""
    filing_date: str
    accession_number: str
    markdown_content: str
    metadata: Dict[str, Any]
    sections_extracted: List[str]


class SECClient:
    """
    High-level SEC filing client.

    Provides a clean interface for:
    - Looking up companies by ticker
    - Fetching 10-Q filings
    - Converting filings to clean markdown
    """

    def __init__(self):
        self._edgar = sec_edgar_service
        self._rate_limiter = sec_rate_limiter
        self._parser = filing_parser
        self._serializer = markdown_serializer

    async def get_cik(self, ticker: str) -> str:
        """
        Map a stock ticker to SEC CIK number.

        Args:
            ticker: Stock ticker (e.g., "AAPL")

        Returns:
            10-digit CIK string (e.g., "0000320193")

        Raises:
            CompanyNotFoundError: If ticker not found
        """
        ticker_upper = ticker.upper().strip()

        try:
            results = await self._edgar.search_company(ticker_upper)
        except SECEdgarServiceError as e:
            logger.error(f"SEC service error looking up {ticker}: {e}")
            raise

        # Look for exact ticker match
        for result in results:
            if result.get("ticker", "").upper() == ticker_upper:
                return result["cik"]

        # If no exact match, raise error
        if not results:
            raise CompanyNotFoundError(ticker)

        # Return first result if no exact match (partial match)
        return results[0]["cik"]

    async def get_company_info(self, ticker: str) -> Dict[str, Any]:
        """
        Get company information by ticker.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with ticker, name, cik
        """
        ticker_upper = ticker.upper().strip()
        results = await self._edgar.search_company(ticker_upper)

        for result in results:
            if result.get("ticker", "").upper() == ticker_upper:
                return result

        if results:
            return results[0]

        raise CompanyNotFoundError(ticker)

    async def _get_latest_filing(
        self, ticker: str, filing_type: str
    ) -> Dict[str, Any]:
        """
        Get the latest filing of a specific type for a company.

        Args:
            ticker: Stock ticker
            filing_type: Filing type (e.g., "10-Q", "10-K")

        Returns:
            Dict with filing metadata (filing_date, accession_number, etc.)

        Raises:
            CompanyNotFoundError: If ticker not found
            FilingNotFoundError: If no filings of this type exist
        """
        cik = await self.get_cik(ticker)
        filing_types = [filing_type, f"{filing_type}/A"]

        filings = await self._rate_limiter.execute_with_backoff(
            lambda: self._edgar.get_filings(cik, filing_types, limit=1)
        )

        if not filings:
            raise FilingNotFoundError(ticker, filing_type)

        return filings[0]

    async def _get_filings(
        self,
        ticker: str,
        filing_type: str,
        limit: int = 10,
        include_amended: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get list of filings of a specific type for a company.

        Args:
            ticker: Stock ticker
            filing_type: Filing type (e.g., "10-Q", "10-K")
            limit: Maximum number of filings to return
            include_amended: Whether to include amended filings

        Returns:
            List of filing metadata dicts
        """
        cik = await self.get_cik(ticker)

        filing_types = [filing_type]
        if include_amended:
            filing_types.append(f"{filing_type}/A")

        filings = await self._rate_limiter.execute_with_backoff(
            lambda: self._edgar.get_filings(cik, filing_types, limit=limit)
        )

        return filings

    async def get_latest_10q(self, ticker: str) -> Dict[str, Any]:
        """
        Get the latest 10-Q filing metadata for a company.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with filing metadata (filing_date, accession_number, etc.)

        Raises:
            CompanyNotFoundError: If ticker not found
            FilingNotFoundError: If no 10-Q filings exist
        """
        return await self._get_latest_filing(ticker, "10-Q")

    async def get_10q_filings(
        self,
        ticker: str,
        limit: int = 10,
        include_amended: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get list of 10-Q filings for a company.

        Args:
            ticker: Stock ticker
            limit: Maximum number of filings to return
            include_amended: Whether to include 10-Q/A (amended) filings

        Returns:
            List of filing metadata dicts
        """
        return await self._get_filings(ticker, "10-Q", limit, include_amended)

    async def get_latest_10k(self, ticker: str) -> Dict[str, Any]:
        """
        Get the latest 10-K filing metadata for a company.

        Args:
            ticker: Stock ticker

        Returns:
            Dict with filing metadata (filing_date, accession_number, etc.)

        Raises:
            CompanyNotFoundError: If ticker not found
            FilingNotFoundError: If no 10-K filings exist
        """
        return await self._get_latest_filing(ticker, "10-K")

    async def get_10k_filings(
        self,
        ticker: str,
        limit: int = 10,
        include_amended: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get list of 10-K filings for a company.

        Args:
            ticker: Stock ticker
            limit: Maximum number of filings to return
            include_amended: Whether to include 10-K/A (amended) filings

        Returns:
            List of filing metadata dicts
        """
        return await self._get_filings(ticker, "10-K", limit, include_amended)

    async def fetch_filing_html(self, document_url: str) -> str:
        """
        Fetch raw HTML content of a filing.

        Args:
            document_url: URL to the filing document

        Returns:
            Raw HTML string
        """
        return await self._rate_limiter.execute_with_backoff(
            lambda: self._edgar.get_filing_document(document_url, timeout=60.0)
        )

    async def parse_filing_to_markdown(
        self,
        ticker: str,
        filing: Optional[Dict[str, Any]] = None,
        filing_type: str = "10-Q",
    ) -> FilingMarkdownResult:
        """
        Fetch and parse a filing to clean markdown.

        Args:
            ticker: Stock ticker (used for company info)
            filing: Optional filing metadata dict. If not provided,
                   fetches the latest filing of the specified type.
            filing_type: Type of filing to fetch if not provided ("10-Q" or "10-K")

        Returns:
            FilingMarkdownResult with markdown content and metadata

        Raises:
            FilingNotFoundError: If no filing found
            FilingParseError: If parsing fails
        """
        # Get company info
        company_info = await self.get_company_info(ticker)

        # Get filing if not provided
        if filing is None:
            if filing_type == "10-K":
                filing = await self.get_latest_10k(ticker)
            else:
                filing = await self.get_latest_10q(ticker)

        # Fetch HTML content
        document_url = filing.get("document_url")
        if not document_url:
            raise FilingParseError(
                filing.get("accession_number", "unknown"),
                "No document URL in filing metadata"
            )

        try:
            html_content = await self.fetch_filing_html(document_url)
        except (SECEdgarServiceError, SECRateLimitError) as e:
            raise FilingParseError(
                filing.get("accession_number", "unknown"),
                f"Failed to fetch document: {e}"
            )

        # Parse HTML to semantic structure
        try:
            parsed = self._parser.parse(html_content, filing.get("filing_type", "10-Q"))
        except Exception as e:
            logger.error(f"Failed to parse filing: {e}")
            raise FilingParseError(
                filing.get("accession_number", "unknown"),
                f"Parse error: {e}"
            )

        # Build metadata for serializer
        metadata = {
            "ticker": company_info.get("ticker", ticker.upper()),
            "company_name": company_info.get("name", ""),
            "filing_type": filing.get("filing_type", "10-Q"),
            "filing_date": filing.get("filing_date", ""),
            "period_end_date": filing.get("report_date", ""),
            "accession_number": filing.get("accession_number", ""),
            "sec_url": filing.get("sec_url", ""),
            "fiscal_period": self._determine_fiscal_period(filing),
            "parsing_method": parsed.parsing_method,
        }

        # Serialize to markdown
        markdown_content = self._serializer.serialize(parsed, metadata)

        # Determine which sections were extracted
        sections_extracted = [
            section_type
            for section_type, section in parsed.sections.items()
            if section and section.content
        ]

        return FilingMarkdownResult(
            filing_date=filing.get("filing_date", ""),
            accession_number=filing.get("accession_number", ""),
            markdown_content=markdown_content,
            metadata=metadata,
            sections_extracted=sections_extracted,
        )

    def _determine_fiscal_period(self, filing: Dict[str, Any]) -> str:
        """Determine fiscal period from filing metadata"""
        report_date = filing.get("report_date", "")
        filing_type = filing.get("filing_type", "")
        if not report_date:
            return ""

        try:
            # Parse YYYY-MM-DD format
            parts = report_date.split("-")
            if len(parts) != 3:
                return ""

            year = parts[0]
            month = int(parts[1])

            # For 10-K filings, return fiscal year
            if filing_type.startswith("10-K"):
                return f"FY {year}"

            # Determine quarter based on month for 10-Q
            if month <= 3:
                quarter = "Q1"
            elif month <= 6:
                quarter = "Q2"
            elif month <= 9:
                quarter = "Q3"
            else:
                quarter = "Q4"

            return f"{quarter} {year}"
        except (ValueError, IndexError):
            return ""


# Singleton instance
sec_client = SECClient()
