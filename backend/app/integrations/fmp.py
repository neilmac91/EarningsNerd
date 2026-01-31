"""Financial Modeling Prep (FMP) integration for stock validation, price data, and earnings calendar."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _coerce_float(value: object) -> Optional[float]:
    """Safely convert a value to float."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: object) -> Optional[date]:
    """Parse date from various formats."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


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


@dataclass
class FMPEarningsEvent:
    """Earnings calendar event from FMP API."""

    symbol: str
    earnings_date: date
    eps_estimated: Optional[float]
    eps_actual: Optional[float]
    revenue_estimated: Optional[float]
    revenue_actual: Optional[float]
    time: Optional[str]  # "bmo" (before market open) or "amc" (after market close)
    raw: dict


class FMPClient:
    """Async client for Financial Modeling Prep API.

    Supports:
    - Stock validation (profiles, ETF lists)
    - Real-time quotes
    - Earnings calendar
    """

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

    # -------------------------------------------------------------------------
    # Stock Validation Methods
    # -------------------------------------------------------------------------

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
                price=_coerce_float(item.get("price")),
                changes=_coerce_float(item.get("changes")),
                changes_percentage=_coerce_float(item.get("changesPercentage")),
                market_cap=_coerce_float(item.get("mktCap")),
                raw=item,
            )
            results[profile.symbol] = profile

        return results

    # -------------------------------------------------------------------------
    # Earnings Calendar Methods
    # -------------------------------------------------------------------------

    async def fetch_earnings_calendar(
        self,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> Dict[str, FMPEarningsEvent]:
        """Fetch earnings calendar for a date range.

        Returns a dict keyed by symbol with the most recent earnings event for each.
        """
        if not self._api_key:
            logger.info("FMP API key not configured. Skipping earnings calendar lookup.")
            return {}

        # Default to 14-day window (7 days past, 7 days future)
        today = date.today()
        if from_date is None:
            from_date = today - timedelta(days=7)
        if to_date is None:
            to_date = today + timedelta(days=7)

        url = f"{self._base_url}/earnings-calendar"
        params = {
            "apikey": self._api_key,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("FMP earnings calendar request failed", exc_info=exc)
                return {}

        try:
            payload = response.json()
        except ValueError:
            logger.warning("FMP earnings calendar response was not valid JSON")
            return {}

        if not isinstance(payload, list):
            logger.warning("FMP earnings calendar response was not a list")
            return {}

        return self._parse_earnings_list(payload)

    async def fetch_upcoming_earnings(
        self,
        days_ahead: int = 14,
    ) -> Dict[str, FMPEarningsEvent]:
        """Fetch upcoming earnings for the next N days.

        Returns a dict keyed by symbol.
        """
        today = date.today()
        return await self.fetch_earnings_calendar(
            from_date=today,
            to_date=today + timedelta(days=days_ahead),
        )

    def _parse_earnings_list(self, payload: List[dict]) -> Dict[str, FMPEarningsEvent]:
        """Parse list of earnings events into a dict keyed by symbol.

        If multiple events exist for the same symbol, keeps the one closest to today.
        """
        results: Dict[str, FMPEarningsEvent] = {}
        today = date.today()

        for item in payload:
            event = self._parse_single_event(item)
            if event is None:
                continue

            symbol = event.symbol.upper()
            existing = results.get(symbol)

            # Keep the event closest to today
            if existing is None:
                results[symbol] = event
            else:
                existing_delta = abs((existing.earnings_date - today).days)
                new_delta = abs((event.earnings_date - today).days)
                if new_delta < existing_delta:
                    results[symbol] = event

        return results

    @staticmethod
    def _parse_single_event(item: dict) -> Optional[FMPEarningsEvent]:
        """Parse a single earnings event from the API response."""
        if not isinstance(item, dict):
            return None

        symbol = item.get("symbol")
        if not symbol or not isinstance(symbol, str):
            return None

        earnings_date = _parse_date(item.get("date"))
        if earnings_date is None:
            return None

        return FMPEarningsEvent(
            symbol=symbol.upper(),
            earnings_date=earnings_date,
            eps_estimated=_coerce_float(item.get("epsEstimated")),
            eps_actual=_coerce_float(item.get("eps")),
            revenue_estimated=_coerce_float(item.get("revenueEstimated")),
            revenue_actual=_coerce_float(item.get("revenue")),
            time=item.get("time") if isinstance(item.get("time"), str) else None,
            raw=item,
        )


fmp_client = FMPClient()
