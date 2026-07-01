from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.reporting_this_week_service import reporting_this_week_service

router = APIRouter()


class ReportingCompanyOut(BaseModel):
    ticker: str
    name: str
    earnings_date: str
    time: Optional[str] = None


class ReportingThisWeekResponse(BaseModel):
    companies: List[ReportingCompanyOut]
    week_start: str
    week_end: str
    status: str
    timestamp: str


@router.get("/reporting_this_week", response_model=ReportingThisWeekResponse)
async def get_reporting_this_week(
    limit: int = Query(16, ge=1, le=16),
):
    """Curated large-cap companies reporting earnings in the current US market week
    (Mon-Fri, America/New_York). Returns an empty `companies` list (never an error) on
    weekends, holidays, a sparse week, or upstream failure — the frontend omits the
    homepage section entirely when `companies` is empty."""
    return await reporting_this_week_service.get_reporting_this_week(limit=limit)
