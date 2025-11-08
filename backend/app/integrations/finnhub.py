"""Finnhub integration used to enrich hot filings with news buzz data."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _coerce_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class FinnhubSentiment:
    """Normalized sentiment payload from Finnhub's news sentiment endpoint."""

    symbol: str
    buzz_ratio: Optional[float]
    articles_in_last_week: Optional[float]
    weekly_average_articles: Optional[float]
    company_news_score: Optional[float]
    bullish_percent: Optional[float]
    sector_bullish_percent: Optional[float]
    raw: dict


class FinnhubClient:
    """Lightweight asynchronous client for Finnhub."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_concurrency: Optional[int] = None,
    ) -> None:
        self._api_key = (api_key or settings.FINNHUB_API_KEY or "").strip()
        self._base_url = (base_url or settings.FINNHUB_API_BASE).rstrip("/")
        timeout_value = timeout_seconds or settings.FINNHUB_TIMEOUT_SECONDS
        self._timeout = httpx.Timeout(timeout_value)
        self._max_concurrency = max(1, max_concurrency or settings.FINNHUB_MAX_CONCURRENCY)

    async def fetch_news_sentiment(self, symbols: Iterable[str]) -> Dict[str, FinnhubSentiment]:
        """Fetch news sentiment for the provided symbols."""

        if not self._api_key:
            logger.info("Finnhub API key not configured. Skipping sentiment lookup.")
            return {}

        unique_symbols = {symbol.strip().upper() for symbol in symbols if symbol}
        if not unique_symbols:
            return {}

        semaphore = asyncio.Semaphore(self._max_concurrency)
        results: Dict[str, FinnhubSentiment] = {}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            tasks = [
                asyncio.create_task(self._fetch_single_sentiment(client, semaphore, symbol))
                for symbol in unique_symbols
            ]

            for task in asyncio.as_completed(tasks):
                try:
                    sentiment = await task
                except Exception as exc:  # pragma: no cover - network/runtime errors
                    logger.warning("Finnhub sentiment lookup failed", exc_info=exc)
                    continue

                if sentiment:
                    results[sentiment.symbol] = sentiment

        return results

    async def _fetch_single_sentiment(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        symbol: str,
    ) -> Optional[FinnhubSentiment]:
        url = f"{self._base_url}/news-sentiment"
        params = {"symbol": symbol}
        headers = {"X-Finnhub-Token": self._api_key, "Accept": "application/json"}

        async with semaphore:
            try:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as exc:  # pragma: no cover - network errors
                logger.warning("Finnhub news sentiment request failed", exc_info=exc)
                return None

        try:
            payload = response.json()
        except ValueError:  # pragma: no cover - invalid response
            logger.warning("Finnhub news sentiment response was not valid JSON")
            return None

        return self._parse_sentiment(symbol, payload)

    @staticmethod
    def _parse_sentiment(symbol: str, payload: dict) -> Optional[FinnhubSentiment]:
        if not isinstance(payload, dict):
            return None

        buzz_data = payload.get("buzz") if isinstance(payload.get("buzz"), dict) else {}
        sentiment_data = (
            payload.get("sentiment") if isinstance(payload.get("sentiment"), dict) else {}
        )

        buzz_ratio = _coerce_float(buzz_data.get("buzz"))
        articles_in_last_week = _coerce_float(buzz_data.get("articlesInLastWeek"))
        weekly_average = _coerce_float(buzz_data.get("weeklyAverage"))
        company_news_score = _coerce_float(payload.get("companyNewsScore"))
        bullish_percent = _coerce_float(sentiment_data.get("bullishPercent"))
        sector_bullish_percent = _coerce_float(sentiment_data.get("sectorAverageBullishPercent"))

        return FinnhubSentiment(
            symbol=symbol,
            buzz_ratio=buzz_ratio,
            articles_in_last_week=articles_in_last_week,
            weekly_average_articles=weekly_average,
            company_news_score=company_news_score,
            bullish_percent=bullish_percent,
            sector_bullish_percent=sector_bullish_percent,
            raw=payload,
        )


finnhub_client = FinnhubClient()

