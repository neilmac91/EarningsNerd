"""Insider-activity endpoint (P4, SEC Form 4)."""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.schemas.insiders import InsiderActivityResponse
from app.services import insider_service
from app.services.edgar.exceptions import CompanyNotFoundError, EdgarError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{ticker}/insiders", response_model=InsiderActivityResponse)
async def get_company_insiders(
    ticker: str,
    window_days: int = Query(
        90,
        ge=1,
        le=730,
        description="Trailing window (days) for the buy/sell aggregation.",
    ),
) -> InsiderActivityResponse:
    """Summarize a company's recent insider (Form 4) open-market trades.

    Live SEC EDGAR read (no DB): resolves the ticker, pulls its most recent
    Form 4 filings, and returns a buy/sell signal — with a Rule 10b5-1 split —
    plus the most recent individual transactions.
    """
    try:
        return await insider_service.get_insider_activity(ticker, window_days=window_days)
    except CompanyNotFoundError:
        raise HTTPException(status_code=404, detail="Company not found")
    except EdgarError as exc:
        logger.warning("Insider activity fetch failed for %s: %s", ticker, exc)
        raise HTTPException(status_code=502, detail="Could not retrieve insider data")
