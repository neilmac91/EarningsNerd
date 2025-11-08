import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from dateutil import parser as date_parser

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_datetime(value: object) -> Optional[datetime]:
    if value in (None, "", 0):
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        try:
            # Most EarningsWhispers timestamps are in seconds
            return datetime.utcfromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        try:
            parsed = date_parser.parse(value)
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except (ValueError, OverflowError, TypeError):
            return None

    return None


def _coerce_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class EarningsWhispersSignal:
    symbol: str
    score: float
    raw_score: Optional[float]
    event_time: Optional[datetime]
    metadata: Dict[str, object]


class EarningsWhispersClient:
    """Lightweight client for the public EarningsWhispers API."""

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 6.0) -> None:
        self._base_url = (base_url or settings.EARNINGS_WHISPERS_API_BASE).rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)

    @staticmethod
    def _extract_entries(payload: object) -> List[dict]:
        if isinstance(payload, list):
            return [entry for entry in payload if isinstance(entry, dict)]

        if isinstance(payload, dict):
            for key in ("hot", "Hot", "results", "data", "payload"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [entry for entry in value if isinstance(entry, dict)]

        return []

    async def fetch_hot_symbols(self, limit: int = 25) -> Dict[str, EarningsWhispersSignal]:
        """Fetch hot symbols from EarningsWhispers.

        The public API does not require authentication. We normalise the response
        so the rest of the application can consume consistent structures.
        """

        params = {"type": "hot", "format": "json"}
        headers = {
            "Accept": "application/json",
            "User-Agent": settings.HOT_FILINGS_USER_AGENT,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                response = await client.get(self._base_url, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failures
            logger.warning("Failed to fetch EarningsWhispers hot symbols", exc_info=exc)
            return {}

        try:
            payload = response.json()
        except ValueError:  # pragma: no cover - invalid API response
            logger.warning("Invalid JSON received from EarningsWhispers hot endpoint")
            return {}

        entries = self._extract_entries(payload)
        if not entries:
            logger.info("EarningsWhispers hot endpoint returned no entries")
            return {}

        signals: Dict[str, EarningsWhispersSignal] = {}
        for entry in entries:
            symbol_value = next(
                (entry.get(key) for key in ("symbol", "ticker", "Symbol", "Ticker")),
                None,
            )
            if not symbol_value:
                continue

            symbol = str(symbol_value).strip().upper()
            if not symbol:
                continue

            raw_score = None
            for key in ("score", "Score", "buzz", "Buzz", "mentions", "Mentions", "rank", "Rank"):
                raw_score = _coerce_float(entry.get(key))
                if raw_score is not None:
                    break

            score = raw_score if raw_score is not None else 1.0

            event_time = None
            for key in ("datetime", "date", "eventDate", "event_time", "time"):
                event_time = _parse_datetime(entry.get(key))
                if event_time is not None:
                    break

            metadata = {
                "name": entry.get("name") or entry.get("company") or entry.get("Company"),
                "rank": entry.get("rank") or entry.get("Rank"),
            }

            signals[symbol] = EarningsWhispersSignal(
                symbol=symbol,
                score=score,
                raw_score=raw_score,
                event_time=event_time,
                metadata=metadata,
            )

            if len(signals) >= limit:
                break

        return signals


earnings_whispers_client = EarningsWhispersClient()

