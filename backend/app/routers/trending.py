from fastapi import APIRouter

from app.services.trending_service import trending_service

router = APIRouter()


@router.get("/trending_tickers")
async def get_trending_tickers():
    """Return trending tickers from X or fallback sources."""
    data = await trending_service.get_trending_tickers()

    tickers = data.get("tickers") or []
    if not tickers:
        # Ensure clients receive a helpful message even for empty datasets
        data.setdefault("status", "unavailable")
        data.setdefault("message", "Trending data is temporarily unavailable. Showing latest known status.")

    # Remove internal bookkeeping callers don't need to see
    data.pop("cached", None)
    return data
