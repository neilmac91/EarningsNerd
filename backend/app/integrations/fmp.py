"""FMP (Financial Modeling Prep) integration for earnings calendar data."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

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
    """Async client for Financial Modeling Prep Earnings Calendar API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self._api_key = (api_key or settings.FMP_API_KEY or "").strip()
        self._base_url = (base_url or settings.FMP_API_BASE).rstrip("/")
        timeout_value = timeout_seconds or settings.FMP_TIMEOUT_SECONDS
        self._timeout = httpx.Timeout(timeout_value)

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
