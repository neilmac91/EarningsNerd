"""Insider-activity endpoint (P4, SEC Form 4)."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.schemas.insiders import InsiderActivityResponse
from app.services import insider_service
from app.services.edgar.circuit_breaker import CircuitOpenError
from app.services.edgar.exceptions import CompanyNotFoundError, EdgarError
from app.services.rate_limiter import RateLimiter, enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

# Unauthenticated + always a LIVE SEC EDGAR read (no DB cache): every request consumes the
# process-wide 10 req/s SEC budget, so an anonymous burst here starves every other EDGAR
# consumer. 30/min/IP is far above any legitimate single-user browsing rate.
_insiders_rate_limiter = RateLimiter(limit=30, window_seconds=60)


@router.get("/{ticker}/insiders", response_model=InsiderActivityResponse)
async def get_company_insiders(
    request: Request,
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
    enforce_rate_limit(
        request,
        _insiders_rate_limiter,
        "insiders",
        error_detail="Too many insider-activity requests. Please retry in a minute.",
    )
    try:
        return await insider_service.get_insider_activity(ticker, window_days=window_days)
    except CompanyNotFoundError:
        raise HTTPException(status_code=404, detail="Company not found")
    except CircuitOpenError:
        logger.warning("Insider activity unavailable (SEC circuit open) for %s", ticker)
        raise HTTPException(status_code=503, detail="Insider data temporarily unavailable")
    except EdgarError as exc:
        logger.warning("Insider activity fetch failed for %s: %s", ticker, exc)
        raise HTTPException(status_code=502, detail="Could not retrieve insider data")
