"""Multi-year fundamentals timeline endpoint."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.schemas.fundamentals import FundamentalsTimelineResponse
from app.services.edgar import CompanyNotFoundError
from app.services.fundamentals_service import get_fundamentals_timeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{ticker}/fundamentals", response_model=FundamentalsTimelineResponse)
async def company_fundamentals(ticker: str):
    """Return an annual (fiscal-year) time series of headline financial metrics.

    Backed by the SEC company-facts API. Covers revenue, gross/operating income,
    net income, operating cash flow, diluted EPS, total assets, shareholders'
    equity, and derived gross/operating/net margins — up to ~12 years.
    """

    try:
        timeline = await get_fundamentals_timeline(ticker)
    except CompanyNotFoundError:
        raise HTTPException(status_code=404, detail=f"No SEC company found for '{ticker}'.")
    except Exception as exc:  # upstream / parse failure
        logger.warning("Fundamentals timeline failed for %s", ticker, exc_info=exc)
        raise HTTPException(status_code=502, detail="Fundamentals data is temporarily unavailable.")

    return FundamentalsTimelineResponse(**asdict(timeline))
