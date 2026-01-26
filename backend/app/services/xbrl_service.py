from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import httpx
import random
import re
import logging
from bs4 import BeautifulSoup
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level cache for XBRL data
# Key: "{cik}:{accession_number}"
# Value: (cached_datetime, data_dict)
_xbrl_cache: Dict[str, Tuple[datetime, Optional[Dict]]] = {}


def _get_cache_ttl() -> timedelta:
    """Get cache TTL from settings, with fallback."""
    ttl_hours = getattr(settings, 'XBRL_CACHE_TTL_HOURS', 24)
    return timedelta(hours=ttl_hours)


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
    ttl = _get_cache_ttl()
    valid_count = sum(1 for cached_time, _ in _xbrl_cache.values()
                      if now - cached_time < ttl)
    return {
        "total_entries": len(_xbrl_cache),
        "valid_entries": valid_count,
        "expired_entries": len(_xbrl_cache) - valid_count,
    }


def _cleanup_expired_cache() -> None:
    """Remove expired entries from cache."""
    global _xbrl_cache
    now = datetime.now()
    ttl = _get_cache_ttl()
    expired_keys = [
        key for key, (cached_time, _) in _xbrl_cache.items()
        if now - cached_time >= ttl
    ]
    for key in expired_keys:
        del _xbrl_cache[key]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired XBRL cache entries")

# Comprehensive list of revenue field names used by major companies
# Defined at module level for performance (avoid recreating on each call)
REVENUE_FIELD_NAMES = [
    # Standard revenue fields (most common)
    "Revenues",
    "Revenue",  # Singular form used by some companies
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomer",
    # Net revenue variations
    "NetRevenues",
    "NetSales",  # Common for retail/consumer goods (Walmart, Target)
    "TotalRevenue",
    "TotalRevenues",
    "TotalNetRevenues",
    "TotalNetSales",
    # Product/Service breakdowns (sometimes used as primary)
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenueFromSalesOfGoods",
    "RevenueFromServices",
    "SalesRevenueProductsAndServices",
    # Pharmaceutical/Biotech specific (BioMarin, Gilead, Amgen, etc.)
    "ProductRevenue",
    "ProductSales",
    "ProductSalesNet",
    "NetProductRevenue",
    "NetProductSales",
    "ProductRevenueNet",
    "RevenuesFromExternalCustomers",
    "CollaborationRevenue",
    "LicenseRevenue",
    "RoyaltyRevenue",
    "ContractWithCustomerLiabilityRevenueRecognized",
    # Other variations used by specific industries
    "OperatingRevenue",
    "RegulatedAndUnregulatedOperatingRevenue",
    # Financial services
    "InterestAndDividendIncomeOperating",
    "RevenuesNetOfInterestExpense",
    # Technology/Software
    "SubscriptionRevenue",
    "ServiceRevenue",
]

# Comprehensive list of EPS field names used by major companies
# Different companies use different GAAP tags for earnings per share
EPS_FIELD_NAMES = [
    # Basic EPS (most common)
    "EarningsPerShareBasic",
    "BasicEarningsLossPerShare",
    "NetIncomeLossPerBasicShare",
    "EarningsPerShareBasicIncludingDiscontinuedOperations",
    # Diluted EPS
    "EarningsPerShareDiluted",
    "DilutedEarningsLossPerShare",
    "NetIncomeLossPerDilutedShare",
    "EarningsPerShareDilutedIncludingDiscontinuedOperations",
    # Combined (when basic and diluted are the same)
    "EarningsPerShareBasicAndDiluted",
    "BasicAndDilutedEarningsLossPerShare",
    # Continuing operations specific
    "IncomeLossFromContinuingOperationsPerBasicShare",
    "IncomeLossFromContinuingOperationsPerDilutedShare",
    # Attributable to common stockholders
    "EarningsPerShareBasicAttributableToCommonStockholders",
    "EarningsPerShareDilutedAttributableToCommonStockholders",
    # Attributable to parent
    "NetIncomeLossAttributableToParentPerBasicShare",
    "NetIncomeLossAttributableToParentPerDilutedShare",
    # Discontinued operations
    "IncomeLossFromDiscontinuedOperationsNetOfTaxPerBasicShare",
    "IncomeLossFromDiscontinuedOperationsNetOfTaxPerDilutedShare",
]

