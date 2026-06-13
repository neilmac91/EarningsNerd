import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company, Filing
# EdgarTools migration: Using new edgar module for SEC services
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.exceptions import EdgarError as SECEdgarServiceError
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Constants for filings endpoint configuration
SEC_REQUEST_TIMEOUT_SECONDS = 20.0  # Timeout for SEC EDGAR requests (within frontend's 30s limit)
CACHED_FILINGS_LIMIT = 20  # Maximum number of cached filings to return as fallback

router = APIRouter()


class CompanyInfo(BaseModel):
    id: int
    ticker: str
    name: str
    exchange: Optional[str] = None

class FilingResponse(BaseModel):
    id: Optional[int]
    filing_type: str
    filing_date: str
    report_date: Optional[str]
    accession_number: str
    document_url: str
    sec_url: str
    company: Optional[CompanyInfo] = None
    
    @classmethod
    def from_orm(cls, filing):
        """Convert Filing model to FilingResponse"""
        company_info = None
        if hasattr(filing, 'company') and filing.company:
            company_info = CompanyInfo(
                id=filing.company.id,
                ticker=filing.company.ticker,
                name=filing.company.name,
                exchange=filing.company.exchange
            )
        
        return cls(
            id=filing.id,
            filing_type=filing.filing_type,
            filing_date=filing.filing_date.isoformat() if filing.filing_date else None,
            report_date=filing.period_end_date.isoformat() if filing.period_end_date else None,
            accession_number=filing.accession_number,
            document_url=filing.document_url,
            sec_url=filing.sec_url,
            company=company_info
        )
    
    class Config:
        from_attributes = True

@router.get("/company/{ticker}", response_model=List[FilingResponse])
async def get_company_filings(
    ticker: str,
    filing_types: Optional[str] = Query(None, description="Comma-separated filing types (e.g., '10-K,10-Q')"),
    db: Session = Depends(get_db)
):
    """Get filings for a company.

    Falls back to cached database filings if SEC EDGAR is slow or unavailable.
    """
    ticker_upper = ticker.upper()
    company = db.query(Company).filter(Company.ticker == ticker_upper).first()

    if not company:
        # Try to fetch company from SEC and create it
        try:
            sec_results = await sec_edgar_service.search_company(ticker)
            if sec_results:
                sec_data = sec_results[0]
                company = Company(
                    cik=sec_data["cik"],
                    ticker=sec_data["ticker"],
                    name=sec_data["name"],
                    exchange=sec_data.get("exchange")
                )
                db.add(company)
                db.commit()
                db.refresh(company)
            else:
                raise HTTPException(status_code=404, detail="Company not found")
        except HTTPException:
            raise
        except SECEdgarServiceError as e:
            raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}") from e

    # Parse filing types
    types_list = ["10-K", "10-Q"]
    if filing_types:
        types_list = [t.strip() for t in filing_types.split(",")]

    # Helper to get cached filings from database
    def get_cached_filings() -> List[FilingResponse]:
        cached = db.query(Filing).filter(
            Filing.company_id == company.id,
            Filing.filing_type.in_(types_list)
        ).order_by(Filing.filing_date.desc()).limit(CACHED_FILINGS_LIMIT).all()
        return [FilingResponse.from_orm(f) for f in cached]

    try:
        # Try to fetch from SEC with a timeout to ensure we respond within frontend's limit
        sec_filings = await asyncio.wait_for(
            sec_edgar_service.get_filings(company.cik, types_list),
            timeout=SEC_REQUEST_TIMEOUT_SECONDS
        )

        filings = []
        new_filings = []  # Track newly added filings for batch refresh

        for sec_filing in sec_filings:
            # Validate required fields from SEC response before database operations
            sec_url = sec_filing.get("sec_url")
            document_url = sec_filing.get("document_url")

            # Skip filings with missing required URLs to prevent NOT NULL violations
            if not sec_url:
                logger.warning(
                    f"Skipping filing {sec_filing.get('accession_number')} - missing sec_url"
                )
                continue

            # Check if filing exists in database
            filing = db.query(Filing).filter(
                Filing.accession_number == sec_filing["accession_number"]
            ).first()

            if not filing:
                # Only create new filing if we have all required fields
                if not document_url:
                    logger.warning(
                        f"Skipping new filing {sec_filing.get('accession_number')} - missing document_url"
                    )
                    continue

                filing = Filing(
                    company_id=company.id,
                    accession_number=sec_filing["accession_number"],
                    filing_type=sec_filing["filing_type"],
                    filing_date=datetime.fromisoformat(sec_filing["filing_date"]),
                    period_end_date=datetime.fromisoformat(sec_filing["report_date"]) if sec_filing.get("report_date") else None,
                    document_url=document_url,
                    sec_url=sec_url
                )
                db.add(filing)
                new_filings.append(filing)
            else:
                # Update existing filing with new URL format if it's using old format
                # Only update if new values are valid (not None)
                if filing.sec_url and "cgi-bin/viewer" in filing.sec_url:
                    if sec_url and document_url:
                        filing.sec_url = sec_url
                        filing.document_url = document_url
                    else:
                        logger.warning(
                            f"Skipping URL update for filing {filing.accession_number} - "
                            f"new sec_url or document_url is None"
                        )

            filings.append(filing)

        # Batch commit: single transaction for all database changes
        if new_filings or db.dirty:
            db.commit()
            # Refresh new filings to get generated IDs
            for filing in new_filings:
                db.refresh(filing)

        # Convert to response models after commit
        return [FilingResponse.from_orm(f) for f in filings]

    except asyncio.TimeoutError:
        # SEC EDGAR is slow, fall back to cached data
        logger.warning(f"SEC EDGAR timeout for {ticker_upper}, returning cached filings")
        db.rollback()  # Ensure clean session state
        cached = get_cached_filings()
        if cached:
            return cached
        # No cached data available
        raise HTTPException(
            status_code=503,
            detail="SEC EDGAR is slow to respond and no cached data is available. Please retry in a moment."
        )
    except SECEdgarServiceError as e:
        # SEC EDGAR error, try to return cached data
        logger.warning(f"SEC EDGAR error for {ticker_upper}: {e}, attempting to return cached filings")
        db.rollback()  # Ensure clean session state
        cached = get_cached_filings()
        if cached:
            return cached
        raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
    except Exception as e:
        logger.exception(f"Unexpected error fetching filings for {ticker_upper}")
        # Rollback any pending transaction to recover session state
        db.rollback()
        # Try to return cached data on any error
        cached = get_cached_filings()
        if cached:
            logger.info(f"Returning {len(cached)} cached filings for {ticker_upper} after error")
            return cached
        raise HTTPException(status_code=500, detail=f"Error fetching filings: {str(e)}") from e

@router.get("/{filing_id}", response_model=FilingResponse)
async def get_filing(filing_id: int, db: Session = Depends(get_db)):
    """Get a specific filing"""
    from sqlalchemy.orm import joinedload
    filing = db.query(Filing).options(joinedload(Filing.company)).filter(Filing.id == filing_id).first()
    
    if not filing:
        raise HTTPException(status_code=404, detail="Filing not found")
    
    return FilingResponse.from_orm(filing)

@router.get("/recent/latest", response_model=List[FilingResponse])
async def get_recent_filings(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get recent filings across all companies"""
    from sqlalchemy import desc
    from sqlalchemy.orm import joinedload
    # Use joinedload to eagerly load company relationship, avoiding N+1 queries
    filings = db.query(Filing).options(joinedload(Filing.company)).order_by(desc(Filing.filing_date)).limit(limit).all()

    return [FilingResponse.from_orm(filing) for filing in filings]


