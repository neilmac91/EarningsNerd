from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Company
from app.services.sec_edgar import sec_edgar_service
from pydantic import BaseModel
import httpx
import asyncio

router = APIRouter()

class StockQuote(BaseModel):
    price: Optional[float]
    change: Optional[float]
    change_percent: Optional[float]
    currency: Optional[str] = "USD"
    pre_market_price: Optional[float] = None
    pre_market_change: Optional[float] = None
    pre_market_change_percent: Optional[float] = None
    post_market_price: Optional[float] = None
    post_market_change: Optional[float] = None
    post_market_change_percent: Optional[float] = None

class CompanyResponse(BaseModel):
    id: int
    cik: str
    ticker: str
    name: str
    exchange: Optional[str]
    stock_quote: Optional[StockQuote] = None
    
    class Config:
        from_attributes = True

@router.get("/search", response_model=List[CompanyResponse])
async def search_companies(
    q: str = Query(..., min_length=1, description="Search query (company name or ticker)"),
    db: Session = Depends(get_db)
):
    """Search for companies by name or ticker"""
    try:
        # Search SEC database
        sec_results = await sec_edgar_service.search_company(q)
        
        if not sec_results:
            return []
        
        # Store or update companies in database
        companies = []
        for sec_data in sec_results:
            company = db.query(Company).filter(Company.cik == sec_data["cik"]).first()
            
            if not company:
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
                # Update if needed
                company.ticker = sec_data["ticker"]
                company.name = sec_data["name"]
                company.exchange = sec_data.get("exchange")
                db.commit()
            
            companies.append(company)
        
        # Fetch stock quotes for all companies in parallel (but don't fail if some fail)
        quote_tasks = [get_stock_quote(company.ticker) for company in companies]
        stock_quotes = await asyncio.gather(*quote_tasks, return_exceptions=True)
        
        # Create response with stock quotes
        result = []
        for i, company in enumerate(companies):
            quote = stock_quotes[i] if not isinstance(stock_quotes[i], Exception) else None
            result.append(CompanyResponse(
                id=company.id,
                cik=company.cik,
                ticker=company.ticker,
                name=company.name,
                exchange=company.exchange,
                stock_quote=quote
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching companies: {str(e)}")

@router.get("/trending", response_model=List[CompanyResponse])
async def get_trending_companies(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Get trending companies based on search/filing activity"""
    from sqlalchemy import func, desc
    from app.models import UserSearch, Filing
    
    # Get companies with most recent filings in the last 30 days
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    # Get companies with most filings in recent period
    trending_query = db.query(
        Company.id,
        Company.cik,
        Company.ticker,
        Company.name,
        Company.exchange,
        func.count(Filing.id).label('filing_count')
    ).join(
        Filing, Company.id == Filing.company_id
    ).filter(
        Filing.filing_date >= thirty_days_ago
    ).group_by(
        Company.id
    ).order_by(
        desc('filing_count')
    ).limit(limit).all()
    
    # Convert to CompanyResponse
    result = []
    for row in trending_query:
        quote = await get_stock_quote(row.ticker)
        result.append(CompanyResponse(
            id=row.id,
            cik=row.cik,
            ticker=row.ticker,
            name=row.name,
            exchange=row.exchange,
            stock_quote=quote
        ))
    
    return result

async def get_stock_quote(ticker: str) -> Optional[StockQuote]:
    """Fetch real-time stock quote from Yahoo Finance"""
    try:
        # Yahoo Finance API endpoint (free, no API key required)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://finance.yahoo.com/"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            
            # Check if response is valid JSON
            if response.headers.get("content-type", "").startswith("application/json"):
                data = response.json()
            else:
                # Try to parse anyway
                try:
                    data = response.json()
                except:
                    return None
            
            result = data.get("chart", {}).get("result", [])
            if not result:
                return None
            
            quote_data = result[0]
            meta = quote_data.get("meta", {})
            
            regular_market_price = meta.get("regularMarketPrice")
            previous_close = meta.get("previousClose")
            
            if regular_market_price is None or previous_close is None:
                return None
            
            change = regular_market_price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
            currency = meta.get("currency", "USD")
            
            # Pre-market data
            pre_market_price = meta.get("preMarketPrice")
            pre_market_change = None
            pre_market_change_percent = None
            if pre_market_price is not None:
                pre_market_change = pre_market_price - previous_close
                pre_market_change_percent = (pre_market_change / previous_close) * 100 if previous_close != 0 else 0
            
            # Post-market (after-hours) data
            post_market_price = meta.get("postMarketPrice")
            post_market_change = None
            post_market_change_percent = None
            if post_market_price is not None:
                post_market_change = post_market_price - previous_close
                post_market_change_percent = (post_market_change / previous_close) * 100 if previous_close != 0 else 0
            
            return StockQuote(
                price=round(regular_market_price, 2),
                change=round(change, 2),
                change_percent=round(change_percent, 2),
                currency=currency,
                pre_market_price=round(pre_market_price, 2) if pre_market_price is not None else None,
                pre_market_change=round(pre_market_change, 2) if pre_market_change is not None else None,
                pre_market_change_percent=round(pre_market_change_percent, 2) if pre_market_change_percent is not None else None,
                post_market_price=round(post_market_price, 2) if post_market_price is not None else None,
                post_market_change=round(post_market_change, 2) if post_market_change is not None else None,
                post_market_change_percent=round(post_market_change_percent, 2) if post_market_change_percent is not None else None
            )
    except httpx.HTTPError:
        # Network or HTTP errors - silently fail
        return None
    except Exception as e:
        # Silently fail - don't break the page if stock quote fails
        print(f"Error fetching stock quote for {ticker}: {str(e)}")
        return None

@router.get("/{ticker}", response_model=CompanyResponse)
async def get_company(ticker: str, db: Session = Depends(get_db)):
    """Get company by ticker"""
    company = db.query(Company).filter(Company.ticker == ticker.upper()).first()
    
    if not company:
        # Try to fetch from SEC
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}")
    
    # Fetch stock quote
    stock_quote = await get_stock_quote(company.ticker)
    
    # Create response with stock quote
    company_dict = {
        "id": company.id,
        "cik": company.cik,
        "ticker": company.ticker,
        "name": company.name,
        "exchange": company.exchange,
        "stock_quote": stock_quote
    }
    
    return CompanyResponse(**company_dict)