# Comprehensive list of Net Income field names used by major companies
# Different companies use different GAAP tags for net income/profit
NET_INCOME_FIELD_NAMES = [
    # Primary net income fields (most common)
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
    "NetIncomeLossAvailableToCommonStockholdersDiluted",
    # Attributable variations
    "NetIncomeLossAttributableToParent",
    "NetIncomeLossAttributableToReportingEntity",
    # Continuing operations (for companies with discontinued ops)
    "IncomeLossFromContinuingOperations",
    "IncomeLossFromContinuingOperationsIncludingPortionAttributableToNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsAfterTax",
    "IncomeLossFromContinuingOperationsAttributableToParent",
    # Comprehensive income (used by some companies as primary)
    "ComprehensiveIncomeNetOfTax",
    "ComprehensiveIncomeNetOfTaxIncludingPortionAttributableToNoncontrollingInterest",
    "ComprehensiveIncomeNetOfTaxAttributableToParent",
    # Operating income (fallback for some industries)
    "OperatingIncomeLoss",
    "IncomeLossFromOperations",
    # Before taxes (useful for analysis)
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    # Pharmaceutical/Biotech specific
    "IncomeLossBeforeGainOrLossOnSaleOfPropertiesIncomeFromEquityMethodInvestmentsAndIncomeTaxes",
    "IncomeLossFromEquityMethodInvestments",
    # Net income including noncontrolling interest
    "NetIncomeLossIncludingPortionAttributableToNoncontrollingInterest",
]


def compute_period_change(
    current_value: Optional[float],
    prior_value: Optional[float]
) -> Dict[str, Optional[Union[float, str]]]:
    """Compute OBJECTIVE period-over-period change between two values.

    This function provides purely mathematical change calculations with
    no interpretation or subjective language. The output is factual data only.

    Args:
        current_value: The current period's value
        prior_value: The prior period's value for comparison

    Returns:
        Dictionary containing:
        - absolute: The raw numerical difference (current - prior)
        - percentage: The percentage change ((current - prior) / |prior|) * 100
        - direction: "increase", "decrease", or "unchanged" (factual only)

        Returns None values if calculation not possible (missing data or division by zero)
    """
    result: Dict[str, Optional[Union[float, str]]] = {
        "absolute": None,
        "percentage": None,
        "direction": None,
    }

    # Cannot compute change without both values
    if current_value is None or prior_value is None:
        return result

    # Handle division by zero for percentage calculation
    if prior_value == 0:
        result["absolute"] = round(current_value, 2)
        result["direction"] = "increase" if current_value > 0 else ("decrease" if current_value < 0 else "unchanged")
        return result

    # Compute changes
    absolute_change = current_value - prior_value
    percentage_change = (absolute_change / abs(prior_value)) * 100

    result["absolute"] = round(absolute_change, 2)
    result["percentage"] = round(percentage_change, 2)

    # Factual direction indicator (no subjective language)
    if absolute_change > 0:
        result["direction"] = "increase"
    elif absolute_change < 0:
        result["direction"] = "decrease"
    else:
        result["direction"] = "unchanged"

    return result


