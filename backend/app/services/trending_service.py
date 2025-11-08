from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.sec_edgar import SECEdgarService


class TrendingTickerService:
    """Service responsible for fetching and caching trending stock tickers."""

    _cache_ttl = timedelta(minutes=10)
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

    async def get_trending_tickers(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Return trending tickers, using caching and fallbacks when necessary."""

        now = datetime.utcnow()

        if not force_refresh and self._cache_data and self._cache_timestamp:
            if now - self._cache_timestamp < self._cache_ttl:
                return {**self._cache_data, "cached": True}

        result: Optional[Dict[str, Any]] = None

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
            }
            self._cache_data = payload
            self._cache_timestamp = now
            return payload

        if self._cache_data:
            # Provide stale data if available
            return {
                **self._cache_data,
                "source": f"{self._cache_data.get('source', 'cache')} (stale)",
                "timestamp": self._cache_data.get("timestamp", now.isoformat() + "Z"),
                "cached": True,
            }

        # Final fallback when nothing is available
        return {
            "tickers": [],
            "source": "unavailable",
            "timestamp": now.isoformat() + "Z",
        }

    async def _fetch_from_x(self) -> Optional[Dict[str, Any]]:
        token = settings.TWITTER_BEARER_TOKEN.strip() if settings.TWITTER_BEARER_TOKEN else ""
        if not token:
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
        except httpx.HTTPError:
            return None

        data = response.json()
        tweets: List[Dict[str, Any]] = data.get("data", [])
        if not tweets:
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
        except httpx.HTTPError:
            return None

        payload = response.json()
        results = payload.get("finance", {}).get("result", [])
        if not results:
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


trending_service = TrendingTickerService()
