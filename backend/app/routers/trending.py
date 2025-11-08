from fastapi import APIRouter, HTTPException

from app.services.trending_service import trending_service

router = APIRouter()


@router.get("/trending_tickers")
async def get_trending_tickers():
    """Return trending tickers from X or fallback sources."""
    data = await trending_service.get_trending_tickers()

    if not data.get("tickers"):
        # Provide a clear error when nothing is available at all
        if not data.get("cached"):
            raise HTTPException(status_code=503, detail="Trending tickers are temporarily unavailable.")

    # Remove the internal cached flag from the response payload
    data.pop("cached", None)
    return data