class XBRLService:
    def __init__(self):
        self.base_url = settings.SEC_EDGAR_BASE_URL
        self.user_agent = settings.SEC_USER_AGENT

    async def get_xbrl_data(self, accession_number: str, cik: str) -> Optional[Dict]:
        """Extract XBRL data from SEC filing with caching.

        XBRL data changes only quarterly, so we cache results for 24 hours
        to reduce redundant SEC API calls on retries and repeated requests.
        """
        global _xbrl_cache

        # Build cache key
        cache_key = f"{cik}:{accession_number}"
        ttl = _get_cache_ttl()

        # Check cache first
        if cache_key in _xbrl_cache:
            cached_time, cached_data = _xbrl_cache[cache_key]
            if datetime.now() - cached_time < ttl:
                logger.debug(f"XBRL cache hit for {cache_key}")
                return cached_data
            else:
                logger.debug(f"XBRL cache expired for {cache_key}")
                del _xbrl_cache[cache_key]

        # Cache miss - fetch from SEC
        result: Optional[Dict] = None
        try:
            # SEC EDGAR XBRL data endpoint
            # Format: https://data.sec.gov/api/xbrl/companyfacts/CIK{number}.json
            cik_padded = str(cik).zfill(10)
            facts_url = f"{self.base_url}/api/xbrl/companyfacts/CIK{cik_padded}.json"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    facts_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    result = self._parse_xbrl_facts(data, target_accession=accession_number)
                else:
                    # Fallback: try to extract from filing HTML
                    result = await self._extract_from_filing_html(accession_number, cik)

        except Exception as e:
            logger.error(f"Error fetching XBRL data: {str(e)}", exc_info=True)
            result = None

        finally:
            # Only cache successful results for 24 hours
            # CRITICAL FIX: Do NOT cache None/failure results for 24 hours!
            # This was causing persistent failures where a transient SEC API issue
            # would block all retries for an entire day.
            if result is not None:
                _xbrl_cache[cache_key] = (datetime.now(), result)
                logger.debug(f"XBRL cached for {cache_key} (result: found)")
            else:
                # For failures, don't cache at all - allow immediate retry
                # This enables the "Retry Full Analysis" button to actually work
                logger.debug(f"XBRL NOT cached for {cache_key} (result: none - allowing retry)")

            # Probabilistic cache cleanup to avoid race conditions in async environments
            # ~1% chance of cleanup when cache has >100 entries
            if len(_xbrl_cache) > 100 and random.random() < 0.01:
                _cleanup_expired_cache()

        return result

    def _parse_xbrl_facts(self, facts_data: Dict, target_accession: Optional[str] = None) -> Dict:
        """Parse XBRL facts from SEC API response.

        Args:
            facts_data: Raw XBRL facts from SEC API
            target_accession: If provided, filter to entries matching this accession number.
                            Falls back to most recent 5 periods if no match found.
        """
        result = {
            "revenue": [],
            "net_income": [],
            "total_assets": [],
            "total_liabilities": [],
            "cash_and_equivalents": [],
            "earnings_per_share": [],
        }

        # Normalize target accession for matching (remove dashes)
        normalized_accession = target_accession.replace("-", "") if target_accession else None

        def _filter_and_sort_data(data_list: list, max_items: int = 5) -> list:
            """Sort by date descending and optionally filter by accession.

            This fixes the critical bug where we were taking the FIRST 5 items
            (oldest data) instead of the MOST RECENT 5 items.
            """
            if not isinstance(data_list, list):
                return []

            # Filter to valid dict entries with dates
            valid_items = [
                item for item in data_list
                if isinstance(item, dict) and item.get("end")
            ]

            # Sort by end date DESCENDING (most recent first)
            sorted_items = sorted(
                valid_items,
                key=lambda x: x.get("end", ""),
                reverse=True
            )

            # If we have a target accession, try to filter to matching entries
            if normalized_accession:
                # Diagnostic logging: show sample accession numbers from data
                sample_accns = [item.get("accn", "MISSING") for item in sorted_items[:5]]
                logger.debug(
                    f"XBRL filter: target={normalized_accession}, "
                    f"sample_accns={sample_accns}, total_items={len(sorted_items)}"
                )

                matching = [
                    item for item in sorted_items
                    if item.get("accn", "").replace("-", "") == normalized_accession
                ]
                # If we found matches for this specific filing, use them
                if matching:
                    logger.debug(f"XBRL filter: found {len(matching)} matches for {normalized_accession}")
                    return matching[:max_items]
                else:
                    # CRITICAL FIX: Do NOT fall back to wrong-year data!
                    # Return empty list instead of data from a different filing period.
                    # This prevents the bug where Jan 2025 filing shows 2018 revenue data.
                    logger.warning(
                        f"XBRL filter: NO matches for accession {normalized_accession}. "
                        f"Returning empty list to avoid wrong-year data. "
                        f"Sample accns in data: {sample_accns}"
                    )
                    return []

            # Only fall back to most recent entries when NO target accession specified
            # (e.g., for general company lookups, not specific filing analysis)
            return sorted_items[:max_items]

        try:
            facts = facts_data.get("facts", {})

            # US GAAP facts
            us_gaap = facts.get("us-gaap", {})
            if not isinstance(us_gaap, dict):
                return result

            # Extract revenue - try multiple possible field names
            # Uses module-level REVENUE_FIELD_NAMES constant for performance
            revenue_data = []
            matched_revenue_field = None
            for revenue_key in REVENUE_FIELD_NAMES:
                if revenue_key in us_gaap:
                    revenues_fact = us_gaap[revenue_key]
                    if isinstance(revenues_fact, dict) and "units" in revenues_fact:
                        revenue_data = revenues_fact["units"].get("USD", [])
                        if revenue_data:
                            matched_revenue_field = revenue_key
                            logger.debug(f"XBRL: Found revenue using field '{revenue_key}'")
                            break

            if not revenue_data:
                # Log available revenue-like fields for debugging
                available_revenue_fields = [k for k in us_gaap.keys() if 'revenue' in k.lower() or 'sales' in k.lower()]
                logger.warning(
                    f"XBRL: No revenue data found. Tried {len(REVENUE_FIELD_NAMES)} field names. "
                    f"Available revenue-like fields in XBRL: {available_revenue_fields[:10]}"
                )

            for item in _filter_and_sort_data(revenue_data):
                result["revenue"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                    "accn": item.get("accn"),
                })

            # Extract net income - try multiple possible field names
            # Uses module-level NET_INCOME_FIELD_NAMES constant for comprehensive coverage
            net_income_data = []
            matched_net_income_field = None
            for net_income_key in NET_INCOME_FIELD_NAMES:
                if net_income_key in us_gaap:
                    net_income_fact = us_gaap[net_income_key]
                    if isinstance(net_income_fact, dict) and "units" in net_income_fact:
                        net_income_data = net_income_fact["units"].get("USD", [])
                        if net_income_data:
                            matched_net_income_field = net_income_key
                            logger.debug(f"XBRL: Found net income using field '{net_income_key}'")
                            break

            if not net_income_data:
                # Log available income-like fields for debugging
                available_income_fields = [k for k in us_gaap.keys() if 'income' in k.lower() or 'profit' in k.lower() or 'loss' in k.lower()]
                logger.warning(
                    f"XBRL: No net income data found. Tried {len(NET_INCOME_FIELD_NAMES)} field names. "
                    f"Available income-like fields in XBRL: {available_income_fields[:10]}"
                )

            for item in _filter_and_sort_data(net_income_data):
                result["net_income"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                    "accn": item.get("accn"),
                })

            # Extract total assets
            if "Assets" in us_gaap:
                assets_fact = us_gaap["Assets"]
                if isinstance(assets_fact, dict) and "units" in assets_fact:
                    assets_data = assets_fact["units"].get("USD", [])
                    for item in _filter_and_sort_data(assets_data):
                        result["total_assets"].append({
                            "period": item.get("end"),
                            "value": item.get("val"),
                            "form": item.get("form"),
                            "accn": item.get("accn"),
                        })

            # Extract EPS - try multiple field names and unit formats
            # Uses module-level EPS_FIELD_NAMES constant for comprehensive coverage
            eps_data = []
            matched_eps_field = None
            for eps_key in EPS_FIELD_NAMES:
                if eps_key in us_gaap:
                    eps_fact = us_gaap[eps_key]
                    if isinstance(eps_fact, dict) and "units" in eps_fact:
                        units = eps_fact["units"]
                        # Try different unit formats (USD/shares is most common for EPS)
                        for unit_key in ["USD/shares", "USD", "shares", "pure"]:
                            if unit_key in units:
                                eps_data = units[unit_key]
                                if eps_data:
                                    matched_eps_field = eps_key
                                    logger.debug(f"XBRL: Found EPS using field '{eps_key}' with unit '{unit_key}'")
                                    break
                    if eps_data:
                        break

            if not eps_data:
                logger.debug(f"XBRL: No EPS data found. Tried {len(EPS_FIELD_NAMES)} field names.")

            for item in _filter_and_sort_data(eps_data):
                result["earnings_per_share"].append({
                    "period": item.get("end"),
                    "value": item.get("val"),
                    "form": item.get("form"),
                    "accn": item.get("accn"),
                })
        except Exception as e:
            logger.warning(f"Error parsing XBRL facts: {str(e)}", exc_info=True)

        return result

    async def _extract_from_filing_html(self, accession_number: str, cik: str) -> Optional[Dict]:
        """Fallback: Extract financial data from filing HTML"""
        try:
            # Parse accession number (format: 0001234567-12-000001)
            accession_dashed = accession_number.replace("-", "")
            if len(accession_dashed) == 18:
                # Format: https://www.sec.gov/Archives/edgar/data/{cik}/{accession_dashed}/{accession_number}.txt
                filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_dashed}/{accession_number}.txt"
            else:
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    filing_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    # Search for XBRL instance document
                    content = response.text
                    # Look for XBRL instance document link
                    xbrl_match = re.search(r'href="([^"]*\.xml)"', content)
                    if xbrl_match:
                        xbrl_url = xbrl_match.group(1)
                        if not xbrl_url.startswith("http"):
                            xbrl_url = f"https://www.sec.gov{xbrl_url}"
                        
                        # Parse XBRL XML
                        return await self._parse_xbrl_xml(xbrl_url)
            
            return None
        except Exception as e:
            logger.error(f"Error extracting from HTML: {str(e)}", exc_info=True)
            return None

    async def _parse_xbrl_xml(self, xbrl_url: str) -> Optional[Dict]:
        """Parse XBRL XML document"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    xbrl_url,
                    headers={"User-Agent": self.user_agent},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    # Basic XML parsing to extract key financial facts
                    # This is a simplified parser - in production, use a proper XBRL library
                    soup = BeautifulSoup(response.text, 'xml')
                    
                    result = {
                        "revenue": [],
                        "net_income": [],
                        "total_assets": [],
                        "total_liabilities": [],
                        "cash_and_equivalents": [],
                        "earnings_per_share": [],
                    }
                    
                    # Build context lookup to map context IDs to reporting periods
                    context_periods: Dict[str, Optional[str]] = {}
                    for context in soup.find_all('context'):
                        context_id = context.get('id')
                        if not context_id:
                            continue

                        period_value: Optional[str] = None
                        period_tag = context.find('period')
                        if period_tag:
                            instant = period_tag.find('instant')
                            if instant and instant.string:
                                period_value = instant.string.strip()
                            else:
                                end_date = period_tag.find('endDate')
                                if end_date and end_date.string:
                                    period_value = end_date.string.strip()
                        if period_value:
                            context_periods[context_id] = period_value

                    raw_tag_mappings = {
                        'us-gaap:Revenues': 'revenue',
                        'us-gaap:SalesRevenueNet': 'revenue',
                        'us-gaap:NetIncomeLoss': 'net_income',
                        'us-gaap:ProfitLoss': 'net_income',
                        'us-gaap:Assets': 'total_assets',
                        'us-gaap:Liabilities': 'total_liabilities',
                        'us-gaap:LiabilitiesAndStockholdersEquity': 'total_liabilities',
                        'us-gaap:CashAndCashEquivalentsAtCarryingValue': 'cash_and_equivalents',
                        'us-gaap:CashAndCashEquivalentsPeriodIncreaseDecrease': 'cash_and_equivalents',
                        'us-gaap:EarningsPerShareBasic': 'earnings_per_share',
                        'us-gaap:EarningsPerShareDiluted': 'earnings_per_share',
                        'us-gaap:EarningsPerShareBasicAndDiluted': 'earnings_per_share',
                    }

                    tag_mappings: Dict[str, str] = {}
                    for tag_name, mapped_key in raw_tag_mappings.items():
                        tag_mappings[tag_name.lower()] = mapped_key
                        if ":" in tag_name:
                            local_name = tag_name.split(":", 1)[1]
                            tag_mappings[local_name.lower()] = mapped_key

                    def _parse_numeric_value(raw: Optional[str]) -> Optional[float]:
                        if raw is None:
                            return None
                        text = raw.strip()
                        if not text:
                            return None
                        negative = text.startswith('(') and text.endswith(')')
                        if negative:
                            text = text[1:-1]
                        text = text.replace(',', '')
                        try:
                            value = float(text)
                        except ValueError:
                            return None
                        return -value if negative else value

                    # BeautifulSoup find_all() doesn't accept a list directly
                    # We need to search for each tag name individually or use a lambda
                    def _is_target_tag(tag):
                        """Check if tag matches any of our lookup tags"""
                        tag_name_lower = tag.name.lower() if tag.name else ""
                        return tag_name_lower in tag_mappings
                    
                    for tag in soup.find_all(_is_target_tag):
                        mapped_key = tag_mappings.get(tag.name.lower())
                        if not mapped_key:
                            continue

                        numeric_value = _parse_numeric_value(tag.string)
                        if numeric_value is None:
                            continue

                        context_ref = tag.get('contextRef', '').strip()
                        result.setdefault(mapped_key, []).append(
                            {
                                "period": context_periods.get(context_ref),
                                "value": numeric_value,
                                "form": tag.get('form'),
                            }
                        )
                    
                    return result if any(result.values()) else None
            
            return None
        except Exception as e:
            logger.error(f"Error parsing XBRL XML: {str(e)}", exc_info=True)
            return None

    def extract_standardized_metrics(self, xbrl_data: Dict) -> Dict:
        """Extract standardized financial metrics from XBRL data"""

        def _normalise_series(entries: List[Dict]) -> List[Dict]:
            cleaned: List[Dict] = []
            seen_periods = set()
            # Sort descending by period (ISO dates sort lexicographically)
            sorted_entries = sorted(
                (entry for entry in entries if entry.get("period") and entry.get("value") is not None),
                key=lambda item: item.get("period"),
                reverse=True,
            )
            for entry in sorted_entries:
                period = entry.get("period")
                if period in seen_periods:
                    continue
                seen_periods.add(period)
                cleaned.append(
                    {
                        "period": period,
                        "value": entry.get("value"),
                        "form": entry.get("form"),
                    }
                )
            return cleaned

        def _build_metric_entry(series: List[Dict]) -> Dict:
            """Build a metric entry with current, prior, series, and period change."""
            entry: Dict[str, any] = {}
            if series:
                entry["current"] = series[0]
            if len(series) > 1:
                entry["prior"] = series[1]
                # Compute period-over-period change (OBJECTIVE calculation only)
                current_val = series[0].get("value")
                prior_val = series[1].get("value")
                entry["change"] = compute_period_change(current_val, prior_val)
            if series:
                entry["series"] = series
            return entry

        metrics: Dict[str, Dict] = {}

        revenue_series = _normalise_series(xbrl_data.get("revenue", []))
        net_income_series = _normalise_series(xbrl_data.get("net_income", []))
        eps_series = _normalise_series(xbrl_data.get("earnings_per_share", []))

        if revenue_series:
            metrics["revenue"] = _build_metric_entry(revenue_series)

        if net_income_series:
            metrics["net_income"] = _build_metric_entry(net_income_series)

        if eps_series:
            metrics["earnings_per_share"] = _build_metric_entry(eps_series)

        # Build net margin series by aligning revenue and net income periods
        if revenue_series and net_income_series:
            income_by_period = {entry["period"]: entry for entry in net_income_series}
            margin_series: List[Dict] = []
            for revenue_entry in revenue_series:
                period = revenue_entry["period"]
                income_entry = income_by_period.get(period)
                revenue_value = revenue_entry.get("value")
                income_value = income_entry.get("value") if income_entry else None
                if (
                    revenue_value is not None
                    and income_value is not None
                    and revenue_value != 0
                ):
                    margin_series.append(
                        {
                            "period": period,
                            "value": (income_value / revenue_value) * 100,
                            "form": revenue_entry.get("form"),
                        }
                    )
            if margin_series:
                metrics["net_margin"] = _build_metric_entry(margin_series)

        return metrics

xbrl_service = XBRLService()

