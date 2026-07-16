from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.hot_filings import hot_filings_service
from app.services.pulse_service import compose_pulse

router = APIRouter()


@router.get("/hot_filings")
async def get_hot_filings(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Return the hottest recent filings ranked by buzz score.

    Always served through the 15-min cache. Cache bypass is deliberately NOT a query param:
    this endpoint is unauthenticated, and an anonymous `force_refresh` let any caller force
    the full DB-aggregation + FMP/Finnhub recompute per request. Operators refresh via
    POST /hot_filings/refresh (admin token) below.
    """
    data = await hot_filings_service.get_hot_filings(db, limit=limit)
    # Provide fallback to recent filings if nothing returned
    if not data.get("filings"):
        from sqlalchemy import desc
        from app.models import Filing

        fallback_filings = (
            db.query(Filing)
            .order_by(desc(Filing.filing_date))
            .limit(limit)
            .all()
        )
        data["filings"] = [
            {
                "filing_id": filing.id,
                "symbol": filing.company.ticker if filing.company else None,
                "company_name": filing.company.name if filing.company else None,
                "filing_type": filing.filing_type,
                "filing_date": filing.filing_date.isoformat(),
                "buzz_score": 0.0,
                "sources": ["recent_filings"],
                "buzz_components": {
                    "recency": 0.0,
                    "search_activity": 0.0,
                    "filing_velocity": 0.0,
                    "filing_type_bonus": 0.0,
                    "earnings_calendar": 0.0,
                    "news_buzz": 0.0,
                    "news_headlines": 0.0,
                    "news_sentiment": 0.0,
                },
            }
            for filing in fallback_filings
        ]

    # Compose the calm "Filing Pulse" from the already-computed buzz components (no new data
    # fetched). Build NEW dicts rather than mutating in place — `data` may be the shared in-memory
    # cache entry returned by hot_filings_service, so mutating it would pollute the cache and race
    # across concurrent requests.
    enriched_filings = [
        {**filing, "pulse": compose_pulse(filing.get("buzz_components"), filing.get("buzz_score"))}
        for filing in data.get("filings", [])
    ]

    # last_updated is emitted as a 'Z'-suffixed UTC string by the service (iso_z); a bare UTC
    # isoformat without the 'Z' would make the browser's new Date() parse it as local time, skewing
    # the "Updated N ago" label. This stays as a defensive fallback for any value lacking the 'Z'.
    last_updated = data.get("last_updated")
    if isinstance(last_updated, str) and last_updated and not last_updated.endswith("Z"):
        last_updated += "Z"

    return {**data, "filings": enriched_filings, "last_updated": last_updated}


@router.post("/hot_filings/refresh", status_code=status.HTTP_202_ACCEPTED)
async def refresh_hot_filings(
    db: Session = Depends(get_db),
    admin_token: str | None = Header(None, alias="X-Admin-Token"),
):
    """Manually refresh the hot filings cache. Requires admin token if configured."""
    required_token = settings.HOT_FILINGS_REFRESH_TOKEN
    if required_token:
        if admin_token != required_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token")
    else:
        # If no token configured, block refresh to avoid accidental exposure
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Refresh token not configured")

    await hot_filings_service.get_hot_filings(db, force_refresh=True)
    return {"status": "refreshing"}
