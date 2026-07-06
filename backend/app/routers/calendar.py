"""Public earnings-calendar endpoint (strategy §3.7).

`GET /api/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD` serves the anticipated-earnings calendar straight
from Postgres (`earnings_events`) — no provider call on the render path. Dates are America/New_York
calendar days; the frontend treats them as plain strings. Public (no auth): it's a discovery surface.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import earnings_calendar_service, index_membership_service
from app.services.index_membership_service import UniverseLabel

router = APIRouter()

# Bound the window so a pathological range can't scan the whole table.
_MAX_RANGE_DAYS = 62


class CalendarEventOut(BaseModel):
    ticker: str
    company_name: str
    event_date: Optional[str]
    event_time: Optional[str]
    status: str
    confidence: str
    eps_estimate: Optional[float]
    eps_actual: Optional[float]
    anticipation_score: float


class CalendarResponse(BaseModel):
    events: List[CalendarEventOut]
    # Which universe these events were filtered to: "sp500_nasdaq100" when the index filter is
    # active, else "all". A Literal so Pydantic enforces it and the OpenAPI schema documents the enum.
    universe: UniverseLabel


@router.get("", response_model=CalendarResponse)
@router.get("/", response_model=CalendarResponse)
def get_calendar(
    from_: date = Query(..., alias="from", description="Start date (inclusive), YYYY-MM-DD"),
    to: date = Query(..., description="End date (inclusive), YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Earnings events in [from, to], soonest first then most-anticipated. Empty list, never an
    error, when nothing is scheduled — the frontend renders its own empty state."""
    if to < from_:
        raise HTTPException(status_code=400, detail="`to` must be on or after `from`.")
    if (to - from_) > timedelta(days=_MAX_RANGE_DAYS):
        raise HTTPException(status_code=400, detail=f"Range too wide (max {_MAX_RANGE_DAYS} days).")
    return {
        "events": earnings_calendar_service.events_in_range(db, from_, to),
        "universe": index_membership_service.active_universe_label(),
    }
