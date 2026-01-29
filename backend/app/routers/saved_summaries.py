from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import SavedSummary, Summary, Filing, Company, User
from app.routers.auth import get_current_user

router = APIRouter()

class SavedSummaryCreate(BaseModel):
    summary_id: int
    notes: Optional[str] = None

class SavedSummaryResponse(BaseModel):
    id: int
    summary_id: int
    notes: Optional[str]
    created_at: str
    summary: dict
    filing: dict
    company: dict
    
    class Config:
        from_attributes = True

@router.post("/", response_model=SavedSummaryResponse)
async def save_summary(
    data: SavedSummaryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a summary to user's account"""
    # Check if summary exists and eagerly load related data to avoid N+1 queries
    row = (
        db.query(Summary, Filing, Company)
        .join(Filing, Summary.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(Summary.id == data.summary_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Summary not found")
    summary, filing, company = row

    # Check if already saved
    existing = db.query(SavedSummary).filter(
        SavedSummary.user_id == current_user.id,
        SavedSummary.summary_id == data.summary_id
    ).first()

    if existing:
        # Update notes if provided
        if data.notes is not None:
            existing.notes = data.notes
            db.commit()
            db.refresh(existing)
        return _format_saved_summary_response(
            existing, db, summary=summary, filing=filing, company=company
        )

    # Create new saved summary
    saved_summary = SavedSummary(
        user_id=current_user.id,
        summary_id=data.summary_id,
        notes=data.notes
    )
    db.add(saved_summary)
    db.commit()
    db.refresh(saved_summary)

    return _format_saved_summary_response(
        saved_summary, db, summary=summary, filing=filing, company=company
    )

@router.get("/", response_model=List[SavedSummaryResponse])
async def get_saved_summaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all saved summaries for current user"""
    rows = (
        db.query(SavedSummary, Summary, Filing, Company)
        .join(Summary, SavedSummary.summary_id == Summary.id)
        .join(Filing, Summary.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(SavedSummary.user_id == current_user.id)
        .order_by(desc(SavedSummary.created_at))
        .all()
    )
    
    return [
        _format_saved_summary_response(
            saved_summary,
            db,
            summary=summary,
            filing=filing,
            company=company,
        )
        for saved_summary, summary, filing, company in rows
    ]

@router.delete("/{saved_summary_id}")
async def delete_saved_summary(
    saved_summary_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a saved summary"""
    saved_summary = db.query(SavedSummary).filter(
        SavedSummary.id == saved_summary_id,
        SavedSummary.user_id == current_user.id
    ).first()
    
    if not saved_summary:
        raise HTTPException(status_code=404, detail="Saved summary not found")
    
    db.delete(saved_summary)
    db.commit()
    
    return {"status": "success"}

@router.put("/{saved_summary_id}")
async def update_saved_summary(
    saved_summary_id: int,
    notes: Optional[str] = Query(None, description="Optional notes to add to the saved summary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notes for a saved summary"""
    # Single query with joins to avoid N+1
    row = (
        db.query(SavedSummary, Summary, Filing, Company)
        .join(Summary, SavedSummary.summary_id == Summary.id)
        .join(Filing, Summary.filing_id == Filing.id)
        .join(Company, Filing.company_id == Company.id)
        .filter(
            SavedSummary.id == saved_summary_id,
            SavedSummary.user_id == current_user.id
        )
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Saved summary not found")
    saved_summary, summary, filing, company = row

    if notes is not None:
        saved_summary.notes = notes
        db.commit()
        db.refresh(saved_summary)

    return _format_saved_summary_response(
        saved_summary, db, summary=summary, filing=filing, company=company
    )

def _format_saved_summary_response(
    saved_summary: SavedSummary,
    db: Session,
    *,
    summary: Optional[Summary] = None,
    filing: Optional[Filing] = None,
    company: Optional[Company] = None,
) -> dict:
    """Format saved summary response with related data"""
    summary = summary or db.query(Summary).filter(Summary.id == saved_summary.summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    
    filing = filing or db.query(Filing).filter(Filing.id == summary.filing_id).first()
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    company = company or db.query(Company).filter(Company.id == filing.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return {
        "id": saved_summary.id,
        "summary_id": saved_summary.summary_id,
        "notes": saved_summary.notes,
        "created_at": saved_summary.created_at.isoformat() if saved_summary.created_at else None,
        "summary": {
            "id": summary.id,
            "filing_id": summary.filing_id,
            "business_overview": summary.business_overview,
        },
        "filing": {
            "id": filing.id,
            "filing_type": filing.filing_type,
            "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
            "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
        },
        "company": {
            "id": company.id,
            "ticker": company.ticker,
            "name": company.name,
        }
    }

