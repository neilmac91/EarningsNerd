from __future__ import annotations

import asyncio
import atexit
from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.sec_edgar import SECEdgarService


class TrendingTickerService:
    """Service responsible for fetching and caching trending stock tickers."""

    _cache_ttl = timedelta(minutes=10)
    _persistent_cache_ttl = timedelta(hours=24)
    _persistent_cache_filename = ".cache/trending_tickers.json"
    _symbol_lookup_ttl = timedelta(hours=12)
    _positive_keywords = {
        "beat",
        "bull",
        "bullish",
        "breakout",
        "crush",
        "gain",
        "gains",
        "green",
        "higher",
        "moon",
        "outperform",
        "rally",
        "record",
        "strong",
        "surge",
        "up",
        "upgrade",
        "win",
    }
    _negative_keywords = {
        "bear",
        "bearish",
        "breakdown",
        "cut",
        "cuts",
        "downgrade",
        "drop",
        "dump",
        "fall",
        "fear",
        "gap down",
        "lower",
        "miss",
        "plunge",
        "red",
        "sell",
        "short",
        "weak",
    }

    def __init__(self) -> None:
        self._cache_data: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._symbol_lookup: Dict[str, str] = {}
        self._symbol_lookup_loaded_at: Optional[datetime] = None
        self._sec_service = SECEdgarService()
        self._logger = logging.getLogger(__name__)
        self._last_error: Optional[str] = None
        cache_root = Path("/tmp") if settings.ENVIRONMENT == "production" else Path(".")
        self._cache_file_path = (cache_root / self._persistent_cache_filename).resolve()
        self._symbol_cache_path = (cache_root / ".cache/sec_ticker_lookup.json").resolve()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._http_client_lock = asyncio.Lock()
        # Rate limit tracking: source -> (backoff_until, consecutive_429s)
        self._rate_limit_backoff: Dict[str, tuple[Optional[datetime], int]] = {}
        self._ensure_cache_directory()
        self._load_persistent_cache(initial_load=True)
        self._load_symbol_lookup_from_disk()
        atexit.register(self._close_http_client_sync)

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

        client = await self._get_http_client()
        fetch_tasks = {
            "x": asyncio.create_task(self._fetch_from_x(client)),
            "yahoo": asyncio.create_task(self._fetch_from_yahoo(client)),
        }

        fetch_results: Dict[str, Optional[Dict[str, Any]]] = {}
        for source, task in fetch_tasks.items():
            try:
                fetch_results[source] = await task
            except Exception as exc:
                message = f"{source} trending fetch error: {exc.__class__.__name__}"
                self._last_error = message
                self._logger.warning("Failed to fetch trending data from %s: %s", source, exc, exc_info=True)
                fetch_results[source] = None

        x_data = fetch_results.get("x")
        yahoo_data = fetch_results.get("yahoo")

        if x_data and x_data.get("tickers"):
            result = x_data
        elif yahoo_data and yahoo_data.get("tickers"):
            result = yahoo_data

        if result and result.get("tickers"):
            enriched_tickers = await self._enrich_company_metadata(result["tickers"])
            payload = {
                "tickers": enriched_tickers,
                "source": result.get("source", "unknown"),
                "timestamp": now.isoformat() + "Z",
                "cached": False,
                "status": "ok",
            }
            if result.get("message"):
                payload["message"] = result["message"]
            self._cache_data = payload
            self._cache_timestamp = now
            self._persist_cache(payload)
            return payload

        if self._cache_data:
            # Provide stale data if available
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

        persistent_payload = self._load_persistent_cache()
        if persistent_payload and persistent_payload.get("tickers"):
            message = persistent_payload.get("message") or "Serving persisted trending data."
            if self._last_error:
                message = f"{message} Last error: {self._last_error}"
            persistent_payload.update(
                {
                    "cached": True,
                    "status": persistent_payload.get("status", "stale"),
                    "message": message,
                    "source": f"{persistent_payload.get('source', 'cache')} (persisted)",
                }
            )
            self._cache_data = persistent_payload
            timestamp_raw = persistent_payload.get("timestamp")
            timestamp = self._parse_timestamp(timestamp_raw) if timestamp_raw else None
            if timestamp:
                self._cache_timestamp = timestamp
            return persistent_payload

        # Final fallback when nothing is available
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

    async def _fetch_from_x(self, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        source = "x"
        
        # Check if we're in backoff period
        if self._is_rate_limited(source):
            backoff_until, _ = self._rate_limit_backoff[source]
            remaining = (backoff_until - datetime.utcnow()).total_seconds() / 60 if backoff_until else 0
            self._last_error = f"X API rate-limited. Retry after {remaining:.0f} minutes"
            self._logger.info("Skipping X fetch due to rate limit backoff (%.0f min remaining)", remaining)
            return None
        
        token = settings.TWITTER_BEARER_TOKEN.strip() if settings.TWITTER_BEARER_TOKEN else ""
        if not token:
            self._logger.info("Skipping X trending fetch: TWITTER_BEARER_TOKEN is not configured.")
            self._last_error = "X API token not configured."
            return None

        url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": "lang:en -is:retweet has:cashtags",
            "max_results": 100,
            "tweet.fields": "created_at,entities,lang,public_metrics",
        }

        headers = {
            "Authorization": f"Bearer {token}",
        }

        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            # Success - reset rate limit tracking
            self._record_success(source)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._record_rate_limit(source)
                self._last_error = f"X API returned 429 (rate limited)"
                self._logger.warning("Rate limited by X API. Backing off.")
            else:
                self._last_error = f"X API returned {exc.response.status_code}"
                self._logger.warning("Failed to fetch trending data from X: %s", self._last_error)
            return None
        except httpx.HTTPError as exc:
            self._last_error = f"X API error: {exc.__class__.__name__}"
            self._logger.warning("Failed to fetch trending data from X: %s", exc, exc_info=True)
            return None

        data = response.json()
        tweets: List[Dict[str, Any]] = data.get("data", [])
        if not tweets:
            self._last_error = "X API returned no tweets."
            return None

        mentions: Dict[str, int] = defaultdict(int)
        sentiment_totals: Dict[str, float] = defaultdict(float)
        engagement_totals: Dict[str, int] = defaultdict(int)

        for tweet in tweets:
            entities = tweet.get("entities") or {}
            cashtags = entities.get("cashtags") or []
            text = tweet.get("text", "")
            sentiment_score = self._score_sentiment(text)
            metrics = tweet.get("public_metrics") or {}
            engagement = (
                metrics.get("retweet_count", 0) * 2
                + metrics.get("reply_count", 0)
                + metrics.get("quote_count", 0)
                + metrics.get("like_count", 0)
                + 1
            )

            for cashtag in cashtags:
                symbol = cashtag.get("tag", "").upper()
                if not symbol:
                    continue
                mentions[symbol] += 1
                engagement_totals[symbol] += engagement
                sentiment_totals[symbol] += sentiment_score * engagement

        if not mentions:
            return None

        sorted_symbols = sorted(
            engagement_totals.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        tickers: List[Dict[str, Any]] = []
        for symbol, count in sorted_symbols[:15]:
            avg_sentiment = 0.0
            if engagement_totals[symbol]:
                avg_sentiment = sentiment_totals[symbol] / engagement_totals[symbol]
            tickers.append(
                {
                    "symbol": symbol,
                    "name": None,
                    "tweet_volume": mentions.get(symbol, 0),
                    "engagement": count,
                    "sentiment_score": round(avg_sentiment, 3),
                }
            )

        return {"tickers": tickers, "source": "X API"}

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

    async def _fetch_from_yahoo(self, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
        source = "yahoo"
        
        # Check if we're in backoff period
        if self._is_rate_limited(source):
            backoff_until, _ = self._rate_limit_backoff[source]
            remaining = (backoff_until - datetime.utcnow()).total_seconds() / 60 if backoff_until else 0
            self._last_error = f"Yahoo trending rate-limited. Retry after {remaining:.0f} minutes"
            self._logger.info("Skipping Yahoo fetch due to rate limit backoff (%.0f min remaining)", remaining)
            return None
        
        url = "https://query1.finance.yahoo.com/v1/finance/trending/US"
        try:
            response = await client.get(url)
            response.raise_for_status()
            # Success - reset rate limit tracking
            self._record_success(source)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                self._record_rate_limit(source)
                self._last_error = f"Yahoo trending returned 429 (rate limited)"
                self._logger.warning("Rate limited by Yahoo Finance. Backing off.")
            else:
                self._last_error = f"Yahoo trending returned {exc.response.status_code}"
                self._logger.warning("Failed to fetch trending data from Yahoo Finance: %s", self._last_error)
            return None
        except httpx.HTTPError as exc:
            self._last_error = f"Yahoo trending error: {exc.__class__.__name__}"
            self._logger.warning("Failed to fetch trending data from Yahoo Finance", exc_info=True)
            return None

        payload = response.json()
        results = payload.get("finance", {}).get("result", [])
        if not results:
            self._last_error = "Yahoo trending response had no results."
            return None

        tickers: List[Dict[str, Any]] = []
        for result in results:
            for quote in result.get("quotes", []) or []:
                symbol = quote.get("symbol")
                if not symbol:
                    continue
                tickers.append(
                    {
                        "symbol": symbol.upper(),
                        "name": quote.get("shortName") or quote.get("longName"),
                        "tweet_volume": quote.get("regularMarketVolume"),
                        "sentiment_score": None,
                    }
                )

        if not tickers:
            return None

        return {"tickers": tickers[:15], "source": "Yahoo Finance"}

    async def _enrich_company_metadata(self, tickers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tickers:
            return []

        await self._ensure_symbol_lookup()

        enriched: List[Dict[str, Any]] = []
        for ticker in tickers:
            symbol = ticker.get("symbol", "").upper()
            name = ticker.get("name")
            if not name:
                name = self._symbol_lookup.get(symbol)
            enriched.append(
                {
                    **ticker,
                    "symbol": symbol,
                    "name": name,
                }
            )
        return enriched

    async def _ensure_symbol_lookup(self) -> None:
        if self._symbol_lookup and self._symbol_lookup_loaded_at:
            age = datetime.utcnow() - self._symbol_lookup_loaded_at
            if age < self._symbol_lookup_ttl:
                return

        try:
            tickers_data = await self._sec_service.get_company_tickers()
        except Exception:
            return

        lookup: Dict[str, str] = {}
        for entry in tickers_data.values():
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker")
            name = entry.get("title")
            if ticker and name:
                lookup[ticker.upper()] = name

        if lookup:
            self._symbol_lookup = lookup
            self._symbol_lookup_loaded_at = datetime.utcnow()
            self._persist_symbol_lookup()

    def _score_sentiment(self, text: str) -> float:
        if not text:
            return 0.0

        lowered = text.lower()
        positive_hits = sum(1 for word in self._positive_keywords if word in lowered)
        negative_hits = sum(1 for word in self._negative_keywords if word in lowered)

        total = positive_hits + negative_hits
        if total == 0:
            return 0.0

        return (positive_hits - negative_hits) / total

    def _ensure_cache_directory(self) -> None:
        try:
            self._cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            self._symbol_cache_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            self._logger.debug("Unable to ensure cache directory exists: %s", exc, exc_info=True)

    def _persist_cache(self, payload: Dict[str, Any]) -> None:
        sanitized = {**payload}
        sanitized.pop("cached", None)
        try:
            with self._cache_file_path.open("w", encoding="utf-8") as cache_file:
                json.dump(sanitized, cache_file)
        except Exception as exc:
            self._logger.debug("Unable to persist trending cache: %s", exc, exc_info=True)

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
            self._logger.debug("Unable to load persisted trending cache: %s", exc, exc_info=True)
            return None

    def _default_fallback_tickers(self) -> List[Dict[str, Any]]:
        return [
            {"symbol": "AAPL", "name": "Apple Inc.", "tweet_volume": None, "sentiment_score": None},
            {"symbol": "MSFT", "name": "Microsoft Corporation", "tweet_volume": None, "sentiment_score": None},
            {"symbol": "NVDA", "name": "NVIDIA Corporation", "tweet_volume": None, "sentiment_score": None},
            {"symbol": "AMZN", "name": "Amazon.com, Inc.", "tweet_volume": None, "sentiment_score": None},
            {"symbol": "TSLA", "name": "Tesla, Inc.", "tweet_volume": None, "sentiment_score": None},
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

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client and not self._http_client.is_closed:
            return self._http_client

        async with self._http_client_lock:
            if self._http_client is None or self._http_client.is_closed:
                self._http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(8.0, connect=2.0, read=6.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                )
        return self._http_client

    def _close_http_client_sync(self) -> None:
        client = self._http_client
        if not client or client.is_closed:
            return

        async def _close() -> None:
            await client.aclose()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(_close())
        else:
            asyncio.run(_close())
        self._http_client = None

    def _persist_symbol_lookup(self) -> None:
        if not self._symbol_lookup:
            return
        payload = {
            "loaded_at": datetime.utcnow().isoformat() + "Z",
            "symbols": self._symbol_lookup,
        }
        try:
            with self._symbol_cache_path.open("w", encoding="utf-8") as cache_file:
                json.dump(payload, cache_file)
        except Exception as exc:
            self._logger.debug("Unable to persist symbol lookup: %s", exc, exc_info=True)

    def _load_symbol_lookup_from_disk(self) -> None:
        try:
            if not self._symbol_cache_path.is_file():
                return
            with self._symbol_cache_path.open("r", encoding="utf-8") as cache_file:
                data = json.load(cache_file)
            symbols = data.get("symbols") or {}
            loaded_at_raw = data.get("loaded_at")
            loaded_at = self._parse_timestamp(loaded_at_raw) if loaded_at_raw else None
            if not isinstance(symbols, dict) or not loaded_at:
                return
            if datetime.utcnow() - loaded_at > self._symbol_lookup_ttl:
                return
            self._symbol_lookup = {str(k).upper(): str(v) for k, v in symbols.items()}
            self._symbol_lookup_loaded_at = loaded_at
        except Exception as exc:
            self._logger.debug("Unable to load symbol lookup cache: %s", exc, exc_info=True)


trending_service = TrendingTickerService()
