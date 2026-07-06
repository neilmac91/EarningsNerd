"""Alpha Vantage EARNINGS_CALENDAR integration — the bulk forward-estimates layer.

ONE CSV request returns the entire US-listed forward calendar (~6k rows, 3 months out); free-tier
25 req/day is ample for a daily cron. This is a **bridge** source (personal-use free tier — see
tasks/earnings-calendar-strategy.md §2/§3.6): the earnings engine works with no key at all
(EDGAR-only), so ``fetch_earnings_calendar`` returns ``[]`` when ``ALPHA_VANTAGE_API_KEY`` is unset.

CSV columns (verified live 2026-07-03):
    symbol,name,reportDate,fiscalDateEnding,estimate,currency,timeOfTheDay
``timeOfTheDay`` is sparsely populated (pre-market / post-market) — the engine derives the bmo/amc
slot from the company's own reporting history instead, so this field is a nice-to-have here.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

import httpx

from app.config import settings
from app.utils.numbers import coerce_float

logger = logging.getLogger(__name__)


def _parse_date(value: object) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_time(value: object) -> Optional[str]:
    """Map AV's ``timeOfTheDay`` to the engine's bmo/amc slot vocabulary (or None)."""
    if not value or not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v in ("pre-market", "premarket", "bmo"):
        return "bmo"
    if v in ("post-market", "postmarket", "amc"):
        return "amc"
    return None


@dataclass
class AVEarningsRow:
    """One forward earnings row from the Alpha Vantage bulk calendar."""

    symbol: str
    company_name: Optional[str]
    report_date: date
    fiscal_period_end: Optional[date]
    eps_estimate: Optional[float]
    currency: Optional[str]
    event_time: Optional[str]  # bmo | amc | None


class AlphaVantageClient:
    """Async client for Alpha Vantage's EARNINGS_CALENDAR (bulk CSV)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        horizon: Optional[str] = None,
    ) -> None:
        self._api_key = (api_key if api_key is not None else getattr(settings, "ALPHA_VANTAGE_API_KEY", "") or "").strip()
        self._base_url = (base_url or getattr(settings, "ALPHA_VANTAGE_API_BASE", "https://www.alphavantage.co/query")).rstrip("/")
        timeout_value = timeout_seconds or getattr(settings, "ALPHA_VANTAGE_TIMEOUT_SECONDS", 20.0)
        self._timeout = httpx.Timeout(timeout_value)
        self._horizon = horizon or getattr(settings, "ALPHA_VANTAGE_HORIZON", "3month")

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def fetch_earnings_calendar(self) -> List[AVEarningsRow]:
        """Fetch the whole US forward earnings calendar. Returns [] when unconfigured or on error.

        Never raises — a flaky bridge source must not break the daily ingest (the EDGAR layer
        still produces reported + pattern-estimated rows on its own).
        """
        if not self._api_key:
            logger.info("Alpha Vantage API key not configured; skipping bulk earnings calendar.")
            return []

        params = {
            "function": "EARNINGS_CALENDAR",
            "horizon": self._horizon,
            "apikey": self._api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self._base_url, params=params)
                response.raise_for_status()
                body = response.text
        except httpx.HTTPError as exc:
            logger.warning("Alpha Vantage earnings calendar request failed: %s", exc)
            return []

        # A non-CSV body (JSON "Information"/"Note") means throttling or a bad key — AV returns 200
        # with a JSON message rather than an HTTP error. Detect and degrade to empty.
        stripped = body.lstrip()
        if not stripped or stripped[0] in "{[":
            logger.warning("Alpha Vantage returned a non-CSV body (rate limit or invalid key): %s", stripped[:160])
            return []

        return self._parse_csv(body)

    @staticmethod
    def _parse_csv(body: str) -> List[AVEarningsRow]:
        rows: List[AVEarningsRow] = []
        reader = csv.DictReader(io.StringIO(body))
        for raw in reader:
            symbol = (raw.get("symbol") or "").strip().upper()
            report_date = _parse_date(raw.get("reportDate"))
            if not symbol or report_date is None:
                continue
            rows.append(
                AVEarningsRow(
                    symbol=symbol,
                    company_name=(raw.get("name") or "").strip() or None,
                    report_date=report_date,
                    fiscal_period_end=_parse_date(raw.get("fiscalDateEnding")),
                    eps_estimate=coerce_float(raw.get("estimate")),
                    currency=(raw.get("currency") or "").strip() or None,
                    event_time=_normalize_time(raw.get("timeOfTheDay")),
                )
            )
        return rows


alpha_vantage_client = AlphaVantageClient()
