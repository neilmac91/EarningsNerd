"""
EdgarTools XBRL Service

Provides XBRL financial data extraction using EdgarTools.
This service maintains API compatibility with the legacy xbrl_service.py
to enable gradual migration.

Caching Strategy (Two-Tier):
- L1: In-memory cache (fast, process-local, LRU eviction at 1000 entries)
- L2: Redis cache (persistent, shared across instances)

Usage:
    from app.services.edgar.xbrl_service import edgar_xbrl_service

    # Get XBRL data (compatible with legacy interface)
    data = await edgar_xbrl_service.get_xbrl_data(accession_number, cik)

    # Extract standardized metrics
    metrics = edgar_xbrl_service.extract_standardized_metrics(data)
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from edgar import Company as EdgarCompany, set_identity

from .async_executor import run_in_executor, run_in_executor_with_timeout
from .config import EDGAR_IDENTITY, EDGAR_DEFAULT_TIMEOUT_SECONDS
from .models import FinancialMetric, MetricChange, MetricSeries, XBRLData

logger = logging.getLogger(__name__)

# Ensure identity is set
set_identity(EDGAR_IDENTITY)

# Module-level cache for XBRL data (L1 - in-memory with LRU eviction)
# Key: "{cik}:{accession_number}"
# Value: (cached_datetime, data_dict)
# Using OrderedDict for LRU eviction - most recently accessed items at end
_xbrl_cache: OrderedDict[str, Tuple[datetime, Optional[Dict]]] = OrderedDict()
_cache_ttl = timedelta(hours=24)
_cache_max_size = 1000  # Maximum entries before LRU eviction

# Cache operation counters for structured logging and metrics
_cache_hits = 0
_cache_misses = 0
_cache_evictions = 0

# Async lock to protect cache operations from concurrent coroutine access.
# WHY lazy initialization: asyncio.Lock must be created within an event loop context.
# If created at module import time (outside of async context), it binds to no loop
# or the wrong loop, causing "attached to a different loop" errors.
# By creating it lazily on first use, we ensure it binds to the correct running loop.
_cache_lock: asyncio.Lock | None = None


def _get_cache_lock() -> asyncio.Lock:
    """
    Get or create the cache lock (lazy initialization for event loop safety).

    This pattern ensures the asyncio.Lock is created within the context of the
    event loop that will actually use it, avoiding "attached to a different loop" errors.
    """
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


def clear_xbrl_cache() -> int:
    """
    Clear the XBRL cache. Returns number of entries cleared.

    Note: For async contexts, prefer async_clear_xbrl_cache() for thread safety.
    """
    global _xbrl_cache
    count = len(_xbrl_cache)
    _xbrl_cache.clear()
    logger.info(f"Cleared {count} XBRL cache entries")
    return count


async def async_clear_xbrl_cache() -> int:
    """Clear the XBRL cache (async-safe). Returns number of entries cleared."""
    global _xbrl_cache
    async with _get_cache_lock():
        count = len(_xbrl_cache)
        _xbrl_cache.clear()
        logger.info(f"Cleared {count} XBRL cache entries")
        return count


def _cache_set_sync(key: str, value: Tuple[datetime, Optional[Dict]]) -> None:
    """
    Set a value in L1 cache with LRU eviction (sync version, call within lock).

    If cache exceeds max size, evicts oldest entries (least recently used).
    Tracks eviction count for metrics and uses structured logging.
    """
    global _xbrl_cache, _cache_evictions

    # If key exists, move to end (most recently used)
    if key in _xbrl_cache:
        _xbrl_cache.move_to_end(key)
        _xbrl_cache[key] = value
        return

    # Add new entry
    _xbrl_cache[key] = value

    # Evict oldest entries if over max size
    evicted_this_call = 0
    while len(_xbrl_cache) > _cache_max_size:
        oldest_key, (cached_time, _) = _xbrl_cache.popitem(last=False)
        _cache_evictions += 1
        evicted_this_call += 1
        # Structured log with key details for debugging cache pressure
        logger.info(
            "XBRL L1 cache eviction",
            extra={
                "event": "cache_eviction",
                "cache_type": "xbrl_l1",
                "evicted_key": oldest_key,
                "entry_age_hours": round((datetime.now() - cached_time).total_seconds() / 3600, 2),
                "cache_size": len(_xbrl_cache),
                "total_evictions": _cache_evictions,
            }
        )

    # Log batch eviction summary if multiple entries evicted
    if evicted_this_call > 1:
        logger.warning(
            f"XBRL L1 cache batch eviction: {evicted_this_call} entries",
            extra={
                "event": "cache_batch_eviction",
                "cache_type": "xbrl_l1",
                "evicted_count": evicted_this_call,
                "new_key": key,
                "cache_size": len(_xbrl_cache),
            }
        )


def get_xbrl_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics for monitoring (L1 in-memory cache).

    Returns dict with both new (l1_*) and legacy (total_entries, valid_entries)
    keys for backward compatibility.
    """
    now = datetime.now()
    total = len(_xbrl_cache)
    valid_count = sum(
        1 for cached_time, _ in _xbrl_cache.values()
        if now - cached_time < _cache_ttl
    )
    expired_count = total - valid_count

    # Calculate hit rate
    total_ops = _cache_hits + _cache_misses
    hit_rate = round(_cache_hits / total_ops * 100, 2) if total_ops > 0 else 0.0

    return {
        # New L1-prefixed keys for two-tier caching clarity
        "l1_total_entries": total,
        "l1_valid_entries": valid_count,
        "l1_expired_entries": expired_count,
        "l1_max_size": _cache_max_size,
        "l1_utilization_percent": round(total / _cache_max_size * 100, 1) if _cache_max_size > 0 else 0,
        "l1_hits": _cache_hits,
        "l1_misses": _cache_misses,
        "l1_hit_rate": hit_rate,
        "l1_evictions": _cache_evictions,
        "cache_ttl_hours": _cache_ttl.total_seconds() / 3600,
        # Backward compatibility aliases (deprecated)
        "total_entries": total,
        "valid_entries": valid_count,
        "expired_entries": expired_count,
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

        Uses two-tier caching:
        - L1: In-memory cache (fast, process-local)
        - L2: Redis cache (persistent, shared across instances)

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
        global _xbrl_cache, _cache_hits, _cache_misses

        # Build cache keys
        memory_key = f"{cik}:{accession_number}"
        redis_key = f"xbrl:{cik}:{accession_number}"

        # L1: Check in-memory cache first (fastest) - protected by async lock
        async with _get_cache_lock():
            if memory_key in _xbrl_cache:
                cached_time, cached_data = _xbrl_cache[memory_key]
                if datetime.now() - cached_time < _cache_ttl:
                    # Move to end for LRU ordering (most recently used)
                    _xbrl_cache.move_to_end(memory_key)
                    _cache_hits += 1
                    logger.debug(f"XBRL L1 cache hit for {memory_key}")
                    return cached_data
                else:
                    logger.debug(f"XBRL L1 cache expired for {memory_key}")
                    del _xbrl_cache[memory_key]
                    # L1 cache miss (expired) - track inside lock for thread safety
                    _cache_misses += 1
            else:
                # L1 cache miss (not found) - track inside lock for thread safety
                _cache_misses += 1

        # L2: Check Redis cache (persistent, shared)
        redis_data = await self._get_from_redis(redis_key)
        if redis_data is not None:
            logger.debug(f"XBRL L2 cache hit for {redis_key}")
            # Populate L1 cache from L2 with LRU eviction
            async with _get_cache_lock():
                _cache_set_sync(memory_key, (datetime.now(), redis_data))
            return redis_data

        # Cache miss - fetch from EdgarTools
        result = await self._fetch_xbrl_data(cik, accession_number)

        # Cache successful results in both tiers
        if result is not None:
            async with _get_cache_lock():
                _cache_set_sync(memory_key, (datetime.now(), result))
            await self._set_to_redis(redis_key, result)
            logger.debug(f"XBRL cached (L1+L2) for {memory_key}")
        else:
            logger.debug(f"XBRL NOT cached for {memory_key} (no data)")

        return result

    async def _get_from_redis(self, key: str) -> Optional[Dict[str, Any]]:
        """Get XBRL data from Redis cache (L2)."""
        try:
            from app.services.redis_service import cache_get
            return await cache_get(key)
        except Exception as e:
            logger.debug(f"Redis L2 cache get failed for {key}: {e}")
            return None

    async def _set_to_redis(self, key: str, data: Dict[str, Any]) -> bool:
        """Set XBRL data in Redis cache (L2)."""
        try:
            from app.services.redis_service import cache_set, CacheTTL
            return await cache_set(key, data, CacheTTL.XBRL_DATA)
        except Exception as e:
            logger.debug(f"Redis L2 cache set failed for {key}: {e}")
            return False

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

    def extract_standardized_metrics(self, xbrl_data: Optional[Dict]) -> Dict[str, Any]:
        """
        Extract standardized financial metrics from XBRL data.

        This method maintains backward compatibility with the legacy interface.

        Args:
            xbrl_data: Raw XBRL data dictionary (can be None)

        Returns:
            Dictionary with standardized metrics including current, prior,
            change calculations, and series data. Returns empty dict if
            xbrl_data is None or empty.
        """
        # Handle None or empty input
        if not xbrl_data:
            return {}

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
