from app.utils.datetimes import utcnow, iso_z
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.trending_service import trending_service

router = APIRouter()


class PriceData(BaseModel):
    """Price data for a single ticker."""
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None


class PriceRefreshResponse(BaseModel):
    """Response from price refresh endpoint."""
    prices: dict[str, PriceData]
    timestamp: str


@router.get("/trending_tickers")
async def get_trending_tickers():
    """
    LEGACY: return trending tickers from Stocktwits with FMP validation.

    The homepage surface is flag-hidden (NEXT_PUBLIC_ENABLE_MARKET_MOVERS, default off): FMP's
    legacy API is dead for this account (every call 403s → the curated fallback always serves)
    and no license-clean $0 replacement exists — see tasks/homepage-sections-review-findings.md.
    Endpoint + service are tombstoned pending the teardown PR (importer allowlist:
    tests/unit/test_dead_integrations_allowlist.py).
    """
    data = await trending_service.get_trending_tickers()

    tickers = data.get("tickers") or []
    if not tickers:
        # Ensure clients receive a helpful message even for empty datasets
        data.setdefault("status", "unavailable")
        data.setdefault("message", "Trending data is temporarily unavailable. Showing latest known status.")

    # Remove internal bookkeeping callers don't need to see
    data.pop("cached", None)
    return data


@router.get("/trending_tickers/refresh-prices")
async def refresh_ticker_prices(
    symbols: List[str] = Query(
        default=[],
        description="List of ticker symbols to refresh prices for",
        max_length=50,
    ),
):
    """
    Refresh prices for the given tickers.

    This lightweight endpoint supports 2-minute price refresh intervals
    without refetching the full trending list.

    Max 50 symbols per request.
    """
    if not symbols:
        return PriceRefreshResponse(
            prices={},
            timestamp=iso_z(utcnow()),
        )

    prices_raw = await trending_service.refresh_prices(symbols)

    prices = {
        symbol: PriceData(
            price=data.get("price"),
            change=data.get("change"),
            change_percent=data.get("change_percent"),
        )
        for symbol, data in prices_raw.items()
    }

    return PriceRefreshResponse(
        prices=prices,
        timestamp=iso_z(utcnow()),
    )
