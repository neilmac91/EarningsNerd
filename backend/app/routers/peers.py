"""Cross-company peer comparison endpoint (P3/F3)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.peers import PeerComparisonResponse
from app.services import peers_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{ticker}/peers", response_model=PeerComparisonResponse)
async def get_company_peers(
    ticker: str,
    metric: str = Query(
        "revenue",
        description="Standardized concept to compare on, e.g. 'revenue', 'net_income', 'net_margin'.",
    ),
    db: Session = Depends(get_db),
) -> PeerComparisonResponse:
    """Rank a company against same-SIC peers on one metric, from the financial_fact table.

    A single indexed read (no live SEC calls). Coverage grows with the facts backfill;
    the subject is always returned, even before peers/facts exist.
    """
    data = peers_service.get_peers(db, ticker, metric)
    if data is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return data
