from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.models import Watchlist, Company, User
from app.routers.auth import get_current_user

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

