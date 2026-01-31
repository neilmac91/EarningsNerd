from __future__ import annotations

import asyncio
import atexit
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import httpx

from app.config import settings
from app.integrations.stocktwits import stocktwits_client, StocktwitsClient, StocktwitsSymbol
from app.integrations.fmp import fmp_client, FMPClient
from app.services.redis_service import (
    cache_get,
    cache_set,
    CacheNamespace,
    CacheTTL,
)


class TrendingTickerService:
    """
    Service responsible for fetching and caching trending stock tickers.

    Data sources (in priority order):
    1. Stocktwits + FMP validation (primary)
    2. Stale cache
    3. Curated fallback list
    """

    _cache_ttl = timedelta(minutes=10)
    _persistent_cache_ttl = timedelta(hours=24)
    _persistent_cache_filename = ".cache/trending_tickers.json"
    _etf_cache_ttl = timedelta(days=7)
    _validation_cache_ttl = timedelta(hours=6)
    _price_cache_ttl = timedelta(minutes=2)

    def __init__(
        self,
        stocktwits: Optional[StocktwitsClient] = None,
        fmp: Optional[FMPClient] = None,
    ) -> None:
        self._stocktwits = stocktwits or stocktwits_client
        self._fmp = fmp or fmp_client
        self._cache_data: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._logger = logging.getLogger(__name__)
        self._last_error: Optional[str] = None

        # Memory cache for ETF symbols (L1 cache)
        self._etf_symbols: Optional[Set[str]] = None
        self._etf_symbols_loaded_at: Optional[datetime] = None

        import tempfile
        cache_root = Path(tempfile.gettempdir()) if settings.ENVIRONMENT == "production" else Path(".")
        self._cache_file_path = (cache_root / self._persistent_cache_filename).resolve()

        # Rate limit tracking: source -> (backoff_until, consecutive_429s)
        self._rate_limit_backoff: Dict[str, tuple[Optional[datetime], int]] = {}

        self._ensure_cache_directory()
        self._load_persistent_cache(initial_load=True)

    async def get_trending_tickers(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Return trending tickers, using caching and fallbacks when necessary."""
        now = datetime.utcnow()

        if not force_refresh and self._cache_data and self._cache_timestamp:
            if now - self._cache_timestamp < self._cache_ttl:
                cached_payload = {**self._cache_data}
                cached_payload["cached"] = True
                cached_payload.setdefault("status", "ok")
                if self._last_error:
                    cached_payload.setdefault("message", f"Showing cached results. Last error: {self._last_error}")
                return cached_payload

        result: Optional[Dict[str, Any]] = None
        self._last_error = None

        # Try Stocktwits + FMP as primary source
        result = await self._fetch_from_stocktwits_fmp()

        if result and result.get("tickers"):
            payload = {
                "tickers": result["tickers"],
                "source": result.get("source", "Stocktwits"),
                "timestamp": now.isoformat() + "Z",
                "cached": False,
                "status": "ok",
            }
            if result.get("message"):
                payload["message"] = result["message"]
            if result.get("filtered_count"):
                payload["filtered_count"] = result["filtered_count"]

            self._cache_data = payload
            self._cache_timestamp = now
            self._persist_cache(payload)
            return payload

        # Fallback to stale in-memory cache
        if self._cache_data:
            stale_payload = {
                **self._cache_data,
                "cached": True,
                "status": "stale",
                "source": f"{self._cache_data.get('source', 'cache')} (stale)",
                "timestamp": self._cache_data.get("timestamp", now.isoformat() + "Z"),
            }
            message = "Upstream trending sources unavailable. Showing cached data."
            if self._last_error:
                message = f"{message} Last error: {self._last_error}"
            stale_payload["message"] = message
            return stale_payload

        # Fallback to persistent file cache
        persistent_payload = self._load_persistent_cache()
        if persistent_payload and persistent_payload.get("tickers"):
            message = persistent_payload.get("message") or "Serving persisted trending data."
            if self._last_error:
                message = f"{message} Last error: {self._last_error}"
            persistent_payload.update({
                "cached": True,
                "status": persistent_payload.get("status", "stale"),
                "message": message,
                "source": f"{persistent_payload.get('source', 'cache')} (persisted)",
            })
            self._cache_data = persistent_payload
            timestamp_raw = persistent_payload.get("timestamp")
            timestamp = self._parse_timestamp(timestamp_raw) if timestamp_raw else None
            if timestamp:
                self._cache_timestamp = timestamp
            return persistent_payload

        # Final fallback to curated list
        fallback_tickers = self._default_fallback_tickers()
        fallback_status = "fallback" if fallback_tickers else "unavailable"
        fallback_message = "Trending sources are temporarily unavailable."
        if fallback_status == "fallback":
            fallback_message = "Showing curated fallback trending tickers."
        if self._last_error:
            fallback_message = f"{fallback_message} Last error: {self._last_error}"
        return {
            "tickers": fallback_tickers,
            "source": "curated" if fallback_tickers else "unavailable",
            "timestamp": now.isoformat() + "Z",
            "cached": False,
            "status": fallback_status,
            "message": fallback_message,
        }

    async def refresh_prices(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Refresh prices for the given symbols.

        Returns a dict mapping symbol -> price data.
        Used for 2-minute price refresh intervals.
        """
        if not symbols:
            return {}

        if not self._fmp.is_configured:
            self._logger.debug("FMP not configured, skipping price refresh")
            return {}

        try:
            quotes = await self._fmp.get_quotes(symbols)
            return {
                symbol: {
                    "price": data.get("price"),
                    "change": data.get("change"),
                    "change_percent": data.get("changesPercentage"),
                }
                for symbol, data in quotes.items()
            }
        except Exception as exc:
            self._logger.warning("Price refresh failed: %s", exc)
            return {}

    async def _fetch_from_stocktwits_fmp(self) -> Optional[Dict[str, Any]]:
        """
        Fetch trending from Stocktwits and validate with FMP.

        Steps:
        1. Fetch raw trending from Stocktwits
        2. Pre-filter obvious non-stocks (crypto, forex, warrants)
        3. Filter against cached ETF list
        4. Validate remaining symbols with FMP profiles
        5. Return validated stocks with price data
        """
        source = "stocktwits"

        # Check rate limit backoff
        if self._is_rate_limited(source):
            backoff_until, _ = self._rate_limit_backoff[source]
            remaining = (backoff_until - datetime.utcnow()).total_seconds() / 60 if backoff_until else 0
            self._last_error = f"Stocktwits rate-limited. Retry after {remaining:.0f} minutes"
            self._logger.info("Skipping Stocktwits fetch due to rate limit backoff (%.0f min remaining)", remaining)
            return None

        # Step 1: Fetch from Stocktwits
        try:
            raw_symbols = await self._stocktwits.fetch_trending()
        except Exception as exc:
            self._last_error = f"Stocktwits fetch error: {exc.__class__.__name__}"
            self._logger.warning("Stocktwits fetch failed: %s", exc)
            return None

        if not raw_symbols:
            self._last_error = "Stocktwits returned no symbols"
            return None

        self._record_success(source)

        # Step 2: Pre-filter (zero API calls)
        filtered_symbols = self._stocktwits.pre_filter_symbols(raw_symbols)
        pre_filter_removed = len(raw_symbols) - len(filtered_symbols)

        if not filtered_symbols:
            self._last_error = "All Stocktwits symbols filtered out (crypto/forex)"
            return None

        # Step 3: Filter against cached ETF list
        etf_symbols = await self._get_etf_list()
        non_etf_symbols = [s for s in filtered_symbols if s.symbol not in etf_symbols]
        etf_removed = len(filtered_symbols) - len(non_etf_symbols)

        if not non_etf_symbols:
            self._last_error = "All remaining symbols were ETFs"
            return None

        # Step 4: Validate with FMP (with caching)
        validated_symbols = await self._validate_symbols_with_fmp(non_etf_symbols)
        validation_removed = len(non_etf_symbols) - len(validated_symbols)

        total_filtered = pre_filter_removed + etf_removed + validation_removed

        if not validated_symbols:
            self._last_error = "No symbols passed FMP validation"
            return None

        # Build result
        tickers = []
        for item in validated_symbols[:10]:  # Limit to top 10
            tickers.append({
                "symbol": item["symbol"],
                "name": item.get("name"),
                "watchlist_count": item.get("watchlist_count"),
                "price": item.get("price"),
                "change": item.get("change"),
                "change_percent": item.get("change_percent"),
            })

        return {
            "tickers": tickers,
            "source": "Stocktwits",
            "filtered_count": total_filtered,
        }

    async def _get_etf_list(self) -> Set[str]:
        """
        Get ETF symbol set with two-tier caching.

        L1: In-memory cache (1 day TTL)
        L2: Redis cache (7 day TTL)
        """
        now = datetime.utcnow()

        # Check L1 (memory) cache
        if self._etf_symbols and self._etf_symbols_loaded_at:
            if now - self._etf_symbols_loaded_at < timedelta(days=1):
                return self._etf_symbols

        # Check L2 (Redis) cache
        cache_key = f"{CacheNamespace.COMPANY}:etf_list"
        cached = await cache_get(cache_key)
        if cached and isinstance(cached, list):
            self._etf_symbols = set(cached)
            self._etf_symbols_loaded_at = now
            return self._etf_symbols

        # Fetch from FMP
        if not self._fmp.is_configured:
            self._logger.debug("FMP not configured, returning empty ETF list")
            return set()

        try:
            etf_list = await self._fmp.get_etf_list()
            etf_symbols = {etf.symbol for etf in etf_list}

            # Cache in Redis (L2)
            await cache_set(
                cache_key,
                list(etf_symbols),
                ttl=int(self._etf_cache_ttl.total_seconds()),
            )

            # Cache in memory (L1)
            self._etf_symbols = etf_symbols
            self._etf_symbols_loaded_at = now

            self._logger.info("Loaded %d ETF symbols from FMP", len(etf_symbols))
            return etf_symbols

        except Exception as exc:
            self._logger.warning("Failed to load ETF list: %s", exc)
            return self._etf_symbols or set()

    async def _validate_symbols_with_fmp(
        self, symbols: List[StocktwitsSymbol]
    ) -> List[Dict[str, Any]]:
        """
        Validate symbols with FMP profiles and enrich with price data.

        Uses per-symbol caching to minimize API calls.
        """
        if not self._fmp.is_configured:
            # Return symbols without validation if FMP not configured
            return [
                {
                    "symbol": s.symbol,
                    "name": s.title,
                    "watchlist_count": s.watchlist_count,
                }
                for s in symbols
            ]

        # Check cache for each symbol
        results: List[Dict[str, Any]] = []
        uncached_symbols: List[StocktwitsSymbol] = []

        for item in symbols:
            cache_key = f"{CacheNamespace.COMPANY}:valid:{item.symbol}"
            cached = await cache_get(cache_key)

            if cached is not None:
                if cached.get("is_valid", False):
                    results.append({
                        "symbol": item.symbol,
                        "name": cached.get("name") or item.title,
                        "watchlist_count": item.watchlist_count,
                        "price": cached.get("price"),
                        "change": cached.get("change"),
                        "change_percent": cached.get("change_percent"),
                    })
            else:
                uncached_symbols.append(item)

        if not uncached_symbols:
            return results

        # Batch validate uncached symbols
        symbol_list = [s.symbol for s in uncached_symbols]
        try:
            profiles = await self._fmp.get_profiles(symbol_list)
        except Exception as exc:
            self._logger.warning("FMP profile fetch failed: %s", exc)
            # Return uncached symbols without validation
            for item in uncached_symbols:
                results.append({
                    "symbol": item.symbol,
                    "name": item.title,
                    "watchlist_count": item.watchlist_count,
                })
            return results

        # Process profiles and cache results
        for item in uncached_symbols:
            profile = profiles.get(item.symbol)
            cache_key = f"{CacheNamespace.COMPANY}:valid:{item.symbol}"

            if profile and profile.is_valid_stock:
                cache_data = {
                    "is_valid": True,
                    "name": profile.company_name,
                    "price": profile.price,
                    "change": profile.changes,
                    "change_percent": profile.changes_percentage,
                }
                await cache_set(
                    cache_key,
                    cache_data,
                    ttl=int(self._validation_cache_ttl.total_seconds()),
                )
                results.append({
                    "symbol": item.symbol,
                    "name": profile.company_name or item.title,
                    "watchlist_count": item.watchlist_count,
                    "price": profile.price,
                    "change": profile.changes,
                    "change_percent": profile.changes_percentage,
                })
            else:
                # Cache negative result too (shorter TTL)
                await cache_set(
                    cache_key,
                    {"is_valid": False},
                    ttl=int(self._validation_cache_ttl.total_seconds()),
                )

        return results

    def _is_rate_limited(self, source: str) -> bool:
        """Check if a source is currently rate-limited."""
        backoff_info = self._rate_limit_backoff.get(source)
        if not backoff_info:
            return False
        backoff_until, _ = backoff_info
        if backoff_until and datetime.utcnow() < backoff_until:
            return True
        return False

    def _record_rate_limit(self, source: str) -> None:
        """Record a rate limit hit and set exponential backoff."""
        backoff_info = self._rate_limit_backoff.get(source, (None, 0))
        _, consecutive_429s = backoff_info

        # Exponential backoff: 1min, 5min, 15min, 30min, max 1 hour
        backoff_minutes = min(60, (2 ** consecutive_429s) * 1 if consecutive_429s < 3 else 15 + (consecutive_429s - 3) * 5)
        backoff_until = datetime.utcnow() + timedelta(minutes=backoff_minutes)

        self._rate_limit_backoff[source] = (backoff_until, consecutive_429s + 1)
        self._logger.warning(
            "Rate limit hit for %s. Backing off for %d minutes (consecutive: %d)",
            source,
            backoff_minutes,
            consecutive_429s + 1,
        )

    def _record_success(self, source: str) -> None:
        """Record a successful request, resetting rate limit tracking."""
        if source in self._rate_limit_backoff:
            self._rate_limit_backoff[source] = (None, 0)

    def _ensure_cache_directory(self) -> None:
        try:
            self._cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._logger.debug("Unable to ensure cache directory exists: %s", exc)

    def _persist_cache(self, payload: Dict[str, Any]) -> None:
        sanitized = {**payload}
        sanitized.pop("cached", None)
        try:
            with self._cache_file_path.open("w", encoding="utf-8") as cache_file:
                json.dump(sanitized, cache_file)
        except Exception as exc:
            self._logger.debug("Unable to persist trending cache: %s", exc)

    def _load_persistent_cache(self, initial_load: bool = False) -> Optional[Dict[str, Any]]:
        try:
            if not self._cache_file_path.is_file():
                return None

            with self._cache_file_path.open("r", encoding="utf-8") as cache_file:
                data = json.load(cache_file)

            timestamp_raw = data.get("timestamp")
            timestamp = self._parse_timestamp(timestamp_raw) if timestamp_raw else None
            if not timestamp:
                return None

            if datetime.utcnow() - timestamp > self._persistent_cache_ttl and not initial_load:
                return None

            self._cache_data = data
            self._cache_timestamp = timestamp
            return data
        except Exception as exc:
            self._logger.debug("Unable to load persisted trending cache: %s", exc)
            return None

    def _default_fallback_tickers(self) -> List[Dict[str, Any]]:
        return [
            {"symbol": "NVDA", "name": "NVIDIA Corporation", "watchlist_count": None, "price": None, "change": None, "change_percent": None},
            {"symbol": "TSLA", "name": "Tesla, Inc.", "watchlist_count": None, "price": None, "change": None, "change_percent": None},
            {"symbol": "AAPL", "name": "Apple Inc.", "watchlist_count": None, "price": None, "change": None, "change_percent": None},
            {"symbol": "MSFT", "name": "Microsoft Corporation", "watchlist_count": None, "price": None, "change": None, "change_percent": None},
            {"symbol": "AMZN", "name": "Amazon.com, Inc.", "watchlist_count": None, "price": None, "change": None, "change_percent": None},
        ]

    def _parse_timestamp(self, timestamp_raw: str) -> Optional[datetime]:
        if not timestamp_raw:
            return None
        try:
            normalized = timestamp_raw
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None


trending_service = TrendingTickerService()
