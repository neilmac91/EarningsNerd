from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.notable_filings_service import notable_filings_service

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
    db: Session = Depends(get_db),
):
    """Market-wide notable SEC filings from the past week, ranked and deduped one per company.

    Served ONLY from the `notable_filings` table (populated by the scheduled EDGAR scan job);
    returns an empty `filings` list (never an error) while `NOTABLE_FILINGS_ENABLED` is off,
    when fewer than 3 distinct companies qualify, or on any upstream failure — the homepage
    section omits itself when `filings` is empty."""
    return await notable_filings_service.get_notable_filings(db, limit=limit)
