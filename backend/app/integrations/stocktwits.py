"""Stocktwits integration for fetching trending stock symbols."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StocktwitsSymbol:
    """Normalized trending symbol from Stocktwits."""

    symbol: str
    title: str
    watchlist_count: Optional[int]
    raw: dict


class StocktwitsClient:
    """Lightweight async client for Stocktwits trending API."""

    TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        timeout_value = timeout_seconds or getattr(settings, 'STOCKTWITS_TIMEOUT_SECONDS', 6.0)
        self._timeout = httpx.Timeout(timeout_value)

    async def fetch_trending(self) -> List[StocktwitsSymbol]:
        """
        Fetch trending symbols from Stocktwits.

        Returns a list of StocktwitsSymbol objects, empty list on error.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self.TRENDING_URL)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Stocktwits API returned %d: %s",
                exc.response.status_code,
                exc.response.text[:200] if exc.response.text else "no body",
            )
            return []
        except httpx.HTTPError as exc:
            logger.warning("Stocktwits request failed: %s", exc)
            return []
        except ValueError as exc:
            logger.warning("Stocktwits returned invalid JSON: %s", exc)
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> List[StocktwitsSymbol]:
        """Parse Stocktwits API response into normalized objects."""
        if not isinstance(data, dict):
            return []

        symbols_raw = data.get("symbols", [])
        if not isinstance(symbols_raw, list):
            return []

        results: List[StocktwitsSymbol] = []
        for item in symbols_raw:
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol")
            if not symbol:
                continue

            results.append(
                StocktwitsSymbol(
                    symbol=str(symbol).upper(),
                    title=item.get("title") or "",
                    watchlist_count=item.get("watchlist_count"),
                    raw=item,
                )
            )

        return results

    @staticmethod
    def pre_filter_symbols(symbols: List[StocktwitsSymbol]) -> List[StocktwitsSymbol]:
        """
        Pre-filter symbols to remove obvious non-stocks before FMP validation.

        Filters out:
        - Crypto (.X suffix on Stocktwits)
        - Forex pairs (contain /)
        - Warrants and units (.WS, .WT, .U suffixes)
        - Invalid characters
        - Excessively long symbols (>6 chars)
        """
        filtered: List[StocktwitsSymbol] = []

        for item in symbols:
            symbol = item.symbol.upper()

            # Skip crypto (Stocktwits uses .X suffix)
            if symbol.endswith(".X"):
                continue

            # Skip forex pairs
            if "/" in symbol:
                continue

            # Skip warrants, units, and other special securities
            if any(suffix in symbol for suffix in [".WS", ".WT", ".U", "-WT", "-WS"]):
                continue

            # Skip symbols with invalid characters
            cleaned = symbol.replace("-", "").replace(".", "")
            if not cleaned.isalnum():
                continue

            # Skip excessively long symbols (likely not standard US stocks)
            if len(symbol) > 6:
                continue

            # Skip single-character symbols (rare, often indexes)
            if len(symbol) == 1:
                continue

            filtered.append(item)

        return filtered


stocktwits_client = StocktwitsClient()
