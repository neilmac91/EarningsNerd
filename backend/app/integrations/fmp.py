"""Financial Modeling Prep (FMP) integration for stock validation and price data."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class FMPProfile:
    """Normalized company profile from FMP."""

    symbol: str
    company_name: str
    exchange: str
    is_etf: bool
    is_fund: bool
    is_actively_trading: bool
    price: Optional[float]
    changes: Optional[float]
    changes_percentage: Optional[float]
    market_cap: Optional[float]
    raw: dict

    @property
    def is_valid_stock(self) -> bool:
        """Check if this profile represents a valid tradable stock."""
        # Must not be ETF or fund
        if self.is_etf or self.is_fund:
            return False

        # Must be on a major US exchange
        valid_exchanges = {"NASDAQ", "NYSE", "AMEX", "NYSEArca"}
        if self.exchange not in valid_exchanges:
            return False

        # Must be actively trading
        if not self.is_actively_trading:
            return False

        return True


@dataclass
class FMPEtf:
    """ETF entry from FMP ETF list."""

    symbol: str
    name: str


class FMPClient:
    """Lightweight async client for Financial Modeling Prep API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_concurrency: Optional[int] = None,
    ) -> None:
        self._api_key = (api_key or getattr(settings, 'FMP_API_KEY', '') or "").strip()
        self._base_url = (base_url or getattr(settings, 'FMP_API_BASE', 'https://financialmodelingprep.com/api/v3')).rstrip("/")
        timeout_value = timeout_seconds or getattr(settings, 'FMP_TIMEOUT_SECONDS', 6.0)
        self._timeout = httpx.Timeout(timeout_value)
        self._max_concurrency = max(1, max_concurrency or getattr(settings, 'FMP_MAX_CONCURRENCY', 4))
        self._semaphore = asyncio.Semaphore(self._max_concurrency)

    @property
    def is_configured(self) -> bool:
        """Check if FMP API key is configured."""
        return bool(self._api_key)

    async def get_etf_list(self) -> List[FMPEtf]:
        """
        Fetch complete ETF list from FMP.

        This is a single API call that can be cached for a week.
        Returns empty list if API key not configured or on error.
        """
        if not self._api_key:
            logger.debug("FMP API key not configured, skipping ETF list fetch")
            return []

        url = f"{self._base_url}/etf/list"
        params = {"apikey": self._api_key}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "FMP ETF list returned %d: %s",
                exc.response.status_code,
                exc.response.text[:200] if exc.response.text else "no body",
            )
            return []
        except httpx.HTTPError as exc:
            logger.warning("FMP ETF list request failed: %s", exc)
            return []
        except ValueError as exc:
            logger.warning("FMP ETF list returned invalid JSON: %s", exc)
            return []

        if not isinstance(data, list):
            return []

        results: List[FMPEtf] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if symbol:
                results.append(
                    FMPEtf(
                        symbol=str(symbol).upper(),
                        name=item.get("name") or "",
                    )
                )

        return results

    async def get_profiles(self, symbols: List[str]) -> Dict[str, FMPProfile]:
        """
        Fetch company profiles for multiple symbols (batch).

        FMP supports comma-separated symbols in the URL path.
        Processes symbols in batches of 25 for resilience.

        Returns a dict mapping symbol -> FMPProfile.
        """
        if not self._api_key:
            logger.debug("FMP API key not configured, skipping profile fetch")
            return {}

        if not symbols:
            return {}

        results: Dict[str, FMPProfile] = {}
        batch_size = 25

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            symbols_param = ",".join(batch)
            url = f"{self._base_url}/profile/{symbols_param}"
            params = {"apikey": self._api_key}

            try:
                async with self._semaphore:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        data = response.json()
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "FMP profile batch returned %d for %d symbols",
                    exc.response.status_code,
                    len(batch),
                )
                continue
            except httpx.HTTPError as exc:
                logger.warning("FMP profile batch request failed: %s", exc)
                continue
            except ValueError as exc:
                logger.warning("FMP profile batch returned invalid JSON: %s", exc)
                continue

            results.update(self._parse_profiles(data))

        return results

    async def get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch real-time quotes for multiple symbols.

        This is a lightweight endpoint for price updates.
        Processes symbols in batches of 50 for resilience.
        """
        if not self._api_key:
            return {}

        if not symbols:
            return {}

        results: Dict[str, Dict] = {}
        batch_size = 50

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            symbols_param = ",".join(batch)
            url = f"{self._base_url}/quote/{symbols_param}"
            params = {"apikey": self._api_key}

            try:
                async with self._semaphore:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.get(url, params=params)
                        response.raise_for_status()
                        data = response.json()
            except httpx.HTTPError as exc:
                logger.warning("FMP quote batch request failed: %s", exc)
                continue
            except ValueError as exc:
                logger.warning("FMP quote batch returned invalid JSON: %s", exc)
                continue

            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue
                symbol = item.get("symbol")
                if symbol:
                    results[symbol.upper()] = {
                        "price": item.get("price"),
                        "change": item.get("change"),
                        "changesPercentage": item.get("changesPercentage"),
                        "volume": item.get("volume"),
                        "marketCap": item.get("marketCap"),
                    }

        return results

    def _parse_profiles(self, data: list) -> Dict[str, FMPProfile]:
        """Parse FMP profile response into normalized objects."""
        if not isinstance(data, list):
            return {}

        results: Dict[str, FMPProfile] = {}
        for item in data:
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol")
            if not symbol:
                continue

            profile = FMPProfile(
                symbol=str(symbol).upper(),
                company_name=item.get("companyName") or "",
                exchange=item.get("exchangeShortName") or "",
                is_etf=bool(item.get("isEtf", False)),
                is_fund=bool(item.get("isFund", False)),
                is_actively_trading=bool(item.get("isActivelyTrading", True)),
                price=self._coerce_float(item.get("price")),
                changes=self._coerce_float(item.get("changes")),
                changes_percentage=self._coerce_float(item.get("changesPercentage")),
                market_cap=self._coerce_float(item.get("mktCap")),
                raw=item,
            )
            results[profile.symbol] = profile

        return results

    @staticmethod
    def _coerce_float(value) -> Optional[float]:
        """Safely convert a value to float."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


fmp_client = FMPClient()
