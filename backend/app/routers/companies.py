from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Tuple
from app.database import get_db
from app.models import Company
# EdgarTools migration: Using new edgar module for SEC services
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.exceptions import EdgarError as SECEdgarServiceError
from pydantic import BaseModel
from datetime import datetime, timedelta
import httpx
import asyncio
import atexit
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

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

QUOTE_CACHE_TTL = timedelta(seconds=120)
MAX_QUOTE_CACHE_SIZE = 256
QUOTE_TIMEOUT_SECONDS = 4.0
YAHOO_TIMEOUT = httpx.Timeout(3.0, connect=1.0, read=2.5)
YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com/",
}

_quote_cache: Dict[str, Tuple[StockQuote, datetime]] = {}
_yahoo_client: Optional[httpx.AsyncClient] = None
_yahoo_client_lock = asyncio.Lock()


def _get_cached_quote(ticker: str) -> Optional[StockQuote]:
    ticker_key = ticker.upper()
    cached = _quote_cache.get(ticker_key)
    if not cached:
        return None

    quote, cached_at = cached
    if datetime.utcnow() - cached_at > QUOTE_CACHE_TTL:
        _quote_cache.pop(ticker_key, None)
        return None

    return quote


def _store_cached_quote(ticker: str, quote: StockQuote) -> None:
    if not quote:
        return

    ticker_key = ticker.upper()
    if ticker_key not in _quote_cache and len(_quote_cache) >= MAX_QUOTE_CACHE_SIZE:
        oldest_key = next(iter(_quote_cache))
        _quote_cache.pop(oldest_key, None)

    _quote_cache[ticker_key] = (quote, datetime.utcnow())


async def _get_yahoo_client() -> httpx.AsyncClient:
    global _yahoo_client
    if _yahoo_client and not _yahoo_client.is_closed:
        return _yahoo_client

    async with _yahoo_client_lock:
        if _yahoo_client is None or _yahoo_client.is_closed:
            _yahoo_client = httpx.AsyncClient(
                timeout=YAHOO_TIMEOUT,
                headers=YAHOO_HEADERS,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
    return _yahoo_client


def _close_yahoo_client_sync() -> None:
    global _yahoo_client
    client = _yahoo_client
    if not client or client.is_closed:
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    async def _async_close():
        await client.aclose()

    try:
        if loop and loop.is_running():
            loop.create_task(_async_close())
        else:
            asyncio.run(_async_close())
    except (RuntimeError, Exception):
        # Ignore errors during shutdown/cleanup
        pass
    _yahoo_client = None


atexit.register(_close_yahoo_client_sync)


async def _get_stock_quote_with_timeout(ticker: str) -> Optional[StockQuote]:
    try:
        return await asyncio.wait_for(get_stock_quote(ticker), timeout=QUOTE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return None

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
        companies: List[Company] = []
        ciks = [result["cik"] for result in sec_results if result.get("cik")]
        existing_companies: Dict[str, Company] = {}
        if ciks:
            existing = db.query(Company).filter(Company.cik.in_(ciks)).all()
            existing_companies = {company.cik: company for company in existing}

        new_companies: List[Company] = []
        updated_companies: List[Company] = []

        for sec_data in sec_results:
            cik = sec_data.get("cik")
            if not cik:
                continue

            company = existing_companies.get(cik)
            if not company:
                company = Company(
                    cik=cik,
                    ticker=sec_data.get("ticker"),
                    name=sec_data.get("name"),
                    exchange=sec_data.get("exchange"),
                )
                db.add(company)
                new_companies.append(company)
            else:
                updated = False
                ticker = sec_data.get("ticker")
                name = sec_data.get("name")
                exchange = sec_data.get("exchange")

                if ticker and company.ticker != ticker:
                    company.ticker = ticker
                    updated = True
                if name and company.name != name:
                    company.name = name
                    updated = True
                if company.exchange != exchange:
                    company.exchange = exchange
                    updated = True

                if updated:
                    updated_companies.append(company)

            if company:
                companies.append(company)

        if new_companies or updated_companies:
            db.flush()
            db.commit()
            for company in new_companies:
                db.refresh(company)

        # Fetch stock quotes for all companies in parallel (but don't fail if some fail)
        quote_tasks = [_get_stock_quote_with_timeout(company.ticker) for company in companies]
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
    except SECEdgarServiceError as e:
        logger.warning(f"SEC EDGAR error searching for '{q}': {e}")
        raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.")
    except Exception as e:
        logger.error(f"Unexpected error searching companies for '{q}': {e}")
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
    quote_tasks = [get_stock_quote(row.ticker) for row in trending_query]
    quotes = await asyncio.gather(*quote_tasks, return_exceptions=True) if quote_tasks else []

    for row, quote in zip(trending_query, quotes):
        resolved_quote = quote if not isinstance(quote, Exception) else None
        result.append(CompanyResponse(
            id=row.id,
            cik=row.cik,
            ticker=row.ticker,
            name=row.name,
            exchange=row.exchange,
            stock_quote=resolved_quote
        ))

    return result

async def get_stock_quote(ticker: str) -> Optional[StockQuote]:
    """Fetch real-time stock quote from Yahoo Finance"""
    cached_quote = _get_cached_quote(ticker)
    if cached_quote:
        return cached_quote

    try:
        ticker_key = ticker.upper()
        # Yahoo Finance API endpoint (free, no API key required)
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_key}"
        client = await _get_yahoo_client()
        response = await client.get(url)
        response.raise_for_status()

        # Check if response is valid JSON
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
        else:
            # Try to parse anyway
            try:
                data = response.json()
            except ValueError:
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

        quote = StockQuote(
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
        _store_cached_quote(ticker_key, quote)
        return quote
    except httpx.TimeoutException:
        return None
    except httpx.HTTPError:
        # Network or HTTP errors - silently fail
        return None
    except Exception as e:
        # Silently fail - don't break the page if stock quote fails
        if ticker:
            logger.error(f"Error fetching stock quote for {ticker}: {str(e)}")
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
        except SECEdgarServiceError as e:
            raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}") from e
    
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

