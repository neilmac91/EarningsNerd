from __future__ import annotations

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

        x_data = await self._fetch_from_x()
        if x_data and x_data.get("tickers"):
            result = x_data
        else:
            fallback_data = await self._fetch_from_yahoo()
            if fallback_data and fallback_data.get("tickers"):
                result = fallback_data

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

    async def _fetch_from_x(self) -> Optional[Dict[str, Any]]:
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
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
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

        for tweet in tweets:
            entities = tweet.get("entities") or {}
            cashtags = entities.get("cashtags") or []
            text = tweet.get("text", "")
            sentiment_score = self._score_sentiment(text)

            for cashtag in cashtags:
                symbol = cashtag.get("tag", "").upper()
                if not symbol:
                    continue
                mentions[symbol] += 1
                sentiment_totals[symbol] += sentiment_score

        if not mentions:
            return None

        sorted_symbols = sorted(mentions.items(), key=lambda item: item[1], reverse=True)

        tickers: List[Dict[str, Any]] = []
        for symbol, count in sorted_symbols[:15]:
            avg_sentiment = 0.0
            if mentions[symbol]:
                avg_sentiment = sentiment_totals[symbol] / mentions[symbol]
            tickers.append(
                {
                    "symbol": symbol,
                    "name": None,
                    "tweet_volume": count,
                    "sentiment_score": round(avg_sentiment, 3),
                }
            )

        return {"tickers": tickers, "source": "X API"}

    async def _fetch_from_yahoo(self) -> Optional[Dict[str, Any]]:
        url = "https://query1.finance.yahoo.com/v1/finance/trending/US"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
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
            if age < timedelta(hours=12):
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


trending_service = TrendingTickerService()
