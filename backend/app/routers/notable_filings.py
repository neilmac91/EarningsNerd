from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import filing_list_service
from app.services.notable_filings_service import MAX_FILINGS, notable_filings_service

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
    limit: int = Query(MAX_FILINGS, ge=1, le=12),
    db: Session = Depends(get_db),
):
    """Notable SEC filings from the past week under D-046's rule: 10-K and 10-Q filings only, from
    companies that hold a summary the filing page shows, newest first, one per company, at most six.
    A `limit` above six is served six rather than refused, so an existing caller keeps its answer.

    Served ONLY from the `notable_filings` table (populated by the scheduled EDGAR scan job);
    returns an empty `filings` list (never an error) while `NOTABLE_FILINGS_ENABLED` is off,
    when fewer than 3 distinct companies qualify, or on any upstream failure — the homepage
    section omits itself when `filings` is empty.

    The read and the session release are one unit off the event loop, so the pooled connection is
    back before the route yields to the dependency's finalizer
    (``lessons/ops-release-cached-filing-reads-before-yield.md``)."""
    def notable_for_reader() -> Dict[str, Any]:
        try:
            return notable_filings_service.get_notable_filings(db, limit=limit)
        finally:
            filing_list_service.release_request_session(db)

    return await run_in_threadpool(notable_for_reader)
