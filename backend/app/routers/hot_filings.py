from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.hot_filings import hot_filings_service

router = APIRouter()


@router.get("/hot_filings")
async def get_hot_filings(
    limit: int = Query(10, ge=1, le=20),
    force_refresh: bool = Query(False, description="Force regeneration of cached data"),
    db: Session = Depends(get_db),
):
    """Return the hottest recent filings ranked by buzz score."""
    data = await hot_filings_service.get_hot_filings(db, limit=limit, force_refresh=force_refresh)
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
    return data


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
