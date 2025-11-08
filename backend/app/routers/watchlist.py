from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models import Watchlist, Company, User, Filing, Summary
from app.routers.auth import get_current_user
from app.routers.summaries import get_generation_progress_snapshot

router = APIRouter()

class WatchlistResponse(BaseModel):
    id: int
    company_id: int
    created_at: str
    company: dict
    
    class Config:
        from_attributes = True

@router.post("/{ticker}")
async def add_to_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add company to watchlist"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if already in watchlist
    existing = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.company_id == company.id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Company already in watchlist")
    
    watchlist_item = Watchlist(
        user_id=current_user.id,
        company_id=company.id
    )
    db.add(watchlist_item)
    db.commit()
    db.refresh(watchlist_item)
    
    return {
        "id": watchlist_item.id,
        "company_id": watchlist_item.company_id,
        "created_at": watchlist_item.created_at.isoformat() if watchlist_item.created_at else None,
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "name": company.name,
        }
    }

@router.get("/", response_model=List[WatchlistResponse])
async def get_watchlist(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's watchlist"""
    watchlist_items = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id
    ).order_by(desc(Watchlist.created_at)).all()
    
    result = []
    for item in watchlist_items:
        company = db.query(Company).filter(Company.id == item.company_id).first()
        if company:
            result.append({
                "id": item.id,
                "company_id": item.company_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "company": {
                    "id": company.id,
                    "ticker": company.ticker,
                    "name": company.name,
                }
            })
    
    return result

@router.delete("/{ticker}")
async def remove_from_watchlist(
    ticker: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove company from watchlist"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    watchlist_item = db.query(Watchlist).filter(
        Watchlist.user_id == current_user.id,
        Watchlist.company_id == company.id
    ).first()
    
    if not watchlist_item:
        raise HTTPException(status_code=404, detail="Company not in watchlist")
    
    db.delete(watchlist_item)
    db.commit()
    
    return {"status": "success"}


class WatchlistCompany(BaseModel):
    id: int
    ticker: str
    name: str


class WatchlistFilingSnapshot(BaseModel):
    id: int
    filing_type: str
    filing_date: Optional[str]
    period_end_date: Optional[str]
    summary_id: Optional[int]
    summary_status: str
    summary_created_at: Optional[str]
    summary_updated_at: Optional[str]
    needs_regeneration: bool
    progress: Optional[Dict[str, Any]] = None


class WatchlistInsightResponse(BaseModel):
    company: WatchlistCompany
    latest_filing: Optional[WatchlistFilingSnapshot]
    total_filings: int


@router.get("/insights", response_model=List[WatchlistInsightResponse])
async def get_watchlist_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return enriched status information for the user's watchlist."""
    watchlist_items = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id)
        .order_by(desc(Watchlist.created_at))
        .all()
    )

    insights: List[WatchlistInsightResponse] = []

    for item in watchlist_items:
        company = db.query(Company).filter(Company.id == item.company_id).first()
        if not company:
            continue

        filing_query = (
            db.query(Filing)
            .filter(Filing.company_id == company.id)
            .order_by(desc(Filing.filing_date))
        )
        latest_filing: Optional[Filing] = filing_query.first()
        total_filings = filing_query.count()

        filing_snapshot: Optional[WatchlistFilingSnapshot] = None

        if latest_filing:
            summary: Optional[Summary] = (
                db.query(Summary)
                .filter(Summary.filing_id == latest_filing.id)
                .order_by(desc(Summary.updated_at), desc(Summary.created_at))
                .first()
            )

            progress_snapshot = get_generation_progress_snapshot(latest_filing.id)

            summary_status = "missing"
            needs_regeneration = True
            summary_id: Optional[int] = None
            summary_created_at: Optional[str] = None
            summary_updated_at: Optional[str] = None

            if summary:
                summary_id = summary.id
                summary_created_at = summary.created_at.isoformat() if summary.created_at else None
                summary_updated_at = summary.updated_at.isoformat() if summary.updated_at else None

                overview = (summary.business_overview or "").lower()
                placeholder_tokens = [
                    "generating summary",
                    "summary temporarily unavailable",
                    "requires openai api key"
                ]
                has_placeholder = any(token in overview for token in placeholder_tokens)

                if has_placeholder:
                    summary_status = "placeholder"
                    needs_regeneration = True
                else:
                    summary_status = "ready"
                    needs_regeneration = False
            elif progress_snapshot:
                stage = progress_snapshot.get("stage", "generating")
                if stage == "error":
                    summary_status = "error"
                    needs_regeneration = True
                else:
                    summary_status = f"generating:{stage}"
                    needs_regeneration = False
            else:
                summary_status = "missing"
                needs_regeneration = True

            filing_snapshot = WatchlistFilingSnapshot(
                id=latest_filing.id,
                filing_type=latest_filing.filing_type,
                filing_date=latest_filing.filing_date.isoformat() if latest_filing.filing_date else None,
                period_end_date=latest_filing.period_end_date.isoformat() if latest_filing.period_end_date else None,
                summary_id=summary_id,
                summary_status=summary_status,
                summary_created_at=summary_created_at,
                summary_updated_at=summary_updated_at,
                needs_regeneration=needs_regeneration,
                progress=progress_snapshot,
            )

        insights.append(
            WatchlistInsightResponse(
                company=WatchlistCompany(
                    id=company.id,
                    ticker=company.ticker,
                    name=company.name,
                ),
                latest_filing=filing_snapshot,
                total_filings=total_filings,
            )
        )

    return insights

