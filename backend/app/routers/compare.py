from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models import Summary, Filing, Company, User
from app.routers.auth import get_current_user

router = APIRouter()

class ComparisonRequest(BaseModel):
    filing_ids: List[int]

class ComparisonResponse(BaseModel):
    filings: List[dict]
    comparison: dict

@router.post("/", response_model=ComparisonResponse)
async def compare_filings(
    request: ComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare multiple filings side-by-side (Pro feature)"""
    # Check if user is Pro
    if not current_user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Multi-year comparison is a Pro feature. Upgrade to Pro to access this feature."
        )
    
    if len(request.filing_ids) < 2 or len(request.filing_ids) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must compare between 2 and 5 filings"
        )
    
    # Fetch summaries for all filings
    summaries = []
    filings_data = []
    
    for filing_id in request.filing_ids:
        filing = db.query(Filing).filter(Filing.id == filing_id).first()
        if not filing:
            raise HTTPException(status_code=404, detail=f"Filing {filing_id} not found")
        
        summary = db.query(Summary).filter(Summary.filing_id == filing_id).first()
        if not summary:
            raise HTTPException(
                status_code=404, 
                detail=f"Summary for filing {filing_id} not found. Please generate summaries first."
            )
        
        company = db.query(Company).filter(Company.id == filing.company_id).first()
        
        filings_data.append({
            "id": filing.id,
            "filing_type": filing.filing_type,
            "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
            "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
            "company": {
                "ticker": company.ticker,
                "name": company.name,
            },
        })
        
        summaries.append({
            "filing_id": filing.id,
            "summary": summary,
        })
    
    # Extract financial metrics for comparison
    financial_metrics = []
    for item in summaries:
        raw_summary = item["summary"].raw_summary or {}
        sections = raw_summary.get("sections", {})
        financial_highlights = sections.get("financial_highlights", {})
        
        if financial_highlights.get("table"):
            financial_metrics.append({
                "filing_id": item["filing_id"],
                "metrics": financial_highlights["table"],
            })
    
    # Extract risk factors for comparison
    risk_factors_list = []
    for item in summaries:
        raw_summary = item["summary"].raw_summary or {}
        sections = raw_summary.get("sections", {})
        risks = sections.get("risk_factors", [])
        
        risk_factors_list.append({
            "filing_id": item["filing_id"],
            "risks": risks,
        })
    
    # Generate comparison analysis
    comparison = {
        "financial_metrics": financial_metrics,
        "risk_factors": risk_factors_list,
        "summary_count": len(summaries),
    }
    
    return ComparisonResponse(
        filings=filings_data,
        comparison=comparison
    )

