"""Personalised dashboard endpoints (Phase 3): the "what changed" feed + earnings calendar."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.services import calendar_service, dashboard_feed_service

router = APIRouter()


class WhatChangedItem(BaseModel):
    metric: str
    label: str
    direction: str           # up | down | flat
    pct: Optional[float]
    current: float
    prior: Optional[float]


class WhatChanged(BaseModel):
    headline: str
    items: List[WhatChangedItem]
    data_quality: str        # ok | partial


class FeedCompany(BaseModel):
    id: int
    ticker: str
    name: str


class FeedItem(BaseModel):
    filing_id: int
    accession_number: Optional[str]
    company: FeedCompany
    filing_type: str
    filing_date: Optional[str]
    period_end_date: Optional[str]
    summary_id: Optional[int]
    summary_status: str
    what_changed: Optional[WhatChanged]


class FeedResponse(BaseModel):
    items: List[FeedItem]


class CalendarEvent(BaseModel):
    ticker: str
    company_name: str
    earnings_date: Optional[str]
    time: Optional[str]
    eps_estimated: Optional[float]
    revenue_estimated: Optional[float]


class CalendarResponse(BaseModel):
    events: List[CalendarEvent]


@router.get("/feed", response_model=FeedResponse)
async def get_dashboard_feed(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Each watched company's newest 10-K/10-Q (FPI annual forms behind the flag) with a
    deterministic "what changed" line — one item per company, newest company first. ``limit`` caps
    the number of companies (not filings).

    DB-only (no live EDGAR on render); cheap enough to serve uncached. Returns an empty list for
    users with no watched companies (the UI renders a guided empty state)."""
    return {"items": dashboard_feed_service.compose_feed(db, current_user.id, limit=limit)}


@router.get("/calendar/upcoming", response_model=CalendarResponse)
async def get_upcoming_calendar(
    days: int = Query(14, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upcoming earnings dates for the user's watched companies (empty when FMP is unconfigured)."""
    events = await calendar_service.upcoming_for_user(db, current_user.id, days_ahead=days)
    return {"events": events}
