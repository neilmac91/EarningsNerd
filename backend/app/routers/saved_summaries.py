from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.services import saved_summary_service
from app.services.saved_summary_service import SavedSummaryRelatedRowMissing

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
    try:
        saved = saved_summary_service.save_summary(
            db, user_id=current_user.id, summary_id=data.summary_id, notes=data.notes
        )
    except SavedSummaryRelatedRowMissing as exc:
        raise HTTPException(status_code=404, detail=exc.detail)
    if saved is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return saved

@router.get("/", response_model=List[SavedSummaryResponse])
async def get_saved_summaries(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all saved summaries for current user"""
    try:
        return saved_summary_service.list_saved_summaries(db, current_user.id)
    except SavedSummaryRelatedRowMissing as exc:
        raise HTTPException(status_code=404, detail=exc.detail)

class SavedSummaryStatus(BaseModel):
    is_saved: bool


@router.get("/status/{summary_id}", response_model=SavedSummaryStatus)
def get_saved_summary_status(
    summary_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check one summary without loading saved-library content or other users' bookmarks."""
    is_saved = saved_summary_service.saved_summary_status(
        db, user_id=current_user.id, summary_id=summary_id
    )
    if is_saved is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return {"is_saved": is_saved}


@router.delete("/{saved_summary_id}")
async def delete_saved_summary(
    saved_summary_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a saved summary"""
    if not saved_summary_service.delete_saved_summary(
        db, user_id=current_user.id, saved_summary_id=saved_summary_id
    ):
        raise HTTPException(status_code=404, detail="Saved summary not found")

    return {"status": "success"}

@router.put("/{saved_summary_id}")
async def update_saved_summary(
    saved_summary_id: int,
    notes: Optional[str] = Query(None, description="Optional notes to add to the saved summary"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notes for a saved summary"""
    try:
        updated = saved_summary_service.update_saved_summary_notes(
            db, user_id=current_user.id, saved_summary_id=saved_summary_id, notes=notes
        )
    except SavedSummaryRelatedRowMissing as exc:
        raise HTTPException(status_code=404, detail=exc.detail)
    if updated is None:
        raise HTTPException(status_code=404, detail="Saved summary not found")
    return updated
