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

    # Get XBRL financial data
    xbrl = await client.get_xbrl_data("AAPL", accession_number="...")
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from edgar import Company as EdgarCompany, set_identity, find as edgar_find

from .async_executor import run_in_executor, run_in_executor_with_timeout
from .config import EDGAR_IDENTITY, FilingType, EDGAR_DEFAULT_TIMEOUT_SECONDS
from .exceptions import (
    CompanyNotFoundError,
    FilingNotFoundError,
    EdgarError,
    EdgarNetworkError,
    EdgarTimeoutError,
    EdgarRateLimitError,
    translate_edgartools_exception,
)
from .models import Company, Filing, XBRLData, FinancialMetric

logger = logging.getLogger(__name__)

# Initialize EdgarTools identity on module load
set_identity(EDGAR_IDENTITY)
logger.info(f"EdgarTools initialized with identity: {EDGAR_IDENTITY}")

# Lazy-init semaphore for search concurrency control
# Cannot create at module level - no event loop exists yet
_edgar_search_semaphore: Optional[asyncio.Semaphore] = None


def _get_search_semaphore() -> asyncio.Semaphore:
    """Get or create the search semaphore (lazy initialization)."""
    global _edgar_search_semaphore
    if _edgar_search_semaphore is None:
        _edgar_search_semaphore = asyncio.Semaphore(EDGAR_THREAD_POOL_SIZE)
    return _edgar_search_semaphore


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
            edgar_company = await run_in_executor_with_timeout(
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
            search_results = await run_in_executor_with_timeout(
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
                async with _get_search_semaphore():
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
        Get filings for a company by type.

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
        ticker = ticker.upper().strip()
        logger.debug(f"Getting {filing_type.value} filings for {ticker}")

        try:
            edgar_company = await run_in_executor_with_timeout(
                lambda: EdgarCompany(ticker),
                timeout=self.timeout,
            )

            # Build list of form types to fetch
            form_types = [filing_type.value]
            if include_amended and not filing_type.is_amended:
                amended_value = f"{filing_type.value}/A"
                form_types.append(amended_value)

            filings = []
            for form_type in form_types:
                form_filings = await run_in_executor_with_timeout(
                    lambda ft=form_type: list(edgar_company.get_filings(form=ft)),
                    timeout=self.timeout,
                )
                filings.extend(form_filings)

            # Sort by filing date descending, handling None dates gracefully
            from datetime import date as date_type_sort
            filings.sort(
                key=lambda f: f.filing_date if f.filing_date else date_type_sort.min,
                reverse=True
            )

            # Apply limit
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

    async def get_xbrl_data(
        self,
        ticker: str,
        accession_number: Optional[str] = None,
    ) -> Optional[XBRLData]:
        """
        Get XBRL financial data for a company.

        Args:
            ticker: Stock ticker symbol
            accession_number: Optional specific filing accession number.
                            If not provided, uses the latest 10-K or 10-Q.

        Returns:
            XBRLData object with financial metrics, or None if not available

        Raises:
            CompanyNotFoundError: If the ticker is not found
            EdgarError: For other errors
        """
        ticker = ticker.upper().strip()
        logger.debug(f"Getting XBRL data for {ticker}")

        try:
            edgar_company = await run_in_executor_with_timeout(
                lambda: EdgarCompany(ticker),
                timeout=self.timeout,
            )

            # Get financials via EdgarTools
            financials = await run_in_executor_with_timeout(
                lambda: edgar_company.financials,
                timeout=self.timeout,
            )

            if not financials:
                logger.warning(f"No financials available for {ticker}")
                return None

            return await self._extract_xbrl_data(financials, accession_number)

        except Exception as exc:
            if "not found" in str(exc).lower():
                raise CompanyNotFoundError(ticker, cause=exc)
            logger.error(f"Error getting XBRL data for {ticker}: {exc}")
            return None

    async def get_filing_html(
        self,
        ticker: str,
        accession_number: str,
    ) -> str:
        """
        Get the HTML content of a specific filing.

        Args:
            ticker: Stock ticker symbol
            accession_number: Filing accession number

        Returns:
            HTML content as string

        Raises:
            FilingNotFoundError: If the filing is not found
        """
        ticker = ticker.upper().strip()

        try:
            edgar_company = await run_in_executor_with_timeout(
                lambda: EdgarCompany(ticker),
                timeout=self.timeout,
            )

            # Find the specific filing
            filings = await run_in_executor_with_timeout(
                lambda: list(edgar_company.get_filings()),
                timeout=self.timeout,
            )

            target_accession = accession_number.replace("-", "")
            for filing in filings:
                if filing.accession_number.replace("-", "") == target_accession:
                    html = await run_in_executor_with_timeout(
                        lambda f=filing: f.html(),
                        timeout=self.timeout * 2,  # HTML can be large
                    )
                    return html

            raise FilingNotFoundError(ticker, "unknown", accession_number=accession_number)

        except FilingNotFoundError:
            raise
        except Exception as exc:
            raise translate_edgartools_exception(exc) from exc

    async def get_filing_markdown(
        self,
        ticker: str,
        accession_number: str,
    ) -> str:
        """
        Get the filing content as clean markdown.

        Args:
            ticker: Stock ticker symbol
            accession_number: Filing accession number

        Returns:
            Markdown content as string
        """
        ticker = ticker.upper().strip()

        try:
            edgar_company = await run_in_executor_with_timeout(
                lambda: EdgarCompany(ticker),
                timeout=self.timeout,
            )

            filings = await run_in_executor_with_timeout(
                lambda: list(edgar_company.get_filings()),
                timeout=self.timeout,
            )

            target_accession = accession_number.replace("-", "")
            for filing in filings:
                if filing.accession_number.replace("-", "") == target_accession:
                    markdown = await run_in_executor_with_timeout(
                        lambda f=filing: f.markdown(),
                        timeout=self.timeout * 2,
                    )
                    return markdown

            raise FilingNotFoundError(ticker, "unknown", accession_number=accession_number)

        except FilingNotFoundError:
            raise
        except Exception as exc:
            raise translate_edgartools_exception(exc) from exc

    # Private transformation methods

    def _transform_company(self, edgar_company: EdgarCompany, ticker: str) -> Company:
        """Transform EdgarTools Company to our Company model."""
        return Company(
            cik=edgar_company.cik,
            ticker=ticker,
            name=edgar_company.name,
            sic_code=str(edgar_company.sic) if hasattr(edgar_company, 'sic') and edgar_company.sic else None,
            sic_description=edgar_company.industry if hasattr(edgar_company, 'industry') else None,
            exchange=None,  # EdgarTools doesn't provide this directly
        )

    def _transform_filing(self, edgar_filing, ticker: str, cik: str) -> Filing:
        """Transform EdgarTools Filing to our Filing model."""
        from datetime import date as date_type

        # Parse filing date with error handling
        filing_date = edgar_filing.filing_date
        if isinstance(filing_date, str):
            try:
                filing_date = date_type.fromisoformat(filing_date)
            except (ValueError, TypeError):
                logger.warning(f"Invalid filing date format: {filing_date}")
                filing_date = None

        # Parse period end date with error handling
        period_end = None
        if hasattr(edgar_filing, 'period_of_report') and edgar_filing.period_of_report:
            period_end = edgar_filing.period_of_report
            if isinstance(period_end, str):
                try:
                    period_end = date_type.fromisoformat(period_end)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid period_of_report format: {period_end}")
                    period_end = None

        # Determine filing type enum - use non-strict mode to get UNKNOWN for unrecognized forms
        filing_type = FilingType.from_string(edgar_filing.form, strict=False)

        return Filing(
            accession_number=edgar_filing.accession_number,
            filing_type=filing_type,
            filing_date=filing_date,
            period_end_date=period_end,
            ticker=ticker,
            cik=cik,
            company_name=edgar_filing.company if hasattr(edgar_filing, 'company') else None,
            document_url=edgar_filing.primary_document if hasattr(edgar_filing, 'primary_document') else None,
        )

    async def _extract_xbrl_data(
        self,
        financials,
        accession_number: Optional[str] = None,
    ) -> Optional[XBRLData]:
        """Extract XBRL data from EdgarTools financials object."""
        from datetime import date as date_type

        xbrl_data = XBRLData()

        try:
            # Get income statement
            income_stmt = await run_in_executor(lambda: financials.income_statement)
            if income_stmt is not None:
                df = await run_in_executor(lambda: income_stmt.to_dataframe())
                if df is not None and not df.empty:
                    xbrl_data.revenue = self._extract_metric_series(df, ["Revenues", "Revenue", "TotalRevenue", "NetSales"], accession_number)
                    xbrl_data.net_income = self._extract_metric_series(df, ["NetIncomeLoss", "ProfitLoss", "NetIncome"], accession_number)
                    xbrl_data.earnings_per_share = self._extract_metric_series(df, ["EarningsPerShareBasic", "BasicEarningsPerShare", "EarningsPerShareDiluted"], accession_number)

            # Get balance sheet
            balance_sheet = await run_in_executor(lambda: financials.balance_sheet)
            if balance_sheet is not None:
                df = await run_in_executor(lambda: balance_sheet.to_dataframe())
                if df is not None and not df.empty:
                    xbrl_data.total_assets = self._extract_metric_series(df, ["Assets", "TotalAssets"], accession_number)
                    xbrl_data.total_liabilities = self._extract_metric_series(df, ["Liabilities", "TotalLiabilities"], accession_number)
                    xbrl_data.cash_and_equivalents = self._extract_metric_series(df, ["CashAndCashEquivalentsAtCarryingValue", "Cash", "CashAndCashEquivalents"], accession_number)

        except Exception as exc:
            logger.warning(f"Error extracting XBRL data: {exc}")

        return xbrl_data if not xbrl_data.is_empty() else None

    def _extract_metric_series(
        self,
        df,
        candidates: List[str],
        accession_number: Optional[str],
    ) -> List[FinancialMetric]:
        """Extract a metric series from a DataFrame."""
        from datetime import date as date_type

        metrics = []

        # Find the first matching row
        for candidate in candidates:
            if candidate in df.index:
                row = df.loc[candidate]
                for col in row.index:
                    value = row[col]
                    if value is not None and not (hasattr(value, '__iter__') and len(value) == 0):
                        try:
                            # Parse the column as a date with error handling
                            period_end = None
                            if isinstance(col, date_type):
                                period_end = col
                            elif isinstance(col, str):
                                try:
                                    period_end = date_type.fromisoformat(col)
                                except (ValueError, TypeError):
                                    logger.debug(f"Skipping metric with unparseable date: {col}")
                                    continue
                            else:
                                # Try to convert to date if it has date-like attributes
                                if hasattr(col, 'date'):
                                    period_end = col.date()
                                else:
                                    continue

                            if period_end is None:
                                continue

                            metrics.append(FinancialMetric(
                                name=candidate,
                                value=float(value),
                                period_end=period_end,
                                accession_number=accession_number,
                            ))
                        except (ValueError, TypeError) as e:
                            logger.debug(f"Error extracting metric value: {e}")
                            continue
                break  # Use first matching candidate

        # Sort by period descending
        metrics.sort(key=lambda m: m.period_end, reverse=True)
        return metrics[:5]  # Return most recent 5 periods


# Singleton instance for convenience
edgar_client = EdgarClient()
