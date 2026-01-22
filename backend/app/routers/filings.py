from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
from app.database import get_db
from app.models import Company, Filing, FilingContentCache
from app.services.sec_edgar import sec_edgar_service, SECEdgarServiceError
from app.services.sec_client import (
    sec_client,
    CompanyNotFoundError,
    FilingNotFoundError,
    FilingParseError,
)
from app.services.sec_rate_limiter import SECRateLimitError
from app.schemas import (
    FilingMarkdownResponse,
    FilingMetadata,
    FilingListItem,
    FilingListResponse,
)
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _determine_fiscal_period(filing: dict) -> str:
    """Determine fiscal period from filing metadata"""
    report_date = filing.get("report_date", "")
    if not report_date:
        return ""

    try:
        parts = report_date.split("-")
        if len(parts) != 3:
            return ""

        year = parts[0]
        month = int(parts[1])

        if month <= 3:
            quarter = "Q1"
        elif month <= 6:
            quarter = "Q2"
        elif month <= 9:
            quarter = "Q3"
        else:
            quarter = "Q4"

        return f"{quarter} {year}"
    except (ValueError, IndexError):
        return ""

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
    """Get filings for a company"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    
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
    
    try:
        # Fetch from SEC
        sec_filings = await sec_edgar_service.get_filings(company.cik, types_list)
        
        filings = []
        for sec_filing in sec_filings:
            # Check if filing exists in database
            filing = db.query(Filing).filter(
                Filing.accession_number == sec_filing["accession_number"]
            ).first()
            
            if not filing:
                filing = Filing(
                    company_id=company.id,
                    accession_number=sec_filing["accession_number"],
                    filing_type=sec_filing["filing_type"],
                    filing_date=datetime.fromisoformat(sec_filing["filing_date"]),
                    period_end_date=datetime.fromisoformat(sec_filing["report_date"]) if sec_filing.get("report_date") else None,
                    document_url=sec_filing["document_url"],
                    sec_url=sec_filing["sec_url"]
                )
                db.add(filing)
                db.commit()
                db.refresh(filing)
            else:
                # Update existing filing with new URL format if it's using old format
                if filing.sec_url and "cgi-bin/viewer" in filing.sec_url:
                    filing.sec_url = sec_filing["sec_url"]
                    filing.document_url = sec_filing["document_url"]
                    db.commit()
                    db.refresh(filing)
            
            # Convert to response model
            filings.append(FilingResponse.from_orm(filing))
        
        return filings
    except SECEdgarServiceError as e:
        raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
    except Exception as e:
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
    filings = db.query(Filing).join(Company).order_by(desc(Filing.filing_date)).limit(limit).all()

    return [FilingResponse.from_orm(filing) for filing in filings]


@router.get("/{ticker}/10q/markdown", response_model=FilingMarkdownResponse)
async def get_10q_markdown(
    ticker: str,
    force_refresh: bool = Query(False, description="Force refresh even if cached"),
    db: Session = Depends(get_db)
):
    """
    Get the latest 10-Q filing as clean, AI-ready Markdown.

    This endpoint fetches the most recent 10-Q filing for a company,
    parses it into a semantic structure, and converts it to clean
    Markdown optimized for LLM consumption.

    Results are cached in the database. Use force_refresh=true to bypass cache.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")
        force_refresh: Bypass cache and fetch fresh data

    Returns:
        FilingMarkdownResponse with:
        - filing_date: When the filing was submitted
        - accession_number: SEC accession number
        - markdown_content: Clean, structured Markdown
        - metadata: Additional filing information

    Raises:
        404: Company or filing not found
        503: SEC EDGAR unavailable or rate limited
        500: Parse error or other server error
    """
    ticker_upper = ticker.upper().strip()

    try:
        # Get filing metadata first to check cache
        filing_metadata = await sec_client.get_latest_10q(ticker_upper)
        company_info = await sec_client.get_company_info(ticker_upper)
        accession_number = filing_metadata.get("accession_number", "")

        # Check cache if not forcing refresh
        if not force_refresh:
            # Look up filing in database
            filing_record = db.query(Filing).filter(
                Filing.accession_number == accession_number
            ).first()

            if filing_record and filing_record.content_cache:
                cache = filing_record.content_cache
                if cache.markdown_content and cache.markdown_sections:
                    logger.info(f"Returning cached markdown for {ticker_upper}")
                    return FilingMarkdownResponse(
                        filing_date=filing_metadata.get("filing_date", ""),
                        accession_number=accession_number,
                        markdown_content=cache.markdown_content,
                        metadata=FilingMetadata(
                            ticker=company_info.get("ticker", ticker_upper),
                            company_name=company_info.get("name", ""),
                            filing_type=filing_metadata.get("filing_type", "10-Q"),
                            fiscal_period=_determine_fiscal_period(filing_metadata),
                            sections_extracted=cache.markdown_sections or [],
                        ),
                    )

        # Generate fresh markdown
        result = await sec_client.parse_filing_to_markdown(
            ticker_upper,
            filing=filing_metadata,
        )

        # Cache the result
        try:
            filing_record = db.query(Filing).filter(
                Filing.accession_number == accession_number
            ).first()

            if filing_record:
                if filing_record.content_cache:
                    # Update existing cache
                    filing_record.content_cache.markdown_content = result.markdown_content
                    filing_record.content_cache.markdown_sections = result.sections_extracted
                    filing_record.content_cache.markdown_generated_at = datetime.utcnow()
                else:
                    # Create new cache entry
                    cache = FilingContentCache(
                        filing_id=filing_record.id,
                        markdown_content=result.markdown_content,
                        markdown_sections=result.sections_extracted,
                        markdown_generated_at=datetime.utcnow(),
                    )
                    db.add(cache)
                db.commit()
                logger.info(f"Cached markdown for {ticker_upper}")
        except Exception as cache_error:
            logger.warning(f"Failed to cache markdown: {cache_error}")
            # Don't fail the request if caching fails

        return FilingMarkdownResponse(
            filing_date=result.filing_date,
            accession_number=result.accession_number,
            markdown_content=result.markdown_content,
            metadata=FilingMetadata(
                ticker=result.metadata.get("ticker", ticker_upper),
                company_name=result.metadata.get("company_name", ""),
                filing_type=result.metadata.get("filing_type", "10-Q"),
                fiscal_period=result.metadata.get("fiscal_period", ""),
                sections_extracted=result.sections_extracted,
            ),
        )

    except CompanyNotFoundError as e:
        logger.warning(f"Company not found: {ticker}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "CompanyNotFound",
                "message": str(e),
                "ticker": ticker_upper,
            }
        )

    except FilingNotFoundError as e:
        logger.warning(f"Filing not found for {ticker}: {e}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "FilingNotFound",
                "message": str(e),
                "ticker": ticker_upper,
            }
        )

    except SECRateLimitError as e:
        logger.error(f"SEC rate limit exceeded: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "RateLimitExceeded",
                "message": "SEC rate limit exceeded. Please try again in a few minutes.",
                "ticker": ticker_upper,
            }
        )

    except SECEdgarServiceError as e:
        logger.error(f"SEC service error: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SECServiceError",
                "message": "SEC EDGAR is temporarily unavailable. Please retry shortly.",
                "ticker": ticker_upper,
            }
        )

    except FilingParseError as e:
        logger.error(f"Filing parse error for {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ParseError",
                "message": f"Failed to parse filing: {e.reason}",
                "ticker": ticker_upper,
            }
        )

    except Exception as e:
        logger.exception(f"Unexpected error getting 10-Q markdown for {ticker}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": "An unexpected error occurred.",
                "ticker": ticker_upper,
            }
        )


@router.get("/{ticker}/10q/list", response_model=FilingListResponse)
async def list_10q_filings(
    ticker: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of filings to return"),
    include_amended: bool = Query(True, description="Include 10-Q/A amended filings"),
):
    """
    List available 10-Q filings for a company.

    Returns a list of 10-Q filings with metadata, allowing users
    to select a specific filing for markdown conversion.

    Args:
        ticker: Stock ticker symbol
        limit: Maximum filings to return (1-50)
        include_amended: Whether to include 10-Q/A filings

    Returns:
        FilingListResponse with list of available filings
    """
    ticker_upper = ticker.upper().strip()

    try:
        # Get company info
        company_info = await sec_client.get_company_info(ticker_upper)

        # Get filings list
        filings = await sec_client.get_10q_filings(
            ticker_upper,
            limit=limit,
            include_amended=include_amended,
        )

        filing_items = [
            FilingListItem(
                filing_type=f.get("filing_type", "10-Q"),
                filing_date=f.get("filing_date", ""),
                report_date=f.get("report_date"),
                accession_number=f.get("accession_number", ""),
                sec_url=f.get("sec_url", ""),
            )
            for f in filings
        ]

        return FilingListResponse(
            ticker=company_info.get("ticker", ticker_upper),
            company_name=company_info.get("name", ""),
            cik=company_info.get("cik", ""),
            filings=filing_items,
            total=len(filing_items),
        )

    except CompanyNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "CompanyNotFound",
                "message": str(e),
                "ticker": ticker_upper,
            }
        )

    except SECEdgarServiceError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SECServiceError",
                "message": "SEC EDGAR is temporarily unavailable.",
                "ticker": ticker_upper,
            }
        )

    except Exception as e:
        logger.exception(f"Error listing 10-Q filings for {ticker}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "InternalError",
                "message": "An unexpected error occurred.",
                "ticker": ticker_upper,
            }
        )

