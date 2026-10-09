from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Tuple
from app.database import get_db
from app.services import company_lookup_service
from app.services.company_coverage import UNSUPPORTED_FOREIGN_REASON, unsupported_foreign_name
# EdgarTools migration: Using new edgar module for SEC services
from app.services.edgar.compat import sec_edgar_service
from app.services.edgar.exceptions import EdgarError as SECEdgarServiceError
from app.services.latest_filing_service import LatestFilingRef
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.utils.datetimes import utcnow
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
# Lazy lock initialization for event loop safety (see xbrl_service.py pattern)
_yahoo_client_lock: Optional[asyncio.Lock] = None


def _get_yahoo_client_lock() -> asyncio.Lock:
    """Get or create the Yahoo client lock (lazy initialization for event loop safety)."""
    global _yahoo_client_lock
    if _yahoo_client_lock is None:
        _yahoo_client_lock = asyncio.Lock()
    return _yahoo_client_lock


def _get_cached_quote(ticker: str) -> Optional[StockQuote]:
    ticker_key = ticker.upper()
    cached = _quote_cache.get(ticker_key)
    if not cached:
        return None

    quote, cached_at = cached
    if utcnow() - cached_at > QUOTE_CACHE_TTL:
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

    _quote_cache[ticker_key] = (quote, utcnow())


async def _get_yahoo_client() -> httpx.AsyncClient:
    global _yahoo_client
    if _yahoo_client and not _yahoo_client.is_closed:
        return _yahoo_client

    async with _get_yahoo_client_lock():
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
    # Set to "unsupported_foreign" for a recognizable foreign issuer (unsponsored ADR) that files
    # no financial reports with the SEC — lets the frontend show an honest "coverage unavailable"
    # state instead of a bare "Company not found".
    coverage_status: Optional[str] = None
    coverage_reason: Optional[str] = None
    # Search only: the filing the company page leads with (latest_filing_service), so the results
    # can say which filing a pick lands on. Absent when no such filing is stored yet.
    latest_filing: Optional[LatestFilingRef] = None

    class Config:
        from_attributes = True


def _unsupported_foreign_response(ticker: str) -> Optional[CompanyResponse]:
    """Honest 'coverage unavailable' response for a known unsupported foreign name, else None.

    Returned BEFORE any SEC resolution so a recognizable ADR ticker can never fuzzy-match onto an
    unrelated reporting issuer (e.g. TCEHY/Tencent must NOT bind to TME/Tencent Music, a real 20-F
    filer at a different CIK). The synthesized response is never persisted to the DB. The curated
    set lives in ``app.services.company_coverage`` (the single source of truth).
    """
    name = unsupported_foreign_name(ticker)
    if not name:
        return None
    return CompanyResponse(
        id=0,
        cik="",
        ticker=(ticker or "").upper().strip(),
        name=name,
        exchange=None,
        stock_quote=None,
        coverage_status="unsupported_foreign",
        coverage_reason=UNSUPPORTED_FOREIGN_REASON,
    )

