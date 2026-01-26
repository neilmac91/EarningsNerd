"""
EdgarTools XBRL Service

Provides XBRL financial data extraction using EdgarTools.
This service maintains API compatibility with the legacy xbrl_service.py
to enable gradual migration.

Usage:
    from app.services.edgar.xbrl_service import edgar_xbrl_service

    # Get XBRL data (compatible with legacy interface)
    data = await edgar_xbrl_service.get_xbrl_data(accession_number, cik)

    # Extract standardized metrics
    metrics = edgar_xbrl_service.extract_standardized_metrics(data)
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from edgar import Company as EdgarCompany, set_identity

from .async_executor import run_in_executor, run_in_executor_with_timeout
from .config import EDGAR_IDENTITY, EDGAR_DEFAULT_TIMEOUT_SECONDS
from .models import FinancialMetric, MetricChange, MetricSeries, XBRLData

logger = logging.getLogger(__name__)

# Ensure identity is set
set_identity(EDGAR_IDENTITY)

# Module-level cache for XBRL data
# Key: "{cik}:{accession_number}"
# Value: (cached_datetime, data_dict)
_xbrl_cache: Dict[str, Tuple[datetime, Optional[Dict]]] = {}
_cache_ttl = timedelta(hours=24)


def clear_xbrl_cache() -> int:
    """Clear the XBRL cache. Returns number of entries cleared."""
    global _xbrl_cache
    count = len(_xbrl_cache)
    _xbrl_cache.clear()
    logger.info(f"Cleared {count} XBRL cache entries")
    return count


def get_xbrl_cache_stats() -> Dict[str, int]:
    """Get cache statistics for monitoring."""
    now = datetime.now()
    valid_count = sum(
        1 for cached_time, _ in _xbrl_cache.values()
        if now - cached_time < _cache_ttl
    )
    return {
        "total_entries": len(_xbrl_cache),
        "valid_entries": valid_count,
        "expired_entries": len(_xbrl_cache) - valid_count,
    }


class EdgarXBRLService:
    """
    XBRL data extraction service using EdgarTools.

    This service provides the same interface as the legacy XBRLService
    but uses EdgarTools for data extraction, eliminating the need for
    100+ hardcoded XBRL field names.
    """

    def __init__(self, timeout: float = EDGAR_DEFAULT_TIMEOUT_SECONDS):
        self.timeout = timeout

    async def get_xbrl_data(
        self,
        accession_number: str,
        cik: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract XBRL data from SEC filing.

        This method maintains backward compatibility with the legacy
        xbrl_service.get_xbrl_data() interface.

        Args:
            accession_number: Filing accession number
            cik: Company CIK (Central Index Key)

        Returns:
            Dictionary with XBRL data in legacy format:
            {
                "revenue": [{"period": "2024-03-31", "value": 123, "form": "10-K", "accn": "..."}],
                "net_income": [...],
                "total_assets": [...],
                "total_liabilities": [...],
                "cash_and_equivalents": [...],
                "earnings_per_share": [...],
            }
        """
        global _xbrl_cache

        # Build cache key
        cache_key = f"{cik}:{accession_number}"

        # Check cache first
        if cache_key in _xbrl_cache:
            cached_time, cached_data = _xbrl_cache[cache_key]
            if datetime.now() - cached_time < _cache_ttl:
                logger.debug(f"XBRL cache hit for {cache_key}")
                return cached_data
            else:
                logger.debug(f"XBRL cache expired for {cache_key}")
                del _xbrl_cache[cache_key]

        # Fetch from EdgarTools
        result = await self._fetch_xbrl_data(cik, accession_number)

        # Cache successful results only
        if result is not None:
            _xbrl_cache[cache_key] = (datetime.now(), result)
            logger.debug(f"XBRL cached for {cache_key}")
        else:
            logger.debug(f"XBRL NOT cached for {cache_key} (no data)")

        return result

    async def _fetch_xbrl_data(
        self,
        cik: str,
        accession_number: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch XBRL data using EdgarTools."""
        try:
            # Pad CIK to 10 digits
            cik_padded = cik.zfill(10)

            # Get company via EdgarTools
            edgar_company = await run_in_executor_with_timeout(
                lambda: EdgarCompany(cik=cik_padded),
                timeout=self.timeout,
            )

            # Get financials
            financials = await run_in_executor_with_timeout(
                lambda: edgar_company.financials,
                timeout=self.timeout,
            )

            if not financials:
                logger.warning(f"No financials available for CIK {cik}")
                return await self._fallback_to_company_facts(cik_padded, accession_number)

            # Extract data from financials
            result = {
                "revenue": [],
                "net_income": [],
                "total_assets": [],
                "total_liabilities": [],
                "cash_and_equivalents": [],
                "earnings_per_share": [],
            }

            # Try to get income statement
            try:
                income_stmt = await run_in_executor(lambda: financials.income_statement)
                if income_stmt is not None:
                    df = await run_in_executor(lambda: income_stmt.to_dataframe())
                    if df is not None and not df.empty:
                        result["revenue"] = self._extract_from_dataframe(
                            df,
                            ["Revenues", "Revenue", "TotalRevenue", "TotalRevenues",
                             "NetSales", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"],
                            accession_number
                        )
                        result["net_income"] = self._extract_from_dataframe(
                            df,
                            ["NetIncomeLoss", "ProfitLoss", "NetIncome",
                             "NetIncomeLossAvailableToCommonStockholdersBasic"],
                            accession_number
                        )
                        result["earnings_per_share"] = self._extract_from_dataframe(
                            df,
                            ["EarningsPerShareBasic", "EarningsPerShareDiluted",
                             "BasicEarningsPerShare", "EarningsPerShareBasicAndDiluted"],
                            accession_number
                        )
            except Exception as e:
                logger.warning(f"Error extracting income statement: {e}")

            # Try to get balance sheet
            try:
                balance_sheet = await run_in_executor(lambda: financials.balance_sheet)
                if balance_sheet is not None:
                    df = await run_in_executor(lambda: balance_sheet.to_dataframe())
                    if df is not None and not df.empty:
                        result["total_assets"] = self._extract_from_dataframe(
                            df,
                            ["Assets", "TotalAssets"],
                            accession_number
                        )
                        result["total_liabilities"] = self._extract_from_dataframe(
                            df,
                            ["Liabilities", "TotalLiabilities", "LiabilitiesAndStockholdersEquity"],
                            accession_number
                        )
                        result["cash_and_equivalents"] = self._extract_from_dataframe(
                            df,
                            ["CashAndCashEquivalentsAtCarryingValue", "Cash",
                             "CashAndCashEquivalents", "CashCashEquivalentsAndShortTermInvestments"],
                            accession_number
                        )
            except Exception as e:
                logger.warning(f"Error extracting balance sheet: {e}")

            # If we got any data, return it
            if any(result.values()):
                return result

            # Fallback to company facts API
            return await self._fallback_to_company_facts(cik_padded, accession_number)

        except Exception as e:
            logger.error(f"Error fetching XBRL data: {e}", exc_info=True)
            return await self._fallback_to_company_facts(cik.zfill(10), accession_number)

    def _extract_from_dataframe(
        self,
        df,
        candidates: List[str],
        accession_number: str,
    ) -> List[Dict[str, Any]]:
        """Extract metric values from a DataFrame."""
        result = []

        for candidate in candidates:
            if candidate in df.index:
                row = df.loc[candidate]
                for col in row.index:
                    try:
                        value = row[col]
                        if value is None:
                            continue
                        # Handle pandas NA
                        if hasattr(value, 'item'):
                            value = value.item()
                        if value is None or (isinstance(value, float) and value != value):  # NaN check
                            continue

                        # Parse column as date
                        period = str(col)
                        if isinstance(col, date):
                            period = col.isoformat()

                        result.append({
                            "period": period,
                            "value": float(value),
                            "form": None,
                            "accn": accession_number,
                        })
                    except (ValueError, TypeError):
                        continue
                break  # Use first matching candidate

        # Sort by period descending and limit to 5
        result.sort(key=lambda x: x["period"], reverse=True)
        return result[:5]

    async def _fallback_to_company_facts(
        self,
        cik: str,
        accession_number: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback to SEC company facts API if EdgarTools financials not available.

        This replicates the logic from the legacy xbrl_service.py for cases
        where EdgarTools doesn't have the data.
        """
        import httpx

        logger.info(f"Falling back to SEC company facts API for CIK {cik}")

        try:
            facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    facts_url,
                    headers={"User-Agent": EDGAR_IDENTITY},
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.warning(f"Company facts API returned {response.status_code}")
                    return None

                data = response.json()
                return self._parse_company_facts(data, accession_number)

        except Exception as e:
            logger.error(f"Error in company facts fallback: {e}")
            return None

    def _parse_company_facts(
        self,
        facts_data: Dict,
        target_accession: str,
    ) -> Dict[str, List[Dict]]:
        """Parse SEC company facts API response."""
        result = {
            "revenue": [],
            "net_income": [],
            "total_assets": [],
            "total_liabilities": [],
            "cash_and_equivalents": [],
            "earnings_per_share": [],
        }

        normalized_accession = target_accession.replace("-", "") if target_accession else None

        def filter_and_sort(data_list: list, max_items: int = 5) -> list:
            if not isinstance(data_list, list):
                return []

            valid_items = [
                item for item in data_list
                if isinstance(item, dict) and item.get("end")
            ]

            sorted_items = sorted(
                valid_items,
                key=lambda x: x.get("end", ""),
                reverse=True
            )

            if normalized_accession:
                matching = [
                    item for item in sorted_items
                    if item.get("accn", "").replace("-", "") == normalized_accession
                ]
                if matching:
                    return matching[:max_items]

            return sorted_items[:max_items]

        try:
            facts = facts_data.get("facts", {})
            us_gaap = facts.get("us-gaap", {})

            if not isinstance(us_gaap, dict):
                return result

            # Revenue
            revenue_fields = ["Revenues", "Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax",
                           "SalesRevenueNet", "NetSales", "TotalRevenue"]
            for field in revenue_fields:
                if field in us_gaap:
                    fact = us_gaap[field]
                    if isinstance(fact, dict) and "units" in fact:
                        data = fact["units"].get("USD", [])
                        if data:
                            for item in filter_and_sort(data):
                                result["revenue"].append({
                                    "period": item.get("end"),
                                    "value": item.get("val"),
                                    "form": item.get("form"),
                                    "accn": item.get("accn"),
                                })
                            break

            # Net Income
            net_income_fields = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
            for field in net_income_fields:
                if field in us_gaap:
                    fact = us_gaap[field]
                    if isinstance(fact, dict) and "units" in fact:
                        data = fact["units"].get("USD", [])
                        if data:
                            for item in filter_and_sort(data):
                                result["net_income"].append({
                                    "period": item.get("end"),
                                    "value": item.get("val"),
                                    "form": item.get("form"),
                                    "accn": item.get("accn"),
                                })
                            break

            # Assets
            if "Assets" in us_gaap:
                fact = us_gaap["Assets"]
                if isinstance(fact, dict) and "units" in fact:
                    data = fact["units"].get("USD", [])
                    for item in filter_and_sort(data):
                        result["total_assets"].append({
                            "period": item.get("end"),
                            "value": item.get("val"),
                            "form": item.get("form"),
                            "accn": item.get("accn"),
                        })

            # EPS
            eps_fields = ["EarningsPerShareBasic", "EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"]
            for field in eps_fields:
                if field in us_gaap:
                    fact = us_gaap[field]
                    if isinstance(fact, dict) and "units" in fact:
                        for unit_key in ["USD/shares", "USD", "pure"]:
                            if unit_key in fact["units"]:
                                data = fact["units"][unit_key]
                                if data:
                                    for item in filter_and_sort(data):
                                        result["earnings_per_share"].append({
                                            "period": item.get("end"),
                                            "value": item.get("val"),
                                            "form": item.get("form"),
                                            "accn": item.get("accn"),
                                        })
                                    break
                        if result["earnings_per_share"]:
                            break

        except Exception as e:
            logger.warning(f"Error parsing company facts: {e}")

        return result

    def extract_standardized_metrics(self, xbrl_data: Dict) -> Dict[str, Any]:
        """
        Extract standardized financial metrics from XBRL data.

        This method maintains backward compatibility with the legacy interface.

        Args:
            xbrl_data: Raw XBRL data dictionary

        Returns:
            Dictionary with standardized metrics including current, prior,
            change calculations, and series data.
        """
        def normalise_series(entries: List[Dict]) -> List[Dict]:
            cleaned = []
            seen_periods = set()
            sorted_entries = sorted(
                (e for e in entries if e.get("period") and e.get("value") is not None),
                key=lambda x: x.get("period"),
                reverse=True,
            )
            for entry in sorted_entries:
                period = entry.get("period")
                if period in seen_periods:
                    continue
                seen_periods.add(period)
                cleaned.append({
                    "period": period,
                    "value": entry.get("value"),
                    "form": entry.get("form"),
                })
            return cleaned

        def build_metric_entry(series: List[Dict]) -> Dict:
            entry = {}
            if series:
                entry["current"] = series[0]
            if len(series) > 1:
                entry["prior"] = series[1]
                current_val = series[0].get("value")
                prior_val = series[1].get("value")
                entry["change"] = MetricChange.compute(current_val, prior_val).to_dict()
            if series:
                entry["series"] = series
            return entry

        metrics = {}

        revenue_series = normalise_series(xbrl_data.get("revenue", []))
        net_income_series = normalise_series(xbrl_data.get("net_income", []))
        eps_series = normalise_series(xbrl_data.get("earnings_per_share", []))

        if revenue_series:
            metrics["revenue"] = build_metric_entry(revenue_series)

        if net_income_series:
            metrics["net_income"] = build_metric_entry(net_income_series)

        if eps_series:
            metrics["earnings_per_share"] = build_metric_entry(eps_series)

        # Calculate net margin
        if revenue_series and net_income_series:
            income_by_period = {e["period"]: e for e in net_income_series}
            margin_series = []
            for rev_entry in revenue_series:
                period = rev_entry["period"]
                inc_entry = income_by_period.get(period)
                rev_value = rev_entry.get("value")
                inc_value = inc_entry.get("value") if inc_entry else None
                if rev_value and inc_value and rev_value != 0:
                    margin_series.append({
                        "period": period,
                        "value": (inc_value / rev_value) * 100,
                        "form": rev_entry.get("form"),
                    })
            if margin_series:
                metrics["net_margin"] = build_metric_entry(margin_series)

        return metrics


# Singleton instance for backward compatibility
edgar_xbrl_service = EdgarXBRLService()
