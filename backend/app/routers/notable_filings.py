from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.notable_filings_service import (
    homepage_notable_filings_service,
    notable_filings_service,
)

router = APIRouter()


class NotableFilingOut(BaseModel):
    ticker: str
    company_name: str
    form: str
    reason: str  # slug (analytics property)
    reason_label: str  # display chip text
    filed_date: str  # YYYY-MM-DD
    sec_url: str


class NotableFilingsResponse(BaseModel):
    filings: List[NotableFilingOut]
    status: str  # "ok" | "empty"
    timestamp: str


@router.get("/notable_filings", response_model=NotableFilingsResponse)
async def get_notable_filings(
    limit: int = Query(8, ge=1, le=12),
    homepage_only: bool = Query(False, description="Only 10-K/10-Q filings in the committed index universe"),
    db: Session = Depends(get_db),
):
    """Market-wide notable SEC filings from the past week, ranked and deduped one per company.

    Served ONLY from the `notable_filings` table (populated by the scheduled EDGAR scan job);
    returns an empty `filings` list (never an error) while `NOTABLE_FILINGS_ENABLED` is off,
    when fewer than 3 distinct companies qualify, or on any upstream failure — the homepage
    section omits itself when `filings` is empty. `homepage_only` selects the committed index
    universe's 10-K/10-Q filings before ranking; the default feed retains all supported forms."""
    if homepage_only:
        return await homepage_notable_filings_service.get_notable_filings(db, limit=limit)
    return await notable_filings_service.get_notable_filings(db, limit=limit)