@router.get("/search", response_model=List[CompanyResponse])
async def search_companies(
    q: str = Query(..., min_length=1, description="Search query (company name or ticker)"),
    db: Session = Depends(get_db)
) -> List[CompanyResponse]:
    """Search for companies by name or ticker"""
    try:
        # Search SEC database
        sec_results = await sec_edgar_service.search_company(q)
        
        if not sec_results:
            return []

        # Resolve every external/cache-backed identity before the first database checkout.  The
        # integrity-recovery path reuses this frozen mapping instead of awaiting inside a
        # transaction.
        primary_by_cik: Dict[str, Optional[str]] = {}
        for sec_data in sec_results:
            cik = sec_data.get("cik")
            if cik and cik not in primary_by_cik:
                primary_by_cik[cik] = await sec_edgar_service.primary_ticker_for_cik(cik)
        
        # Store or update one row per CIK, in SEC result order (data-quality plan P0-1).
        try:
            companies = company_lookup_service.upsert_search_results(db, sec_results, primary_by_cik)
        except company_lookup_service.SearchUpsertConflict as conflict:
            # A concurrent request inserted one of these CIKs between our read and flush.
            logger.warning(
                "company_upsert_conflict cik=%s ticker=%s path=companies.search",
                ",".join(conflict.response_ciks),
                q,
            )
            companies = company_lookup_service.resolve_search_conflict(
                db, sec_results, primary_by_cik, conflict.response_ciks
            )

        company_rows, latest_by_company = company_lookup_service.release_search_rows(db, companies)

        # Fetch stock quotes for all companies in parallel (but don't fail if some fail)
        quote_tasks = [_get_stock_quote_with_timeout(row["ticker"]) for row in company_rows]
        stock_quotes = await asyncio.gather(*quote_tasks, return_exceptions=True)
        
        # Create response with stock quotes
        result = []
        for i, row in enumerate(company_rows):
            quote = stock_quotes[i] if not isinstance(stock_quotes[i], Exception) else None
            result.append(CompanyResponse(
                **row,
                stock_quote=quote,
                latest_filing=latest_by_company.get(row["id"]),
            ))
        
        return result
    except SECEdgarServiceError as e:
        logger.warning(f"SEC EDGAR error searching for '{q}': {e}")
        raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
    except Exception as e:
        logger.error(f"Unexpected error searching companies for '{q}': {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while searching for companies.") from e

@router.get("/trending", response_model=List[CompanyResponse])
async def get_trending_companies(
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db)
) -> List[CompanyResponse]:
    """Get trending companies based on search/filing activity"""
    company_rows = company_lookup_service.trending_company_rows(db, limit)

    # Convert to CompanyResponse
    result = []
    quote_tasks = [get_stock_quote(row["ticker"]) for row in company_rows]
    quotes = await asyncio.gather(*quote_tasks, return_exceptions=True) if quote_tasks else []

    for row, quote in zip(company_rows, quotes):
        resolved_quote = quote if not isinstance(quote, Exception) else None
        result.append(CompanyResponse(
            **row,
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
async def get_company(ticker: str, db: Session = Depends(get_db)) -> CompanyResponse:
    """Get company by ticker"""
    # Known unsupported foreign issuer → honest "coverage unavailable" state, checked BEFORE any DB
    # or SEC lookup so a recognizable ADR ticker can never resolve to a stale/polluted DB row or
    # fuzzy-match an unrelated reporting CIK (the TCEHY/Tencent → TME/Tencent Music guard). Not
    # persisted.
    unsupported = _unsupported_foreign_response(ticker)
    if unsupported is not None:
        return unsupported

    company_row = company_lookup_service.find_company_row_by_ticker(db, ticker)

    if company_row is None:
        # Try to fetch from SEC
        # The lookup released the initial SELECT's transaction before this SEC wait; the Session
        # is reusable for the short persistence unit below.
        try:
            sec_results = await sec_edgar_service.search_company(ticker)
            if sec_results:
                sec_data = sec_results[0]
                primary = await sec_edgar_service.primary_ticker_for_cik(sec_data["cik"])
                company = company_lookup_service.persist_sec_company(db, sec_data, primary)
            else:
                raise HTTPException(status_code=404, detail="Company not found")
        except SECEdgarServiceError as e:
            raise HTTPException(status_code=503, detail="SEC EDGAR is temporarily unavailable. Please retry shortly.") from e
        except HTTPException:
            # Let intended HTTP errors (e.g. the 404 above) propagate unchanged — the generic
            # handler below would otherwise wrap them as a 500.
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching company: {str(e)}") from e

        company_row = company_lookup_service.release_company_row(db, company)

    # Fetch stock quote
    stock_quote = await get_stock_quote(company_row["ticker"])
    
    # Create response with stock quote
    return CompanyResponse(**company_row, stock_quote=stock_quote)
