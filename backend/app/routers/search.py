"""EDGAR full-text search endpoints."""

import logging
from dataclasses import asdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.integrations.sec_api import sec_full_text_search_client
from app.schemas.search import FullTextSearchHit, FullTextSearchResponse
from app.services.rate_limiter import RateLimiter, enforce_rate_limit
from app.services.sec_rate_limiter import SECRateLimitError

logger = logging.getLogger(__name__)

router = APIRouter()

# Unauthenticated + always a LIVE EDGAR full-text-search (EFTS) call: every request consumes
# the process-wide 10 req/s SEC budget. 20/min/IP comfortably covers a person searching;
# it exists to stop anonymous scripts/crawlers from monopolizing the EDGAR budget.
_fts_rate_limiter = RateLimiter(limit=20, window_seconds=60)


@router.get("/full-text", response_model=FullTextSearchResponse)
async def full_text_search(
    request: Request,
    q: str = Query(
        ...,
        min_length=1,
        max_length=400,
        description="Full-text query. Wrap exact phrases in double quotes; supports AND/OR/NOT.",
    ),
    forms: Optional[str] = Query(
        None,
        description="Comma-separated SEC form types to filter by, e.g. '10-K,10-Q,8-K'.",
    ),
    start_date: Optional[date] = Query(
        None,
        alias="startdt",
        description="Earliest filing date, YYYY-MM-DD (EDGAR indexes text from 2001 onward).",
    ),
    end_date: Optional[date] = Query(
        None,
        alias="enddt",
        description="Latest filing date, YYYY-MM-DD.",
    ),
    ciks: Optional[str] = Query(
        None,
        description="Comma-separated zero-padded CIKs to scope the search to specific filers.",
    ),
    from_offset: int = Query(
        0,
        alias="from",
        ge=0,
        le=9990,
        description="Pagination offset. EDGAR caps deep pagination near 10,000 results.",
    ),
):
    """Search the full text of SEC filings and their exhibits.

    Powered by EDGAR full-text search (EFTS). Useful for queries the structured
    APIs can't answer, e.g. every filing mentioning "going concern" or
    "material weakness".
    """
    enforce_rate_limit(
        request,
        _fts_rate_limiter,
        "full-text-search",
        error_detail="Too many search requests. Please retry in a minute.",
    )

    try:
        result = await sec_full_text_search_client.search(
            query=q,
            forms=forms,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            ciks=ciks,
            from_offset=from_offset,
        )
    except SECRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="SEC full-text search is rate-limited right now. Please retry shortly.",
        )
    except Exception as exc:  # network / upstream / parse failure
        logger.warning("EDGAR full-text search failed", exc_info=exc)
        raise HTTPException(
            status_code=502,
            detail="SEC full-text search is temporarily unavailable.",
        )

    return FullTextSearchResponse(
        query=result.query,
        total=result.total,
        count=len(result.hits),
        hits=[FullTextSearchHit(**asdict(hit)) for hit in result.hits],
    )
