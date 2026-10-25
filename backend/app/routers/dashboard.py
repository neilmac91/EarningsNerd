"""Personalised dashboard endpoints (Phase 3): the "what changed" feed + earnings calendar."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.services import calendar_service, dashboard_feed_service, filing_list_service
from app.services.filing_section_service import section_changes_access

router = APIRouter()


class WhatChangedItem(BaseModel):
    metric: str
    label: str
    direction: str           # up | down | flat
    pct: Optional[float]
    current: float
    prior: Optional[float]
    display: Optional[str]   # metric_delta_service's one display string ('+6.4%'); None when incomputable
    tone: str                # gain | loss | flat: the chip's colour (costs that rose are a loss)


class WhatChanged(BaseModel):
    headline: str
    items: List[WhatChangedItem]
    data_quality: str        # ok | partial


class WordingReviewProgress(BaseModel):
    labeled: int
    completed_at: Optional[str]


class WordingChanges(BaseModel):
    """The Item 1A wording-change counts of the filing's cached comparison (behind
    ENABLE_SECTION_CHANGES), with the viewer's review progress when they get the full list."""
    items_total: int
    has_changes: bool
    reference_only: bool
    prior_reference_only: bool
    review: Optional[WordingReviewProgress]


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
    wording_changes: Optional[WordingChanges] = None


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
    def feed_for_viewer():
        # Sync SQLAlchemy off the event loop, the viewer's access included: resolving it reads
        # the subscription row (a lazy load the auth dependency does not make); the feed is a
        # handful of queries plus, for a Pro viewer, the cached diffs their review progress is
        # reconciled against. The unit releases the session before the route returns
        # (lessons/ops-release-cached-filing-reads-before-yield.md).
        try:
            access = section_changes_access(current_user)
            return dashboard_feed_service.compose_feed(db, current_user.id, limit=limit, section_access=access)
        finally:
            filing_list_service.release_request_session(db)

    items = await run_in_threadpool(feed_for_viewer)
    return {"items": items}


@router.get("/calendar/upcoming", response_model=CalendarResponse)
async def get_upcoming_calendar(
    days: int = Query(14, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upcoming earnings dates for the user's watched companies (empty until earnings_events is seeded)."""
    def events_for_viewer():
        # The reads and the release, one unit off the event loop, as the feed's
        # (lessons/ops-release-cached-filing-reads-before-yield.md).
        try:
            return calendar_service.upcoming_for_user(db, current_user.id, days_ahead=days)
        finally:
            filing_list_service.release_request_session(db)

    events = await run_in_threadpool(events_for_viewer)
    return {"events": events}
